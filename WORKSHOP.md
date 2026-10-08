# Workshop and terminal guide

This guide covers authoring and running Python tools in Pylerium. For extensions to the app itself, see [PLUGINS.md](PLUGINS.md). For maps, scheduling, assets and workspace administration, see [OPERATIONS.md](OPERATIONS.md).

## Start the workspace

From the repository root, using your installed Python interpreter:

```powershell
python -m pip install PyQt6 numpy trimesh pillow moderngl
python orchestration-menu.py
```

Ollama and extra rendering libraries are optional. Use the interpreter's full path if `python` resolves to the Windows Store alias. Scripts use the interpreter selected in their execution loadout; install third-party script dependencies into that interpreter, for example `path/to/python.exe -m pip install requests`.

## Create, save and run a tool

1. Open **Workshop**, click **New**, name the project and choose a starting template.
2. Edit the code. Select an existing project in the left list to load it.
3. Set **Arguments** to a JSON array, such as `["--name", "Alex"]`. These are arguments, not a shell command.
4. Set **Working directory** to an existing folder containing your input files. Relative file paths resolve there.
5. Click **Save Project**, then **Run Saved Project**. Running uses the saved entry file; save your edits first.
6. Open **Console** for output and **Barracks** for persisted status, exit codes and logs.

Project code lives under `orchestration_data/projects/`. Import copies the entry script into the workspace; it does not copy sibling modules, datasets or dependencies. Keep required resources in the working directory or configure `PYTHONPATH` in the loadout for companion packages. Use the displayed project path to locate the actual saved entry file.

Execution loadouts configure the Python executable, environment-variable JSON and timeout. A timeout of zero disables it. The Lobby, Operators and Maps pages let you deploy a project with a chosen loadout. A nonzero exit code indicates failure; print useful errors or allow exceptions to show their traceback. Stop and timeout terminate the direct Python process; scripts that create subprocesses need to manage their children.

## Editor and focus mode

The editor provides Python highlighting, line numbers, automatic indentation and four-space Tab indentation. **Focus editor** opens the same editor in a large dark/orange card. Code, cursor and undo history are retained when you return. **Save** or **Ctrl+S** saves from the focus card. **Return to menu** closes the card; Escape dismisses a suggestion first, then closes the card. F11 toggles the main window's fullscreen state; Escape in the main window exits fullscreen before returning to Lobby.

Local completion appears after a short typing pause. It suggests Python keywords, built-ins, document names and selected members for `term`, `ctx`, `json`, `os`, `sys` and `self`. **Tab** or a click accepts a suggestion, **Escape** dismisses it, and **Ctrl+J** requests it. Turn off **Python suggestions** in the focus header if desired. This is a lightweight local helper, not full type inference; it does not execute imports or call a model.

## Insert boilerplate

Choose a template in the editor toolbar and click **Insert boilerplate**. The same toolbar is available in focus mode. Insertion adds code after the current line, preserves existing code and is undoable as one operation. Review imports, variable names and entry points before running: inserting a complete starter into a populated script can duplicate imports or `main()` blocks.

| Choice | Starting point |
| --- | --- |
| Main entry point | `main()` and the `__name__` guard |
| Command-line arguments | `argparse` options |
| Styled terminal output | Semantic terminal messages |
| Shared loadout data | Read and write workspace JSON |
| JSON file read / write | UTF-8 configuration file |
| CSV reader | Dictionary rows from a CSV file |
| HTTP JSON request | Standard-library request with timeout |
| Logging setup | Timestamped Python logging |
| Async task group | Concurrent asyncio tasks |
| Thread pool | Bounded threaded work |
| Dataclass configuration | Typed configuration object |
| SQLite storage | Parameterized database writes |
| Safe subprocess | Argument-list invocation with timeout |
| File discovery | Local `pathlib` iteration |
| Exception handling | Logged input errors |

Enabled plugins can contribute additional project templates. Reopen focus mode to refresh its template list after changing plugin activation. **Insert Terminal Example** also provides a terminal-oriented example.

## Build custom GUI applications

<img width="960" height="697" alt="image" src="https://github.com/user-attachments/assets/ded2ea8e-da50-4060-a45b-8e2722ca8baf" />

