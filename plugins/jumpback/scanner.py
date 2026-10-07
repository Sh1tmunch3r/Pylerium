# Companion module: import with from .scanner import ...
import os
import time
import subprocess
from pathlib import Path

# Common path keywords & process patterns that indicate a game asset or launcher
GAME_PATTERNS = {
    'steam', 'steamapps', 'epic games', 'xboxgames', 'riot games', 'gog galaxy',
    'ubisoft', 'battle.net', 'origin', 'call of duty', 'warzone', 'cyberpunk',
    'fortnite', 'minecraft', 'valorant', 'league of legends', 'gta', 'overwatch',
    'roblox', 'apex', 'csgo', 'cs2', 'unreal', 'unity', 'games', 'gamepass'
}

def resolve_shortcut(lnk_path):
    """
    Resolves the true target path of a .lnk or .url file using Windows COM
    or native PowerShell fallback. Returns (target_path, is_directory, is_url).
    """
    lnk_str = str(lnk_path)
    
    # Internet Shortcuts (.url) used by Steam, Epic, etc.
    if lnk_str.lower().endswith(".url"):
        try:
            with open(lnk_str, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith("URL="):
                        return line.strip().split("=", 1)[1], False, True
        except Exception:
            pass
        return lnk_str, False, False

    # Try win32com if pywin32 is installed
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_str)
        target = shortcut.TargetPath
        if target:
            return target, os.path.isdir(target), False
    except Exception:
        pass

    # Fast PowerShell COM fallback (native on all Windows installs)
    try:
        quoted_path = lnk_str.replace("'", "''")
        cmd = f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{quoted_path}'); Write-Output $s.TargetPath"
        res = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            timeout=1.0
        ).decode('utf-8', errors='ignore').strip()
        if res:
            return res, os.path.isdir(res), False
    except Exception:
        pass

    return lnk_str, False, False

def classify_item(name, target_path, ext, is_dir, is_url):
    """Classifies an item into BO6 telemetry categories."""
    target_lower = str(target_path).lower()
    name_lower = str(name).lower()

    # 1. Launcher Protocols & Steam/Epic Games
    if is_url or "steam://" in target_lower or "com.epicgames" in target_lower:
        return "GAME", "STEAM // LAUNCH" if "steam://" in target_lower else "GAME // LAUNCH"

    # 2. Game Executables & Game Directories
    if any(k in target_lower or k in name_lower for k in GAME_PATTERNS):
        if ext == '.exe' or is_url:
            return "GAME", "GAME // EXEC"
        elif is_dir:
            return "GAME", "GAME // DIR"

    # 3. Directories / Folders
    if is_dir or ext == '':
        return "DIR", "SYS // FOLDER"

    # 4. Standard Desktop Applications
    if ext == '.exe':
        return "APP", "APP // EXEC"

    # 5. Developer Source Code
    if ext in {'.py', '.cpp', '.h', '.cs', '.js', '.ts', '.html', '.css', '.rs', '.go', '.sh', '.ps1', '.pyw'}:
        return "SRC", f"SRC // {ext[1:].upper()}_FILE"

    # 6. Config, Data & Documents
    if ext in {'.json', '.csv', '.db', '.yaml', '.yml', '.xml', '.pdf', '.txt', '.md', '.docx', '.xlsx', '.sql'}:
        return "DOC", f"DOC // {ext[1:].upper()}_FILE"

    # 7. Media & 3D Assets
    if ext in {'.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mkv', '.wav', '.mp3', '.blend', '.fbx', '.obj', '.psd'}:
        return "MEDIA", f"MEDIA // {ext[1:].upper()}_FILE"

    return "GENERIC", f"ITEM // {ext[1:].upper() if ext else 'SYS'}"

def get_recent_items(limit=15, category_filter="ALL", cancel=None, min_mtime=0, on_batch=None):
    """
    Scans the Windows Recent cache and returns parsed telemetry items
    including Games, Apps, Folders, and Documents.
    """
    recent_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent"))
    if not recent_dir.exists():
        return []

    if limit <= 0:
        return []
    items = []
    pending = []
    shortcuts = []
    for shortcut in list(recent_dir.glob("*.lnk")) + list(recent_dir.glob("*.url")):
        if cancel is not None and cancel.is_set():
            return []
        try:
            shortcuts.append((shortcut.stat().st_mtime, shortcut))
        except OSError:
            continue
    shortcuts.sort(key=lambda entry: entry[0], reverse=True)
    # Process both .lnk and .url shortcuts
    for mtime, shortcut in shortcuts:
        if cancel is not None and cancel.is_set():
            return []
        if mtime < min_mtime:
            break
        raw_name = shortcut.stem
        
        # Exclude internal Windows system noise
        if raw_name.lower() in {'desktop.ini', 'automaticdestinations', 'customdestinations'}:
            continue

        try:
            target_path, is_dir, is_url = resolve_shortcut(shortcut)
            
            # Determine extension from target or original name
            ext = Path(target_path).suffix.lower() if not is_url else ''
            if not ext and not is_dir:
                ext = Path(raw_name).suffix.lower()

            cat, cat_label = classify_item(raw_name, target_path, ext, is_dir, is_url)

            # Apply category filter if active
            if category_filter != "ALL" and cat != category_filter:
                continue

            items.append({
                'shortcut_path': str(shortcut),
                'target_path': target_path,
                'name': raw_name,
                'category': cat,
                'category_label': cat_label,
                'mtime': mtime
            })
            if on_batch is not None:
                pending.append(items[-1])
                if len(pending) >= 20:
                    on_batch(pending)
                    pending = []
            if len(items) >= limit:
                break
        except OSError:
            continue

    # Sort strictly by modification timestamp descending
    if on_batch is not None and pending:
        on_batch(pending)
    items.sort(key=lambda x: x['mtime'], reverse=True)
    return items[:limit]

def format_time_ago(mtime):
    """Formats a timestamp into a monospaced telemetry string."""
    diff = time.time() - mtime
    if diff < 60:
        return f"{max(1, int(diff))}s AGO"
    elif diff < 3600:
        return f"{int(diff // 60)}m AGO"
    elif diff < 86400:
        return f"{int(diff // 3600)}h AGO"
    else:
        return f"{int(diff // 86400)}d AGO"
