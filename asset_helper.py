"""Manifest-driven, cached image and OBJ wireframe assets for the loadout UI."""
from __future__ import annotations

import json
import math
import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QImageReader
from model_assets import load_model, import_model_bundle
from app_paths import writable_resources


class TaskSignals(QObject):
    finished = pyqtSignal(object, object, str)


class AssetTask(QRunnable):
    def __init__(self,key,function):
        super().__init__()
        self.key,self.function = key,function
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.key,self.function(),'')
        except Exception as exc:
            self.signals.finished.emit(self.key,None,str(exc))


class AssetLibrary(QObject):
    model_ready = pyqtSignal(str, object, str)
    invalidated = pyqtSignal()

    def __init__(self, root=None):
        super().__init__()
        self.root = Path(root or writable_resources('assets')).resolve()
        self.manifest = {}
        self.errors = []
        self._images = {}
        self._models = {}
        self._scenes = {}
        self._tasks = {}
        self._generation = 0
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.reload()

    def reload(self, force=True):
        self.errors.clear()
        try:
            data = json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('items', {}), dict):
                raise ValueError('Manifest must contain an items object')
        except (OSError, ValueError) as exc:
            self.errors.append(str(exc))
            # Keep the last valid assignments when an external edit is invalid.
            # A subsequent save must not silently erase the user's library.
            return
        changed = data != self.manifest
        self.manifest = data
        if force or changed:
            self._images.clear()
            self._models.clear()
            self._scenes.clear()
            self._generation += 1
            self.invalidated.emit()

    def path(self, value):
        if not isinstance(value, str) or not value:
            return None
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            self.errors.append('Asset paths must stay inside assets/')
            return None
        return path if path.is_file() else None

    def entry(self, name):
        data = self.manifest.get('items', {}).get(name, {})
        return data if isinstance(data, dict) else {}

    def save_manifest(self, data):
        """Atomically replace the manifest, then invalidate all cached assets."""
        if not isinstance(data, dict) or not isinstance(data.get('items', {}), dict):
            raise ValueError('Manifest must be an object with an items object')
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / ('manifest-'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temporary.replace(self.root / 'manifest.json')
        self.reload()

    def import_file(self, filename, kind='icon'):
        """Copy a source into the managed folder and return its manifest path."""
        source = Path(filename).resolve()
        if kind == 'model':
            return import_model_bundle(source,self.root)[0]
        allowed = {'.png','.jpg','.jpeg','.webp','.svg','.bmp'}
        if not source.is_file() or source.suffix.lower() not in allowed:
            raise ValueError('Unsupported or missing asset file')
        folder = self.root / ('backgrounds' if kind == 'background' else 'textures' if kind == 'texture' else 'icons')
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (uuid.uuid4().hex[:8]+'-'+source.name)
        shutil.copy2(source, target)
        return target.relative_to(self.root).as_posix()

    def set_item(self, name, *, icon=None, model=None, texture=None, rotation=None,texture_mode=None):
        """Assign assets using paths relative to assets/. Existing fields survive."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Item name is required')
        data = json.loads(json.dumps(self.manifest))
        entry = data.setdefault('items', {}).setdefault(name, {})
        if texture_mode is not None:
            if texture_mode not in ('automatic','override'):raise ValueError('Texture mode must be automatic or override')
            entry['texture_mode']=texture_mode
        for key, value in [('icon', icon), ('model', model), ('texture',texture)]:
            if value is not None:
                if self.path(value) is None:
                    raise ValueError(f'Missing {key} asset: {value}')
                entry[key] = value
        if rotation is not None:
            if len(rotation) != 3 or not all(math.isfinite(float(v)) for v in rotation):
                raise ValueError('Rotation must contain three finite degrees')
            entry['rotation'] = list(rotation)
        self.save_manifest(data)

    def set_background(self, image, opacity=0.55):
        if self.path(image) is None:
            raise ValueError('Background image does not exist inside assets/')
        data = json.loads(json.dumps(self.manifest))
        data.update(background=image, background_opacity=max(0.0, min(1.0, float(opacity))))
        self.save_manifest(data)

    def image(self, value):
        path = self.path(value)
        if path is None:
            return QPixmap()
        stamp = (str(path), path.stat().st_mtime_ns)
        if stamp not in self._images:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid() and max(size.width(),size.height())>2048:
                size.scale(QSize(2048,2048),Qt.AspectRatioMode.KeepAspectRatio)
                reader.setScaledSize(size)
            self._images[stamp] = QPixmap.fromImage(reader.read())
        return self._images[stamp]

    def paint_image(self, painter, rect, value, cover=False):
        image = self.image(value)
        if image.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return False
        ratio = (max if cover else min)(rect.width()/image.width(), rect.height()/image.height())
        target = QRectF(0, 0, image.width()*ratio, image.height()*ratio)
        target.moveCenter(rect.center())
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(target, image, QRectF(image.rect()))
        painter.restore()
        return True

    def icon(self, name, size=QSize(128, 80), dpr=1.0):
        """Centered transparent canvas, with native aspect ratio and DPI scaling."""
        canvas = QPixmap(max(1, round(size.width()*dpr)), max(1, round(size.height()*dpr)))
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        self.paint_image(painter, QRectF(QPointF(0, 0), QSize(size).toSizeF()), self.entry(name).get('icon'))
        painter.end()
        return QIcon(canvas)

    def model(self, name):
        """Explicit synchronous compatibility API. Viewports use request_model instead."""
        path = self.path(self.entry(name).get('model'))
        if path is None:
            return None
        key = (str(path),path.stat().st_mtime_ns,str(self.entry(name).get('rotation',[0,0,0])))
        if key not in self._models:
            try:
                self._models[key] = load_model(path,self.entry(name).get('rotation',[0,0,0]),self.root).preview_edges
            except (OSError,ValueError,TypeError) as exc:
                self.errors.append(str(exc))
                self._models[key] = None
        return self._models[key]

    def request_model(self,name):
        entry = dict(self.entry(name))
        value = entry.get('model')
        if not value:
            self.model_ready.emit(name,None,'')
            return
        key = (self._generation,name,json.dumps(entry,sort_keys=True))
        if key in self._scenes:
            scene,error = self._scenes[key]
            self.model_ready.emit(name,scene,error)
            return
        if key in self._tasks:
            return
        def load():
            path = self.path(value)
            if path is None:
                raise ValueError('Model file is missing; choose Assign 3D Model again')
            texture = self.path(entry.get('texture')) if entry.get('texture') and entry.get('texture_mode')!='automatic' else None
            return load_model(path,entry.get('rotation',[0,0,0]),self.root,texture,prefer_materials=entry.get('texture_mode','automatic')!='override')
        task = AssetTask(key,load)
        self._tasks[key] = task
        task.signals.finished.connect(self._model_loaded)
        self.pool.start(task)

    def _model_loaded(self,key,scene,error):
        self._tasks.pop(key,None)
        if key[0] != self._generation:
            return
        self._scenes[key] = (scene,error)
        if len(self._scenes)>6:
            self._scenes.pop(next(iter(self._scenes)))
        def cost(value):
            model = value[0]
            if model is None:
                return 0
            return len(model.vertices)*128+sum(len(b)*4 for b in model.batches.values())+sum(
                m['image'].sizeInBytes() for m in model.materials.values() if m.get('image') is not None)
        while len(self._scenes)>1 and sum(cost(value) for value in self._scenes.values())>192_000_000:
            self._scenes.pop(next(iter(self._scenes)))
        if error:
            self.errors.append(error)
        self.model_ready.emit(key[1],scene,error)



ASSETS = AssetLibrary()
