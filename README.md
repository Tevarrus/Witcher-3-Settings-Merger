# Witcher 3 Settings Merger (Beta v0.9.0)

Tired of manually copy-pasting lines into `input.settings`? This simple tool automates the process of adding custom inputs, user settings, and graphics options from your installed mods into *The Witcher 3*'s settings files. It is designed to be a companion to **Script Merger** and **Filelist Updater** to fill the final automation gap. Add it as a tool in **Vortex** and run whenever your modlist changes. That's it!

## Key Features

* **Auto-Detection:** Automatically attempts to find your Game Directory and Documents folder (checks Registry, Steam Library, and scans drives).
* **Intelligent Merging:** Scans your mod folder for input and user settings files and merges them into your main configuration.
* **Vortex Support:** Fully supports Vortex symlinks and hardlinks.
* **Next-Gen Ready:** Updates `input.settings`, `user.settings`, and `dx12user.settings` simultaneously.

## Program Functions

Unlike simple copy-paste scripts which bloat your file with duplicates each time its run or leaves old entries from uninstalled mods, this tool offers a **Baseline** feature to keep your configs clean.

* **Save Baseline:** Takes a snapshot of your current files as backup; either a clean install state or a stable point for experimentation.
* **Load Baseline:** Reverts your settings files to their saved state.
* **Merge:** Searches for and adds your currently installed mods' settings to the respective main files.

## How to Use

1.  **Download** and run the `.exe`, set to be portable, no installation required.
2.  **Ensure** the detected "Game" and "Documents" paths are correct.
3.  Click **Save Baseline** if running for the first time.
4.  Click **Merge Settings** to initiate the program's search and compile functions.
5.  Done.

### Alternate Version Note
I've included an earlier non-GUI command line version for those that want a run and done solution like **Filelist Updater**; it will try to auto-detect your directories, auto-search for settings files, and automatically merge them if they're not already in the main files. It is only additive and won't remove any entries if you remove mods but you can always just reset to baseline yourself by deleting those files and running Settings Merge fresh or keeping and restoring your own backups. If it fails, you'll have to resort to the GUI version to manually add directory paths.

## Compatibility

* **Game Version:** Should be Next-Gen (4.0+) & Classic (1.32) agnostic.
* **Mod Manager:** Works with **Vortex**, **MO2** (if using VFS root), and manual installs. Anything that puts the settings fragments in the *Witcher 3* game directory.
* **Game Store:** Purpose built to search Steam libraries but should also work with GOG, Epic, etc.

## Disclaimer
This tool is currently in **Beta (v0.9.0)**. It was developed hastily in an afternoon for my own personal use, has worked for me, but **YMMV**. It is provided as-is in the hope of saving others some tedium. This is my only contribution to the Nexus community and am otherwise not actively engaged in modding and am unlikely to have time to follow up or provide support. Though if you have any killer ideas for features that I would want to use and I happen to read them in the comments I might add them.

## Note to Mod Creators and Meticulous Modlist Curators
The program will look for any files with "user" or "input" combined with the phrase ".settings" so if you format your settings files this way it should find them. It will then check their content for relevant headings to confirm before importing.

The only issue I found in my own list was with *Brew With a View*, the user settings files for which were formatted in such a way that Vortex didn't want to deploy them until I removed the `.txt` suffix and then they deployed successfully (for some reason) and were then able to be found by **Settings Merger**. I assume this may happen with other mods so if you encounter import issues you should search ".settings" in your mod staging folder and ensure everything is deploying somewhere in the *Witcher 3* game folder with the above keywords in some orientation, then Settings Merger should find them and do its job.

No promises if two mods want to do slightly different things with the same keybind in the same context; it will add and trigger both. If you want to avoid that, you'll have to change that manually.
