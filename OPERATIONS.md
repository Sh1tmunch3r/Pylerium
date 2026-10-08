# <img width="559" height="559" alt="pixil-frame-0 (12)" src="https://github.com/user-attachments/assets/daea753a-f6af-43d6-bb30-8bb5cdde061d" />
# Pylerium local operations

Detailed authoring guides: [Workshop and terminal](WORKSHOP.md) · [Plugin builder and API](PLUGINS.md) · [Windows executable](BUILD.md)

Requires Python 3.10+; install the complete runtime with `python -m pip install -r requirements.txt`. AI assistance is optional. Models load asynchronously and use the current textured renderer, with software fallback where GPU rendering is unavailable. Native Qt OpenGL is an optional path (`PYLERIUM_NATIVE_GL=1`).

```powershell
python loadout-menu.py          # Original loadout menu with asset support
python orchestration-menu.py    # Separate local runner / orchestration workspace
python test_orchestration.py    # Offscreen integration checks
```

The runner is a copy of the asset-enabled menu with a separate functional interface. It reuses the original background, typography, selection cards, wireframe canvas, and preview panel. Its lobby, loadouts, operators, maps, missions, arsenal, workshop, console, barracks, assets, settings, and plugins pages use the BO6-inspired theme. It is not a pixel-identical recreation of every game screen and includes no proprietary game assets.

## Assets

`assets/manifest.json` maps **item names, stable `project:<id>` keys and `loadout:<project-id>:<slot>` keys** to files beneath `assets/`. Missing images/models fall back to the existing procedural artwork. Example assets are original SVG drawings and a simple OBJ inspection prop.

```json
{
  "background": "backgrounds/lobby.svg",
  "background_opacity": 0.55,
  "items": {
    "XM4": {
      "icon": "icons/receiver.svg",
      "model": "models/receiver.obj",
      "rotation": [0, 0, 0]
    }
  }
}
```

Icons fit within the card's image zone, preserving aspect ratio and leaving labels clear. `ASSETS.icon()` returns a centered, transparent, DPI-aware QIcon. Backgrounds fill their area with cropping; the original gradient, vignette, orange lighting, and animated atmospheric overlays remain above them.

OBJ models support vertices, polygon faces, negative indices, UV coordinates, and line segments. They are centered and fitted automatically; `rotation` contains X/Y/Z angles in degrees. Keep the OBJ, referenced `.mtl` files, and texture subfolders together when importing: the importer copies referenced dependencies while preserving their relative paths. References must resolve inside the source model folder; missing or external resources are reported. **Existing models imported by the older single-file importer must be re-imported from their original folder to recover omitted materials/textures.**

Models and textures load on background workers rather than inside card paint events. Import **OBJ, GLB, glTF, STL, PLY and OFF**. Keep external material/texture dependencies alongside their source model when importing. Static geometry is supported; skeletal animation is not evaluated. GPU shading supports discovered materials and maps; software fallback preserves textured model inspection. Missing resources and unsupported content show an explanation.

The Assets studio selects project and execution-slot assignments, filters targets, previews images and models, adjusts rotation, assigns texture overrides and removes artwork. Use **Reload Asset Manifest** after external changes. Each loadout card shows static image/model artwork; its inspection panel supports orbit, zoom, fit, materials/wireframe and expanded inspection.

The runner's **Assets** page imports files and updates the manifest. From Python:

```python
from asset_helper import ASSETS
icon = ASSETS.import_file(r"C:\art\tool.png", "icon")
model = ASSETS.import_file(r"C:\art\tool.obj", "model")
ASSETS.set_item("project:<saved-project-id>", icon=icon, model=model, rotation=[0, 90, 0])
texture = ASSETS.import_file(r"C:\art\diffuse.png", "texture")
ASSETS.set_item("project:<saved-project-id>", texture=texture)  # optional override; MTL maps are automatic
background = ASSETS.import_file(r"C:\art\lobby.jpg", "background")
ASSETS.set_background(background, opacity=0.6)
```

`loadout-menu.assets-backup.py` supplies the execution screen’s original card template. The project-aware screen, runtime and artwork integration live in `project_loadout_ui.py`, `project_loadout.py`, `loadout_runtime.py` and `loadout_artwork.py`. Local backup snapshots are ignored by Git.

