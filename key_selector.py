"""
key_selector.py
===============
Full key selection UI window.

Displays all available keys in a categorized grid that mimics
the look of a physical keyboard. Each key is a compact, dark tile
that glows when selected. Click a tile to toggle it.

Design:
    - OLED-black background (#0A0A12)
    - Compact keycap tiles with subtle border glow
    - Adaptive column counts per category
    - Smooth selected/hover state transitions
"""

import tkinter as tk
from tkinter import ttk

from key_registry import KEY_REGISTRY, get_categories
from config_manager import (
    load_config,
    save_selected_keys_and_spawn_anchor,
    save_spawn_anchor,
    save_config,
    DEFAULT_CONFIG,
)
import copy


from shared_theme import COLORS

# Adaptive column count per category — tuned for each group's key count.
CATEGORY_COLUMNS = {
    "Navigation":    6,
    "Arrows":        8,
    "Punctuation":   11,
    "Letters":       13,
    "Numbers":       10,
    "Modifiers":     5,
    "Function Keys": 12,
    "Numpad":        6,
}

DEFAULT_COLUMNS = 8

SPAWN_OPTIONS = [
    ("center", "Center"),
    ("top_left", "Top left"),
    ("top_right", "Top right"),
    ("bottom_left", "Bottom left"),
    ("bottom_right", "Bottom right"),
]


