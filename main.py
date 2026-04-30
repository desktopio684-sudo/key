"""
main.py
=======
Entry point for the On-Screen Keyboard application.

Flow:
    1. Load saved config
    2. If no keys configured → show the key selector
    3. If keys configured → launch floating keys immediately
    4. Start system tray icon in background
    5. Bind global hotkeys:
       - Ctrl+K opens key selector
       - Ctrl+H toggles key visibility (hide/show)
    6. Run Tkinter mainloop

Shortcuts:
    Ctrl+K  → Open the key selector window
    Ctrl+H  → Hide/Show floating keys

Graceful Shutdown:
    - Ctrl+C in terminal       → clean exit
    - Type "quit" / "exit"     → clean exit
    - SIGTERM / SIGHUP         → clean exit
    - Tray → Quit              → clean exit
"""

import sys
import os
import signal
import atexit
import subprocess
import threading
import tkinter as tk
import shutil
import logging

from config_manager import load_config, flush_config
from key_selector import KeySelectorWindow
from floating_keys import FloatingKeyManager
from tray_icon import TrayIcon


class OnScreenKeyboardApp:
    """
    Main application controller.

    Coordinates the key selector, floating buttons, system tray,
    and global keyboard shortcut.

    Handles graceful shutdown from:
        - Ctrl+C (SIGINT)
        - SIGTERM / SIGHUP
        - Typing "quit" or "exit" in the terminal
        - Tray → Quit
        - atexit fallback
    """

    def __init__(self):
        # ── Shutdown guard (prevents double-cleanup) ─────────────
        self._shutting_down = False
        self._shutdown_lock = threading.Lock()

        # ── Hidden root window (never shown) ─────────────────────
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("On-Screen Keyboard")

        self._selector_open = False

        # ── Thread-Safe Event Bindings ───────────────────────────
        self.root.bind("<<TrayToggle>>", lambda e: self.key_manager.toggle_visibility())
        self.root.bind("<<TrayShow>>", lambda e: self.key_manager.show_all())
        self.root.bind("<<TrayHide>>", lambda e: self.key_manager.hide_all())
        self.root.bind("<<TrayReconfigure>>", lambda e: self._open_selector())
        self.root.bind("<<AppQuit>>", lambda e: self._quit())

        # ── Core components ──────────────────────────────────────
        self.key_manager = FloatingKeyManager(self.root)
        self.tray = TrayIcon(
            on_toggle=lambda: self.root.event_generate("<<TrayToggle>>", when="tail"),
            on_show=lambda: self.root.event_generate("<<TrayShow>>", when="tail"),
            on_hide=lambda: self.root.event_generate("<<TrayHide>>", when="tail"),
            on_reconfigure=lambda: self.root.event_generate("<<TrayReconfigure>>", when="tail"),
            on_quit=lambda: self.root.event_generate("<<AppQuit>>", when="tail"),
            on_clear_modifiers=lambda: self.key_manager.clear_all_modifiers(),
        )

        # ── Register shutdown hooks ──────────────────────────────
        self._register_signal_handlers()
        atexit.register(self._atexit_cleanup)

        # Catch root window destruction (e.g. via WM or unexpected close)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        # Logging — configured in main() before app creation
        self._logger = logging.getLogger("onscreen-keys.OnScreenKeyboardApp")

    def start(self):
        """Launch the application."""
        self._logger.info("Starting On-Screen Keyboard...")

        config = load_config()
        selected_keys = config.get("selected_keys", [])

        if selected_keys:
            self._logger.info(f"Loading {len(selected_keys)} saved key(s)...")
            self.key_manager.activate_keys(selected_keys)
        else:
            self._logger.info("No keys configured. Opening selector...")
            self._open_selector()

        self.tray.start()
        self._start_hotkey_listener()
        self._start_terminal_listener()

        self._logger.info("On-Screen Keyboard is running.")
        self._logger.info("Right-click the tray icon for options.")
        self._logger.info("Press Ctrl+K to open the key selector.")
        self._logger.info("Press Ctrl+H to hide/show floating keys.")
        self.root.mainloop()

    # ── Global hotkeys (Ctrl+K / Ctrl+H) ─────────────────────────

    def _start_hotkey_listener(self):
        """
        Poll for Ctrl+K using a hidden Tk binding approach.

        We create a tiny transparent window that grabs
        the keyboard shortcut via X11. This avoids needing
        a separate dependency like `keyboard` or `pynput`.
        """
        # Use xdotool to set up a global hotkey listener
        # We'll poll via Tk's after() method instead — simpler and reliable
        self._setup_xdotool_hotkey()

    def _setup_xdotool_hotkey(self):
        """
        Register Ctrl+K / Ctrl+H globally using X11 key grabbing.
        Falls back to periodic polling if xbindkeys is not available.

        Simpler approach: use Tk's bind on a small always-present window.
        """
        # Create a tiny 1x1 transparent window for catching hotkeys
        self._hotkey_win = tk.Toplevel(self.root)
        self._hotkey_win.overrideredirect(True)
        self._hotkey_win.attributes("-alpha", 0.0)       # Fully transparent
        self._hotkey_win.attributes("-topmost", True)
        self._hotkey_win.geometry("1x1+0+0")

        # Unfortunately Tk can only capture key events when focused.
        # For truly global hotkeys on X11, we use xdotool's key listening.
        # Let's use a subprocess-based approach with `xbindkeys` or
        # fall back to watching for the key combo.
        self._start_global_hotkey_process()

    def _start_global_hotkey_process(self):
        """
        Use `xdotool` search to create a global hotkey by listening
        to X11 key events via subprocess.

        We spawn a background process that watches for Ctrl+K
        and sends a signal back to our app.
        """
        import threading

        def _hotkey_watcher():
            """
            Use `xinput` or `xev` to watch for Ctrl+K.
            Simpler: use `xdotool`'s `getactivewindow` with periodic check.

            Most reliable for our use case: just use pynput if available,
            otherwise fall back to a fifo-based xdotool approach.
            """
            try:
                # Try using python-xlib directly for key grabbing
                from Xlib import X, XK
                from Xlib.display import Display

                disp = Display()
                root_win = disp.screen().root

                keycode_open_selector = disp.keysym_to_keycode(XK.XK_k)
                keycode_toggle_visibility = disp.keysym_to_keycode(XK.XK_h)
                hotkey_keycodes = {
                    keycode_open_selector: "<<TrayReconfigure>>",
                    keycode_toggle_visibility: "<<TrayToggle>>",
                }

                root_win.grab_key(
                    keycode_open_selector,
                    X.ControlMask,
                    True,
                    X.GrabModeAsync,
                    X.GrabModeAsync,
                )
                root_win.grab_key(
                    keycode_toggle_visibility,
                    X.ControlMask,
                    True,
                    X.GrabModeAsync,
                    X.GrabModeAsync,
                )

                # Also grab with NumLock, CapsLock, etc.
                for extra_mod in [0, X.Mod2Mask, X.LockMask, X.Mod2Mask | X.LockMask]:
                    root_win.grab_key(
                        keycode_open_selector,
                        X.ControlMask | extra_mod,
                        True,
                        X.GrabModeAsync,
                        X.GrabModeAsync,
                    )
                    root_win.grab_key(
                        keycode_toggle_visibility,
                        X.ControlMask | extra_mod,
                        True,
                        X.GrabModeAsync,
                        X.GrabModeAsync,
                    )

                print("[main] Global hotkeys registered ✓ (Ctrl+K, Ctrl+H)")

                while True:
                    event = disp.next_event()
                    if event.type == X.KeyPress:
                        target_event = hotkey_keycodes.get(event.detail)
                        if target_event:
                            self.root.event_generate(target_event, when="tail")

            except ImportError:
                print("[main] Warning: python-xlib not available for global hotkey.")
                print("[main] Ctrl+K/Ctrl+H shortcuts disabled. Use tray icon instead.")
            except Exception as e:
                print(f"[main] Warning: Could not register global hotkey: {e}")
                print("[main] Ctrl+K/Ctrl+H shortcuts disabled. Use tray icon instead.")

        thread = threading.Thread(target=_hotkey_watcher, daemon=True)
        thread.start()

    # ── Actions ──────────────────────────────────────────────────

    def _open_selector(self):
        """Open the key selector window (called from tray, hotkey, or startup)."""
        if self._selector_open:
            return

        self._selector_open = True

        def on_activate(selected_key_ids):
            """Callback when user clicks Activate in the selector."""
            self._selector_open = False
            print(f"[main] Activating {len(selected_key_ids)} key(s)...")
            self.key_manager.activate_keys(selected_key_ids)

        def on_clear():
            """Callback when user clears all selected keys."""
            print("[main] Clearing all active keys...")
            self.key_manager.destroy_all()

        # Schedule on main thread (important for Tk)
        def create_selector():
            selector = KeySelectorWindow(
                on_activate_callback=on_activate,
                parent_root=self.root,
                on_clear_callback=on_clear,
            )
            # Handle window close (X button)
            selector.window.protocol(
                "WM_DELETE_WINDOW",
                lambda: self._on_selector_close(selector),
            )

        create_selector()

    def _on_selector_close(self, selector):
        """Handle the selector window being closed without activating."""
        self._selector_open = False
        selector.window.destroy()

        # If no keys are active, nothing to show
        if not self.key_manager.floating_keys:
            print("[main] No keys selected. App is idle. Use tray to reconfigure.")

    # ── Signal & Terminal Shutdown ────────────────────────────────

    def _register_signal_handlers(self):
        """
        Register OS signal handlers for graceful shutdown.

        Handles:
            SIGINT  → Ctrl+C in terminal
            SIGTERM → kill / systemd stop
            SIGHUP  → terminal closed
        """
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                signal.signal(sig, self._signal_handler)
            except (OSError, ValueError):
                # Some signals can't be caught on certain platforms
                pass

        # Tkinter swallows SIGINT by default. We need a periodic poll
        # on the mainloop so Python's signal handler actually fires.
        self._install_sigint_poll()

    def _install_sigint_poll(self):
        """
        Tkinter's mainloop blocks Python's signal delivery. A tiny
        recurring `after()` call lets Python process pending signals
        (like Ctrl+C) between Tk events.

        Without this, pressing Ctrl+C in the terminal appears to do
        nothing until the app receives another Tk event.
        """
        if not self._shutting_down:
            try:
                self.root.after(200, self._install_sigint_poll)
            except tk.TclError:
                pass  # Root already destroyed

    def _signal_handler(self, signum, frame):
        """
        Handle OS signals by scheduling a clean shutdown on the Tk thread.

        IMPORTANT: Signal handlers run asynchronously — we MUST NOT
        touch Tk widgets directly here. Use `after()` to defer to the loop.
        """
        sig_name = signal.Signals(signum).name
        self._logger.warning(f"Received {sig_name} — shutting down gracefully...")

        try:
            self.root.after(0, self._quit)
        except tk.TclError:
            self._force_cleanup()
            sys.exit(0)

    def _start_terminal_listener(self):
        """
        Spawn a daemon thread that reads stdin for "quit" / "exit".

        This lets users type a command to stop the app gracefully,
        which is especially nice when running from a terminal.

        The thread is a daemon, so it dies automatically if the
        main thread exits without going through this path.
        """
        # Only listen if stdin is a real terminal (not piped/redirected)
        if not sys.stdin.isatty():
            return

        def _listen():
            quit_commands = {"quit", "exit", "q", "stop"}
            try:
                while not self._shutting_down:
                    line = sys.stdin.readline()

                    # EOF (terminal closed)
                    if not line:
                        break

                    cmd = line.strip().lower()
                    if cmd in quit_commands:
                        print(f'[main] Received "{cmd}" command — shutting down...')
                        try:
                            self.root.event_generate("<<AppQuit>>", when="tail")
                        except tk.TclError:
                            self._force_cleanup()
                            os._exit(0)
                        break

            except (EOFError, OSError):
                # stdin closed or unreadable — nothing to do
                pass

        thread = threading.Thread(target=_listen, name="TerminalListener", daemon=True)
        thread.start()

    def _quit(self):
        """
        Clean, idempotent shutdown.

        Safe to call from any thread or callback — uses a lock
        to guarantee exactly-once execution, then schedules
        actual cleanup on the Tk main thread.
        """
        with self._shutdown_lock:
            if self._shutting_down:
                return   # Already running — skip duplicate
            self._shutting_down = True

        # Schedule all widget destruction on Tk main thread
        self.root.after(0, self._quit_in_main_thread)

    def _quit_in_main_thread(self):
        """Run the actual cleanup — MUST be called from Tk main thread."""
        self._logger.info("Shutting down...")

        try:
            self.key_manager.destroy_all()
        except Exception as e:
            self._logger.warning(f"Warning during key cleanup: {e}")

        try:
            self.tray.stop()
        except Exception as e:
            self._logger.warning(f"Warning during tray cleanup: {e}")

        try:
            flush_config()
        except Exception as e:
            self._logger.warning(f"Warning during config flush: {e}")

        self._destroy_root()
        self._logger.info("Goodbye!")

    def _destroy_root(self):
        """
        Destroy the Tk root window, which exits the mainloop.

        Separated into its own method so it runs inside the
        Tk event loop thread (via `after()`).
        """
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass  # Already destroyed

    def _force_cleanup(self):
        """
        Emergency cleanup when the Tk root is already gone.

        Called as a last resort from signal handlers or atexit
        when `root.after()` is no longer available.
        """
        try:
            self.tray.stop()
        except Exception:
            pass

        try:
            flush_config()
        except Exception:
            pass

    def _atexit_cleanup(self):
        """
        atexit fallback — runs when Python interpreter is shutting down.

        This is the safety net that catches any edge case where
        the app exits without going through `_quit()` first
        (e.g. unhandled exception, os._exit elsewhere, etc.).
        """
        if not self._shutting_down:
            print("[main] atexit cleanup triggered.")
            self._force_cleanup()


