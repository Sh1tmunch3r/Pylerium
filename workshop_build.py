"""Non-blocking, cancellable Workshop executable builds."""
from pathlib import Path
from PyQt6.QtCore import QProcess,QProcessEnvironment,QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QCheckBox,QHBoxLayout,QFileDialog,QMessageBox,QWidget,QComboBox,QSpinBox,QPlainTextEdit,QScrollArea
from gui_components import button,label,STYLE,Disclosure
from terminal_console import TerminalConsole
from app_paths import python_executable,sdk_root
from asset_helper import ASSETS


class BuildDialog(QDialog):
    def __init__(self,window,project):
        super().__init__(window);self.host=window;self.project=project
        self.setWindowTitle('Workshop // Build executable');self.resize(960,700);self.setStyleSheet(STYLE)
        box=QVBoxLayout(self);box.addWidget(label('BUILD APPLICATION',26))
        box.addWidget(label('Package your project with the shared styling, GUI SDK, model renderer and resource files.'))
        form=QFormLayout();self.name=QLineEdit(project['name']);self.output=QLineEdit(str(Path(project['script']).parent/'dist'))
        self.python=QLineEdit(window.profile_python.text() or python_executable())
        self.extra_imports=QLineEdit();self.extra_imports.setPlaceholderText('Optional: dynamic package imports, comma-separated')
        self.icon=QLineEdit();self.icon.setPlaceholderText('Default application icon')
        icon_row=QHBoxLayout();icon_row.addWidget(self.icon);icon_row.addWidget(button('Choose icon',self.choose_icon));icon_row.addWidget(button('Clear',self.icon.clear))
        form.addRow('Application name',self.name);form.addRow('Build Python',self.python)
        form.addRow('Additional imports',self.extra_imports)
        form.addRow('Application icon',icon_row)
        row=QHBoxLayout();row.addWidget(self.output);row.addWidget(button('Browse',self.choose_output));form.addRow('Output folder',row)
        self.console_mode=QCheckBox('Keep a terminal window (command-line tools)');self.console_mode.setChecked(not project.get('interactive',False))
        self.assets=QCheckBox('Include complete assigned asset library');self.assets.setChecked(window.settings.get('build_assets',True))
        self.plugins=QCheckBox('Include installed plugin sources');self.plugins.setChecked(window.settings.get('build_plugins',True))
        form.addRow(self.console_mode);form.addRow(self.assets);form.addRow(self.plugins);box.addLayout(form)
        advanced=QWidget();fields=QFormLayout(advanced)
        self.packaging=QComboBox();self.packaging.addItems(['Single executable','Application folder'])
        self.version=QLineEdit();self.version.setPlaceholderText('Optional: 1.0.0.0')
        self.company=QLineEdit();self.description=QLineEdit();self.product=QLineEdit();self.copyright=QLineEdit()
        self.debug=QComboBox();self.debug.addItems(['None','all','imports','bootloader','noarchive'])
        self.optimize=QSpinBox();self.optimize.setRange(0,2)
        self.clean=QCheckBox('Clean build cache');self.clean.setChecked(True)
        self.noupx=QCheckBox('Disable UPX compression');self.noupx.setChecked(True)
        self.admin=QCheckBox('Request administrator privileges at launch')
        self.advanced_json=QPlainTextEdit();self.advanced_json.setMaximumHeight(140)
        self.advanced_json.setPlainText('{"data": [], "binaries": [], "collect_all": [], "exclude": [], "paths": [], "hooks": [], "runtime_hooks": [], "extra_args": []}')
        for title,control in [('Packaging',self.packaging),('Version',self.version),('Company',self.company),('Description',self.description),('Product',self.product),('Copyright',self.copyright),('Debug mode',self.debug),('Optimization',self.optimize),('',self.clean),('',self.noupx),('',self.admin),('Resources / advanced JSON',self.advanced_json)]:fields.addRow(title,control)
        fields.addRow(label('Resource entries use source:destination. Advanced JSON also accepts splash, manifest, version_file, runtime_tmpdir, collect_submodules, hidden_imports, uac_uiaccess and disable_traceback. extra_args accepts any additional PyInstaller arguments as separate strings.',11,'#9aabb4'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(advanced);scroll.setMaximumHeight(300)
        box.addWidget(Disclosure('BRANDING / PACKAGING / ADVANCED OPTIONS',scroll))
        saved=window.store.get('settings','build:'+project['id'],{})
        self.icon.setText(saved.get('icon','') or '')
        for key,field in [('version',self.version),('company',self.company),('description',self.description),('product',self.product),('copyright',self.copyright)]:field.setText(saved.get(key,''))
        self.packaging.setCurrentIndex(int(saved.get('onedir',False)));self.optimize.setValue(saved.get('optimize',0))
        self.clean.setChecked(saved.get('clean',True));self.noupx.setChecked(saved.get('noupx',True));self.admin.setChecked(saved.get('uac_admin',False))
        if saved.get('debug'):self.debug.setCurrentText(saved['debug'])
        if saved.get('_advanced_json'):self.advanced_json.setPlainText(saved['_advanced_json'])
        box.addWidget(label('Build Python must have PyInstaller and the application dependencies installed. Local project files are bundled; additional external packages must be installed in that interpreter. User databases remain in persistent application storage.',11,'#9aabb4'))
        self.log=TerminalConsole();box.addWidget(self.log,1)
        self.status=label('READY',12,'#26d8ee');box.addWidget(self.status)
        actions=QHBoxLayout();self.build=button('BUILD EXE',self.start,True);self.cancel=button('CANCEL BUILD',self.stop);self.cancel.setEnabled(False)
        actions.addWidget(self.build);actions.addWidget(self.cancel);actions.addWidget(button('OPEN OUTPUT',self.open_output));box.addLayout(actions)
        self.process=QProcess(self);self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished);self.process.errorOccurred.connect(self.failed)

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,'Executable output',self.output.text())
        if path:self.output.setText(path)

    def choose_icon(self):
        filename,_=QFileDialog.getOpenFileName(self,'Application icon',self.icon.text(),'Icons / images (*.ico *.png *.jpg *.jpeg *.webp *.bmp)')
        if filename:self.icon.setText(filename)

    def options(self):
        import json
        result=json.loads(self.advanced_json.toPlainText())
        if not isinstance(result,dict):raise ValueError('Advanced options must be a JSON object')
        result.update(icon=self.icon.text().strip() or None,onedir=self.packaging.currentIndex()==1,
            optimize=self.optimize.value(),clean=self.clean.isChecked(),noupx=self.noupx.isChecked(),uac_admin=self.admin.isChecked())
        for key,field in [('version',self.version),('company',self.company),('description',self.description),('product',self.product),('copyright',self.copyright)]:
            if field.text().strip():result[key]=field.text().strip()
        if self.debug.currentText()!='None':result['debug']=self.debug.currentText()
        return result

    def start(self):
        import re
        import json
        from file_saving import write_text_atomic
        try:options=self.options()
        except (ValueError,TypeError) as exc:self.status.setText(str(exc));return
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,79}',self.name.text().strip()):
            self.status.setText('Use letters, numbers, spaces, underscores or dashes for the application name.');return
        if not Path(self.python.text()).is_file():self.status.setText('Choose an existing Python interpreter.');return
        destination=Path(self.output.text()).resolve()
        self.target=destination/(self.name.text().strip() if options.get('onedir') else '')/(self.name.text().strip()+'.exe')
        if self.target.exists() and QMessageBox.question(self,'Replace executable',f'Replace {self.target}?')!=QMessageBox.StandardButton.Yes:return
        args=['-u',str(sdk_root()/'build_exe.py'),'--project',self.project['script'],
            '--name',self.name.text().strip(),'--output',str(destination),'--project-id',self.project['id'],'--no-icon-picker']
        config=self.host.store.root/'build-options'/(self.project['id']+'.json')
        write_text_atomic(config,json.dumps(options,indent=2));args.extend(['--options-file',str(config)])
        self.host.store.put('settings','build:'+self.project['id'],{**options,'_advanced_json':self.advanced_json.toPlainText()})
        if self.console_mode.isChecked():args.append('--console')
        if self.assets.isChecked():args.extend(['--assets',str(ASSETS.root)])
        if self.plugins.isChecked():
            args.extend(['--plugins',str(self.host.plugin_host.root)])
            for ident in self.host.plugin_host.enabled():args.extend(['--enabled-plugin',ident])
        for module in self.extra_imports.text().split(','):
            if module.strip():args.extend(['--hidden-import',module.strip()])
        env=QProcessEnvironment.systemEnvironment();env.insert('PYTHONIOENCODING','utf-8')
        self.process.setProcessEnvironment(env)
        self.build.setEnabled(False);self.cancel.setEnabled(True);self.status.setText('BUILDING // live output below')
        from ui_audio import play_cue
        play_cue("deploy")
        self.process.start(self.python.text(),args)

    def read(self):self.log.feed('build',bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace'))
    def finished(self,code,status):
        self.read();self.build.setEnabled(True);self.cancel.setEnabled(False)
        ok=code==0 and status==QProcess.ExitStatus.NormalExit and self.target.is_file()
        from ui_audio import play_cue
        play_cue('success' if ok else 'error')
        self.status.setText('BUILT // '+str(self.target) if ok else 'BUILD FAILED / CANCELLED // see output')
        if ok:
            self.host.store.put('build',self.project['id'],{'id':self.project['id'],'name':self.name.text().strip(),'path':str(self.target)})
    def failed(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self.status.setText(self.process.errorString());self.build.setEnabled(True);self.cancel.setEnabled(False)
    def stop(self):
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            # PyInstaller launches child tools; stop the build tree, not just its parent.
            import subprocess,os
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(self.process.processId()),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            else:self.process.kill()
    def open_output(self):QDesktopServices.openUrl(QUrl.fromLocalFile(self.output.text()))
    def closeEvent(self,event):
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            if QMessageBox.question(self,'Build running','Cancel the build and close?')!=QMessageBox.StandardButton.Yes:event.ignore();return
            self.stop();self.process.waitForFinished(3000)
        event.accept()
