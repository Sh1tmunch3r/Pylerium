# Plugin builder and API guide

Plugins extend the desktop app with pages, actions, project templates, terminal styles, execution hooks and commands callable from Workshop scripts. See [WORKSHOP.md](WORKSHOP.md) for editing, running scripts and full terminal usage; [OPERATIONS.md](OPERATIONS.md) covers the surrounding workspace.

The included collection adds **15 opt-in starter plugins** with real analysis pages, script commands and advanced Workshop projects. Search Plugins by name, ID or description. Start with **Getting Started**. See [the collection guide](STARTER_TOOLS.md) for tool capabilities, limits and complete examples.

## Build a plugin in the app

1. Open **Plugins** and select a template in the builder dropdown.
2. Click **New from Template**. Give the extension a display name and description. An empty ID is generated from the display name when validated/saved.
3. Edit `plugin.py`; use **Add File** for companion `.py` modules and the file dropdown to switch between them.
4. Use **Focus editor** for a large themed card. Its template dropdown and **New from template** action remain available. Save/Ctrl+S saves the plugin; returning preserves editor state.
5. Click **Validate**, then **Save Plugin**. A new plugin remains disabled.
6. Click **Save & Enable / Reload** to execute registration and add its features to the workspace.
7. Test its actions, pages and Workshop commands. Use **Disable** to remove contributions without deleting its saved files.

To edit an existing extension, select it and use **Edit Selected**, or double-click its entry. Unsaved changes prompt for Save, Discard or Cancel before replacing the current plugin. Existing IDs are fixed. If a new plugin ID already exists, saving offers to update the existing files, create a numbered copy, or cancel. Opening the existing plugin is also available for editing.

### Builder templates

| Template | Includes |
| --- | --- |
| Custom extension | Basic action and exported echo command |
| Custom UI page | QWidget page registered into navigation |
| Project launcher | Dynamic project/loadout selectors and launch button |
| Shared data tool | Workspace shared-data inspection and child command |
| Execution hook | Run-completion notification |
| Output style and template | Named output style and Workshop starter |
| Script commands | Callable transformation exported to scripts |

These are editable starting points. The API is a general Python extension mechanism; arbitrary functionality comes from your code, imports and UI design. The builder does not install dependencies or generate a complete extension automatically.

## Files and manifest

Plugins are discovered from immediate subfolders of `plugins/`:

```text
plugins/my_tools/
    plugin.json
    plugin.py
    helpers.py
```

```json
{
  "id": "my_tools",
  "name": "My Tools",
  "description": "Reports and reusable commands",
  "api_version": 1,
  "entry": "plugin.py"
}
```

IDs must use letters, digits, underscores or hyphens and be unique. API version must be `1`. The entry path must resolve to an existing file inside the plugin folder; it defaults to `plugin.py` when omitted. Use **Rescan** after creating/editing manifests outside the app. Discovery reads metadata without importing plugin code.

The builder edits Python files; manage images, datasets, dependency specifications and other resource files externally. **Add File** accepts a unique simple Python filename such as `helpers.py`. Companion imports use package-relative syntax:

```python
from .helpers import summarize
```

For plugin-owned resource paths, derive them from `Path(__file__).parent`, not the app's current working directory.

## Lifecycle and validation

The entry module must define a top-level synchronous `register(ctx)` function. Optional `unregister(ctx)` releases resources when disabling/reloading.

| Operation | Behavior |
| --- | --- |
| Rescan/discovery | Reads manifests; does not execute plugin modules |
| Validate | Parses all builder Python files and checks for `register`; does not import or run them |
| Save Plugin | Writes manifest/modules; leaves current activation unchanged |
| Enable | Imports the module and calls `register(ctx)` in the app process |
| Save & Enable / Reload | Saves, disables the old instance, then registers the new version |
| Disable | Calls optional `unregister`, then removes host-managed contributions |
| Next app launch | Reloads previously enabled plugins |

Syntax validation cannot prove imports, callback signatures or runtime behavior. If registration fails, the host removes its partially registered contributions and leaves the plugin disabled. A failed reload does not restore the previous instance. Saving code alone does not update the already loaded UI module.

The host removes pages, actions, templates, styles and hooks registered through `ctx`. Your cleanup must stop your timers/workers and disconnect extra signals you connected directly. Plugins run in the application process with normal account permissions. Keep registration, UI callbacks and hooks short; use background work for slow tasks and Qt signals to deliver results to widgets on the UI thread.

## Context API reference

