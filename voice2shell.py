#!/usr/bin/env python3
"""Voice2Shell — speak commands to your terminal."""

import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import numpy as np
import pyaudio
import scipy.signal as signal
import whisper

from platform_support import (
    PLATFORM, DEFAULT_FONT, AVAILABLE_TERMINALS, DEFAULT_TERMINAL,
    HOTKEY_OPTIONS, send_to_terminal, HotkeyListener,
)


class VoiceControl:
    def __init__(self):
        self.is_recording = False
        self.audio_frames = []
        self.audio_stream = None
        self.pyaudio_inst = pyaudio.PyAudio()
        dev_info = self.pyaudio_inst.get_default_input_device_info()
        self._mic_rate = int(dev_info['defaultSampleRate'])
        self._whisper_rate = 16000
        self.model = None
        self._model_loading = True
        self._silence_counter = 0
        self._current_energy = 0
        self._settings_visible = False
        self._hotkey_hold_start = 0
        self._hotkey_active = False
        self._hotkey_threshold = 0.3

        self.root = tk.Tk()
        self.root.title("Voice2Shell")
        self.root.attributes("-topmost", True)
        self.root.geometry("470x210")
        self.root.resizable(True, True)
        self.root.minsize(430, 170)
        self.root.configure(bg="#1e1e2e")

        self._build_ui()
        threading.Thread(target=self._load_model, daemon=True).start()

    def _build_ui(self):
        bg = "#1e1e2e"
        F = DEFAULT_FONT
        label_style = {"font": (F, 8), "bg": bg, "fg": "#6c7086", "anchor": "w"}
        slider_style = {
            "bg": bg, "fg": "#cdd6f4", "troughcolor": "#313244",
            "highlightthickness": 0, "sliderrelief": tk.FLAT,
            "font": (F, 8),
        }

        # --- Top button bar ---
        btn_frame = tk.Frame(self.root, bg="#313244")
        btn_frame.pack(fill=tk.X)

        btn_style = {
            "font": (F, 9, "bold"),
            "relief": tk.FLAT,
            "pady": 3,
            "cursor": "hand2",
            "borderwidth": 0,
            "width": 8,
        }

        self.record_btn = tk.Button(
            btn_frame, text="● Record", command=self._toggle_recording,
            bg="#f38ba8", fg="#1e1e2e", activebackground="#f5c2e7",
            **btn_style
        )
        self.record_btn.pack(side=tk.LEFT, padx=(6, 2), pady=3)

        self.exec_btn = tk.Button(
            btn_frame, text="▶ Send", command=self._execute,
            bg="#a6e3a1", fg="#1e1e2e", activebackground="#94e2d5",
            **btn_style
        )
        self.exec_btn.pack(side=tk.LEFT, padx=2, pady=3)

        self.clear_btn = tk.Button(
            btn_frame, text="✕ Clear", command=self._clear_input,
            bg="#11111b", fg="#f38ba8", activebackground="#313244",
            **btn_style
        )
        self.clear_btn.pack(side=tk.LEFT, padx=2, pady=3)

        # Settings gear button (pack RIGHT first so it never gets squeezed)
        gear_size = 24
        self.gear_canvas = tk.Canvas(
            btn_frame, width=gear_size, height=gear_size,
            bg="#313244", highlightthickness=0, cursor="hand2"
        )
        self.gear_canvas.pack(side=tk.RIGHT, padx=(0, 6), pady=3)
        self.gear_canvas.create_text(
            gear_size // 2, gear_size // 2, text="⚙",
            font=(F, 12), fill="#6c7086", tags="gear"
        )
        self.gear_canvas.bind("<Button-1>", lambda e: self._toggle_settings_panel())

        self.status_label = tk.Label(
            btn_frame, text="Ready", font=(F, 8),
            anchor="w", bg="#313244", fg="#a6adc8"
        )
        self.status_label.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 3))

        # --- Settings row ---
        settings_frame = tk.Frame(self.root, bg=bg)
        settings_frame.pack(fill=tk.X, padx=10, pady=(4, 0))

        no_value_slider = {**slider_style, "showvalue": False}

        # Silence timeout
        tk.Label(settings_frame, text="Silence:", **label_style).pack(side=tk.LEFT)
        self.silence_var = tk.DoubleVar(value=2.0)
        self.silence_slider = tk.Scale(
            settings_frame, from_=1, to=10, resolution=1,
            orient=tk.HORIZONTAL, variable=self.silence_var,
            length=60, command=self._on_silence_change,
            **no_value_slider
        )
        self.silence_slider.pack(side=tk.LEFT, padx=(2, 0))
        self.silence_label = tk.Label(
            settings_frame, text="2sec", font=(F, 8),
            bg=bg, fg="#cdd6f4", width=5, anchor="w"
        )
        self.silence_label.pack(side=tk.LEFT, padx=(2, 10))

        # Mic threshold
        tk.Label(settings_frame, text="Threshold:", **label_style).pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=300)
        self.threshold_slider = tk.Scale(
            settings_frame, from_=50, to=2000, resolution=50,
            orient=tk.HORIZONTAL, variable=self.threshold_var,
            length=60, command=self._on_threshold_change,
            **no_value_slider
        )
        self.threshold_slider.pack(side=tk.LEFT, padx=(2, 0))
        self.threshold_label = tk.Label(
            settings_frame, text="300", font=(F, 8),
            bg=bg, fg="#cdd6f4", width=5, anchor="w"
        )
        self.threshold_label.pack(side=tk.LEFT, padx=(2, 0))

        # --- Audio level visualizer ---
        meter_outer = tk.Frame(self.root, bg=bg)
        meter_outer.pack(fill=tk.X, padx=10, pady=(2, 0))

        meter_frame = tk.Frame(meter_outer, bg=bg)
        meter_frame.pack(fill=tk.X)

        tk.Label(meter_frame, text="Mic:", **label_style).pack(side=tk.LEFT)

        self.meter_canvas = tk.Canvas(
            meter_frame, height=14, bg="#11111b",
            highlightthickness=0, relief=tk.FLAT
        )
        self.meter_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))

        self.energy_label = tk.Label(
            meter_frame, text="---", font=(F, 8),
            bg=bg, fg="#6c7086", width=5, anchor="e"
        )
        self.energy_label.pack(side=tk.LEFT)

        # Scale labels under the meter
        scale_frame = tk.Frame(meter_outer, bg=bg)
        scale_frame.pack(fill=tk.X, padx=(32, 40))
        for val in ("0", "500", "1000", "1500", "2000"):
            tk.Label(
                scale_frame, text=val, font=(F, 7),
                bg=bg, fg="#45475a"
            ).pack(side=tk.LEFT, expand=True)

        # Start always-on mic monitoring
        self._start_mic_monitor()

        # --- Input box ---
        self.input_box = tk.Text(
            self.root, font=tkfont.Font(family=F, size=10), height=3,
            bg="#313244", fg="#cdd6f4", insertbackground="#f5e0dc",
            relief=tk.FLAT, padx=6, pady=6, wrap=tk.WORD,
            highlightthickness=2, highlightcolor="#89b4fa",
            highlightbackground="#45475a"
        )
        self.input_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.focus_set()

        self.root.bind("<Escape>", lambda e: self.root.destroy())

        # --- Settings panel (hidden by default) ---
        self.settings_panel = tk.Frame(self.root, bg="#181825", relief=tk.FLAT,
                                       highlightthickness=1, highlightbackground="#45475a")

        settings_bg = "#181825"
        settings_label = {"font": (F, 9), "bg": settings_bg, "fg": "#6c7086", "anchor": "w"}

        header_frame = tk.Frame(self.settings_panel, bg=settings_bg)
        header_frame.pack(fill=tk.X, padx=10, pady=(8, 6))
        tk.Label(header_frame, text="Settings", font=(F, 10, "bold"),
                 bg=settings_bg, fg="#cdd6f4").pack(side=tk.LEFT)
        tk.Label(header_frame, text="v1.8", font=(F, 8),
                 bg=settings_bg, fg="#45475a").pack(side=tk.RIGHT)

        # Terminal selection
        term_frame = tk.Frame(self.settings_panel, bg=settings_bg)
        term_frame.pack(fill=tk.X, padx=10, pady=3)

        tk.Label(term_frame, text="Terminal app:", **settings_label).pack(side=tk.LEFT)

        self.terminal_var = tk.StringVar(value=DEFAULT_TERMINAL)
        for name in AVAILABLE_TERMINALS:
            tk.Radiobutton(
                term_frame, text=name, variable=self.terminal_var, value=name,
                font=(F, 9), bg=settings_bg, fg="#cdd6f4",
                selectcolor="#313244", activebackground=settings_bg,
                activeforeground="#cdd6f4", highlightthickness=0,
                cursor="hand2"
            ).pack(side=tk.LEFT, padx=(12, 0))

        # Whisper model selection
        model_frame = tk.Frame(self.settings_panel, bg=settings_bg)
        model_frame.pack(fill=tk.X, padx=10, pady=3)

        tk.Label(model_frame, text="Whisper model:", **settings_label).pack(side=tk.LEFT)

        self.model_var = tk.StringVar(value="base")
        for name in ("tiny", "base", "small"):
            tk.Radiobutton(
                model_frame, text=name, variable=self.model_var, value=name,
                font=(F, 9), bg=settings_bg, fg="#cdd6f4",
                selectcolor="#313244", activebackground=settings_bg,
                activeforeground="#cdd6f4", highlightthickness=0,
                cursor="hand2", command=self._on_model_change
            ).pack(side=tk.LEFT, padx=(12, 0))

        # Font size selection
        font_frame = tk.Frame(self.settings_panel, bg=settings_bg)
        font_frame.pack(fill=tk.X, padx=10, pady=3)

        tk.Label(font_frame, text="Font size:", **settings_label).pack(side=tk.LEFT)

        self.fontsize_var = tk.StringVar(value="small")
        for name in ("small", "large"):
            tk.Radiobutton(
                font_frame, text=name, variable=self.fontsize_var, value=name,
                font=(F, 9), bg=settings_bg, fg="#cdd6f4",
                selectcolor="#313244", activebackground=settings_bg,
                activeforeground="#cdd6f4", highlightthickness=0,
                cursor="hand2", command=self._on_fontsize_change
            ).pack(side=tk.LEFT, padx=(12, 0))

        # Push-to-talk hotkey
        hotkey_frame = tk.Frame(self.settings_panel, bg=settings_bg)
        hotkey_frame.pack(fill=tk.X, padx=10, pady=(3, 8))

        tk.Label(hotkey_frame, text="Push-to-talk:", **settings_label).pack(side=tk.LEFT)

        self.hotkey_var = tk.StringVar(value=HOTKEY_OPTIONS[0])
        for name in HOTKEY_OPTIONS:
            tk.Radiobutton(
                hotkey_frame, text=name, variable=self.hotkey_var, value=name,
                font=(F, 9), bg=settings_bg, fg="#cdd6f4",
                selectcolor="#313244", activebackground=settings_bg,
                activeforeground="#cdd6f4", highlightthickness=0,
                cursor="hand2", command=self._on_hotkey_change
            ).pack(side=tk.LEFT, padx=(8, 0))

    def _toggle_settings_panel(self):
        if self._settings_visible:
            self.settings_panel.pack_forget()
            self._settings_visible = False
            self.gear_canvas.itemconfig("gear", fill="#6c7086")
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            self.root.geometry(f"{w}x{h - self._settings_height}")
        else:
            self.settings_panel.pack(fill=tk.X, padx=10, pady=(0, 4),
                                     before=self.input_box)
            self._settings_visible = True
            self.gear_canvas.itemconfig("gear", fill="#89b4fa")
            self.root.update_idletasks()
            self._settings_height = self.settings_panel.winfo_reqheight() + 4
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            self.root.geometry(f"{w}x{h + self._settings_height}")

    def _on_fontsize_change(self):
        F = DEFAULT_FONT
        size = self.fontsize_var.get()
        if size == "small":
            btn_font = (F, 9, "bold")
            input_font = (F, 10)
            label_font = (F, 8)
            status_font = (F, 8)
        else:
            btn_font = (F, 12, "bold")
            input_font = (F, 14)
            label_font = (F, 10)
            status_font = (F, 10)

        self.record_btn.config(font=btn_font)
        self.exec_btn.config(font=btn_font)
        self.clear_btn.config(font=btn_font)
        self.status_label.config(font=status_font)
        self.input_box.config(font=tkfont.Font(family=F, size=int(input_font[1])))
        self.silence_label.config(font=label_font)
        self.threshold_label.config(font=label_font)
        self.energy_label.config(font=label_font)

    def _on_model_change(self):
        new_model = self.model_var.get()
        self._model_loading = True
        self._set_status(f"Loading {new_model} model...", "#f9e2af")
        def load():
            try:
                self.model = whisper.load_model(new_model)
                self._model_loading = False
                self.root.after(0, lambda: self._set_status("Ready", "#a6e3a1"))
            except Exception as e:
                self._model_loading = False
                self.root.after(0, lambda: self._set_status(f"Model failed: {e}", "#f38ba8"))
        threading.Thread(target=load, daemon=True).start()

    def _on_enter(self, event):
        self._execute()
        return "break"

    def _execute(self):
        cmd = self.input_box.get("1.0", tk.END).strip()
        if not cmd:
            return
        self.input_box.delete("1.0", tk.END)
        success, err = send_to_terminal(cmd, self.terminal_var.get())
        if success:
            self._set_status("Sent!", "#a6e3a1")
        else:
            self._set_status("Error: " + err, "#f38ba8")

    def _clear_input(self):
        self.input_box.delete("1.0", tk.END)
        self._set_status("Cleared", "#cdd6f4")

    def _load_model(self):
        self.root.after(0, lambda: self._set_status("Loading Whisper model...", "#f9e2af"))
        try:
            self.model = whisper.load_model("base")
            self._model_loading = False
            self.root.after(0, lambda: self._set_status("Ready", "#a6e3a1"))
        except Exception as e:
            self._model_loading = False
            self.root.after(0, lambda: self._set_status(f"Model failed: {e}", "#f38ba8"))

    def _toggle_recording(self):
        if self._model_loading:
            self._set_status("Model still loading...", "#f9e2af")
            return

        if self.is_recording:
            self.is_recording = False
            self.audio_frames = []
            self.record_btn.config(text="● Record", bg="#f38ba8")
            self._set_status("Ready", "#a6e3a1")
            self._stop_recording()
        else:
            self.is_recording = True
            self._silence_counter = 0
            if not self.audio_frames:
                self._transcribed_so_far = ""
            self.record_btn.config(text="■ Stop", bg="#fab387")
            self._set_status("Listening...", "#f38ba8")
            self._start_recording()

    def _start_mic_monitor(self):
        pass

    def _start_recording(self):
        self.audio_stream = self.pyaudio_inst.open(
            format=pyaudio.paInt16, channels=1, rate=self._mic_rate,
            input=True, frames_per_buffer=1024,
            stream_callback=self._audio_callback
        )
        self.audio_stream.start_stream()
        self._schedule_live_transcribe()
        self._update_energy_meter()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if self.is_recording:
            audio_chunk = np.frombuffer(in_data, dtype=np.int16)
            self._current_energy = int(np.abs(audio_chunk).mean())

            self.audio_frames.append(in_data)
            threshold = self.threshold_var.get()

            if self._current_energy > threshold:
                self._silence_counter = 0
            else:
                self._silence_counter += 1
                callbacks_per_sec = self._mic_rate / 1024
                silence_limit = int(self.silence_var.get() * callbacks_per_sec)
                if self._silence_counter > silence_limit and len(self.audio_frames) > 16:
                    self.root.after(0, self._auto_stop)

        return (in_data, pyaudio.paContinue)

    def _draw_threshold_line(self):
        canvas_width = self.meter_canvas.winfo_width()
        canvas_height = self.meter_canvas.winfo_height()
        threshold = self.threshold_var.get()
        thresh_x = int(canvas_width * min(1.0, threshold / 2000))
        self.meter_canvas.delete("thresh")
        self.meter_canvas.create_line(
            thresh_x, 0, thresh_x, canvas_height,
            fill="#cdd6f4", width=2, dash=(3, 3), tags="thresh"
        )

    def _on_silence_change(self, *args):
        val = int(self.silence_var.get())
        self.silence_label.config(text=f"{val}sec")

    def _on_threshold_change(self, *args):
        self.threshold_label.config(text=str(self.threshold_var.get()))
        if not self.is_recording:
            self.meter_canvas.delete("all")
            self._draw_threshold_line()

    def _update_energy_meter(self):
        if not self.is_recording:
            self.meter_canvas.delete("all")
            self._draw_threshold_line()
            self.energy_label.config(text="---", fg="#6c7086")
            return
        energy = self._current_energy
        threshold = self.threshold_var.get()
        canvas_width = self.meter_canvas.winfo_width()
        canvas_height = self.meter_canvas.winfo_height()

        self.meter_canvas.delete("all")

        max_energy = 2000
        fill_ratio = min(1.0, energy / max_energy)
        bar_width = int(canvas_width * fill_ratio)

        if bar_width > 0:
            num_segments = max(1, bar_width // 4)
            segment_w = max(1, bar_width // num_segments)

            for i in range(num_segments):
                x = i * (segment_w + 1)
                ratio = x / max(1, canvas_width)
                if ratio < 0.5:
                    color = "#a6e3a1"
                elif ratio < 0.75:
                    color = "#f9e2af"
                else:
                    color = "#f38ba8"
                self.meter_canvas.create_rectangle(
                    x, 2, x + segment_w, canvas_height - 2,
                    fill=color, outline=""
                )

        # Draw threshold line
        thresh_x = int(canvas_width * min(1.0, threshold / max_energy))
        self.meter_canvas.create_line(
            thresh_x, 0, thresh_x, canvas_height,
            fill="#cdd6f4", width=2, dash=(3, 3)
        )

        self.energy_label.config(text=str(energy), fg="#cdd6f4")
        self.root.after(50, self._update_energy_meter)

    def _auto_stop(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.audio_frames = []
        self.record_btn.config(text="● Record", bg="#f38ba8")
        self._set_status("Stopped (silence)", "#a6e3a1")
        self._stop_recording()

    def _schedule_live_transcribe(self):
        if not self.is_recording:
            return
        threading.Thread(target=self._transcribe_live, daemon=True).start()

    def _transcribe_live(self):
        try:
            if not self.audio_frames:
                self.root.after(1000, self._schedule_live_transcribe)
                return

            audio_np = self._prepare_audio(self.audio_frames)
            result = self.model.transcribe(audio_np, language="en", fp16=False)
            text = result["text"].strip()

            if text:
                self.root.after(0, lambda t=text: self._update_live_text(t))

            self.root.after(1000, self._schedule_live_transcribe)
        except Exception:
            self.root.after(1000, self._schedule_live_transcribe)

    def _update_live_text(self, text):
        if not self.is_recording:
            return
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", text)
        self.input_box.see(tk.END)

        self.root.update_idletasks()
        box_width = self.input_box.winfo_width()
        if box_width > 1:
            font = tkfont.Font(font=self.input_box.cget("font"))
            chars_per_line = max(1, box_width // font.measure("m"))
            wrapped_lines = 0
            for line in text.split("\n"):
                wrapped_lines += max(1, -(-len(line) // chars_per_line))
            needed_height = wrapped_lines + 1
            min_win_height = 100 + needed_height * font.metrics("linespace") + 30
            current_height = self.root.winfo_height()
            if min_win_height > current_height:
                width = self.root.winfo_width()
                self.root.geometry(f"{width}x{min_win_height}")

        self._set_status("Listening...", "#f38ba8")

    def _prepare_audio(self, raw_frames):
        audio_np = np.frombuffer(b"".join(raw_frames), dtype=np.int16).astype(np.float32) / 32768.0
        if self._mic_rate != self._whisper_rate:
            gcd = np.gcd(self._whisper_rate, self._mic_rate)
            audio_np = signal.resample_poly(audio_np, self._whisper_rate // gcd, self._mic_rate // gcd)
        threshold = 0.01
        above = np.where(np.abs(audio_np) > threshold)[0]
        if len(above) == 0:
            return audio_np
        return audio_np[above[0]:]

    def _stop_recording(self):
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None

    def _set_status(self, text, color="#cdd6f4"):
        self.status_label.config(text=text, fg=color)

    # --- Global hotkey ---

    def _on_hotkey_change(self):
        if hasattr(self, '_hotkey_listener'):
            self._hotkey_listener.update_hotkey(self.hotkey_var.get())

    def _start_hotkey_listener(self):
        def on_press():
            self.root.after(int(self._hotkey_threshold * 1000),
                           self._hotkey_check_and_start)

        def on_release():
            if self.is_recording:
                self.root.after(0, self._hotkey_stop_and_send)

        self._hotkey_listener = HotkeyListener(
            on_press=on_press,
            on_release=on_release,
            hotkey_name=self.hotkey_var.get(),
        )
        self._hotkey_listener.start()

    def _hotkey_check_and_start(self):
        if self._hotkey_listener._active and not self.is_recording:
            self._hotkey_start_recording()

    def _hotkey_start_recording(self):
        if self._model_loading or self.is_recording:
            return
        self.is_recording = True
        self._silence_counter = 0
        self.audio_frames = []
        self._transcribed_so_far = ""
        self.record_btn.config(text="■ Stop", bg="#fab387")
        self._set_status("Listening (hotkey)...", "#f38ba8")
        self._start_recording()

    def _hotkey_stop_and_send(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.record_btn.config(text="● Record", bg="#f38ba8")
        self._stop_recording()

        if not self.audio_frames:
            self._set_status("Ready", "#a6e3a1")
            return

        self._set_status("Transcribing...", "#f9e2af")
        def transcribe_and_send():
            try:
                audio_np = self._prepare_audio(self.audio_frames)
                result = self.model.transcribe(audio_np, language="en", fp16=False)
                text = result["text"].strip()
                if text:
                    self.root.after(0, lambda t=text: self._hotkey_send(t))
                else:
                    self.root.after(0, lambda: self._set_status("Couldn't understand", "#f38ba8"))
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Error: {e}", "#f38ba8"))
        threading.Thread(target=transcribe_and_send, daemon=True).start()

    def _hotkey_send(self, text):
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", text)
        self._execute()

    def run(self):
        self._start_hotkey_listener()
        self.root.mainloop()


if __name__ == "__main__":
    app = VoiceControl()
    app.run()
