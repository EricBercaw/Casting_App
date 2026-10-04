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

# Bluetooth audio is deliberately delayed to match the Apple TV video path.
BASE_BLUETOOTH_AUDIO_DELAY_MS = 190
AUDIO_DELAY_ADJUST_MIN_MS = -50
AUDIO_DELAY_ADJUST_MAX_MS = 50
AUDIO_DELAY_STEP_MS = 5
DELAY_SINK_NAME = "bt_delay"
DELAY_SINK_DESCRIPTION = "Living Room Audio (Synced)"

BLUETOOTH_VOLUME_DEFAULT = 40
BLUETOOTH_VOLUME_MIN = 0
BLUETOOTH_VOLUME_MAX = 100
BLUETOOTH_VOLUME_STEP = 1
BLUETOOTH_VOLUME_CONFIG = os.path.expanduser(
    "~/.config/apple-tv-cast/volume"
)





class CastingApp(tk.Tk):

    def __init__(self):

        super().__init__()



        self.title("Apple TV Cast")

        self.geometry("820x1000")

        self.resizable(True, True)



        self.cast_process = None

        self.bluetooth_devices = {}

        self.restart_job = None

        self.cast_monitor_job = None

        self.bluetooth_monitor_job = None
        self.bluetooth_was_connected = False
        self.bluetooth_routed_sink = None
        self.audio_delay_null_module_id = None
        self.audio_delay_loopback_module_id = None
        self.audio_delay_physical_sink = None
        self.audio_delay_job = None



        self.bluetooth_volume_job = None
        self.screensaver_window_id = None

        self.screensaver_suspended = False



        self.resolution = tk.StringVar(value="720p")
        self.audio_delay_adjustment = tk.IntVar(value=0)



        self.bluetooth_volume = tk.IntVar(
            value=self.load_saved_volume()
        )
        # Higher-DPI Tk rendering
        try:
            self.tk.call("tk", "scaling", 1.35)
        except Exception:
            pass

        self.setup_dark_theme()
        self.create_ui()
        self.style_native_sliders()

        self.refresh_all()
        self.start_bluetooth_monitor()



    # =====================================================

    # UI

    # =====================================================




    def setup_dark_theme(self):
        """Configure the app's dark visual theme."""

        self.ui_bg = "#000000"
        self.ui_panel = "#0d0d0d"
        self.ui_panel_alt = "#181818"
        self.ui_border = "#3a3a3a"

        self.ui_text = "#ffffff"
        self.ui_muted = "#c0c0c0"

        self.ui_accent = "#ffffff"
        self.ui_accent_hover = "#dddddd"

        self.ui_danger = "#dc2626"
        self.ui_danger_hover = "#ef4444"

        self.configure(bg=self.ui_bg)

        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=self.ui_bg,
            foreground=self.ui_text,
            font=("DejaVu Sans", 11),
        )

        style.configure(
            "TFrame",
            background=self.ui_bg,
        )

        style.configure(
            "TLabel",
            background=self.ui_bg,
            foreground=self.ui_text,
        )

        style.configure(
            "Title.TLabel",
            background=self.ui_bg,
            foreground="#ffffff",
            font=("DejaVu Sans", 24, "bold"),
        )

        style.configure(
            "Subtitle.TLabel",
            background=self.ui_bg,
            foreground=self.ui_muted,
            font=("DejaVu Sans", 11),
        )

        style.configure(
            "TLabelframe",
            background=self.ui_bg,
            foreground=self.ui_text,
            bordercolor=self.ui_border,
            lightcolor=self.ui_border,
            darkcolor=self.ui_border,
            borderwidth=1,
            relief="solid",
        )

        style.configure(
            "TLabelframe.Label",
            background=self.ui_bg,
            foreground="#ffffff",
            font=("DejaVu Sans", 11, "bold"),
        )

        style.configure(
            "TButton",
            background=self.ui_panel_alt,
            foreground=self.ui_text,
            borderwidth=0,
            focusthickness=0,
            padding=(13, 8),
            font=("DejaVu Sans", 11),
        )

        style.map(
            "TButton",
            background=[
                ("pressed", "#1e293b"),
                ("active", "#26344d"),
                ("disabled", "#111827"),
            ],
            foreground=[
                ("disabled", "#64748b"),
            ],
        )

        style.configure(
            "Accent.TButton",
            background="#ffffff",
            foreground="#000000",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("DejaVu Sans", 10, "bold"),
        )

        style.map(
            "Accent.TButton",
            background=[
                ("pressed", "#bfbfbf"),
                ("active", "#e5e5e5"),
                ("disabled", "#1e3a5f"),
            ],
            foreground=[
                ("disabled", "#94a3b8"),
            ],
        )

        style.configure(
            "Danger.TButton",
            background="#7f1d1d",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("DejaVu Sans", 10, "bold"),
        )

        style.map(
            "Danger.TButton",
            background=[
                ("pressed", "#991b1b"),
                ("active", self.ui_danger_hover),
            ],
        )

        style.configure(
            "TRadiobutton",
            background=self.ui_bg,
            foreground=self.ui_text,
            indicatorbackground=self.ui_panel_alt,
            indicatormargin=5,
        )

        style.map(
            "TRadiobutton",
            background=[
                ("active", self.ui_bg),
                ("selected", self.ui_bg),
            ],
            foreground=[
                ("active", "#ffffff"),
                ("selected", "#ffffff"),
            ],
            indicatorbackground=[
                ("selected", self.ui_accent),
                ("active", self.ui_panel_alt),
            ],
        )

        style.configure(
            "White.Vertical.TScrollbar",
            background="#ffffff",
            troughcolor="#000000",
            bordercolor="#000000",
            lightcolor="#ffffff",
            darkcolor="#ffffff",
            arrowcolor="#000000",
        )

        style.map(
            "White.Vertical.TScrollbar",
            background=[
                ("active", "#dddddd"),
                ("pressed", "#bbbbbb"),
            ],
        )

        style.configure(
            "TCombobox",
            fieldbackground=self.ui_panel_alt,
            background=self.ui_panel_alt,
            foreground=self.ui_text,
            arrowcolor=self.ui_text,
            bordercolor=self.ui_border,
            lightcolor=self.ui_border,
            darkcolor=self.ui_border,
            padding=6,
        )

        style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", self.ui_panel_alt),
            ],
            foreground=[
                ("readonly", self.ui_text),
            ],
            selectbackground=[
                ("readonly", self.ui_accent),
            ],
            selectforeground=[
                ("readonly", "#ffffff"),
            ],
        )


    def style_native_sliders(self):
        """Dark styling for tkinter Scale widgets."""

        for name in (
            "audio_delay_scale",
            "bluetooth_volume_scale",
        ):
            slider = getattr(self, name, None)

            if slider is None:
                continue

            slider.configure(
                bg=self.ui_bg,
                fg=self.ui_text,
                activebackground=self.ui_accent_hover,
                troughcolor=self.ui_panel_alt,
                highlightthickness=0,
                bd=0,
                relief="flat",
            )



    def _on_ui_mousewheel(self, event):
        """Scroll the main UI with the mouse wheel."""

        if not hasattr(self, "ui_canvas"):
            return

        if getattr(event, "num", None) == 4:
            self.ui_canvas.yview_scroll(-3, "units")

        elif getattr(event, "num", None) == 5:
            self.ui_canvas.yview_scroll(3, "units")

        elif getattr(event, "delta", 0):
            direction = -1 if event.delta > 0 else 1
            self.ui_canvas.yview_scroll(
                direction * 3,
                "units",
            )


    def _update_ui_scroll_region(self, _event=None):
        if hasattr(self, "ui_canvas"):
            self.ui_canvas.configure(
                scrollregion=self.ui_canvas.bbox("all")
            )


    def _resize_scrollable_frame(self, event):
        if (
            hasattr(self, "ui_canvas")
            and hasattr(self, "ui_canvas_window")
        ):
            self.ui_canvas.itemconfigure(
                self.ui_canvas_window,
                width=event.width,
            )


    def create_ui(self):

        scroll_container = ttk.Frame(self)
        scroll_container.pack(
            fill="both",
            expand=True,
        )

        self.ui_canvas = tk.Canvas(
            scroll_container,
            bg=self.ui_bg,
            highlightthickness=0,
            bd=0,
        )

        self.ui_scrollbar = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=self.ui_canvas.yview,
            style="White.Vertical.TScrollbar",
        )

        self.ui_canvas.configure(
            yscrollcommand=self.ui_scrollbar.set
        )

        self.ui_scrollbar.pack(
            side="right",
            fill="y",
        )

        self.ui_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        main = ttk.Frame(
            self.ui_canvas,
            padding=18
        )

        self.ui_canvas_window = self.ui_canvas.create_window(
            (0, 0),
            window=main,
            anchor="nw",
        )

        main.bind(
            "<Configure>",
            self._update_ui_scroll_region,
        )

        self.ui_canvas.bind(
            "<Configure>",
            self._resize_scrollable_frame,
        )

        self.bind_all(
            "<MouseWheel>",
            self._on_ui_mousewheel,
        )

        self.bind_all(
            "<Button-4>",
            self._on_ui_mousewheel,
        )

        self.bind_all(
            "<Button-5>",
            self._on_ui_mousewheel,
        )



        ttk.Label(

            main,

            text="Apple TV Cast",

            style="Title.TLabel",

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

            text="Selected: 720p (1280x720)",

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


        # -------------------------------------------------
        # BLUETOOTH VOLUME
        # -------------------------------------------------

        volume_frame = ttk.LabelFrame(
            main,
            text="Bluetooth Volume",
            padding=12,
        )
        volume_frame.pack(fill="x", pady=(18, 0))

        ttk.Label(
            volume_frame,
            text=(
                "Controls the loudness of Living Room Audio / ESP32. "
                "This does not change the Apple TV video stream or "
                "Bluetooth synchronization delay."
            ),
            wraplength=660,
        ).pack(anchor="w")

        volume_row = ttk.Frame(volume_frame)
        volume_row.pack(fill="x", pady=(8, 0))

        ttk.Label(
            volume_row,
            text="0%"
        ).pack(side="left")

        self.bluetooth_volume_scale = tk.Scale(
            volume_row,
            from_=BLUETOOTH_VOLUME_MIN,
            to=BLUETOOTH_VOLUME_MAX,
            resolution=BLUETOOTH_VOLUME_STEP,
            orient="horizontal",
            showvalue=False,
            variable=self.bluetooth_volume,
            command=self.bluetooth_volume_changed,
            length=480,
        )
        self.bluetooth_volume_scale.pack(
            side="left",
            fill="x",
            expand=True,
            padx=10,
        )

        ttk.Label(
            volume_row,
            text="100%"
        ).pack(side="left")

        self.bluetooth_volume_status = ttk.Label(
            volume_frame,
            text=f"Volume: {self.bluetooth_volume.get()}%",
        )
        self.bluetooth_volume_status.pack(
            anchor="w",
            pady=(8, 0),
        )


        # BLUETOOTH AUDIO SYNC

        # -------------------------------------------------

        sync_frame = ttk.LabelFrame(

            main,

            text="Bluetooth Audio Sync",

            padding=12,

        )

        sync_frame.pack(fill="x", pady=(18, 0))



        ttk.Label(

            sync_frame,

            text=(

                "Base delay is 190 ms. Use the slider to fine-tune Bluetooth "

                "audio from -50 ms to +50 ms without changing the video cast."

            ),

            wraplength=660,

        ).pack(anchor="w")



        slider_row = ttk.Frame(sync_frame)

        slider_row.pack(fill="x", pady=(8, 0))



        ttk.Label(slider_row, text="-50 ms").pack(side="left")



        self.audio_delay_scale = tk.Scale(

            slider_row,

            from_=AUDIO_DELAY_ADJUST_MIN_MS,

            to=AUDIO_DELAY_ADJUST_MAX_MS,

            resolution=AUDIO_DELAY_STEP_MS,

            orient="horizontal",

            showvalue=False,

            variable=self.audio_delay_adjustment,

            command=self.audio_delay_changed,

            length=480,

        )

        self.audio_delay_scale.pack(side="left", fill="x", expand=True, padx=10)



        ttk.Label(slider_row, text="+50 ms").pack(side="left")



        self.audio_delay_status = ttk.Label(

            sync_frame,

            text="Fine tune: +0 ms | Total Bluetooth audio delay: 190 ms",

        )

        self.audio_delay_status.pack(anchor="w", pady=(8, 0))



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

                "• 720p default; 480p / 1080p / 4K selectable\n"

                "• VAAPI hardware encoding\n"

                f"• {LATENCY_MARGIN_MS} ms video stability margin\n"

                f"• Bluetooth audio delay: {BASE_BLUETOOTH_AUDIO_DELAY_MS} ms base "
                "with ±50 ms fine tuning\n"
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




    def load_saved_volume(self):
        try:
            with open(
                BLUETOOTH_VOLUME_CONFIG,
                "r",
                encoding="utf-8",
            ) as handle:
                value = int(handle.read().strip())

            return max(
                BLUETOOTH_VOLUME_MIN,
                min(BLUETOOTH_VOLUME_MAX, value),
            )
        except Exception:
            return BLUETOOTH_VOLUME_DEFAULT


    def save_bluetooth_volume(self):
        try:
            directory = os.path.dirname(
                BLUETOOTH_VOLUME_CONFIG
            )
            os.makedirs(directory, exist_ok=True)

            with open(
                BLUETOOTH_VOLUME_CONFIG,
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    str(self.bluetooth_volume.get())
                )
        except Exception:
            pass


    def update_bluetooth_volume_status(self):
        self.bluetooth_volume_status.config(
            text=f"Volume: {self.bluetooth_volume.get()}%"
        )


    def bluetooth_volume_changed(self, _value=None):
        self.update_bluetooth_volume_status()
        self.save_bluetooth_volume()

        if self.bluetooth_volume_job is not None:
            try:
                self.after_cancel(
                    self.bluetooth_volume_job
                )
            except Exception:
                pass

        # Small debounce prevents dozens of pactl calls while
        # dragging the slider.
        self.bluetooth_volume_job = self.after(
            80,
            self.apply_bluetooth_volume,
        )


    def apply_bluetooth_volume(self):
        self.bluetooth_volume_job = None

        mac = self.get_target_bluetooth_mac()

        if not mac or not self.is_bluetooth_connected(mac):
            return

        physical_sink = self.find_bluetooth_sink(mac)

        if not physical_sink:
            return

        volume = self.bluetooth_volume.get()

        self.run_command(
            [
                "pactl",
                "set-sink-mute",
                physical_sink,
                "0",
            ]
        )

        self.run_command(
            [
                "pactl",
                "set-sink-volume",
                physical_sink,
                f"{volume}%",
            ]
        )


    def get_total_audio_delay_ms(self):

        return max(

            0,

            BASE_BLUETOOTH_AUDIO_DELAY_MS + self.audio_delay_adjustment.get(),

        )



    def update_audio_delay_status(self):

        adjustment = self.audio_delay_adjustment.get()

        total = self.get_total_audio_delay_ms()

        sign = "+" if adjustment >= 0 else ""

        self.audio_delay_status.config(

            text=(

                f"Fine tune: {sign}{adjustment} ms | "

                f"Total Bluetooth audio delay: {total} ms"

            )

        )



    def audio_delay_changed(self, _value=None):

        self.update_audio_delay_status()



        if self.audio_delay_job is not None:

            try:

                self.after_cancel(self.audio_delay_job)

            except Exception:

                pass



        # Debounce slider movement so we do not continuously reload the

        # loopback module while the user is dragging the control.

        self.audio_delay_job = self.after(300, self.apply_audio_delay_change)



    def apply_audio_delay_change(self):

        self.audio_delay_job = None

        mac = self.get_target_bluetooth_mac()



        if not mac or not self.is_bluetooth_connected(mac):

            return



        sink = self.find_bluetooth_sink(mac)

        if not sink:

            return



        self.ensure_audio_delay_path(sink, recreate_loopback=True)

        self.run_command(["pactl", "set-default-sink", DELAY_SINK_NAME])

        self.move_application_audio_to_sink(DELAY_SINK_NAME)

        self.refresh_audio()



    def get_resolution(self):

        return RESOLUTIONS.get(

            self.resolution.get(),

            RESOLUTIONS["720p"],

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

        # Cancel any delayed restart before touching the running process.
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



        # First stop the process group started by this app.
        if process is not None and process.poll() is None:

            try:

                os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                process.wait(timeout=2)

            except subprocess.TimeoutExpired:

                try:

                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)

                    process.wait(timeout=1)

                except Exception:

                    pass

            except Exception:

                try:

                    process.terminate()

                except Exception:

                    pass



        # systemd-inhibit can occasionally leave the DoubleTake child alive.
        # Kill any remaining instance of this exact custom DoubleTake binary.
        try:

            leftovers = self.run_command(["pgrep", "-f", DOUBLETAKE_PATH])

            for line in leftovers.stdout.splitlines():

                try:

                    pid = int(line.strip())

                    if pid != os.getpid():

                        os.kill(pid, signal.SIGTERM)

                except (ValueError, ProcessLookupError, PermissionError):

                    pass

            time.sleep(0.15)

            leftovers = self.run_command(["pgrep", "-f", DOUBLETAKE_PATH])

            for line in leftovers.stdout.splitlines():

                try:

                    pid = int(line.strip())

                    if pid != os.getpid():

                        os.kill(pid, signal.SIGKILL)

                except (ValueError, ProcessLookupError, PermissionError):

                    pass

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



    def get_target_bluetooth_mac(self):

        for label, mac in self.bluetooth_devices.items():

            name = label.rsplit(" [", 1)[0]

            if name.casefold() == TARGET_BLUETOOTH_NAME.casefold():

                return mac



        # Refresh the paired-device list if the app has not seen the target yet.

        try:

            devices = self.run_command(

                ["bluetoothctl", "devices", "Paired"]

            )

            for line in devices.stdout.splitlines():

                match = re.match(

                    r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)",

                    line,

                )

                if not match:

                    continue

                mac = match.group(1)

                name = match.group(2).strip()

                if name.casefold() == TARGET_BLUETOOTH_NAME.casefold():

                    return mac

        except Exception:

            pass



        return None



    def is_bluetooth_connected(self, mac):

        if not mac:

            return False

        try:

            info = self.run_command(["bluetoothctl", "info", mac])

            return "Connected: yes" in info.stdout

        except Exception:

            return False



    def get_sink_index(self, sink_name):

        try:

            sinks = self.run_command(["pactl", "list", "short", "sinks"])

            for line in sinks.stdout.splitlines():

                pieces = line.split()

                if len(pieces) >= 2 and pieces[1] == sink_name:

                    return pieces[0]

        except Exception:

            pass



        return None



    def get_sink_inputs(self):

        """Return sink-input id, sink index and owner module when available."""

        result = self.run_command(["pactl", "list", "sink-inputs"])

        items = []

        current = None



        for raw_line in result.stdout.splitlines():

            line = raw_line.strip()

            match = re.match(r"Sink Input #(\d+)", line)

            if match:

                if current is not None:

                    items.append(current)

                current = {

                    "id": match.group(1),

                    "sink": None,

                    "owner_module": None,

                }

                continue



            if current is None:

                continue



            if line.startswith("Owner Module:"):

                current["owner_module"] = line.split(":", 1)[1].strip()

            elif line.startswith("Sink:"):

                current["sink"] = line.split(":", 1)[1].strip()



        if current is not None:

            items.append(current)



        return items



    def move_application_audio_to_sink(self, target_sink):

        target_index = self.get_sink_index(target_sink)

        if target_index is None:

            return



        loopback_owner = (

            str(self.audio_delay_loopback_module_id)

            if self.audio_delay_loopback_module_id is not None

            else None

        )



        for item in self.get_sink_inputs():

            # Never move our own bt_delay -> Bluetooth loopback stream.

            if loopback_owner and item.get("owner_module") == loopback_owner:

                continue



            if item.get("sink") == str(target_index):

                continue



            self.run_command(

                ["pactl", "move-sink-input", item["id"], target_sink]

            )



    def unload_module(self, module_id):

        if module_id is None:

            return



        try:

            self.run_command(["pactl", "unload-module", str(module_id)])

        except Exception:

            pass



    def remove_stale_audio_delay_modules(self):

        """Remove bt_delay modules left over from an earlier app/test run."""

        try:

            modules = self.run_command(["pactl", "list", "short", "modules"])

            loopbacks = []

            null_sinks = []



            for line in modules.stdout.splitlines():

                pieces = line.split(None, 2)

                if len(pieces) < 2:

                    continue



                module_id = pieces[0]

                module_name = pieces[1]

                arguments = pieces[2] if len(pieces) >= 3 else ""



                if (

                    module_name == "module-loopback"

                    and f"source={DELAY_SINK_NAME}.monitor" in arguments

                ):

                    loopbacks.append(module_id)

                elif (

                    module_name == "module-null-sink"

                    and f"sink_name={DELAY_SINK_NAME}" in arguments

                ):

                    null_sinks.append(module_id)



            for module_id in loopbacks:

                self.unload_module(module_id)



            for module_id in null_sinks:

                self.unload_module(module_id)

        except Exception:

            pass



        self.audio_delay_loopback_module_id = None

        self.audio_delay_null_module_id = None

        self.audio_delay_physical_sink = None



    def ensure_audio_delay_path(self, physical_sink, recreate_loopback=False):

        if not physical_sink:

            return False



        delay_sink_exists = self.get_sink_index(DELAY_SINK_NAME) is not None



        if (

            not delay_sink_exists

            or self.audio_delay_null_module_id is None

            or self.audio_delay_physical_sink != physical_sink

        ):

            self.remove_stale_audio_delay_modules()



            null_result = self.run_command(

                [

                    "pactl",

                    "load-module",

                    "module-null-sink",

                    f"sink_name={DELAY_SINK_NAME}",

                    f"sink_properties=device.description={DELAY_SINK_DESCRIPTION.replace(' ', '_')}",

                ]

            )



            if null_result.returncode != 0 or not null_result.stdout.strip():

                return False



            self.audio_delay_null_module_id = null_result.stdout.strip()

            self.audio_delay_physical_sink = physical_sink

            recreate_loopback = True



        if recreate_loopback or self.audio_delay_loopback_module_id is None:

            self.unload_module(self.audio_delay_loopback_module_id)

            self.audio_delay_loopback_module_id = None



            total_delay = self.get_total_audio_delay_ms()

            loop_result = self.run_command(

                [

                    "pactl",

                    "load-module",

                    "module-loopback",

                    f"source={DELAY_SINK_NAME}.monitor",

                    f"sink={physical_sink}",

                    f"latency_msec={total_delay}",

                    "source_dont_move=true",

                    "sink_dont_move=true",

                ]

            )



            if loop_result.returncode != 0 or not loop_result.stdout.strip():

                return False



            self.audio_delay_loopback_module_id = loop_result.stdout.strip()



        return True



    def choose_fallback_sink(self):

        try:

            sinks = self.run_command(["pactl", "list", "short", "sinks"])

            candidates = []



            for line in sinks.stdout.splitlines():

                pieces = line.split()

                if len(pieces) < 2:

                    continue



                sink = pieces[1]

                if sink == DELAY_SINK_NAME:

                    continue

                if "bluez" in sink.lower():

                    continue

                candidates.append(sink)



            return candidates[0] if candidates else None

        except Exception:

            return None



    def cleanup_audio_delay_path(self, restore_sink=None):

        if restore_sink is None:

            restore_sink = self.choose_fallback_sink()



        if restore_sink and self.get_sink_index(restore_sink) is not None:

            self.run_command(["pactl", "set-default-sink", restore_sink])

            self.move_application_audio_to_sink(restore_sink)



        self.unload_module(self.audio_delay_loopback_module_id)

        self.audio_delay_loopback_module_id = None



        self.unload_module(self.audio_delay_null_module_id)

        self.audio_delay_null_module_id = None

        self.audio_delay_physical_sink = None



    def route_audio_to_bluetooth(

        self,

        mac,

        wait_for_sink=False,

        initialize_volume=False,

    ):

        physical_sink = None

        attempts = 10 if wait_for_sink else 1



        for attempt in range(attempts):

            physical_sink = self.find_bluetooth_sink(mac)

            if physical_sink:

                break

            if attempt < attempts - 1:

                time.sleep(0.5)



        if not physical_sink:

            return None



        # The real Bluetooth sink stays unmuted, but applications play into

        # bt_delay. bt_delay.monitor is then looped to Bluetooth with the

        # requested latency.

        self.run_command(["pactl", "set-sink-mute", physical_sink, "0"])



        if initialize_volume:

            self.run_command(["pactl", "set-sink-volume", physical_sink, f"{self.bluetooth_volume.get()}%"])



        if not self.ensure_audio_delay_path(physical_sink):

            return None



        self.run_command(["pactl", "set-default-sink", DELAY_SINK_NAME])

        self.move_application_audio_to_sink(DELAY_SINK_NAME)



        self.refresh_audio()

        return physical_sink



    def start_bluetooth_monitor(self):

        if self.bluetooth_monitor_job is not None:

            try:

                self.after_cancel(self.bluetooth_monitor_job)

            except Exception:

                pass



        self.bluetooth_monitor_job = self.after(

            1000,

            self.monitor_bluetooth_connection,

        )



    def monitor_bluetooth_connection(self):

        self.bluetooth_monitor_job = None

        connected = False



        try:

            mac = self.get_target_bluetooth_mac()

            connected = self.is_bluetooth_connected(mac)



            if connected:

                sink = self.find_bluetooth_sink(mac)

                if sink:
                    # BlueZ can report Connected before PipeWire exposes the
                    # A2DP sink. Once the sink exists, always enforce routing
                    # and move existing streams. This mirrors the terminal
                    # sequence that reliably restores audio.
                    first_route = self.bluetooth_routed_sink != sink
                    routed_sink = self.route_audio_to_bluetooth(
                        mac,
                        wait_for_sink=False,
                        initialize_volume=first_route,
                    )

                    if routed_sink:
                        self.bluetooth_routed_sink = routed_sink
                        self.bluetooth_status.config(
                            text=(
                                f"{TARGET_BLUETOOTH_NAME}: Connected | "
                                f"Audio routing: Automatic | Delay: {self.get_total_audio_delay_ms()} ms | Volume: {self.bluetooth_volume.get()}%"
                            )
                        )
                    else:
                        self.bluetooth_status.config(
                            text=(
                                f"{TARGET_BLUETOOTH_NAME}: Connected | "
                                "Waiting for A2DP audio output..."
                            )
                        )
                else:
                    # Force an initial route as soon as the sink appears, even
                    # if BlueZ was already connected on the previous poll.
                    self.bluetooth_routed_sink = None
                    self.bluetooth_status.config(
                        text=(
                            f"{TARGET_BLUETOOTH_NAME}: Connected | "
                            "Waiting for A2DP audio output..."
                        )
                    )

            else:
                # Reset routing state so the same sink name is initialized
                # again on the next connection.
                self.bluetooth_routed_sink = None
                if self.bluetooth_was_connected:
                    # Remove the delayed virtual sink so PipeWire can fall
                    # back to a normal local output after Bluetooth disconnects.
                    self.cleanup_audio_delay_path()
                    self.refresh_bluetooth()



        except Exception:

            # Keep monitoring even if Bluetooth/PipeWire is temporarily busy.

            pass



        self.bluetooth_was_connected = connected

        self.bluetooth_monitor_job = self.after(

            1000,

            self.monitor_bluetooth_connection,

        )



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

        sink = self.route_audio_to_bluetooth(

            mac,

            wait_for_sink=True,

            initialize_volume=True,

        )



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



        self.bluetooth_routed_sink = sink
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

        # Refresh UI state without treating it as a user resolution change.
        # Calling resolution_changed() here can restart an active cast.
        selected = self.resolution.get()
        width, height = self.get_resolution()
        self.resolution_status.config(
            text=f"Selected: {selected} ({width}x{height})"
        )

        self.update_audio_delay_status()

        self.refresh_bluetooth()

        self.refresh_audio()



    def destroy(self):

        if self.bluetooth_monitor_job is not None:

            try:

                self.after_cancel(self.bluetooth_monitor_job)

            except Exception:

                pass

            self.bluetooth_monitor_job = None



        if self.audio_delay_job is not None:

            try:

                self.after_cancel(self.audio_delay_job)

            except Exception:

                pass

            self.audio_delay_job = None




        if self.bluetooth_volume_job is not None:
            try:
                self.after_cancel(
                    self.bluetooth_volume_job
                )
            except Exception:
                pass

            self.bluetooth_volume_job = None

        # Preserve ordinary Bluetooth audio when the app closes: remove the

        # sync buffer and return application audio to the physical BT sink.

        restore_sink = None

        mac = self.get_target_bluetooth_mac()

        if mac and self.is_bluetooth_connected(mac):

            restore_sink = self.find_bluetooth_sink(mac)



        self.cleanup_audio_delay_path(restore_sink=restore_sink)



        self.stop_cast(

            cancel_restart=True,

            release_screensaver=True,

        )

        super().destroy()




if __name__ == "__main__":

    app = CastingApp()

    app.mainloop()
