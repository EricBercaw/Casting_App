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
# MAIN APP
# =========================================================

class CastingApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Apple TV Cast")
        self.geometry("720x850")
        self.resizable(True, True)

        self.cast_process = None
        self.bluetooth_devices = {}
        self.restart_job = None

        # -------------------------------------------------
        # DEFAULT AUDIO MODE
        #
        # cast:
        #   Apple TV receives video + audio
        #
        # bluetooth:
        #   Apple TV receives video only
        #   Bluetooth speaker receives audio
        # -------------------------------------------------

        self.audio_mode = tk.StringVar(
            value="cast"
        )

        # -------------------------------------------------
        # DEFAULT VIDEO RESOLUTION
        #
        # 480p is selected when the app starts.
        # -------------------------------------------------

        self.resolution = tk.StringVar(
            value="480p"
        )

        # -------------------------------------------------
        # AUDIO SYNC OFFSET
        #
        # Base video timing = 120 ms
        # Base audio timing = 120 ms
        #
        # -5 = audio earlier
        # +5 = audio later
        # -------------------------------------------------

        self.audio_offset_ms = tk.IntVar(
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

        title = ttk.Label(
            main,
            text="Apple TV Cast",
            font=("Arial", 20, "bold")
        )

        title.pack(
            anchor="w"
        )


        subtitle = ttk.Label(
            main,
            text=(
                "Cast desktop to Apple TV "
                "with selectable video quality and audio output"
            )
        )

        subtitle.pack(
            anchor="w",
            pady=(0, 18)
        )


        # =================================================
        # APPLE TV CAST
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
            text="Not Casting"
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
        # VIDEO RESOLUTION
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


        ttk.Radiobutton(
            resolution_buttons,
            text="480p",
            variable=self.resolution,
            value="480p",
            command=self.resolution_changed
        ).pack(
            side="left"
        )


        ttk.Radiobutton(
            resolution_buttons,
            text="720p",
            variable=self.resolution,
            value="720p",
            command=self.resolution_changed
        ).pack(
            side="left",
            padx=(15, 0)
        )


        ttk.Radiobutton(
            resolution_buttons,
            text="1080p",
            variable=self.resolution,
            value="1080p",
            command=self.resolution_changed
        ).pack(
            side="left",
            padx=(15, 0)
        )


        ttk.Radiobutton(
            resolution_buttons,
            text="4K",
            variable=self.resolution,
            value="4K",
            command=self.resolution_changed
        ).pack(
            side="left",
            padx=(15, 0)
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

        offset_frame = ttk.Frame(
            audio_mode_frame
        )

        offset_frame.pack(
            anchor="w",
            pady=(14, 0)
        )


        ttk.Label(
            offset_frame,
            text="Apple TV audio sync:"
        ).pack(
            side="left"
        )


        ttk.Button(
            offset_frame,
            text="Audio -5 ms",
            command=lambda: self.adjust_audio_offset(-5)
        ).pack(
            side="left",
            padx=(10, 0)
        )


        ttk.Button(
            offset_frame,
            text="Reset",
            command=self.reset_audio_offset
        ).pack(
            side="left",
            padx=(6, 0)
        )


        ttk.Button(
            offset_frame,
            text="Audio +5 ms",
            command=lambda: self.adjust_audio_offset(5)
        ).pack(
            side="left",
            padx=(6, 0)
        )


        self.audio_offset_status = ttk.Label(
            audio_mode_frame,
            text="Audio timing: 120 ms | Offset: 0 ms"
        )

        self.audio_offset_status.pack(
            anchor="w",
            pady=(8, 0)
        )


        timing_info = ttk.Label(
            audio_mode_frame,
            text=(
                "Video remains fixed at 120 ms. "
                "Audio offset adjusts audio only."
            )
        )

        timing_info.pack(
            anchor="w",
            pady=(5, 0)
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
        # COMPUTER AUDIO OUTPUT
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

        info = ttk.Label(
            main,
            text=(
                "\nDefault: 480p + Apple TV video/audio\n"
                "Video timing: fixed at 120 ms\n"
                "Audio timing: 120 ms + selected audio offset\n"
                "Resolution/audio timing changes restart the cast automatically.\n"
                "Sleep is automatically disabled while casting."
            ),
            justify="left"
        )

        info.pack(
            anchor="w"
        )


    # =====================================================
    # RESOLUTION
    # =====================================================

    def get_resolution(self):

        selected = self.resolution.get()

        return RESOLUTIONS.get(
            selected,
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

        mode = self.audio_mode.get()

        if mode == "bluetooth":

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
    # AUDIO SYNC OFFSET
    # =====================================================

    def update_audio_offset_status(self):

        offset = self.audio_offset_ms.get()

        audio_timing = 120 + offset


        if offset > 0:

            offset_text = (
                f"+{offset} ms"
            )

        else:

            offset_text = (
                f"{offset} ms"
            )


        self.audio_offset_status.config(
            text=(
                f"Audio timing: {audio_timing} ms "
                f"| Offset: {offset_text}"
            )
        )


    def adjust_audio_offset(
        self,
        delta
    ):

        current = self.audio_offset_ms.get()

        new_offset = current + delta

        # Limit fine adjustment to +/-100 ms.

        new_offset = max(
            -100,
            min(
                100,
                new_offset
            )
        )


        if new_offset == current:
            return


        self.audio_offset_ms.set(
            new_offset
        )

        self.update_audio_offset_status()

        self.restart_cast_for_setting_change()


    def reset_audio_offset(self):

        if self.audio_offset_ms.get() == 0:
            return


        self.audio_offset_ms.set(
            0
        )

        self.update_audio_offset_status()

        self.restart_cast_for_setting_change()


    # =====================================================
    # AUTO-RESTART AFTER SETTINGS CHANGE
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


        self.stop_cast(
            cancel_restart=False
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

    def run_command(
        self,
        command
    ):

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
            "-width",
            "-height",
            "-audio-offset-ms",
            "-target-latency-ms"
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
                    "Your current Doubletake binary is missing "
                    "required custom options:\n\n"
                    + "\n".join(missing)
                    + "\n\n"
                    "Rebuild your custom Doubletake version first."
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
            self.cast_process
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


        try:

            # -------------------------------------------------
            # DOUBLETAKE COMMAND
            #
            # IMPORTANT TIMING DESIGN:
            #
            # target-latency-ms = 120
            #
            # This fixes BOTH streams to 120 ms first.
            #
            # audio-offset-ms then adjusts ONLY audio.
            #
            # Video therefore remains fixed at 120 ms.
            #
            # Examples:
            #
            # offset  0:
            #   video = 120
            #   audio = 120
            #
            # offset -5:
            #   video = 120
            #   audio = 115
            #
            # offset +5:
            #   video = 120
            #   audio = 125
            # -------------------------------------------------

            cast_command = [

                DOUBLETAKE_PATH,

                "-target",
                APPLE_TV_IP,

                "-hwaccel",
                "auto",

                "-fps",
                "30",

                "-bitrate",
                "0",

                # ---------------------------------------------
                # SELECTED RESOLUTION
                # ---------------------------------------------

                "-width",
                width,

                "-height",
                height,

                # ---------------------------------------------
                # FIXED VIDEO/AUDIO BASE TIMING
                # ---------------------------------------------

                "-target-latency-ms",
                "120",

                # ---------------------------------------------
                # AUDIO-ONLY FINE ADJUSTMENT
                # ---------------------------------------------

                "-audio-offset-ms",
                str(
                    self.audio_offset_ms.get()
                ),

                # ---------------------------------------------
                # NETWORK PORT RANGE
                # ---------------------------------------------

                "-port-range",
                "60000-60010"

            ]


            # -------------------------------------------------
            # BLUETOOTH MODE
            # -------------------------------------------------

            if self.audio_mode.get() == "bluetooth":

                cast_command.append(
                    "-no-audio"
                )


            # -------------------------------------------------
            # PREVENT COMPUTER SLEEP
            # -------------------------------------------------

            command = [

                "systemd-inhibit",

                "--what=sleep:idle",

                "--who=Apple TV Cast",

                "--why=Casting screen to Apple TV",

                "--mode=block"

            ] + cast_command


            # -------------------------------------------------
            # START DOUBLETAKE
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


            # Give Doubletake a moment to fail if one
            # of the command-line arguments is invalid.

            time.sleep(
                0.15
            )


            if self.cast_process.poll() is not None:

                self.cast_process = None

                messagebox.showerror(
                    "Casting Error",
                    (
                        "Doubletake exited immediately.\n\n"
                        "Check the custom Doubletake build "
                        "and selected resolution."
                    )
                )

                return


            # -------------------------------------------------
            # STATUS
            # -------------------------------------------------

            offset = (
                self.audio_offset_ms.get()
            )

            audio_timing = (
                120 + offset
            )


            if offset > 0:

                offset_text = (
                    f"+{offset} ms"
                )

            else:

                offset_text = (
                    f"{offset} ms"
                )


            if self.audio_mode.get() == "bluetooth":

                status = (
                    "Casting to Living Room Apple TV "
                    f"— {selected_resolution} "
                    f"({width}×{height}) "
                    "— Video Only "
                    "| Audio → Bluetooth "
                    "| Video 120 ms "
                    "| Sleep Disabled"
                )

            else:

                status = (
                    "Casting to Living Room Apple TV "
                    f"— {selected_resolution} "
                    f"({width}×{height}) "
                    "— Video + Audio "
                    "| Video 120 ms "
                    f"| Audio {audio_timing} ms "
                    f"({offset_text}) "
                    "| Sleep Disabled"
                )


            self.cast_status.config(
                text=status
            )


            self.cast_button.config(
                state="disabled"
            )


        except Exception as error:

            self.cast_process = None

            messagebox.showerror(
                "Casting Error",
                str(error)
            )


    def stop_cast(
        self,
        cancel_restart=True
    ):

        # -------------------------------------------------
        # CANCEL PENDING RESTART
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


            if (
                service.stdout.strip()
                == "active"
            ):

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


            if (
                "Powered: yes"
                in controller.stdout
            ):

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


            for line in (
                devices.stdout
                .splitlines()
            ):

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


        # -------------------------------------------------
        # CONNECT BLUETOOTH
        # -------------------------------------------------

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


        # Give PipeWire time to create sink.

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


        # -------------------------------------------------
        # SET DEFAULT AUDIO OUTPUT
        # -------------------------------------------------

        self.run_command(
            [
                "pactl",
                "set-default-sink",
                sink
            ]
        )


        # -------------------------------------------------
        # MOVE EXISTING AUDIO STREAMS
        # -------------------------------------------------

        inputs = self.run_command(
            [
                "pactl",
                "list",
                "short",
                "sink-inputs"
            ]
        )


        for line in (
            inputs.stdout
            .splitlines()
        ):

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


        # -------------------------------------------------
        # SWITCH TO BLUETOOTH MODE
        # -------------------------------------------------

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


        for line in (
            sinks.stdout
            .splitlines()
        ):

            pieces = line.split()


            if len(pieces) < 2:
                continue


            name = pieces[1]


            if (
                "bluez"
                in name.lower()
            ):

                bluez_sinks.append(
                    name
                )


                if (
                    mac_pipewire
                    in name.lower()
                ):

                    return name


        if (
            len(bluez_sinks)
            == 1
        ):

            return (
                bluez_sinks[0]
            )


        return None


    # =====================================================
    # AUDIO STATUS
    # =====================================================

    def refresh_audio(self):

        try:

            result = self.run_command(
                [
                    "pactl",
                    "get-default-sink"
                ]
            )


            sink = (
                result.stdout.strip()
            )


            self.audio_status.config(
                text=sink
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

        self.update_audio_offset_status()


    # =====================================================
    # CLOSE
    # =====================================================

    def destroy(self):

        self.stop_cast(
            cancel_restart=True
        )

        super().destroy()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = CastingApp()

    app.mainloop()