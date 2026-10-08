"""Pixel tests for complete surfaces, UVs, occlusion and asynchronous rendering."""
import tempfile
import time
import unittest
from unittest.mock import patch
from model_offscreen import OffscreenRenderer
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage,QColor
from test_orchestration import APP,wait_until
from model_assets import load_obj
from model_renderer import SoftwareModelRenderer
from model_preview import InteractiveModelCanvas


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def scene(self,repeat=1):
        image=QImage(32,16,QImage.Format.Format_RGBA8888)
        image.fill(QColor('#df5010')); image.save(str(self.root/'orange.png'))
        (self.root/'mesh.mtl').write_text('newmtl surface\nmap_Kd orange.png\n')
        path=self.root/'mesh.obj'
        path.write_text('mtllib mesh.mtl\nv -1 -1 0\nv 1 -1 0\nv 1 1 0\nv -1 1 0\n'
                        'vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl surface\n'+
                        ('f 1/1 2/2 3/3\nf 1/1 3/3 4/4\n'*repeat))
        return load_obj(path)

    def test_complete_textured_square_has_no_internal_holes(self):
        scene=self.scene(repeat=350)
        self.assertEqual(scene.source_faces,700)
        self.assertLess(len(scene.preview_triangles),scene.source_faces)
        image,ms=SoftwareModelRenderer(scene).render(320,240,0,0,1)
        for x in range(145,176):
            for y in range(100,135):
                color=image.pixelColor(x,y)
                self.assertEqual(color.alpha(),255)
                self.assertGreater(color.red(),color.blue()*2)

    def test_depth_and_transparent_texels_do_not_occlude_the_front_surface(self):
        scene=self.scene()
        # An orange square in front of a blue square, stored in reverse depth order.
        original=scene.batches[('surface',True)]
        from array import array
        front=array('f',original)
        for i in range(2,len(front),8):front[i]=-0.5
        scene.batches={('front',False):front,('back',False):original}
        scene.materials['front']={'color':(1,0,0),'image':None}
        scene.materials['back']={'color':(0,0,1),'image':None}
        image,_=SoftwareModelRenderer(scene).render(320,240,0,0,1)
        self.assertGreater(image.pixelColor(160,118).red(),image.pixelColor(160,118).blue())
        transparent=QImage(8,8,QImage.Format.Format_RGBA8888);transparent.fill(QColor(255,255,255,0))
        scene.materials['front']['image']=transparent
        scene.batches={('front',True):front,('back',False):original}
        image,_=SoftwareModelRenderer(scene).render(320,240,0,0,1)
        self.assertGreater(image.pixelColor(160,118).blue(),image.pixelColor(160,118).red())

    def test_cancellation_and_resolution_do_not_change_framing(self):
        renderer=SoftwareModelRenderer(self.scene())
        cancel=Event();cancel.set()
        self.assertIsNone(renderer.render(320,240,0,0,1,cancel)[0])
        large,_=renderer.render(640,480,0,0,1)
        small,_=renderer.render(320,240,0,0,1,viewport=(640,480))
        self.assertEqual(large.pixelColor(320,235).alpha(),small.pixelColor(160,117).alpha())

    def test_async_surface_keeps_input_loop_live_and_reuses_paused_frame(self):
        scene=self.scene(repeat=1500)
        canvas=InteractiveModelCanvas();canvas.resize(640,380)
        canvas.item_data=SimpleNamespace(name='fixture',category='RIFLE');canvas.paused=True
        ticks=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
        entered,release=Event(),Event()
        software_render=SoftwareModelRenderer.render
        gpu_render=OffscreenRenderer.render
        def gated(render):
            def run(renderer,*args,**kwargs):
                entered.set()
                if not release.wait(10):raise RuntimeError('Test renderer was not released')
                return render(renderer,*args,**kwargs)
            return run
        try:
            with patch.object(SoftwareModelRenderer,'render',gated(software_render)), patch.object(OffscreenRenderer,'render',gated(gpu_render)):
                canvas.loaded('fixture',scene,'');canvas.show()
                wait_until(entered.is_set,5)
                ticks.clear()
                wait_until(lambda:len(ticks)>1,5)
                self.assertIsNone(canvas.surface_frame)
                release.set()
                wait_until(lambda:canvas.surface_frame is not None,15)
                image=canvas.surface_frame;APP.processEvents();canvas.grab()
                self.assertIs(canvas.surface_frame,image)
                self.assertLess(canvas.last_paint_ms,50)
        finally:
            release.set();timer.stop();canvas.close();APP.processEvents()
