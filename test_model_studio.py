import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import numpy as np
import trimesh
from PIL import Image
from PyQt6.QtGui import QImage,QColor
from test_orchestration import APP,wait_until
from model_assets import load_model,load_obj,import_model_bundle
from model_offscreen import OffscreenRenderer
from model_preview import InteractiveModelCanvas
from model_inspector import InspectWeaponDialog
from unittest.mock import patch


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def triangle(self):
        mesh=trimesh.Trimesh(vertices=[[-1,-1,0],[1,-1,0],[0,1,0]],faces=[[0,1,2]],process=False)
        mesh.visual=trimesh.visual.TextureVisuals(uv=[[0,0],[1,0],[.5,1]],image=Image.new('RGB',(64,64),'red'))
        path=self.root/'mesh.glb';path.write_bytes(trimesh.Scene(mesh).export(file_type='glb'));return path

    def test_automatic_images_win_and_explicit_override_remains_available(self):
        path=self.triangle();fallback=self.root/'fallback.png';Image.new('RGB',(64,64),'blue').save(fallback)
        automatic=load_model(path,texture=fallback)
        self.assertEqual(next(iter(automatic.materials.values()))['image'].pixelColor(0,0).name(),'#ff0000')
        overridden=load_model(path,texture=fallback,prefer_materials=False)
        self.assertEqual(next(iter(overridden.materials.values()))['image'].pixelColor(0,0).name(),'#0000ff')

    def test_companion_import_and_authored_obj_normals(self):
        image=QImage(64,64,QImage.Format.Format_RGB32);image.fill(QColor('green'));image.save(str(self.root/'weapon_basecolor.png'))
        obj=self.root/'weapon.obj'
        obj.write_text('v -1 -1 0\nv 1 -1 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt .5 1\nvn 0 1 0\nusemtl body\nf 1/1/1 2/2/1 3/3/1\n')
        relative,_=import_model_bundle(obj,self.root/'assets');scene=load_model(self.root/'assets'/relative)
        self.assertIsNotNone(scene.materials['body']['image'])
        self.assertEqual(tuple(scene.batches[('body',True)][5:8]),(0,1,0))

    def test_obj_catalogue_picture_is_not_an_automatic_texture(self):
        obj=self.root/'weapon.obj'
        obj.write_text('v -1 -1 0\nv 1 -1 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt .5 1\nusemtl body\nf 1/1 2/2 3/3\n')
        Image.new('RGBA',(64,64),(255,0,0,0)).save(self.root/'weapon.png')
        scene=load_model(obj)
        self.assertIsNone(scene.materials['body']['image'])
        Image.new('RGBA',(64,64),(255,0,0,0)).save(self.root/'weapon_basecolor.png')
        scene=load_model(obj)
        self.assertFalse(scene.materials['body']['texture_alpha'])
        try:renderer=OffscreenRenderer(scene)
        except Exception as exc:self.skipTest('GPU unavailable: '+str(exc))
        try:
            image,_=renderer.render(600,400,0,0,1)
            self.assertGreater(image.pixelColor(300,195).alpha(),250)
            self.assertGreater(image.pixelColor(300,195).red(),60)
        finally:renderer.close()

    def test_gpu_full_resolution_texture_depth_and_cancellation(self):
        scene=load_model(self.triangle())
        try:renderer=OffscreenRenderer(scene)
        except Exception as exc:self.skipTest('GPU unavailable: '+str(exc))
        try:
            image,_=renderer.render(1200,800,0,0,1)
            self.assertEqual((image.width(),image.height()),(1200,800))
            self.assertGreater(image.pixelColor(600,390).red(),60)
            self.assertLess(image.pixelColor(600,390).blue(),50)
            cancel=Event();cancel.set();self.assertIsNone(renderer.render(1200,800,0,0,1,cancel)[0])
        finally:renderer.close()

    def test_native_orbit_does_not_degrade_after_a_slow_frame(self):
        canvas=InteractiveModelCanvas();canvas.resize(1000,500);canvas.render_ms=300
        canvas.item_data=SimpleNamespace(name='fixture',category='WEAPON');canvas.loaded('fixture',load_model(self.triangle()),'');canvas.show()
        try:
            wait_until(lambda:canvas.surface_frame is not None,15)
            self.assertGreaterEqual(canvas.surface_frame.width(),1000)
            self.assertTrue(canvas.renderer.is_gpu)
        finally:canvas.shutdown_renderer();canvas.close();APP.processEvents()

    def test_studio_supersampling_and_full_resolution_export(self):
        canvas=InteractiveModelCanvas();canvas.resize(600,400);canvas.paused=True
        canvas.item_data=SimpleNamespace(name='fixture',category='WEAPON');canvas.loaded('fixture',load_model(self.triangle()),'')
        canvas.set_quality(4096);canvas.show()
        try:
            wait_until(lambda:canvas.surface_frame is not None,15)
            self.assertGreaterEqual(canvas.surface_frame.width(),1200)
            target=self.root/'export.png'
            with patch('model_preview.QFileDialog.getSaveFileName',return_value=(str(target),'PNG')):canvas.export_preview()
            exported=QImage(str(target));self.assertEqual(exported.size(),canvas.surface_frame.size())
        finally:canvas.shutdown_renderer();canvas.close();APP.processEvents()

    def test_inspection_turntable_materials_and_cleanup(self):
        source=InteractiveModelCanvas();source.item_data=SimpleNamespace(name='fixture',category='WEAPON')
        source.loaded('fixture',load_model(self.triangle()),'')
        dialog=InspectWeaponDialog(source);dialog.show()
        try:
            wait_until(lambda:dialog.canvas.surface_frame is not None,15)
            self.assertTrue(dialog.canvas.renderer.is_gpu);self.assertEqual(dialog.materials.count(),1)
            start=dialog.canvas.rotation;dialog.start_inspect();dialog.inspect_frame(.5)
            self.assertAlmostEqual(dialog.canvas.rotation,start+np.pi)
            dialog.animation.stop();dialog.set_zoom(1.8);self.assertEqual(dialog.canvas.zoom,1.8)
        finally:
            worker=dialog.canvas.render_worker;dialog.close();source.close();APP.processEvents()
            if worker:worker.thread.join(3);self.assertFalse(worker.thread.is_alive())
