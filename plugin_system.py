"""Opt-in local Python plugins. Enabled plugins execute with application permissions."""
import importlib.util
import json
import re
import sys
import importlib
from pathlib import Path


def discover(root):
    results = []
    root = Path(root).resolve()
    if not root.exists():
        return results
    for filename in sorted(root.glob('*/plugin.json')):
        try:
            data = json.loads(filename.read_text(encoding='utf-8'))
            ident = data['id']
            if not re.fullmatch(r'[a-zA-Z0-9_-]+',ident):
                raise ValueError('Plugin ID must use letters, numbers, underscores or hyphens')
            if data.get('api_version') != 1:
                raise ValueError('Unsupported plugin API version (expected 1)')
            entry = (filename.parent/data.get('entry','plugin.py')).resolve()
            if not entry.is_relative_to(filename.parent.resolve()) or not entry.is_file():
                raise ValueError('Entry must be an existing file inside the plugin folder')
            if any(p['id'] == ident for p in results):
                raise ValueError('Duplicate plugin ID')
            data.update(folder=str(filename.parent.resolve()),entry_path=str(entry),error='')
            results.append(data)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            results.append({'id':filename.parent.name,'name':filename.parent.name,
                            'description':'Invalid plugin manifest','error':str(exc)})
    return results


def load_module(descriptor):
    name = '_systematic_plugin_'+descriptor['id']
    importlib.invalidate_caches()
    for key in list(sys.modules):
        if key==name or key.startswith(name+'.'):
            sys.modules.pop(key,None)
    spec = importlib.util.spec_from_file_location(name,descriptor['entry_path'],
                                                 submodule_search_locations=[descriptor['folder']])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        # Source compilation avoids stale timestamp-based bytecode after rapid edits.
        source = Path(descriptor['entry_path']).read_text(encoding='utf-8')
        exec(compile(source,descriptor['entry_path'],'exec'),module.__dict__)
    except Exception:
        sys.modules.pop(name,None)
        raise
    return module


class PluginContext:
    api_version = 1

    def __init__(self,host,descriptor):
        self.host, self.descriptor = host, descriptor
        self.window = host.window
        self.store = self.window.store
        self.runner = self.window.runner
        self.pages, self.actions, self.templates, self.styles, self.hooks = [], [], [], [], []
        self.selectors = []

    @property
    def audio(self):
        from ui_audio import audio_engine
        return audio_engine()

    def play_cue(self,cue):
        return self.audio.play(cue)

    def selector(self,kind):
        if kind not in ('project','profile','operator','workflow'):
            raise ValueError('Selector kind must be project, profile, operator or workflow')
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        self.window.fill_combo(combo,self.store.list(kind))
        self.selectors.append((kind,combo))
        return combo

    def refresh_selectors(self):
        for kind,combo in self.selectors:
            self.window.fill_combo(combo,self.store.list(kind))

    def log(self,text):
        self.window.receive_output('plugin:'+self.descriptor['id'],str(text)+'\n')

    def add_page(self,name,widget):
        from PyQt6.QtWidgets import QPushButton
        title = 'PLUGIN // '+self.descriptor['id']+' // '+name.upper()
        if title in self.window.page_ids:
            raise ValueError('Plugin page already exists')
        index = self.window.stack.addWidget(widget)
        self.window.page_ids[title] = index
        b = QPushButton(name.upper())
        b.setCheckable(True)
        b.clicked.connect(lambda:self.window.navigate(title))
        self.window.nav[title] = b
        self.window.plugin_navigation.addWidget(b)
        self.window.plugin_navigation_scroll.show()
        self.pages.append((title,widget,b))

    def add_action(self,name,callback):
        from PyQt6.QtWidgets import QPushButton
        b = QPushButton(name)
        b.clicked.connect(lambda:self.host.invoke(self.descriptor['id'],callback))
        self.window.plugin_actions.addWidget(b)
        self.actions.append(b)

    def add_template(self,name,code):
        if not isinstance(code,str):
            raise ValueError('Template code must be a string')
        key = self.descriptor['id']+' // '+name
        self.window.plugin_templates[key] = code
        self.templates.append(key)

    def add_style(self,name,**style):
        key = self.descriptor['id']+'.'+name
        self.window.validated_output_styles(json.dumps({key:style}))
        self.window.plugin_styles[key] = style
        self.styles.append(key)

    def on(self,event,callback):
        if event not in ('output','run_finished'):
            raise ValueError('Events are output and run_finished')
        self.hooks.append((event,callback))

    def cleanup(self):
        for title,widget,b in self.pages:
            self.window.stack.removeWidget(widget)
            widget.deleteLater()
            b.deleteLater()
            self.window.page_ids.pop(title,None)
            self.window.nav.pop(title,None)
        # Removing stacked pages shifts indices; always derive them again.
        for title,index in list(self.window.page_ids.items()):
            widget = self.window.page_widgets.get(title)
            if widget:
                self.window.page_ids[title] = self.window.stack.indexOf(widget)
        for context in self.host.contexts.values():
            for title,widget,b in context.pages:
                if title in self.window.page_ids:
                    self.window.page_ids[title] = self.window.stack.indexOf(widget)
        for b in self.actions:
            b.deleteLater()
        self.pages.clear()
        if not any(context.pages for context in self.host.contexts.values()):self.window.plugin_navigation_scroll.hide()
        self.actions.clear()
        for key in self.templates:
            self.window.plugin_templates.pop(key,None)
        for key in self.styles:
            self.window.plugin_styles.pop(key,None)
        self.hooks.clear()
        self.selectors.clear()


class PluginHost:
    def __init__(self,window,root):
        self.window, self.root = window, Path(root)
        self.contexts, self.modules = {}, {}
        self._emitting = set()

    def descriptors(self):
        return discover(self.root)

    def enabled(self):
        return sorted(self.contexts)

    def enable(self,descriptor):
        ident = descriptor['id']
        if ident in self.contexts:
            return
        if descriptor.get('error'):
            raise ValueError(descriptor['error'])
        context = PluginContext(self,descriptor)
        self.contexts[ident] = context
        try:
            module = load_module(descriptor)
            module.register(context)
            self.modules[ident] = module
        except Exception as exc:
            context.cleanup()
            self.contexts.pop(ident,None)
            raise ValueError(f'{ident}: {exc}') from exc
        self.window.sync_plugin_environment()

    def disable(self,ident):
        context = self.contexts.get(ident)
        module = self.modules.get(ident)
        if context:
            if module and callable(getattr(module,'unregister',None)):
                self.invoke(ident,lambda:module.unregister(context))
            context.cleanup()
            self.contexts.pop(ident,None)
            self.modules.pop(ident,None)
        self.window.sync_plugin_environment()

    def invoke(self,ident,callback,*args):
        try:
            return callback(*args)
        except Exception as exc:
            from ui_audio import play_cue
            play_cue('error')
            self.window.console.feed('plugin-errors',f'{ident}: {exc}\n')

    def emit(self,event,*args):
        if event in self._emitting:
            return
        self._emitting.add(event)
        try:
            for ident,context in list(self.contexts.items()):
                for name,callback in list(context.hooks):
                    if name == event:
                        self.invoke(ident,callback,*args)
        finally:
            self._emitting.discard(event)
