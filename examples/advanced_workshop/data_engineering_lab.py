from pathlib import Path
import sys
_example_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_example_root / "sdk" if (_example_root / "sdk").is_dir() else _example_root))

# Complete application: tool processes, cancellation, editor, terminal,
# model studio, pipeline map and shared workspace results.
# Extend toolkit_ui.advanced_window or subclass the returned window type.
from pylerium_gui import create_application, run
from toolkit_ui import advanced_window

def MyWindow():
    return advanced_window('DATA ENGINEERING LAB', ('json_lab', 'csv_profiler', 'sqlite_explorer', 'markdown_report'))

def main():
    app = create_application('Data engineering lab')
    window = MyWindow()
    return run(window)

if __name__ == '__main__':
    raise SystemExit(main())
