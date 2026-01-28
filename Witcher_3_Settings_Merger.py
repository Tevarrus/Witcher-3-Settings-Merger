import os
import sys
import shutil
import winreg
import ctypes.wintypes
import string
import datetime
import threading
import re
import tkinter as tk
import subprocess
from tkinter import filedialog, scrolledtext, messagebox, ttk
try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ================= RESOURCE PATH HELPER =================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================= CONFIGURATION =================
APP_NAME = "Witcher 3 Settings Merger"
VERSION = "0.9.0 (Beta)"
LOG_FILE = "Merger_Log.txt"

IGNORED_SECTIONS = [
    "[Version]", 
    "[Gameplay/EntityPool]", 
    "[Engine]",
    "[Rendering]"
]

# ================= PATH UTILS =================
# ================= ASSETS =================
def create_pixel_assets():
    """Generates 14x14 Checkbox and Radio assets for Dark Theme."""
    # Colors
    C_BG = "#2b2b2b" # Background
    C_BD = "#666666" # Border
    C_FG = "#ffffff" # Check/Dot
    
    # 1. Checkbox Unchecked
    img_chk_off = tk.PhotoImage(width=14, height=14)
    img_chk_off.put(C_BG, to=(0,0,13,13))
    # Border
    img_chk_off.put(C_BD, to=(0,0,14,1))  # Top
    img_chk_off.put(C_BD, to=(0,13,14,14))# Bottom
    img_chk_off.put(C_BD, to=(0,0,1,14))  # Left
    img_chk_off.put(C_BD, to=(13,0,14,14))# Right
    
    # 2. Checkbox Checked
    img_chk_on = img_chk_off.copy()
    # Draw Check (Generic V shape)
    #      X
    #       X
    # X    X
    #  X  X
    #   XX
    coords = [
        (3,6), (3,7),
        (4,7), (4,8),
        (5,8), (5,9),
        (6,9), (6,8),
        (7,8), (7,7),
        (8,7), (8,6),
        (9,6), (9,5),
        (10,5)
    ]
    for x,y in coords:
        img_chk_on.put(C_FG, to=(x,y,x+1,y+1))

    # 3. Radio Unchecked
    img_rad_off = tk.PhotoImage(width=14, height=14)
    img_rad_off.put(C_BG, to=(0,0,14,14))
    # Approximation of circle border
    # Corners
    img_rad_off.put(C_BD, to=(4,0,10,1)) # Top
    img_rad_off.put(C_BD, to=(4,13,10,14)) # Bot
    img_rad_off.put(C_BD, to=(0,4,1,10)) # Left
    img_rad_off.put(C_BD, to=(13,4,14,10)) # Right
    img_rad_off.put(C_BD, to=(1,2,2,4)) # TL
    img_rad_off.put(C_BD, to=(2,1,4,2)) # TL2
    img_rad_off.put(C_BD, to=(12,2,13,4)) # TR
    img_rad_off.put(C_BD, to=(10,1,12,2)) # TR2
    img_rad_off.put(C_BD, to=(1,10,2,12)) # BL
    img_rad_off.put(C_BD, to=(2,12,4,13)) # BL2
    img_rad_off.put(C_BD, to=(12,10,13,12)) # BR
    img_rad_off.put(C_BD, to=(10,12,12,13)) # BR2
    
    # 4. Radio Checked
    img_rad_on = img_rad_off.copy()
    # Center Dot
    img_rad_on.put(C_FG, to=(4,4,10,10)) # 6x6 square roughly
    
    return img_chk_off, img_chk_on, img_rad_off, img_rad_on


def get_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1: drives.append(letter + ":\\")
        bitmask >>= 1
    return drives

def apply_dark_title_bar(window):
    """
    Forces Windows 10/11 Title Bar to use Dark Mode via DWM API.
    """
    try:
        window.update()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except:
        pass

def apply_window_icon(window):
    """
    Sets the window icon using 'icon.ico' from the resource path.
    Falls back gracefully if the icon file is missing.
    """
    try:
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            window.iconbitmap(icon_path)
    except Exception:
        pass # Fallback to default feather

def center_on_screen(window, width=None, height=None):
    """
    Centers the window on the screen. 
    If width/height not provided, uses currently requested geometry.
    """
    window.update_idletasks()
    
    if width is None: width = window.winfo_reqwidth()
    if height is None: height = window.winfo_reqheight()
    
    # Check if width/height are reasonable defaults if req is tiny (e.g. before pack)
    if width < 200: width = 600
    if height < 200: height = 750

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    # Ensure not off-top
    if y < 0: y = 0

    window.geometry(f'{width}x{height}+{x}+{y}')

