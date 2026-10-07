"""Shared tool pages used by starter plugins and advanced Workshop applications."""
import json
from pathlib import Path
from PyQt6.QtCore import QProcess,QTimer,pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QSplitter,QFileDialog,QProgressBar,QTabWidget
from app_paths import python_executable,sdk_root
from gui_components import button,label
from workshop_editor import WorkshopEditor
from terminal_console import TerminalConsole
from toolkit_core import TOOLS


class ToolPage(QWidget):
    result_ready=pyqtSignal(str)

    def __init__(self,kind,ctx=None):
        super().__init__();self.kind=kind;self.ctx=ctx;self.result='';self.output_bytes=bytearray();self.errors=bytearray()
        title,description,prompt,option=TOOLS[kind]
        layout=QVBoxLayout(self);layout.addWidget(label(title.upper(),25));layout.addWidget(label(description,12,'#9aabb4'))
        layout.addWidget(label(prompt,12));self.input=WorkshopEditor();self.input.setMinimumHeight(120)
        self.option=WorkshopEditor() if kind=='text_diff' else QLineEdit()
        if kind=='text_diff':self.option.setMaximumHeight(120)
        self.option.setPlaceholderText(option or 'No extra options needed');self.option.setVisible(bool(option))
        layout.addWidget(self.option)
        split=QSplitter();split.addWidget(self.input)
        self.output=WorkshopEditor();self.output.setReadOnly(True);split.addWidget(self.output);layout.addWidget(split,1)
        row=QHBoxLayout();self.start=button('RUN ANALYSIS',self.analyze,True);row.addWidget(self.start)
        self.stop=button('CANCEL',self.cancel);self.stop.setEnabled(False);row.addWidget(self.stop)
        row.addWidget(button('OPEN INPUT',self.open_input));row.addWidget(button('EXPORT RESULT',self.export_result))
        row.addWidget(button('COPY RESULT',self.copy_result))
        if ctx: row.addWidget(button('PUBLISH SHARED RESULT',self.publish))
        layout.addLayout(row);self.progress=QProgressBar();self.progress.setRange(0,1);layout.addWidget(self.progress)
        self.status=label('READY // isolated process • 30 second deadline • files stay unchanged',11,'#26d8ee');layout.addWidget(self.status)
        from ui_audio import play_cue
        self.process=QProcess(self);self.process.started.connect(lambda:play_cue("deploy"));self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(lambda:self.errors.extend(bytes(self.process.readAllStandardError())))
        self.process.finished.connect(self.finished);self.process.errorOccurred.connect(self.process_error)
        self.deadline=QTimer(self);self.deadline.setSingleShot(True);self.deadline.timeout.connect(self.cancel)
        self.set_sample()

    def set_sample(self):
        samples={'json_lab':'{"project":"My tool","ready":true,"steps":[1,2,3]}','csv_profiler':'name,score\nalpha,10\nbeta,20\ngamma,\n','regex_lab':'task-001 completed\ntask-002 failed','text_diff':'before\nunchanged\n','log_analyzer':'INFO Start\nERROR Missing texture\nERROR Missing texture\nINFO Done','python_inspector':'import json\n\ndef report(values):\n    return json.dumps(values)\n','codec_lab':'Hello Pylerium','markdown_report':'[{"task":"Import model","status":"done"},{"task":"Review","status":"pending"}]'}
        self.input.setPlainText(samples.get(self.kind,''))
        if self.kind=='regex_lab':self.option.setText(r'task-(\d+)')
        if self.kind=='text_diff':self.option.setPlainText('after\nunchanged\n')

    def option_value(self):
        return self.option.toPlainText() if self.kind=='text_diff' else self.option.text()

    def analyze(self):
        if self.process.state()!=QProcess.ProcessState.NotRunning:return
        payload=json.dumps([self.kind,self.input.toPlainText(),self.option_value()]).encode()
        if len(payload)>8_000_000:self.status.setText('Input too large');return
        self.output_bytes.clear();self.errors.clear();self.start.setEnabled(False);self.stop.setEnabled(True);self.progress.setRange(0,0)
        self.status.setText('RUNNING // cancel remains available')
        script='import sys,json;sys.path.insert(0,'+repr(str(sdk_root()))+');from toolkit_core import execute;args=json.loads(sys.stdin.buffer.read());print(execute(*args))'
        self.process.started.connect(self.write_payload_once)
        self.payload=payload;self.deadline.start(30000)
        self.process.start(python_executable(),['-u','-c',script])

    def write_payload_once(self):
        self.process.write(self.payload);self.process.closeWriteChannel()
        self.process.started.disconnect(self.write_payload_once)

    def read_output(self):
        self.output_bytes.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.output_bytes)>8_000_000:self.cancel();self.status.setText('Result exceeded 8 MB; narrow the input')

    def finished(self,code,status):
        from ui_audio import play_cue
        play_cue("success" if code==0 else "error")
        self.deadline.stop();self.read_output();self.start.setEnabled(True);self.stop.setEnabled(False);self.progress.setRange(0,1);self.progress.setValue(int(code==0))
        self.result=(self.output_bytes if code==0 else self.errors or b'Cancelled / deadline reached').decode('utf-8',errors='replace')
        preview=self.result[:250000]
        if len(self.result)>250000:preview+='\n\n[Preview truncated. Copy/export retains the complete result.]'
        self.output.setPlainText(preview);self.status.setText('COMPLETE' if code==0 else 'FAILED / CANCELLED')
        if code==0:self.result_ready.emit(self.result)
        if self.ctx:self.ctx.log(TOOLS[self.kind][0]+': '+('complete' if code==0 else 'failed'))

    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            try:self.process.started.disconnect(self.write_payload_once)
            except TypeError:pass
            self.deadline.stop();self.start.setEnabled(True);self.stop.setEnabled(False);self.progress.setRange(0,1);self.status.setText(self.process.errorString())

    def cancel(self):
        self.deadline.stop()
        if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill()

    def shutdown(self):
        self.cancel();self.process.waitForFinished(1000)

    def open_input(self):
        if self.kind in ('duplicate_finder','file_catalog'):
            path=QFileDialog.getExistingDirectory(self,'Choose folder')
            if path:self.input.setPlainText(path)
            return
        path,_=QFileDialog.getOpenFileName(self,'Open input')
        if not path:return
        if self.kind in ('file_integrity','sqlite_explorer'):self.input.setPlainText(path);return
        try:
            if Path(path).stat().st_size>4_000_000:raise ValueError('Input exceeds 4 MB')
            self.input.setPlainText(Path(path).read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:self.status.setText(str(exc))

    def export_result(self):
        path,_=QFileDialog.getSaveFileName(self,'Export result','report.txt','Reports (*.txt *.json *.md)')
        if path:
            try:Path(path).write_text(self.result,encoding='utf-8');self.status.setText('EXPORTED '+path)
            except OSError as exc:self.status.setText(str(exc))

    def copy_result(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.result)

    def publish(self):
        if not self.result:self.status.setText('Run the tool first');return
        self.ctx.store.set_shared('toolkit.'+self.kind,self.result);self.ctx.log('Published shared result: toolkit.'+self.kind)


def register_tool(ctx,kind):
    page=ToolPage(kind,ctx);ctx.add_page(TOOLS[kind][0],page)
    ctx.add_action('OPEN '+TOOLS[kind][0].upper(),lambda:ctx.window.navigate('PLUGIN // '+ctx.descriptor['id']+' // '+TOOLS[kind][0].upper()))
    sample=repr(page.input.toPlainText())
    if kind in ('file_integrity','sqlite_explorer'):sample='__file__' if kind=='file_integrity' else 'os.environ["ORCHESTRATOR_SHARED_DB"]'
    if kind in ('file_catalog','duplicate_finder'):sample='str(Path.cwd())'
    ctx.add_template('Script analysis',f"import os\nfrom pathlib import Path\nfrom workspace_plugins import call\nfrom ultimate_terminal import terminal as term\nresult = call({ctx.descriptor['id']!r}, 'analyze', {sample}, {page.option_value()!r})\nterm.print(result)\n")
    return page


def advanced_window(title,kinds):
    from systematic_gui import AppWindow,PreviewPanel,WorkflowMap,theme
    class AdvancedWindow(AppWindow):
        def __init__(self):
            super().__init__(title,'ADVANCED WORKSHOP // SHARED COMPONENTS')
            self.tool_pages=[];self.console=TerminalConsole()
            for kind in kinds:
                page=self.add_page(TOOLS[kind][0]);tool=ToolPage(kind);self.tool_pages.append(tool)
                tool.result_ready.connect(lambda value,k=kind:self.record_result(k,value));page.addWidget(tool)
            recipe=self.add_page('Recipe editor','Edit a script and copy it into Workshop to run with execution loadouts.')
            self.editor=WorkshopEditor();self.editor.setPlainText('from toolkit_core import execute\nfrom ultimate_terminal import terminal as term\nfrom shared_loadout import set_value\n\nresult = execute("json_lab", \'{"ready": true}\')\nset_value("toolkit.report", result)\nterm.print(result)\n');recipe.addWidget(self.editor)
            recipe.addWidget(button('Save Python recipe',self.save_recipe))
            console=self.add_page('Terminal');console.addWidget(self.console)
            self.map=WorkflowMap();self.map.nodes=[{'id':'input','depends_on':[],'status':'ready'},{'id':'analyze','depends_on':['input'],'status':'ready'},{'id':'report','depends_on':['analyze'],'status':'ready'}]
            flow=self.add_page('Pipeline');flow.addWidget(self.map)
            models=self.add_page('Model studio','Original asset preview; right-click for camera, quality and PNG export.')
            self.preview=PreviewPanel();self.preview.set_item(theme().PRIMARY_ITEMS[0]);models.addWidget(self.preview)
            shared=self.add_page('Shared results','Reads/writes the launching Workshop workspace through the shared-data SDK.')
            self.shared_output=WorkshopEditor();self.shared_output.setReadOnly(True);shared.addWidget(self.shared_output)
            shared.addWidget(button('Refresh shared state',self.refresh_shared));self.refresh_shared()
            self.add_action('Save recipe',self.save_recipe,'Ctrl+S')
            self.console.feed('toolkit','\x1b[36mAdvanced workspace ready. Run a tool to populate reports.\x1b[0m\n')

        def record_result(self,kind,value):
            self.console.feed(kind,'\x1b[32mAnalysis complete\x1b[0m\n'+value[:4000]+'\n')
            self.map.nodes[1]['status']='succeeded';self.map.nodes[2]['status']='ready';self.map.update()
            try:
                from shared_loadout import set_value
                set_value('toolkit.'+kind,value);self.refresh_shared()
            except RuntimeError:self.notice('Report ready; launch from Workshop to publish shared state')

        def refresh_shared(self):
            try:
                from shared_loadout import all_values
                self.shared_output.setPlainText(json.dumps(all_values(),indent=2))
            except RuntimeError:self.shared_output.setPlainText('Launch from Workshop for shared-state integration.')

        def save_recipe(self):
            path,_=QFileDialog.getSaveFileName(self,'Save Workshop recipe','recipe.py','Python (*.py)')
            if path:
                try:Path(path).write_text(self.editor.toPlainText(),encoding='utf-8');self.notice('Saved '+path)
                except OSError as exc:self.notice(str(exc))

        def closeEvent(self,event):
            for page in self.tool_pages:page.shutdown()
            super().closeEvent(event)
    return AdvancedWindow()
