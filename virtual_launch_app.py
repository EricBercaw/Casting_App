#!/usr/bin/env python3
"""Launch applications only on the Apple TV Cast virtual X11 desktop (:99).

Firefox/Chromium get independent browser profiles so already-open windows on
HDMI-2 cannot steal these launches. Snap browser profiles live inside their
own snap common directories, which are writable under Snap confinement.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DISPLAY = ":99"
CACHE = Path.home() / ".cache" / "apple-tv-cast"
LOG = CACHE / "virtual-apps.log"


def show_error(message: str) -> None:
    print(message, file=sys.stderr)
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror("Virtual Screen App Launcher", message)
        root.destroy()
    except Exception:
        pass


def find_desktop_app(kind: str) -> Path | None:
    home = Path.home()
    paths = []
    for folder in (home / ".local/share/applications", home / "Desktop"):
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.desktop")))
    for path in paths:
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        filename = path.name.lower().replace("_", "-")
        titles = [line.split("=", 1)[1].strip().lower()
                  for line in body.splitlines() if line.startswith("Name=")]
        title = titles[0] if titles else ""
        if kind == "visualizer":
            match = "music-visualizer" in filename or "music visualizer" in title
        else:
            match = (("spotify" in filename and ("lite" in filename or "light" in filename))
                     or ("spotify" in title and ("lite" in title or "light" in title)))
        if match and "Exec=" in body:
            return path
    return None


def app_command(kind: str, env: dict[str, str]) -> list[str]:
    home = Path.home()
    if kind == "terminal":
        exe = (shutil.which("qterminal") or shutil.which("lxterminal")
               or shutil.which("xfce4-terminal") or shutil.which("xterm"))
        if not exe:
            raise RuntimeError("No terminal emulator found. Install one: sudo apt install qterminal")
        # Keep the virtual D-Bus bus for QTerminal: do not route to HDMI-2.
        return [exe]

    if kind == "firefox":
        # Prefer the actual snap launcher when installed, rather than the
        # Ubuntu deb-to-snap transition wrapper in /usr/bin/firefox.
        snap_exe = Path("/snap/bin/firefox")
        is_snap = snap_exe.exists()
        exe = str(snap_exe) if is_snap else (shutil.which("firefox") or shutil.which("firefox-esr"))
        if not exe:
            raise RuntimeError("Firefox is not installed.")
        profile = (home / "snap/firefox/common/apple-tv-virtual-profile" if is_snap
                   else home / ".mozilla/apple-tv-virtual-profile")
        profile.mkdir(parents=True, exist_ok=True)
        return [exe, "--no-remote", "--profile", str(profile), "--new-window", "about:blank"]

    if kind == "chromium":
        snap_exe = Path("/snap/bin/chromium")
        is_snap = snap_exe.exists()
        exe = str(snap_exe) if is_snap else (
            shutil.which("chromium-browser") or shutil.which("chromium")
            or shutil.which("google-chrome-stable") or shutil.which("google-chrome"))
        if not exe:
            raise RuntimeError("Chromium or Chrome is not installed.")
        profile = (home / "snap/chromium/common/apple-tv-virtual-profile" if is_snap
                   else home / ".config/apple-tv-cast/virtual-chromium")
        profile.mkdir(parents=True, exist_ok=True)
        return [exe, f"--user-data-dir={profile}", "--ozone-platform=x11",
                "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--new-window", "about:blank"]

    if kind in ("visualizer", "spotify"):
        app = find_desktop_app(kind)
        if app is None:
            label = "Music Visualizer" if kind == "visualizer" else "Spotify Lite"
            raise RuntimeError(f"Could not find a {label} desktop launcher in "
                               "~/.local/share/applications or ~/Desktop.")
        gio = shutil.which("gio")
        if not gio:
            raise RuntimeError("gio is missing. Install: sudo apt install libglib2.0-bin")
        return [gio, "launch", str(app)]

    raise RuntimeError("Unknown virtual screen application: " + kind)


def launch(kind: str) -> None:
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    env["XDG_SESSION_TYPE"] = "x11"
    env.pop("WAYLAND_DISPLAY", None)

    if kind in ("firefox", "chromium"):
        # The private LXQt XDG_CONFIG_HOME can be inaccessible to confined
        # Snap applications. Their own profiles still remain independent.
        env.pop("XDG_CONFIG_HOME", None)
        env["MOZ_ENABLE_WAYLAND"] = "0"
        # Snap desktop portal and browser integrations generally need the real
        # logged-in user D-Bus session, not our miniature LXQt session bus.
        host_bus = env.get("APPLETV_HOST_DBUS_ADDRESS", "")
        if host_bus:
            env["DBUS_SESSION_BUS_ADDRESS"] = host_bus
    elif kind in ("visualizer", "spotify"):
        host_bus = env.get("APPLETV_HOST_DBUS_ADDRESS", "")
        if host_bus:
            env["DBUS_SESSION_BUS_ADDRESS"] = host_bus

    cmd = app_command(kind, env)
    CACHE.mkdir(parents=True, exist_ok=True)
    with LOG.open("ab") as output:
        output.write((f"\n=== Virtual desktop launch: {kind} ===\n"
                      f"Command: {cmd[0]}\n").encode("utf-8"))
        output.flush()
        process = subprocess.Popen(cmd, env=env, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT)
    # Catch wrappers failing immediately. Keep real diagnostics in the log.
    time.sleep(0.7)
    if process.poll() not in (None, 0):
        raise RuntimeError(
            f"{kind.title()} exited with status {process.returncode}.\n"
            f"See: {LOG}\n"
            f"Try launching manually in the virtual terminal if it persists."
        )


if __name__ == "__main__":
    try:
        launch(sys.argv[1] if len(sys.argv) > 1 else "")
    except (RuntimeError, OSError) as exc:
        show_error(str(exc))
        raise SystemExit(1)