def setup_popup_geometry(window, parent, mode="secondary"):
    """
    Configures popup geometry based on mode:
    - 'secondary': Match Parent Height, Wider Width, Adjacent Position (for Conflict/Help)
    - 'tertiary': Minimal Fit, Centered on Parent (for Dialogs)
    """
    window.update_idletasks()
    
    # Get Parent Geometry via geometry string to get TRUE decorative position
    # winfo_rootx/y gives content area, excluding title bar.
    # geometry() returns "WxH+X+Y" where X/Y are top-left of decorative frame.
    geom_str = parent.geometry()
    match = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", geom_str)
    
    if match:
        parent_w_true = int(match.group(1))
        parent_h_true = int(match.group(2))
        parent_x_true = int(match.group(3))
        parent_y_true = int(match.group(4))
    else:
        # Fallback if geometry string fails or is weird
        parent_x_true = parent.winfo_rootx()
        parent_y_true = parent.winfo_rooty()
        # rooty is below title bar. We can guess title bar height ~30-40px?
        # Better to just use rooty and accept slight offset if regex fails.
        parent_w_true = parent.winfo_width()
        parent_h_true = parent.winfo_height()

    req_w = window.winfo_reqwidth()
    req_h = window.winfo_reqheight()
    
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    if mode == "secondary":
        # --- SECONDARY: Match Height, Wider, Adjacent ---
        h = parent_h_true # Strictly match parent height
        
        # Width: Content + 60% extra padding (approx 1.6x)
        w = int(req_w * 1.6)
        min_w = 600 # Wider min for comfort
        w = max(w, min_w)
        
        max_w = int(screen_w * 0.50) # Allow half screen
        if w > max_w: w = max_w
        
        # Position: Right adjacent
        # Using parent_x_true (frame edge) + parent_w_true (frame width)
        x = parent_x_true + parent_w_true + 10
        y = parent_y_true # Align Top of Title Bars
        
        # Screen Check
        if x + w > screen_w:
            # Try Left
            x_left = parent_x_true - w - 10
            if x_left >= 0:
                x = x_left
            else:
                # Fallback: Center offset
                x = parent_x_true + 50
                y = parent_y_true + 50
                
        window.geometry(f"{w}x{h}+{x}+{y}")
        
    else:
        # --- TERTIARY: Minimal Fit, Centered ---
        w = req_w
        h = req_h
        
        # Center relative to parent
        # Use simple arithmetic on centers
        center_x = parent_x_true + (parent_w_true // 2)
        center_y = parent_y_true + (parent_h_true // 2)
        
        x = center_x - (w // 2)
        y = center_y - (h // 2)
        
        # Ensure onscreen
        if x < 0: x = 0
        if y < 0: y = 0
        
        window.geometry(f"{w}x{h}+{x}+{y}")





def position_window_adjacent(window, parent):
    """
    Positions the 'window' directly adjacent to the 'parent' window.
    Tries Right side first, then Left side if off-screen.
    """
    window.update_idletasks() # Ensure dimensions are calculated
    
    # Get Parent Geometry
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    
    # Get Window Geometry (reqwidth/reqheight for autosize windows)
    req_w = window.winfo_reqwidth()
    req_h = window.winfo_reqheight()
    
    # Calculate Right Position
    # Gap of 10 pixels
    x = parent_x + parent_w + 10
    y = parent_y
    
    # Screen Width Check (rudimentary)
    screen_w = window.winfo_screenwidth()
    if x + req_w > screen_w:
        # Try Left
        x = parent_x - req_w - 10
        
    # Ensure y is somewhat aligned but not off-top
    if y < 0: y = 0
    
    window.geometry(f"+{x}+{y}")

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

# ================= PARSING LOGIC =================
# ================= INPUT CONSTANTS =================
W3_VALID_INPUTS = [
    # Keyboard - Letters
    "IK_A", "IK_B", "IK_C", "IK_D", "IK_E", "IK_F", "IK_G", "IK_H", "IK_I", "IK_J", "IK_K", "IK_L", "IK_M", 
    "IK_N", "IK_O", "IK_P", "IK_Q", "IK_R", "IK_S", "IK_T", "IK_U", "IK_V", "IK_W", "IK_X", "IK_Y", "IK_Z",
    # Keyboard - Numbers & F-Keys
    "IK_0", "IK_1", "IK_2", "IK_3", "IK_4", "IK_5", "IK_6", "IK_7", "IK_8", "IK_9",
    "IK_F1", "IK_F2", "IK_F3", "IK_F4", "IK_F5", "IK_F6", "IK_F7", "IK_F8", "IK_F9", "IK_F10", "IK_F11", "IK_F12",
    # Keyboard - Special
    "IK_Escape", "IK_Tab", "IK_Space", "IK_Enter", "IK_Backspace", "IK_LShift", "IK_RShift", "IK_LControl", "IK_RControl",
    "IK_LAlt", "IK_RAlt", "IK_CapsLock", "IK_NumPad0", "IK_NumPad1", "IK_NumPad2", "IK_NumPad3", "IK_NumPad4",
    "IK_NumPad5", "IK_NumPad6", "IK_NumPad7", "IK_NumPad8", "IK_NumPad9", "IK_NumStar", "IK_NumSlash", "IK_NumPlus", "IK_NumMinus",
    "IK_Up", "IK_Down", "IK_Left", "IK_Right", "IK_Home", "IK_End", "IK_PageUp", "IK_PageDown", "IK_Insert", "IK_Delete",
    "IK_Tilde", "IK_SingleQuote", "IK_Comma", "IK_Period", "IK_Slash", "IK_Semicolon", "IK_LeftBracket", "IK_RightBracket", "IK_Backslash",
    # Mouse
    "IK_LeftMouse", "IK_RightMouse", "IK_MiddleMouse", "IK_Mouse4", "IK_Mouse5", "IK_Mouse6", "IK_Mouse7", "IK_Mouse8",
    "IK_MouseWheelUp", "IK_MouseWheelDown", "IK_MouseX", "IK_MouseY",
    # Controller (Standard/Xbox)
    "IK_Pad_A_CROSS", "IK_Pad_B_CIRCLE", "IK_Pad_X_SQUARE", "IK_Pad_Y_TRIANGLE", 
    "IK_Pad_Start", "IK_Pad_Back_Select",
    "IK_Pad_DigitUp", "IK_Pad_DigitDown", "IK_Pad_DigitLeft", "IK_Pad_DigitRight",
    "IK_Pad_LeftTrigger", "IK_Pad_RightTrigger", "IK_Pad_LeftShoulder", "IK_Pad_RightShoulder",
    "IK_Pad_LeftThumb", "IK_Pad_RightThumb",
    "IK_Pad_LeftAxisX", "IK_Pad_LeftAxisY", "IK_Pad_RightAxisX", "IK_Pad_RightAxisY"
]
W3_VALID_INPUTS.sort()

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

def parse_file_to_dict(filepath, source_name="Unknown"):
    """
    Returns a dict structure:
    data[section] = [ {'line': raw_line, 'key': extracted_key, 'source': source_name} ]
    """
    data = {}
    current_section = None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean = line.strip()
                if not clean or clean.startswith(';') or clean.startswith('//'): continue
                
                if clean.startswith('[') and clean.endswith(']'):
                    # Robust Parsing: Normalize Section Header
                    # "[ Section ]" -> "[Section]"
                    raw_name = clean[1:-1].strip()
                    normalized_section = f"[{raw_name}]"
                    
                    if normalized_section in IGNORED_SECTIONS:
                        current_section = None
                    else:
                        current_section = normalized_section
                        if current_section not in data: data[current_section] = []
                elif current_section:
                    # extract key for comparison
                    # For user settings: Key is usually before '=' (GrassDensity=3000)
                    # For input settings: Key is the bind (IK_E=(Action...))
                    key_part = clean.split('=', 1)[0].strip()
                    entry = {
                        'line': clean,
                        'key': key_part, 
                        'source': source_name
                    }
                    data[current_section].append(entry)
    except: pass
    return data

# ================= UI CLASSES =================

class DarkDialog(tk.Toplevel):
    """
    Custom replacements for messagebox to match the Dark Theme.
    """
    def __init__(self, parent, title, message, buttons=["OK"], icon="info"):
        super().__init__(parent)
        self.withdraw() # Hide immediately
        self.title(title)
        self.configure(bg="#202020")
        self.after(10, lambda: apply_dark_title_bar(self))
        apply_window_icon(self)
        self.result = None
        
        # Geometry: Auto-size but constrain width for messages
        # We let pack handle height.
        # Position adjacent to parent
        self.resizable(False, False)
        
        # Content
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True) # expand=True fills space
        
        # Icon/Title (Text based)
        icon_char = "ℹ"
        icon_color = "#ffffff"
        if icon == "warning": icon_char = "⚠"; icon_color = "#ffcc00"
        elif icon == "error": icon_char = "✖"; icon_color = "#ff5555"
        
        lbl_icon = tk.Label(frame, text=icon_char, font=("Segoe UI", 24), bg="#202020", fg=icon_color)
        lbl_icon.pack(side="top", pady=(0, 10))
        
        lbl_msg = ttk.Label(frame, text=message, wraplength=360, justify="center")
        lbl_msg.pack(side="top", expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        
        for btn_text in buttons:
            b = ttk.Button(btn_frame, text=btn_text, command=lambda t=btn_text: self.on_btn(t))
            b.pack(side="right", padx=5)
            
        self.transient(parent)
        
        # Position after widgets packed
        setup_popup_geometry(self, parent, mode="tertiary")
        
        self.deiconify()
        self.grab_set()
        self.focus_set()
        self.wait_window()

    def on_btn(self, text):
        self.result = text
        self.destroy()

class RemapDialog(tk.Toplevel):
    def __init__(self, parent, current_key):
        super().__init__(parent)
        self.withdraw() # Hide immediately
        self.title("Remap Input")
        self.configure(bg="#202020")
        self.result = None
        
        # Center and Size
        w, h = 400, 500
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.transient(parent)
        # Grab set moved to end
        
        # Apply dark title bar
        apply_dark_title_bar(self)
        apply_window_icon(self)
        
        # UI Elements
        tk.Label(self, text=f"Remapping: {current_key}", font=("Segoe UI", 10, "bold"), bg="#202020", fg="#e0e0e0").pack(pady=10)
        
        # Search Frame
        search_frame = tk.Frame(self, bg="#202020")
        search_frame.pack(fill="x", padx=10, pady=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_list)
        entry = tk.Entry(search_frame, textvariable=self.search_var, bg="#333333", fg="#ffffff", insertbackground="white", font=("Consolas", 10))
        entry.pack(fill="x")
        entry.focus_set()
        
        # Listbox Frame
        list_frame = tk.Frame(self, bg="#202020")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.listbox = tk.Listbox(list_frame, bg="#2b2b2b", fg="#e0e0e0", font=("Consolas", 10), selectbackground="#404040", highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.listbox.bind("<Double-Button-1>", self._on_confirm)
        
        # Buttons
        btn_frame = tk.Frame(self, bg="#202020")
        btn_frame.pack(fill="x", pady=10)
        
        tk.Button(btn_frame, text="Confirm", command=self._on_confirm, bg="#404040", fg="white", relief="flat", padx=15).pack(side="left", padx=20)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, bg="#333333", fg="white", relief="flat", padx=15).pack(side="right", padx=20)
        
        # Populate initially
        self._filter_list()
        
        self.deiconify() # Reveal
        self.grab_set() # Lock
        self.wait_window()

    def _filter_list(self, *args):
        query = self.search_var.get().upper()
        self.listbox.delete(0, tk.END)
        
        for item in W3_VALID_INPUTS:
            if query in item.upper():
                self.listbox.insert(tk.END, item)

    def _on_confirm(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            self.result = self.listbox.get(sel[0])
            self.destroy()


class ConflictWindow(tk.Toplevel):
    def __init__(self, parent, file_type, conflicts):
        super().__init__(parent)
        self.withdraw() # Hide immediately to prevent flash
        self.title(f"Conflict Manager - {file_type}")
        self.configure(bg="#202020")
        self.result = {}
        self.conflicts = conflicts
        self.file_type = file_type
        self.cancelled = True
        self.key_icon = None # Will store the PhotoImage
        
        # 1. Main Layout (Fills the fixed window size)
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        lbl = ttk.Label(self.main_frame, text=f"Conflicts detected in {file_type}.\nSelect the settings to keep:", font=("Segoe UI", 11, "bold"))
        lbl.pack(side="top", fill="x", pady=(0, 10))
        
        # 2. Scrollable Area
        self.canvas = tk.Canvas(self.main_frame, bg="#2b2b2b", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 3. Inner Content Frame
        self.scroll_frame = tk.Frame(self.canvas, bg="#2b2b2b")
        
        # BINDING: This forces the scrollbar to match the TEXT height exactly.
        self.scroll_frame.bind(
            "<Configure>", 
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Create Window inside Canvas
        self.window_id = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        
        # BINDING: This forces the text to fill the width of the window.
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.window_id, width=e.width)
        )
        
        # Mousewheel
        self._bind_mousewheel()
        
        # 4. Populate
        self.vars = {}
        # Generate Icon for Remap Buttons (One-time)
        self.key_icon = self._generate_key_icon() if HAS_PIL else None
        
        self._populate_list()
        
        # 5. Footer Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", pady=15, padx=10) # Increased pady for visual separation

        # Left: Bulk Tools
        tools_frame = ttk.Frame(btn_frame)
        tools_frame.pack(side="left")
        
        ttk.Button(tools_frame, text="Enable All", command=lambda: self.bulk_select("all"), width=12).pack(side="left", padx=2)
        ttk.Button(tools_frame, text="Disable All", command=lambda: self.bulk_select("none"), width=12).pack(side="left", padx=2)
        ttk.Button(tools_frame, text="Vanilla Only", command=lambda: self.bulk_select("vanilla"), width=12).pack(side="left", padx=2)

        # Right: Confirm
        ttk.Button(btn_frame, text="Confirm Selection", command=self.on_confirm, style="Primary.TButton").pack(side="right")
        
        # 6. Final Setup
        self.transient(parent)
        self.parent = parent
        
        self.after(10, lambda: apply_dark_title_bar(self))
        apply_window_icon(self)
        self.update_idletasks()
        setup_popup_geometry(self, parent, mode="secondary")
        self.deiconify() # Reveal now that geometry is set
        self.grab_set() # Lock input last

    def _generate_key_icon(self):
        """
        Generates a 20x20 transparent icon appearing like a keyboard key.
        - Rounded/Filled Rectangle (Light Gray)
        - Darker border on bottom/right for 3D effect
        - Letter 'K' in center
        """
        try:
            # Create transparent image
            size = 20
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Key Dimensions (16x16 centered)
            # x0, y0, x1, y1
            pad = 2
            x0, y0 = pad, pad
            x1, y1 = size-pad, size-pad
            
            # Draw Shadow/Border (slightly offset bottom-right or essentially the 'dark' side)
            # Actually, let's draw a filled rect for the key face
            # Face Color: #e0e0e0 (Light Gray)
            # Border Color: #a0a0a0 (Darker Gray) for bottom/right
            
            # Draw Main Face
            draw.rectangle([x0, y0, x1, y1], fill="#e0e0e0", outline=None)
            
            # Draw 3D Bevel (Bottom and Right lines)
            draw.line([(x0, y1), (x1, y1), (x1, y0)], fill="#888888", width=1)
            
            # Draw Letter '?' (Simple pixel art style)
            # Center approx (10, 10)
            color = "#202020"
            
            # Hook
            # Top Bar: (7, 6) -> (13, 6)
            draw.line([(7, 6), (13, 6)], fill=color, width=1)
            # Right Down: (13, 6) -> (13, 9)
            draw.line([(13, 6), (13, 9)], fill=color, width=1)
            # Inward: (13, 9) -> (10, 9)
            draw.line([(13, 9), (10, 9)], fill=color, width=1)
            # Stem Down: (10, 9) -> (10, 11)
            draw.line([(10, 9), (10, 11)], fill=color, width=1)
            
            # Dot
            draw.point((10, 14), fill=color)
            draw.point((10, 13), fill=color) # Make it 2px tall for visibility
            
            return ImageTk.PhotoImage(img)
            
        except Exception as e:
            print(f"Icon Gen Error: {e}")
            return None

    def _bind_mousewheel(self):
        """Binds mousewheel to the canvas when hovering."""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")

        # Bind enter/leave for the canvas and the internal frame
        self.canvas.bind('<Enter>', _bind_to_mousewheel)
        self.canvas.bind('<Leave>', _unbind_from_mousewheel)
        self.scroll_frame.bind('<Enter>', _bind_to_mousewheel)
        self.scroll_frame.bind('<Leave>', _unbind_from_mousewheel)

    def _parse_line(self, key, line):
        """
        Extracts the 'Action' or 'Value' from a line using Regex for robustness.
        - input.settings: IK_E=(Action=CastSign) -> CastSign
        - user.settings: GrassDensity=3000 -> 3000
        Handles spaces gracefully (e.g. Action = CastSign).
        """
        # input.settings Logic: Look for Action=...
        if "Action" in line:
            # Regex: Action \s* = \s* (capture until comma or paren)
            match = re.search(r"Action\s*=\s*([^,)]+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
        # user.settings or Fallback input: Value after first =
        # GrassDensity=3000 or GrassDensity = 3000
        if "=" in line:
             try:
                 # Split by first = only, then strip whitespace
                 parts = line.split("=", 1)
                 val = parts[1].strip()
                 return val
             except: pass
             
        # Fallback: Just return part of line
        return line

    def _populate_list(self):
        # Conflicts structure:
        # conflicts[section][key] = [ {line, source}, {line, source} ... ]
        
        row_idx = 0
        
        # Grid Configuration
        # Col 0: Select (width small)
        # Col 1: Source (width moderate)
        # Col 2: Action (width moderate)
        # Col 3: Input (width moderate? maybe fill)
        # Col 4: Remap (width small)
        
        # We can configure weights on the scroll_frame, BUT scroll_frame is just a frame.
        # We need to set weights on columns for it to expand nicely.
        self.scroll_frame.grid_columnconfigure(3, weight=1) 
        
        for section, keys in self.conflicts.items():
            if not keys: continue
            
            # --- SECTION HEADER ---
            lbl = tk.Label(self.scroll_frame, text=section, font=("Consolas", 10, "bold"), bg="#333333", fg="#ffffff")
            lbl.grid(row=row_idx, column=0, columnspan=5, sticky="ew", pady=(15, 5))
            row_idx += 1
            
            for key, options in keys.items():
                
                # --- GROUP HEADER ROW ---
                # Select | Source | Action | Input | Remap
                h_style = {"bg": "#2b2b2b", "fg": "#888888", "font": ("Segoe UI", 8, "bold")}
                tk.Label(self.scroll_frame, text="", **h_style).grid(row=row_idx, column=0, sticky="w") # Select
                tk.Label(self.scroll_frame, text="SOURCE", **h_style).grid(row=row_idx, column=1, sticky="w", padx=5)
                tk.Label(self.scroll_frame, text="ACTION / VALUE", **h_style).grid(row=row_idx, column=2, sticky="w", padx=5)
                tk.Label(self.scroll_frame, text="INPUT / KEY", **h_style).grid(row=row_idx, column=3, sticky="w", padx=5)
                # Remap Header (Center)
                tk.Label(self.scroll_frame, text="REMAP", **h_style).grid(row=row_idx, column=4, sticky="", padx=5)
                row_idx += 1
                
                # Sort options? Keep native order usually (Base -> Mod A -> Mod B)
                
                # Determine Selection Type
                is_input_file = "input.settings" in self.file_type
                
                if not is_input_file:
                    # RADIO BUTTON SETUP
                    # Determine default selected index
                    default_idx = len(options)-1
                    for i, o in enumerate(options):
                        if o.get('selected', False):
                            default_idx = i
                            break
                    selected_val = tk.IntVar(value=default_idx) 
                    self.vars[(section, key)] = selected_val

                for idx, opt in enumerate(options):
                    line_content = opt['line']
                    source = opt['source']
                    
                    # Parse Action
                    action_val = self._parse_line(key, line_content)
                    
                    # Col 0: SELECT
                    if is_input_file:
                        # Checkbox (Use new Dark Style)
                        is_selected = opt.get('selected', False)
                        var = tk.BooleanVar(value=is_selected)
                        self.vars[(section, key, idx)] = var
                        
                        btn = ttk.Checkbutton(self.scroll_frame, variable=var, style="Seamless.TCheckbutton")
                        btn.grid(row=row_idx, column=0, sticky="w", padx=5)
                    else:
                        # Radio (Use new Seamless Style)
                        btn = ttk.Radiobutton(self.scroll_frame, variable=selected_val, value=idx, style="Seamless.TRadiobutton")
                        btn.grid(row=row_idx, column=0, sticky="w", padx=5)

                    # Col 1: SOURCE
                    tk.Label(self.scroll_frame, text=f"[{source}]", font=("Segoe UI", 9), bg="#2b2b2b", fg="#888888")\
                        .grid(row=row_idx, column=1, sticky="w", padx=5)

                    # Col 2: ACTION (Bold White)
                    tk.Label(self.scroll_frame, text=action_val, font=("Segoe UI", 9, "bold"), bg="#2b2b2b", fg="#ffffff")\
                        .grid(row=row_idx, column=2, sticky="w", padx=5)
                        
                    # Col 3: INPUT / KEY (Light Grey)
                    # Use a mutable label ref so we can update it
                    lbl_input = tk.Label(self.scroll_frame, text=key, font=("Segoe UI", 9), bg="#2b2b2b", fg="#aaaaaa")
                    lbl_input.grid(row=row_idx, column=3, sticky="w", padx=5)
                        
                    # Col 4: REMAP Button
                    # Only map if it's input.settings? Yes, usually rebind user.settings keys is dangerous.
                    if is_input_file:
                        if self.key_icon:
                            btn_remap = tk.Button(self.scroll_frame, image=self.key_icon, bg="#333333", activebackground="#444444", 
                                                  relief="flat", borderwidth=0,
                                                  command=lambda s=section, k=key, i=idx, l=lbl_input: self._on_remap(s, k, i, l))
                        else:
                            btn_remap = tk.Button(self.scroll_frame, text="✏️", font=("Segoe UI", 8), bg="#333333", fg="white", 
                                                  relief="flat", width=3,
                                                  command=lambda s=section, k=key, i=idx, l=lbl_input: self._on_remap(s, k, i, l))
                        btn_remap.grid(row=row_idx, column=4, sticky="", padx=5)

                    row_idx += 1

                # Separator after group
                ttk.Separator(self.scroll_frame, orient='horizontal').grid(row=row_idx, column=0, columnspan=5, sticky='ew', pady=(5, 15))
                row_idx += 1

    def _on_remap(self, section, key, idx, lbl_widget):
        # Open Dialog
        dlg = RemapDialog(self, key)
        if dlg.result:
             new_key = dlg.result
             
             # Disable global refresh to avoid reset?
             # We just update local data structure
             
             # 1. Update Layout
             lbl_widget.configure(text=new_key, fg="#ffff00") # Yellow to indicate change
             
             # 2. Update Data
             # conflicts[section][key][idx]['line'] needs update? 
             # Wait, 'line' acts as the Definition.
             # If input.settings, format is KEY=(Action=...)
             # So we need to reconstruct the line.
             
             old_entry = self.conflicts[section][key][idx]
             old_line = old_entry['line']
             
             # Reconstruct: Switch the KEY part.
             # "IK_E=(Action=CastSign)" -> "IK_New=(Action=CastSign)"
             # We assume standard format: KEY=(...)
             
             if "=(" in old_line:
                 rhs = old_line.split("=(", 1)[1]
                 new_line = f"{new_key}=({rhs}"
                 self.conflicts[section][key][idx]['line'] = new_line
                 # Also update source to indicate manual edit?
                 self.conflicts[section][key][idx]['source'] = "Custom Rebind"
                 
                 # Force select this option?
                 if (section, key, idx) in self.vars:
                     self.vars[(section, key, idx)].set(True)
             else:
                 # Fallback? Maybe just user.settings format logic if we allowed it?
                 pass

    def bulk_select(self, mode):
        """
        Bulk Toggle Logic:
        - "all": Enables all checkboxes.
        - "none": Disables all checkboxes.
        - "vanilla": Enables ONLY options with "vanilla" in Source.
        
        Refined for Radio Buttons:
        - Radios cannot have "multiple" selected.
        - "all"/"none" mostly apply to Checkboxes (input.settings).
        - "vanilla" works for Radios by selecting the Vanilla option if present.
        """
        for key_tuple, var in self.vars.items():
            # key_tuple is (section, key, idx) for Checkboxes
            # key_tuple is (section, key) for Radios
            
            # --- CHECKBOXES (input.settings) ---
            if len(key_tuple) == 3:
                section, key, idx = key_tuple
                
                # Retrieve Option Data
                # We need to look up the source in self.conflicts
                try:
                    opt = self.conflicts[section][key][idx]
                    source = opt['source'].lower()
                except: continue

                if mode == "all":
                    var.set(True)
                elif mode == "none":
                    var.set(False)
                elif mode == "vanilla":
                    # True if vanilla, False otherwise
                    is_vanilla = "vanilla" in source or "baseline" in source
                    var.set(is_vanilla)

            # --- RADIO BUTTONS (user.settings) ---
            elif len(key_tuple) == 2:
                section, key = key_tuple
                
                # var is an IntVar holding the INDEX
                # We can't toggle "all" or "none" (must pick one).
                # Only "vanilla" makes sense here.
                
                if mode == "vanilla":
                    options = self.conflicts[section][key]
                    # Find index of vanilla option
                    for i, opt in enumerate(options):
                        src = opt['source'].lower()
                        if "vanilla" in src or "baseline" in src:
                            var.set(i)
                            break
                            
    def on_confirm(self):
        # Compile results back into a clean list
        # We need to return: result[section] = [line, line...]
        
        for section, keys in self.conflicts.items():
            if section not in self.result: self.result[section] = []
            
            for key, options in keys.items():
                if "input.settings" in self.file_type:
                    # Checkboxes
                    for idx, opt in enumerate(options):
                        if self.vars[(section, key, idx)].get():
                            self.result[section].append(opt['line'])
                else:
                    # Radio
                    chosen_idx = self.vars[(section, key)].get()
                    self.result[section].append(options[chosen_idx]['line'])
        
                    self.result[section].append(options[chosen_idx]['line'])
        
        self.cancelled = False
        self.destroy()

# ================= MERGE LOGIC =================
def analyze_conflicts(base_data, mods_data, current_data_on_disk, review_mode=False):
    """
    Builds the conflict map.
    If review_mode=True, it detects ANY diff per key and marks current selection.
    """
    final_map = {}

    def normalize(s): return s.replace(" ", "").replace("\t", "")

    # --- OPTIMIZATION: Build Touched Keys Set ---
    # We only care about keys that are actually modified by at least one Mod.
    # If a key exists in Vanilla but NO mod touches it, it's irrelevant.
    touched_keys = set()
    for m_data in mods_data:
        for section, entries in m_data.items():
            for entry in entries:
                touched_keys.add((section, entry['key']))

    # Helper to merge data
    # We want to track ALL unique options for a key
    def add_to_map(data_dict, check_touched=False):
        for section, entries in data_dict.items():
            for entry in entries:
                k = entry['key']
                
                # FAST FAIL CHECK
                if check_touched and (section, k) not in touched_keys:
                    continue

                if section not in final_map: final_map[section] = {}
                if k not in final_map[section]: final_map[section][k] = []
                
                # Check uniqueness based on line content
                exists = False
                for existing in final_map[section][k]:
                    if normalize(existing['line']) == normalize(entry['line']): 
                        exists = True
                
                if not exists:
                    final_map[section][k].append(entry)

    # 1. Process Base/Vanilla (Filtered)
    add_to_map(base_data, check_touched=True)
    
    # 2. Process Mods (All)
    for m in mods_data: add_to_map(m, check_touched=False)

    # Now filter into 'conflicts' (or 'changes' if review_mode)
    conflicts = {}
    resolved_lines = {} # For auto-resolved stuff
    auto_resolved_count = 0

    for section, keys in final_map.items():
        if section not in resolved_lines: resolved_lines[section] = []
        if section not in conflicts: conflicts[section] = {}
        
        for k, entries in keys.items():
            # STATE DETECTION: which entry is currently active?
            # For input.settings, there might be MULTIPLE active lines for the same key.
            # We need to collect ALL active lines for this key from current_data_on_disk.
            active_lines_normalized = set()
            if section in current_data_on_disk:
                for item in current_data_on_disk[section]:
                    if item['key'] == k:
                        active_lines_normalized.add(normalize(item['line']))
            
            # Mark selected
            found_active_count = 0
            for entry in entries:
                if normalize(entry['line']) in active_lines_normalized:
                    entry['selected'] = True
                    found_active_count += 1
                else:
                    entry['selected'] = False

            # If we have a current value that matches NOTHING, add it as a custom option.
            # But which one? If there are multiple active lines that don't match known entries, we potentially have multiple custom values.
            # For simplicity, if we found NO matches but we HAVE active lines, adds all unmatched active lines.
            
            # Re-scan active lines to find ones we didn't match
            known_lines_normalized = set(normalize(e['line']) for e in entries)
            
            for line_norm in active_lines_normalized:
                if line_norm not in known_lines_normalized:
                    # Retrieve original line text? We only stored normalized in the set.
                    # Need to find the original line again.
                    raw_line = ""
                    for item in current_data_on_disk[section]:
                        if item['key'] == k and normalize(item['line']) == line_norm:
                            raw_line = item['line']
                            break
                    
                    custom_entry = {
                        'line': raw_line,
                        'key': k,
                        'source': 'Current Custom Value',
                        'selected': True
                    }
                    entries.append(custom_entry)
            
            # --- NOISE FILTERING ---
            # Hide keys that are purely Baseline/Vanilla or purely Current File (unless custom)
            # Relevance Rule: Must have at least one entry from a Mod OR be a "Current Custom Value"
            
            is_relevant = False
            for e in entries:
                src = e['source']
                if src == "Current Custom Value":
                    is_relevant = True
                    break
                if src not in ["Baseline/Vanilla", "Current File"]:
                    # It's a Mod or something else
                    is_relevant = True
                    # Don't break yet, we might need to count sources later
            
            if not is_relevant:
                # Treat as resolved (keep default/current) and SKIP conflict detection
                is_conflict = False
            else:
                # --- DECISION LOGIC ---
                is_conflict = False
                
                if review_mode:
                    # REVIEW MODE: Show everything that is relevant (Mod or Custom involved)
                    # If we have >1 entry (e.g. Base + Mod, or Mod A + Mod B), show it.
                    if len(entries) > 1:
                        is_conflict = True
                else:
                    # MERGE MODE: Silent Auto-Merge unless True Conflict
                    # Filter: Exclude Base/Current/Custom. Look ONLY at Mod sources.
                    mod_sources = set()
                    for e in entries:
                         if e['source'] not in ["Baseline/Vanilla", "Current File", "Current Custom Value"]:
                             mod_sources.add(e['source'])
                    
                    if len(mod_sources) > 1:
                        # >1 Unique Mod Source involved -> CONFLICT
                        is_conflict = True
                    elif len(mod_sources) == 1:
                         # Exactly 1 Mod Source -> AUTO RESOLVE
                         is_conflict = False
                         auto_resolved_count += 1
                    else:
                         # 0 Mod Sources (Only Baseline/Current/Custom?)
                         # Should be handled by Relevance check, but if here:
                         is_conflict = False
                         # Not strictly an "auto resolve" of a mod, just keeping existing.
            
            if is_conflict:
                conflicts[section][k] = entries
            else:
                 # Auto-resolve: Keep ALL valid entries
                 for e in entries:
                     resolved_lines[section].append(e['line'])

    return conflicts, resolved_lines, auto_resolved_count


def apply_merge(resolved_lines, target_full_path, app_instance):
    output_lines = []
    for section in sorted(resolved_lines.keys()):
        output_lines.append(f"{section}\n")
        for line in sorted(resolved_lines[section]):
            output_lines.append(f"{line}\n")
        output_lines.append("\n")

    with open(target_full_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    
    app_instance.log(f"Saved {os.path.basename(target_full_path)}.")
    return True

def merge_smart(target_full_path, fragment_files, app_instance, review_mode=False):
    file_name = os.path.basename(target_full_path)
    app_instance.log(f"{'Reviewing' if review_mode else 'Processing'} {file_name}...")
    
    # 1. Load Base
    base_data = {}
    if os.path.exists(target_full_path):
        # For 'Base', we actually want vanilla or empty.
        # But here 'target_full_path' IS the current file.
        # We need to distinguish "Baseline" vs "Current".
        # Ideally, we should ignore current file for Baseline, and try to find a .base backup?
        # Or just treat empty as baseline.
        # EXISTING LOGIC: Used parse_file_to_dict(target, "Current File"). 
        # But for diffing, we want "Original" vs "Mods".
        pass 

    # For Analyze function:
    # Base Data: Should be the .base file if exists (Pure Vanilla/Previous Snapshot).
    # Current Data: The actual file on disk right now (target_full_path).
    
    base_path = target_full_path + ".base"
    if os.path.exists(base_path):
        base_data = parse_file_to_dict(base_path, "Baseline/Vanilla")
    else:
        # If no baseline, treat keys as new? Or use current as base?
        # If we use current as base, we can't detect diffs.
        base_data = {} 

    current_data = {}
    if os.path.exists(target_full_path):
        current_data = parse_file_to_dict(target_full_path, "Current File")

    # 2. Load Fragments
    mods_data = []
    for fpath in fragment_files:
        mod_name = os.path.basename(os.path.dirname(fpath))
        if not mod_name or mod_name == ".": mod_name = os.path.basename(fpath)
        mods_data.append(parse_file_to_dict(fpath, mod_name))

    # 3. Analyze
    conflicts, resolved_lines, auto_resolved_high_level = analyze_conflicts(base_data, mods_data, current_data, review_mode)

    # 4. Launch UI if needed
    has_conflicts = any(len(k) > 0 for k in conflicts.values())
    conflict_count = sum(len(k) for k in conflicts.values())
    
    if has_conflicts:
        app_instance.log(f"{'Changes' if review_mode else 'Conflicts'} found in {file_name}. Opening Manager...")
        
        done_event = threading.Event()
        user_selections = {}
        flags = {'cancelled': False}

        def open_window():
            win = ConflictWindow(app_instance.root, file_name, conflicts)
            app_instance.root.wait_window(win)
            if win.cancelled:
                flags['cancelled'] = True
            else:
                user_selections.update(win.result)
            done_event.set()

        app_instance.root.after(0, open_window)
        done_event.wait()
        
        if flags['cancelled']:
            app_instance.log(f"Cancelled {file_name}.")
            return False

        for section, lines in user_selections.items():
            if section not in resolved_lines: resolved_lines[section] = []
            resolved_lines[section].extend(lines)
            
        app_instance.log(f"Merge Complete. Auto-resolved {auto_resolved_high_level} settings. User resolved {conflict_count} conflicts.")
    
    elif review_mode:
        app_instance.log("No differences found to review.")
        return True # Nothing to save, but success
    else:
        app_instance.log(f"Merge Complete. Auto-resolved {auto_resolved_high_level} settings. No conflicts detected.")

    return apply_merge(resolved_lines, target_full_path, app_instance)


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

# ================= GUI APP =================
class MergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION}")
        # self.root.geometry("600x750") # Removed fixed geometry to use center
        self.root.minsize(600, 1000) # Increased min height (again) for full 200px banner
        # Lock Width, Allow Height Resize
        self.root.resizable(False, True) 
        self.root.configure(bg="#202020")
        
        # Center main window
        center_on_screen(self.root, 600, 1000)
        
        apply_dark_title_bar(self.root)
        apply_window_icon(self.root)
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- DARK THEME CONFIG ---
        BG_MAIN = "#202020"
        BG_CONTENT = "#2b2b2b"
        TXT_HEADER = "#ffffff"
        TXT_BODY = "#e0e0e0"
        BTN_BG = "#333333"
        BTN_HOVER = "#444444"
        BTN_ACTIVE = "#1a1a1a"
        ENTRY_BG = "#1f1f1f"
        ENTRY_BORDER = "#3a3a3a"

        style.configure(".", background=BG_MAIN, foreground=TXT_BODY, font=("Segoe UI", 10))
        style.configure("TLabel", background=BG_MAIN, foreground=TXT_BODY)
        style.configure("TFrame", background=BG_MAIN)
        
        # Labelframe styles
        style.configure("TLabelframe", background=BG_MAIN, bordercolor=BTN_BG)
        style.configure("TLabelframe.Label", background=BG_MAIN, foreground=TXT_HEADER, font=("Segoe UI", 10, "bold"))

        # Button styles
        style.configure("TButton", 
                        background=BTN_BG, 
                        foreground="#ffffff", 
                        borderwidth=1, 
                        focuscolor="none",
                        font=("Segoe UI", 10))
        
        style.map("TButton",
                  background=[('active', BTN_HOVER), ('pressed', BTN_ACTIVE)],
                  foreground=[('disabled', '#666666')])

        # Special "Primary" Button Style (Standard Border, just identifying name)
        style.configure("Primary.TButton", 
                        background=BTN_BG, 
                        foreground="#ffffff",
                        borderwidth=1,
                        bordercolor=BTN_BG, # Standard border
                        lightcolor="#ffffff",
                        darkcolor="#ffffff",
                        focuscolor="none")
        style.map("Primary.TButton",
                  background=[('active', BTN_HOVER), ('pressed', BTN_ACTIVE)])
                  
        # Separator
        style.configure("Horizontal.TSeparator", background="#444444")

        # Scrollbar
        # Scrollbar (Refined Dark Style)
        style.configure("Vertical.TScrollbar", 
                        background="#333333", 
                        troughcolor="#202020", 
                        bordercolor="#333333", 
                        arrowcolor="#ffffff",
                        lightcolor="#333333",
                        darkcolor="#333333")
        
        style.map("Vertical.TScrollbar",
                  background=[('active', '#444444'), ('pressed', '#555555')],
                  arrowcolor=[('active', '#ffffff'), ('pressed', '#ffffff')])

        # Custom Image-Based Checkboxes/Radios for strict control
        self.assets = create_pixel_assets() # Keep Ref! (chk_off, chk_on, rad_off, rad_on)
        
        # Define Elements
        style.element_create("DarkCheck.Indicator", "image", self.assets[0],
                             ("selected", self.assets[1]),
                             ("active", self.assets[0])) # Active can be lighter if needed
                             
        style.element_create("DarkRadio.Indicator", "image", self.assets[2],
                             ("selected", self.assets[3]),
                             ("active", self.assets[2]))

        # Define Styles
        style.layout("Dark.TCheckbutton", 
                     [('Checkbutton.padding', {'sticky': 'nswe', 'children': 
                        [('DarkCheck.Indicator', {'side': 'left', 'sticky': ''}), 
                         ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': 
                            [('Checkbutton.label', {'sticky': 'nswe'})]})]})])
                            
        style.configure("Dark.TCheckbutton", background=BG_MAIN, foreground=TXT_BODY, focuscolor=BG_MAIN)
        style.map("Dark.TCheckbutton", background=[('active', BG_MAIN)])

        style.layout("Dark.TRadiobutton", 
                     [('Radiobutton.padding', {'sticky': 'nswe', 'children': 
                        [('DarkRadio.Indicator', {'side': 'left', 'sticky': ''}), 
                         ('Radiobutton.focus', {'side': 'left', 'sticky': 'w', 'children': 
                            [('Radiobutton.label', {'sticky': 'nswe'})]})]})])

        style.configure("Dark.TRadiobutton", background=BG_MAIN, foreground=TXT_BODY, focuscolor=BG_MAIN)
        style.map("Dark.TRadiobutton", background=[('active', BG_MAIN)])

        # --- SEAMLESS CHECKBOX/RADIO (for Lists with #2b2b2b background) ---
        style.layout("Seamless.TCheckbutton", 
                     [('Checkbutton.padding', {'sticky': 'nswe', 'children': 
                        [('DarkCheck.Indicator', {'side': 'left', 'sticky': ''}), 
                         ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': 
                            [('Checkbutton.label', {'sticky': 'nswe'})]})]})])
                            
        style.configure("Seamless.TCheckbutton", 
                        background="#2b2b2b", 
                        foreground=TXT_BODY, 
                        focuscolor="#2b2b2b",
                        indicatorbackground="#2b2b2b",
                        indicatorforeground="#ffffff")
                        
        style.map("Seamless.TCheckbutton", 
                  background=[('active', "#2b2b2b")],
                  indicatorcolor=[('selected', '#ffffff')])

        style.layout("Seamless.TRadiobutton", 
                     [('Radiobutton.padding', {'sticky': 'nswe', 'children': 
                        [('DarkRadio.Indicator', {'side': 'left', 'sticky': ''}), 
                         ('Radiobutton.focus', {'side': 'left', 'sticky': 'w', 'children': 
                            [('Radiobutton.label', {'sticky': 'nswe'})]})]})])

        style.configure("Seamless.TRadiobutton", 
                        background="#2b2b2b", 
                        foreground=TXT_BODY, 
                        focuscolor="#2b2b2b",
                        indicatorbackground="#2b2b2b",
                        indicatorforeground="#ffffff")
                        
        style.map("Seamless.TRadiobutton", 
                  background=[('active', "#2b2b2b")],
                  indicatorcolor=[('selected', '#ffffff')])

        # --- HEADER / HELP ---

        # --- HEADER / BANNER ---
        self.banner_img = self.load_banner() # Keep reference
        
        if self.banner_img:
            # Banner Mode
            # Background matches main window to avoid "black lines" if image has transparency or rounding
            banner_lbl = ttk.Label(root, image=self.banner_img, background="#202020")
            banner_lbl.pack(side="top", fill="x", padx=0, pady=0)
        else:
            # Fallback Text Title
            title_frame = ttk.Frame(root, padding="10 5 10 5")
            title_frame.pack(fill="x")
            ttk.Label(title_frame, text="Witcher 3 Settings Merger", font=("Segoe UI", 14, "bold"), foreground=TXT_HEADER).pack(side="left")

        # --- SUB-HEADER (Help Button Centered) ---
        sub_frame = ttk.Frame(root, padding="10 5 10 0")
        sub_frame.pack(fill="x")
        
        # Help Button (Centered)
        # Using pack with expand=True centers it if it's the only child
        ttk.Button(sub_frame, text="How to Use", command=self.show_help, width=12).pack(expand=True)


        # --- PATH SELECTION ---
        path_frame = ttk.LabelFrame(root, text="Directories", padding="10")
        path_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(path_frame, text="Game Directory:").grid(row=0, column=0, sticky="w")
        
        self.entry_game = tk.Entry(path_frame, relief="flat", bg="#1f1f1f", fg="#ffffff", insertbackground="white")
        self.entry_game.grid(row=1, column=0, sticky="ew", padx=(0, 5), ipady=3)
        self.entry_game.bind("<KeyRelease>", self.check_paths_live) 
        
        ttk.Button(path_frame, text="Browse", command=self.browse_game).grid(row=1, column=1, padx=2)
        ttk.Button(path_frame, text="Open", command=lambda: self.open_dir(self.entry_game)).grid(row=1, column=2, padx=2)

        ttk.Label(path_frame, text="Documents/The Witcher 3:").grid(row=2, column=0, sticky="w", pady=(10,0))
        
        self.entry_docs = tk.Entry(path_frame, relief="flat", bg="#1f1f1f", fg="#ffffff", insertbackground="white")
        self.entry_docs.grid(row=3, column=0, sticky="ew", padx=(0, 5), ipady=3)
        self.entry_docs.bind("<KeyRelease>", self.check_paths_live)
        
        ttk.Button(path_frame, text="Browse", command=self.browse_docs).grid(row=3, column=1, padx=2)
        ttk.Button(path_frame, text="Open", command=lambda: self.open_dir(self.entry_docs)).grid(row=3, column=2, padx=2)
        path_frame.columnconfigure(0, weight=1)

        # --- ACTIONS ---
        btn_frame = ttk.LabelFrame(root, text="Actions", padding="10")
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="Save Baseline", command=self.save_baseline_ui).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Load Baseline", command=lambda: self.run_thread("Load")).pack(fill="x", pady=2)
        ttk.Separator(btn_frame, orient='horizontal').pack(fill='x', pady=5)
        ttk.Button(btn_frame, text="Merge Settings", command=lambda: self.run_thread("Merge"), style="Primary.TButton").pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Manage Settings", command=lambda: self.run_thread("Review")).pack(fill="x", pady=2)

        # --- OPTIONS ---
        opt_frame = ttk.Frame(root)
        opt_frame.pack(fill="x", padx=15, pady=0)
        self.log_to_file_var = tk.BooleanVar(value=False)
        # Added spaces as requested
        ttk.Checkbutton(opt_frame, text="  Save Output to Log File", variable=self.log_to_file_var, style="Dark.TCheckbutton").pack(side="left")

        # --- LOGGING ---
        log_frame = ttk.LabelFrame(root, text="Output Log", padding="5")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Custom ScrolledText implementation using Text + ttk.Scrollbar for theming support
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill="both", expand=True)

        self.log_area = tk.Text(log_container, state='disabled', height=10, bg="#101010", fg="#cccccc", insertbackground="white", relief="flat", padx=5, pady=5)
        self.log_area.pack(side="left", fill="both", expand=True)
        
        log_scroll = ttk.Scrollbar(log_container, orient="vertical", command=self.log_area.yview)
        log_scroll.pack(side="right", fill="y")
        
        self.log_area.configure(yscrollcommand=log_scroll.set)

        # --- FOOTER ---
        # Padding: Left, Top, Right, Bottom
        # User requested equal space above and below the button relative to window/log.
        # "10 20 10 20" gives 20px above and 20px below within the frame.
        footer_frame = ttk.Frame(root, padding="10 20 10 20")
        footer_frame.pack(fill="x", side="bottom") # Ensure it stays at bottom
        
        # Reset Button (Centers by default with expand=True)
        ttk.Button(footer_frame, text="Settings Files Reset", command=self.factory_reset_ui).pack(expand=True)
        
        # Version Number (Bottom Left)
        # We use place() to position it absolutely within the footer frame, 
        # avoiding interference with the centered pack layout of the button.
        v_short = VERSION.split(' ')[0]
        lbl_ver = ttk.Label(footer_frame, text=f"v{v_short}", font=("Segoe UI", 8), foreground="#555555")
        # Anchor SW (South West) -> Bottom Left. 
        # relx=0 (Left), rely=1.0 (Bottom). 
        # x=0, y=0 (No offset, frame padding handles edges? No, frame padding is internal.)
        # Frame has padding="10...". 
        # Actually place is relative to the widget's border area.
        lbl_ver.place(relx=0.0, rely=1.0, anchor="sw", x=0, y=0)

        # Initial Auto-Detect
        self.log("Initializing...")
        self.root.after(100, self.auto_detect_paths)
        
        # Apply dark title bar (needs window to be mapped or created)
        self.root.after(10, lambda: apply_dark_title_bar(self.root))

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
        game_path = self.entry_game.get()
        if game_path and os.path.exists(game_path):
            self.entry_game.config(bg="#1f1f1f", fg="#ffffff")
        else:
            self.entry_game.config(bg="#500000", fg="#ffffff") # Dark Red for error

        docs_path = self.entry_docs.get()
        if docs_path and os.path.exists(docs_path):
            self.entry_docs.config(bg="#1f1f1f", fg="#ffffff")
        else:
            self.entry_docs.config(bg="#500000", fg="#ffffff")

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

    def open_dir(self, entry_widget):
        path = entry_widget.get()
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                self.log(f"Error opening folder: {e}")
        else:
             DarkDialog(self.root, "Invalid Path", "Directory does not exist.", buttons=["OK"], icon="warning")

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
            self.root.after(0, self.check_paths_live)

        raw_docs = get_true_documents_path()
        docs = os.path.join(raw_docs, "The Witcher 3")
        if os.path.exists(docs):
            self.root.after(0, lambda: self._update_entry(self.entry_docs, docs))
            self.log(f"Found ConfigFolder: {docs}")
        else:
             self.log("Could not find Configs automatically.")
             self.root.after(0, self.check_paths_live)

    def _update_entry(self, entry_widget, text):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, text)
        self.check_paths_live()

    def save_baseline_ui(self):
        docs_path = self.entry_docs.get()
        if not os.path.exists(docs_path):
            DarkDialog(self.root, "Error", "Documents path invalid.", buttons=["OK"], icon="error")
            return

        base_exists = os.path.exists(os.path.join(docs_path, "input.settings.base"))
        if base_exists:
            dlg = DarkDialog(self.root, "Overwrite Baseline?", 
                                          "A Baseline backup already exists.\n\nDo you want to overwrite it with your CURRENT settings?",
                                          buttons=["Yes", "No"], icon="warning")
            if dlg.result != "Yes": return

        self.run_thread("Save")

    def factory_reset_ui(self):
        dlg = DarkDialog(self.root, "Factory Reset - WARNING", 
                                      "Are you sure? This will delete your settings files:\n"
                                      "- input.settings (+.base)\n"
                                      "- user.settings (+.base)\n"
                                      "- dx12user.settings (+.base)\n\n"
                                      "You will lose ALL custom configurations.\nProceed?",
                                      buttons=["Yes", "No"], icon="warning")
        if dlg.result != "Yes": return

        docs_path = self.entry_docs.get()
        if not os.path.exists(docs_path):
             DarkDialog(self.root, "Error", "Documents path invalid.", buttons=["OK"], icon="error")
             return

        targets = ["input.settings", "user.settings", "dx12user.settings"]
        deleted_count = 0
        
        for t in targets:
            full_path = os.path.join(docs_path, t)
            base_path = full_path + ".base"
            
            if os.path.exists(full_path):
                try: os.remove(full_path); deleted_count += 1
                except: pass
            if os.path.exists(base_path):
                try: os.remove(base_path); deleted_count += 1
                except: pass
        
        self.log(f"Factory Reset: Deleted {deleted_count} files.")
        
        dlg_launch = DarkDialog(self.root, "Reset Complete", 
                                     "Files deleted. You must launch the game to regenerate them.\n\n"
                                     "Launch The Witcher 3 now?",
                                     buttons=["Yes", "No"], icon="info")
        if dlg_launch.result == "Yes":
            game_root = self.entry_game.get()
            # Try DX12 path first as requested, then DX11, then fallback
            exe_candidates = [
                os.path.join(game_root, "bin", "x64_dx12", "witcher3.exe"),
                os.path.join(game_root, "bin", "x64", "witcher3.exe")
            ]
            
            launched = False
            for exe in exe_candidates:
                if os.path.exists(exe):
                    try:
                        self.log(f"Launching: {exe}")
                        # Use subprocess to set the CWD (Working Directory) correctly
                        # Games often fail if CWD is not their own folder
                        subprocess.Popen([exe], cwd=os.path.dirname(exe))
                        launched = True
                        break
                    except Exception as e:
                        self.log(f"Failed to launch {exe}: {e}")
            
            if not launched:
                 DarkDialog(self.root, "Launch Failed", "Could not find witcher3.exe in standard paths.\nPlease launch the game manually.", buttons=["OK"], icon="error")


    def run_thread(self, mode):
        self.check_paths_live() 
        if self.entry_game['bg'] == "#500000" or self.entry_docs['bg'] == "#500000":
            DarkDialog(self.root, "Invalid Paths", "Please fix the red (invalid) directory paths before proceeding.", buttons=["OK"], icon="warning")
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
            # Smart Merge Logic
            s1 = merge_smart(os.path.join(docs_path, "input.settings"), fragments['input'], self)
            s2 = merge_smart(os.path.join(docs_path, "user.settings"), fragments['user'], self)
            s3 = merge_smart(os.path.join(docs_path, "dx12user.settings"), fragments['user'], self)
            
            if not (s1 and s2 and s3):
                self.log("--- Operation Cancelled ---")
                return
        
        elif mode == "Review":
            fragments = scan_game_for_fragments(game_path, self.log)
            # Review Mode = True
            s1 = merge_smart(os.path.join(docs_path, "input.settings"), fragments['input'], self, review_mode=True)
            s2 = merge_smart(os.path.join(docs_path, "user.settings"), fragments['user'], self, review_mode=True)
            s3 = merge_smart(os.path.join(docs_path, "dx12user.settings"), fragments['user'], self, review_mode=True)

            if not (s1 and s2 and s3):
                self.log("--- Review Cancelled ---")
                return

        self.log("--- Operation Complete ---")

    # --- BANNER LOGIC ---
    def load_banner(self):
        """
        Loads 'banner.png' (or jpg), resizes to 600px width,
        and CENTER CROPS to 120px height.
        Returns ImageTk.PhotoImage or None.
        """
        if not HAS_PIL: return None
        
        candidates = ["banner.png", "banner.jpg"]
        target = None
        for c in candidates:
            # Check resource path first (bundled), then local
            # Actually, for external files users drop in, we want local dir.
            # But if we BUNDLE a default banner, we want resource_path.
            # The User Request specifically asked to wrap it in resource_path.
            # "Change Image.open("banner.png") to Image.open(resource_path("banner.png"))"
            
            # Let's check if the resource path exists.
            path = resource_path(c)
            if os.path.exists(path):
                target = path
                break
            
            # Fallback to local cwd if not found in bundle (for user provided)
            if os.path.exists(c):
                target = c
                break
        
        if not target: return None
        
        try:
            img = Image.open(target)
            
            # 1. Resize Width to 600 (Maintain Aspect Ratio)
            w_percent = (600 / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            
            # High-quality resize
            img = img.resize((600, h_size), Image.Resampling.LANCZOS)
            
            # 2. No Crop - Full Image as requested
            # User requested "fit the whole image"
            
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Banner Error: {e}")
            return None
        
    def show_help(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("How to Use")
        # Removed fixed geometry 
        # help_win.geometry("500x600")
        help_win.configure(bg="#202020")
        apply_dark_title_bar(help_win)
        apply_window_icon(help_win)
        
        help_text = """WITCHER 3 SETTINGS MERGER - USER MANUAL

1. PURPOSE
Tired of manually adding lines of code from mods to settings files? The Witcher 3 Settings Merger is a tool designed to automate resolving setting overlaps and conflicts.

With multiple mods trying to add new keybinds or settings, it can be tedious to micromanage the game's configuration files (input.settings, user.settings); often becoming cluttered with actions from uninstalled mods, having undesirably double-bound actions, or even just succumbing to human error. This tool solves that by intelligently merging mod configurations into your existing files while giving you full control over possible conflicts.


2. CORE FUNCTIONS & FEATURES
* Baseline Backup: Creates a pristine snapshot (.base) of your settings. This allows you to experiment freely and always revert to a clean state.
* Smart Auto-Merge: Automatically detects and merges non-conflicting settings from all your installed mods. If only one mod changes a specific key, it is accepted instantly without bothering you.
* Conflict Manager: A powerful visual interface that appears ONLY when real conflicts exist (e.g., two mods trying to bind IK_E to different actions).
* Rebind on the Fly: Would you prefer a mod action be activated by a different key? Use the built-in Remap Input feature to assign it to any valid controller, mouse, or keyboard input instantly.
* Ease of Use: Auto-detects directories and includes a "Factory Reset" to delete existing settings files and re-launch the game to regenerate them if you need a fresh start.


3. WORKFLOW GUIDE

Step 1: Preparation
1. Ensure you have run the game at least once to generate your standard config files.
2. Install your mods as usual (using a mod manager or manually).
3. Open this tool. It should auto-detect your Game Directory and Documents folder. If not, click "Browse" to locate them.

Step 2: Establish a Baseline (Recommended)
Before merging, click "Save Baseline".
* This creates a backup of your current input.settings, user.settings, and dx12user.settings as .base files.
* Why? Future merges will use this baseline to detect "clean" changes, preventing your file from growing endlessly with duplicate entries from previous merges.

Step 3: Merge
Click "Merge Settings". The tool will:
1. Deep scan your game folder for *.settings, *.txt, or *.ini files that include either 'input' or 'user'.
2. Compare them against your Baseline and Current files.
3. Auto-Resolve: Any unique changes are applied immediately.
4. Conflict Detected?: If conflicting mod changes are found, the Conflict Manager window opens.

Step 4: Review & Resolve (If prompted)
In the Conflict Manager window:
* Select: Check the box for the version of the setting you want to keep.
* Source: Shows which mod provided the setting (e.g., [Mod_A]).
* Action: Shows what the key actually does (e.g., CastSign).
* Remap: Click the Pencil button to change the keybind entirely (e.g., change IK_E to IK_F).
* Click "Save & Continue" when finished.

Step 5: Manage & Adjust (Ongoing)
Once your initial merge is done, use the "Manage Settings" button to tweak your setup at any time.
* Difference from Merge: Unlike "Merge Settings" which hides resolved items to focus on errors, "Manage Settings" shows you everything that your mods are touching.
* Custom Layouts: Use this mode to fine-tune your controls. Want to see every key Mod A is using? Open Manage Settings, review the entries, and use the Remap tool to move them to your preferred keys. The tool remembers your choices, ensuring your custom input layout persists even after game updates.


4. DISCLAIMER
This software is made available under the GNU General Public License v3.0.

* No Warranty: This software is provided "as is". The author is not responsible if your Roach ends up on a roof (though that's likely the game's fault, not ours).
"""
        container = ttk.Frame(help_win, padding=10)
        container.pack(fill="both", expand=True)

        text_widget = tk.Text(container, wrap=tk.WORD, bg="#101010", fg="#cccccc", insertbackground="white", relief="flat", padx=10, pady=10)
        text_widget.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        scroll.pack(side="right", fill="y")
        text_widget.configure(yscrollcommand=scroll.set)

        text_widget.insert(tk.END, help_text)
        text_widget.configure(state='disabled')
        
        # Position
        help_win.update_idletasks() # Calc size
        setup_popup_geometry(help_win, self.root, mode="secondary")

if __name__ == "__main__":
    root = tk.Tk()
    app = MergerApp(root)
    root.mainloop()