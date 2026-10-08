"""Asynchronous loading, texture imports, bounded fallback, aspect-ratio regression tests."""
import json
import math
import tempfile
import time
import unittest
from threading import Event
from unittest.mock import patch
import asset_helper
from pathlib import Path

from test_orchestration import APP,wait_until
from PyQt6.QtCore import QTimer,QSize,Qt
from PyQt6.QtGui import QImage,QColor
from asset_helper import ASSETS,AssetLibrary
from model_assets import import_model_bundle,load_obj,map_filename
from model_preview import InteractiveModelCanvas
from types import SimpleNamespace


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def textured_obj(self):
        folder = self.root/'source'
        folder.mkdir()
        textures = folder/'textures'
        textures.mkdir()
        image = QImage(256,128,QImage.Format.Format_RGB32)
        image.fill(QColor('#f06413'))
        image.save(str(textures/'base color.png'))
        (folder/'material.mtl').write_text('newmtl orange\nKd 0.8 0.2 0.1\nmap_Kd -s 1 1 1 "textures/base color.png"\n')
        obj = folder/'mesh.obj'
        obj.write_text('mtllib material.mtl\nv -1 -1 0\nv 1 -1 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0.5 1\nusemtl orange\nf 1/1 2/2 3/3\n')
        return obj

    def test_bundle_keeps_materials_textures_and_uvs(self):
        obj = self.textured_obj()
        target = self.root/'assets'
        relative,warnings = import_model_bundle(obj,target)
        self.assertEqual(warnings,[])
        scene = load_obj(target/relative,root=target)
        self.assertEqual(scene.source_faces,1)
        self.assertIsNotNone(scene.materials['orange']['image'])
        self.assertEqual(scene.materials['orange']['image'].pixelColor(10,10).name(),'#f06413')
        self.assertTrue(scene.preview_triangles[0][3])
        self.assertEqual(len(scene.batches[('orange',True)]),24)
        self.assertEqual(map_filename(r'-s 1 1 1 textures\base.png'),'textures/base.png')

    def test_async_loading_keeps_event_loop_and_bounds_render(self):
        obj = self.root/'large.obj'
        with obj.open('w') as stream:
            for i in range(18000):
                x = i%100
                y = i//100
                stream.write(f'v {x} {y} 0\nv {x+0.7} {y} 0\nv {x} {y+0.7} 0\n')
            for i in range(18000):
                n = i*3+1
                stream.write(f'f {n} {n+1} {n+2}\n')
        library = AssetLibrary(self.root)
        library.manifest = {'items':{'large':{'model':'large.obj'}}}
        result = []
        library.model_ready.connect(lambda name,scene,error:result.append((scene,error)))
        ticks = []
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda:ticks.append(time.monotonic()))
        timer.start()
        # Hold the worker until the GUI timer has demonstrably progressed.
        # Fast loads can otherwise finish before three timer deliveries.
        release = Event()
        actual_load = asset_helper.load_model
        def gated_load(*args, **kwargs):
            if not release.wait(10):
                raise RuntimeError('Test worker was not released')
            return actual_load(*args, **kwargs)
        try:
            with patch('asset_helper.load_model', side_effect=gated_load):
                begin = time.perf_counter()
                library.request_model('large')
                self.assertLess(time.perf_counter()-begin,0.1)
                wait_until(lambda:len(ticks)>2,5)
                self.assertFalse(result)
                release.set()
                wait_until(lambda:bool(result),15)
        finally:
            release.set()
            timer.stop()
        scene,error = result[0]
        self.assertEqual(error,'')
        self.assertGreater(len(ticks),2)
        self.assertLessEqual(len(scene.preview_edges),1200)
        self.assertLessEqual(len(scene.preview_triangles),400)
        self.assertEqual(scene.source_faces,18000)
        canvas = InteractiveModelCanvas()
        canvas.resize(640,380)
        canvas.item_data = SimpleNamespace(name='large',category='PYTHON PROJECT')
        canvas.loaded('large',scene,'')
        canvas.show()
        APP.processEvents()
        canvas.grab()
        self.assertLess(canvas.last_paint_ms,120)
        canvas.hide()
        canvas.deleteLater()
        library.pool.waitForDone()

    def test_missing_resources_and_invalid_geometry_are_explanatory(self):
        obj = self.textured_obj()
        (obj.parent/'textures'/'base color.png').unlink()
        scene = load_obj(obj)
        self.assertTrue(any('Missing texture' in warning for warning in scene.warnings))
        bad = self.root/'bad.obj'
        bad.write_text('v 0 0 0\nv 1 0 0\nf 1 2 999\n')
        with self.assertRaisesRegex(ValueError,'invalid vertex'):
            load_obj(bad)

    def test_texture_override_and_image_fit(self):
        obj = self.textured_obj()
        override = QImage(16,16,QImage.Format.Format_RGB32)
        override.fill(QColor('#26d8ee'))
        path = self.root/'override.png'
        override.save(str(path))
        scene = load_obj(obj,texture=path)
        self.assertEqual(scene.materials['orange']['image'].pixelColor(1,1).name(),'#26d8ee')
        library = AssetLibrary(obj.parent)
        library.manifest = {'items':{'test':{'icon':'textures/base color.png'}}}
        icon = library.icon('test',QSize(200,200)).pixmap(QSize(200,200)).toImage()
        self.assertEqual(icon.pixelColor(100,10).alpha(),0)
        self.assertGreater(icon.pixelColor(100,100).alpha(),0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