class KeySelectorWindow:
    """
    A Tkinter window that lets the user pick which keys
    to display as floating on-screen buttons.

    Visual style: dark keycap tiles in a categorized grid.
    """

    def __init__(self, on_activate_callback, parent_root=None, on_clear_callback=None):
        """
        Args:
            on_activate_callback: function(selected_key_ids: list)
                Called when the user clicks "Activate".
            parent_root: optional existing Tk root to attach to.
            on_clear_callback: optional function called when Clear All is pressed.
        """
        self.on_activate = on_activate_callback
        self.on_clear = on_clear_callback
        self.checkboxes = {}    # key_id → BooleanVar
        self.ui_updaters = {}   # key_id → function to refresh tile visually
        self._tab_buttons = {}

        # ── Window setup ─────────────────────────────────────────
        if parent_root:
            self.window = tk.Toplevel(parent_root)
        else:
            self.window = tk.Tk()

        self.window.title("On-Screen Keyboard — Select Broken Keys")
        self.window.geometry("1100x700")

        self.window.resizable(True, True)
        self.window.configure(bg=COLORS["bg"])
        self.spawn_anchor_var = tk.StringVar(
            self.window,
            value=DEFAULT_CONFIG["spawn_anchor"],
        )

        self._build_ui()
        self._load_saved_selections()

    # ─────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Construct the full UI layout."""

        # ── Header ───────────────────────────────────────────────
        header = tk.Frame(self.window, bg=COLORS["bg"])
        header.pack(fill="x", padx=24, pady=(18, 6))

        tk.Label(
            header,
            text="⌨  Select Your Broken Keys",
            font=("Sans", 15, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["accent"],
        ).pack(side="left")

        tk.Label(
            header,
            text="Click the keys that aren't working on your keyboard",
            font=("Sans", 9),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
        ).pack(side="left", padx=(14, 0))

        # ── Tabs ─────────────────────────────────────────────────
        self._build_tab_bar()

        self.content_frame = tk.Frame(self.window, bg=COLORS["bg"])
        self.content_frame.pack(fill="both", expand=True, padx=0, pady=(4, 0))

        self.keys_tab = tk.Frame(self.content_frame, bg=COLORS["bg"])
        self.config_tab = tk.Frame(self.content_frame, bg=COLORS["bg"])

        # ── Scrollable key content area ──────────────────────────
        container = tk.Frame(self.keys_tab, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=0, pady=0)

        self._canvas = tk.Canvas(
            container,
            bg=COLORS["bg"],
            highlightthickness=0,
            borderwidth=0,
        )

        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self._canvas.yview,
        )

        self.scroll_frame = tk.Frame(self._canvas, bg=COLORS["bg"])
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )

        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw",
        )

        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)

        # Stretch scroll_frame to canvas width
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # ── Mouse wheel scrolling ────────────────────────────────
        def _scroll_linux(event):
            self._canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

        def _scroll_generic(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._canvas.bind_all("<Button-4>", _scroll_linux)
        self._canvas.bind_all("<Button-5>", _scroll_linux)
        self._canvas.bind_all("<MouseWheel>", _scroll_generic)

        # ── Populate categories ──────────────────────────────────
        for category in get_categories():
            self._add_category_section(category)

        self._build_config_tab()
        self._show_tab("keys")

        # ── Bottom bar ───────────────────────────────────────────
        self._build_bottom_bar()

    def _build_tab_bar(self):
        """Build top-level selector/configuration tabs."""
        tab_bar = tk.Frame(self.window, bg=COLORS["bg"])
        tab_bar.pack(fill="x", padx=24, pady=(6, 0))

        for tab_id, label in (("keys", "Keys"), ("config", "Configuration")):
            btn = tk.Button(
                tab_bar,
                text=label,
                font=("Sans", 9, "bold"),
                bg=COLORS["surface"],
                fg=COLORS["text"],
                activebackground=COLORS["tile_hover"],
                activeforeground=COLORS["text_selected"],
                relief="flat",
                padx=14,
                pady=7,
                cursor="hand2",
                command=lambda t=tab_id: self._show_tab(t),
            )
            btn.pack(side="left", padx=(0, 8))
            self._tab_buttons[tab_id] = btn

    def _show_tab(self, tab_id):
        """Show either the key selection or configuration tab."""
        for frame in (self.keys_tab, self.config_tab):
            frame.pack_forget()

        if tab_id == "config":
            self.config_tab.pack(fill="both", expand=True)
        else:
            self.keys_tab.pack(fill="both", expand=True)
            tab_id = "keys"

        for name, btn in self._tab_buttons.items():
            selected = name == tab_id
            btn.config(
                bg=COLORS["tile_selected"] if selected else COLORS["surface"],
                fg=COLORS["text_selected"] if selected else COLORS["text"],
            )

    def _build_config_tab(self):
        """Build configuration controls."""
        panel = tk.Frame(self.config_tab, bg=COLORS["bg"])
        panel.pack(anchor="nw", fill="x", padx=24, pady=22)

        tk.Label(
            panel,
            text="Floating key spawn position",
            font=("Sans", 11, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["text_selected"],
        ).pack(anchor="w")

        tk.Label(
            panel,
            text="Changing this resets dragged positions so the next activation uses this location.",
            font=("Sans", 9),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
        ).pack(anchor="w", pady=(3, 14))

        option_grid = tk.Frame(panel, bg=COLORS["bg"])
        option_grid.pack(anchor="w")

        for i, (value, label) in enumerate(SPAWN_OPTIONS):
            option = tk.Radiobutton(
                option_grid,
                text=label,
                value=value,
                variable=self.spawn_anchor_var,
                command=self._save_spawn_setting,
                font=("Sans", 10),
                bg=COLORS["bg"],
                fg=COLORS["text"],
                activebackground=COLORS["bg"],
                activeforeground=COLORS["accent"],
                selectcolor=COLORS["surface"],
                relief="flat",
                padx=8,
                pady=6,
                cursor="hand2",
            )
            option.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 22), pady=4)

    def _on_canvas_resize(self, event):
        """Keep the scroll_frame as wide as the canvas viewport."""
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    def _build_bottom_bar(self):
        """Build the sticky bottom action bar."""

        bar = tk.Frame(self.window, bg=COLORS["surface"], height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # ── Left: Reset ──────────────────────────────────────────
        reset_btn = tk.Button(
            bar,
            text="⟲  Reset Config",
            font=("Sans", 9),
            bg=COLORS["surface"],
            fg=COLORS["red"],
            activebackground=COLORS["red"],
            activeforeground=COLORS["bg"],
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._reset_config,
        )
        reset_btn.pack(side="left", padx=(20, 0), pady=10)

        # ── Left: Count label ────────────────────────────────────
        self.count_label = tk.Label(
            bar,
            text="0 keys selected",
            font=("Sans", 9),
            bg=COLORS["surface"],
            fg=COLORS["text_dim"],
        )
        self.count_label.pack(side="left", padx=(14, 0))

        # ── Right: Activate ──────────────────────────────────────
        activate_btn = tk.Button(
            bar,
            text="  Activate Selected Keys  ",
            font=("Sans", 10, "bold"),
            bg=COLORS["green"],
            fg="#0A0A12",
            activebackground="#94E2D5",
            activeforeground="#0A0A12",
            relief="flat",
            padx=18,
            pady=7,
            cursor="hand2",
            command=self._on_activate,
        )
        activate_btn.pack(side="right", padx=(0, 20), pady=10)

        # ── Right: Clear All ─────────────────────────────────────
        clear_btn = tk.Button(
            bar,
            text="Clear All",
            font=("Sans", 9),
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["tile_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._deselect_all,
        )
        clear_btn.pack(side="right", padx=(0, 8), pady=10)

    # ─────────────────────────────────────────────────────────────
    # Category Sections
    # ─────────────────────────────────────────────────────────────

    def _add_category_section(self, category):
        """Add a labeled section with keycap tiles for one category."""

        keys = KEY_REGISTRY[category]
        columns = CATEGORY_COLUMNS.get(category, DEFAULT_COLUMNS)

        # ── Section header ───────────────────────────────────────
        header = tk.Frame(self.scroll_frame, bg=COLORS["bg"])
        header.pack(fill="x", padx=20, pady=(14, 3))

        tk.Label(
            header,
            text=category.upper(),
            font=("Sans", 8, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
        ).pack(side="left")

        tk.Button(
            header,
            text="deselect all",
            font=("Sans", 7),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["accent"],
            relief="flat",
            padx=4,
            pady=0,
            cursor="hand2",
            borderwidth=0,
            command=lambda c=category: self._select_category(c, False),
        ).pack(side="right", padx=(0, 4))

        tk.Button(
            header,
            text="select all",
            font=("Sans", 7),
            bg=COLORS["bg"],
            fg=COLORS["text_dim"],
            activebackground=COLORS["bg"],
            activeforeground=COLORS["accent"],
            relief="flat",
            padx=4,
            pady=0,
            cursor="hand2",
            borderwidth=0,
            command=lambda c=category: self._select_category(c, True),
        ).pack(side="right", padx=(0, 4))

        # Thin separator
        tk.Frame(
            self.scroll_frame, bg=COLORS["separator"], height=1,
        ).pack(fill="x", padx=20, pady=(0, 5))

        # ── Key tile grid ────────────────────────────────────────
        grid = tk.Frame(self.scroll_frame, bg=COLORS["bg"])
        grid.pack(fill="x", padx=18, pady=(0, 4))

        for col_i in range(columns):
            grid.columnconfigure(col_i, weight=1, uniform="keycol")

        for i, key in enumerate(keys):
            var = tk.BooleanVar(value=False)
            self.checkboxes[key["id"]] = var

            # Outer border frame (acts as the glow border)
            border_frame = tk.Frame(
                grid, bg=COLORS["border"],
                padx=1, pady=1,
            )
            border_frame.grid(
                row=i // columns,
                column=i % columns,
                sticky="nsew",
                padx=6, pady=3,
            )

            font_size = 20 if category == "Arrows" else 10
            btn_pady = 6 if category == "Arrows" else 14

            # Inner keycap button
            tile = tk.Button(
                border_frame,
                text=key["label"],
                font=("Monospace", font_size, "bold"),
                bg=COLORS["tile"],
                fg=COLORS["text"],
                activebackground=COLORS["tile_hover"],
                activeforeground=COLORS["accent"],
                relief="flat",
                anchor="center",
                padx=2,
                pady=btn_pady,
                cursor="hand2",
                borderwidth=0,
            )
            tile.pack(fill="both", expand=True)

            # Build the visual updater (closure-safe)
            updater = self._make_updater(var, tile, border_frame, key)
            self.ui_updaters[key["id"]] = updater

            # Build the toggle command (closure-safe)
            toggle_cmd = self._make_toggle(var, updater)
            tile.config(command=toggle_cmd)

            # Hover effects
            self._bind_hover(tile, border_frame, var)

    # ─────────────────────────────────────────────────────────────
    # Tile Helpers (closure-safe factories)
    # ─────────────────────────────────────────────────────────────

    def _make_updater(self, var, tile, border, key):
        """
        Return a function that refreshes a tile's visuals
        based on its BooleanVar state.
        """
        def updater():
            if var.get():
                tile.config(
                    bg=COLORS["tile_selected"],
                    fg=COLORS["text_selected"],
                )
                border.config(bg=COLORS["border_selected"])
            else:
                tile.config(
                    bg=COLORS["tile"],
                    fg=COLORS["text"],
                )
                border.config(bg=COLORS["border"])
        return updater

    def _make_toggle(self, var, updater):
        """Return a command that flips the var, refreshes tile, and updates count."""
        def toggle():
            var.set(not var.get())
            updater()
            self._update_count()
        return toggle

    def _bind_hover(self, tile, border, var):
        """Attach enter/leave hover effects to a tile."""

        def on_enter(e):
            if not var.get():
                tile.config(bg=COLORS["tile_hover"])
                border.config(bg=COLORS["border_hover"])

        def on_leave(e):
            if not var.get():
                tile.config(bg=COLORS["tile"])
                border.config(bg=COLORS["border"])

        tile.bind("<Enter>", on_enter)
        tile.bind("<Leave>", on_leave)

    # ─────────────────────────────────────────────────────────────
    # State Management
    # ─────────────────────────────────────────────────────────────

    def _load_saved_selections(self):
        """Pre-check tiles from saved config."""
        config = load_config()
        saved_keys = config.get("selected_keys", [])
        self.spawn_anchor_var.set(config.get("spawn_anchor", DEFAULT_CONFIG["spawn_anchor"]))

        for key_id in saved_keys:
            if key_id in self.checkboxes:
                self.checkboxes[key_id].set(True)

        self._refresh_ui()

    def _refresh_ui(self):
        """Refresh all tile visuals to match their internal state."""
        for updater in self.ui_updaters.values():
            updater()
        self._update_count()

    def _update_count(self):
        """Update the 'N keys selected' counter label."""
        count = sum(1 for var in self.checkboxes.values() if var.get())
        self.count_label.config(
            text=f"{count} key{'s' if count != 1 else ''} selected"
        )

    def _select_category(self, category, state):
        """Select or deselect all keys in a category."""
        keys = KEY_REGISTRY[category]
        for key in keys:
            if key["id"] in self.checkboxes:
                self.checkboxes[key["id"]].set(state)
        self._refresh_ui()

    def _deselect_all(self):
        """Clear all selections and remove currently active floating keys."""
        for var in self.checkboxes.values():
            var.set(False)
        self._refresh_ui()
        save_selected_keys_and_spawn_anchor([], self.spawn_anchor_var.get())

        if self.on_clear:
            self.on_clear()

        self.count_label.config(text="All keys cleared", fg=COLORS["red"])
        self.window.after(
            2000,
            lambda: (
                self._update_count(),
                self.count_label.config(fg=COLORS["text_dim"]),
            ),
        )

    def _save_spawn_setting(self):
        """Persist the selected spawn anchor."""
        save_spawn_anchor(self.spawn_anchor_var.get(), clear_positions=True)

    def _reset_config(self):
        """
        Reset everything — wipe saved key selections AND saved button
        positions from the config file, then uncheck all tiles.
        """
        save_config(copy.deepcopy(DEFAULT_CONFIG))

        for var in self.checkboxes.values():
            var.set(False)
        self.spawn_anchor_var.set(DEFAULT_CONFIG["spawn_anchor"])

        self._refresh_ui()

        # Flash confirmation
        self.count_label.config(text="Config reset ✓", fg=COLORS["red"])
        self.window.after(
            2500,
            lambda: (
                self._update_count(),
                self.count_label.config(fg=COLORS["text_dim"]),
            ),
        )

    def _on_activate(self):
        """Gather selected keys and invoke the callback."""
        selected = [
            key_id
            for key_id, var in self.checkboxes.items()
            if var.get()
        ]

        if not selected:
            self.count_label.config(
                text="⚠ Select at least one key!",
                fg=COLORS["red"],
            )
            self.window.after(
                2000,
                lambda: self.count_label.config(fg=COLORS["text_dim"]),
            )
            self._update_count()
            return

        save_selected_keys_and_spawn_anchor(selected, self.spawn_anchor_var.get())
        self.window.destroy()
        self.on_activate(selected)

    def run(self):
        """Start the selector window mainloop (if standalone)."""
        self.window.mainloop()