Six additional **GUI / Advanced / …** applications combine real tool processes, recipe editing, terminal output, shared results, model previews and pipeline visualization. See [Starter tools and projects](STARTER_TOOLS.md). Standalone example files are in `examples/advanced_workshop/`.

Choose **Workshop → New → GUI / …** for a complete runnable application. Runnable starters also appear in **Insert boilerplate** and in focus mode. Start with **GUI / Blank custom application** for an independent window with your own layout. Add only the components you need; the toolkit supplies the shared style, not the operations application.

| GUI starter | Reusable components |
| --- | --- |
| Blank custom application | Minimal window and your own layout, with shared panels and buttons |
| Panels and actions | Optional page navigation, panels and your own menu/toolbar actions |
| Forms and data pages | Settings inputs, selectors, checkboxes, tables and multipage navigation |
| Complete component gallery | Original icon buttons, loadout cards/sidebar, item selector dialog, stats, Python editor/focus card, ANSI console, lists, trees, tabs, sliders, progress, dialogs and file picker |
| Model preview and workflow | Original interactive model/material preview, statistics/controls and dependency map |
| Responsive background work | Worker-thread tasks with success/error callbacks delivered on the GUI thread |


**Insert boilerplate → GUI element / …** provides nine small snippets: panels/buttons, forms, menus/toolbars, tabs/data views, dialogs/file pickers, editor/terminal, model canvas, workflow map and background tasks. Insert these into your window's `__init__` after `super().__init__()`; insertion follows the current line's indentation. They add widgets to `self.content`; replace that layout with any layout in your own application. These snippets are insertion tools, not complete projects in the New dialog.

`systematic_gui` is the public toolkit; `gui_components` holds the **same** stylesheet and `button`, `label`, `panel` factories imported by the main application. Theme widgets come from the original menu classes. `WorkflowMap`, `WorkshopEditor`, `EditorCard`, `TerminalConsole`, model previews and item data use their original implementations. Menus, tabs, sliders and dialogs share the central style. All SDK modules are available through the runner's `PYTHONPATH`; create your own handlers and subclasses without duplicating styling.

```python
from pylerium_gui import create_application, AppWindow, button, panel, run

class MyTool(AppWindow):
    def __init__(self):
        super().__init__('MY TOOL', 'LOCAL WORKSPACE')
        # Compose your own layout directly; pages are optional.
        card, box = panel()
        box.addWidget(button('Run', lambda: self.notice('Ready'), primary=True))
        self.content.addWidget(card)
        self.content.addStretch()

if __name__ == '__main__':
    app = create_application('My tool')
    window = MyTool()
    raise SystemExit(run(window))
```

GUI projects created from **New** are marked interactive and stay open until you close them or click **Stop**. They do not inherit the batch-job timeout. If you insert a GUI starter into an existing batch project, use an execution loadout with timeout **0**. Keep file/network/CPU work in `window.run_background(work, on_success, on_error)`; worker functions return data and callbacks update widgets. `create_application` reuses an existing QApplication, and `run(window)` holds the window through the event loop.

The packaged interpreter includes Qt, NumPy, Trimesh, Pillow and ModernGL for these starters and model previews. If selecting an external interpreter, install `PyQt6 numpy trimesh pillow moderngl` there. The runner passes the current workspace path so custom GUIs use the same assigned assets/background. AppWindow creates no operations store, plugin host or built-in workspace pages. Its content layout is yours. Navigation appears only when you call add_page; menus and toolbars appear only when you add them. Animated backgrounds are optional via motion=True. PyleriumWindow remains an alias for older saved projects.

### Build standalone executables

Choose **Workshop → Build EXE** after saving your project. Select an application name, output folder and build Python. That interpreter needs `pyinstaller PyQt6 numpy trimesh pillow moderngl glcontext`. Builds run in a separate process with live output, cancellation and an Open Output action. GUI applications hide the terminal; console tools can keep it. Existing executables require an explicit replacement choice.

