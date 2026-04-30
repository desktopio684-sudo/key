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

import subprocess
import tkinter as tk

from key_registry import get_key_by_id, get_category_for_key
from config_manager import save_key_position, get_saved_position

from shared_theme import FLOATING_OPACITY, get_floating_colors

# Minimum button size
MIN_WIDTH = 48
MIN_HEIGHT = 36

# Padding inside each button
PAD_X = 10
PAD_Y = 6


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

        # Resolve per-category color scheme
        category = get_category_for_key(key_id)
        self.colors = get_floating_colors(category)

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False

        self._build_window()

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
            # Default cascade position from top-right corner
            x = self.root.winfo_screenwidth() - w - 20
            y = 40

        self.window.geometry(f"{w}x{h}+{x}+{y}")

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

        self.window.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        """
        On release:
            - If it was a drag → save new position
            - If it was a click (no drag) → simulate key press
        """
        if self._is_dragging:
            # Save the new position
            x = self.window.winfo_x()
            y = self.window.winfo_y()
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

        # Visual flash feedback
        self.btn_label.config(bg=self.colors["flash"], fg=self.colors["active_fg"])
        self.window.update_idletasks()

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
                    ["xdotool", "key", "--clearmodifiers", self.xdotool_key],
                    timeout=2,
                    check=False,
                )
            else:
                # Fallback: no tracked window — just send key blindly
                subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", self.xdotool_key],
                    timeout=2,
                    check=False,
                )
        except FileNotFoundError:
            print("[floating_keys] Error: xdotool not found! Install with: sudo apt install xdotool")
        except subprocess.TimeoutExpired:
            print(f"[floating_keys] Warning: xdotool timed out for key '{self.xdotool_key}'")

        # Reset color after brief flash
        self.window.after(
            120,
            lambda: self.btn_label.config(bg=self.colors["bg"], fg=self.colors["fg"]),
        )

    def _on_hover_enter(self, event):
        """Lighten button on hover."""
        if not self._is_dragging:
            self.btn_label.config(bg=self.colors["active_bg"], fg=self.colors["active_fg"])

    def _on_hover_leave(self, event):
        """Reset button color on hover leave."""
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

    def activate_keys(self, key_ids):
        """
        Create floating buttons for the given key IDs.

        Destroys any previously active buttons first.

        Args:
            key_ids: list of key ID strings from the registry.
        """
        self.destroy_all()

        # Calculate cascade offset so buttons don't overlap
        screen_w = self.root.winfo_screenwidth()
        start_x = screen_w - 80
        start_y = 40
        offset_y = 50

        for i, key_id in enumerate(key_ids):
            try:
                fk = FloatingKey(self.root, key_id, manager=self)

                # If no saved position, cascade vertically
                saved = get_saved_position(key_id)
                if not saved:
                    x = start_x
                    y = start_y + (i * offset_y)

                    # Wrap to next column if off-screen
                    screen_h = self.root.winfo_screenheight()
                    if y + 50 > screen_h:
                        start_x -= 70
                        start_y = 40
                        y = start_y

                    fk.window.geometry(f"+{x}+{y}")

                self.floating_keys[key_id] = fk

            except ValueError as e:
                print(f"[floating_keys] Skipping unknown key: {e}")

        self._visible = True

        # Collect our X11 window IDs so the focus tracker can ignore them
        self._collect_our_window_ids()

        # Start continuous focus tracking
        if not self._focus_poll_running:
            self._focus_poll_running = True
            self._poll_focus()

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

        Runs every 150ms. Saves the last window ID that ISN'T
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
        for fk in self.floating_keys.values():
            fk.destroy()
        self.floating_keys.clear()
        self._our_window_ids.clear()
        self._visible = False

    def is_visible(self):
        """Return whether buttons are currently visible."""
        return self._visible
