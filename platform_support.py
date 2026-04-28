"""Platform abstraction for Voice2Shell."""

import subprocess
import sys
import threading

PLATFORM = {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform, "linux")

if PLATFORM == "macos":
    DEFAULT_FONT = "Menlo"
    AVAILABLE_TERMINALS = ["iTerm", "Terminal"]
    DEFAULT_TERMINAL = "iTerm"
    HOTKEY_OPTIONS = ["Right Option", "Right Command", "Ctrl+Space", "F5"]
elif PLATFORM == "linux":
    DEFAULT_FONT = "DejaVu Sans Mono"
    AVAILABLE_TERMINALS = ["gnome-terminal", "konsole", "xfce4-terminal", "alacritty", "xterm"]
    DEFAULT_TERMINAL = "gnome-terminal"
    HOTKEY_OPTIONS = ["Right Alt", "Right Super", "Ctrl+Space", "F5"]
else:
    DEFAULT_FONT = "Consolas"
    AVAILABLE_TERMINALS = ["PowerShell", "cmd", "Windows Terminal"]
    DEFAULT_TERMINAL = "PowerShell"
    HOTKEY_OPTIONS = ["Right Alt", "Right Win", "Ctrl+Space", "F5"]


def send_to_terminal(command: str, terminal_app: str) -> tuple:
    if PLATFORM == "macos":
        return _send_macos(command, terminal_app)
    elif PLATFORM == "linux":
        return _send_linux(command, terminal_app)
    else:
        return _send_windows(command, terminal_app)


