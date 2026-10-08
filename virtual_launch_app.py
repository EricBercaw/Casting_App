#!/usr/bin/env python3
"""Launch apps on the virtual desktop with isolated browser sessions.

Run from LXQt desktop icons or its application menu. The launch environment
(DESKTOP=:99, virtual DBus, virtual XDG_CONFIG_HOME) is inherited from LXQt.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def show_error(message):
    print(message, file=sys.stderr)
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror("Virtual Lubuntu", message)
        root.destroy()
    except Exception:
        pass


def find_desktop_app(kind):
    home = Path.home()
    paths = []
    for folder in (home / ".local/share/applications", home / "Desktop"):
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.desktop")))
    matches = []
    for path in paths:
        name = path.name.lower().replace("_", "-")
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        titles = [s.split("=", 1)[1].strip().lower()
                  for s in body.splitlines() if s.startswith("Name=")]
        title = titles[0] if titles else ""
        if kind == "visualizer":
            good = "music-visualizer" in name or "music visualizer" in title
        else:
            good = (("spotify" in name and ("lite" in name or "light" in name))
                    or ("spotify" in title and ("lite" in title or "light" in title)))
        if good and "Exec=" in body:
            matches.append(path)
    return matches[0] if matches else None


def launch(kind):
    home = Path.home()
    conf = home / ".config" / "apple-tv-cast"
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    if kind == "firefox":
        exe = shutil.which("firefox") or shutil.which("firefox-esr")
        if not exe:
            raise RuntimeError("Firefox is not installed.")
        # --no-remote prevents an existing physical-screen Firefox from
        # stealing a new virtual-screen window. Uses a separate profile.
        profile = conf / "virtual-firefox"
        profile.mkdir(parents=True, exist_ok=True)
        cmd = [exe, "--no-remote", "--profile", str(profile)]
    elif kind == "chromium":
        exe = (shutil.which("chromium-browser") or shutil.which("chromium")
               or shutil.which("google-chrome-stable") or shutil.which("google-chrome"))
        if not exe:
            raise RuntimeError("Chromium or Chrome is not installed.")
        profile = conf / "virtual-chromium"
        profile.mkdir(parents=True, exist_ok=True)
        cmd = [exe, f"--user-data-dir={profile}", "--ozone-platform=x11",
               "--disable-gpu", "--no-first-run"]
    elif kind in ("visualizer", "spotify"):
        app = find_desktop_app(kind)
        if app is None:
            expected = "Music Visualizer" if kind == "visualizer" else "Spotify Lite"
            raise RuntimeError(
                f"No {expected} desktop launcher was found in "
                "~/.local/share/applications or ~/Desktop. Install its "
                "desktop launcher first, or use the LXQt application menu."
            )
        if not shutil.which("gio"):
            raise RuntimeError("gio is missing (package libglib2.0-bin).")
        # These two custom apps normally read Spotifyd/MPRIS using playerctl.
        # Point them at the original user session bus for track metadata while
        # keeping their X11 windows on the independent :99 virtual display.
        host_bus = env.get("APPLETV_HOST_DBUS_ADDRESS", "")
        if host_bus:
            env["DBUS_SESSION_BUS_ADDRESS"] = host_bus
        cmd = ["gio", "launch", str(app)]
    else:
        raise RuntimeError("Unknown virtual app: " + kind)
    subprocess.Popen(cmd, env=env, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        launch(sys.argv[1] if len(sys.argv) > 1 else "")
    except (RuntimeError, OSError) as exc:
        show_error(str(exc))
        raise SystemExit(1)