## Navigation and execution

- **Lobby:** select a saved project and execution loadout, deploy, inspect activity, or stop all operations.
  <img width="1897" height="1050" alt="image" src="https://github.com/user-attachments/assets/eaff0769-40f8-46f3-a61f-ba1f33f9a500" />
- **Loadouts:** save interpreter paths, environment JSON, and timeouts. Zero disables the timeout. Edit shared JSON values available to every operator.
  <img width="1905" height="1069" alt="image" src="https://github.com/user-attachments/assets/e8f96acd-0636-4023-8579-8fcf683f3b94" />
- **Operators:** save callsigns paired with projects and execution loadouts. Deploy them independently.
  <img width="1900" height="1061" alt="image" src="https://github.com/user-attachments/assets/8ce99662-7304-43d8-8f85-8f881af97e2d" />
- **Maps:** edit, visualize, validate, and deploy dependency graphs. Independent nodes run concurrently up to the configured limit. Failed/cancelled dependencies skip downstream nodes. Only one map runs at a time; manual projects can also occupy execution slots.
  <img width="1900" height="1060" alt="image" src="https://github.com/user-attachments/assets/a229802b-1738-4063-b7d3-9d62a154b200" />
- **Missions:** schedule saved maps at recurring intervals while the app is open. Busy runners defer a mission; missed intervals are not replayed. Stop-all disables recurring missions.
  <img width="1896" height="1062" alt="image" src="https://github.com/user-attachments/assets/f3afedee-2d73-4b74-b4bd-86a8221295c0" />
- **Arsenal:** open a project execution loadout, import a Python entry script, or export/import bundles. Right-click projects for editor/run actions, renaming, duplication, opening the project folder, copying its path and assigning artwork to individual slots.
  <img width="1904" height="1069" alt="image" src="https://github.com/user-attachments/assets/1ebdab4c-a076-48d9-9958-30944d361648" />
  <img width="1904" height="1059" alt="image" src="https://github.com/user-attachments/assets/9e2db947-0ec9-4cb9-9067-54d4c36f61d9" />
- **Workshop:** create tools from templates, edit highlighted Python with line numbers and automatic indentation, set JSON arguments and working directories, save, and run. Imported scripts are copied; adjacent modules/resources are not copied automatically. Use a working directory containing required resources and imports.
  <img width="1911" height="1069" alt="image" src="https://github.com/user-attachments/assets/0b38223f-121e-4a98-96fd-54e50e50715a" />
- **Console:** render ANSI colors, tables, gradients, and cursor-based progress output. Select an isolated run or a grouped view of all runs, freeze the display, customize fonts/output themes/styles, stop selected jobs, and export readable output.
  <img width="1906" height="842" alt="image" src="https://github.com/user-attachments/assets/70578259-8d38-4769-9105-990f856f1981" />
- **Barracks:** inspect persisted run status, duration, exit codes, and logs.
  <img width="1908" height="1069" alt="image" src="https://github.com/user-attachments/assets/1824ecac-21aa-43a2-8351-0bb81bffe384" />
- **Assets/Settings:** customize artwork, concurrent process limits, motion, and optional Ollama assistance.
  <img width="1909" height="1064" alt="image" src="https://github.com/user-attachments/assets/390a080c-6d67-4942-bf08-30805c60c4df" />
  <img width="1918" height="1079" alt="image" src="https://github.com/user-attachments/assets/8bf1b0f9-1dcb-46cc-b080-ec1e814c2c76" />
- **Plugins:** rescan local extensions, explicitly enable/disable them, or create a scaffold. The bundled Output Tools example starts disabled.
  <img width="1911" height="1074" alt="image" src="https://github.com/user-attachments/assets/62dc67f5-e96a-49df-add8-d8c7f81591ec" />

## Dynamic assignment and workflow builder

Project, loadout, operator and mission references are selected from saved workspace entities. The Assets picker lists projects and existing items; project artwork is stored against a stable project ID, so a rename retains the assignment. Older name-based project artwork is upgraded automatically while retaining its original item entry.

