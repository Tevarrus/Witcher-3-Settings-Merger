# Witcher 3 Settings Merger (Beta v0.9.0)

Jan 29, 2026 - Note: I'm currently trying to navigate the false positives of the file being misidentified as malware. I'm going to try releasing an unpackaged OneDir folder compile via Nuitka as that seems to greatly reduce the VirusTotal flags.

## Purpose
Tired of manually copy-pasting lines into `input.settings`? With multiple mods trying to add new keybinds or settings, it can be tedious to micromanage the game's configuration files. These files often become cluttered with actions from uninstalled mods, suffer from undesirable double-bound actions, or succumb to simple human error.

**Witcher 3 Settings Merger** automates the process of adding custom inputs, user settings, and graphics options from your installed mods into *The Witcher 3*'s settings files and gives you a GUI to manage your choices. It is designed to be a companion to **Script Merger** and **Filelist Updater** to fill the final automation gap. 

## Core Functions & Features
* **Baseline Backup:** Creates a pristine snapshot (`.base`) of your settings. This allows you to experiment freely and always revert to a clean state.
* **Auto-Detection:** Automatically attempts to find your Game Directory and Documents folder (checks Registry, Steam Library, and scans drives).
* **Smart Auto-Merge:** Automatically detects and merges non-conflicting settings from all your installed mods. If only one mod changes a specific input, it is integrated automatically.
* **Conflict Manager:** A powerful visual interface that appears **ONLY** when mod conflicts exist (e.g., two mods trying to bind `IK_E` to different actions or overlap vanilla).
* **Rebind on the Fly:** Prefer a different binding? Use the built-in **Remap Input** feature to assign it to any valid controller, mouse, or keyboard input.
* **Ease of Use:** Auto-detects directories and includes a **Factory Reset** to delete existing settings files and re-launch the game to regenerate them if you need a fresh start.
* **Next-Gen Ready:** Updates `input.settings`, `user.settings`, and `dx12user.settings` simultaneously.
* **Vortex Support:** Fully supports Vortex symlinks and hardlinks.

## Workflow Guide

### Step 1: Preparation
1.  Ensure you have run the game at least once to generate your standard config files.
2.  Install your mods as usual (using a mod manager or manually).
3.  Open this tool. It should auto-detect your **Game Directory** and **Documents** folder. If not, click **"Browse"** to locate them.

### Step 2: Establish a Baseline (Recommended)
Before merging, click **"Save Baseline"**.
* This creates a backup of your current `input.settings`, `user.settings`, and `dx12user.settings` as `.base` files.
* **Why?** Future merges will use this baseline to detect "clean" changes, preventing your file from growing endlessly with duplicate entries from previous merges.

### Step 3: Merge
Click **"Merge Settings"**. The tool will:
1.  Deep scan your game folder for `*.settings`, `*.txt`, or `*.ini` files that include either 'input' or 'user'in the filename.
2.  Compare them against your Baseline and Current files.
3.  **Auto-Resolve:** Any unique changes are applied immediately.
4.  **Conflict Detected?:** If conflicting mod changes are found, the Conflict Manager window opens.

### Step 4: Review & Resolve (If prompted)
In the Conflict Manager window:
* **Select:** Check the box for the version of the setting you want to keep.
* **Source:** Shows which mod provided the setting (e.g., `[Mod_A]`).
* **Action:** Shows what the key actually does (e.g., `CastSign`).
* **Remap:** Click the **?** button to change the keybind entirely (e.g., change `IK_E` to `IK_F`).
* Click **"Save & Continue"** when finished.

### Step 5: Manage & Adjust (Ongoing)
Once your initial merge is done, use the **"Manage Settings"** button to tweak your setup at any time.
* **Difference from Merge:** Unlike "Merge Settings" which hides resolved items to focus on errors, "Manage Settings" shows you **everything** that your mods are touching.
* **Custom Layouts:** Use this mode to fine-tune your controls. Want to see every key Mod A is using? Open Manage Settings, review the entries, and use the Remap tool to move them to your preferred keys. The tool remembers your choices, ensuring your custom input layout persists even after game updates.

### Alternate Version Note
I've included an earlier non-GUI command line version just on Github for those that want a run and done solution like **Filelist Updater**; it will try to auto-detect your directories, auto-search for settings files, and automatically merge them if they're not already in the main files. It is only additive and won't remove any entries if you remove mods but you can always just reset to baseline yourself by deleting those files and running Settings Merge fresh or keeping and restoring your own backups. If it fails, you'll have to resort to the GUI version to manually add directory paths and manage choices.

## Compatibility

* **Game Version:** Should be Next-Gen (4.0+) & Classic (1.32) agnostic.
* **Mod Manager:** Works with **Vortex**, **MO2** (if using VFS root), and manual installs. Anything that puts the settings fragments in the *Witcher 3* game directory.
* **Game Store:** Purpose built to search Steam libraries but should also work with GOG, Epic, etc.

## Disclaimer
This tool is currently in **Beta (v0.9.0)**. It was developed hastily in an afternoon for my own personal use, has worked for me, but **YMMV**. It is provided as-is in the hope of saving others some tedium. This is my only contribution to the Nexus community and am otherwise not actively engaged in modding and am unlikely to have time to follow up or provide support. Though if you have any killer ideas for features that I would want to use and I happen to read them in the comments I might add them.

## Note to Mod Creators and Meticulous Modlist Curators
The program will look for any files with `user` or `input` combined with the phrase `.settings`, `.txt`, or `.ini` so if you format your settings files this way it should find them. It will then check their content for relevant headings to confirm before importing.

The only issue I found in my own list was with *Brew With a View*, the user settings files for which were formatted in such a way that Vortex didn't want to deploy them until I removed the `.txt` suffix and then they deployed successfully (for some reason) and were then able to be found by **Settings Merger**. I assume this may happen with other mods so if you encounter import issues you should search `.settings` in your mod staging folder and ensure everything is deploying somewhere in the *Witcher 3* game folder with the above keywords in some orientation, then Settings Merger should find them and do its job.

## License & Permissions

**Copyright © 2026 Craeven/Tevarrus (handles). All Rights Reserved.**

**Distribution:** You are not allowed to upload this file to other sites without the author's express permission.

**Modification:** You are not allowed to modify files, improve them, or use assets from them without the author's express permission.

**Commercial Use:** You are not allowed to use this file or its source code for any commercial purposes.
