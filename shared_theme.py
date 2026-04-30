"""
shared_theme.py
===============
Centralized UI styling constants for both the Key Selector window
and the Floating Key buttons. Ensures visual consistency across the app.
"""

# ─── Selector Window Palette ─────────────────────────────────────────
# Ultra-dark, cold-toned palette inspired by mechanical keyboard aesthetics.
COLORS = {
    "bg":              "#0A0A12",    # Near-OLED black
    "surface":         "#12121E",    # Slightly lifted surface
    "tile":            "#151520",    # Key tile background
    "tile_hover":      "#1E1E30",    # Tile on hover
    "tile_selected":   "#1A2238",    # Tile when selected (subtle blue tint)
    "border":          "#1E1E2E",    # Default tile border
    "border_selected": "#7287FD",    # Selected glow border (Catppuccin Lavender)
    "border_hover":    "#45475A",    # Hover border
    "text":            "#A6ADC8",    # Default text
    "text_dim":        "#585B70",    # Dimmed text (subtitles, hints)
    "text_selected":   "#CDD6F4",    # Bright text when selected
    "accent":          "#B4BEFE",    # Primary accent (headers, highlights)
    "green":           "#A6E3A1",    # Success / activate
    "red":             "#F38BA8",    # Danger / reset
    "separator":       "#1E1E2E",    # Section separator lines
}

# ─── Floating Button Palette ─────────────────────────────────────────
# Default fallback palette
FLOATING_BUTTON = {
    "bg":          "#313244",
    "fg":          "#cdd6f4",
    "active_bg":   "#89b4fa",
    "active_fg":   "#1e1e2e",
    "border":      "#45475a",
    "flash":       "#a6e3a1",
}

# Global opacity for all floating keys (0.0 = invisible, 1.0 = solid)
FLOATING_OPACITY = 0.82

# ─── Per-Category Floating Key Colors ────────────────────────────────
# Each category gets a distinct color scheme so keys are visually grouped.
CATEGORY_COLORS = {
    "Navigation": {
        "bg":        "#1A2744",    # Deep navy blue
        "fg":        "#89B4FA",    # Blue text
        "active_bg": "#89B4FA",
        "active_fg": "#11111B",
        "border":    "#3A4764",
        "flash":     "#B4BEFE",
    },
    "Arrows": {
        "bg":        "#1E3A3A",    # Teal dark
        "fg":        "#94E2D5",    # Teal text
        "active_bg": "#94E2D5",
        "active_fg": "#11111B",
        "border":    "#3E5A5A",
        "flash":     "#A6E3A1",
    },
    "Punctuation": {
        "bg":        "#2D1B3E",    # Dark purple
        "fg":        "#CBA6F7",    # Mauve text
        "active_bg": "#CBA6F7",
        "active_fg": "#11111B",
        "border":    "#4D3B5E",
        "flash":     "#F5C2E7",
    },
    "Letters": {
        "bg":        "#1E2030",    # Slate blue-grey
        "fg":        "#BAC2DE",    # Soft lavender text
        "active_bg": "#B4BEFE",
        "active_fg": "#11111B",
        "border":    "#3E4050",
        "flash":     "#A6E3A1",
    },
    "Numbers": {
        "bg":        "#2A2215",    # Warm amber dark
        "fg":        "#F9E2AF",    # Yellow text
        "active_bg": "#F9E2AF",
        "active_fg": "#11111B",
        "border":    "#4A4235",
        "flash":     "#F5E0DC",
    },
    "Modifiers": {
        "bg":        "#2E1520",    # Dark rose
        "fg":        "#F38BA8",    # Red/pink text
        "active_bg": "#F38BA8",
        "active_fg": "#11111B",
        "border":    "#4E3540",
        "flash":     "#F5C2E7",
    },
    "Function Keys": {
        "bg":        "#152E1A",    # Forest green dark
        "fg":        "#A6E3A1",    # Green text
        "active_bg": "#A6E3A1",
        "active_fg": "#11111B",
        "border":    "#354E3A",
        "flash":     "#94E2D5",
    },
    "Numpad": {
        "bg":        "#2A1A10",    # Warm brown dark
        "fg":        "#FAB387",    # Peach text
        "active_bg": "#FAB387",
        "active_fg": "#11111B",
        "border":    "#4A3A30",
        "flash":     "#F9E2AF",
    },
}


def get_floating_colors(category):
    """
    Return the color dict for a given category.
    Falls back to the default FLOATING_BUTTON palette if category is unknown.
    """
    return CATEGORY_COLORS.get(category, FLOATING_BUTTON)
