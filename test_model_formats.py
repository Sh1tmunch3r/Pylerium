import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image
from model_assets import load_model,import_model_bundle
from test_orchestration import APP
from model_preview import InteractiveModelCanvas


class FormatTests(unittest.TestCase):
    def test_formats_portable_import_and_scene_instances(self):
        mesh=trimesh.creation.box()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for ext in ('stl','ply','off','glb','gltf'):
                with self.subTest(format=ext):
                    path=root/('box.'+ext)
                    if ext=='gltf':
                        data=trimesh.Scene(mesh).export(file_type='gltf')
                        for name,blob in data.items():(root/name).write_bytes(blob)
                        path=root/'model.gltf'
                    else:mesh.export(str(path))
                    self.assertEqual(load_model(path).source_faces,12)
                    relative,_=import_model_bundle(path,root/'assets')
                    self.assertEqual(load_model(root/'assets'/relative).source_faces,12)
            scene=trimesh.Scene();scene.add_geometry(mesh,node_name='one')
            translation=np.eye(4);translation[0,3]=4;scene.add_geometry(mesh,node_name='two',transform=translation)
            path=root/'instances.glb';path.write_bytes(scene.export(file_type='glb'))
            result=load_model(path);self.assertEqual(result.source_faces,24)
            self.assertEqual(len(result.batches),2)

    def test_glb_textures_uvs_and_external_path_rejection(self):
        mesh=trimesh.Trimesh(vertices=[[-1,-1,0],[1,-1,0],[0,1,0]],faces=[[0,1,2]],process=False)
        mesh.visual=trimesh.visual.TextureVisuals(uv=[[0,0],[1,0],[.5,1]],image=Image.new('RGB',(4,4),'red'))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'textured.glb';path.write_bytes(trimesh.Scene(mesh).export(file_type='glb'))
            result=load_model(path)
            self.assertTrue(next(iter(result.batches))[1]);self.assertEqual(next(iter(result.materials.values()))['image'].pixelColor(0,0).name(),'#ff0000')
            path=root/'invalid.gltf';path.write_text('{"asset":{"version":"2.0"},"buffers":[{"uri":"../escape.bin"}]}')
            with self.assertRaisesRegex(ValueError,'outside'):load_model(path)

    def test_camera_controls(self):
        canvas=InteractiveModelCanvas();canvas.resize(800,400)
        before=canvas.project((0,0,0))[0];canvas.pan.setX(40);canvas.pan.setY(20)
        after=canvas.project((0,0,0))[0];self.assertEqual(after.x()-before.x(),40);self.assertEqual(after.y()-before.y(),20)
        canvas.set_camera(1,.5);self.assertTrue(canvas.paused);self.assertEqual(canvas.pan.x(),0)
        canvas.set_quality(1440);self.assertEqual(canvas.quality,1440);canvas.reset_view();self.assertEqual(canvas.zoom,1)
        canvas.close()
