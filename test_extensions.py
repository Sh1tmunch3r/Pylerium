"""Terminal rendering, code cleanup, real local HTTP, and plugin integration checks."""
import json
import runpy
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from test_orchestration import APP, wait_until
from generated_code import clean_python_response, validate_python
from orchestration_ui import OrchestrationWindow
from terminal_console import AnsiStream, TerminalConsole


class MockOllama(BaseHTTPRequestHandler):
    requests = []

    def log_message(self,*args):
        pass

    def respond(self,data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.requests.append(self.path)
        self.respond({'models':[{'name':'local-code:latest','size':1_500_000_000},
                                {'name':'small-model:latest','size':500_000_000}]})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.requests.append(data)
        self.respond({'response':'Here is your Python code:\n```python\nprint("ready")\n```\nRun it when ready.'})


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        theme = SimpleNamespace(**runpy.run_path(str(Path(__file__).parent/'orchestration-menu.py')))
        self.window = OrchestrationWindow(theme,self.temp.name)

    def tearDown(self):
        self.window.runner.stop_all()
        wait_until(lambda:not self.window.runner.jobs)
        self.window.code.document().setModified(False)
        self.window.close()
        APP.processEvents()
        self.temp.cleanup()

    def test_ansi_split_colors_progress_and_isolation(self):
        stream = AnsiStream()
        stream.feed('\x1b[38;2;255;')
        stream.feed('100;19mOrange\x1b[0m\n')
        self.assertEqual(stream.document.firstBlock().begin().fragment().charFormat().foreground().color().name(),'#ff6413')
        stream.feed('Loading 10%\r\x1b[2KDone 100%\n')
        self.assertEqual(stream.document.toPlainText(),'Orange\nDone 100%\n')
        console = self.window.console
        console.feed('a','first\r\x1b[2Kupdated')
        console.feed('b','independent\n')
        console.select_run('a')
        self.assertIn('updated',console.toPlainText())
        self.assertNotIn('independent',console.toPlainText())
        console.select_run(None)
        self.assertNotIn('\x1b',console.toPlainText())
        self.assertIn('independent',console.toPlainText())

    def test_clean_python_wrappers_preserve_strings(self):
        variants = ['```python\nprint("ok")\n```',
            'Explanation\n` ` ` python\nprint("ok")\n` ` `\nMore prose',
            'python\nprint("ok")',
            '<think>planning</think>\n~~~py\nprint("ok")\n~~~',
            '```python\nprint("ok")']
        for value in variants:
            self.assertEqual(validate_python(clean_python_response(value)),'print("ok")\n')
        raw = 'text = """\n```python\nnot code\n```\n"""\n'
        self.assertEqual(clean_python_response(raw),raw)
        with self.assertRaises(ValueError):
            clean_python_response('```javascript\nalert(1)\n```')

    def test_ollama_discovery_generation_and_insertion(self):
        MockOllama.requests = []
        server = ThreadingHTTPServer(('127.0.0.1',0),MockOllama)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            w = self.window
            self.assertFalse(w.settings['ai_enabled'])
            self.assertEqual(MockOllama.requests,[])
            w.ollama_url.setText(f'http://127.0.0.1:{server.server_port}/ollama')
            w.ai_enabled.setChecked(True)
            wait_until(lambda:w.models_reply is None)
            self.assertEqual(w.ollama_model.count(),2)
            self.assertEqual(w.ollama_model.currentData(),'local-code:latest')
            w.save_settings()
            w.ai_prompt.setPlainText('Write a ready message')
            w.generate_draft()
            wait_until(lambda:w.ai_reply is None)
            self.assertEqual(w.ai_draft.toPlainText(),'print("ready")\n')
            w.apply_draft()
            self.assertEqual(w.code.toPlainText(),'print("ready")\n')
            self.assertIn('/ollama/api/tags',MockOllama.requests)
            self.assertEqual(MockOllama.requests[-1]['model'],'local-code:latest')
        finally:
            server.shutdown()
            server.server_close()

    def test_plugin_lifecycle_and_script_commands(self):
        w = self.window
        self.assertEqual(w.plugin_host.enabled(),[])
        # Optional example plugins can be removed by the user; own this fixture.
        folder=Path(self.temp.name)/'fixture_plugins'/'output_tools';folder.mkdir(parents=True)
        (folder/'plugin.json').write_text(json.dumps({'id':'output_tools','name':'Fixture tools','api_version':1,'entry':'plugin.py'}))
        (folder/'plugin.py').write_text('''
def summarize(values): return {'items': len(values)}
SCRIPT_COMMANDS = {'summarize': summarize}
def register(ctx):
    from PyQt6.QtWidgets import QWidget
    ctx.add_page('Inspector', QWidget())
    ctx.add_style('highlight', foreground='#ff7b1c', bold=True)
    ctx.add_template('Styled plugin report', "from ultimate_terminal import terminal as term\\nfrom shared_loadout import all_values\\nfrom workspace_plugins import call\\nterm.section('PLUGIN REPORT')\\nterm.print(call('output_tools', 'summarize', all_values()), style='output_tools.highlight')\\n")
''')
        w.plugin_host.root=folder.parent
        descriptor = next(d for d in w.plugin_host.descriptors() if d['id']=='output_tools')
        w.plugin_host.enable(descriptor)
        self.assertEqual(w.stack.count(),12)
        self.assertIn('output_tools // Styled plugin report',w.plugin_templates)
        self.assertIn('output_tools.highlight',w.runner.output_settings['styles'])
        code = w.plugin_templates['output_tools // Styled plugin report']
        script = Path(self.temp.name)/'plugin-check.py'
        script.write_text(code,encoding='utf-8')
        project = {'id':'plugin','name':'plugin','script':str(script),'cwd':self.temp.name,'args':[]}
        ident = w.runner.launch(project,w.profiles[0])
        wait_until(lambda:not w.runner.jobs)
        row = w.store.db.execute('SELECT status,log FROM runs WHERE id=?',(ident,)).fetchone()
        self.assertEqual(row[0],'succeeded',row[1])
        self.assertIn('PLUGIN REPORT',row[1])
        self.assertIn('\x1b[',row[1])
        w.plugin_host.disable('output_tools')
        self.assertEqual(w.stack.count(),11)
        self.assertNotIn('output_tools.highlight',w.runner.output_settings['styles'])
        for name in w.nav:
            w.navigate(name)
            self.assertEqual(w.stack.currentIndex(),w.page_ids[name])

    def test_terminal_preview_custom_styles_and_worker(self):
        w = self.window
        w.output_styles.setText('{"important":{"foreground":"#ff7b1c","bold":true}}')
        w.save_output_settings()
        w.preview_terminal()
        self.assertIn('OUTPUT PREVIEW',w.console.toPlainText())
        self.assertNotIn('\x1b',w.console.toPlainText())
        script = Path(self.temp.name)/'terminal-check.py'
        script.write_text(w.terminal_example(),encoding='utf-8')
        ident = w.runner.launch({'id':'styled','name':'Styled','script':str(script),'cwd':self.temp.name,'args':[]},w.profiles[0])
        wait_until(lambda:not w.runner.jobs)
        row = w.store.db.execute('SELECT status,log FROM runs WHERE id=?',(ident,)).fetchone()
        self.assertEqual(row[0],'succeeded',row[1])
        self.assertIn('Complete',row[1])
        w.console.select_run(ident)
        self.assertIn('100.00%',w.console.toPlainText())
        self.assertNotIn('20.00%',w.console.toPlainText())

    def test_editor_indentation_and_failed_plugin_cleanup(self):
        w = self.window
        w.code.setPlainText('if True:')
        cursor = w.code.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        w.code.setTextCursor(cursor)
        QTest.keyClick(w.code,Qt.Key.Key_Return)
        self.assertEqual(w.code.toPlainText(),'if True:\n    ')
        root = Path(self.temp.name)/'plugins'
        folder = root/'broken'
        folder.mkdir(parents=True)
        (folder/'plugin.json').write_text(json.dumps({'id':'broken','name':'broken','api_version':1,'entry':'plugin.py'}))
        (folder/'plugin.py').write_text("def register(ctx):\n    from PyQt6.QtWidgets import QWidget\n    ctx.add_page('Temporary', QWidget())\n    raise RuntimeError('expected registration failure')\n")
        w.plugin_host.root = root
        with self.assertRaises(ValueError):
            w.plugin_host.enable(w.plugin_host.descriptors()[0])
        self.assertEqual(w.plugin_host.enabled(),[])
        self.assertEqual(w.stack.count(),11)
        self.assertTrue(all(not name.startswith('PLUGIN //') for name in w.nav))


if __name__ == '__main__':
    unittest.main(verbosity=2)
