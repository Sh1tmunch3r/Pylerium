# Starter tools and advanced Workshop projects

Open **Plugins**, search for **Starter Tools** (or a tool name), select one and enable it. New tools are opt-in. Enable **Getting Started** for a saved checklist linking Workshop, loadouts, operators, dependency maps, missions, assets, plugins and run history. Its project selector creates a complete editable advanced application.

## Included plugins

| Plugin | Capabilities |
| --- | --- |
| Getting Started | Persistent checklist, page shortcuts and advanced project creation |
| JSON Lab | Validation, formatting, JSON Pointer leaf paths |
| CSV Profiler | Missing/distinct counts, numeric summaries, record preview |
| Regex Lab | Match ranges, numbered/named capture groups |
| Text Diff | Unified differences between versions |
| File Integrity | Streaming SHA-256, expected checksum comparison |
| Duplicate Finder | Size prefilter, content hashes, duplicate groups and potential space savings; no deletion |
| File Catalog | Folder inventory, filename search, sizes and extensions |
| SQLite Explorer | Read-only schemas and SQL queries, capped at 500 displayed rows |
| Log Analyzer | Severity counts, repeated lines, text search |
| Python Inspector | Syntax validation, imports, functions, classes and branch counts; does not execute input |
| Codec Lab | Base64, URL encoding/decoding and text checksums |
| Report Builder | JSON records to Markdown tables |
| Run Observatory | Latest 200 persisted runs, status counts, active job count and selected run output |
| Workspace Inspector | Projects, profiles, operators, maps, schedules, shared state and plugin metadata; environment values redacted |

Analysis pages have editable sample inputs, input pickers, output viewers, cancel, copy, export and **Publish shared result**. Results publish under `toolkit.<tool_id>` only when requested. Reports remain available for export until the page is closed; publishing makes them persistent.

Analysis uses a separate Python process with a 30-second deadline, avoiding GUI freezes from CPU-heavy work. Directory scans skip symlinks, `.git`, `__pycache__` and `node_modules` and stop at 20,000 files. Input/result limits keep previews bounded; the output editor displays the first 250,000 characters, while copy/export retain the complete result. SQLite uses read-only/query-only mode and a query instruction budget. These are authoring tools and bounded previews, not full IDE static analysis or database administration.

Each analysis plugin exports `analyze(text, option='')` for Workshop scripts and supplies a runnable script template:

```python
from workspace_plugins import call
from shared_loadout import set_value
from ultimate_terminal import terminal as term

report = call('starter_json_lab', 'analyze', '{"ready": true}', '')
set_value('my_report', report)
term.print(report)
```

The plugin must be enabled before deploying the script. Direct `from toolkit_core import execute` works without enabling a plugin. Script calls run within the script's own interpreter and use its execution timeout.

## Six advanced applications

Choose **Workshop → New → GUI / Advanced / …** or **Insert boilerplate**. Complete copies also live in `examples/advanced_workshop/`.

| Application | Tool pages |
| --- | --- |
| Data engineering lab | JSON, CSV, SQLite, Markdown reports |
| Source review workstation | Python inspection, diffs, regex, logs |
| Digital asset audit | Catalog, integrity, duplicates |
| Incident investigation desk | Logs, regex, diffs, SQLite |
| Report publishing studio | JSON, CSV, reports, codecs |
| Developer utilities cockpit | Python, JSON, codecs, integrity |

Every application composes selected shared widgets and the main application stylesheet in an independent AppWindow with isolated tool processes, cancellation, a Python recipe editor, ANSI terminal, model studio, pipeline map and shared results. Successful analyses automatically publish results to the launching Workshop's shared database. The displayed pipeline is a reporting visualization; use the main **Maps** page to configure executable dependency graphs. Save recipes and create Workshop projects to run them with loadouts/operators/missions and retain run history. Use **GUI / Blank custom application** and **GUI element / …** insertion snippets to design your own layout without loading the operations window.

New GUIs created through **New** are interactive projects and stay open until closed. Boilerplate inserted into an existing project retains that project's execution settings. Launch standalone examples from Workshop to enable shared-state integration; standalone Python launches show a helpful shared-state placeholder.

## Model studio

Assign **OBJ, GLB, glTF, STL, PLY or OFF** from Assets. GLB/glTF support node transforms, mesh instances, UVs and base-color textures. PLY face/vertex colours are represented as material groups; palettes above 512 colours are reduced to 64 for preview performance. Non-OBJ imports become self-contained GLB files; keep glTF buffers and images alongside the source until import completes. OBJ retains referenced MTL and image dependencies. Models are limited to 96 MB source, 256 MB external dependencies, 500,000 vertices and 300,000 triangles.

- Left drag: orbit; right/middle drag: pan.
- Wheel: zoom from 0.2× to 4×; double-click or **F**: fit/reset.
- **Space**: pause/resume.
- Right-click: inspection studio, camera presets, Fast/Native/Studio quality, floor grid and PNG export.

Rendering uses a dedicated offscreen GPU worker with at most one in-flight frame, native device resolution, 4× MSAA, mipmaps and anisotropic filtering. Buffers/material textures are reused; paused views reuse their cached frame. Normal/bump and metallic/roughness maps contribute to studio lighting when supplied. A software fallback remains available. **Inspect weapon** opens the large interactive studio with a 360° turntable, camera controls, material list and texture viewing. Skeletal animation is not evaluated. FBX, Blender `.blend`, CAD and compressed Draco meshes are not included; export these to an uncompressed supported format. Correct UVs and matching textures are still required.

Source dependencies: `python -m pip install PyQt6 numpy trimesh pillow moderngl`. The portable executable bundles these dependencies for both the host and Workshop interpreter. See [Model preview details](WORKSHOP.md#texture-previews).
