#!/usr/bin/env python3

import os
import re
import signal
import subprocess
import time
import tkinter as tk
from tkinter import messagebox, ttk

# =========================================================
# SETTINGS
# =========================================================

DOUBLETAKE_PATH = "/home/ericb/doubletake/bin/doubletake"
APPLE_TV_IP = "192.168.86.21"
TARGET_BLUETOOTH_NAME = "Living Room Audio"

RESOLUTIONS = {
    "480p": ("854", "480"),
    "720p": ("1280", "720"),
    "1080p": ("1920", "1080"),
    "4K": ("3840", "2160"),
}

# Retain the stable video buffer that was already working well.
LATENCY_MARGIN_MS = 90


class CastingApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Apple TV Cast")
        self.geometry("740x700")
        self.resizable(True, True)

        self.cast_process = None
        self.bluetooth_devices = {}
        self.restart_job = None
        self.cast_monitor_job = None

        self.screensaver_window_id = None
        self.screensaver_suspended = False

        self.resolution = tk.StringVar(value="480p")

        self.create_ui()
        self.refresh_all()

    # =====================================================
    # UI
    # =====================================================

    def create_ui(self):
        main = ttk.Frame(self, padding=18)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Apple TV Cast",
            font=("Arial", 20, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            main,
            text=(
                "Apple TV receives video only. Computer audio stays separate "
                "and can be sent to Living Room Audio over Bluetooth."
            ),
            wraplength=680,
        ).pack(anchor="w", pady=(0, 18))

        # -------------------------------------------------
        # CASTING
        # -------------------------------------------------
        cast_frame = ttk.LabelFrame(main, text="Apple TV", padding=12)
        cast_frame.pack(fill="x")

        self.cast_status = ttk.Label(
            cast_frame,
            text="Not Casting",
            wraplength=680,
        )
        self.cast_status.pack(anchor="w", pady=(0, 10))

        button_row = ttk.Frame(cast_frame)
        button_row.pack(anchor="w")

        self.cast_button = ttk.Button(
            button_row,
            text="Cast Screen",
            command=self.start_cast,
        )
        self.cast_button.pack(side="left")

        self.stop_button = ttk.Button(
            button_row,
            text="Stop Casting",
            command=self.stop_cast,
        )
        self.stop_button.pack(side="left", padx=(10, 0))

        # -------------------------------------------------
        # RESOLUTION
        # -------------------------------------------------
        resolution_frame = ttk.LabelFrame(
            main,
            text="Video Resolution",
            padding=12,
        )
        resolution_frame.pack(fill="x", pady=(18, 0))

        resolution_buttons = ttk.Frame(resolution_frame)
        resolution_buttons.pack(anchor="w")

        for index, resolution in enumerate(["480p", "720p", "1080p", "4K"]):
            ttk.Radiobutton(
                resolution_buttons,
                text=resolution,
                variable=self.resolution,
                value=resolution,
                command=self.resolution_changed,
            ).pack(side="left", padx=(0 if index == 0 else 15, 0))

        self.resolution_status = ttk.Label(
            resolution_frame,
            text="Selected: 480p (854x480)",
        )
        self.resolution_status.pack(anchor="w", pady=(10, 0))

        # -------------------------------------------------
        # BLUETOOTH AUDIO
        # -------------------------------------------------
        bluetooth_frame = ttk.LabelFrame(
            main,
            text="Bluetooth Audio",
            padding=12,
        )
        bluetooth_frame.pack(fill="x", pady=(18, 0))

        ttk.Label(
            bluetooth_frame,
            text=(
                "Preferred device: Living Room Audio. This controls only the "
                "computer's audio output; DoubleTake remains video-only."
            ),
            wraplength=660,
        ).pack(anchor="w", pady=(0, 8))

        self.bluetooth_status = ttk.Label(
            bluetooth_frame,
            text="Checking Bluetooth...",
            wraplength=660,
        )
        self.bluetooth_status.pack(anchor="w", pady=(0, 10))

        self.bluetooth_combo = ttk.Combobox(
            bluetooth_frame,
            state="readonly",
            width=55,
        )
        self.bluetooth_combo.pack(fill="x")

        bt_buttons = ttk.Frame(bluetooth_frame)
        bt_buttons.pack(anchor="w", pady=(10, 0))

        ttk.Button(
            bt_buttons,
            text="Refresh",
            command=self.refresh_bluetooth,
        ).pack(side="left")

        ttk.Button(
            bt_buttons,
            text="Open Bluetooth Manager",
            command=self.open_bluetooth_manager,
        ).pack(side="left", padx=(10, 0))

        ttk.Button(
            bt_buttons,
            text="Connect + Use Audio",
            command=self.connect_bluetooth,
        ).pack(side="left", padx=(10, 0))

        # -------------------------------------------------
        # CURRENT AUDIO OUTPUT
        # -------------------------------------------------
        audio_frame = ttk.LabelFrame(
            main,
            text="Current Computer Audio Output",
            padding=12,
        )
        audio_frame.pack(fill="x", pady=(18, 0))

        self.audio_status = ttk.Label(
            audio_frame,
            text="Checking...",
            wraplength=660,
        )
        self.audio_status.pack(anchor="w")

        # -------------------------------------------------
        # INFO
        # -------------------------------------------------
        ttk.Label(
            main,
            text=(
                "\nConfiguration:\n"
                "• Apple TV casting is always video-only\n"
                "• DoubleTake always uses -no-audio\n"
                "• 480p default; 720p / 1080p / 4K selectable\n"
                "• VAAPI hardware encoding\n"
                f"• {LATENCY_MARGIN_MS} ms video stability margin\n"
                "• No AirPlay audio offset or periodic audio refresh\n"
                "• Sleep and screensaver disabled while casting"
            ),
            justify="left",
        ).pack(anchor="w")

    # =====================================================
    # HELPERS
    # =====================================================

    def run_command(self, command, timeout=None):
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )

    def get_resolution(self):
        return RESOLUTIONS.get(
            self.resolution.get(),
            RESOLUTIONS["480p"],
        )

    def resolution_changed(self):
        selected = self.resolution.get()
        width, height = self.get_resolution()

        self.resolution_status.config(
            text=f"Selected: {selected} ({width}x{height})"
        )

        self.restart_cast_for_setting_change()

    # =====================================================
    # SCREEN SAVER / DISPLAY INHIBITION
    # =====================================================

    def inhibit_screensaver(self):
        if self.screensaver_suspended:
            return

        try:
            self.update_idletasks()
            window_id = str(self.winfo_id())

            result = subprocess.run(
                ["xdg-screensaver", "suspend", window_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            if result.returncode == 0:
                self.screensaver_window_id = window_id
                self.screensaver_suspended = True
        except Exception:
            pass

    def uninhibit_screensaver(self):
        if not self.screensaver_suspended:
            return

        try:
            if self.screensaver_window_id:
                subprocess.run(
                    [
                        "xdg-screensaver",
                        "resume",
                        self.screensaver_window_id,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        except Exception:
            pass

        self.screensaver_window_id = None
        self.screensaver_suspended = False

    # =====================================================
    # DOUBLETAKE
    # =====================================================

    def check_doubletake_features(self):
        try:
            result = self.run_command(
                [DOUBLETAKE_PATH, "-h"],
                timeout=5,
            )
            help_text = result.stdout
        except Exception as error:
            messagebox.showerror(
                "DoubleTake",
                "Could not inspect DoubleTake:\n\n" + str(error),
            )
            return False

        required = [
            "-quality",
            "-target-latency-ms",
            "-latency-margin-ms",
            "-no-audio",
        ]

        missing = [option for option in required if option not in help_text]

        if missing:
            messagebox.showerror(
                "DoubleTake Build",
                (
                    "Your custom DoubleTake binary is missing required options:\n\n"
                    + "\n".join(missing)
                    + "\n\nRebuild your customized DoubleTake binary."
                ),
            )
            return False

        return True

    def restart_cast_for_setting_change(self):
        is_casting = (
            self.cast_process is not None
            and self.cast_process.poll() is None
        )

        if not is_casting:
            return

        if self.restart_job is not None:
            try:
                self.after_cancel(self.restart_job)
            except Exception:
                pass
            self.restart_job = None

        self.stop_cast(
            cancel_restart=False,
            release_screensaver=False,
        )

        self.cast_status.config(text="Restarting cast with new video settings...")
        self.cast_button.config(state="disabled")
        self.restart_job = self.after(700, self.start_cast)

    def start_cast(self):
        self.restart_job = None

        if self.cast_process is not None and self.cast_process.poll() is None:
            messagebox.showinfo("Casting", "Casting is already running.")
            return

        if not os.path.exists(DOUBLETAKE_PATH):
            messagebox.showerror(
                "DoubleTake Missing",
                "DoubleTake was not found at:\n\n" + DOUBLETAKE_PATH,
            )
            return

        if not self.check_doubletake_features():
            return

        width, height = self.get_resolution()
        selected_resolution = self.resolution.get()

        try:
            cast_command = [
                DOUBLETAKE_PATH,
                "-target",
                APPLE_TV_IP,
                "-quality",
                selected_resolution,
                "-hwaccel",
                "vaapi",
                "-fps",
                "30",
                "-target-latency-ms",
                "0",
                "-latency-margin-ms",
                str(LATENCY_MARGIN_MS),
                "-port-range",
                "60000-60010",
                # Audio is intentionally never sent over AirPlay.
                "-no-audio",
            ]

            command = [
                "systemd-inhibit",
                "--what=sleep:idle",
                "--who=Apple TV Cast",
                "--why=Casting screen to Apple TV",
                "--mode=block",
            ] + cast_command

            self.inhibit_screensaver()

            self.cast_process = subprocess.Popen(
                command,
                cwd=os.path.dirname(DOUBLETAKE_PATH),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            time.sleep(0.15)

            if self.cast_process.poll() is not None:
                self.cast_process = None
                self.uninhibit_screensaver()
                messagebox.showerror(
                    "Casting Error",
                    (
                        "DoubleTake exited immediately.\n\n"
                        "Check the custom DoubleTake build and selected settings."
                    ),
                )
                return

            self.cast_status.config(
                text=(
                    "Casting to Living Room Apple TV "
                    f"— {selected_resolution} ({width}x{height}) "
                    "— Video Only | Audio stays on computer/Bluetooth "
                    "| Screen Saver Disabled | Sleep Disabled"
                )
            )
            self.cast_button.config(state="disabled")
            self.start_cast_monitor()

        except Exception as error:
            self.cast_process = None
            self.uninhibit_screensaver()
            self.cast_button.config(state="normal")
            messagebox.showerror("Casting Error", str(error))

    def start_cast_monitor(self):
        if self.cast_monitor_job is not None:
            try:
                self.after_cancel(self.cast_monitor_job)
            except Exception:
                pass

        self.cast_monitor_job = self.after(1000, self.monitor_cast_process)

    def monitor_cast_process(self):
        self.cast_monitor_job = None

        if self.cast_process is None:
            return

        if self.cast_process.poll() is None:
            self.cast_monitor_job = self.after(1000, self.monitor_cast_process)
            return

        self.cast_process = None
        self.uninhibit_screensaver()
        self.cast_status.config(text="Not Casting")
        self.cast_button.config(state="normal")

    def stop_cast(self, cancel_restart=True, release_screensaver=True):
        if cancel_restart and self.restart_job is not None:
            try:
                self.after_cancel(self.restart_job)
            except Exception:
                pass
            self.restart_job = None

        if self.cast_monitor_job is not None:
            try:
                self.after_cancel(self.cast_monitor_job)
            except Exception:
                pass
            self.cast_monitor_job = None

        process = self.cast_process
        self.cast_process = None

        if process is not None and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    pass
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass

        if release_screensaver:
            self.uninhibit_screensaver()

        self.cast_status.config(text="Not Casting")
        self.cast_button.config(state="normal")

    # =====================================================
    # BLUETOOTH
    # =====================================================

    def refresh_bluetooth(self):
        self.bluetooth_devices = {}

        try:
            service = self.run_command(
                ["systemctl", "is-active", "bluetooth"]
            )

            if service.stdout.strip() == "active":
                status_text = "Bluetooth service: Active"
            else:
                status_text = "Bluetooth service: Inactive"

            controller = self.run_command(["bluetoothctl", "show"])
            if "Powered: yes" in controller.stdout:
                status_text += " | Adapter: On"
            else:
                status_text += " | Adapter: Off"

            devices = self.run_command(
                ["bluetoothctl", "devices", "Paired"]
            )

            labels = []
            preferred_index = None

            for line in devices.stdout.splitlines():
                match = re.match(
                    r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)",
                    line,
                )
                if not match:
                    continue

                mac = match.group(1)
                name = match.group(2).strip()
                label = f"{name} [{mac}]"

                self.bluetooth_devices[label] = mac
                labels.append(label)

                if name.casefold() == TARGET_BLUETOOTH_NAME.casefold():
                    preferred_index = len(labels) - 1

            self.bluetooth_combo["values"] = labels

            if labels:
                if preferred_index is not None:
                    self.bluetooth_combo.current(preferred_index)
                    status_text += f" | {TARGET_BLUETOOTH_NAME}: Paired"
                else:
                    self.bluetooth_combo.current(0)
                    status_text += f" | {TARGET_BLUETOOTH_NAME}: Not paired"
            else:
                self.bluetooth_combo.set("")
                status_text += " | No paired audio devices"

            self.bluetooth_status.config(text=status_text)

        except Exception as error:
            self.bluetooth_status.config(
                text="Bluetooth error: " + str(error)
            )

        self.refresh_audio()

    def open_bluetooth_manager(self):
        try:
            subprocess.Popen(["blueman-manager"])
        except Exception as error:
            messagebox.showerror("Bluetooth Manager", str(error))

    def connect_bluetooth(self):
        selected = self.bluetooth_combo.get()

        if not selected:
            messagebox.showinfo(
                "Bluetooth",
                (
                    f"{TARGET_BLUETOOTH_NAME} is not paired yet.\n\n"
                    "Use the one-time Bluetooth setup in Terminal or click "
                    "Open Bluetooth Manager, then Refresh."
                ),
            )
            return

        mac = self.bluetooth_devices.get(selected)
        if not mac:
            messagebox.showerror("Bluetooth", "Could not determine device MAC address.")
            return

        # Keep the receiver trusted so reconnects are painless.
        self.run_command(["bluetoothctl", "trust", mac])
        result = self.run_command(["bluetoothctl", "connect", mac])

        if (
            "successful" not in result.stdout.lower()
            and "connected: yes" not in result.stdout.lower()
        ):
            info = self.run_command(["bluetoothctl", "info", mac])
            if "Connected: yes" not in info.stdout:
                messagebox.showwarning("Bluetooth", result.stdout or info.stdout)
                self.refresh_all()
                return

        # PipeWire/PulseAudio can take a moment to expose the A2DP sink.
        sink = None
        for _ in range(10):
            time.sleep(0.5)
            sink = self.find_bluetooth_sink(mac)
            if sink:
                break

        if not sink:
            messagebox.showerror(
                "Audio",
                (
                    "Bluetooth connected, but no Bluetooth audio output appeared.\n\n"
                    "Confirm the ESP32 firmware is running and that the device "
                    "advertises as an A2DP audio receiver."
                ),
            )
            self.refresh_all()
            return

        self.run_command(["pactl", "set-default-sink", sink])

        # Move any audio that is already playing to the new receiver.
        inputs = self.run_command(
            ["pactl", "list", "short", "sink-inputs"]
        )

        for line in inputs.stdout.splitlines():
            pieces = line.split()
            if not pieces:
                continue
            self.run_command(
                ["pactl", "move-sink-input", pieces[0], sink]
            )

        self.refresh_all()
        messagebox.showinfo(
            "Bluetooth",
            (
                f"{selected} is connected and is now the computer's audio output.\n\n"
                "Apple TV casting remains video-only."
            ),
        )

    def find_bluetooth_sink(self, mac):
        sinks = self.run_command(
            ["pactl", "list", "short", "sinks"]
        )

        mac_pipewire = mac.replace(":", "_").lower()
        bluez_sinks = []

        for line in sinks.stdout.splitlines():
            pieces = line.split()
            if len(pieces) < 2:
                continue

            name = pieces[1]
            if "bluez" not in name.lower():
                continue

            bluez_sinks.append(name)
            if mac_pipewire in name.lower():
                return name

        if len(bluez_sinks) == 1:
            return bluez_sinks[0]

        return None

    def refresh_audio(self):
        try:
            result = self.run_command(["pactl", "get-default-sink"])
            self.audio_status.config(text=result.stdout.strip() or "Unknown")
        except Exception as error:
            self.audio_status.config(text=str(error))

    def refresh_all(self):
        self.resolution_changed()
        self.refresh_bluetooth()
        self.refresh_audio()

    def destroy(self):
        self.stop_cast(
            cancel_restart=True,
            release_screensaver=True,
        )
        super().destroy()


if __name__ == "__main__":
    app = CastingApp()
    app.mainloop()
