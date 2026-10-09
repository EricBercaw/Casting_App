"""Virtual Lubuntu-style desktop for Apple TV Cast.

Keeps physical X11 session untouched.  Captured desktop lives on a separate
Xvfb server (:99), running its own PCManFM-Qt desktop and Openbox without an LXQt panel.
All preview VNC connections are restricted to localhost.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


class VirtualScreenError(RuntimeError):
    """A problem with the independent desktop that the UI should display."""


class VirtualScreenManager:
    DISPLAY = ":99"
    SCREEN = "1920x1080x24"
    VNC_PORT = 5999
    PACKAGES = (
        "xvfb openbox lxqt-panel pcmanfm-qt lxqt-runner "
        "dbus-x11 x11vnc tigervnc-viewer x11-utils x11-xserver-utils"
    )

    def __init__(self):
        self.xvfb = None
        self.desktop_session = None
        self.vnc_server = None
        self.viewer = None
        self.browser = None
        self.opened_apps = []

        self.cache_dir = Path.home() / ".cache" / "apple-tv-cast"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.cache_dir / "virtual-screen.log"
        self.bus_file = self.cache_dir / "virtual-session-bus"
        self.virtual_config = Path.home() / ".config" / "apple-tv-cast" / "virtual-lxqt"
        self.desktop_dir = Path.home() / ".local" / "share" / "apple-tv-cast" / "virtual-desktop"

    def _environment(self, *, session_bus=False):
        env = os.environ.copy()
        env["DISPLAY"] = self.DISPLAY
        env["XDG_SESSION_TYPE"] = "x11"
        env["XDG_CURRENT_DESKTOP"] = "LXQt"
        env["DESKTOP_SESSION"] = "Lubuntu"
        env["XDG_SESSION_DESKTOP"] = "Lubuntu"
        env["XDG_MENU_PREFIX"] = "lxqt-"
        env["QT_QPA_PLATFORMTHEME"] = "lxqt"
        env["XDG_CONFIG_HOME"] = str(self.virtual_config)
        # Spotifyd/playerctl and the visualizer may need the MPRIS bus from
        # the actual logged-in desktop, not the virtual shell's private bus.
        real_bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
        if not real_bus and os.environ.get("XDG_RUNTIME_DIR"):
            real_bus = "unix:path=" + os.environ["XDG_RUNTIME_DIR"] + "/bus"
        if real_bus:
            env["APPLETV_HOST_DBUS_ADDRESS"] = real_bus
        env.pop("WAYLAND_DISPLAY", None)
        if session_bus:
            try:
                address = self.bus_file.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                address = ""
            if address:
                env["DBUS_SESSION_BUS_ADDRESS"] = address
        return env

    def capture_environment(self):
        """Change only X11 video source, preserving existing physical audio bus."""
        env = os.environ.copy()
        env["DISPLAY"] = self.DISPLAY
        env.pop("WAYLAND_DISPLAY", None)
        return env

    def _ready(self):
        try:
            result = subprocess.run(
                ["xdpyinfo", "-display", self.DISPLAY],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _spawn(self, command, *, virtual=True, session_bus=False):
        with self.log_path.open("ab") as output:
            return subprocess.Popen(
                command,
                env=(self._environment(session_bus=session_bus)
                     if virtual else os.environ.copy()),
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
            )

    def _prepare_virtual_desktop(self):
        self.virtual_config.mkdir(parents=True, exist_ok=True)
        self.desktop_dir.mkdir(parents=True, exist_ok=True)

        # A private Desktop directory prevents shortcuts appearing on HDMI-2.
        dirs_path = self.virtual_config / "user-dirs.dirs"
        if not dirs_path.exists():
            dirs_path.write_text(
                'XDG_DESKTOP_DIR="$HOME/.local/share/apple-tv-cast/virtual-desktop"\n'
                'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n',
                encoding="utf-8",
            )

        launch_file = Path(__file__).with_name("virtual_launch_app.py")
        if not launch_file.exists():
            return

        choices = (
            ("Firefox", "firefox", "firefox"),
            ("Chromium", "chromium", "chromium"),
            ("Music Visualizer", "visualizer", "audio-x-generic"),
            ("Spotify Lite", "spotify", "multimedia-player"),
            ("Terminal", "terminal", "utilities-terminal"),
        )
        for name, arg, icon in choices:
            path = self.desktop_dir / (name.replace(" ", "-").lower() + ".desktop")
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={name}\n"
                f"Icon={icon}\n"
                f'Exec={sys.executable} "{launch_file}" {arg}\n'
                "Terminal=false\n"
                "Categories=AudioVideo;\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
            gio = shutil.which("gio")
            if gio:
                try:
                    subprocess.run(
                        [gio, "set", "-t", "string", str(path), "metadata::trusted", "true"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2, check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass

    def _start_desktop_session(self):
        required = ("dbus-run-session", "openbox", "pcmanfm-qt")
        missing = [cmd for cmd in required if not shutil.which(cmd)]
        if missing:
            raise VirtualScreenError(
                "Required Lubuntu desktop components are missing: "
                + ", ".join(missing)
                + ". Install with: sudo apt install " + self.PACKAGES
            )
        self._prepare_virtual_desktop()
        try:
            self.bus_file.unlink(missing_ok=True)
        except OSError:
            pass

        # Separate D-Bus bus avoids reusing the physical desktop's app session.
        # Start desktop *components* instead of a second login/session manager:
        # this avoids LXQt's user-wide service and power-management autostarts.
        launch_script = """
            umask 077
            printf '%s' "$DBUS_SESSION_BUS_ADDRESS" > "$VIRTUAL_BUS_FILE"
            xset s off -dpms >/dev/null 2>&1 || true
            openbox --sm-disable &
            wm=$!
            pcmanfm-qt --desktop --profile=apple-tv-virtual &
            if command -v lxqt-runner >/dev/null 2>&1; then
                lxqt-runner &
            fi
            wait "$wm"
        """
        env = self._environment()
        env["VIRTUAL_BUS_FILE"] = str(self.bus_file)
        with self.log_path.open("ab") as output:
            self.desktop_session = subprocess.Popen(
                ["dbus-run-session", "--", "bash", "-c", launch_script],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
            )

        # Fail early if the desktop process cannot be started.
        for _ in range(25):
            if self.desktop_session.poll() is not None:
                break
            if self.bus_file.exists() and self.bus_file.stat().st_size > 0:
                return
            time.sleep(0.10)
        if self.desktop_session.poll() is not None:
            raise VirtualScreenError(
                "Could not start virtual Lubuntu desktop. See " + str(self.log_path)
            )
        raise VirtualScreenError(
            "Virtual desktop did not initialize its D-Bus session. See "
            + str(self.log_path)
        )

    def ensure_started(self):
        """Start Xvfb and the private desktop on :99 without touching :0."""
        if self.xvfb is None:
            if self._ready():
                raise VirtualScreenError(
                    "DISPLAY=:99 is already in use by another program. "
                    "Close that display before starting Virtual Screen."
                )
            if not shutil.which("Xvfb") or not shutil.which("xdpyinfo"):
                raise VirtualScreenError(
                    "Xvfb or xdpyinfo is missing. Run: sudo apt install "
                    + self.PACKAGES
                )
            self.xvfb = self._spawn(
                ["Xvfb", self.DISPLAY,
                 "-screen", "0", self.SCREEN,
                 "-nolisten", "tcp", "-noreset"],
                virtual=False,
            )
            for _ in range(40):
                if self._ready():
                    break
                if self.xvfb.poll() is not None:
                    break
                time.sleep(0.10)
            if not self._ready():
                self._terminate(self.xvfb)
                self.xvfb = None
                raise VirtualScreenError(
                    "Cannot start Xvfb on :99. See " + str(self.log_path)
                )

        if not self._ready():
            raise VirtualScreenError(
                "Virtual display :99 stopped unexpectedly. Restart casting app."
            )
        if self.desktop_session is None or self.desktop_session.poll() is not None:
            self._start_desktop_session()

    def open_browser(self):
        """Existing 'Open Browser' button launches isolated virtual Chromium."""
        self.ensure_started()
        browser = shutil.which("chromium-browser") or shutil.which("chromium")
        if not browser:
            browser = shutil.which("google-chrome-stable") or shutil.which("google-chrome")
        if not browser:
            raise VirtualScreenError("Chromium or Chrome is not installed.")
        profile = (Path.home() / ".config" / "apple-tv-cast" / "virtual-chromium")
        profile.mkdir(parents=True, exist_ok=True)
        self.browser = self._spawn(
            [browser,
             f"--user-data-dir={profile}",
             "--ozone-platform=x11",
             "--disable-gpu",
             "--no-first-run",
             "--no-default-browser-check",
             "--window-size=1280,720", "about:blank"],
            session_bus=True,
        )

    def open_viewer(self):
        """Open controllable VNC viewer on the physical display."""
        self.ensure_started()
        if not shutil.which("x11vnc"):
            raise VirtualScreenError("Missing x11vnc. Run: sudo apt install x11vnc")
        vncviewer = shutil.which("vncviewer") or shutil.which("xtigervncviewer")
        if not vncviewer:
            raise VirtualScreenError(
                "Missing VNC viewer. Run: sudo apt install tigervnc-viewer"
            )
        if self.vnc_server is None or self.vnc_server.poll() is not None:
            self.vnc_server = self._spawn(
                ["x11vnc", "-display", self.DISPLAY,
                 "-localhost", "-nopw", "-forever", "-shared",
                 "-rfbport", str(self.VNC_PORT), "-quiet"]
            )
            time.sleep(0.35)
            if self.vnc_server.poll() is not None:
                raise VirtualScreenError(
                    "Cannot start local viewer server (port 5999). See "
                    + str(self.log_path)
                )
        self.viewer = self._spawn(
            [vncviewer, f"127.0.0.1::{self.VNC_PORT}"],
            virtual=False,
        )

    @staticmethod
    def _terminate(process, *, group=False):
        if process is None or process.poll() is not None:
            return
        if group:
            # Child starts a new process session so its process group belongs
            # exclusively to this app. Do not ever send signals to our own PGID.
            try:
                pgid = os.getpgid(process.pid)
                if pgid != os.getpgrp():
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                return
        else:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if group:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait(timeout=2)

    def stop(self):
        """Clean up just this virtual desktop, not the physical session."""
        for key in ("viewer", "browser", "vnc_server"):
            self._terminate(getattr(self, key))
            setattr(self, key, None)
        self._terminate(self.desktop_session, group=True)
        self.desktop_session = None
        self._terminate(self.xvfb)
        self.xvfb = None
        try:
            self.bus_file.unlink(missing_ok=True)
        except OSError:
            pass
