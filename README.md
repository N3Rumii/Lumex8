Lumex8

Lumex8 is a Python script launcher inspired by the Windows 8 tile start menu.

I built this because I wanted an easier way to launch my Python scripts. I do most of my work on a graphic tablet, so I wanted a touchscreen-friendly interface. It’s been a long time since I used the actual Windows 8 menu, but this is how I remember it feeling—sort of.
Compatibility

This script is designed for Linux. It should work on any distro provided you have Gnome Terminal installed.

    Note: The script currently relies on gnome-terminal as the backend for launching applications. If you are on KDE or another desktop environment, you will need to install Gnome Terminal or modify the script to use your preferred terminal.

Prerequisites

Before installing, make sure you have the following system packages:

    python3-pip

    python3-venv

    libxcb-cursor0

Installation

 Download the script Create a directory where you want the app to live, and paste Lumex8.py there. Open your terminal in this directory.

 Set up the Virtual Environment Run the following command to create a virtual environment:
    

    python3 -m venv venv

Activate the Environment


    source venv/bin/activate

Your command line should now look something like (venv) user@computer:~/lumex8$.

Install Dependencies With the environment active, install the required libraries:


    pip install PyQt6 pynput

Usage

To launch the script, simply run:


    python lumex8.py

/Note (Using uv)

When I was coding this in PyCharm, it handled the environment setup for me and it used UV. Recently, If you have uv installed, you can skip the manual venv activation and just run:


    uv run lumex8.py

FAQ

1. Why doesn't it fetch all apps from my system? This was never designed to replace the standard Start Menu. At its core, it is a launcher for my custom Python scripts. I didn't want to pollute the menu with all the random clutter I have installed on my PC.

2. Does this work on KDE? Currently, the only thing stopping it is the dependency on gnome-terminal. If you replace that line in the code with your terminal of choice (like Konsole), it should work. I plan to address this in a future update.

3. Why Windows 8 style? I use a graphic tablet for work, so a touch-friendly interface was my main goal. Also, I just like the aesthetic.
Known Bugs

    Some system applications (mainly System Settings) refuse to launch via the terminal backend. I may add a side menu for these, similar to the original Windows 8 charms bar.

Changelog

    0.6 - Optimization: Fixed performance issues caused by saving layout on every pixel of movement while dragging tiles.

    0.5 - Added a toggleable Start button on the desktop and keyboard navigation (Arrows + Tab). Removed Folders

    0.4 - Added ability to fetch standard applications and fltapacks alongside Python scripts (with icons).

    0.3 - Added ability to use custom icons from a local drive.

    0.2 - Added Group functionality and added ability to move tiles.

    0.1 - Added Folders.