`ctx.api_version` is `1`; `ctx.descriptor` contains discovered manifest metadata including folder/entry paths. `ctx.window`, `ctx.store` and `ctx.runner` expose the app, persistence and runner. These are low-level implementation objects; use the small registration API where possible and inspect the source before relying on other methods.

| API | Contract |
| --- | --- |
| `ctx.log(text)` | Appends text plus a newline to the plugin's Console stream |
| `ctx.add_page(name, widget)` | Adds a QWidget and navigation button; page title includes plugin ID |
| `ctx.add_action(name, callback)` | Adds a plugin action; callback is invoked without arguments |
| `ctx.add_template(name, code)` | Adds a string-valued project template named `plugin_id // name` |
| `ctx.add_style(name, **style)` | Adds a validated terminal style named `plugin_id.name` |
| `ctx.on(event, callback)` | Subscribes to `output` or `run_finished` |
| `ctx.selector(kind)` | Returns a live QComboBox for a saved entity kind |

Hook signatures:

```python
def register(ctx):
    ctx.on("output", lambda run_id, raw_text: None)
    ctx.on("run_finished", lambda run_id, status: ctx.log(f"{run_id}: {status}"))
```

Output is raw text and can include ANSI or partial lines. `run_finished` supplies the stored status string; it does not supply the exit code as a third argument. Callbacks run on the Qt UI thread. Host action/hook exceptions are caught and written to the `plugin-errors` Console stream. Avoid logging every output chunk back into output hooks; the host suppresses recursive emissions of the same event, but excessive output still adds noise.

### Dynamic entity selectors

Supported kinds are `project`, `profile`, `operator` and `workflow`. A profile is an execution loadout and a workflow is a map. `currentText()` is a display name; `currentData()` is the stable ID used for assignment. Selectors refresh when workspace entities change, preserving valid selection where possible. Check for an empty selection before launching.

```python
def register(ctx):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

    page = QWidget()
    layout = QVBoxLayout(page)
    project = ctx.selector("project")
    profile = ctx.selector("profile")
    launch = QPushButton("Run selected project")

    def run_selected():
        if not project.currentData() or not profile.currentData():
            ctx.log("Create/select a project and execution loadout first")
            return
        ctx.window.safe(lambda: ctx.window.launch(project.currentData(), profile.currentData()))

    launch.clicked.connect(run_selected)
    layout.addWidget(project)
    layout.addWidget(profile)
    layout.addWidget(launch)
    ctx.add_page("Launcher", page)
```

Pages inherit the app's styling unless overridden. Create widgets inside `register`, not at module import. A plugin's command module may also be imported in a runner process where there is no QApplication.

## Complete example: reporting extension

Create a plugin with ID `my_tools` and the following files. It provides an action, a Workshop template, an output style and a reusable script command.

`helpers.py`:

```python
def summarize(values):
    return {"count": len(values), "keys": sorted(str(key) for key in values)}
```

`plugin.py`:

```python
from .helpers import summarize

SCRIPT_COMMANDS = {"summarize": summarize}

def register(ctx):
    ctx.add_action("Inspect shared keys", lambda: ctx.log(summarize(ctx.store.shared())))
    ctx.add_style("highlight", foreground="#ff7b1c", bold=True)
    ctx.add_template("Shared report", '''from ultimate_terminal import terminal as term
from shared_loadout import all_values
from workspace_plugins import call

report = call("my_tools", "summarize", all_values())
term.print("Shared state report", style="my_tools.highlight")
term.table([["Keys", report["count"]]], headers=["Metric", "Value"])
term.panel("\\n".join(report["keys"]) or "No shared values", title="Keys", width=60)
''')
    ctx.on("run_finished", lambda run_id, status: ctx.log(f"Finished {run_id}: {status}"))

def unregister(ctx):
    # Release resources you create beyond the host-managed contributions.
    pass
```

Save and enable the plugin. Click **Inspect shared keys** and check Console. In Workshop, choose `my_tools // Shared report` as a new-project template, or insert it using the editor toolbar. Save and run the project. You should see the plugin's orange heading, a table and a panel of shared keys, followed by a completion message in the plugin stream. No model or AI service is required.

## Commands called by Workshop scripts

Export a module-level dictionary of callable values:

```python
def transform(value, *, prefix=""):
    return prefix + str(value).upper()

SCRIPT_COMMANDS = {"transform": transform}
```

Call it from a saved runner script:

```python
from workspace_plugins import available, call

print(available())
result = call("my_tools", "transform", "ready", prefix="Status: ")
print(result)
```

