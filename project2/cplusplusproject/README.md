# SecureImageViewer — iRoll Secure Viewer

Desktop Qt6/C++17 application for creating and viewing encrypted image archives (`.iroll` files). Features infinite scrolling, grid gallery, synchronized dual-pane viewing, keyboard-driven navigation, zoom, search, and a built-in encoder.

## Features

- **Encrypted Archives** — Pack image folders into `.iroll` files with XOR obfuscation and Qt compression
- **Infinite Scroll Viewer** — Browse images seamlessly with async preloading and caching
- **Dual Pane Mode** — Compare two sets of images side-by-side with synchronized scrolling
- **Grid Gallery** — Thumbnail overview of all loaded images
- **Zoom** — Ctrl+MouseWheel from 25% to 400%
- **Slideshow** — Auto-advance with configurable interval (1–10 seconds)
- **Search/Filter** — Live filter playlists by filename
- **Drag & Drop** — Load `.iroll` files by dragging from file manager
- **Export** — Extract images from archives back to disk
- **Keyboard Shortcuts** — Full keyboard control (see `?` panel)
- **Image Info Overlay** — Hover to see filename, resolution, and file size
- **Dark Theme** — Modern dark UI

## Dependencies

- **Qt 6** (Core, Gui, Widgets, Concurrent)
- **CMake** ≥ 3.16
- **C++17** compiler (GCC 9+, Clang 10+)

### Ubuntu / Debian
```bash
sudo apt install qt6-base-dev libqt6concurrent-dev cmake g++
```

## Build

```bash
cd cplusplusproject
cmake -B build
cmake --build build
./build/SecureImageViewer
```

Or use the convenience script:
```bash
bash comand
```

## Usage

### Creating Archives
1. Click **New Encoder**
2. Select an image folder (supports `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`)
3. Choose output filename (`.iroll`)
4. Click **ENCRYPT & PACK**

### Viewing Images
1. Click **Add to Left** or **Add to Right**, or drag `.iroll` files into a playlist
2. Check the rolls you want active in each pane
3. Images appear in the viewer automatically
4. Use arrow keys or mouse wheel to navigate
5. Click **Grid** for thumbnail overview

### Dual Pane Mode
1. Click **Dual Pane** in the toolbar
2. Left pane uses the **LEFT PANE** playlist
3. Right pane uses the **RIGHT PANE** playlist
4. Scrolling and navigation are synchronized between panes
5. Use **Shuffle** to randomize image order within each roll

### Exporting
1. Click **Export Images**
2. Select the `.iroll` archive
3. Choose output directory
4. Click **EXTRACT ALL**

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `↑` `↓` `←` `→` | Navigate images |
| `F11` | Toggle fullscreen |
| `Esc` | Exit fullscreen |
| `Space` | Toggle slideshow |
| `Ctrl + Wheel` | Zoom in / out |
| `Ctrl + F` | Focus search bar |
| `Ctrl + E` | Export dialog |
| `?` | Keyboard shortcuts panel |

## Architecture

```
main.cpp               Application entry, UI, session management
├── ImageVault.hpp     .iroll format encoder/decoder
├── InfiniteViewer.hpp Infinite scroll image viewer widget
└── DualViewer.hpp     Dual-pane synchronized viewer
```

### .iroll File Format

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 8 bytes | Magic header `"IROLL_V1"` |
| 8 | 4 bytes | File count (`quint32`) |
| 12+ | varies | Per-file entries (name, original size, compressed size, XOR'd + compressed data) |

Encryption: simple XOR with key `0x5A` applied to Qt-compressed data.

## License

Proprietary — all rights reserved.