In Maps, use **Add Node** to select a project, loadout, optional operator and prerequisite checkboxes. A unique step label is generated automatically. The step table shows project/loadout names and supports edit/remove actions; JSON remains available for advanced editing. **Fix Duplicate Labels** repairs repeated labels without deleting steps. Dependencies referring to an old duplicate label remain attached to its first occurrence; review that choice before saving. Removing a step also removes references to it from downstream prerequisites.

## In-app plugin builder
<img width="1560" height="669" alt="image" src="https://github.com/user-attachments/assets/d5d3e193-dacf-452b-ba4d-238709871cc5" />

Both the Workshop and plugin-builder editors have a small **Focus editor** button. It moves the same editor into a nearly full-screen themed card; its document, cursor, selection, and undo history remain intact. Use Return to Menu or Escape to restore it. Save works in the card, with Ctrl+S as a shortcut.

Python suggestions appear after a short pause when typing an identifier, or after a recognized member prefix such as `term.` or `ctx.`. Suggestions include keywords, built-ins, names found in the current document, and selected SDK/standard-library member hints. Tab or a click accepts a suggestion; Escape dismisses it and Ctrl+J requests one. Suggestions are suppressed inside comments/strings and can be disabled in the focus-card header. This is local lightweight completion, without executing imports, contacting AI, or requiring a language server; it is not full VS Code/Pylance type inference.

The Plugins tab includes a full Python editor with metadata, file selection, companion module creation, syntax validation, saving, explicit enabling/reloading, and disabling. Double-click an existing plugin (or use Edit Selected) to modify it. New plugins can start from custom extension, UI page, project launcher, shared-data tool, execution hook, output style/template, or script-command examples. These templates are starting points; you can replace their code with any plugin supported by the Python host API.

A display name automatically supplies the plugin ID when creating a new plugin. Existing IDs stay fixed. **Validate** checks all Python modules and the entry file's `register(ctx)` function without running the plugin. **Save** writes its metadata/code and leaves activation unchanged. **Save & Enable / Reload** explicitly executes registration and updates workspace contributions. Registration failures remove partially added contributions, leave the plugin disabled, and show the error. Unsaved plugin changes are checked before switching plugins or closing the app.

Plugins can use `ctx.selector('project')`, `ctx.selector('profile')`, `ctx.selector('operator')`, or `ctx.selector('workflow')` to get a live QComboBox of saved entities. `currentData()` returns the stable ID and `currentText()` displays the name. These selectors refresh after workspace changes, so a project-launcher plugin never needs hardcoded project names or IDs. Custom code continues to have normal application permissions; slow plugin callbacks should use background workers.

F11 toggles fullscreen; Escape exits fullscreen first, otherwise returns to the lobby. Drag the preview to orbit, scroll to zoom, and double-click to reset.

Maps use this format (IDs are shown in the JSON editor; the demo is preconfigured):

```json
{
  "nodes": [
    {"id": "prepare", "project": "hello", "profile": "default", "operator": "local", "depends_on": []},
    {"id": "build", "project": "hello", "profile": "default", "operator": "local", "depends_on": ["prepare"]}
  ]
}
```

Each node chooses its own project/profile; `operator` supplies its execution callsign. The separately saved operator pairing is used when deploying from the Operators page.

## Project loadout and runtime policies

Loadouts are saved per project as JSON in the local document store. The primary entry point accepts a base argument array plus any named attachment arrays. Secondary processes may run before execution or alongside it; companions stop when the primary pipeline ends. Context loads a selected environment file and explicit variable overrides.

| Slot | Runtime behavior |
| --- | --- |
| Primary | Entry point, CLI arguments and editor access |
| Secondary | Pre-execution helpers or companion processes |
| Tactical | cProfile, debug logging or strict warnings |
| Output / lethal | JSON execution report or configured post-run script |
| Field upgrade | Environment file and variable overrides |
| Perks and specialty | Assignable policy toggles |
| Wildcard | Worker/device hints or multiple execution passes |

**Run Project executes Python; it never invokes built-in EXE packaging.** Use **Workshop → Build EXE** explicitly. Old `pyinstaller`/`build_compiler` output hook selections normalize to `none`.

