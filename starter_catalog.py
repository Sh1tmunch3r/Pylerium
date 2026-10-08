"""Curated, opt-in plugins and complete editable Workshop projects."""
from textwrap import dedent
from toolkit_core import TOOLS

STARTER_PLUGIN_IDS=['starter_'+kind for kind in TOOLS]+['starter_guide','starter_run_observatory','starter_workspace_inspector']

PROJECTS={
    'Data engineering lab':('json_lab','csv_profiler','sqlite_explorer','markdown_report'),
    'Source review workstation':('python_inspector','text_diff','regex_lab','log_analyzer'),
    'Digital asset audit':('file_catalog','file_integrity','duplicate_finder'),
    'Incident investigation desk':('log_analyzer','regex_lab','text_diff','sqlite_explorer'),
    'Report publishing studio':('json_lab','csv_profiler','markdown_report','codec_lab'),
    'Developer utilities cockpit':('python_inspector','json_lab','codec_lab','file_integrity'),
}

ADVANCED_TEMPLATES={}
for title,kinds in PROJECTS.items():
    ADVANCED_TEMPLATES['GUI / Advanced / '+title]=dedent(f'''
        # Complete application: tool processes, cancellation, editor, terminal,
        # model studio, pipeline map and shared workspace results.
        # Extend toolkit_ui.advanced_window or subclass the returned window type.
        from pylerium_gui import create_application, run, configure_audio
        from toolkit_ui import advanced_window

        def MyWindow():
            return advanced_window({title.upper()!r}, {kinds!r})

        def main():
            app = create_application({title!r})
            # configure_audio(enabled=True, volume=18)
            window = MyWindow()
            return run(window)

        if __name__ == '__main__':
            raise SystemExit(main())
    ''').strip()+'\n'
