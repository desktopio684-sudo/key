"""
floating_keys.py
================
Draggable, always-on-top floating key buttons.

Each selected key gets its own tiny borderless Toplevel window
that can be dragged freely on screen. Clicking a button runs
`xdotool key <keyname>` to simulate the key press.

FOCUS FIX:
    On-screen keyboard windows MUST NOT steal focus from the
    target application. However, Tk managed windows inevitably
    receive focus on click. Our workaround:

    1. FloatingKeyManager continuously polls `xdotool getactivewindow`
       every 150ms to remember which EXTERNAL window last had focus.
    2. When a floating key is clicked, we REFOCUS that external window
       before running `xdotool key`, so the keystroke lands in the
       user's editor/terminal — not in our button.
"""

import math
import re
import subprocess
import tkinter as tk

from key_registry import get_key_by_id, get_category_for_key
from config_manager import save_key_position, get_saved_position, get_spawn_anchor

from shared_theme import FLOATING_OPACITY, get_floating_colors

# Minimum button size
MIN_WIDTH = 48
MIN_HEIGHT = 36

# Padding inside each button
PAD_X = 10
PAD_Y = 6

# Keep floating keys comfortably inside the visible screen area.
SCREEN_MARGIN = 8

# Default spawn positions stay farther from corners than manual dragging.
SPAWN_MARGIN = 28
DENSE_MIN_WIDTH = 28
DENSE_MIN_HEIGHT = 24

_PRIMARY_MONITOR_BOUNDS = None
LATCHING_MODIFIER_KEY_IDS = {"ctrl_l", "alt_l", "super_l", "shift_l"}
MODIFIER_SEND_ORDER = ("ctrl_l", "alt_l", "super_l", "shift_l")
MODIFIER_XDOTOOL_KEYS = {
    "ctrl_l": "Control_L",
    "alt_l": "Alt_L",
    "super_l": "Super_L",
    "shift_l": "Shift_L",
}


def _parse_xrandr_primary_bounds(output):
    """
    Parse primary monitor bounds from xrandr output.

    Returns (x, y, width, height), preferring the primary monitor and
    falling back to the first connected monitor.
    """
    connected = []
    pattern = re.compile(r"\bconnected\b(?:\s+primary)?\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")

    for line in output.splitlines():
        if " connected" not in line:
            continue

        match = pattern.search(line)
        if not match:
            continue

        width, height, x, y = (int(value) for value in match.groups())
        bounds = (x, y, width, height)
        if " primary " in f" {line} ":
            return bounds
        connected.append(bounds)

    return connected[0] if connected else None


def _get_primary_monitor_bounds(root):
    """Return primary monitor bounds, falling back to Tk's primary screen."""
    global _PRIMARY_MONITOR_BOUNDS
    if _PRIMARY_MONITOR_BOUNDS is not None:
        return _PRIMARY_MONITOR_BOUNDS

    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if result.returncode == 0:
            bounds = _parse_xrandr_primary_bounds(result.stdout)
            if bounds:
                _PRIMARY_MONITOR_BOUNDS = bounds
                return bounds
    except Exception:
        pass

    _PRIMARY_MONITOR_BOUNDS = (
        0,
        0,
        int(root.winfo_screenwidth()),
        int(root.winfo_screenheight()),
    )
    return _PRIMARY_MONITOR_BOUNDS


