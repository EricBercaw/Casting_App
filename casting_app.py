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
# MAIN APP
# =========================================================

class CastingApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Apple TV Cast")
        self.geometry("650x750")
        self.resizable(True, True)

        self.cast_process = None
        self.bluetooth_devices = {}

        # -------------------------------------------------
        # AUDIO MODE
        #
        # bluetooth:
        #   Apple TV = video only
        #   Bluetooth speaker = audio
        #
        # cast:
        #   Apple TV = video + audio
        #
        # DEFAULT:
        #   Apple TV video + audio
        # -------------------------------------------------

        self.audio_mode = tk.StringVar(
            value="cast"
        )

        self.audio_offset_ms = tk.IntVar(value=0)

        # Casting resolution / quality
        self.quality = tk.StringVar(value="720p")

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
            text="Cast desktop to Apple TV with selectable audio output"
        )

        subtitle.pack(
            anchor="w",
            pady=(0, 18)
        )


        # =================================================
        # APPLE TV SECTION
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
        # CAST QUALITY
        # =================================================

        quality_frame = ttk.LabelFrame(
            main,
            text="Cast Quality",
            padding=12
        )

        quality_frame.pack(
            fill="x",
            pady=(18, 0)
        )


        ttk.Label(
            quality_frame,
            text="Resolution:"
        ).pack(
            side="left",
            padx=(0, 12)
        )


        ttk.Radiobutton(
            quality_frame,
            text="480p",
            variable=self.quality,
            value="480p"
        ).pack(
            side="left",
            padx=(0, 12)
        )


        ttk.Radiobutton(
            quality_frame,
            text="720p",
            variable=self.quality,
            value="720p"
        ).pack(
            side="left",
            padx=(0, 12)
        )


        ttk.Radiobutton(
            quality_frame,
            text="1080p",
            variable=self.quality,
            value="1080p"
        ).pack(
            side="left",
            padx=(0, 12)
        )


        ttk.Radiobutton(
            quality_frame,
            text="4K",
            variable=self.quality,
            value="4k"
        ).pack(
            side="left"
        )


        # =================================================
        # AUDIO OUTPUT MODE
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
            text="Bluetooth Speaker — Apple TV receives video only",
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
        # AUDIO SYNC OFFSET
        # =================================================

        offset_frame = ttk.Frame(
            audio_mode_frame
        )

        offset_frame.pack(
            anchor="w",
            pady=(12, 0)
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
            text="Audio offset: 0 ms"
        )

        self.audio_offset_status.pack(
            anchor="w",
            pady=(8, 0)
        )

        # =================================================
        # BLUETOOTH SECTION
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
        # CURRENT AUDIO STATUS
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
                "\nHow to use:\n\n"
                "Apple TV Audio — Default:\n"
                "1. Apple TV — Cast video + audio is selected automatically.\n"
                "2. Click Cast Screen.\n"
                "3. Apple TV receives both video and cast audio.\n\n"
                "Bluetooth Audio:\n"
                "1. Select or connect your Bluetooth speaker.\n"
                "2. Bluetooth mode will be selected automatically.\n"
                "3. Click Cast Screen.\n"
                "4. Apple TV receives video only; audio stays on Bluetooth.\n\n"
                "Sleep is automatically disabled while casting."
            ),
            justify="left"
        )

        info.pack(
            anchor="w"
        )


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



    # =====================================================
    # AUDIO SYNC OFFSET
    # =====================================================

    def update_audio_offset_status(self):

        offset = self.audio_offset_ms.get()

        if offset > 0:

            text = (
                f"Audio offset: +{offset} ms "
                "(audio later)"
            )

        elif offset < 0:

            text = (
                f"Audio offset: {offset} ms "
                "(audio earlier)"
            )

        else:

            text = "Audio offset: 0 ms"

        self.audio_offset_status.config(
            text=text
        )


    def restart_cast_for_audio_offset(self):

        is_casting = (
            self.cast_process
            and
            self.cast_process.poll() is None
        )

        # The audio offset only affects Apple TV audio mode.
        if (
            is_casting
            and
            self.audio_mode.get() == "cast"
        ):

            self.stop_cast()

            self.cast_status.config(
                text="Restarting cast with new audio sync..."
            )

            # Give Doubletake / Apple TV a moment to close
            # the old AirPlay session before reconnecting.
            self.after(
                700,
                self.start_cast
            )


    def adjust_audio_offset(
        self,
        delta
    ):

        current = self.audio_offset_ms.get()

        new_offset = current + delta

        # Plenty of adjustment range while preventing
        # accidental extreme values.
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

        self.restart_cast_for_audio_offset()


    def reset_audio_offset(self):

        if self.audio_offset_ms.get() == 0:

            return

        self.audio_offset_ms.set(
            0
        )

        self.update_audio_offset_status()

        self.restart_cast_for_audio_offset()


    # =====================================================
    # HELPER
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
    # CASTING
    # =====================================================

    def start_cast(self):

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
                "Doubletake was not found at:\n\n"
                + DOUBLETAKE_PATH
            )

            return


        try:

            # -------------------------------------------------
            # BASE DOUBLETAKE COMMAND
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

                # Use Doubletake's automatic A/V timing policy.
                "-target-latency-ms",
                "0",

                # Add extra buffering to BOTH audio and video
                # while preserving their normal relative timing.
                "-quality",
                self.quality.get(),
                "-latency-margin-ms",
                "40",

                # Fine A/V synchronization adjustment.
                #
                # Positive = audio later
                # Negative = audio earlier
                "-audio-offset-ms",
                str(self.audio_offset_ms.get()),

                "-port-range",
                "60000-60010"

            ]


            # -------------------------------------------------
            # AUDIO MODE
            #
            # BLUETOOTH:
            #   Add -no-audio.
            #   Apple TV receives video only.
            #
            # CAST:
            #   No -no-audio option.
            #   Apple TV receives video + audio.
            # -------------------------------------------------

            if self.audio_mode.get() == "bluetooth":

                cast_command.append(
                    "-no-audio"
                )


            # -------------------------------------------------
            # PREVENT COMPUTER FROM SLEEPING
            # -------------------------------------------------

            command = [

                "systemd-inhibit",

                "--what=sleep:idle",

                "--who=Apple TV Cast",

                "--why=Casting screen to Apple TV",

                "--mode=block"

            ] + cast_command


            # -------------------------------------------------
            # START CAST
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


            # -------------------------------------------------
            # UPDATE STATUS
            # -------------------------------------------------

            if self.audio_mode.get() == "bluetooth":

                self.cast_status.config(
                    text=(
                        "Casting to Living Room Apple TV "
                        "— Video Only | Audio → Bluetooth "
                        "| Sleep Disabled"
                    )
                )

            else:

                self.cast_status.config(
                    text=(
                        "Casting to Living Room Apple TV "
                        "— Video + Audio | Sleep Disabled"
                    )
                )


            self.cast_button.config(
                state="disabled"
            )


        except Exception as error:

            messagebox.showerror(
                "Casting Error",
                str(error)
            )


    def stop_cast(self):

        if not self.cast_process:

            self.cast_status.config(
                text="Not Casting"
            )

            return


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
                text=
                "Bluetooth error: "
                + str(error)
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
                "No paired Bluetooth speaker found.\n\n"
                "Click Open Bluetooth Manager first."
            )

            return


        mac = (
            self.bluetooth_devices[
                selected
            ]
        )


        # -------------------------------------------------
        # CONNECT BLUETOOTH DEVICE
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


        # Give PipeWire time to create the Bluetooth sink.

        time.sleep(
            2
        )


        sink = self.find_bluetooth_sink(
            mac
        )


        if not sink:

            messagebox.showerror(
                "Audio",
                "Bluetooth connected, but no "
                "Bluetooth audio output appeared."
            )

            self.refresh_all()

            return


        # -------------------------------------------------
        # SET BLUETOOTH AS DEFAULT AUDIO OUTPUT
        # -------------------------------------------------

        self.run_command(
            [
                "pactl",
                "set-default-sink",
                sink
            ]
        )


        # -------------------------------------------------
        # MOVE EXISTING AUDIO STREAMS TO BLUETOOTH
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
        # USER EXPLICITLY SELECTED BLUETOOTH AUDIO,
        # SO SWITCH CASTING MODE TO BLUETOOTH
        # -------------------------------------------------

        self.audio_mode.set(
            "bluetooth"
        )

        self.audio_mode_changed()


        self.refresh_audio()


        messagebox.showinfo(
            "Bluetooth",
            "Bluetooth speaker is now "
            "your audio output.\n\n"
            "Apple TV casting will use video-only mode."
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
    # REFRESH ALL
    # =====================================================

    def refresh_all(self):

        self.refresh_bluetooth()
        self.audio_mode_changed()


    # =====================================================
    # CLOSE
    # =====================================================

    def destroy(self):

        self.stop_cast()

        super().destroy()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = CastingApp()

    app.mainloop()