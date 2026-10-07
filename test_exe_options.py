import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from exe_options import apply_options,icon_file


class ExeOptionsTests(unittest.TestCase):
    def test_icon_sizes_metadata_resources_and_folder_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=root/'source.png';Image.new('RGBA',(80,40),'red').save(image)
            command=['python','-m','PyInstaller','--onefile']
            apply_options(command,root,'MyApp',{'icon':str(image),'onedir':True,'version':'1.2.3.4',
                'company':"Example's company",'data':['source:resources'],'noupx':True,'optimize':1,'extra_args':['--log-level','INFO']})
            self.assertIn('--onedir',command);self.assertNotIn('--onefile',command);self.assertIn('--noupx',command)
            self.assertIn('source:resources',command)
            with Image.open(root/'application.ico') as icon:
                self.assertIn((16,16),icon.ico.sizes());self.assertIn((256,256),icon.ico.sizes())
                self.assertEqual(icon.getpixel((128,128)),(255,0,0,255))
                self.assertEqual(icon.getpixel((128,0))[3],0)
            from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file
            info=load_version_info_from_text_file(str(root/'version_info.txt'))
            self.assertIn('Example',str(info));self.assertIn('1.2.3.4',str(info))

    def test_direct_builder_prompts_and_unattended_mode_skips_picker(self):
        import build_exe
        with patch('build_exe.prepare_runtime'),patch('build_exe.subprocess.run'),patch('exe_options.apply_options'),patch('exe_options.pick_icon',return_value=None) as picker:
            with patch('sys.argv',['build_exe.py']):build_exe.main()
            picker.assert_called_once()
            picker.reset_mock()
            with patch('sys.argv',['build_exe.py','--no-icon-picker']):build_exe.main()
            picker.assert_not_called()

    def test_invalid_resource_options_and_version_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):apply_options([],Path(directory),'MyApp',{'version':'one'})
            with self.assertRaises(ValueError):apply_options([],Path(directory),'MyApp',{'extra_args':'--console'})
            with self.assertRaises(ValueError):icon_file(Path(directory)/'missing.ico',directory)
