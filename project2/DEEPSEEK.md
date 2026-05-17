# SecureImageViewer — iRoll Secure Viewer

## Overview

Desktop Qt6/C++17 application for creating and viewing encrypted image archives (`.iroll` files) with XOR obfuscation + Qt compression. Designed to keep NSFW/sensitive content casually hidden from kids or family on a shared home PC — not meant for defense against technically skilled adversaries.

Features: infinite scrolling, grid gallery, synchronized dual-pane viewing, zoom, slideshow, search/filter, favorites, PIN lock, quick-hide, blurred viewer/gallery, and batch encoder with dedup.

---

## Project Structure

```
project2/
├── DEEPSEEK.md                # This file
├── todolist.md                # Task tracking
└── cplusplusproject/
    ├── CMakeLists.txt          # Build system (Qt6 + CMake)
    ├── main.cpp                # Entry point, UI, dialogs, session management
    ├── ImageVault.hpp          # .iroll format (pack/load/decrypt/export/dedup/batch)
    ├── InfiniteViewer.hpp      # Infinite scroll widget (painting, cache, async, zoom, blur, random slideshow)
    ├── DualViewer.hpp          # Dual-pane with sync'd scrolling, syncGuard for dedup
    ├── viewer.cpp              # CLI example of ImageVault (standalone)
    ├── comand                  # Quick build script (rm -rf build && mkdir build && cd build && cmake .. && make && ./SecureImageViewer)
    ├── README.md               # User-facing documentation
    ├── BUILDING.md             # Build instructions per distro
    ├── config.json             # Runtime config (PIN, window title, dim-on-unfocus)
    ├── .github/workflows/      # CI config (build.yml)
    └── build/                  # Active build directory
```

## Tech Stack

| Layer           | Technology                        |
|-----------------|-----------------------------------|
| Language        | C++17                             |
| GUI             | Qt6 (Core, Gui, Widgets)          |
| Concurrency     | Qt6::Concurrent + lambdas         |
| Build           | CMake ≥ 3.16, AUTOMOC ON          |
| Compression     | qCompress / qUncompress           |
| Obfuscation     | XOR with fixed key `0x5A`         |
| Hash (dedup)    | QCryptographicHash::Md5           |
| Config          | QJsonDocument / config.json       |
| Tray            | QSystemTrayIcon                   |

## Code Conventions

### General Style
- **Indentation**: 4 spaces (no tabs)
- **Class names**: PascalCase (e.g. `ImageVault`, `InfiniteScrollWidget`, `PinDialog`)
- **Method names**: camelCase (e.g. `loadImages()`, `setBlurImages()`, `toggleFavorite()`)
- **Variable names**: camelCase (e.g. `fileList`, `scrollY`, `zoomFactor`)
- **Member names**: camelCase, no prefix (e.g. `imageCache`, `pendingRequests`, `thumbnailLoadIndex`)
- **Headers**: exclusively `.hpp`, implementations are inline for all Q_OBJECT classes
- **Guards**: `#ifndef / #define / #endif` (never `#pragma once`)

### Qt / MOC
- Q_OBJECT classes are defined **and** implemented entirely in the `.hpp` file
- `CMAKE_AUTOMOC ON` — no need to manually list moc files
- `main.cpp` includes `#include "main.moc"` at the end
- **Q_OBJECT classes MUST be at file scope** — MOC cannot process nested classes

### Signal/Slot Patterns
- Lambda connections for UI actions (buttons, checkboxes, shortcuts)
- Member function connections for internal sync (e.g. `syncScrollLeftToRight`, `userNavigated`)
- Signals emitted at the **end** of the triggering method
- **Always match signal/slot argument counts** — `returnPressed()` cannot connect to `clicked(bool)`; wrap in lambda

### Composite IDs
- Image identifiers: `"vault_path||filename"`
- Separator: `"||"` (double pipe)
- Hidden playlist flag stored in `Qt::UserRole + 1`

