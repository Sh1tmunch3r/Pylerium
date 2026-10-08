"""Script API: call commands exported by explicitly enabled workspace plugins."""
import json
import os
from pathlib import Path

from plugin_system import discover, load_module

_modules = {}


def available():
    return json.loads(os.environ.get('ORCHESTRATOR_ENABLED_PLUGINS','[]'))


def call(plugin_id,command,*args,**kwargs):
    if plugin_id not in available():
        raise ValueError(f'Plugin {plugin_id!r} is not enabled for this run')
    if plugin_id not in _modules:
        root = os.environ.get('ORCHESTRATOR_PLUGIN_ROOT')
        if not root:
            raise RuntimeError('Run this script from the orchestration workspace')
        descriptor = next((p for p in discover(Path(root)) if p['id'] == plugin_id),None)
        if not descriptor or descriptor.get('error'):
            raise ValueError('Plugin is missing or invalid')
        _modules[plugin_id] = load_module(descriptor)
    commands = getattr(_modules[plugin_id],'SCRIPT_COMMANDS',{})
    function = commands.get(command)
    if not callable(function):
        raise ValueError(f'Unknown command {command!r} in {plugin_id!r}')
    return function(*args,**kwargs)
