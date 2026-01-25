import os
import shutil
import winreg
import ctypes.wintypes
import string
import datetime

# ================= CONFIGURATION =================
APP_NAME = "Witcher 3 Settings Merger (CLI)"
VERSION = "0.9.1 (Beta)"
LOG_FILE = "Merger_Log.txt"

IGNORED_SECTIONS = [
    "[Version]", 
    "[Gameplay/EntityPool]", 
    "[Engine]",
    "[Rendering]"
]

# ================= LOGGING SYSTEM =================
def log(message):
    timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except: pass

def clear_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"--- {APP_NAME} v{VERSION} Log ---\n")
    except: pass

# ================= PATH DETECTION =================
def get_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1: drives.append(letter + ":\\")
        bitmask >>= 1
    return drives

def get_true_documents_path():
    CSIDL_PERSONAL = 5
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
    return buf.value

def find_steam_libraries():
    libraries = []
    steam_path = None
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(hkey, "InstallPath")
    except:
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(hkey, "InstallPath")
        except: pass

    if steam_path and os.path.exists(steam_path):
        libraries.append(os.path.join(steam_path, "steamapps", "common"))
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            try:
                with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        clean = line.strip().replace('"', '').replace('\\\\', '\\')
                        if ":\\" in clean and os.path.exists(clean):
                            potential_lib = os.path.join(clean, "steamapps", "common")
                            if os.path.exists(potential_lib):
                                libraries.append(potential_lib)
            except: pass
    return libraries

def find_game_path_robust():
    log("Searching Registry...")
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 292030")
        path, _ = winreg.QueryValueEx(hkey, "InstallLocation")
        if os.path.exists(path): return path
    except: pass
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games\1495134320", 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
        path, _ = winreg.QueryValueEx(hkey, "path")
        if os.path.exists(path): return path
    except: pass
    
    log("Parsing Steam Configs...")
    steam_libs = find_steam_libraries()
    for lib in steam_libs:
        possible_names = ["The Witcher 3", "The Witcher 3 Wild Hunt"]
        for name in possible_names:
            w3_path = os.path.join(lib, name)
            if os.path.exists(w3_path): return w3_path

    log("Scanning drives (This may take a moment)...")
    drives = get_drives()
    common_roots = [
        "GOG Games\\The Witcher 3 Wild Hunt",
        "Games\\The Witcher 3 Wild Hunt",
        "Games\\The Witcher 3",
        "SteamLibrary\\steamapps\\common\\The Witcher 3"
    ]
    for drive in drives:
        for root in common_roots:
            full_path = os.path.join(drive, root)
            if os.path.exists(full_path): return full_path
    return None

# ================= CORE LOGIC =================
def is_valid_settings_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in range(20):
                line = f.readline().strip()
                if line.startswith('[') and line.endswith(']'):
                    return True
    except: pass
    return False

def scan_game_for_fragments(game_path):
    fragments = {'input': [], 'user': []}
    log(f"Scanning mods in: {game_path}")
    
    for root, dirs, files in os.walk(game_path, followlinks=True):
        for file in files:
            lower_name = file.lower()
            full_path = os.path.join(root, file)
            
            if "config" in root.lower() and "r4game" in root.lower(): continue
            if "bin" in root.lower() and "x64" in root.lower(): continue

            if "input" in lower_name and ("settings" in lower_name or "txt" in lower_name or "ini" in lower_name):
                 if lower_name != "input.settings" and is_valid_settings_file(full_path):
                     fragments['input'].append(full_path)

            elif "user" in lower_name and ("settings" in lower_name or "txt" in lower_name):
                if lower_name not in ["user.settings", "dx12user.settings"] and is_valid_settings_file(full_path):
                    fragments['user'].append(full_path)
    return fragments

def parse_ini_file(filepath):
    data = {}
    current_section = None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('//'): continue
                if line.startswith('[') and line.endswith(']'):
                    if line in IGNORED_SECTIONS:
                        current_section = None
                    else:
                        current_section = line
                        if current_section not in data: data[current_section] = []
                elif current_section:
                    data[current_section].append(line)
    except: pass
    return data

def merge_file(target_full_path, fragment_files):
    if not os.path.exists(target_full_path): 
        log(f"Skipped (Missing): {os.path.basename(target_full_path)}")
        return
    
    # Auto-Create Baseline if missing (Safety for silent run)
    base_file = target_full_path + ".base"
    if not os.path.exists(base_file):
        shutil.copy2(target_full_path, base_file)
        log(f"Auto-Created Baseline: {os.path.basename(target_full_path)}")

    file_name = os.path.basename(target_full_path)
    existing_map = {}
    current_section = None
    with open(target_full_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            clean = line.strip()
            if clean.startswith('[') and clean.endswith(']'):
                current_section = clean
                if current_section not in existing_map: existing_map[current_section] = set()
            elif current_section and clean:
                existing_map[current_section].add(clean)

    new_entries = {}
    total_added = 0
    for fpath in fragment_files:
        data = parse_ini_file(fpath)
        for section, lines in data.items():
            if section not in new_entries: new_entries[section] = []
            known_lines = existing_map.get(section, set())
            for line in lines:
                if line not in known_lines and line not in new_entries[section]:
                    new_entries[section].append(line)
                    total_added += 1

    if total_added == 0:
        log(f"No new entries for {file_name}")
        return

    log(f"Injecting {total_added} lines into {file_name}")
    
    final_output = []
    with open(target_full_path, 'r', encoding='utf-8') as f:
        current_section = None
        for line in f:
            clean_line = line.strip()
            if clean_line.startswith('[') and clean_line.endswith(']'):
                current_section = clean_line
                final_output.append(line)
                if current_section in new_entries:
                    for new_val in new_entries[current_section]:
                        final_output.append(f"{new_val}\n")
                    del new_entries[current_section]
            else:
                final_output.append(line)

    if new_entries:
        for section, lines in new_entries.items():
            final_output.append(f"\n{section}\n")
            for line in lines:
                final_output.append(f"{line}\n")

    with open(target_full_path, 'w', encoding='utf-8') as f:
        f.writelines(final_output)

def main():
    clear_log()
    print(f"--- {APP_NAME} v{VERSION} ---")
    log("Started.")

    # 1. LOCATE
    game_path = find_game_path_robust()
    if not game_path:
        log("CRITICAL: Could not auto-detect game folder.")
        print("\n[!] Could not auto-detect game folder.")
        print("Please use the GUI version to set paths manually.")
        input("Press Enter to exit...")
        return

    log(f"Game Path: {game_path}")

    docs_raw = get_true_documents_path()
    docs_w3 = os.path.join(docs_raw, "The Witcher 3")
    if not os.path.exists(os.path.join(docs_w3, "input.settings")):
        log("CRITICAL: Could not find Documents/The Witcher 3.")
        print("\n[!] Could not find config files.")
        input("Press Enter to exit...")
        return
        
    log(f"Docs Path: {docs_w3}")

    # 2. EXECUTE MERGE
    fragments = scan_game_for_fragments(game_path)
    
    log("Processing input.settings...")
    merge_file(os.path.join(docs_w3, "input.settings"), fragments['input'])
    
    log("Processing user.settings...")
    merge_file(os.path.join(docs_w3, "user.settings"), fragments['user'])
    merge_file(os.path.join(docs_w3, "dx12user.settings"), fragments['user'])

    log("Completed.")
    print(f"\nDone! Check {LOG_FILE} for details.")

if __name__ == "__main__":
    main()
    input("Press Enter to close...")