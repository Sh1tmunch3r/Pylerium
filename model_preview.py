"""Responsive shared preview, with asynchronous scene loading and bounded fallback."""
import math
import os
import time
from threading import Event

from PyQt6.QtCore import QLineF,QPointF,QRectF,Qt,QTimer,QThreadPool,pyqtSignal
from PyQt6.QtGui import QColor,QFont,QPainter,QPen,QRadialGradient,QImage
from PyQt6.QtWidgets import QApplication,QWidget,QMenu,QFileDialog

from asset_helper import ASSETS,AssetTask
from model_renderer import SoftwareModelRenderer
from model_offscreen import RenderWorker


class InteractiveModelCanvas(QWidget):
    model_status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.item_data = None
        self.scene = None
        self.rotation,self.elevation,self.zoom = 0.0,-0.28,1.0
        self.paused,self.profile_mode,self.textured = False,False,True
        self.drag_position = None
        self.last_frame = time.monotonic()
        self.sync_until = 0.0
        self.loading = False
        self.message = 'Choose an item to preview.'
        self.gpu = None
        self.gpu_failed = False
        self.texture_pixmaps = {}
        self.last_paint_ms = 0.0
        self.renderer = None
        self.render_task = None
        self.render_cancel = Event()
        self.render_generation = 0
        self.surface_frame = None
        self.surface_key = None
        self.render_ms = 0.0
        self.last_render_status=0.0
        self.quality = 2560
        self.render_worker = None
        self.pan = QPointF()
        self.pan_drag = False
        self.show_grid = True
        preferences=getattr(type(self),'default_preferences',{})
        self.show_grid=preferences.get('model_grid',True);self.quality=preferences.get('model_quality',2560)
        self.orbit_speed=preferences.get('model_orbit_speed',100)/100
        self.paused=not(preferences.get('motion',True) and preferences.get('model_auto_orbit',True))
        self.fit_factor = 1.0
        self.pan_moved = False
        self.setMinimumHeight(250)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip('Drag to orbit • Right/middle drag to pan • Scroll to zoom • Space pauses • F fits • Right-click for view/quality/export')
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.animate)
        ASSETS.model_ready.connect(self.loaded)
        ASSETS.invalidated.connect(self.reload_model)

    def set_item(self,data):
        if self.item_data is None or getattr(self.item_data,'asset_key',self.item_data.name)!=getattr(data,'asset_key',data.name):
            self.rotation,self.elevation,self.zoom=.7,-.18,1.0;self.pan=QPointF()
        self.item_data = data
        self.sync_until = time.monotonic()+0.6
        self.reload_model()

    def reload_model(self):
        if self.item_data is None:
            return
        self.scene = None
        self.clear_surface()
        self.texture_pixmaps.clear()
        if self.gpu:
            self.gpu.hide()
        key = getattr(self.item_data,'asset_key',self.item_data.name)
        self.loading = bool(ASSETS.entry(key).get('model'))
        self.set_status('Loading model and textures in the background…' if self.loading else 'Procedural preview — assign a model in Assets to customize this item.')
        ASSETS.request_model(key)
        self.update()

    def set_status(self,text):
        self.message = text
        self.model_status.emit(text)

    def loaded(self,name,scene,error):
        if self.item_data is None or name!=getattr(self.item_data,'asset_key',self.item_data.name):
            return
        if scene is not None and scene is self.scene and not self.loading and not error:
            return
        self.loading = False
        self.scene = scene
        self.clear_surface()
        self.texture_pixmaps.clear()
        if error:
            self.set_status('Model could not load: '+error+'. Procedural preview remains available.')
        elif scene:
            self.fit_model()
            textures = sum(m['image'] is not None for m in scene.materials.values())
            self.ensure_gpu()
            self.set_status(f'Preparing sharp preview • {scene.source_faces:,} triangles • {textures} textured materials'+
                (' • '+ '; '.join(scene.warnings) if scene.warnings else ' • Model fitted automatically'))
            if self.gpu:
                self.gpu.set_scene(scene)
        self.update_gpu_visibility()
        self.update()

    def clear_surface(self):
        self.render_cancel.set()
        self.render_cancel = Event()
        self.render_generation += 1
        self.renderer = self.surface_frame = self.surface_key = None
        self.render_task=None
        self.last_render_status=0.0

    def request_surface(self):
        if self.render_task is not None or not self.scene or not self.scene.batches or not self.textured or self.profile_mode:
            return
        key=(self.render_generation,self.width(),self.height(),self.rotation,self.elevation,self.zoom,
               self.drag_position is not None,self.quality,self.pan.x(),self.pan.y(),self.paused,self.fit_factor,self.devicePixelRatioF())
        if key==self.surface_key:
            return
        # Full device resolution is the default; speed controls are explicit.
        # Never silently turn an orbiting textured model into a 480-pixel image.
        maximum=min(self.quality,1440) if key[6] else self.quality
        supersampling=2 if self.quality>=4096 and self.paused and not key[6] else 1
        ratio=min(self.devicePixelRatioF()*supersampling,maximum/max(self.width(),self.height()))
        width,height=max(1,round(self.width()*ratio)),max(1,round(self.height()*ratio))
        if self.render_worker is None:
            self.render_worker=RenderWorker(self);self.render_worker.finished.connect(self.surface_ready)
        self.render_task=key
        self.render_worker.submit(self.scene,key,dict(width=width,height=height,rotation=key[3],elevation=key[4],zoom=key[5],viewport=(key[1],key[2]),pan=(key[8],key[9]),framing=key[11]),self.render_cancel)

    def surface_ready(self,key,result,error):
        if key!=self.render_task:return
        self.render_task=None
        if error:
            self.set_status('Surface preview unavailable: '+error)
            self.textured=False
        elif result and result[1] is not None:
            self.renderer,self.surface_frame,self.render_ms=result
            self.surface_key=key
            if time.monotonic()-self.last_render_status>1:
                self.last_render_status=time.monotonic()
                self.model_status.emit(f'{self.renderer.name} • {self.scene.source_faces:,} triangles • {self.surface_frame.width()}×{self.surface_frame.height()} • {self.render_ms:.1f} ms/frame'+(' • '+ '; '.join(self.scene.warnings) if self.scene.warnings else ''))
        self.update()
        # Do not build up a queue: the next request always uses the newest orbit.
        if self.isVisible(): self.request_surface()

    def ensure_gpu(self):
        # Dynamic native GL children can recreate Windows' top-level surface and
        # break popup/window state. Keep the bounded textured renderer as default.
        if os.environ.get('PYLERIUM_NATIVE_GL') != '1' or self.gpu_failed or QApplication.platformName() in ('offscreen','minimal'):
            return False
        if self.gpu:
            return True
        try:
            from model_gpu import GpuModelView
            self.gpu = GpuModelView(self)
            self.gpu.failed.connect(self.gpu_error)
            self.gpu.ready.connect(lambda:self.model_status.emit(self.message))
            self.resize_gpu()
            return True
        except (ImportError,RuntimeError) as exc:
            self.gpu_failed = True
            return False

    def gpu_error(self,error):
        self.gpu_failed = True
        if self.gpu:
            QTimer.singleShot(0,self.gpu.hide)
        self.set_status('GPU unavailable — using a bounded software preview. Textures and orbit controls remain available.')
        self.setToolTip(self.message+'\n'+error)
        self.update()

    def update_gpu_visibility(self):
        if self.gpu:
            self.gpu.setVisible(self.scene is not None and not self.profile_mode and not self.gpu_failed)
            self.gpu.update()

    def resize_gpu(self):
        if self.gpu:
            self.gpu.setGeometry(12,35,max(1,self.width()-24),max(1,self.height()-70))

    def resizeEvent(self,event):
        self.fit_model()
        self.resize_gpu()
        super().resizeEvent(event)

    def showEvent(self,event):
        if self.render_cancel.is_set():
            self.render_cancel=Event(); self.render_generation+=1; self.surface_key=None
        self.last_frame = time.monotonic()
        self.timer.start(16)
        super().showEvent(event)

    def hideEvent(self,event):
        self.render_cancel.set()
        if self.render_worker:
            self.render_worker.stop();self.render_worker=None
        self.render_task=None
        self.timer.stop()
        super().hideEvent(event)

    def animate(self):
        now = time.monotonic()
        dt = min(now-self.last_frame,0.1)
        self.last_frame = now
        modal=QApplication.activeModalWidget()
        if QApplication.activePopupWidget() or modal and not modal.isAncestorOf(self):
            return
        moving=not self.paused and self.drag_position is None
        if moving:
            self.rotation = (self.rotation+dt*0.22*getattr(self,'orbit_speed',1.0))%math.tau
        if self.paused and self.surface_key is not None and not self.gpu:
            return
        self.update_gpu_visibility()
        self.update()

    def reset_view(self):
        self.rotation,self.elevation,self.zoom = 0.0,-0.28,1.0
        self.pan=QPointF()
        self.fit_model()
        self.update_gpu_visibility()
        self.update()

    def shutdown_renderer(self):
        self.render_cancel.set()
        if self.render_worker:self.render_worker.stop();self.render_worker=None
        self.render_task=None;self.timer.stop()

    def mousePressEvent(self,event):
        if event.button() in (Qt.MouseButton.LeftButton,Qt.MouseButton.MiddleButton,Qt.MouseButton.RightButton):
            self.pan_drag=event.button()!=Qt.MouseButton.LeftButton
            self.pan_moved=False
            self.drag_position = event.position()
            self.setFocus()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self,event):
        if self.drag_position is not None:
            delta = event.position()-self.drag_position
            if self.pan_drag:
                self.pan+=delta
                if abs(delta.x())+abs(delta.y())>2:self.pan_moved=True
            else:
                self.rotation += delta.x()*0.009
                self.elevation = max(-math.pi/2,min(math.pi/2,self.elevation+delta.y()*0.006))
            self.drag_position = event.position()
            self.update_gpu_visibility()
            self.update()

    def mouseReleaseEvent(self,event):
        if event.button() in (Qt.MouseButton.LeftButton,Qt.MouseButton.MiddleButton,Qt.MouseButton.RightButton):
            self.drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()

    def mouseDoubleClickEvent(self,event):
        self.reset_view()

    def wheelEvent(self,event):
        self.zoom = max(0.2,min(4.0,self.zoom*math.exp(event.angleDelta().y()/1200)))
        self.update_gpu_visibility()
        self.update()
        event.accept()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Space:
            self.paused = not self.paused
            self.surface_key=None
            self.update()
            event.accept()
        elif event.key()==Qt.Key.Key_F:
            self.reset_view(); event.accept()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self,event):
        if self.pan_moved:
            self.pan_moved=False;event.accept();return
        menu=QMenu(self)
        menu.addAction('Inspect weapon / model',self.inspect_weapon)
        for title,rotation,elevation in [('Front',0,0),('Back',math.pi,0),('Left',-math.pi/2,0),('Right',math.pi/2,0),('Top',0,math.pi/2),('Perspective',.65,-.28)]:
            menu.addAction(title,lambda checked=False,r=rotation,e=elevation:self.set_camera(r,e))
        menu.addAction('Fit model',self.reset_view)
        quality=menu.addMenu('Surface quality')
        for title,size in [('Fast',960),('Native / sharp',2560),('Studio',4096)]:
            action=quality.addAction(title,lambda checked=False,n=size:self.set_quality(n))
            action.setCheckable(True);action.setChecked(self.quality==size)
        menu.addAction('Toggle floor grid',self.toggle_grid)
        menu.addAction('Export preview PNG',self.export_preview)
        menu.exec(event.globalPos())

    def inspect_weapon(self):
        from model_inspector import InspectWeaponDialog
        dialog=InspectWeaponDialog(self,self)
        dialog.exec()

    def set_camera(self,rotation,elevation):
        self.paused=True;self.rotation=rotation;self.elevation=elevation
        self.pan=QPointF();self.fit_model();self.surface_key=None;self.update_gpu_visibility();self.update()

    def fit_model(self):
        self.fit_factor=1.0
        if not self.scene or not self.scene.bounds:return
        points=[self.project(vertex)[0] for vertex in self.scene.bounds]
        width=max(point.x() for point in points)-min(point.x() for point in points)
        height=max(point.y() for point in points)-min(point.y() for point in points)
        # Fit the actual projected bounds, rather than a sphere that makes long,
        # thin assets tiny. Eight corners keep fitting cheap on the GUI thread.
        self.fit_factor=max(.4,min(4.0,.90*min(max(1,self.width()-60)/max(1,width),max(1,self.height()-80)/max(1,height))))*self.zoom

    def set_quality(self,size):
        self.quality=size;self.surface_key=None;self.update()

    def toggle_grid(self):
        self.show_grid=not self.show_grid;self.update()

    def export_preview(self):
        filename,_=QFileDialog.getSaveFileName(self,'Export model preview','model-preview.png','PNG (*.png)')
        if not filename:return
        if self.surface_frame is not None:
            image=QImage(self.surface_frame.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent)
            painter=QPainter(image);painter.scale(image.width()/self.width(),image.height()/self.height())
            self.render(painter);painter.end();saved=image.save(filename,'PNG')
        else:saved=self.grab().save(filename,'PNG')
        if not saved:self.set_status('Could not save preview image')

    def project(self,vertex):
        x,y,z = vertex
        c,s = math.cos(self.rotation),math.sin(self.rotation)
        x,z = x*c+z*s,-x*s+z*c
        c,s = math.cos(self.elevation),math.sin(self.elevation)
        y,z = y*c-z*s,y*s+z*c
        radius = self.scene.radius if self.scene else 2.0
        distance = max(5.5,radius*3.4)
        scale = max(1,min(self.width()-40,self.height()-85))*2.0*self.zoom*self.fit_factor/(distance+z)
        return QPointF(self.width()/2+x*scale+self.pan.x(),self.height()*0.49-y*scale+self.pan.y()),z

    def geometry(self):
        if self.scene:
            return self.scene.preview_edges
        category = self.item_data.category if self.item_data else ''
        if 'RIFLE' in category or 'GUN' in category or category=='PISTOL':
            boxes = [(-0.65,0.1,0,1.4,0.35,0.3),(0.85,0.12,0,1.25,0.1,0.1),
                     (-1.35,0.02,0,0.5,0.45,0.25),(0,-0.4,0,0.25,0.65,0.22),
                     (0.42,-0.3,0,0.18,0.45,0.2)]
        elif category=='MELEE':
            boxes = [(-0.8,0,0,0.8,0.22,0.2),(0.35,0,0,1.4,0.28,0.06)]
        else:
            boxes = [(0,0,0,1.1,1.25,0.8),(0,0.75,0,0.5,0.18,0.4)]
        segments = []
        for cx,cy,cz,w,h,d in boxes:
            v = [(cx+dx*w/2,cy+dy*h/2,cz+dz*d/2) for dx in (-1,1) for dy in (-1,1) for dz in (-1,1)]
            for i in range(8):
                for bit in (1,2,4):
                    j = i^bit
                    if i<j:
                        segments.append((v[i],v[j]))
        return segments

    def paintEvent(self,event):
        start = time.perf_counter()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#0b0c0e'))
        glow = QRadialGradient(QPointF(self.width()/2,self.height()/2),self.width()*0.65)
        glow.setColorAt(0,QColor(20,85,100,65)); glow.setColorAt(1,QColor(0,0,0,0))
        p.fillRect(self.rect(),glow)
        p.setClipRect(self.rect().adjusted(12,35,-12,-35))
        gpu_active = self.gpu is not None and not self.gpu_failed and self.scene and not self.profile_mode
        if not gpu_active:
            p.setPen(QPen(QColor(38,216,238,35),1))
            floor = []
            for i in range(-8,9):
                n = i*0.4
                for a,b in [((n,-1.7,-3.2),(n,-1.7,3.2)),((-3.2,-1.7,n),(3.2,-1.7,n))]:
                    floor.append(QLineF(self.project(a)[0],self.project(b)[0]))
            if self.show_grid: p.drawLines(floor)
            if self.profile_mode and self.item_data:
                values = [getattr(self.item_data,k,0) for k in ('damage','firepower','accuracy','mobility','handling','range_stat')]
                segments = []
                for i,value in enumerate(values):
                    x,top = (i-2.5)*0.55,-0.8+value/65
                    for z in (-0.3,0.3):
                        segments.extend([((x,-0.8,z),(x,top,z)),((x,top,z),(x+0.3,top,z)),((x+0.3,top,z),(x+0.3,-0.8,z))])
            else:
                segments = self.geometry()
                if self.scene and self.textured:
                    self.request_surface()
                    if self.surface_frame is not None:
                        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                        p.drawImage(QRectF(self.rect()),self.surface_frame)
                        segments=[]
            if segments:
                p.setPen(QPen(QColor(80,225,240,170),1))
                p.drawLines([QLineF(self.project(a)[0],self.project(b)[0]) for a,b in segments])
        p.setClipping(False)
        if not self.paused:
            p.setPen(QPen(QColor(240,100,19,115),1))
            if not gpu_active:
                scan_y = 40+(self.rotation%math.tau)/math.tau*max(1,self.height()-80)
                p.drawLine(QPointF(15,scan_y),QPointF(self.width()-15,scan_y))
            else:
                p.drawLine(22,33,self.width()-22,33)
        p.setPen(QPen(QColor(145,170,180,170),1))
        for x,y,dx,dy in [(10,10,1,1),(self.width()-10,10,-1,1),(10,self.height()-10,1,-1),(self.width()-10,self.height()-10,-1,-1)]:
            p.drawLine(x,y,x+dx*16,y); p.drawLine(x,y,x,y+dy*16)
        p.setFont(QFont('Consolas',8)); p.setPen(QColor('#26d8ee'))
        status = 'LOADING MODEL…' if self.loading else 'PAUSED' if self.paused else 'AUTO ORBIT'
        p.drawText(QRectF(22,12,self.width()-44,20),Qt.AlignmentFlag.AlignLeft,status)
        p.setPen(QColor('#9a9a9a'))
        mode = 'STAT PROFILE' if self.profile_mode else 'TEXTURED' if self.scene and self.textured else 'WIREFRAME'
        accelerated=gpu_active or self.renderer and self.renderer.is_gpu
        p.drawText(QRectF(22,self.height()-30,self.width()-44,20),Qt.AlignmentFlag.AlignLeft,f'{mode} / {"GPU" if accelerated else "SOFTWARE"} / {self.zoom:.1f}x')
        p.end()
        self.last_paint_ms = (time.perf_counter()-start)*1000