### Async Handling
- `QtConcurrent::run()` for background image loading/decoding
- `QMetaObject::invokeMethod()` to update the main thread
- Image cache: `QCache<int, QPixmap>` with capacity `CACHE_SIZE = 50`
- Thumbnails: batch loading of 10 using recursive `QTimer::singleShot`
- `pendingRequests` (`QSet<int>`) prevents duplicate async loads; cleared on reload/zoom/fit/blur change

### .iroll File Format (Proprietary)
- **Header**: Magic bytes `"IROLL_V1"` (8 bytes)
- **Next**: `quint32` file count
- **Per file**: name (QString), original size (qint64), compressed size (qint64), compressed+XOR data
- **XOR key**: `0x5A` (fixed constant in `ImageVault::XOR_KEY`)

### Visual / Theming
- Dark theme via Qt stylesheets globally
- Sidebar: fixed 280px width, background `#181818`
- Content area: background `#222`
- Accent colors: `#4CAF50` (green), `#FFD700` (star/favorite), `#ccc`, `#eee` (text)

## Key Classes & Responsibilities

| Class                    | File         | Role |
|--------------------------|--------------|------|
| `ImageVault`             | ImageVault.hpp | .iroll pack/load/extract/dedup/batch-subfolders. Error reporting via `get_last_error()`. |
| `InfiniteScrollWidget`   | InfiniteViewer.hpp | Infinite-scroll image renderer. Handles painting, caching, async loading, zoom, blur, random slideshow. Emits `userNavigated` for slideshow pause. |
| `DualPaneWidget`         | DualViewer.hpp | Side-by-side viewer with `syncGuard` to prevent feedback loops. Forwards `setZoom`, `setBlurImages`, `setRandomSlideshow`. Exposes `left()`/`right()` accessors. |
| `PlaylistWidget`         | main.cpp | QListWidget subclass with drag-drop (`.iroll`, `.dat`, `.bin`, `.db`), internal reorder, custom context menu for hide. |
| `PinDialog`              | main.cpp | 4-digit PIN gate dialog. Reads from `config.json`. |
| `EncoderDialog`          | main.cpp | Archiver UI with dedup checkbox and batch-subfolder mode. |
| `ExportDialog`           | main.cpp | Extract images from `.iroll` to folder with progress. |
| `ShortcutsDialog`        | main.cpp | Reference panel listing all keyboard bindings. |
| `MainWindow`             | main.cpp | Application orchestrator: two playlists, viewer stack, toolbar, tray icon, favorites, search, info overlay, all shortcuts. |

## Agent Rules

1. **Keep Q_OBJECT classes inline in .hpp** — implementations go in the header, not separate .cpp files.
2. **Q_OBJECT classes must be at file scope** — never nest them inside another class.
3. **Use `std::vector<QString>`** for file lists, not `QStringList`.
4. **Build**: run `cmake -B build && cmake --build build` from `cplusplusproject/`.
5. **Never use `#pragma once`** — use `#ifndef / #define / #endif` guards.
6. **Register new source files** in `CMakeLists.txt` under `add_executable()`.
7. **Register new Qt modules** in both `find_package()` and `target_link_libraries()`.
8. **Do not commit changes** unless explicitly requested.
9. **Private slots go under `private slots:`** access specifier.
10. **Use progress callbacks** (`std::function<void(int,int)>`) for long operations like `pack()` and `extract_all()`.
11. **Never use raw newlines inside C++ string literals** — use `
` escape or adjacent string concatenation. The `write_file` tool's `
` gets interpreted as a real newline, so prefer adjacent strings: `"line1
" "line2"`.
12. **Match signal/slot argument counts exactly** — wrap mismatched connections in lambdas.
13. **Lambda captures**: member variables are accessed via `this` capture; local variables need explicit capture by value.
14. **Config** is stored in `config.json` at runtime (PIN, window title, dim-on-unfocus). Read with QJsonDocument.
15. **File extensions**: the app accepts `.iroll`, `.dat`, `.bin`, `.db` — the latter three are for stealth/disguised archives.
