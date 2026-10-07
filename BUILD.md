# Windows executable

Run `dist/Pylerium.exe` by double-clicking it. It includes the desktop UI, default assets, bundled Output Tools example, terminal/shared-data SDK and a separate Python 3.13 interpreter for Workshop jobs. Python does not need to be installed to launch it or run standard-library/SDK tools.

## Persistent data

When the EXE remains in this repository's `dist` folder, it detects and uses the existing `orchestration_data` workspace, assets and plugins. If copied to a new location without a workspace, it creates `%LOCALAPPDATA%\Pylerium`. Assets and default plugins are copied there on first use. Saves never target the EXE's temporary extraction directory.

For a portable workspace, put an existing `orchestration_data/shared.sqlite3` beside the executable along with the matching `assets` and `plugins` folders. Or set `PYLERIUM_HOME` to a writable workspace root before launching. Back up/move data while the app is closed. Existing projects contain absolute script/working-directory paths; moving their files to another computer requires updating those paths or importing project bundles.

The default execution loadout points to the bundled interpreter on a fresh workspace. Other loadouts can select a separately installed Python environment for third-party dependencies. A packaged interpreter path is resolved again on each app launch/run because one-file extraction paths change. Third-party script dependencies beyond the bundled Qt/SDK are not automatically included; configure an appropriate external interpreter or module path. Do not install into the temporary extracted interpreter because those changes will disappear.

The single executable extracts its runtime before opening, so startup can take a few seconds. Startup exceptions are saved as `startup-error.log` in the selected workspace and displayed in a dialog. This build targets Windows x64.

## Saving existing names

Saving an existing project updates its file atomically. Distinct projects can share a display name because their storage folders use unique IDs. If a new plugin's ID already exists, the builder offers **Yes** to update matching files, **No** to create a numbered copy, or **Cancel** to retain the unsaved draft. Updating leaves unrelated companion files intact and requires a reload to update live contributions. Close external applications that hold files locked if Windows refuses a save; a failed atomic replacement preserves the original file.

## Rebuild

Use a Windows Python installation with PyQt6 and PyInstaller:

```powershell
python -m pip install PyQt6 pyinstaller
python build_exe.py
```

Build intermediates go to `build`; the deliverable is `dist/Pylerium.exe`. The script bundles a copy of the build interpreter's standard library/native runtime and creates an isolated runtime path. Runtime SDK imports are supplied through the runner environment. Existing user projects, run logs and custom plugin folders are not embedded in the EXE.

Resource and persistence paths follow [PyInstaller's runtime documentation](https://pyinstaller.org/en/stable/runtime-information.html): bundled resources live in the extraction directory, while user-authored files belong in the persistent workspace.

## Verification

```powershell
python -m unittest discover -s . -p "test_*.py" -v
$env:PYLERIUM_HOME = "$env:TEMP\PyleriumSmoke"
& dist/Pylerium.exe --smoke-test "$env:TEMP\systematic-smoke.json"
Remove-Item Env:PYLERIUM_HOME
```

Use a fresh smoke workspace, since this check creates two same-name test projects and updates a shared value. The JSON result reports startup, saving, an actual child Python run (terminal output/shared SQLite/SSL/asyncio), focus mode and fullscreen exit. A failed check reports its traceback. GUI applications can return control to PowerShell before finishing; wait for the JSON result or launch with `Start-Process -Wait`.

Further usage: [Workshop and terminal](WORKSHOP.md), [Plugins](PLUGINS.md), [Operations](OPERATIONS.md).
