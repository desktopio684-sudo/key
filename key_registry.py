"""
key_registry.py
===============
Master registry of all mappable keys, organized by category.

Each key entry maps a human-readable label to the xdotool key name
that will be used to simulate the key press.
"""


# Each key: {"id": unique_id, "label": display_text, "xdotool_key": xdotool_name}
# Grouped by category for the selector UI.

KEY_REGISTRY = {

    # ─── Navigation & Control ────────────────────────────────────────
    "Navigation": [
        {"id": "enter",     "label": "Enter ⏎",    "xdotool_key": "Return"},
        {"id": "tab",       "label": "Tab ⇥",      "xdotool_key": "Tab"},
        {"id": "backspace", "label": "⌫ Bksp",     "xdotool_key": "BackSpace"},
        {"id": "delete",    "label": "Del",         "xdotool_key": "Delete"},
        {"id": "escape",    "label": "Esc",         "xdotool_key": "Escape"},
        {"id": "space",     "label": "Space ␣",     "xdotool_key": "space"},
        {"id": "insert",    "label": "Ins",         "xdotool_key": "Insert"},
        {"id": "home",      "label": "Home",        "xdotool_key": "Home"},
        {"id": "end",       "label": "End",         "xdotool_key": "End"},
        {"id": "pageup",    "label": "PgUp",        "xdotool_key": "Prior"},
        {"id": "pagedown",  "label": "PgDn",        "xdotool_key": "Next"},
    ],

    # ─── Arrow Keys ──────────────────────────────────────────────────
    "Arrows": [
        {"id": "up",    "label": "↑",  "xdotool_key": "Up"},
        {"id": "down",  "label": "↓",  "xdotool_key": "Down"},
        {"id": "left",  "label": "←",  "xdotool_key": "Left"},
        {"id": "right", "label": "→",  "xdotool_key": "Right"},
    ],

    # ─── Punctuation & Symbols ───────────────────────────────────────
    "Punctuation": [
        {"id": "dot",        "label": ".",    "xdotool_key": "period"},
        {"id": "comma",      "label": ",",    "xdotool_key": "comma"},
        {"id": "semicolon",  "label": ";",    "xdotool_key": "semicolon"},
        {"id": "colon",      "label": ":",    "xdotool_key": "colon"},
        {"id": "apostrophe", "label": "'",    "xdotool_key": "apostrophe"},
        {"id": "quote",      "label": '"',    "xdotool_key": "quotedbl"},
        {"id": "slash",      "label": "/",    "xdotool_key": "slash"},
        {"id": "backslash",  "label": "\\",   "xdotool_key": "backslash"},
        {"id": "minus",      "label": "-",    "xdotool_key": "minus"},
        {"id": "equal",      "label": "=",    "xdotool_key": "equal"},
        {"id": "plus",       "label": "+",    "xdotool_key": "plus"},
        {"id": "underscore", "label": "_",    "xdotool_key": "underscore"},
        {"id": "at",         "label": "@",    "xdotool_key": "at"},
        {"id": "hash",       "label": "#",    "xdotool_key": "numbersign"},
        {"id": "dollar",     "label": "$",    "xdotool_key": "dollar"},
        {"id": "percent",    "label": "%",    "xdotool_key": "percent"},
        {"id": "caret",      "label": "^",    "xdotool_key": "asciicircum"},
        {"id": "ampersand",  "label": "&",    "xdotool_key": "ampersand"},
        {"id": "asterisk",   "label": "*",    "xdotool_key": "asterisk"},
        {"id": "lparen",     "label": "(",    "xdotool_key": "parenleft"},
        {"id": "rparen",     "label": ")",    "xdotool_key": "parenright"},
        {"id": "lbracket",   "label": "[",    "xdotool_key": "bracketleft"},
        {"id": "rbracket",   "label": "]",    "xdotool_key": "bracketright"},
        {"id": "lbrace",     "label": "{",    "xdotool_key": "braceleft"},
        {"id": "rbrace",     "label": "}",    "xdotool_key": "braceright"},
        {"id": "pipe",       "label": "|",    "xdotool_key": "bar"},
        {"id": "tilde",      "label": "~",    "xdotool_key": "asciitilde"},
        {"id": "backtick",   "label": "`",    "xdotool_key": "grave"},
        {"id": "exclaim",    "label": "!",    "xdotool_key": "exclam"},
        {"id": "question",   "label": "?",    "xdotool_key": "question"},
        {"id": "less",       "label": "<",    "xdotool_key": "less"},
        {"id": "greater",    "label": ">",    "xdotool_key": "greater"},
    ],

    # ─── Letters ─────────────────────────────────────────────────────
    "Letters": [
        {"id": f"key_{c}", "label": c.upper(), "xdotool_key": c}
        for c in "abcdefghijklmnopqrstuvwxyz"
    ],

    # ─── Numbers ─────────────────────────────────────────────────────
    "Numbers": [
        {"id": f"num_{n}", "label": str(n), "xdotool_key": str(n)}
        for n in range(0, 10)
    ],

    # ─── Modifiers ───────────────────────────────────────────────────
    "Modifiers": [
        {"id": "shift_l",   "label": "Shift ⇧",     "xdotool_key": "Shift_L"},
        {"id": "ctrl_l",    "label": "Ctrl",         "xdotool_key": "Control_L"},
        {"id": "alt_l",     "label": "Alt",          "xdotool_key": "Alt_L"},
        {"id": "super_l",   "label": "Super ❖",      "xdotool_key": "Super_L"},
        {"id": "caps_lock", "label": "Caps Lock ⇪",  "xdotool_key": "Caps_Lock"},
    ],

    # ─── Function Keys ──────────────────────────────────────────────
    "Function Keys": [
        {"id": f"f{n}", "label": f"F{n}", "xdotool_key": f"F{n}"}
        for n in range(1, 13)
    ],

    # ─── Numpad ──────────────────────────────────────────────────────
    "Numpad": [
        {"id": "kp_enter",    "label": "Num Enter",  "xdotool_key": "KP_Enter"},
        {"id": "kp_add",      "label": "Num +",      "xdotool_key": "KP_Add"},
        {"id": "kp_subtract", "label": "Num -",      "xdotool_key": "KP_Subtract"},
        {"id": "kp_multiply", "label": "Num *",      "xdotool_key": "KP_Multiply"},
        {"id": "kp_divide",   "label": "Num /",      "xdotool_key": "KP_Divide"},
        {"id": "kp_decimal",  "label": "Num .",       "xdotool_key": "KP_Decimal"},
    ],
}


def get_all_keys():
    """Return a flat list of all key entries across all categories."""
    all_keys = []
    for category_keys in KEY_REGISTRY.values():
        all_keys.extend(category_keys)
    return all_keys


def get_key_by_id(key_id):
    """Look up a single key entry by its unique ID."""
    for category_keys in KEY_REGISTRY.values():
        for key in category_keys:
            if key["id"] == key_id:
                return key
    return None


def get_category_for_key(key_id):
    """Return the category name a key_id belongs to, or None."""
    for category, keys in KEY_REGISTRY.items():
        for key in keys:
            if key["id"] == key_id:
                return category
    return None


def get_categories():
    """Return the list of category names in display order."""
    return list(KEY_REGISTRY.keys())
