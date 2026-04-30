# On-Screen Keyboard for Broken Keys

A lightweight Linux desktop utility that creates draggable floating key buttons for keys that are broken on your physical keyboard.

When you click a floating key, the app sends that key press to your currently focused external application.

## 1. Setup

### Requirements

- Linux desktop session with **X11** (uses `xdotool` + `python-xlib`)
- Python 3.10+ (tested in this repo with Python 3.12)
- Tkinter (`python3-tk` package on many distros)
- `xdotool`
- Optional but recommended for better tray menu backend: `python3-gi` / AppIndicator runtime

Example (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk xdotool python3-gi gir1.2-appindicator3-0.1
```

### Install

From the project root:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
./run.sh
```

Or directly:

```bash
source venv/bin/activate
python3 main.py
```

### Config location

The app saves selected keys and button positions in:

`~/.config/onscreen-keys/config.json`

## 2. Features and Shortcuts

### Core features

- Floating, always-on-top key buttons for selected keys
- Drag-and-drop positioning for each key button
- Key press simulation via `xdotool key --clearmodifiers`
- Focus-aware key sending:
  - Tracks the last active external window
  - Refocuses it before sending a key, so keys land in your editor/terminal
- Visual feedback flash on button click
- Persistent key selection and per-key position storage
- Full key selection UI with categories:
  - Navigation, Arrows, Punctuation, Letters, Numbers, Modifiers, Function Keys, Numpad
- Selector helpers:
  - Per-category select all / deselect all
  - Global clear all
  - Config reset (clears selected keys + saved positions)
- System tray menu:
  - Show / Hide Keys
  - Show Keys
  - Hide Keys
  - Reconfigure Keys
  - Quit
- Graceful shutdown support:
  - Tray quit
  - `Ctrl+C`
  - terminal commands: `quit`, `exit`, `q`, `stop`

### Keyboard shortcuts

- `Ctrl+K`: Open key selector (reconfigure keys)
- `Ctrl+H`: Toggle floating keys visibility (hide/show)

## 3. Local Development

### Dev workflow

1. Create/activate virtual environment.
2. Install dependencies from `requirements.txt`.
3. Run `python3 main.py` (or `./run.sh`).
4. Edit code and rerun.

### Useful checks

Syntax check all Python files:

```bash
python3 -m py_compile *.py
```

### Project structure

- `main.py`: app lifecycle, global hotkeys, startup/shutdown flow
- `key_selector.py`: key selection UI
- `floating_keys.py`: floating key windows + focus-aware key injection
- `tray_icon.py`: system tray integration
- `key_registry.py`: key catalog and categories
- `config_manager.py`: persistent config read/write/debounced saves
- `shared_theme.py`: shared UI colors/styles
- `run.sh`: convenience launcher

## MIT License

This project is licensed under the MIT License. See [LICENSE](./LICENSE).
