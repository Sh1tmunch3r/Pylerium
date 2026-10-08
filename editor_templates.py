"""Local, editable starting points; insertion never runs code."""
from gui_templates import GUI_TEMPLATES, COMPONENT_TEMPLATES
WORKSHOP_TEMPLATES = {
    'Main entry point': 'def main():\n    print("Ready")\n\n\nif __name__ == "__main__":\n    main()\n',
    'Command-line arguments': 'import argparse\n\nparser = argparse.ArgumentParser(description="My tool")\nparser.add_argument("--name", default="World")\nargs = parser.parse_args()\nprint(f"Hello {args.name}")\n',
    'Styled terminal output': 'from ultimate_terminal import terminal as term\n\nterm.info("Starting operation")\nterm.success("Operation complete")\n',
    'Shared loadout data': 'from shared_loadout import get, set_value\n\ndata = get("my_tool", {})\ndata["status"] = "ready"\nset_value("my_tool", data)\nprint(data)\n',
    'JSON file read / write': 'import json\nfrom pathlib import Path\n\npath = Path("data.json")\ndata = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}\npath.write_text(json.dumps(data, indent=2), encoding="utf-8")\n',
    'CSV reader': 'import csv\nfrom pathlib import Path\n\nwith Path("data.csv").open(newline="", encoding="utf-8-sig") as stream:\n    for row in csv.DictReader(stream):\n        print(row)\n',
    'HTTP JSON request': 'import json\nfrom urllib.request import urlopen\n\nurl = "http://localhost:11434/api/tags"\nwith urlopen(url, timeout=10) as response:\n    data = json.load(response)\nprint(data)\n',
    'Logging setup': 'import logging\n\nlogging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")\nlog = logging.getLogger(__name__)\nlog.info("Tool started")\n',
    'Async task group': 'import asyncio\n\nasync def worker(value):\n    await asyncio.sleep(0.1)\n    return value\n\nasync def main():\n    print(await asyncio.gather(*(worker(i) for i in range(3))))\n\nasyncio.run(main())\n',
    'Thread pool': 'from concurrent.futures import ThreadPoolExecutor\n\ndef worker(value):\n    return value * 2\n\nwith ThreadPoolExecutor(max_workers=4) as pool:\n    print(list(pool.map(worker, range(10))))\n',
    'Dataclass configuration': 'from dataclasses import dataclass\n\n@dataclass\nclass Config:\n    name: str = "My tool"\n    retries: int = 3\n\nconfig = Config()\nprint(config)\n',
    'SQLite storage': 'import sqlite3\n\nwith sqlite3.connect("tool.db") as database:\n    database.execute("CREATE TABLE IF NOT EXISTS events (message TEXT)")\n    database.execute("INSERT INTO events VALUES (?)", ("Ready",))\n    print(database.execute("SELECT message FROM events").fetchall())\n',
    'Safe subprocess': 'import subprocess\nimport sys\n\nresult = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, timeout=30, check=True)\nprint(result.stdout)\n',
    'File discovery': 'from pathlib import Path\n\nroot = Path.cwd()\nfor path in root.glob("*.py"):\n    print(path.name, path.stat().st_size)\n',
    'Exception handling': 'import logging\n\ntry:\n    result = int("42")\nexcept ValueError:\n    logging.exception("Invalid input")\nelse:\n    print(result)\n',
}
WORKSHOP_TEMPLATES.update(GUI_TEMPLATES)
WORKSHOP_TEMPLATES.update(COMPONENT_TEMPLATES)
from starter_catalog import ADVANCED_TEMPLATES
WORKSHOP_TEMPLATES.update(ADVANCED_TEMPLATES)

from extended_templates import TOOL_GUI_TEMPLATES
WORKSHOP_TEMPLATES.update(TOOL_GUI_TEMPLATES)

from creative_templates import CREATIVE_TEMPLATES
WORKSHOP_TEMPLATES.update(CREATIVE_TEMPLATES)
