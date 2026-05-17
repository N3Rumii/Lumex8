# SecureImageViewer — To-Do

## Critical / Bugs

- [x] **`InfiniteViewer.hpp` has unused `VaultWrapper` forward-declared struct** — removed.
- [x] **`scrollY` wrapping** — fixed in `jumpToSpecificIndex` and `paintEvent` (proper modulo wrapping for negative values).
- [x] **`pendingRequests` invalidation** — cleared on `loadImages()`, `setFitToScreen()`, and `setZoom()`.
- [x] **`setScrollY` double-update in dual sync** — added `syncGuard` flag in `DualPaneWidget` to prevent feedback loops.

## Improvements

- [ ] **Separate `.cpp` files for large Q_OBJECT classes** — deferred (project convention is all-inline `.hpp`).
- [x] **Build system cleanup** — removed stale `buildold/` directory.
- [x] **`std::random_shuffle` comment** — cleaned up; all usage now `std::shuffle` with `std::mt19937`.
- [x] **Error handling in `load_archive`** — added `QString *errorOut` parameter and `get_last_error()` method.
- [x] **Memory management** — added `~MainWindow()` destructor that deletes all `ImageVault*` in `loadedVaults`.
- [ ] **Thumbnail loading safety** — deferred (edge case when gallery item removed mid-async callback).
- [x] **Slideshow pause on user interaction** — `userNavigated()` signal from viewer → `pauseSlideshow()` unchecks Auto checkbox.

## Features (Future)

- [x] **Separate playlists per viewport** — LEFT PANE / RIGHT PANE with independent checkboxes.
- [x] **Shuffle reorders images within rolls** — `shufflePerVault()` permutes each `.iroll` individually.
- [x] **Export / extract images** — `ImageVault::extract_file()` and `extract_all()` + ExportDialog UI.
- [x] **Keyboard shortcuts panel** — `?` key opens ShortcutsDialog listing all bindings + Ctrl+F, Ctrl+E, Space shortcuts.
- [x] **Zoom (Ctrl+Wheel)** — 25%–400% range, zoom label in toolbar, `InfiniteScrollWidget::setZoom()`.
- [x] **Search/filter** — `QLineEdit` above playlists filters items in both left/right by filename.
- [x] **Batch encode** multiple folders into separate `.iroll` files — (merged into suggestions below as batch import from subfolders).
- [x] **Drag-reorder** — playlists use `InternalMove` drag-drop mode; `orderChanged` signal triggers rebuild.
- [x] **Image info overlay** — semi-transparent label on hover showing filename, resolution, file size.

## Build & Testing

- [ ] **Write unit tests** for `ImageVault` pack/load round-trip — deferred (needs test framework integration).
- [x] **Add CI config** — `.github/workflows/build.yml` for Ubuntu 22.04 + Qt6.
- [x] **Document required system packages** — `BUILDING.md` with distro-specific install instructions.
- [x] **Project documentation** — `README.md` with features, usage, architecture, and .iroll format spec.

---

## Keep It Out of Sight

*Goal: prevent kids/family from accidentally stumbling on NSFW content.*

- [x] **Simple PIN lock on launch** — 4-digit PIN before the app shows anything. No crypto, just a gate. Optional: auto-lock after N minutes idle.
- [x] **Quick-hide hotkey** — single key (e.g. `Ctrl+H` or middle mouse button) instantly minimizes to tray or switches to a blank window. Restore with click or hotkey.
- [x] **Blurred gallery thumbnails by default** — gallery grid shows pixelated/blurred thumbnails. Reveal on hover or hold a modifier key.
- [x] **Start minimized / start on blank screen** — app opens to an empty viewer or the encoder dialog, not the last viewed image.
- [x] **No auto-load last session** — don't remember which `.iroll` files were open. Start fresh each time.

## Leave No Obvious Traces

- [ ] **Skip OS recent-files list** — deferred (requires platform-specific code)** — prevent loaded `.iroll` files from appearing in Windows/macOS/Linux "recent documents".
- [x] **Custom file extension** — let the user choose the extension (`.dat`, `.bin`, `.db`, or anything) so archives don't stand out as `.iroll`.
- [x] **Innocent window title** — option to show "Settings", "System Update", or a custom title instead of "iRoll Secure Viewer".
- [ ] **Clear file dialog history** — deferred (Qt doesn't persist dialog history cross-session by default)** — wipe the Qt file picker's remembered paths after each session.
- [x] **No thumbnail cache on disk** — already the case (all images decoded in RAM only, never written to disk)** — ensure the OS doesn't generate `.thumb` or `thumbs.db` files from viewed images.

## Simple Access Control

- [x] **Hide playlist entries** — right-click → "Hide" on a playlist item. Hidden rolls only reappear when a "Show hidden" checkbox is toggled.
- [ ] **Separate "safe" and "private" panes** — partially done via independent left/right playlists; explicit safe/private labelling deferred panes** — left playlist for harmless images, right playlist for private ones. In single-pane mode, only left content is shown until right pane is explicitly opened.
- [x] **Window dims when unfocused** — slightly darken or reduce opacity when another window is clicked, so passersby can't read the screen easily.

## Quality of Life

- [ ] **Drag image out to save** — deferred (requires drag-source support from viewer widget)** — drag a single image from the viewer to a folder to extract it without opening the export dialog.
- [x] **Copy image to clipboard** — `Ctrl+C` copies the current image so it can be pasted elsewhere.
- [x] **Slideshow with random order** — shuffle playback mode for slideshows.
- [x] **Star/favorite toggle** — mark images as favorites, filter by favorites.
- [x] **Skip duplicate files when packing** — detect identical images by hash when creating a `.iroll`.
- [x] **Batch import from subfolders** — pack each subfolder into its own `.iroll` in one go.