- **Ghost:** use a project `.venv` with the installed SDK dependencies available through system site packages. Existing environments are updated to keep those dependencies visible.
- **Scavenger:** install `requirements.txt` when present, otherwise continue with available dependencies.
- **Juggernaut:** request Windows administrator access, wait for the elevated project, stream its output and preserve its exit code. Declining elevation fails the run.
- **Ninja:** hide console windows while retaining captured project output.
- **Sleight of Hand:** run Ruff formatting before execution; Ruff must be available in the selected interpreter.
- **Hardline:** continue after optional helper-hook failures; primary project failures still fail the run.

Overkill and Danger Close provide CPU worker and CUDA-device hints. Project libraries must support and use these settings; selecting them does not automatically parallelize code or install GPU drivers. Repeat runs the configured number of passes and stops on primary failure.

## Shared data and persistence
<img width="1879" height="807" alt="image" src="https://github.com/user-attachments/assets/a13e5052-f75f-4521-b788-7224260c60b7" />

`orchestration_data/shared.sqlite3` stores projects, profiles, operators, maps, missions, settings, shared JSON values, workflow results, and run logs. Code lives under `orchestration_data/projects/`. SQLite WAL and atomic updates allow concurrent workers to share state without losing increments.

```python
from shared_loadout import get, set_value, update, all_values

set_value("build_result", {"ok": True})
update("completed", lambda old: (old or 0) + 1)
print(get("build_result"))
```

Deployed scripts receive `ORCHESTRATOR_SHARED_DB`, `ORCHESTRATOR_RUN_ID`, `ORCHESTRATOR_OPERATOR`, and `ORCHESTRATOR_PROJECT_ID`. The shared-state SDK is automatically added to their Python import path. This is local sharing within this workspace, not cross-machine synchronization.

Bundles include entry scripts, execution profiles, operators, maps, and shared values. They exclude dependencies, adjacent project files, artwork, run logs, schedules, and AI settings. Imports allocate new IDs, remap references, and preserve existing shared keys. Interpreter paths may need updating on another computer. Profile environment variables are included in exports.

Each run retains the most recent 2 MB of output; the live console retains 10,000 text blocks. Scripts execute with normal account permissions, not in a security sandbox. Stop and timeout controls kill the directly launched Python process; descendants spawned by a script require their own cleanup. The UI must remain open for missions to run.

## Optional Ollama
<img width="1298" height="296" alt="image" src="https://github.com/user-attachments/assets/1bfc4be8-f0dd-4483-9b17-78747b355438" /><img width="349" height="816" alt="image" src="https://github.com/user-attachments/assets/bdc89fe9-f617-44d0-a1ae-711c5e54a1ae" />

