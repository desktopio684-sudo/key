"""
tray_icon.py
============
System tray integration using pystray.

Right-click the tray icon to see all options:
    - Show Keys        → make floating buttons visible
    - Hide Keys        → hide floating buttons
    - Reconfigure Keys → reopen key selector (Ctrl+K)
    - ─────────────
    - Quit             → exit the application
"""

import threading
from PIL import Image, ImageDraw

try:
    import pystray
    from pystray import MenuItem, Menu
    PYSTRAY_AVAILABLE = True

    # Log which backend pystray selected (appindicator = menus work, xorg = broken)
    _backend = pystray.Icon.__module__
    print(f"[tray_icon] pystray backend: {_backend}")

    if "xorg" in _backend:
        print("[tray_icon] ⚠  xorg backend detected — right-click menus may not work!")
        print("[tray_icon]    Fix: enable system-site-packages so PyGObject (gi) is available.")

except ImportError:
    PYSTRAY_AVAILABLE = False
    print("[tray_icon] Warning: pystray not installed. System tray disabled.")
    print("[tray_icon] Install with: pip install pystray")


# ─── Icon generation ─────────────────────────────────────────────────

def _create_tray_icon_image(size=64):
    """
    Generate a clear keyboard-shaped tray icon using Pillow.

    Draws a rounded rectangle with small key squares inside
    to look like a miniature keyboard.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Background (rounded keyboard body) ───────────────────────
    margin = 4
    draw.rounded_rectangle(
        [margin, margin + 8, size - margin, size - margin],
        radius=8,
        fill="#89b4fa",
        outline="#45475a",
        width=2,
    )

    # ── Draw key rows ────────────────────────────────────────────
    key_color = "#1e1e2e"
    pad = 10
    key_h = 6
    gap_y = 4
    start_y = 20

    key_rows = [
        5,   # Top row:    5 keys
        4,   # Middle row: 4 keys
        3,   # Bottom row: 3 keys (space-bar shape)
    ]

    for row_idx, num_keys in enumerate(key_rows):
        y = start_y + row_idx * (key_h + gap_y)
        available_w = size - 2 * pad
        gap_x = 3
        key_w = (available_w - (num_keys - 1) * gap_x) // num_keys

        # Center the row
        total_row_w = num_keys * key_w + (num_keys - 1) * gap_x
        x_offset = pad + (available_w - total_row_w) // 2

        for k in range(num_keys):
            x = x_offset + k * (key_w + gap_x)
            draw.rounded_rectangle(
                [x, y, x + key_w, y + key_h],
                radius=2,
                fill=key_color,
            )

    return img


# ─── Tray icon class ─────────────────────────────────────────────────

class TrayIcon:
    """
    System tray icon with full right-click menu:
        - Show Keys
        - Hide Keys
        - Reconfigure Keys (Ctrl+K)
        - Separator
        - Quit

    Runs in a background thread so it doesn't block the Tk mainloop.
    """

    def __init__(self, on_toggle, on_show, on_hide, on_reconfigure, on_quit):
        """
        Args:
            on_toggle:      callable() — toggle floating key visibility
            on_show:        callable() — show all floating keys
            on_hide:        callable() — hide all floating keys
            on_reconfigure: callable() — reopen key selector
            on_quit:        callable() — quit the application
        """
        self.on_toggle = on_toggle
        self.on_show = on_show
        self.on_hide = on_hide
        self.on_reconfigure = on_reconfigure
        self.on_quit = on_quit
        self.icon = None
        self._thread = None
        self._stopped = False

    def start(self):
        """Start the tray icon in a background thread."""
        if not PYSTRAY_AVAILABLE:
            print("[tray_icon] pystray not available, skipping tray.")
            return

        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Create and run the pystray icon (blocks in its own thread)."""
        image = _create_tray_icon_image()

        # ── Full right-click menu ────────────────────────────────
        menu = Menu(
            MenuItem(
                "Show / Hide Keys",
                self._handle_toggle,
                default=True,   # Double-click / left-click action
            ),
            Menu.SEPARATOR,
            MenuItem("Show Keys", self._handle_show),
            MenuItem("Hide Keys", self._handle_hide),
            Menu.SEPARATOR,
            MenuItem("Reconfigure Keys  (Ctrl+K)", self._handle_reconfigure),
            Menu.SEPARATOR,
            MenuItem("Quit", self._handle_quit),
        )

        self.icon = pystray.Icon(
            name="onscreen-keys",
            icon=image,
            title="On-Screen Keyboard",
            menu=menu,
        )

        self.icon.run()

    # ── Menu handlers ────────────────────────────────────────────

    def _handle_toggle(self, icon, item):
        """Toggle key visibility."""
        self.on_toggle()

    def _handle_show(self, icon, item):
        """Show all floating keys."""
        self.on_show()

    def _handle_hide(self, icon, item):
        """Hide all floating keys."""
        self.on_hide()

    def _handle_reconfigure(self, icon, item):
        """Reopen the key selector."""
        self.on_reconfigure()

    def _handle_quit(self, icon, item):
        """Quit the application cleanly."""
        if self.icon and not self._stopped:
            self._stopped = True
            self.icon.stop()
        self.on_quit()

    def stop(self):
        """
        Stop the tray icon safely.

        Idempotent — calling multiple times is harmless.
        Joins the thread with a timeout (2s) so shutdown
        doesn't hang if pystray gets stuck.
        """
        if self._stopped:
            return

        self._stopped = True

        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass  # Already stopped

        # Wait briefly for the pystray thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