# ─── Entry point ─────────────────────────────────────────────────────

def _check_xdotool():
    """Return True if xdotool is available, False otherwise."""
    return shutil.which("xdotool") is not None


def _setup_logging():
    """Configure logging to file and stderr."""
    log_dir = os.path.expanduser("~/.config/onscreen-keys")
    log_file = os.path.join(log_dir, "app.log")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )
    return logging.getLogger("onscreen-keys")


def main():
    """Create and start the application."""
    logger = _setup_logging()

    # Check for xdotool before doing anything else
    if not _check_xdotool():
        logger.error("xdotool not found — this app requires it to simulate key presses")
        logger.error("Install with: sudo apt install xdotool")
        tk.messagebox.showerror(
            "Missing Dependency",
            "xdotool is required but not installed.\n\n"
            "Install with: sudo apt install xdotool",
        )
        sys.exit(1)

    print("=" * 50)
    print("  ⌨  On-Screen Keyboard for Broken Keys")
    print("  ──────────────────────────────────────")
    print("  Shortcuts:")
    print("    Ctrl+K  → Open key selector")
    print("    Ctrl+H  → Hide/Show floating keys")
    print("  Tray Icon:")
    print("    Right-click → Show/Hide, Reconfigure, Quit")
    print("  Usage:")
    print("    Click a key  → Simulates key press")
    print("    Drag a key   → Reposition it")
    print("=" * 50)

    app = OnScreenKeyboardApp()
    app.start()


if __name__ == "__main__":
    main()
