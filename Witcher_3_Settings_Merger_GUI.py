import os
import shutil
import winreg
import ctypes.wintypes
import string
import datetime
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk

# ================= CONFIGURATION =================
APP_NAME = "Witcher 3 Settings Merger (GUI)"
VERSION = "0.9.0 (Beta)"  # Updated to reflect pre-release status
LOG_FILE = "Merger_Log.txt"

IGNORED_SECTIONS = [
    "[Version]", 
    "[Gameplay/EntityPool]", 
    "[Engine]",
    "[Rendering]"
]

# ================= PATH UTILS =================
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

def find_game_path_robust(logger_func=None):
    if logger_func: logger_func("Searching Registry...")
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
    
    if logger_func: logger_func("Parsing Steam Configs...")
    steam_libs = find_steam_libraries()
    for lib in steam_libs:
        possible_names = ["The Witcher 3", "The Witcher 3 Wild Hunt"]
        for name in possible_names:
            w3_path = os.path.join(lib, name)
            if os.path.exists(w3_path): return w3_path

    if logger_func: logger_func("Scanning drives (This may take a moment)...")
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

def scan_game_for_fragments(game_path, logger_func):
    fragments = {'input': [], 'user': []}
    logger_func(f"Scanning mods in: {game_path}")
    
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

def save_baseline_file(target_full_path, logger_func):
    if not os.path.exists(target_full_path): return
    base_file = target_full_path + ".base"
    shutil.copy2(target_full_path, base_file)
    logger_func(f"Saved Baseline: {os.path.basename(target_full_path)}")

def load_baseline_file(target_full_path, logger_func):
    base_file = target_full_path + ".base"
    if os.path.exists(base_file):
        shutil.copy2(base_file, target_full_path)
        logger_func(f"Restored: {os.path.basename(target_full_path)}")
    else:
        logger_func(f"No Baseline found for {os.path.basename(target_full_path)}")

def merge_file(target_full_path, fragment_files, logger_func):
    if not os.path.exists(target_full_path): 
        logger_func(f"Skipped (Missing): {os.path.basename(target_full_path)}")
        return
    
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
        logger_func(f"No new entries for {file_name}")
        return

    logger_func(f"Injecting {total_added} lines into {file_name}")
    
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

