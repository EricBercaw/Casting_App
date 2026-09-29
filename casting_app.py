#!/usr/bin/env python3

import os
import re
import signal
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox


# =========================================================
# SETTINGS
# =========================================================

DOUBLETAKE_PATH = "/home/ericb/doubletake/bin/doubletake"
APPLE_TV_IP = "192.168.86.21"


# =========================================================
# VIDEO RESOLUTIONS
# =========================================================

RESOLUTIONS = {
    "480p": ("854", "480"),
    "720p": ("1280", "720"),
    "1080p": ("1920", "1080"),
    "4K": ("3840", "2160"),
}


# =========================================================
# LATENCY / SYNC SETTINGS
# =========================================================
#
# Doubletake automatic screen timing is approximately:
#
#   Video = 75 ms
#   Audio = 85 ms
#
# We add 90 ms of shared buffering:
#
#   Video = ~165 ms
#   Audio = ~175 ms
#
# Then the default -5 ms audio calibration gives:
#
#   Video = ~165 ms
#   Audio = ~170 ms
#
# The +/-5 ms buttons modify AUDIO ONLY.
# =========================================================

LATENCY_MARGIN_MS = 90

BASE_AUDIO_OFFSET_MS = -5

NOMINAL_VIDEO_LATENCY_MS = 165
NOMINAL_AUDIO_LATENCY_MS = 170


# =========================================================
# MAIN APP
# =========================================================

class CastingApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Apple TV Cast")
        self.geometry("740x880")
        self.resizable(True, True)

        self.cast_process = None
        self.bluetooth_devices = {}

        self.restart_job = None
        self.cast_monitor_job = None

        # Screensaver inhibitor state.
        self.screensaver_window_id = None
        self.screensaver_suspended = False

        # -------------------------------------------------
        # DEFAULT AUDIO MODE
        # -------------------------------------------------

        self.audio_mode = tk.StringVar(
            value="cast"
        )

        # -------------------------------------------------
        # DEFAULT RESOLUTION
        # -------------------------------------------------

        self.resolution = tk.StringVar(
            value="480p"
        )

        # -------------------------------------------------
        # USER AUDIO FINE ADJUSTMENT
        #
        # 0 means calibrated default:
        #
        #   BASE_AUDIO_OFFSET_MS = -5 ms
        #
        # Audio -5:
        #   effective offset = -10 ms
        #
        # Audio +5:
        #   effective offset = 0 ms
        # -------------------------------------------------

        self.audio_adjust_ms = tk.IntVar(
            value=0
        )

        self.create_ui()
        self.refresh_all()


    # =====================================================
    # UI
    # =====================================================

    def create_ui(self):

        main = ttk.Frame(
            self,
            padding=18
        )

        main.pack(
            fill="both",
            expand=True
        )


        # =================================================
        # TITLE
        # =================================================

        ttk.Label(
            main,
            text="Apple TV Cast",
            font=("Arial", 20, "bold")
        ).pack(
            anchor="w"
        )


        ttk.Label(
            main,
            text=(
                "Cast desktop to Apple TV with selectable "
                "resolution and fine audio synchronization"
            )
        ).pack(
            anchor="w",
            pady=(0, 18)
        )


        # =================================================
        # CAST
        # =================================================

        cast_frame = ttk.LabelFrame(
            main,
            text="Apple TV",
            padding=12
        )

        cast_frame.pack(
            fill="x"
        )


        self.cast_status = ttk.Label(
            cast_frame,
            text="Not Casting",
            wraplength=680
        )

        self.cast_status.pack(
            anchor="w",
            pady=(0, 10)
        )


        button_row = ttk.Frame(
            cast_frame
        )

        button_row.pack(
            anchor="w"
        )


        self.cast_button = ttk.Button(
            button_row,
            text="Cast Screen",
            command=self.start_cast
        )

        self.cast_button.pack(
            side="left"
        )


        self.stop_button = ttk.Button(
            button_row,
            text="Stop Casting",
            command=self.stop_cast
        )

        self.stop_button.pack(
            side="left",
            padx=(10, 0)
        )


        # =================================================
        # RESOLUTION
        # =================================================

        resolution_frame = ttk.LabelFrame(
            main,
            text="Video Resolution",
            padding=12
        )

        resolution_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        resolution_buttons = ttk.Frame(
            resolution_frame
        )

        resolution_buttons.pack(
            anchor="w"
        )


        for index, resolution in enumerate(
            ["480p", "720p", "1080p", "4K"]
        ):

            ttk.Radiobutton(
                resolution_buttons,
                text=resolution,
                variable=self.resolution,
                value=resolution,
                command=self.resolution_changed
            ).pack(
                side="left",
                padx=(0 if index == 0 else 15, 0)
            )


        self.resolution_status = ttk.Label(
            resolution_frame,
            text="Selected: 480p (854×480)"
        )

        self.resolution_status.pack(
            anchor="w",
            pady=(10, 0)
        )


        # =================================================
        # AUDIO OUTPUT
        # =================================================

        audio_mode_frame = ttk.LabelFrame(
            main,
            text="Audio Output While Casting",
            padding=12
        )

        audio_mode_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        ttk.Radiobutton(
            audio_mode_frame,
            text="Apple TV — Cast video + audio",
            variable=self.audio_mode,
            value="cast",
            command=self.audio_mode_changed
        ).pack(
            anchor="w"
        )


        ttk.Radiobutton(
            audio_mode_frame,
            text=(
                "Bluetooth Speaker — "
                "Apple TV receives video only"
            ),
            variable=self.audio_mode,
            value="bluetooth",
            command=self.audio_mode_changed
        ).pack(
            anchor="w",
            pady=(8, 0)
        )


        self.audio_mode_status = ttk.Label(
            audio_mode_frame,
            text="Selected: Apple TV (video + audio)"
        )

        self.audio_mode_status.pack(
            anchor="w",
            pady=(10, 0)
        )


        # =================================================
        # AUDIO SYNC
        # =================================================

        sync_frame = ttk.LabelFrame(
            main,
            text="Audio Synchronization",
            padding=12
        )

        sync_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        sync_buttons = ttk.Frame(
            sync_frame
        )

        sync_buttons.pack(
            anchor="w"
        )


        ttk.Button(
            sync_buttons,
            text="Audio -5 ms",
            command=lambda: self.adjust_audio(-5)
        ).pack(
            side="left"
        )


        ttk.Button(
            sync_buttons,
            text="Reset",
            command=self.reset_audio
        ).pack(
            side="left",
            padx=(8, 0)
        )


        ttk.Button(
            sync_buttons,
            text="Audio +5 ms",
            command=lambda: self.adjust_audio(5)
        ).pack(
            side="left",
            padx=(8, 0)
        )


        self.audio_sync_status = ttk.Label(
            sync_frame,
            text=(
                f"Audio: ~{NOMINAL_AUDIO_LATENCY_MS} ms "
                "| Fine adjustment: 0 ms"
            )
        )

        self.audio_sync_status.pack(
            anchor="w",
            pady=(10, 0)
        )


        self.video_sync_status = ttk.Label(
            sync_frame,
            text=(
                f"Video: ~{NOMINAL_VIDEO_LATENCY_MS} ms "
                "(unchanged by audio adjustment)"
            )
        )

        self.video_sync_status.pack(
            anchor="w",
            pady=(5, 0)
        )


        ttk.Label(
            sync_frame,
            text=(
                f"A {LATENCY_MARGIN_MS} ms playout margin "
                "is retained for smoother playback. "
                "The buttons adjust audio timing only."
            ),
            wraplength=660
        ).pack(
            anchor="w",
            pady=(8, 0)
        )


        # =================================================
        # BLUETOOTH
        # =================================================

        bluetooth_frame = ttk.LabelFrame(
            main,
            text="Bluetooth Audio",
            padding=12
        )

        bluetooth_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        self.bluetooth_status = ttk.Label(
            bluetooth_frame,
            text="Checking Bluetooth..."
        )

        self.bluetooth_status.pack(
            anchor="w",
            pady=(0, 10)
        )


        self.bluetooth_combo = ttk.Combobox(
            bluetooth_frame,
            state="readonly",
            width=55
        )

        self.bluetooth_combo.pack(
            fill="x"
        )


        bt_buttons = ttk.Frame(
            bluetooth_frame
        )

        bt_buttons.pack(
            anchor="w",
            pady=(10, 0)
        )


        ttk.Button(
            bt_buttons,
            text="Refresh",
            command=self.refresh_bluetooth
        ).pack(
            side="left"
        )


        ttk.Button(
            bt_buttons,
            text="Open Bluetooth Manager",
            command=self.open_bluetooth_manager
        ).pack(
            side="left",
            padx=(10, 0)
        )


        ttk.Button(
            bt_buttons,
            text="Connect + Use Audio",
            command=self.connect_bluetooth
        ).pack(
            side="left",
            padx=(10, 0)
        )


        # =================================================
        # COMPUTER AUDIO
        # =================================================

        audio_frame = ttk.LabelFrame(
            main,
            text="Current Computer Audio Output",
            padding=12
        )

        audio_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        self.audio_status = ttk.Label(
            audio_frame,
            text="Checking..."
        )

        self.audio_status.pack(
            anchor="w"
        )


        # =================================================
        # INFO
        # =================================================

        ttk.Label(
            main,
            text=(
                "\nDefault configuration:\n"
                "• 480p video\n"
                "• Apple TV video + audio\n"
                "• VAAPI hardware encoding\n"
                "• Automatic AirPlay timing\n"
                f"• {LATENCY_MARGIN_MS} ms additional stability margin\n"
                f"• ~{NOMINAL_VIDEO_LATENCY_MS} ms nominal video timing\n"
                f"• ~{NOMINAL_AUDIO_LATENCY_MS} ms nominal audio timing\n"
                "• ±5 ms audio-only fine adjustment\n"
                "• Sleep disabled while casting\n"
                "• Screensaver/display blanking disabled while casting"
            ),
            justify="left"
        ).pack(
            anchor="w"
        )


    # =====================================================
    # RESOLUTION
    # =====================================================

    def get_resolution(self):

        return RESOLUTIONS.get(
            self.resolution.get(),
            RESOLUTIONS["480p"]
        )


    def resolution_changed(self):

        selected = self.resolution.get()

        width, height = self.get_resolution()

        self.resolution_status.config(
            text=(
                f"Selected: {selected} "
                f"({width}×{height})"
            )
        )

        self.restart_cast_for_setting_change()


    # =====================================================
    # AUDIO MODE
    # =====================================================

    def audio_mode_changed(self):

        if self.audio_mode.get() == "bluetooth":

            self.audio_mode_status.config(
                text=(
                    "Selected: Bluetooth Speaker "
                    "(Apple TV video only)"
                )
            )

        else:

            self.audio_mode_status.config(
                text=(
                    "Selected: Apple TV "
                    "(video + audio)"
                )
            )

        self.restart_cast_for_setting_change()


    # =====================================================
    # AUDIO SYNC
    # =====================================================

    def get_effective_audio_offset(self):

        return (
            BASE_AUDIO_OFFSET_MS
            + self.audio_adjust_ms.get()
        )


    def get_nominal_audio_latency(self):

        return (
            NOMINAL_AUDIO_LATENCY_MS
            + self.audio_adjust_ms.get()
        )


    def update_audio_sync_status(self):

        adjustment = self.audio_adjust_ms.get()

        audio_latency = (
            self.get_nominal_audio_latency()
        )


        if adjustment > 0:
            adjustment_text = f"+{adjustment} ms"

        else:
            adjustment_text = f"{adjustment} ms"


        self.audio_sync_status.config(
            text=(
                f"Audio: ~{audio_latency} ms "
                f"| Fine adjustment: {adjustment_text}"
            )
        )


        self.video_sync_status.config(
            text=(
                f"Video: ~{NOMINAL_VIDEO_LATENCY_MS} ms "
                "(unchanged by audio adjustment)"
            )
        )


    def adjust_audio(self, delta):

        current = self.audio_adjust_ms.get()

        new_value = current + delta

        new_value = max(
            -100,
            min(
                100,
                new_value
            )
        )


        if new_value == current:
            return


        self.audio_adjust_ms.set(
            new_value
        )

        self.update_audio_sync_status()

        self.restart_cast_for_setting_change()


    def reset_audio(self):

        if self.audio_adjust_ms.get() == 0:
            return


        self.audio_adjust_ms.set(
            0
        )

        self.update_audio_sync_status()

        self.restart_cast_for_setting_change()


    # =====================================================
    # SCREEN SAVER / DISPLAY INHIBITION
    # =====================================================

    def inhibit_screensaver(self):

        if self.screensaver_suspended:
            return


        try:

            self.update_idletasks()

            window_id = str(
                self.winfo_id()
            )


            result = subprocess.run(
                [
                    "xdg-screensaver",
                    "suspend",
                    window_id
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )


            if result.returncode == 0:

                self.screensaver_window_id = (
                    window_id
                )

                self.screensaver_suspended = True


        except Exception:

            # Casting should still work even if the
            # screensaver command is unavailable.

            self.screensaver_window_id = None
            self.screensaver_suspended = False


    def uninhibit_screensaver(self):

        if not self.screensaver_suspended:
            return


        try:

            if self.screensaver_window_id:

                subprocess.run(
                    [
                        "xdg-screensaver",
                        "resume",
                        self.screensaver_window_id
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )


        except Exception:
            pass


        self.screensaver_window_id = None
        self.screensaver_suspended = False


    # =====================================================
    # AUTO RESTART
    # =====================================================

    def restart_cast_for_setting_change(self):

        is_casting = (
            self.cast_process is not None
            and
            self.cast_process.poll() is None
        )


        if not is_casting:
            return


        if self.restart_job is not None:

            try:

                self.after_cancel(
                    self.restart_job
                )

            except Exception:
                pass


            self.restart_job = None


        # Keep screensaver inhibited during the brief
        # automatic restart.

        self.stop_cast(
            cancel_restart=False,
            release_screensaver=False
        )


        self.cast_status.config(
            text="Restarting cast with new settings..."
        )


        self.restart_job = self.after(
            700,
            self.start_cast
        )


    # =====================================================
    # COMMAND HELPER
    # =====================================================

    def run_command(self, command):

        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )


    # =====================================================
    # CHECK CUSTOM DOUBLETAKE
    # =====================================================

    def check_doubletake_features(self):

        try:

            result = subprocess.run(
                [
                    DOUBLETAKE_PATH,
                    "-h"
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=5
            )

            help_text = result.stdout


        except Exception as error:

            messagebox.showerror(
                "Doubletake",
                (
                    "Could not inspect Doubletake:\n\n"
                    + str(error)
                )
            )

            return False


        required = [
            "-quality",
            "-target-latency-ms",
            "-latency-margin-ms",
            "-audio-offset-ms"
        ]


        missing = [
            option
            for option in required
            if option not in help_text
        ]


        if missing:

            messagebox.showerror(
                "Doubletake Build",
                (
                    "Your custom Doubletake binary "
                    "is missing required options:\n\n"
                    + "\n".join(missing)
                    + "\n\n"
                    "Rebuild your customized Doubletake binary."
                )
            )

            return False


        return True


    # =====================================================
    # CASTING
    # =====================================================

    def start_cast(self):

        self.restart_job = None


        if (
            self.cast_process is not None
            and
            self.cast_process.poll() is None
        ):

            messagebox.showinfo(
                "Casting",
                "Casting is already running."
            )

            return


        if not os.path.exists(
            DOUBLETAKE_PATH
        ):

            messagebox.showerror(
                "Doubletake Missing",
                (
                    "Doubletake was not found at:\n\n"
                    + DOUBLETAKE_PATH
                )
            )

            return


        if not self.check_doubletake_features():
            return


        width, height = self.get_resolution()

        selected_resolution = (
            self.resolution.get()
        )

        effective_audio_offset = (
            self.get_effective_audio_offset()
        )

        nominal_audio_latency = (
            self.get_nominal_audio_latency()
        )


        try:

            # -------------------------------------------------
            # DOUBLETAKE
            # -------------------------------------------------

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

                # Preserve Doubletake's automatic
                # separate audio/video timing.
                "-target-latency-ms",
                "0",

                # IMPORTANT:
                # Use the actual configured constant.
                # This was previously hard-coded to 40.
                "-latency-margin-ms",
                str(
                    LATENCY_MARGIN_MS
                ),

                # Fine audio-only synchronization.
                "-audio-offset-ms",
                str(
                    effective_audio_offset
                ),

                "-port-range",
                "60000-60010"

            ]


            if self.audio_mode.get() == "bluetooth":

                cast_command.append(
                    "-no-audio"
                )


            # -------------------------------------------------
            # SYSTEMD IDLE/SLEEP INHIBITOR
            # -------------------------------------------------

            command = [

                "systemd-inhibit",

                "--what=sleep:idle",

                "--who=Apple TV Cast",

                "--why=Casting screen to Apple TV",

                "--mode=block"

            ] + cast_command


            # -------------------------------------------------
            # SCREEN SAVER INHIBITOR
            # -------------------------------------------------

            self.inhibit_screensaver()


            # -------------------------------------------------
            # START
            # -------------------------------------------------

            self.cast_process = subprocess.Popen(
                command,
                cwd=os.path.dirname(
                    DOUBLETAKE_PATH
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )


            time.sleep(
                0.15
            )


            # Immediate failure.
            if (
                self.cast_process.poll()
                is not None
            ):

                self.cast_process = None

                self.uninhibit_screensaver()

                messagebox.showerror(
                    "Casting Error",
                    (
                        "Doubletake exited immediately.\n\n"
                        "Check the custom Doubletake build "
                        "and selected settings."
                    )
                )

                return


            # -------------------------------------------------
            # STATUS
            # -------------------------------------------------

            adjustment = (
                self.audio_adjust_ms.get()
            )


            if adjustment > 0:
                adjustment_text = f"+{adjustment} ms"

            else:
                adjustment_text = f"{adjustment} ms"


            if self.audio_mode.get() == "bluetooth":

                status = (
                    "Casting to Living Room Apple TV "
                    f"— {selected_resolution} "
                    f"({width}×{height}) "
                    "— Video Only "
                    "| Audio → Bluetooth "
                    f"| Video ~{NOMINAL_VIDEO_LATENCY_MS} ms "
                    "| Screen Saver Disabled "
                    "| Sleep Disabled"
                )

            else:

                status = (
                    "Casting to Living Room Apple TV "
                    f"— {selected_resolution} "
                    f"({width}×{height}) "
                    "— Video + Audio "
                    f"| Video ~{NOMINAL_VIDEO_LATENCY_MS} ms "
                    f"| Audio ~{nominal_audio_latency} ms "
                    f"| Fine {adjustment_text} "
                    "| Screen Saver Disabled "
                    "| Sleep Disabled"
                )


            self.cast_status.config(
                text=status
            )


            self.cast_button.config(
                state="disabled"
            )


            self.start_cast_monitor()


        except Exception as error:

            self.cast_process = None

            self.uninhibit_screensaver()

            messagebox.showerror(
                "Casting Error",
                str(error)
            )


    # =====================================================
    # CAST PROCESS MONITOR
    # =====================================================

    def start_cast_monitor(self):

        if self.cast_monitor_job is not None:

            try:

                self.after_cancel(
                    self.cast_monitor_job
                )

            except Exception:
                pass


        self.cast_monitor_job = self.after(
            1000,
            self.monitor_cast_process
        )


    def monitor_cast_process(self):

        self.cast_monitor_job = None


        if self.cast_process is None:
            return


        if self.cast_process.poll() is None:

            self.cast_monitor_job = self.after(
                1000,
                self.monitor_cast_process
            )

            return


        # Doubletake stopped unexpectedly.

        self.cast_process = None

        self.uninhibit_screensaver()

        self.cast_status.config(
            text="Casting stopped"
        )

        self.cast_button.config(
            state="normal"
        )


    # =====================================================
    # STOP CAST
    # =====================================================

    def stop_cast(
        self,
        cancel_restart=True,
        release_screensaver=True
    ):

        # -------------------------------------------------
        # CANCEL AUTO RESTART
        # -------------------------------------------------

        if (
            cancel_restart
            and
            self.restart_job is not None
        ):

            try:

                self.after_cancel(
                    self.restart_job
                )

            except Exception:
                pass


            self.restart_job = None


        # -------------------------------------------------
        # CANCEL PROCESS MONITOR
        # -------------------------------------------------

        if self.cast_monitor_job is not None:

            try:

                self.after_cancel(
                    self.cast_monitor_job
                )

            except Exception:
                pass


            self.cast_monitor_job = None


        # -------------------------------------------------
        # STOP DOUBLETAKE
        # -------------------------------------------------

        if self.cast_process:

            try:

                if (
                    self.cast_process.poll()
                    is None
                ):

                    os.killpg(
                        os.getpgid(
                            self.cast_process.pid
                        ),
                        signal.SIGTERM
                    )

            except Exception:
                pass


        self.cast_process = None


        # -------------------------------------------------
        # RESTORE SCREEN SAVER
        # -------------------------------------------------

        if release_screensaver:

            self.uninhibit_screensaver()


        self.cast_status.config(
            text="Not Casting"
        )


        self.cast_button.config(
            state="normal"
        )


    # =====================================================
    # BLUETOOTH
    # =====================================================

    def refresh_bluetooth(self):

        self.bluetooth_devices = {}


        try:

            service = self.run_command(
                [
                    "systemctl",
                    "is-active",
                    "bluetooth"
                ]
            )


            if service.stdout.strip() == "active":

                status_text = (
                    "Bluetooth service: Active"
                )

            else:

                status_text = (
                    "Bluetooth service: Inactive"
                )


            controller = self.run_command(
                [
                    "bluetoothctl",
                    "show"
                ]
            )


            if "Powered: yes" in controller.stdout:

                status_text += (
                    " | Adapter: On"
                )

            else:

                status_text += (
                    " | Adapter: Off"
                )


            self.bluetooth_status.config(
                text=status_text
            )


            devices = self.run_command(
                [
                    "bluetoothctl",
                    "devices",
                    "Paired"
                ]
            )


            labels = []


            for line in devices.stdout.splitlines():

                match = re.match(
                    r"Device\s+"
                    r"([0-9A-Fa-f:]{17})"
                    r"\s+(.+)",
                    line
                )


                if not match:
                    continue


                mac = match.group(1)
                name = match.group(2)

                label = (
                    name
                    + " ["
                    + mac
                    + "]"
                )


                self.bluetooth_devices[
                    label
                ] = mac

                labels.append(
                    label
                )


            self.bluetooth_combo[
                "values"
            ] = labels


            if labels:

                self.bluetooth_combo.current(
                    0
                )

            else:

                self.bluetooth_combo.set(
                    ""
                )


        except Exception as error:

            self.bluetooth_status.config(
                text=(
                    "Bluetooth error: "
                    + str(error)
                )
            )


        self.refresh_audio()


    def open_bluetooth_manager(self):

        try:

            subprocess.Popen(
                [
                    "blueman-manager"
                ]
            )

        except Exception as error:

            messagebox.showerror(
                "Bluetooth Manager",
                str(error)
            )


    def connect_bluetooth(self):

        selected = (
            self.bluetooth_combo.get()
        )


        if not selected:

            messagebox.showinfo(
                "Bluetooth",
                (
                    "No paired Bluetooth speaker found.\n\n"
                    "Click Open Bluetooth Manager first."
                )
            )

            return


        mac = (
            self.bluetooth_devices[
                selected
            ]
        )


        result = self.run_command(
            [
                "bluetoothctl",
                "connect",
                mac
            ]
        )


        if (
            "successful"
            not in result.stdout.lower()
            and
            "connected: yes"
            not in result.stdout.lower()
        ):

            messagebox.showwarning(
                "Bluetooth",
                result.stdout
            )


        time.sleep(
            2
        )


        sink = self.find_bluetooth_sink(
            mac
        )


        if not sink:

            messagebox.showerror(
                "Audio",
                (
                    "Bluetooth connected, but no "
                    "Bluetooth audio output appeared."
                )
            )

            self.refresh_all()

            return


        # Set Bluetooth speaker as default sink.

        self.run_command(
            [
                "pactl",
                "set-default-sink",
                sink
            ]
        )


        # Move currently playing streams.

        inputs = self.run_command(
            [
                "pactl",
                "list",
                "short",
                "sink-inputs"
            ]
        )


        for line in inputs.stdout.splitlines():

            pieces = line.split()


            if not pieces:
                continue


            input_id = pieces[0]


            self.run_command(
                [
                    "pactl",
                    "move-sink-input",
                    input_id,
                    sink
                ]
            )


        self.audio_mode.set(
            "bluetooth"
        )

        self.audio_mode_changed()

        self.refresh_audio()


        messagebox.showinfo(
            "Bluetooth",
            (
                "Bluetooth speaker is now "
                "your audio output.\n\n"
                "Apple TV casting will use video-only mode."
            )
        )


    def find_bluetooth_sink(
        self,
        mac
    ):

        sinks = self.run_command(
            [
                "pactl",
                "list",
                "short",
                "sinks"
            ]
        )


        mac_pipewire = (
            mac
            .replace(
                ":",
                "_"
            )
            .lower()
        )


        bluez_sinks = []


        for line in sinks.stdout.splitlines():

            pieces = line.split()


            if len(pieces) < 2:
                continue


            name = pieces[1]


            if "bluez" in name.lower():

                bluez_sinks.append(
                    name
                )


                if mac_pipewire in name.lower():

                    return name


        if len(bluez_sinks) == 1:

            return bluez_sinks[0]


        return None


    # =====================================================
    # COMPUTER AUDIO STATUS
    # =====================================================

    def refresh_audio(self):

        try:

            result = self.run_command(
                [
                    "pactl",
                    "get-default-sink"
                ]
            )


            self.audio_status.config(
                text=result.stdout.strip()
            )


        except Exception as error:

            self.audio_status.config(
                text=str(error)
            )


    # =====================================================
    # REFRESH
    # =====================================================

    def refresh_all(self):

        self.refresh_bluetooth()

        self.audio_mode_changed()

        self.resolution_changed()

        self.update_audio_sync_status()


    # =====================================================
    # CLOSE
    # =====================================================

    def destroy(self):

        self.stop_cast(
            cancel_restart=True,
            release_screensaver=True
        )

        super().destroy()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = CastingApp()

    app.mainloop()