The exporter packages the complete shared GUI SDK and stylesheet, model renderer, a portable interpreter for background tools, and the project's companion files. Include the asset library and installed plugin sources using the build options; the enabled-plugin list is captured from the current workspace. Imported dependencies in project and plugin source are discovered. Use **Additional imports** for packages loaded dynamically by name. Optional scientific/ML engines are included when directly imported or explicitly requested rather than pulled in solely through Trimesh's optional adapters.

Each exported application keeps its own database and writable project data under `%LOCALAPPDATA%/<application name>/`, or an explicit `PYLERIUM_HOME`. Project companion files seed the writable working directory on first launch; subsequent launches retain edits. Updated executables run the newly bundled entry code. Shared state persists in `orchestration_data/shared.sqlite3`; source workspace databases are not shipped. Relative resource/data paths use the writable project directory. Model/image assignments come from the bundled manifest.

### Editors and compact controls

Project metadata and plugin details collapse independently of the editor. **Assist** opens the optional Ollama pane. Workshop has **Projects** and **Plugins** tabs. The Plugins tab keeps its searchable browser visible beside the builder; click a plugin to edit it. Existing Plugins links open this tab. All original options remain accessible. Splitters resize the Workshop panes; long action rows scroll horizontally instead of forcing the editor off-screen.

