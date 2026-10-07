"""Packaged launcher with startup diagnostics and an end-to-end smoke check."""
import json
import os
import runpy
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from app_paths import resource_root, workspace_root, sdk_root
# The menu loads model and plugin modules dynamically; retain their source path.
sys.path.insert(0, str(sdk_root()))
# Explicit import lets the packager analyze the dynamically loaded menu's UI.
from orchestration_ui import OrchestrationWindow


def smoke_check(output):
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    namespace = runpy.run_path(str(resource_root() / 'orchestration-menu.py'))
    window = OrchestrationWindow(SimpleNamespace(**namespace))
    window.show()
    window.create_project('Same name', "print('first')\n")
    first = window.current_project
    window.create_project('Same name', "print('second')\n")
    second = window.current_project
    assert first != second
    window.code.setPlainText("from shared_loadout import update\nfrom ultimate_terminal import terminal as term\nimport sqlite3, ssl, asyncio\nupdate('exe_smoke', lambda old: (old or 0)+1)\nterm.success('STANDALONE_RUN_OK')\n")
    assert window.save_project()
    project = window.store.get('project', second)
    ident = window.runner.launch(project, window.store.get('profile', 'default'))
    deadline = time.monotonic() + 45
    while window.runner.jobs and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert not window.runner.jobs, 'Runner smoke check timed out'
    status, log = window.store.db.execute('SELECT status,log FROM runs WHERE id=?',(ident,)).fetchone()
    assert status == 'succeeded' and 'STANDALONE_RUN_OK' in log, (status,log)
    # Run the component gallery using the separate bundled interpreter, including
    # NumPy and native Qt imports. Automatically close the fixture's window.
    from gui_templates import GUI_TEMPLATES
    gui_code=GUI_TEMPLATES['GUI / Complete component gallery'].replace(
        'return run(window)',
        "from PyQt6.QtCore import QTimer\n    QTimer.singleShot(250, app.quit)\n    print('WORKSHOP_GUI_OK', flush=True)\n    return run(window)")
    window.create_project('GUI smoke',gui_code,interactive=True)
    gui_project=window.store.get('project',window.current_project)
    gui_ident=window.runner.launch(gui_project,window.store.get('profile','default'))
    deadline=time.monotonic()+45
    while window.runner.jobs and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert not window.runner.jobs,'Workshop GUI smoke timed out'
    gui_status,gui_log=window.store.db.execute('SELECT status,log FROM runs WHERE id=?',(gui_ident,)).fetchone()
    assert gui_status=='succeeded' and 'WORKSHOP_GUI_OK' in gui_log,(gui_status,gui_log)
    from starter_catalog import STARTER_PLUGIN_IDS,ADVANCED_TEMPLATES
    for plugin_id in STARTER_PLUGIN_IDS:
        descriptor=next(d for d in window.plugin_host.descriptors() if d['id']==plugin_id)
        window.plugin_host.enable(descriptor)
        if plugin_id=='starter_json_lab':
            tool=window.plugin_host.modules[plugin_id]._page;tool.analyze()
            deadline=time.monotonic()+35
            while not tool.start.isEnabled() and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            assert 'leaf_paths' in tool.result,tool.result
        window.plugin_host.disable(plugin_id)
        app.processEvents()
    # Static GLB decoding is exercised in both host and portable child interpreter.
    import trimesh
    fixture=window.store.root/'model-smoke.glb'
    mesh=trimesh.Trimesh(vertices=[[-1,-1,0],[1,-1,0],[0,1,0]],faces=[[0,1,2]],process=False)
    fixture.write_bytes(trimesh.Scene(mesh).export(file_type='glb'))
    from model_assets import load_model
    assert load_model(fixture).source_faces==1
    from model_preview import InteractiveModelCanvas
    from model_inspector import InspectWeaponDialog
    preview=InteractiveModelCanvas();preview.item_data=SimpleNamespace(name='Inspection fixture',category='WEAPON')
    preview.scene=load_model(fixture)
    inspection=InspectWeaponDialog(preview,window);inspection.show()
    deadline=time.monotonic()+20
    while inspection.canvas.surface_frame is None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert inspection.canvas.surface_frame is not None,'Inspection render timed out'
    renderer_info=inspection.canvas.renderer
    assert renderer_info.is_gpu,renderer_info.reason
    inspection.close();preview.close();app.processEvents()
    advanced_code=next(iter(ADVANCED_TEMPLATES.values())).replace(
        'return run(window)',
        "from model_assets import load_model\n    assert load_model("+repr(str(fixture))+ ").source_faces == 1\n"
        "    from PyQt6.QtCore import QTimer\n"
        "    def complete(value):\n        assert 'leaf_paths' in value\n        print('ADVANCED_TOOLKIT_OK', flush=True)\n        window.close()\n        app.quit()\n"
        "    window.tool_pages[0].result_ready.connect(complete)\n"
        "    QTimer.singleShot(250, window.tool_pages[0].analyze)\n"
        "    QTimer.singleShot(30000, app.quit)\n    return run(window)")
    window.create_project('Advanced toolkit smoke',advanced_code,interactive=True)
    advanced_ident=window.runner.launch(window.store.get('project',window.current_project),window.store.get('profile','default'))
    deadline=time.monotonic()+45
    while window.runner.jobs and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
    assert not window.runner.jobs,'Advanced toolkit smoke timed out'
    advanced_status,advanced_log=window.store.db.execute('SELECT status,log FROM runs WHERE id=?',(advanced_ident,)).fetchone()
    assert advanced_status=='succeeded' and 'ADVANCED_TOOLKIT_OK' in advanced_log,(advanced_status,advanced_log)
    window.navigate('WORKSHOP');window.code_card.open_focus();app.processEvents()
    window.code_card.dialog.close();app.processEvents()
    window.showFullScreen();app.processEvents();window.fullscreen();app.processEvents()
    assert not window.isFullScreen()
    # Exercise the dynamically loaded archive in the frozen host, without reading
    # the user's real browser history or recording desktop activity during a test.
    from plugin_system import load_module
    descriptor=next(d for d in window.plugin_host.descriptors() if d['id']=='jumpback')
    module=load_module(descriptor)
    archive=module.HistoryStore(window.store.root/'jumpback'/'history.sqlite3')
    archive.set('recording',False)
    window.plugin_host.enable(descriptor)
    page=window.plugin_host.modules['jumpback']._active_page
    archive.append([{'event_key':'exe-smoke-visit','occurred':time.time(),'kind':'VIDEO',
                     'source':'Smoke fixture','title':'Jumpback archive smoke check',
                     'target':'https://www.youtube.com/watch?v=smoke'}])
    page.generation+=1;page.request_query()
    deadline=time.monotonic()+10
    while page.tasks and time.monotonic()<deadline:
        app.processEvents();time.sleep(0.01)
    assert not page.tasks, 'Jumpback query timed out'
    assert archive.query(text='archive smoke',kind='VIDEO')[1]==1
    assert page.table.rowCount()>=1
    ident=archive.query(text='archive smoke')[0][0]['id']
    archive.annotate(ident,note='Persisted executable note',pinned=True)
    assert archive.query(text='executable note',pinned=True)[1]==1
    from threading import Event
    assert archive.export(window.store.root/'jumpback-smoke.json',{'text':'archive smoke'},Event())==1
    window.plugin_host.disable('jumpback')
    result = {'ok':True,'run_status':status,'log':log,'workspace':str(workspace_root()),
              'python':window.store.get('profile','default')['python'], 'same_name_projects':2,
              'workshop_gui':{'status':gui_status,'gallery':True,'log':gui_log},
              'starter_toolkit':{'plugins':len(STARTER_PLUGIN_IDS),'advanced_project':advanced_status,'glb':True,'log':advanced_log},
              'weapon_inspection':{'gpu':renderer_info.is_gpu,'renderer':renderer_info.name,'native_resolution':True},
              'jumpback':{'loaded':True,'search':True,'notes':True,'export':True}}
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    window.code.document().setModified(False);window.plugin_builder.dirty=False
    window.close();app.processEvents()


def main():
    try:
        if len(sys.argv) > 2 and sys.argv[1] == '--smoke-test':
            smoke_check(sys.argv[2])
        else:
            runpy.run_path(str(resource_root()/'orchestration-menu.py'), run_name='__main__')
    except Exception:
        folder=workspace_root();folder.mkdir(parents=True,exist_ok=True)
        error=traceback.format_exc()
        (folder/'startup-error.log').write_text(error,encoding='utf-8')
        if '--smoke-test' in sys.argv:
            Path(sys.argv[2]).write_text(json.dumps({'ok':False,'error':error}),encoding='utf-8')
        else:
            from PyQt6.QtWidgets import QApplication,QMessageBox
            app=QApplication.instance() or QApplication([])
            QMessageBox.critical(None,'Pylerium could not start',
                'Startup failed. Details were saved to:\n'+str(folder/'startup-error.log')+'\n\n'+error[-1500:])
        raise SystemExit(1)


if __name__ == '__main__':
    main()
