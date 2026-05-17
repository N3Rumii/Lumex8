"""Terminal definitions and detection."""

import shutil

# (Display Name, Executable, Arguments to run a command)
KNOWN_TERMINALS: list[tuple[str, str, list[str]]] = [
    ("GNOME Terminal", "gnome-terminal", ["--"]),
    ("Konsole", "konsole", ["-e"]),
    ("XFCE Terminal", "xfce4-terminal", ["-x"]),
    ("Kitty", "kitty", ["--"]),
    ("Alacritty", "alacritty", ["-e"]),
    ("XTerm", "xterm", ["-e"]),
    ("Terminator", "terminator", ["-x"]),
    ("Foot", "foot", ["bash", "-c"]),
]


def get_installed_terminals() -> list[tuple[str, str, list[str]]]:
    """Return the list of terminals found on this system."""
    return [
        (name, cmd, args)
        for name, cmd, args in KNOWN_TERMINALS
        if shutil.which(cmd)
    ]
