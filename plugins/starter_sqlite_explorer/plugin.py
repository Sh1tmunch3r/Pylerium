from toolkit_core import execute

def analyze(text, option=""):
    return execute('sqlite_explorer', text, option)

SCRIPT_COMMANDS = {"analyze": analyze}
_page = None

def register(ctx):
    global _page
    from toolkit_ui import register_tool
    _page = register_tool(ctx, 'sqlite_explorer')

def unregister(ctx):
    global _page
    if _page is not None: _page.shutdown()
    _page = None
