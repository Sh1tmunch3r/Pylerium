# Pylerium
Disclaimer: Pylerium is an original open-source developer workbench bringing the aesthetic of Call of Duty UI. It contains no proprietary game assets, extracted code, or trademarked material from Activision, Treyarch, or the Call of Duty franchise.
A local Python workspace for projects, plugins, reusable GUI components, model inspection, process orchestration and searchable activity history.

## Run from source (Windows)

Python 3.10 or newer is required; Python 3.13 is recommended for the Windows executable builder.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe orchestration-menu.py
```

The application creates a local orchestration_data workspace on first use. Personal databases, execution history, generated executables and caches are excluded from Git. Existing projects and plugins in your original Systematic folder have not been moved or deleted. A clean checkout starts its own workspace. Set PYLERIUM_HOME explicitly when you want to use an existing workspace.

## Build a Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build_exe.py
```

The icon picker appears when running the builder directly. Workshop also provides a configurable executable builder. Build output stays local in dist/ and build/.

## Guides

[Operations](OPERATIONS.md) · [Workshop](WORKSHOP.md) · [Plugins](PLUGINS.md) · [Executable builds](BUILD.md)

## Checks

```powershell
python -m unittest discover -s . -p "test_*.py"
```

## Repository preparation

This folder is prepared for https://github.com/Sh1tmunch3r/Pylerium. No commit or push was performed. Origin's push URL and a local pre-push hook intentionally block uploads. Review the files before committing. When you explicitly decide to enable uploads, remove .git/hooks/pre-push and run:

```powershell
git config --unset-all remote.origin.pushurl
```

The accidental parent repository metadata is preserved beside this folder under .git-paused-*; it is no longer active. Any conflicting destination files were backed up beside this folder under .pylerium-copy-backup-* before replacement.
