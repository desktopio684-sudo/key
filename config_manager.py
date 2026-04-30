"""
config_manager.py
=================
Handles saving and loading user preferences.

Config is stored at: ~/.config/onscreen-keys/config.json

Schema:
{
    "selected_keys": ["enter", "dot", "comma", ...],
    "spawn_anchor": "center",
    "positions": {
        "enter": {"x": 100, "y": 200},
        ...
    }
}
"""

import json
import os
import threading
import copy

# ─── Config paths ────────────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.config/onscreen-keys")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


# ─── Default empty config ────────────────────────────────────────────

DEFAULT_CONFIG = {
    "selected_keys": [],
    "spawn_anchor": "center",
    "positions": {},
}

# Valid values for unsaved floating key spawn anchor.
VALID_SPAWN_ANCHORS = {
    "center",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
}

# ─── Debouncing and cache state ──────────────────────────────────────

_cached_config = None
_save_timer = None
_config_lock = threading.Lock()


def _ensure_config_dir():
    """Create the config directory if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    """
    Load config from disk or memory cache.

    Returns the config dict. If the file doesn't exist or is corrupt,
    returns a fresh default config without crashing.
    """
    global _cached_config

    with _config_lock:
        if _cached_config is not None:
            return copy.deepcopy(_cached_config)

        # Fall through to load from disk without holding the lock
        # (I/O operations don't require thread safety)
        _cached_config = None

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data.get("selected_keys"), list):
                data["selected_keys"] = []
            if data.get("spawn_anchor") not in VALID_SPAWN_ANCHORS:
                data["spawn_anchor"] = DEFAULT_CONFIG["spawn_anchor"]
            if not isinstance(data.get("positions"), dict):
                data["positions"] = {}

            with _config_lock:
                _cached_config = data
            return copy.deepcopy(data)

    except (json.JSONDecodeError, IOError, OSError) as e:
        print(f"[config_manager] Warning: Could not load config: {e}")
        print("[config_manager] Using default config.")

    with _config_lock:
        _cached_config = dict(DEFAULT_CONFIG)
    return copy.deepcopy(_cached_config)


def save_config(config, debounce=False):
    """
    Save config to disk, with optional debouncing to avoid excessive I/O.

    Args:
        config: dict with "selected_keys" list and "positions" dict.
        debounce: if True, delays writing to disk to batch changes.
    """
    global _cached_config, _save_timer

    with _config_lock:
        _cached_config = copy.deepcopy(config)

    if debounce:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.5, _write_to_disk)
        _save_timer.daemon = True
        _save_timer.start()
    else:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None
        _write_to_disk()


def _write_to_disk():
    global _cached_config
    config_to_save = None
    with _config_lock:
        if _cached_config is None:
            return
        config_to_save = copy.deepcopy(_cached_config)

    _ensure_config_dir()
    tmp_file = CONFIG_FILE + ".tmp"

    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config_to_save, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, CONFIG_FILE)
    except (IOError, OSError) as e:
        print(f"[config_manager] Error: Could not save config: {e}")


def flush_config():
    """Immediately write any pending debounced changes to disk."""
    global _save_timer
    if _save_timer is not None:
        _save_timer.cancel()
        _save_timer = None
        _write_to_disk()


def save_selected_keys(key_ids):
    """
    Convenience: update just the selected keys in the config.

    Args:
        key_ids: list of key ID strings.
    """
    config = load_config()
    config["selected_keys"] = list(key_ids)
    save_config(config)


def save_selected_keys_and_spawn_anchor(key_ids, anchor):
    """
    Convenience: update selected keys and spawn anchor in one write.

    Args:
        key_ids: list of key ID strings.
        anchor: one of VALID_SPAWN_ANCHORS.
    """
    if anchor not in VALID_SPAWN_ANCHORS:
        anchor = DEFAULT_CONFIG["spawn_anchor"]

    config = load_config()
    config["selected_keys"] = list(key_ids)
    config["spawn_anchor"] = anchor
    save_config(config)


def save_spawn_anchor(anchor, clear_positions=False):
    """
    Convenience: persist default spawn anchor for unsaved keys.

    Args:
        anchor: one of VALID_SPAWN_ANCHORS.
        clear_positions: if True, discard dragged positions so the new
            spawn setting applies on the next activation.
    """
    if anchor not in VALID_SPAWN_ANCHORS:
        anchor = DEFAULT_CONFIG["spawn_anchor"]

    config = load_config()
    config["spawn_anchor"] = anchor
    if clear_positions:
        config["positions"] = {}
    save_config(config)


def get_spawn_anchor():
    """
    Return persisted spawn anchor, falling back to default.
    """
    config = load_config()
    anchor = config.get("spawn_anchor")
    if anchor not in VALID_SPAWN_ANCHORS:
        return DEFAULT_CONFIG["spawn_anchor"]
    return anchor


def save_key_position(key_id, x, y):
    """
    Convenience: update the saved position for a single key button.

    Args:
        key_id: the key's unique ID string.
        x: screen x coordinate.
        y: screen y coordinate.
    """
    config = load_config()
    config["positions"][key_id] = {"x": x, "y": y}
    save_config(config, debounce=True)


def get_saved_position(key_id):
    """
    Get the saved position for a key button.

    Args:
        key_id: the key's unique ID.

    Returns:
        (x, y) tuple, or None if no saved position.
    """
    config = load_config()
    pos = config.get("positions", {}).get(key_id)

    if pos and "x" in pos and "y" in pos:
        return (pos["x"], pos["y"])

    return None
