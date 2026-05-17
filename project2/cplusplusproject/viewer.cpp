// viewer_example.cpp
// Compile: g++ -std=c++17 viewer_example.cpp -o viewer

#include "ImageVault.hpp"
#include <iostream>

// Fake function simulating an Image Library (like OpenCV or SDL)
void display_image_from_memory(const std::vector<char>& data, const std::string& name) {
    if (data.empty()) {
        std::cout << "[Viewer] Error: No data found for " << name << std::endl;
        return;
    }

    std::cout << "------------------------------------------------\n";
    std::cout << "[Viewer] OPENING IMAGE: " << name << "\n";
    std::cout << "[Viewer] Reading " << data.size() << " bytes from RAM...\n";
    std::cout << "[Viewer] Header bytes (hex): " 
              << std::hex << (int)(unsigned char)data[0] << " " 
              << (int)(unsigned char)data[1] << " " 
              << (int)(unsigned char)data[2] << std::dec << "\n";
    std::cout << "[Viewer] Image rendered to screen.\n";
    std::cout << "------------------------------------------------\n";
}

int main() {
    ImageVault vault;

    // 1. Load the obfuscated archive
    std::cout << "Loading secure vault...\n";
    if (!vault.load_archive("my_images.vault")) {
        std::cerr << "Could not load vault!\n";
        return 1;
    }

    // 2. Get list of available images
    std::vector<std::string> images = vault.get_file_list();
    if(images.empty()) {
        std::cout << "Vault is empty.\n";
        return 0;
    }

    // 3. Simulate user selecting the first image
    std::string selected_image = images[0];
    
    // 4. DECODE ON THE FLY
    // The data exists in 'raw_bytes' (RAM) only. It is never written to disk.
    std::vector<char> raw_bytes = vault.get_file_data(selected_image);

    // 5. Pass to rendering engine
    display_image_from_memory(raw_bytes, selected_image);

    // When 'raw_bytes' goes out of scope, the de-obfuscated data is wiped from RAM.
    return 0;
}