This second example requires adding `transform` to the example plugin's `SCRIPT_COMMANDS`. Commands execute **inside the calling runner process**. They are regular Python functions: arguments and results do not cross a remote transport, and exceptions propagate to the caller. They do not receive `ctx` automatically. UI `register` is not called in that process, so commands cannot depend on globals initialized only during registration.

A run receives a snapshot of enabled IDs, but loads command source on first call rather than receiving a frozen code bundle. Each runner process caches modules afterward. Start a fresh run after updating a plugin. Disabling a plugin affects future run snapshots; it does not revoke commands in an existing run.

## Terminal output from plugins

For app actions/hooks, use `ctx.log`. It routes output to the Console; ordinary `print` in UI callbacks goes to the app's launching terminal and is not automatically routed. To log colored text, format a string and pass it to the context:

```python
def register(ctx):
    from ultimate_terminal import Terminal
    output = Terminal(enabled=True, theme="fire", force_truecolor=True)
    ctx.add_action("Ready message", lambda: ctx.log(output.paint("Plugin ready", "success")))
```

For commands invoked by Workshop scripts, normal `print` and `term` output are captured by the runner:

```python
def report(message):
    from ultimate_terminal import terminal as term
    term.info(message)
    return {"reported": True}

SCRIPT_COMMANDS = {"report": report}
```

`ctx.add_style("highlight", foreground="#ff7b1c", bold=True)` makes `my_tools.highlight` available to newly launched scripts while the plugin is enabled. It accepts the same validated style fields as Console Custom Styles: foreground/background hex colors, bold, dim, italic, underline, blink, reverse and strike. Visual support depends on the output display. Already printed text and already running script instances do not change when styles are edited or disabled.

Use tables/panels for final results and live progress for a single evolving task. Blocking terminal animations belong in runner scripts; calling them in the plugin UI thread freezes the interface. See [WORKSHOP.md](WORKSHOP.md#ultimate-terminal-quick-start) for examples and the full output behavior.

## Shared data and persistence

UI plugins can inspect `ctx.store.shared()`; low-level Store methods are defined in [runner_core.py](runner_core.py). Commands running under the runner can use `shared_loadout.get`, `set_value`, `update` and `all_values`. The runner supplies the database environment; the app UI context should use its Store rather than assuming runner-only environment variables are present.

Plugin enablement is saved in workspace settings. Plugin source stays in the plugins directory and is not included in project export bundles. To distribute an extension, copy the whole plugin folder, include its companion files/resources and document dependencies. Install UI dependencies into the app interpreter and command dependencies into every execution-loadout interpreter that uses them. Rescan and explicitly enable it on the destination workspace.

There is no manifest-driven dependency installer, remote plugin registry, permission isolation, plugin settings schema or unloadable process sandbox. Custom settings pages/configuration can be implemented as plugin-owned features.

## Troubleshooting and verification

| Symptom | Check |
| --- | --- |
| Plugin missing | Put `plugin.json` in an immediate plugin subfolder; Rescan |
| Invalid manifest | Check JSON, unique ID, API version and entry path |
| Validation fails | Inspect every companion module and the top-level `register(ctx)` definition |
| Validation passes, enable fails | Inspect runtime imports, dependencies and registration error |
| Saved edits do not affect UI | Use Save & Enable / Reload |
| Script says plugin is not enabled | Enable before launching a new run |
| Unknown command | Export it in `SCRIPT_COMMANDS`; command names are separate from action names |
| Widgets fail in runner | Move widget creation inside `register`; make command imports UI-independent |
| Dropdown has no entities | Save the relevant project/loadout/operator/map first |
| UI freezes | Move slow work out of UI callbacks/hooks |
| Duplicate timers or callbacks after reload | Stop/disconnect owned resources in `unregister` |
| `print` does not appear in Console | Use `ctx.log` for app callbacks; runner commands capture stdout |
| Style not found | Use the `plugin_id.style_name` key and start a new run |
| Companion code seems stale | Restart the app/run if necessary after external helper-module changes |

Test registration and disabling, dynamic selectors, action errors, hook errors, commands, shared-data behavior and cleanup. Validate syntax first; enable in a workspace where the plugin's actual behavior can be exercised. Run the existing automated suite from the repository root:

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

The API implementation is [plugin_system.py](plugin_system.py); child command loading is [workspace_plugins.py](workspace_plugins.py); the editor builder is [plugin_builder.py](plugin_builder.py).