def _send_macos(command: str, terminal_app: str) -> tuple:
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    if terminal_app == "iTerm":
        script = f'''
        tell application "iTerm"
            if (count of windows) > 0 then
                tell current session of current window
                    write text "{escaped}"
                end tell
            else
                create window with default profile
                tell current session of current window
                    write text "{escaped}"
                end tell
            end if
        end tell
        '''
    else:
        script = f'''
        tell application "Terminal"
            if (count of windows) > 0 then
                do script "{escaped}" in front window
            else
                do script "{escaped}"
            end if
        end tell
        '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        return (True, "")
    return (False, result.stderr.strip())


def _send_linux(command: str, terminal_app: str) -> tuple:
    try:
        result = subprocess.run(["which", "xdotool"], capture_output=True)
        if result.returncode != 0:
            return (False, "xdotool not found. Install with: sudo apt install xdotool")

        escaped = command.replace("\\", "\\\\")
        subprocess.run(
            ["xdotool", "search", "--name", terminal_app, "windowactivate", "--sync"],
            capture_output=True, timeout=3
        )
        subprocess.run(
            ["xdotool", "type", "--delay", "12", "--clearmodifiers", escaped],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["xdotool", "key", "Return"],
            capture_output=True, timeout=3
        )
        return (True, "")
    except subprocess.TimeoutExpired:
        return (False, "Timed out sending to terminal")
    except Exception as e:
        return (False, str(e))


def _send_windows(command: str, terminal_app: str) -> tuple:
    try:
        import pyautogui
        import win32gui
        import win32con

        title_hints = {
            "PowerShell": "PowerShell",
            "cmd": "Command Prompt",
            "Windows Terminal": "Windows Terminal",
        }
        hint = title_hints.get(terminal_app, terminal_app)

        target = None
        def enum_cb(hwnd, _):
            nonlocal target
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if hint.lower() in title.lower():
                    target = hwnd
        win32gui.EnumWindows(enum_cb, None)

        if target is None:
            return (False, f"No {terminal_app} window found")

        win32gui.ShowWindow(target, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(target)
        import time
        time.sleep(0.15)

        pyautogui.typewrite(command, interval=0.01)
        pyautogui.press("enter")
        return (True, "")
    except ImportError:
        return (False, "pyautogui or pywin32 not installed")
    except Exception as e:
        return (False, str(e))


class HotkeyListener:
    def __init__(self, on_press, on_release, hotkey_name="Right Option"):
        self._on_press = on_press
        self._on_release = on_release
        self._hotkey_name = hotkey_name
        self._active = False
        self._hold_start = 0
        self._threshold = 0.3

    def update_hotkey(self, hotkey_name: str):
        self._hotkey_name = hotkey_name

    def start(self):
        if PLATFORM == "macos":
            self._start_macos()
        else:
            self._start_pynput()

    def _start_macos(self):
        import Quartz
        import time

        HOTKEY_MAP = {
            "Right Option": {"flag": Quartz.kCGEventFlagMaskAlternate, "keycode": 61, "type": "modifier"},
            "Right Command": {"flag": Quartz.kCGEventFlagMaskCommand, "keycode": 54, "type": "modifier"},
            "Ctrl+Space": {"flag": Quartz.kCGEventFlagMaskControl, "keycode": 49, "type": "combo"},
            "F5": {"flag": None, "keycode": 96, "type": "key"},
        }

        listener = self

        def monitor_thread():
            def handler(proxy, event_type, event, refcon):
                keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                hk = HOTKEY_MAP.get(listener._hotkey_name)
                if not hk:
                    return event

                if hk["type"] == "modifier":
                    if event_type == Quartz.kCGEventFlagsChanged and keycode == hk["keycode"]:
                        flags = Quartz.CGEventGetFlags(event)
                        is_down = bool(flags & hk["flag"])
                        if is_down and not listener._active:
                            listener._active = True
                            listener._hold_start = time.time()
                            listener._on_press()
                        elif not is_down and listener._active:
                            listener._active = False
                            listener._on_release()

                elif hk["type"] == "combo":
                    if keycode == hk["keycode"]:
                        flags = Quartz.CGEventGetFlags(event)
                        ctrl_held = bool(flags & hk["flag"])
                        if event_type == Quartz.kCGEventKeyDown and ctrl_held:
                            if not listener._active:
                                listener._active = True
                                listener._hold_start = time.time()
                                listener._on_press()
                        elif event_type == Quartz.kCGEventKeyUp:
                            if listener._active:
                                listener._active = False
                                listener._on_release()

                elif hk["type"] == "key":
                    if keycode == hk["keycode"]:
                        if event_type == Quartz.kCGEventKeyDown and not listener._active:
                            listener._active = True
                            listener._hold_start = time.time()
                            listener._on_press()
                        elif event_type == Quartz.kCGEventKeyUp and listener._active:
                            listener._active = False
                            listener._on_release()

                return event

            mask = (Quartz.kCGEventKeyDown | Quartz.kCGEventKeyUp | Quartz.kCGEventFlagsChanged)
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                handler,
                None
            )
            if tap is None:
                return

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopDefaultMode)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()

        threading.Thread(target=monitor_thread, daemon=True).start()

    def _start_pynput(self):
        from pynput import keyboard
        import time

        KEY_MAP = {
            "Right Alt": {"key": keyboard.Key.alt_r, "type": "modifier"},
            "Right Super": {"key": keyboard.Key.cmd_r, "type": "modifier"},
            "Right Win": {"key": keyboard.Key.cmd_r, "type": "modifier"},
            "Ctrl+Space": {"ctrl_key": keyboard.Key.ctrl_l, "trigger": keyboard.Key.space, "type": "combo"},
            "F5": {"key": keyboard.Key.f5, "type": "key"},
        }

        listener = self
        ctrl_held = False

        def on_press(key):
            nonlocal ctrl_held
            hk = KEY_MAP.get(listener._hotkey_name)
            if not hk:
                return

            if hk["type"] == "modifier":
                if key == hk["key"] and not listener._active:
                    listener._active = True
                    listener._hold_start = time.time()
                    listener._on_press()
            elif hk["type"] == "combo":
                if key == hk["ctrl_key"]:
                    ctrl_held = True
                elif key == hk["trigger"] and ctrl_held and not listener._active:
                    listener._active = True
                    listener._hold_start = time.time()
                    listener._on_press()
            elif hk["type"] == "key":
                if key == hk["key"] and not listener._active:
                    listener._active = True
                    listener._hold_start = time.time()
                    listener._on_press()

        def on_release(key):
            nonlocal ctrl_held
            hk = KEY_MAP.get(listener._hotkey_name)
            if not hk:
                return

            if hk["type"] == "modifier":
                if key == hk["key"] and listener._active:
                    listener._active = False
                    listener._on_release()
            elif hk["type"] == "combo":
                if key == hk.get("ctrl_key"):
                    ctrl_held = False
                if (key == hk["trigger"] or key == hk.get("ctrl_key")) and listener._active:
                    listener._active = False
                    listener._on_release()
            elif hk["type"] == "key":
                if key == hk["key"] and listener._active:
                    listener._active = False
                    listener._on_release()

        kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        kb_listener.daemon = True
        kb_listener.start()
