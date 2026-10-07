"""Shared executable branding and PyInstaller configuration."""
import json,re
from pathlib import Path


def pick_icon():
    from PyQt6.QtWidgets import QApplication,QFileDialog
    pick_icon.app=QApplication.instance() or QApplication([])
    filename,_=QFileDialog.getOpenFileName(None,'Pylerium // Select application icon (Cancel uses default)','',
        'Icons and images (*.ico *.png *.jpg *.jpeg *.webp *.bmp);;All files (*)')
    return filename or None


def icon_file(filename,stage):
    if not filename or filename=='NONE':return filename
    source=Path(filename).resolve()
    if not source.is_file():raise ValueError('Icon file does not exist: '+str(source))
    from PIL import Image
    target=Path(stage)/'application.ico'
    with Image.open(source) as image:
        image=image.convert('RGBA')
        # Fit the image onto a square transparent canvas, retaining proportions.
        scale=256/max(image.size)
        image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,256))
        canvas.alpha_composite(image,((256-image.width)//2,(256-image.height)//2))
        canvas.save(target,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return str(target)


def apply_options(command,stage,name,options):
    """Apply options to either the desktop build or a Workshop project build."""
    options=dict(options or {})
    if options.get('icon'):
        icon=icon_file(options['icon'],stage);command.extend(['--icon',icon])
        if icon!='NONE':command.extend(['--add-data',icon+':.'])
    if options.get('onedir'):
        command[:]=['--onedir' if value=='--onefile' else value for value in command]
    if options.get('clean',False) and '--clean' not in command:command.append('--clean')
    if options.get('clean') is False:command[:]=[value for value in command if value!='--clean']
    for key,flag in [('noupx','--noupx'),('uac_admin','--uac-admin'),('uac_uiaccess','--uac-uiaccess'),('disable_traceback','--disable-windowed-traceback')]:
        if options.get(key):command.append(flag)
    if options.get('debug'):command.extend(['--debug',str(options['debug'])])
    if 'optimize' in options:command.extend(['--optimize',str(int(options['optimize']))])
    for key,flag in [('exclude','--exclude-module'),('paths','--paths'),('collect_all','--collect-all'),
        ('collect_submodules','--collect-submodules'),('hooks','--additional-hooks-dir'),('runtime_hooks','--runtime-hook'),
        ('data','--add-data'),('binaries','--add-binary'),('hidden_imports','--hidden-import')]:
        values=options.get(key,[])
        if not isinstance(values,list) or not all(isinstance(value,str) for value in values):raise ValueError(key+' must be a list of strings')
        for value in values:command.extend([flag,value])
    for key,flag in [('splash','--splash'),('manifest','--manifest'),('version_file','--version-file'),('runtime_tmpdir','--runtime-tmpdir')]:
        if options.get(key):command.extend([flag,str(options[key])])
    if options.get('version') and not options.get('version_file'):
        version=str(options['version'])
        if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+',version):raise ValueError('Version must have four numeric parts, for example 1.0.0.0')
        numbers=tuple(map(int,version.split('.')))
        if any(number>65535 for number in numbers):raise ValueError('Version parts must be 0–65535')
        strings={'CompanyName':options.get('company',''),'FileDescription':options.get('description',name),
            'FileVersion':version,'ProductVersion':version,'ProductName':options.get('product',name),
            'OriginalFilename':name+'.exe','LegalCopyright':options.get('copyright','')}
        entries=','.join('StringStruct('+repr(key)+','+repr(str(value))+')' for key,value in strings.items())
        text=f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers!r},prodvers={numbers!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[{entries}])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])"
        path=Path(stage)/'version_info.txt';path.write_text(text,encoding='utf-8');command.extend(['--version-file',str(path)])
    extra=options.get('extra_args',[])
    if not isinstance(extra,list) or not all(isinstance(value,str) for value in extra):raise ValueError('extra_args must be a JSON list of arguments')
    command.extend(extra)


def read_options(filename):
    if not filename:return {}
    result=json.loads(Path(filename).read_text(encoding='utf-8'))
    if not isinstance(result,dict):raise ValueError('Build options must be a JSON object')
    return result
