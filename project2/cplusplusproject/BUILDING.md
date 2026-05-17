# Building SecureImageViewer

## Prerequisites

### Ubuntu / Debian (22.04+)
```bash
sudo apt update
sudo apt install -y qt6-base-dev libqt6concurrent-dev cmake g++ make
```

### Fedora
```bash
sudo dnf install qt6-qtbase-devel cmake gcc-c++
```

### Arch Linux
```bash
sudo pacman -S qt6-base cmake gcc
```

### macOS (Homebrew)
```bash
brew install qt@6 cmake
export CMAKE_PREFIX_PATH=$(brew --prefix qt@6)
```

## Build Instructions

```bash
# From the project root (cplusplusproject/)
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

# Run
./build/SecureImageViewer
```

### Debug Build
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j$(nproc)
```

## CMake Configuration

The project uses **AUTOMOC** for Qt Meta-Object Compilation. All Q_OBJECT classes are fully defined in `.hpp` header files — no separate `.cpp` moc files needed.

**Required Qt modules:** Core, Gui, Widgets, Concurrent

To add new Qt modules:
1. Add to `find_package(Qt6 REQUIRED COMPONENTS ...)` in CMakeLists.txt
2. Add to `target_link_libraries()` in CMakeLists.txt

## Troubleshooting

### "Could not find Qt6"
Ensure Qt6 development packages are installed and CMake can find them:
```bash
# Check Qt6 installation
qmake6 --version

# If installed but not found, set CMAKE_PREFIX_PATH
cmake -B build -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/cmake/Qt6
```

### "Could NOT find WrapVulkanHeaders"
This is non-critical for the viewer. The build will succeed with this warning.

### MOC errors on header changes
Delete the build directory and reconfigure:
```bash
rm -rf build
cmake -B build
cmake --build build
```

### Compiler version
GCC 9+ or Clang 10+ required for C++17 support.