# ================= GUI APP =================
class MergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("600x650")
        
        style = ttk.Style()
        style.theme_use('clam')

        # --- HEADER / HELP ---
        top_frame = ttk.Frame(root, padding="10 5 10 0")
        top_frame.pack(fill="x")
        ttk.Label(top_frame, text="Witcher 3 Settings Merger", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(top_frame, text="How to Use", command=self.show_help).pack(side="right")

        # --- PATH SELECTION ---
        path_frame = ttk.LabelFrame(root, text="Directories", padding="10")
        path_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(path_frame, text="Game Directory:").grid(row=0, column=0, sticky="w")
        
        # Standard tk.Entry for color support
        self.entry_game = tk.Entry(path_frame, relief="sunken")
        self.entry_game.grid(row=1, column=0, sticky="ew", padx=(0, 5), ipady=3)
        self.entry_game.bind("<KeyRelease>", self.check_paths_live) # Real-time check
        
        ttk.Button(path_frame, text="Browse", command=self.browse_game).grid(row=1, column=1)

        ttk.Label(path_frame, text="Documents/The Witcher 3:").grid(row=2, column=0, sticky="w", pady=(10,0))
        
        # Standard tk.Entry for color support
        self.entry_docs = tk.Entry(path_frame, relief="sunken")
        self.entry_docs.grid(row=3, column=0, sticky="ew", padx=(0, 5), ipady=3)
        self.entry_docs.bind("<KeyRelease>", self.check_paths_live) # Real-time check
        
        ttk.Button(path_frame, text="Browse", command=self.browse_docs).grid(row=3, column=1)
        path_frame.columnconfigure(0, weight=1)

        # --- ACTIONS ---
        btn_frame = ttk.LabelFrame(root, text="Actions", padding="10")
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="Save Baseline", command=self.save_baseline_ui).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Load Baseline", command=lambda: self.run_thread("Load")).pack(fill="x", pady=2)
        ttk.Separator(btn_frame, orient='horizontal').pack(fill='x', pady=5)
        ttk.Button(btn_frame, text="Merge Settings", command=lambda: self.run_thread("Merge")).pack(fill="x", pady=2)

        # --- OPTIONS ---
        opt_frame = ttk.Frame(root)
        opt_frame.pack(fill="x", padx=15, pady=0)
        self.log_to_file_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Save Output to Log File", variable=self.log_to_file_var).pack(side="left")

        # --- LOGGING ---
        log_frame = ttk.LabelFrame(root, text="Output Log", padding="5")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.log_area.pack(fill="both", expand=True)

        # Initial Auto-Detect
        self.log("Initializing...")
        self.root.after(100, self.auto_detect_paths)

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        full_msg = f"{timestamp} {msg}"
        
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, full_msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

        if self.log_to_file_var.get():
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(full_msg + "\n")
            except: pass

    # --- VALIDATION LOGIC ---
    def check_paths_live(self, event=None):
        # Game Path Check
        game_path = self.entry_game.get()
        if game_path and os.path.exists(game_path):
            self.entry_game.config(bg="white")
        else:
            self.entry_game.config(bg="#ffdddd") # Light Red/Pink

        # Docs Path Check
        docs_path = self.entry_docs.get()
        # Must exist AND look like a Witcher config folder
        if docs_path and os.path.exists(docs_path) and os.path.exists(os.path.join(docs_path, "input.settings")):
            self.entry_docs.config(bg="white")
        else:
            self.entry_docs.config(bg="#ffdddd")

    def browse_game(self):
        path = filedialog.askdirectory(title="Select The Witcher 3 Game Folder")
        if path:
            self.entry_game.delete(0, tk.END)
            self.entry_game.insert(0, path)
            self.check_paths_live()

    def browse_docs(self):
        path = filedialog.askdirectory(title="Select Documents/The Witcher 3 Folder")
        if path:
            self.entry_docs.delete(0, tk.END)
            self.entry_docs.insert(0, path)
            self.check_paths_live()

    def auto_detect_paths(self):
        threading.Thread(target=self._detect_thread, daemon=True).start()

    def _detect_thread(self):
        self.log("Auto-detecting paths...")
        game = find_game_path_robust(self.log)
        if game: 
            self.root.after(0, lambda: self._update_entry(self.entry_game, game))
            self.log(f"Found Game: {game}")
        else:
            self.log("Could not find Game path automatically.")
            self.root.after(0, self.check_paths_live) # Trigger red

        raw_docs = get_true_documents_path()
        docs = os.path.join(raw_docs, "The Witcher 3")
        if os.path.exists(os.path.join(docs, "input.settings")):
            self.root.after(0, lambda: self._update_entry(self.entry_docs, docs))
            self.log(f"Found Configs: {docs}")
        else:
            self.log("Could not find Configs automatically.")
            self.root.after(0, self.check_paths_live) # Trigger red

    def _update_entry(self, entry_widget, text):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, text)
        self.check_paths_live() # Validate immediately after auto-fill

    def save_baseline_ui(self):
        docs_path = self.entry_docs.get()
        if not os.path.exists(docs_path):
            messagebox.showerror("Error", "Documents path invalid.")
            return

        base_exists = os.path.exists(os.path.join(docs_path, "input.settings.base"))
        if base_exists:
            confirm = messagebox.askyesno("Overwrite Baseline?", 
                                          "A Baseline backup already exists.\n\nDo you want to overwrite it with your CURRENT settings?")
            if not confirm: return

        self.run_thread("Save")

    def run_thread(self, mode):
        # Basic check before running
        self.check_paths_live() 
        if self.entry_game['bg'] == "#ffdddd" or self.entry_docs['bg'] == "#ffdddd":
            messagebox.showwarning("Invalid Paths", "Please fix the red (invalid) directory paths before proceeding.")
            return
        threading.Thread(target=self._process_logic, args=(mode,), daemon=True).start()

    def _process_logic(self, mode):
        game_path = self.entry_game.get()
        docs_path = self.entry_docs.get()

        self.log(f"--- Starting: {mode} ---")
        
        targets = ["input.settings", "user.settings", "dx12user.settings"]

        if mode == "Save":
            for t in targets: save_baseline_file(os.path.join(docs_path, t), self.log)
        elif mode == "Load":
            for t in targets: load_baseline_file(os.path.join(docs_path, t), self.log)
        elif mode == "Merge":
            fragments = scan_game_for_fragments(game_path, self.log)
            merge_file(os.path.join(docs_path, "input.settings"), fragments['input'], self.log)
            merge_file(os.path.join(docs_path, "user.settings"), fragments['user'], self.log)
            merge_file(os.path.join(docs_path, "dx12user.settings"), fragments['user'], self.log)

        self.log("--- Operation Complete ---")
        messagebox.showinfo("Success", "Operation Finished.")

    def show_help(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("How to Use")
        help_win.geometry("500x600")
        
        help_text = """What is this tool?
This program automates adding mod inputs and settings to your game config files. It tries to automatically find your Witcher 3 game directory and searches from the root down for installed mods, then merges their input and user settings, if any, into the game's corresponding .setting files in the Documents/The Witcher 3 folder. 

Currently handles input.settings, user.settings, and dx12user.settings. The program attempts to intelligently identify files that contain text that should be included in these primary files based on a variety of keywords in their title as well as in their content. It tries to filter out false positives, place entries under their correct headings, and attempts to prevent duplicate entries.

KEY FEATURES

1. Save Baseline
   Saves a snapshot of your current settings. Default purpose is to use this when your settings are "clean" as they would be on a fresh install of the game, before any merges. Or you could just save the current state before you do some mod experimenting; use it how you want.
   * Note: If you already have a backup, it will ask for confirmation before overwriting.

2. Load Baseline
   The "Undo" button. Reverts your files to the state they were in when you last clicked "Save Baseline".
   * Use this to clean out old keybinds from uninstalled mods before re-merging.

3. Merge Settings
   Scans your Witcher 3 directory for mod settings and adds them to your current settings files. 
   * This is an "Additive" process (it adds lines, but does not remove old ones if mods have since been removed).

---

RECOMMENDED WORKFLOW (Rebuild)
To ensure your settings stay clean:
1. Click "Load Baseline" (Resets to you saved clean state).
2. Click "Merge Settings" (Adds currently installed mods).

---

IMPORTANT NOTES
* Vortex Users: Symlinks etc. should be fully supported.
* Script Merge and Filelist Update: This tool complements these and should be used together.
* Auto-Detect: If directory paths are red/empty, use the Browse buttons to select manually.

* Caveat: I made this for personal use over a few hours in Antigravity and wanted to provide it to others who might save some minutes of their lives. I have yet to thoroughly test it, however, as it's worked well for me so far. YMMV. Provided as-is and likely won't have time to offer support if you have issues."""
        text_widget = scrolledtext.ScrolledText(help_win, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill="both", expand=True)
        text_widget.insert(tk.END, help_text)
        text_widget.configure(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = MergerApp(root)
    root.mainloop()