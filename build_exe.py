"""Reproducible one-file Windows build including a separate script interpreter."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def prepare_runtime(stage):
    """Portable interpreter for tool processes and script-backed components."""
    stage.mkdir(parents=True,exist_ok=True)
    python_home=Path(sys.base_prefix)
    for name in ('python.exe','python3.dll',f'python{sys.version_info.major}{sys.version_info.minor}.dll','LICENSE.txt'):
        shutil.copy2(python_home/name,stage/name)
    for filename in python_home.glob('vcruntime*.dll'):shutil.copy2(filename,stage/filename.name)
    shutil.copytree(python_home/'DLLs',stage/'DLLs',dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    archive=f'python{sys.version_info.major}{sys.version_info.minor}.zip'
    with zipfile.ZipFile(stage/archive,'w',zipfile.ZIP_DEFLATED) as output:
        for path in (python_home/'Lib').rglob('*'):
            relative=path.relative_to(python_home/'Lib')
            if any(part in ('site-packages','__pycache__','test','tests','idlelib') for part in relative.parts):continue
            if path.is_file() and path.suffix not in ('.pyc','.pyo'):output.write(path,relative.as_posix())
    # Isolate the portable interpreter from an installed Python/PYTHONHOME.
    # The app passes the SDK and user PYTHONPATH for each run via a startup shim.
    (stage/f'python{sys.version_info.major}{sys.version_info.minor}._pth').write_text(
        archive+'\nDLLs\nLib/site-packages\n../sdk\n..\nimport site\n',encoding='utf-8')
    site=stage/'Lib'/'site-packages';site.mkdir(parents=True,exist_ok=True)
    # Workshop GUIs use the same vectorized texture renderer as the host.
    # PYZ modules are not importable by the separate portable interpreter.
    import numpy
    numpy_source=Path(numpy.__file__).parent
    shutil.copytree(numpy_source,site/'numpy',dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','tests','*.pyc'))
    numpy_dlls=numpy_source.parent/'numpy.libs'
    if numpy_dlls.exists():shutil.copytree(numpy_dlls,site/'numpy.libs',dirs_exist_ok=True)
    import trimesh,PIL,moderngl,glcontext
    for package in (trimesh,PIL,moderngl,glcontext):
        directory=Path(package.__file__).parent
        shutil.copytree(directory,site/directory.name,dirs_exist_ok=True,
                       ignore=shutil.ignore_patterns('__pycache__','tests','*.pyc'))
        dlls=directory.parent/(directory.name.lower()+'.libs')
        if dlls.is_dir():shutil.copytree(dlls,site/dlls.name,dirs_exist_ok=True)
    (site/'sitecustomize.py').write_text(
        "import os,sys\nfor path in reversed(os.environ.get('PYTHONPATH','').split(os.pathsep)):\n    if path and path not in sys.path: sys.path.insert(0,path)\n",encoding='utf-8')
    # tkinter's standard-library native backend needs its Tcl resources.
    if (python_home/'tcl').exists():shutil.copytree(python_home/'tcl',stage/'tcl',dirs_exist_ok=True)


def build_project(project, output, name, *, windowed=True, assets=None, plugins=None,enabled_plugins=(),project_id='standalone',hidden_imports=(),options=None):
    """Package a Workshop application and its complete shared GUI SDK."""
    import re
    project=Path(project).resolve();output=Path(output).resolve()
    if not project.is_file():raise ValueError('Project entry script does not exist')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,79}',name):
        raise ValueError('Use a name containing letters, numbers, spaces, underscores or dashes')
    source=Path(__file__).resolve().parent
    output.mkdir(parents=True,exist_ok=True)
    import uuid
    stage=output/'.build'/(name+'-'+uuid.uuid4().hex[:8]);stage.mkdir(parents=True,exist_ok=True)
    launcher=stage/'launcher.py'
    launcher.write_text("import os,sys,runpy,shutil,json,uuid\nfrom pathlib import Path\n"
        "root=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))\n"
        "sys.path[:0]=[str(root/'project'),str(root/'sdk')]\n"
        f"home=Path(os.environ.get('PYLERIUM_HOME',os.environ.get('SYSTEMATIC_HOME',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/{name!r}))))\n"
        "os.environ.setdefault('PYLERIUM_HOME',str(home))\n"
        "if (root/'application.ico').is_file():os.environ['PYLERIUM_APP_ICON']=str(root/'application.ico')\n"
        "os.environ.setdefault('ORCHESTRATOR_PLUGIN_ROOT',str(home/'plugins'))\n"
        f"os.environ.setdefault('ORCHESTRATOR_ENABLED_PLUGINS',json.dumps({list(enabled_plugins)!r}))\n"
        f"os.environ.setdefault('ORCHESTRATOR_PROJECT_ID',{project_id!r})\n"
        "os.environ.setdefault('ORCHESTRATOR_RUN_ID',uuid.uuid4().hex)\n"
        "from runner_core import Store\n"
        "store=Store(home/'orchestration_data');store.db.close()\n"
        "os.environ.setdefault('ORCHESTRATOR_SHARED_DB',str(home/'orchestration_data'/'shared.sqlite3'))\n"
        "from app_paths import writable_resources\n"
        "if (root/'plugins').is_dir():writable_resources('plugins')\n"
        "working=home/'project'\n"
        "if not working.exists():shutil.copytree(root/'project',working)\n"
        "os.chdir(working)\n"
        f"sys.argv[0]=str(root/'project'/{project.name!r})\n"
        f"runpy.run_path(sys.argv[0],run_name='__main__')\n",encoding='utf-8')
    # Snapshot files without modifying the source project or including old build outputs.
    snapshot=stage/'project';snapshot.mkdir(exist_ok=True)
    ignored=['__pycache__','.git','.build','build','dist','*.exe','*.pyc']
    if output.is_relative_to(project.parent):
        relative=output.relative_to(project.parent)
        if not relative.parts:raise ValueError('Choose an output folder outside the project root or a subfolder')
        ignored.append(relative.parts[0])
    shutil.copytree(project.parent,snapshot,dirs_exist_ok=True,ignore=shutil.ignore_patterns(*ignored))
    print('Preparing portable tool runtime...',flush=True)
    runtime=stage/'runtime';prepare_runtime(runtime)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile',
        '--windowed' if windowed else '--console','--name',name,'--distpath',str(output),
        '--workpath',str(stage/'work'),'--specpath',str(stage),'--paths',str(source),
        '--paths',str(snapshot),'--add-data',str(snapshot)+':project',
        '--add-data',str(__import__('app_paths').resource_root()/'orchestration-menu.py')+':.',
        '--hidden-import','glcontext.wgl','--add-data',str(runtime)+':runtime']
    import PyQt6
    command.extend(['--add-data',str(Path(PyQt6.__file__))+':PyQt6'])
    for path in source.glob('*.py'):
        if path.name.startswith('test_') or path.name in ('desktop_entry.py','loadout-menu.py','visual-ref.py','orchestration-menu.py'):continue
        command.extend(['--add-data',str(path)+':sdk'])
        if path.stem.isidentifier():command.extend(['--hidden-import',path.stem])
    for path in snapshot.rglob('*.py'):
        relative=path.relative_to(snapshot).with_suffix('')
        if all(part.isidentifier() for part in relative.parts):
            command.extend(['--hidden-import','.'.join(relative.parts)])
    for package in ('PyQt6','PIL','moderngl','glcontext'):
        command.extend(['--collect-all',package])
    for package in ('numpy','trimesh'):
        command.extend(['--collect-data',package,'--collect-binaries',package])
    # Trimesh discovers optional ML/scientific engines. They are not required by
    # our renderer; retain any that the user's project/plugins actually import.
    import ast
    requested=set()
    roots=[snapshot]+([Path(plugins)] if plugins else [])
    for folder in roots:
        for path in folder.rglob('*.py'):
            try:
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                    if isinstance(node,ast.Import):requested.update(alias.name.split('.')[0] for alias in node.names)
                    elif isinstance(node,ast.ImportFrom) and node.module:requested.add(node.module.split('.')[0])
            except (OSError,SyntaxError,UnicodeError):pass
    requested.update(module.split('.')[0] for module in hidden_imports)
    for key in ('hidden_imports','collect_all','collect_submodules'):
        requested.update(module.split('.')[0] for module in (options or {}).get(key,[]))
    for optional in ('torch','torchvision','torchaudio','transformers','scipy','matplotlib','pandas','sympy','pyglet','networkx','pytest','IPython','black','jedi','notebook','jupyter','nbformat','lxml','jsonschema','shapely','skimage','plotly'):
        if optional not in requested:command.extend(['--exclude-module',optional])
    for module in sorted(requested|set(hidden_imports)):
        command.extend(['--hidden-import',module])
    if assets and Path(assets).is_dir():command.extend(['--add-data',str(Path(assets).resolve())+':assets'])
    else:
        empty_assets=stage/'assets';empty_assets.mkdir();(empty_assets/'manifest.json').write_text('{"items":{}}',encoding='utf-8')
        command.extend(['--add-data',str(empty_assets)+':assets'])
    if plugins and Path(plugins).is_dir():command.extend(['--add-data',str(Path(plugins).resolve())+':plugins'])
    resources=__import__('app_paths').resource_root()
    for filename in ('WORKSHOP.md','PLUGINS.md','OPERATIONS.md','STARTER_TOOLS.md'):
        path=source/filename if (source/filename).is_file() else resources/'docs'/filename
        if path.is_file():command.extend(['--add-data',str(path)+':docs'])
    if (resources/'examples').is_dir():command.extend(['--add-data',str(resources/'examples')+':examples'])
    from exe_options import apply_options
    apply_options(command,stage,name,options)
    command.append(str(launcher))
    print('Building standalone application:',name,flush=True)
    subprocess.run(command,check=True)
    print('Built:',output/(name if (options or {}).get('onedir') else '')/(name+'.exe'),flush=True)


def main():
    if sys.platform != 'win32':raise SystemExit('Build this executable on Windows.')
    import argparse
    parser=argparse.ArgumentParser(description='Build the portable Pylerium desktop application.')
    parser.add_argument('--name',default='Pylerium',help='Executable name; use a different name while Pylerium is running.')
    parser.add_argument('--project',help='Workshop entry script; builds your own application')
    parser.add_argument('--output',help='Executable output directory')
    parser.add_argument('--console',action='store_true')
    parser.add_argument('--assets');parser.add_argument('--plugins')
    parser.add_argument('--enabled-plugin',action='append',default=[])
    parser.add_argument('--project-id',default='standalone')
    parser.add_argument('--hidden-import',action='append',default=[])
    parser.add_argument('--icon',help='ICO or image; converted to a multi-resolution Windows icon')
    parser.add_argument('--no-icon-picker',action='store_true',help='Build unattended using the default icon')
    parser.add_argument('--onedir',action='store_true',help='Build an application folder instead of one file')
    parser.add_argument('--options-file',help='JSON with advanced PyInstaller and Windows metadata options')
    args=parser.parse_args();build_name=args.name
    from exe_options import read_options,pick_icon,apply_options
    options=read_options(args.options_file)
    if args.icon:options['icon']=args.icon
    elif not options.get('icon') and not args.no_icon_picker:options['icon']=pick_icon()
    if args.onedir:options['onedir']=True
    if args.project:
        return build_project(args.project,args.output or str(Path(args.project).parent/'dist'),build_name,
            windowed=not args.console,assets=args.assets,plugins=args.plugins,enabled_plugins=args.enabled_plugin,project_id=args.project_id,hidden_imports=args.hidden_import,options=options)
    source=Path(__file__).parent.resolve()
    stage=source/'build'/'runtime'
    prepare_runtime(stage)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed',
        '--name',build_name,'--distpath',str(source/'dist'),'--workpath',str(source/'build'/'pyinstaller'),
        '--specpath',str(source/'build'),'--paths',str(source),
        '--add-data',str(stage)+':runtime',
        '--add-data',str(source/'assets')+':assets',
        '--add-data',str(source/'orchestration-menu.py')+':.',
        '--hidden-import','PyQt6.QtMultimedia','--hidden-import','PyQt6.QtSvg','--hidden-import','PyQt6.QtOpenGL',
        '--hidden-import','ctypes','--hidden-import','ctypes.wintypes','--hidden-import','csv',
        '--hidden-import','PyQt6.QtOpenGLWidgets','--hidden-import','glcontext.wgl','--hidden-import','moderngl']
    for ident in ('output_tools','jumpback'):
        if (source/'plugins'/ident).is_dir():command.extend(['--add-data',str(source/'plugins'/ident)+':plugins/'+ident])
    for path in source.glob('*.py'):
        if path.name.startswith('test_') or path.name in ('desktop_entry.py','loadout-menu.py','visual-ref.py'):continue
        command.extend(['--add-data',str(path)+':sdk'])
    from starter_catalog import STARTER_PLUGIN_IDS
    for ident in STARTER_PLUGIN_IDS:
        command.extend(['--add-data',str(source/'plugins'/ident)+':plugins/'+ident])
    command.extend(['--add-data',str(source/'examples')+':examples'])
    # Static mesh preview only needs Trimesh, NumPy and Pillow, not its optional
    # scientific/rendering ecosystem. Keep the portable distribution bounded.
    for optional in ('scipy','matplotlib','pandas','sympy','pyglet','networkx','pytest','IPython','black','jedi','notebook','jupyter','nbformat','lxml','jsonschema','shapely','skimage','plotly'):
        command.extend(['--exclude-module',optional])
    # Source init permits UI-capable script plugins to import bundled PyQt binaries.
    import PyQt6
    command.extend(['--add-data',str(Path(PyQt6.__file__))+':PyQt6'])
    for name in ('WORKSHOP.md','PLUGINS.md','OPERATIONS.md','STARTER_TOOLS.md'):
        command.extend(['--add-data',str(source/name)+':docs'])
    if args.output:command[command.index('--distpath')+1]=str(Path(args.output).resolve())
    if args.console:command[command.index('--windowed')]='--console'
    apply_options(command,source/'build',build_name,options)
    command.append(str(source/'desktop_entry.py'))
    subprocess.run(command,check=True)
    print('Built:',Path(args.output or source/'dist')/(build_name if options.get('onedir') else '')/f'{build_name}.exe')


if __name__=='__main__':main()
