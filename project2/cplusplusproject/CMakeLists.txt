cmake_minimum_required(VERSION 3.16)

project(SecureImageViewer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

# --- CRITICAL FIX 1: Add "Concurrent" to this list ---
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Concurrent)

add_executable(SecureImageViewer 
    main.cpp 
    InfiniteViewer.hpp 
    ImageVault.hpp
    DualViewer.hpp   
)

# --- CRITICAL FIX 2: Link "Qt6::Concurrent" here ---
target_link_libraries(SecureImageViewer 
    Qt6::Core 
    Qt6::Gui 
    Qt6::Widgets 
    Qt6::Concurrent
)
