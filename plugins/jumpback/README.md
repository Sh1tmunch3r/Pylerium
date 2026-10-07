# Jumpback / Activity Archive

Enable **Jumpback / Activity Archive** in Systematic's **Plugins** page, then open the **JUMPBACK** tab. Capture starts when the plugin is enabled, unless you previously paused it. It continues when you switch to another Systematic page or minimize Systematic. Closing Systematic or disabling the plugin stops capture. There is no hidden service or startup task.

## What it keeps

- **Browser visits:** all visits still present in the detected browser history, including repeated visits to the same address. Opera, Opera GX, Opera Beta, Chrome, Edge, Brave, Vivaldi and Firefox profiles are detected. YouTube visits get their own filter. Titles and URLs are archived; watch completion and playback state are not available from browser history.
- **Desktop sessions:** the foreground app's executable name, window title, timestamp and approximate active duration, sampled every two seconds. Unchanged windows are grouped into sessions. Idle periods after 60 seconds, Systematic's own windows, detected private-window titles, pauses and long gaps are excluded from session time.
- **Windows recent items:** available recent files, folders, code, media and game/application shortcuts. This reflects the Windows Recent cache, not every filesystem operation.
- **Saved moments and Systematic operations:** jot down what you are doing and keep completion records for operations run while the plugin is enabled.

Existing browser history is imported in background batches; later imports pick up new visits every 30 seconds. Locked profiles, including running Opera/GX, use disposable verified copies of the database and its transaction sidecars. Source files are left untouched. Copies that change during capture or fail integrity checks are rejected and retried. Other unreadable sources report an error. A long first Windows shortcut scan does not block the UI. Sources & exclusions shows the latest status and accepts custom `History` / `places.sqlite` paths for portable or unusual profiles.

## Finding things again

Search title, URL, app name, path, source details and your notes across the whole archive. Multiple search words must all match. Results are paged in groups of 100; this does not limit stored or searchable history. Filter by event type, source, time period or bookmarks. Select a row for details, copy its target, reopen a page or file, bookmark it and attach a note. Notes save explicitly and when you move to another row or unload the plugin.

The four counters show archived events, today's events, web/YouTube visits and approximate active app time today. Overlapping browser visits and app sessions are different records; browser visit count is not time spent watching or reading.

**Export results** writes every matching event to JSON or CSV, including notes and bookmarks. JSON keeps original text; CSV prefixes potential spreadsheet formulas to make opening the export safer. Exports use a consistent archive snapshot while capture continues, and replace the destination only after successful completion.

## Persistence and capture controls

Data lives in `orchestration_data/jumpback/history.sqlite3` in the active workspace, separate from plugin source files. Editing, overwriting or reloading the plugin does not replace the archive. There is no automatic expiry or retention limit. Disabling does not delete records. Back up the workspace while Systematic is closed; if copying it while running, SQLite's `-wal` and `-shm` files are part of the live archive.

**Pause capture** stops new imports and foreground sampling while leaving search available; resume continues appending. Visit and recent-item timestamps inside a saved pause interval are skipped on later imports. The setting survives restart and is also available from the plugin's action button. A batch already committing when pause is clicked may finish. Add case-insensitive app names, domains, window-title or path fragments in **Sources & exclusions** to exclude future events. Existing records are not removed by exclusions. A first import cannot resurrect history the browser or Windows has already deleted. Private browsing generally has no persisted visits; detecting private mode from window titles is best effort.

Capture stays local and does not collect keystrokes, clipboard contents, screenshots, credentials, cookies, page bodies or individual in-page interactions. URLs and window titles can contain personal information. Browser visits may be imported later even if you visited them while Systematic was closed; desktop sessions cannot be reconstructed for that time. Keep Systematic running with capture enabled for the continuous desktop trail.

## Implementation references

Browser visits are read using read-only SQLite connections and the [Chromium visits schema](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/history/core/browser/visit_database.cc). Windows foreground sampling uses [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow), [GetLastInputInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo) and [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew). No additional Python packages are needed beyond Systematic's existing PyQt6 dependency.
