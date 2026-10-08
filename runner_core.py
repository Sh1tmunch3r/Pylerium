"""Persistent local orchestration: Qt processes, DAG scheduling, shared SQLite state."""
from __future__ import annotations

import codecs
import json
import os
import shlex
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal
from app_paths import python_executable, sdk_root, workspace_root


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'shared.sqlite3'
        self.db = sqlite3.connect(self.db_path, timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS shared (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, name TEXT,
                status TEXT, started REAL, ended REAL, exit_code INTEGER, log TEXT);
        ''')
        self.db.commit()

    def put(self, kind, ident, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?)',
                            (kind, ident, json.dumps(value)))

    def get(self, kind, ident, default=None):
        row = self.db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, ident)).fetchone()
        return json.loads(row[0]) if row else default

    def list(self, kind):
        return [json.loads(row[0]) for row in self.db.execute(
            'SELECT body FROM documents WHERE kind=? ORDER BY id', (kind,))]

    def set_shared(self, key, value):
        if not key.strip():
            raise ValueError('Shared key cannot be empty')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO shared VALUES (?,?)', (key, json.dumps(value)))

    def shared(self):
        return {k: json.loads(v) for k, v in self.db.execute('SELECT key,value FROM shared ORDER BY key')}

    def history(self):
        return self.db.execute('SELECT id,name,status,started,ended,exit_code FROM runs ORDER BY started DESC LIMIT 200').fetchall()


def validate_workflow(workflow, projects):
    if not isinstance(workflow, dict):
        raise ValueError('Workflow must be a JSON object')
    nodes = workflow.get('nodes', [])
    if not nodes or not isinstance(nodes, list):
        raise ValueError('Workflow needs a nonempty nodes list')
    if not all(isinstance(n, dict) for n in nodes):
        raise ValueError('Each workflow node must be a JSON object')
    ids = [n.get('id') for n in nodes]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Node IDs must be unique nonempty strings')
    known = set(ids)
    for node in nodes:
        if node.get('project') not in projects:
            raise ValueError(f"Unknown project for node {node['id']}")
        deps = node.get('depends_on', [])
        if not isinstance(deps, list) or any(not isinstance(d, str) or d not in known for d in deps):
            raise ValueError(f"Unknown dependencies for {node['id']}")
    pending, done = list(nodes), set()
    while pending:
        ready = [n for n in pending if set(n.get('depends_on', [])) <= done]
        if not ready:
            raise ValueError('Workflow contains a dependency cycle')
        for node in ready:
            done.add(node['id'])
            pending.remove(node)
    return nodes


class Runner(QObject):
    output = pyqtSignal(str, str)
    changed = pyqtSignal()
    completed = pyqtSignal(str, str)
    started = pyqtSignal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.jobs = {}
        self.workflow = None
        self.max_parallel = 2
        self.output_settings = {'theme':'cyber','styles':{}}
        self.plugin_root = str(Path(__file__).parent/'plugins')
        self.enabled_plugins = []

    def launch(self, project, profile, operator='Local operator'):
        loadout = self.store.get('project_loadout', project['id'])
        if loadout:
            from project_loadout import prepare_launch
            project, profile = prepare_launch(project, profile, loadout)
        executable = str(profile.get('python') or python_executable())
        # One-file extraction paths change on each launch. Remap our bundled runtime.
        if getattr(sys, 'frozen', False) and '_MEI' in executable:
            executable = python_executable()
        if not Path(executable).is_file():
            raise ValueError('Python interpreter does not exist')
        cwd = Path(project['cwd']).resolve()
        script = Path(project['script']).resolve()
        if not cwd.is_dir() or not script.is_file():
            raise ValueError('Project script or working directory does not exist')
        arguments = project.get('args', [])
        env_values = profile.get('env', {})
        if not isinstance(arguments, list) or not all(isinstance(a, str) for a in arguments):
            raise ValueError('Arguments must be a JSON list of strings')
        if not isinstance(env_values, dict):
            raise ValueError('Profile environment must be a JSON object')
        timeout = 0 if project.get('interactive') else max(0, int(profile.get('timeout', 300)))
        ident = uuid.uuid4().hex
        process = QProcess(self)
        process.started.connect(lambda:self.started.emit(ident))
        process.setWorkingDirectory(str(cwd))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        for key, value in env_values.items():
            env.insert(str(key), str(value))
        env.insert('PYTHONUNBUFFERED', '1')
        env.insert('PYTHONIOENCODING', 'utf-8')
        env.insert('FORCE_COLOR', '1')
        env.insert('COLORTERM', 'truecolor')
        env.insert('ULTIMATE_TERMINAL_THEME', self.output_settings.get('theme','cyber'))
        env.insert('ULTIMATE_TERMINAL_STYLES', json.dumps(self.output_settings.get('styles',{})))
        env.insert('ORCHESTRATOR_PLUGIN_ROOT', self.plugin_root)
        env.insert('ORCHESTRATOR_ENABLED_PLUGINS', json.dumps(self.enabled_plugins))
        env.insert('ORCHESTRATOR_SHARED_DB', str(self.store.db_path))
        env.insert('ORCHESTRATOR_RUN_ID', ident)
        env.insert('ORCHESTRATOR_OPERATOR', operator)
        env.insert('ORCHESTRATOR_PROJECT_ID', project['id'])
        audio=self.store.get('settings','app',{})
        env.insert('PYLERIUM_AUDIO',json.dumps({k:v for k,v in audio.items() if k.startswith('audio_')}))
        env.insert('PYLERIUM_HOME',str(env_values.get('PYLERIUM_HOME',env_values.get('SYSTEMATIC_HOME',workspace_root()))))
        sdk = str(sdk_root())
        env.insert('PYTHONPATH', sdk + os.pathsep + env.value('PYTHONPATH', ''))
        process.setProcessEnvironment(env)
        timer = QTimer(process)
        timer.setSingleShot(True)
        job = {'process': process, 'timer': timer, 'name': project['name'],
               'status': 'starting', 'decoder': codecs.getincrementaldecoder('utf-8')('replace'),
               'stop_reason': None, 'log': ''}
        self.jobs[ident] = job
        with self.store.db:
            self.store.db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?)',
                (ident, project['name'], 'starting', time.time(), None, None, ''))
        process.readyReadStandardOutput.connect(lambda: self._read(ident))
        process.started.connect(lambda: self._started(ident, timeout))
        process.finished.connect(lambda code, status: self._finish(ident, code,
            'succeeded' if code == 0 and status == QProcess.ExitStatus.NormalExit else 'failed'))
        process.errorOccurred.connect(lambda error: self._error(ident, error))
        timer.timeout.connect(lambda: self.stop(ident, 'timed out'))
        command = ['-u', str(script), *arguments]
        if project.get('_execution_loadout'):
            env.insert('PYLERIUM_EXECUTION_LOADOUT', json.dumps(project['_execution_loadout']))
            process.setProcessEnvironment(env)
            runtime=Path(__file__).with_name('loadout_runtime.py')
            if not runtime.is_file(): runtime=sdk_root()/'loadout_runtime.py'
            command = ['-u', str(runtime), str(script), *arguments]
        process.start(executable, command)
        self.changed.emit()
        return ident

    def _started(self, ident, timeout):
        if ident not in self.jobs:
            return
        self.jobs[ident]['status'] = 'running'
        with self.store.db:
            self.store.db.execute('UPDATE runs SET status=? WHERE id=?', ('running', ident))
        if timeout:
            self.jobs[ident]['timer'].start(min(timeout * 1000, 2147483647))
        self.changed.emit()

    def _read(self, ident, final=False):
        job = self.jobs.get(ident)
        if not job:
            return
        raw = bytes(job['process'].readAllStandardOutput())
        text = job['decoder'].decode(raw, final=final)
        if text:
            job['log'] = (job['log'] + text)[-2_000_000:]
            self.output.emit(ident, text)

    def _error(self, ident, error):
        if ident in self.jobs and error == QProcess.ProcessError.FailedToStart:
            message = self.jobs[ident]['process'].errorString() + '\n'
            self.jobs[ident]['log'] += message
            self.output.emit(ident, message)
            self._finish(ident, -1, 'failed')

    def _finish(self, ident, code, status):
        job = self.jobs.get(ident)
        if not job:
            return
        self._read(ident, final=True)
        job['timer'].stop()
        status = job['stop_reason'] or status
        with self.store.db:
            self.store.db.execute('UPDATE runs SET status=?,ended=?,exit_code=?,log=? WHERE id=?',
                                 (status, time.time(), code, job['log'], ident))
        del self.jobs[ident]
        job['process'].deleteLater()
        self.completed.emit(ident, status)
        self.changed.emit()
        if self.workflow:
            for node in self.workflow['nodes']:
                if node.get('run') == ident:
                    node['status'] = status
            QTimer.singleShot(0, self._schedule)

    def stop(self, ident, reason='cancelled'):
        job = self.jobs.get(ident)
        if job:
            job['stop_reason'] = reason
            if os.name == 'nt' and job['process'].processId():
                # Kill the pipeline's descendants as well as its wrapper.
                import subprocess
                subprocess.run(['taskkill', '/PID', str(job['process'].processId()), '/T', '/F'],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            job['process'].kill()

    def stop_all(self):
        if self.workflow:
            self.workflow['cancelled'] = True
            for node in self.workflow['nodes']:
                if node['status'] == 'pending':
                    node['status'] = 'cancelled'
        for ident in list(self.jobs):
            self.stop(ident)
        self._schedule()

    def start_workflow(self, workflow, projects, profiles, operators):
        if self.workflow:
            raise ValueError('A workflow is already active')
        nodes = validate_workflow(workflow, projects)
        for node in nodes:
            if node.get('profile', 'default') not in profiles:
                raise ValueError(f"Unknown profile for {node['id']}")
            if node.get('operator') and node['operator'] not in operators:
                raise ValueError(f"Unknown operator for {node['id']}")
        self.workflow = {'name': workflow['name'], 'nodes': [dict(n, status='pending') for n in nodes],
                         'projects': projects, 'profiles': profiles, 'operators': operators, 'cancelled': False}
        self._schedule()

    def _schedule(self):
        wf = self.workflow
        if not wf:
            return
        nodes = {n['id']: n for n in wf['nodes']}
        progress = True
        while progress:
            progress = False
            for node in wf['nodes']:
                if node['status'] != 'pending':
                    continue
                deps = [nodes[d]['status'] for d in node.get('depends_on', [])]
                if any(s in ('failed', 'cancelled', 'timed out', 'skipped') for s in deps):
                    node['status'] = 'skipped'
                    progress = True
                elif all(s == 'succeeded' for s in deps) and len(self.jobs) < self.max_parallel and not wf['cancelled']:
                    try:
                        node['run'] = self.launch(wf['projects'][node['project']],
                            wf['profiles'][node.get('profile', 'default')],
                            wf['operators'].get(node.get('operator'), {}).get('name', 'Local operator'))
                        node['status'] = 'running'
                    except (ValueError, OSError) as exc:
                        node['status'] = 'failed'
                        self.output.emit('workflow', f"{node['id']}: {exc}\n")
                    progress = True
        self.changed.emit()
        if all(n['status'] not in ('pending', 'running') for n in wf['nodes']):
            status = 'succeeded' if all(n['status'] == 'succeeded' for n in wf['nodes']) else 'cancelled' if wf['cancelled'] else 'failed'
            self.output.emit('workflow', f"Workflow {wf['name']}: {status}\n")
            self.store.put('workflow_result', uuid.uuid4().hex, {'name': wf['name'], 'status': status, 'nodes': wf['nodes']})
            self.workflow = None
            self.changed.emit()