Every WorkshopEditor has **Ctrl+F / Ctrl+H** find and replace, regex/case/whole-word search, **Ctrl+G** line navigation, **Ctrl+/** comments, **Ctrl+D** duplicate lines, **Ctrl+[ / Ctrl+]** indentation, and **Ctrl+wheel** font zoom. The **Tools** menu adds Python syntax checking and wrapping. Replace All is a single undo operation. Focus mode retains the same document and tools. Settings → Display stores editor font size and interface scaling.

### Settings and stored-data removal

Settings uses category tabs, aligned setting rows and contextual descriptions. **Storage** lists projects, execution profiles, operators, workflows, schedules, build records, shared keys, run logs, plugins, asset bundles and other stored files. Removal shows affected configurations, detached asset assignments and managed files before confirmation. Deleting a project also removes operators/workflows/schedules that depend on it. The default execution profile is protected. Stop active operations and disable the owning plugin before deleting its data files.

Managed files move into `orchestration_data/trash` with a restoration receipt; external imported originals remain untouched. **Restore last removal** restores records and files without overwriting newer assignments or existing files. Restored plugins remain disabled. Removing the final project does not recreate demo content on restart. Invalid external manifest edits retain the last valid in-memory assignments and report an error.

### Texture previews

The default renderer uses an independent offscreen OpenGL context on a dedicated worker. It renders the full mesh at device resolution, with a depth buffer, 4× MSAA, mipmaps, up to 16× anisotropic filtering, smooth authored normals and studio lighting. Base-colour, normal/bump and metallic/roughness maps are loaded where supplied. Material buffers/textures stay on the GPU. At most one frame is in flight; paused views reuse their cached frame. Quality does not silently fall to 480 pixels during auto orbit. OpenGL 3.3 and ModernGL are required for GPU acceleration; a complete software renderer is retained as a fallback. No native Qt OpenGL child is required.

Click **Inspect weapon** beside the preview controls, or right-click the canvas and choose **Inspect weapon / model**. The large studio adds a 360° inspection animation, camera presets, orbit/pan/zoom, quality and wireframe controls, material/texture details, full-size texture viewing and PNG capture. All Workshop GUIs using the shared PreviewPanel inherit this feature; `InspectWeaponDialog` is also exposed by `systematic_gui`.

**Studio** quality adds 2× supersampling to paused views, capped at a 4K framebuffer. PNG capture retains the rendered framebuffer resolution, including overlays. **Native / sharp** is the default, with 4× MSAA and device-resolution rendering while orbiting. Capture uses the most recently completed frame; wait for the preview to settle after changing the camera or quality.

Imports preserve embedded/referenced maps for OBJ, GLB and glTF, and unambiguous named companion diffuse images for UV-equipped meshes (including PLY). STL/OFF typically contain no texture coordinates and render with material/vertex colours. **Assets → Use automatic model materials** chooses embedded/companion maps. **Override model texture** explicitly replaces diffuse maps. Replacing a model returns its material selection to automatic mode. Sidecars can include PNG/JPEG/WebP/BMP/TGA/DDS where Qt or Pillow can decode them; diffuse images are preserved up to 4K.

Models need their matching diffuse images and OBJ UVs for the original appearance. Empty/missing material files are reported in the preview status. Assigning an unrelated image maps that image onto the model's existing UVs; it cannot reconstruct the original material. Package an OBJ, its MTL file and referenced texture images together, or assign the intended texture in **Assets**.

## Ultimate Terminal quick start

The runner adds the SDK directory to `PYTHONPATH`, forces UTF-8/unbuffered output and enables ANSI color for the Console. No separate terminal library installation is needed.

```python
from ultimate_terminal import terminal as term, Style, RGB

term.banner("MY TOOL", width=60, gradient="fire")
term.info("Reading inputs")
term.warning("Using default configuration")
term.table([["Inputs", 12], ["Processed", 12]], headers=["Metric", "Value"])
term.panel("All files processed successfully", title="Result", width=60)
term.add_style("important", Style(foreground=RGB.from_hex("#ff7b1c"), bold=True))
term.print("Output saved", style="important")
term.success("Complete")
```

### Print versus formatted text

`term.print`, semantic messages, `banner`, `panel`, `table`, `separator`, `section`, `log`, `progress` and `live` write output. Formatting helpers such as `paint`, `gradient`, `rainbow`, `rgb`, `bold`, `dim`, `italic`, `underline`, `strike`, `badge` and `progress_bar` return strings. Print their results:

```python
term.print(term.gradient("PYLERIUM", "fire"))
term.print(term.bold("Ready"), term.badge("OK", "success"))
term.print(term.rgb("Accent", 255, 123, 28))
term.log("INFO", "Starting processing", timestamp=True)
term.section("Results", width=60)
term.separator(width=60)
```

Semantic message methods are `success`, `error`, `warning`, `info`, `debug`, `trace`, `title`, `header`, `muted` and `command`. `term.print` accepts multiple values, `style`, `sep`, `end`, `file` and `flush`.

### Themes and styles

Available themes are `cyber`, `purple`, `matrix`, `ocean`, `fire`, `royal`, `mono` and `neon`. Console theme/style settings are passed to newly launched processes. Changing settings does not recolor existing output. A script can override its theme:

```python
term.set_theme("fire")
term.add_style("notice", Style(
    foreground=RGB.from_hex("#ff7b1c"),
    background=RGB.from_hex("#172029"),
    bold=True,
))
term.print("Review this result", style="notice")
```

Console **Custom Styles** accepts a JSON object keyed by style name:

```json
{"notice": {"foreground": "#ff7b1c", "background": "#172029", "bold": true, "underline": false}}
```

Console style validation accepts the Python `Style` fields: RGB foreground/background, bold, dim, italic, underline, blink, reverse and strike. Rendering of dim, blink and reverse depends on the output display. Plugin styles use `plugin_id.style_name`. Use `term.get_style(name)` to inspect a style. `RGB` supports `from_hex`, `hex`, `lighten`, `darken` and `blend`; `Theme` and `term.register_theme` support custom theme objects.

### Progress and live output

```python
import time
from ultimate_terminal import terminal as term

for done in range(11):
    term.progress(done, total=10, width=30, label="Processing", newline=False)
    time.sleep(0.05)
print()  # Finish the live line before the next message.
term.success("Processed 10 items")
```

`progress_bar(value, total=100, width=35, label="", style="primary", show_percent=True)` returns formatted text. `progress` prints it, with `newline=False` rewriting the current line. `live(text)` rewrites a line and flushes immediately; `clear_line()` erases it.

`spinner(message, frames="dots", duration=2.0, interval=0.08, style="primary")` is a **blocking decorative animation**. It does not wrap a task. `animate_progress(total=100, width=35, label="Progress", duration=2.0, style="primary")` also blocks for its animation. Use these in runner scripts, not app/plugin UI callbacks. Additional helpers include `live_spinner`, `typewrite`, `pulse`, `marquee`, `countdown`, `dots`, `scanner` and `rainbow_animation`; their exact options are defined in [ultimate_terminal.py](ultimate_terminal.py). `hidden_cursor()` and `style(...)` are context managers; `hide_cursor`, `show_cursor` and `clear` emit terminal controls, some of which the app Console may ignore.

### Console behavior

Select a run for isolated output, or the grouped view to observe concurrent jobs. Each run has independent ANSI/cursor state. **Freeze View** stops redraw while collection continues; autoscroll can be controlled separately. Export produces readable text, while persisted logs retain raw ANSI for replay.

The Console supports standard, bright, 256-color and RGB SGR colors, carriage returns, line erasure and basic cursor controls. It is an output viewer with no stdin input, not an interactive shell. `input()`, password prompts and interactive command-line applications are unsuitable; use arguments, environment variables or shared data instead. Output limits: runner logs retain the latest 2 MB per run; each displayed stream retains up to 10,000 blocks/1,000,000 characters, with up to 64 displayed streams.

## Share data between tools

```python
from shared_loadout import get, set_value, update, all_values

set_value("my_tool.result", {"ok": True, "files": 12})
count = update("my_tool.completed", lambda old: old + 1, default=0)
print(get("my_tool.result", {}))
print(count)
```

Values must be JSON serializable. `get(key, default=None)` reads, `set_value(key, value)` replaces and returns the value, `update(key, function, default=None)` atomically transforms a value, and `all_values()` returns the shared dictionary. Use `update` for counters shared by concurrent workers. Its callback holds a SQLite write transaction: keep it fast and do not call another shared-data write inside it. There is no `set()` alias; use `set_value`.

The Loadouts shared-data editor uses the same store. Data survives restarts, but is local to this workspace. Suggested key naming is `your_tool.key` to avoid collisions.

## Call enabled plugin commands

```python
from workspace_plugins import available, call
from shared_loadout import all_values

if "output_tools" in available():
    result = call("output_tools", "summarize", all_values())
    print(result)
```

`available()` returns plugin IDs enabled when this run started, not command names. `call(plugin_id, command, *args, **kwargs)` imports that plugin in the child process and invokes its exported callable. UI registration is not called in the child. Commands should avoid Qt UI dependencies. Each child caches imported plugin modules; start a new run after editing plugin code. Disabling a plugin changes future runs, not already launched processes.

## Runner environment reference

| Variable | Purpose |
| --- | --- |
| `ORCHESTRATOR_SHARED_DB` | Workspace SQLite path used by shared SDK |
| `ORCHESTRATOR_RUN_ID` | Unique run ID |
| `ORCHESTRATOR_PROJECT_ID` | Stable project ID |
| `ORCHESTRATOR_OPERATOR` | Execution callsign |
| `ORCHESTRATOR_PLUGIN_ROOT` | Plugin directory |
| `ORCHESTRATOR_ENABLED_PLUGINS` | JSON list of enabled plugin IDs |
| `ULTIMATE_TERMINAL_THEME` | Initial output theme |
| `ULTIMATE_TERMINAL_STYLES` | JSON custom/plugin styles |
| `PYTHONUNBUFFERED`, `PYTHONIOENCODING` | Immediate output and UTF-8 |
| `FORCE_COLOR`, `COLORTERM` | Color-enabled output |
| `PYTHONPATH` | SDK directory prepended to configured import path |

The runner sets these after applying loadout environment values. Shared-state/plugin APIs depend on this context; launch scripts through the app to use them.

## Optional Ollama drafts

Enable assistance in Settings, enter the server URL, refresh downloaded models, choose a model and save settings. No models are downloaded automatically. In Workshop, describe the tool and click **Generate Draft**. Review the result, then **Use Draft in Editor**, save and explicitly run it. Applying a draft replaces editor content. Python fences, stray language markers and surrounding prose are cleaned; invalid Python is rejected. Assistance is optional and never executes generated code automatically.

## Troubleshooting and portability

| Symptom | Check |
| --- | --- |
| Code runs an older version | Save before running; inspect project path |
| `ModuleNotFoundError` | Install into the selected loadout interpreter; configure companion-module path |
| File not found | Check working directory and relative resource paths |
| Arguments rejected | Use a JSON list such as `["--flag", "value"]` |
| Shared SDK says run from workspace | Launch through the app so environment variables are supplied |
| Unknown plugin command | Enable plugin, verify `SCRIPT_COMMANDS`, then start a new run |
| Output appears late | Flush external tools; runner Python is already unbuffered |
| Process waits forever | Remove interactive input; configure a timeout |
| Progress overwrites messages | Finish the live line with `print()` |
| Template syntax passes but runtime fails | Review imports, filenames and application-specific placeholders |

Project bundles carry entry scripts and workspace configuration, not dependencies, companion resources or plugins. Copy those separately and update interpreter paths on the destination computer. Back up `orchestration_data`, your plugins and required external resources with the app stopped. For verification, run `python -m unittest discover -s . -p "test_*.py" -v` from the repository root.


## Pylerium branding and atmosphere

The application and new GUI SDK are branded **Pylerium**. New applications import `pylerium_gui`; saved `systematic_gui` imports and `SystematicWindow` remain compatible. The existing source directory and databases remain in place. `PYLERIUM_HOME` is the preferred workspace override; `SYSTEMATIC_HOME` is also accepted.

The bottom marquee reads `assets/tags.txt` dynamically: one tag per nonblank line, with duplicate lines removed and `#` comments ignored. It checks edits every two seconds. Live workspace notices appear immediately and remain in the recent-event tooltip and scrolling queue. Terminal themes and custom style definitions supply colours, backgrounds, bold, italic, underline, dim, reverse, strike and blink effects. Missing tags fall back to workspace events. Settings → Marquee controls scrolling, speed, hover pause and style cycling.

Assets → **Assign header logo** imports a managed image before the Pylerium heading, fitted to the heading height without distortion. **Remove header logo** removes its assignment; Settings → Storage can remove the imported image itself. The logo assignment and background opacity persist in the manifest.

Settings now includes Runtime, Display, Ambient, Marquee, Editors, Models, Console, Assistance, Storage and Builds categories. Atmospheric options include Sweep/Breathe/Orbit, speed, intensity, glow colour, frame limit, grid, particles and scanlines. Background animation suspends while hidden or minimized. Editor completion/wrapping defaults, model quality/grid/orbit defaults, console follow/refresh and build-inclusion defaults persist in the workspace database. Save Settings applies them to existing widgets and defaults for newly created editors/model canvases.


**Run Project** executes the selected Python entry point with its saved loadout. It never invokes executable packaging. Use **Build EXE** explicitly; old C4/PyInstaller output hooks are disabled automatically.

### Executable branding and advanced options

Workshop's **Build EXE** dialog includes an icon picker and collapsible branding/packaging controls. ICO, PNG, JPEG, WebP and BMP icons become a transparent multi-resolution Windows icon (16–256 pixels). The icon is embedded in the executable and applied to GUI windows using the shared toolkit.

Choose a single executable or application folder, GUI/console mode, Windows version/company/product/description/copyright, debug mode, optimization, cache cleaning, compression and administrator launch behavior. Advanced JSON exposes extra data/binaries, import paths, exclusions, package collections, hooks, runtime hooks, splash screen, Windows manifest, version resource file and temporary extraction directory. `extra_args` is a list of individual arguments for any other PyInstaller options; no shell command is constructed. Build options persist per project. Some advanced options require additional tools or resources supported by the selected PyInstaller installation.

Running `build_exe.py` directly opens the icon picker before building Pylerium. Cancel selects the default icon. Use `--icon path/to/icon.png` to supply one explicitly, or `--no-icon-picker` for unattended builds. `--onedir` selects folder packaging, and `--options-file build-options.json` supplies the same advanced options outside Workshop. Workshop always passes `--no-icon-picker` because it already provides its own picker. For folder builds distribute the entire output folder, including `_internal`, alongside the executable.


## Killchain global command bar

<img width="864" height="618" alt="image" src="https://github.com/user-attachments/assets/1e2f2d10-6511-4b52-add9-84d96024244e" />

While Pylerium is running, Ctrl+Space opens the floating command bar over Windows, including when the main window is minimized. The header button also opens it. If another application owns Ctrl+Space, the overlay reports the conflict; the header button remains available. Closing Pylerium releases the hotkey and stops clipboard capture.

- Type any search to query the existing Jumpback archive across titles, targets, app names, details and notes. Jumpback must be enabled to collect new activity; the command bar can search previously collected activity independently.
- `run <project name / ID / script name>` filters saved Workshop projects. Select a result and press Enter to launch with the default execution profile, using existing process limits and logs. Saved files are executed.
- `set <key> <value>` updates the persistent shared values used by Workshop scripts through shared_loadout. JSON values are accepted; other input is stored as text.
- `clip <text>` searches the INTEL // CLIPBOARD queue. Enter copies a selected text or image back to the clipboard. Capture can be paused; Forget selected and Clear queue remove saved entries. Capture starts with future clipboard changes, and keeps the latest 200 unique entries locally at killchain/clipboard.sqlite3. Images above 16 megapixels or 16 MB and text above one million characters are skipped.
- `go <page>` opens any main or plugin page. Arrow keys select results; Escape dismisses the overlay. History targets open HTTP(S) URLs or existing files; notes without a target are copied.

Clipboard capture is enabled by default and its pause state persists. The queue may contain copied sensitive text; use the capture toggle or clear controls when needed. No clipboard history from before Pylerium was running is imported.


## Tactile audio and animated status

<img width="1901" height="816" alt="image" src="https://github.com/user-attachments/assets/378575f2-51e2-45da-9ad6-ae438683375f" />

Settings → Audio controls opt-in playback, master volume, individual hover/click/deploy/success/error cues and local WAV/MP3 overrides. Defaults are in assets/audio. Hover cues are throttled; players are reused. No multimedia player is created while disabled. Process cues cover Workshop, schedules, plugin launchers and Killchain through the shared runner. Analysis tools and AppWindow background tasks also report completion.

Custom GUIs import `configure_audio` and `play_cue` from pylerium_gui. After create_application(), call `configure_audio(enabled=True, volume=18)` only when your user opts in. Call `play_cue('deploy')`, `play_cue('success')` or `play_cue('error')` for your own operations. Shared buttons and navigation get feedback automatically; an ordinary Qt button can request hover cues with `setProperty('audio_hover', True)`. Plugins use `ctx.audio` or `ctx.play_cue('success')` and honor the host mute settings. WAV files use Qt's cached low-latency sound effects; compressed audio uses its media player.

New editable tool starters include JSON, CSV, regex, diff, checksums, duplicate discovery, file catalogs, read-only SQLite, logs, Python inspection, encoding and reports. Additional projects demonstrate audio controls, background checksums, persistent notes and a terminal marquee. Plugin starters provide those tool pages, an audio studio, notes, a completion journal, model inspection, an editor scratchpad and event marquee. These compose shared components rather than embedding the main workspace.

Settings → Marquee adds Static, Gradient, Rainbow, Pulse and Scanner effects plus a 10–60 FPS limit. Text layout is cached and hidden widgets stop animating. Terminal theme colours, custom styles and semantic success/error/warning colours remain supported.

Workshop-launched GUIs inherit the host audio options. Independent applications retain their own explicit audio choices via QSettings. Templates leave opt-in under user control. The supplied hover_button.mp3 has a predecoded hover_button.wav companion, preferred for repeated low-latency playback. MP3 remains supported as a fallback or explicit override; compressed cues skip overlapping playback rather than restarting an active decoder.

## Creative experience and element starters

The **GUI / Creative** gallery includes constellation, particle, wave, orbital, cellular-life, mandala, digital-rain and terrain experiments, plus a focus garden, branching story studio, idea board and palette laboratory. Simulations have motion controls; visual experiments support PNG export. These use the shared `creative_gallery` components.

The **GUI / Element** gallery adds searchable lists, context actions, drag-and-drop lists, validated forms, property tables, expandable inspectors, cancellable progress, tabs, clipboard swatches, split previews, sortable records and command palettes.

Additional boilerplates demonstrate an event bus, undo/redo history, deterministic world generation, a plugin registry, state machines and atomic document saves. Templates remain editable Python and do not execute when inserted.
