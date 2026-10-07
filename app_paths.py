"""Keep packaged resources separate from persistent user-authored files."""
import os
import shutil
import sys
from pathlib import Path


def resource_root():
    root=Path(getattr(sys, '_MEIPASS', Path(__file__).parent)).resolve()
    # Child Workshop interpreters load SDK source next to bundled resources.
    if not getattr(sys,'frozen',False) and root.name=='sdk' and (root.parent/'orchestration-menu.py').is_file():
        return root.parent
    return root


def workspace_root():
    override = os.environ.get('PYLERIUM_HOME') or os.environ.get('SYSTEMATIC_HOME')
    if override:
        return Path(override).resolve()
    if getattr(sys, 'frozen', False):
        # A build kept in Systematic/dist continues using the existing workspace.
        for candidate in (Path(sys.executable).parent, Path(sys.executable).parent.parent):
            if (candidate/'orchestration_data'/'shared.sqlite3').is_file():
                return candidate.resolve()
        local=Path(os.environ.get('LOCALAPPDATA', str(Path.home())))
        legacy=local/'Systematic'
        return legacy if (legacy/'orchestration_data'/'shared.sqlite3').is_file() else local/'Pylerium'
    return Path(__file__).parent.resolve()


def writable_resources(name):
    source = resource_root() / name
    target = workspace_root() / name
    if source != target and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    elif source != target and name=='plugins':
        # New bundled starters reach existing workspaces; user-edited folders win.
        from starter_catalog import STARTER_PLUGIN_IDS
        import json
        tombstones=target/'.removed.json'
        try:removed=json.loads(tombstones.read_text(encoding='utf-8')) if tombstones.exists() else []
        except (OSError,ValueError):removed=[]
        for ident in STARTER_PLUGIN_IDS:
            if ident not in removed and (source/ident).is_dir() and not (target/ident).exists():
                shutil.copytree(source/ident,target/ident)
    return target


def python_executable():
    if getattr(sys, 'frozen', False):
        return str(resource_root() / 'runtime' / 'python.exe')
    return sys.executable


def sdk_root():
    root=resource_root()
    return root/'sdk' if getattr(sys,'frozen',False) or (root/'sdk').is_dir() and (root/'runtime').is_dir() else root