AI is **off by default**. Enable it in Settings and enter a dynamic HTTP(S) endpoint. The downloaded-model selector loads from [`GET /api/tags`](https://docs.ollama.com/api/tags); choose a model and save. Discovery is asynchronous with a 10-second timeout and never downloads models. Re-enable assistance or use Refresh Downloaded Models after changing servers/models.

The Workshop sends your prompt to Ollama's [`POST /api/generate`](https://docs.ollama.com/api/generate) endpoint only when you click Generate Draft. Requests are asynchronous and have a 120-second transfer timeout. Python Markdown fences (including spaced backticks), response prose outside fences, standalone language tags, and reasoning tags are removed. Valid Python strings containing backticks are preserved. Drafts can be corrected in the draft editor; invalid Python is not inserted. Drafts must be applied, reviewed, saved, and explicitly run; no model automatically executes code. The runner works without Ollama installed.

## Ultimate Terminal in Workshop scripts

The runner makes `ultimate_terminal` importable and forces color-enabled UTF-8 output for launched scripts. Existing terminal APIs remain available, including tables, panels, banners, spinners, live progress, and custom styles.

```python
from ultimate_terminal import terminal as term, Style, RGB

term.success('Connected')
term.print(term.gradient('PYLERIUM'))  # gradient() returns styled text
term.table([['Build', 'OK']], headers=['Stage', 'Result'])
term.add_style('important', Style(foreground=RGB.from_hex('#ff7b1c'), bold=True))
term.print('Important result', style='important')
term.progress(100, label='Build', newline=False)
print()
```

Use **Styled terminal output** when creating a project, or **Insert Terminal Example** in the Workshop. Console themes and style JSON apply to new runs; scripts can also call `term.set_theme()` and `term.add_style()` directly. For example, save this in the Console's Custom Styles field:

```json
{"important": {"foreground": "#ff7b1c", "background": "#172029", "bold": true}}
```

Supported styles include foreground/background RGB colors, bold, italic, underline, and strike. The Console renders standard/bright/256-color/truecolor SGR sequences, carriage returns, line erasure, basic cursor movement, and save/restore controls. It is an output display, not a full interactive shell or VT emulator: unsupported terminal modes/controls are ignored and it has no stdin entry. Each run has independent cursor/style state so concurrent spinners cannot erase another run's output. A display stream retains at most 10,000 blocks/1,000,000 characters; up to 64 streams are displayed. Raw ANSI remains in the persisted run logs for replay; Console exports contain readable text. Freeze View pauses redraw while output continues to be collected.

## Local plugin API (version 1)

Create a folder under `plugins/` with these files:

```json
{"id":"my_tools","name":"My Tools","api_version":1,"entry":"plugin.py","description":"Workspace extensions"}
```

```python
def summarize(values):
    return {"count": len(values)}

SCRIPT_COMMANDS = {"summarize": summarize}

def register(ctx):
    ctx.add_action('Show summary', lambda: ctx.log(summarize(ctx.store.shared())))
    ctx.add_template('Starter', "print('Hello plugin')\n")
    ctx.add_style('highlight', foreground='#ff7b1c', bold=True)
    ctx.on('run_finished', lambda run_id, status: ctx.log(f'{run_id}: {status}'))

def unregister(ctx):
    # Stop timers / disconnect your own signals here, if needed.
    pass
```

`ctx.add_page(name, QWidget)` adds a functional navigation page. `ctx.window`, `ctx.store`, and `ctx.runner` expose the workspace, persistence, and runner. `ctx.on('output', callback)` receives `(run_id, raw_text)`; `run_finished` receives `(run_id, status)`. Hook failures are isolated and logged. Hooks run on the Qt UI thread: keep them short. The host removes registered pages/actions/templates/styles/hooks on disable; plugins must clean up any extra resources they create. Use package-relative imports such as `from .helpers import tool` for companion modules.

Workshop scripts can call explicitly enabled plugin commands:

```python
from workspace_plugins import call, available
from shared_loadout import all_values
print(available())
print(call('output_tools', 'summarize', all_values()))
```

Enabled plugins run with normal application permissions. Discovery reads manifests without importing code. Fresh plugins stay disabled; previously enabled plugins load on the next launch. Running scripts receive a snapshot of enabled plugin IDs. Import-safe plugins should create Qt widgets inside `register()` rather than at module import so their commands can also run in child Python processes. Plugin code and enablement are not included in project bundles.

Run both suites to verify the extensions and existing orchestration:

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

Ollama tests use a local mock HTTP server and cover discovery, generation, and cleaned insertion; they do not require a downloaded model or measure real model performance.


### Preview compatibility and editor templates

Model previews use the bounded textured software renderer by default to avoid Windows native OpenGL surface recreation interfering with menus and fullscreen controls. Textures, orbit, zoom and fit remain available; the software preview samples geometry on large models. Native GPU rendering is optional via `PYLERIUM_NATIVE_GL=1` before launch. Animation pauses while a popup or modal dialog is open. F11 toggles fullscreen from child controls; Escape exits fullscreen before returning to Lobby.

Workshop offers 15 editable boilerplates (CLI, shared state, terminal output, JSON, CSV, HTTP, logging, asyncio, threads, dataclasses, SQLite, subprocesses, file discovery and error handling) plus enabled plugin templates. Insert adds code after the current line in one undo step and never runs it. Plugin Builder offers its template dropdown and New from template both in the menu and the focus card, with the existing unsaved-changes prompt. The focus card uses the same dark/orange theme and retains the original editor and toolbar.
