# <img width="1024" height="559" alt="Q-Photoroom" src="https://github.com/user-attachments/assets/dde7de2b-7b92-4692-b403-dc0fea41e9da" /> <img width="356" height="87" alt="image" src="https://github.com/user-attachments/assets/c1e0f360-5276-4965-b19d-7bec10166688" />




Disclaimer: Pylerium is an original open-source developer workbench bringing the aesthetic of Call of Duty UI. It contains no proprietary game assets, extracted code, or trademarked material from Activision, Treyarch, or the Call of Duty franchise.
A local Python workspace for projects, plugins, reusable GUI components, model inspection, process orchestration and searchable activity history.
<img width="1049" height="1800" alt="image" src="https://github.com/user-attachments/assets/f6b7e46b-3fcd-49fa-a7c0-ef0f710ce637" />

## Run from source (Windows)

Python 3.10 or newer is required; Python 3.13 is recommended for the Windows executable builder.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe orchestration-menu.py
```

The application creates a local `orchestration_data/` workspace on first use. Personal databases, project execution history, virtual environments, caches and generated executables are excluded from Git. Set `PYLERIUM_HOME` to select another workspace.

## Project execution loadouts

Click a project in **Arsenal** to configure its execution loadout. Primary opens the entry point and named argument attachments; use **Open Editor** to edit code and **Run Project** to execute it. Configure companion scripts, environment files, diagnostics, output reports, policies and pipeline overrides per project.

**Run Project does not build an executable.** Packaging is an explicit action in **Workshop → Build EXE**. Legacy C4/PyInstaller output hooks are disabled automatically.

Right-click an Arsenal project for loadout, editor, run, rename, duplicate, folder and asset actions. Assign an image or static 3D model to each execution card. The Assets studio provides model inspection, material overrides, rotation controls and removable assignments.

## Build something creative

Workshop and Plugin Builder include 12 creative experiences, 12 reusable UI elements and 6 additional boilerplates. Explore constellation networks, particles, waves, an orbital observatory, cellular life, mandalas, digital rain, terrain, a focus garden, branching stories, an idea board and color palettes. Templates are editable starting points; creating or inserting one does not enable a plugin automatically.

## Build a Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build_exe.py
```

The icon picker appears when running the builder directly. Workshop also provides a configurable executable builder. Build output stays local in dist/ and build/.

## Guides & Previews

[Operations](OPERATIONS.md) · [Workshop](WORKSHOP.md) · [Plugins](PLUGINS.md) · [Executable builds](BUILD.md) · [Starter gallery](STARTER_TOOLS.md)

## Checks

```powershell
python -m unittest discover -s . -p "test_*.py"
```