def _fit_grid(count, sizes, usable_w, usable_h):
    """
    Choose a grid that keeps every key inside the monitor without overlap.

    Normal layouts use requested button sizes. Dense layouts shrink cells
    only when the selected key count cannot fit otherwise.
    """
    if count <= 0:
        return 1, 1, 1, 1

    max_w = max(width for width, _ in sizes)
    max_h = max(height for _, height in sizes)
    preferred_step_x = max(max_w + 12, 56)
    preferred_step_y = max(max_h + 10, 44)

    best = None
    for cols in range(1, count + 1):
        rows = math.ceil(count / cols)
        if cols * max_w > usable_w or rows * max_h > usable_h:
            continue

        step_x = preferred_step_x if cols == 1 else min(preferred_step_x, (usable_w - max_w) // (cols - 1))
        step_y = preferred_step_y if rows == 1 else min(preferred_step_y, (usable_h - max_h) // (rows - 1))
        if step_x < max_w or step_y < max_h:
            continue

        shape_penalty = abs(cols - rows)
        area_penalty = cols * rows - count
        score = (shape_penalty, area_penalty, cols)
        if best is None or score < best[0]:
            best = (score, cols, rows, step_x, step_y)

    if best:
        _, cols, rows, step_x, step_y = best
        return cols, rows, step_x, step_y

    # Physical space is too small for requested button sizes. Shrink cells
    # rather than overlapping windows; labels may clip in this extreme case.
    cols = min(count, max(1, usable_w // DENSE_MIN_WIDTH))
    rows = math.ceil(count / cols)
    while rows * DENSE_MIN_HEIGHT > usable_h and cols < count:
        cols += 1
        rows = math.ceil(count / cols)

    step_x = max(1, usable_w // max(1, cols))
    step_y = max(1, usable_h // max(1, rows))
    return cols, rows, step_x, step_y


def calculate_spawn_layout(sizes, bounds, anchor):
    """
    Calculate non-overlapping spawn rectangles within monitor bounds.

    Returns a list of (x, y, width, height).
    """
    left, top, screen_w, screen_h = bounds
    usable_w = max(1, screen_w - (2 * SPAWN_MARGIN))
    usable_h = max(1, screen_h - (2 * SPAWN_MARGIN))
    cols, rows, step_x, step_y = _fit_grid(len(sizes), sizes, usable_w, usable_h)
    max_w = max(width for width, _ in sizes)
    max_h = max(height for _, height in sizes)
    layout_w = ((cols - 1) * step_x) + min(max_w, step_x)
    layout_h = ((rows - 1) * step_y) + min(max_h, step_y)

    if anchor == "center":
        origin_x = left + ((screen_w - layout_w) // 2)
        origin_y = top + ((screen_h - layout_h) // 2)
    else:
        origin_x = left + SPAWN_MARGIN
        origin_y = top + SPAWN_MARGIN
        if "right" in anchor:
            origin_x = left + screen_w - SPAWN_MARGIN - layout_w
        if "bottom" in anchor:
            origin_y = top + screen_h - SPAWN_MARGIN - layout_h

    positions = []
    for index, (width, height) in enumerate(sizes):
        col = index % cols
        row = index // cols
        if "right" in anchor:
            col = cols - 1 - col
        if "bottom" in anchor:
            row = rows - 1 - row

        fitted_w = min(width, step_x)
        fitted_h = min(height, step_y)
        positions.append((
            origin_x + (col * step_x),
            origin_y + (row * step_y),
            fitted_w,
            fitted_h,
        ))

    return positions


def key_needs_spawn_position(key_id, position_lookup=get_saved_position):
    """
    Return True when a key should be placed by spawn layout.

    Keys with saved dragged positions keep those positions instead.
    """
    return position_lookup(key_id) is None


def is_latching_modifier(key_id):
    """Return True for modifiers that behave as sticky on-screen keys."""
    return key_id in LATCHING_MODIFIER_KEY_IDS


def build_xdotool_key_spec(base_key, active_modifier_ids):
    """Build an xdotool key spec such as Control_L+Alt_L+t."""
    modifiers = [
        MODIFIER_XDOTOOL_KEYS[key_id]
        for key_id in MODIFIER_SEND_ORDER
        if key_id in active_modifier_ids
    ]
    return "+".join(modifiers + [base_key])


class FloatingKey:
    """
    A single floating key button window.

    Features:
        - Borderless, always-on-top
        - Draggable via click-and-hold
        - Clicking simulates key press via xdotool
        - Refocuses the previously active window before sending key
        - Visual flash feedback on click
        - Saves position on drag end
        - Per-category coloring for visual grouping
        - Semi-transparent for less screen obstruction
    """

    def __init__(self, root, key_id, manager):
        """
        Args:
            root:    The Tk root window (kept hidden).
            key_id:  ID from the key registry.
            manager: The FloatingKeyManager (holds focus tracking state).
        """
        self.root = root
        self.key_id = key_id
        self.manager = manager
        self.key_info = get_key_by_id(key_id)

        if not self.key_info:
            raise ValueError(f"Unknown key ID: {key_id}")

        self.xdotool_key = self.key_info["xdotool_key"]
        self.label_text = self.key_info["label"]
        self.is_sticky_modifier = is_latching_modifier(self.key_id)

        # Resolve per-category color scheme
        category = get_category_for_key(key_id)
        self.colors = get_floating_colors(category)

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False

        self._build_window()

    def _get_screen_bounds(self):
        """
        Return screen bounds as (left, top, width, height).

        Uses the X11 primary monitor when available. This avoids centering
        floating keys on the seam between multiple displays.
        """
        return _get_primary_monitor_bounds(self.root)

    def _clamp_to_visible(self, x, y, width, height):
        """
        Clamp a window rectangle so it remains visible.

        If the button is larger than the available area, place it at center
        of the screen axis so it remains as visible as possible.
        """
        left, top, screen_w, screen_h = self._get_screen_bounds()
        center_x = left + max(0, (screen_w - width) // 2)
        center_y = top + max(0, (screen_h - height) // 2)

        min_x = left + SCREEN_MARGIN
        min_y = top + SCREEN_MARGIN
        max_x = left + max(SCREEN_MARGIN, screen_w - width - SCREEN_MARGIN)
        max_y = top + max(SCREEN_MARGIN, screen_h - height - SCREEN_MARGIN)

        if width + (2 * SCREEN_MARGIN) > screen_w:
            clamped_x = center_x
        else:
            clamped_x = max(min_x, min(int(x), max_x))

        if height + (2 * SCREEN_MARGIN) > screen_h:
            clamped_y = center_y
        else:
            clamped_y = max(min_y, min(int(y), max_y))

        return clamped_x, clamped_y

    def _get_window_size(self):
        """Return current window size with minimum constraints."""
        self.window.update_idletasks()
        width = max(self.window.winfo_width(), self.window.winfo_reqwidth(), MIN_WIDTH)
        height = max(self.window.winfo_height(), self.window.winfo_reqheight(), MIN_HEIGHT)
        return width, height

    def set_position(self, x, y, width=None, height=None):
        """
        Set window position while ensuring it stays in the visible area.

        Optionally accepts explicit width/height to preserve size in geometry.
        """
        current_w, current_h = self._get_window_size()
        width = current_w if width is None else max(int(width), MIN_WIDTH)
        height = current_h if height is None else max(int(height), MIN_HEIGHT)

        clamped_x, clamped_y = self._clamp_to_visible(x, y, width, height)
        self.window.geometry(f"{width}x{height}+{clamped_x}+{clamped_y}")
        return clamped_x, clamped_y

    def _build_window(self):
        """Create the floating button window."""

        self.window = tk.Toplevel(self.root)

        # Use overrideredirect(True) so click the button does NOT
        # participate in the WM focus chain at all. This is how real
        # on-screen keyboards (onboard, florence) work on X11.
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)

        # Apply transparency (X11 compositing required)
        try:
            self.window.attributes("-alpha", FLOATING_OPACITY)
        except Exception:
            pass  # Gracefully ignore if compositor doesn't support it

        self.window.configure(bg=self.colors["border"])

        # ── Inner frame (acts as visual border) ──────────────────
        inner = tk.Frame(
            self.window,
            bg=self.colors["bg"],
            padx=2,
            pady=2,
        )
        inner.pack(padx=1, pady=1, fill="both", expand=True)

        # ── The button label ────────────────────────────────────
        self.btn_label = tk.Label(
            inner,
            text=self.label_text,
            font=("Monospace", 12, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            padx=PAD_X,
            pady=PAD_Y,
            cursor="hand2",
        )
        self.btn_label.pack(fill="both", expand=True)

        # ── Bind events ──────────────────────────────────────────

        # Left-click → simulate key press
        self.btn_label.bind("<Button-1>", self._on_press)
        self.btn_label.bind("<ButtonRelease-1>", self._on_release)

        # Drag via click-and-hold + mouse move
        self.btn_label.bind("<B1-Motion>", self._on_drag)

        # Hover effect
        self.btn_label.bind("<Enter>", self._on_hover_enter)
        self.btn_label.bind("<Leave>", self._on_hover_leave)

        # ── Set minimum size ─────────────────────────────────────
        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), MIN_WIDTH)
        h = max(self.window.winfo_reqheight(), MIN_HEIGHT)

        # ── Position: restored from config or default cascade ────
        saved_pos = get_saved_position(self.key_id)
        if saved_pos:
            x, y = saved_pos
        else:
            # Manager will reposition unsaved keys as a group.
            left, top, screen_w, screen_h = self._get_screen_bounds()
            x = left + ((screen_w - w) // 2)
            y = top + ((screen_h - h) // 2)

        self.set_position(x, y, width=w, height=h)

    # ── Event handlers ───────────────────────────────────────────

    def _on_press(self, event):
        """Record drag start position."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._is_dragging = False

    def _on_drag(self, event):
        """Move the window with the mouse."""
        self._is_dragging = True

        # Calculate new position
        x = self.window.winfo_x() + (event.x - self._drag_start_x)
        y = self.window.winfo_y() + (event.y - self._drag_start_y)

        self.set_position(x, y)

    def _on_release(self, event):
        """
        On release:
            - If it was a drag → save new position
            - If it was a click (no drag) → simulate key press
        """
        if self._is_dragging:
            # Save the new position
            width, height = self._get_window_size()
            x, y = self._clamp_to_visible(
                self.window.winfo_x(),
                self.window.winfo_y(),
                width,
                height,
            )
            self.window.geometry(f"{width}x{height}+{x}+{y}")
            save_key_position(self.key_id, x, y)
            self._is_dragging = False
        else:
            # It was a click → simulate key
            self._simulate_key()

    def _simulate_key(self):
        """
        Simulate the key press via xdotool.

        CRITICAL: We must refocus the user's previously active window
        before sending the keystroke, so it lands in their editor /
        terminal — not our floating button.
        """

        if self.is_sticky_modifier:
            self.manager.toggle_modifier(self.key_id)
            self._refresh_visual_state()
            return

        key_spec = build_xdotool_key_spec(
            self.xdotool_key,
            self.manager.active_modifier_keys,
        )

        last_wid = self.manager.last_focused_window

        try:
            if last_wid:
                # Refocus the user's window, then send the key to it
                subprocess.run(
                    ["xdotool", "windowfocus", "--sync", last_wid],
                    timeout=1,
                    check=False,
                )
                subprocess.run(
                    ["xdotool", "key", key_spec],
                    timeout=2,
                    check=False,
                )
            else:
                # Fallback: no tracked window — just send key blindly
                subprocess.run(
                    ["xdotool", "key", key_spec],
                    timeout=2,
                    check=False,
                )
        except FileNotFoundError:
            print("[floating_keys] Error: xdotool not found! Install with: sudo apt install xdotool")
        except subprocess.TimeoutExpired:
            print(f"[floating_keys] Warning: xdotool timed out for key '{self.xdotool_key}'")

        # Visual flash feedback after sending the key.
        self.btn_label.config(bg=self.colors["flash"], fg=self.colors["active_fg"])
        self.window.update_idletasks()

        # Reset color after brief flash
        self.window.after(
            120,
            self._refresh_visual_state,
        )

    def _on_hover_enter(self, event):
        """Lighten button on hover."""
        if not self._is_dragging and not self._is_latched_modifier():
            self.btn_label.config(bg=self.colors["active_bg"], fg=self.colors["active_fg"])

    def _on_hover_leave(self, event):
        """Reset button color on hover leave."""
        self._refresh_visual_state()

    def _is_latched_modifier(self):
        """Return whether this modifier is currently latched."""
        return self.is_sticky_modifier and self.manager.is_modifier_active(self.key_id)

    def _refresh_visual_state(self):
        """Refresh button color, keeping latched modifiers visibly selected."""
        if self._is_latched_modifier():
            self.btn_label.config(bg=self.colors["active_bg"], fg=self.colors["active_fg"])
        else:
            self.btn_label.config(bg=self.colors["bg"], fg=self.colors["fg"])

    def show(self):
        """Show the floating button."""
        self.window.deiconify()

    def hide(self):
        """Hide the floating button."""
        self.window.withdraw()

    def destroy(self):
        """Destroy the floating button window."""
        self.window.destroy()


class FloatingKeyManager:
    """
    Manages all the floating key buttons.

    Handles creation, showing, hiding, cleanup, and
    continuous focus tracking so keystrokes land in the
    correct target window (not our buttons).
    """

    def __init__(self, root):
        """
        Args:
            root: The hidden Tk root window.
        """
        self.root = root
        self.floating_keys = {}    # key_id → FloatingKey
        self._visible = True

        # ── Focus tracking ───────────────────────────────────────
        # We poll `xdotool getactivewindow` every 150ms and remember
        # the last window ID that ISN'T one of our own windows.
        # This lets us refocus the user's app before sending keys.
        self.last_focused_window = None
        self._our_window_ids = set()      # X11 window IDs of our buttons
        self._focus_poll_running = False
        self.active_modifier_keys = set()

    def is_modifier_active(self, key_id):
        """Return whether an on-screen modifier is latched."""
        return key_id in self.active_modifier_keys

    def toggle_modifier(self, key_id):
        """Toggle a sticky modifier and refresh all modifier button states."""
        if key_id in self.active_modifier_keys:
            self.active_modifier_keys.remove(key_id)
            # Release the modifier via xdotool
            if key_id in MODIFIER_XDOTOOL_KEYS:
                subprocess.run(
                    ["xdotool", "keyup", MODIFIER_XDOTOOL_KEYS[key_id]],
                    timeout=1,
                    check=False,
                )
        else:
            self.active_modifier_keys.add(key_id)
            # Press the modifier via xdotool
            if key_id in MODIFIER_XDOTOOL_KEYS:
                subprocess.run(
                    ["xdotool", "keydown", MODIFIER_XDOTOOL_KEYS[key_id]],
                    timeout=1,
                    check=False,
                )
        # Refresh all modifier buttons to show updated state
        self._refresh_all_modifier_buttons()

    def clear_all_modifiers(self):
        """Release all latched modifiers at once."""
        # Release modifiers in reverse order for natural key-up behavior
        for key_id in reversed(MODIFIER_SEND_ORDER):
            if key_id in self.active_modifier_keys:
                subprocess.run(
                    ["xdotool", "keyup", MODIFIER_XDOTOOL_KEYS[key_id]],
                    timeout=1,
                    check=False,
                )
        self.active_modifier_keys.clear()
        # Refresh all modifier buttons to show updated state
        self._refresh_all_modifier_buttons()

    def _refresh_all_modifier_buttons(self):
        """Refresh visual state of all modifier buttons."""
        for key_id in LATCHING_MODIFIER_KEY_IDS:
            if key_id in self.floating_keys:
                self.floating_keys[key_id]._refresh_visual_state()

    def activate_keys(self, key_ids):
        """
        Create floating buttons for the given key IDs.

        Destroys any previously active buttons first.

        Args:
            key_ids: list of key ID strings from the registry.
        """
        self.destroy_all()
        unsaved_keys = []

        for i, key_id in enumerate(key_ids):
            try:
                fk = FloatingKey(self.root, key_id, manager=self)

                if key_needs_spawn_position(key_id):
                    unsaved_keys.append(fk)

                self.floating_keys[key_id] = fk

            except ValueError as e:
                print(f"[floating_keys] Skipping unknown key: {e}")

        self._position_unsaved_keys(unsaved_keys)
        self._visible = True

        # Collect our X11 window IDs so the focus tracker can ignore them
        self._collect_our_window_ids()

        # Start continuous focus tracking
        if not self._focus_poll_running:
            self._focus_poll_running = True
            self._poll_focus()

    def _position_unsaved_keys(self, keys):
        """Place unsaved keys from the configured anchor with screen padding."""
        if not keys:
            return

        anchor = get_spawn_anchor()
        sizes = [fk._get_window_size() for fk in keys]
        positions = calculate_spawn_layout(sizes, keys[0]._get_screen_bounds(), anchor)
        for fk, (x, y, width, height) in zip(keys, positions):
            fk.set_position(x, y, width=width, height=height)

    def _collect_our_window_ids(self):
        """
        Grab the X11 window IDs of all our floating buttons + root.

        These are excluded from focus tracking so we only remember
        the user's actual application windows.
        """
        self._our_window_ids.clear()

        # Add the hidden root window
        try:
            root_hex = self.root.winfo_id()
            self._our_window_ids.add(str(root_hex))
        except Exception:
            pass

        # Add each floating key window
        for fk in self.floating_keys.values():
            try:
                wid_hex = fk.window.winfo_id()
                self._our_window_ids.add(str(wid_hex))
            except Exception:
                pass

    def _poll_focus(self):
        """
        Periodically check which window has focus.

        Runs every 200ms. Saves the last window ID that ISN'T
        one of our own floating buttons. This runs via Tk's
        `after()` so it's on the main thread — no threading issues.
        """
        if not self._visible:
            # Keep polling but less frequently when hidden
            self.root.after(500, self._poll_focus)
            return

        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            wid = result.stdout.strip()

            if wid and wid not in self._our_window_ids:
                self.last_focused_window = wid

        except Exception:
            pass  # xdotool failed — skip this cycle, no big deal

        # Schedule next poll
        try:
            self.root.after(200, self._poll_focus)
        except Exception:
            self._focus_poll_running = False

    def toggle_visibility(self):
        """Toggle all floating buttons visible/hidden."""
        if self._visible:
            self.hide_all()
        else:
            self.show_all()

    def show_all(self):
        """Show all floating buttons."""
        for fk in self.floating_keys.values():
            fk.show()
        self._visible = True

    def hide_all(self):
        """Hide all floating buttons."""
        for fk in self.floating_keys.values():
            fk.hide()
        self._visible = False

    def destroy_all(self):
        """Destroy all floating button windows."""
        self._focus_poll_running = False
        self.active_modifier_keys.clear()
        for fk in self.floating_keys.values():
            fk.destroy()
        self.floating_keys.clear()
        self._our_window_ids.clear()
        self._visible = False

    def is_visible(self):
        """Return whether buttons are currently visible."""
        return self._visible
