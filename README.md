# Lumex8

Windows 8 Metro-style tile launcher for Linux. Press **Super+P** to toggle.

**Version:** 0.9.0 · **License:** GPL v3

---

## Few words from author

Application was written for my personal use case, I work on graphical tablet and sometimes stream my setup to the mobile phones so it is helpful to have evn a bit of tablet like interface.
Honestly I was fan of w8 when it came out, and when w10 came out i had a lot of driver issues that i didnt have on 8.1 so i was using it until the end of support.
I managed to launch from Lumex emulator games(both ps4 and ps3) and steam games, i send emu  games to steam and then steam shortcut is somewhat supported inside Lumex. Main function is to add phyton scripts and launch them like normal aps, no .sh scripts or anything. Flatpacks, native aps and appimages are also suported. 
I added live tile functionality though plugins, desktop tile from win8 start menu is in it too.
It was vibe coded, especially this version. I dont feel bad with it, i kind of hate coding. I respect the hustle, i used to write some code myself and even now work on programing plc but normal programing? Well, Tedious so I like how it was done by the Ai. 
I think install.sh for this script is not working correctly, i mean it works on my pop os but it had a lot of issues when i tried to install it on xubuntu in live test mode.
Why Lumex8? Cuz Linux8 sounds like kernel version.


---

## Quick Start

```bash
./lumex8/install.sh
uv run python -m lumex8
```

Requires Python 3.12+ and `libxcb-cursor0`.

---

---

## Changelog

- **0.8** — Theme system with webp assets and .skin export/import. AppBar overhaul, desktop tile, per-tile label toggle, collapsible settings, plugin improvements.
- **0.7** — Full modular package: gamepad, kinetic scroll, slideshow, recolor tool, plugin live tiles, multi-terminal, hotkey recorder, .skin export.
- **0.6** — Drag-and-drop optimization.
- **0.5** — Start button, keyboard nav.
- **0.4** — System app importer with icons.
- **0.3** — Custom local icons.
- **0.2** — Groups, tile reordering.
- **0.1** — Folders.
