"""
NOTZYH Low-Lag Recorder
Windows 10 screen recorder powered by FFmpeg.
The app selects hardware encoders when advertised by FFmpeg; unsupported hardware may fail to initialize.
No recorder can guarantee zero FPS impact; use 30 FPS / 720p for lower overhead.
"""

import os
import sys
import shutil
import subprocess
import threading
import time
import re
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "NOTZYH Low-Lag Recorder"

def app_folder():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def ffmpeg_path():
    local = app_folder() / "ffmpeg.exe"
    if local.exists():
        return str(local)
    found = shutil.which("ffmpeg")
    return found

def run_hidden(args, timeout=12):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

class Recorder:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.started_at = None
        self.timer_job = None
        self.encoder = "Auto"
        self.audio_devices = []
        self.build_ui()
        self.refresh_encoders()
        self.refresh_audio_devices()
        self.refresh_audio_devices()
        self.set_status("Ready to record", "#65d6a6")

    def build_ui(self):
        self.root.title(APP_TITLE)
        self.root.geometry("760x680")
        self.root.minsize(700, 630)
        self.root.configure(bg="#101318")
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background="#101318")
        s.configure("Panel.TFrame", background="#191f29")
        s.configure("TLabel", background="#101318", foreground="#e8edf5", font=("Segoe UI", 10))
        s.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground="#fff")
        s.configure("Sub.TLabel", foreground="#9da9ba", font=("Segoe UI", 9))
        s.configure("PanelTitle.TLabel", background="#191f29", foreground="#fff", font=("Segoe UI Semibold", 11))
        s.configure("PanelText.TLabel", background="#191f29", foreground="#aeb9c9", font=("Segoe UI", 9))
        s.configure("TButton", font=("Segoe UI Semibold", 10), padding=(13, 9),
                    background="#27364b", foreground="#fff")
        s.map("TButton", background=[("active", "#344966"), ("disabled", "#242a33")])
        s.configure("Accent.TButton", background="#3478f6", foreground="#fff")
        s.map("Accent.TButton", background=[("active", "#4b8aff")])
        s.configure("TCombobox", fieldbackground="#202938", background="#202938", foreground="#fff")
        s.configure("Horizontal.TProgressbar", troughcolor="#242c38", background="#3478f6")

        main = ttk.Frame(self.root, padding=22)
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="NOTZYH", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  LOW-LAG RECORDER", foreground="#65a0ff",
                  background="#101318", font=("Segoe UI Semibold", 11)).pack(side="left", pady=(10, 0))
        ttk.Label(main, text="Lightweight Windows screen recording • FFmpeg engine",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 16))

        panel = ttk.Frame(main, style="Panel.TFrame", padding=16)
        panel.pack(fill="x", pady=(0, 12))
        ttk.Label(panel, text="RECORDING SETTINGS", style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        ttk.Label(panel, text="Resolution", style="PanelText.TLabel").grid(row=1, column=0, sticky="w")
        self.res_var = tk.StringVar(value="1280x720")
        ttk.Combobox(panel, textvariable=self.res_var, values=["1280x720", "1920x1080", "Desktop (native)"],
                     state="readonly", width=20).grid(row=2, column=0, sticky="ew", padx=(0, 12), pady=(4, 10))

        ttk.Label(panel, text="Frame rate", style="PanelText.TLabel").grid(row=1, column=1, sticky="w")
        self.fps_var = tk.StringVar(value="30")
        ttk.Combobox(panel, textvariable=self.fps_var, values=["30", "60"], state="readonly",
                     width=12).grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(4, 10))

        ttk.Label(panel, text="Encoder", style="PanelText.TLabel").grid(row=1, column=2, sticky="w")
        self.enc_var = tk.StringVar(value="Auto (recommended)")
        ttk.Combobox(panel, textvariable=self.enc_var,
                     values=["Auto (recommended)", "CPU (x264)", "Intel Quick Sync", "NVIDIA NVENC", "AMD AMF"],
                     state="readonly", width=22).grid(row=2, column=2, sticky="ew", padx=(0, 12), pady=(4, 10))

        ttk.Label(panel, text="Quality", style="PanelText.TLabel").grid(row=1, column=3, sticky="w")
        self.quality_var = tk.StringVar(value="Balanced")
        ttk.Combobox(panel, textvariable=self.quality_var, values=["Small file", "Balanced", "High quality"],
                     state="readonly", width=15).grid(row=2, column=3, sticky="ew", pady=(4, 10))

        for i in range(4):
            panel.columnconfigure(i, weight=1)

        audio = ttk.Frame(main, style="Panel.TFrame", padding=12)
        audio.pack(fill="x", pady=(0, 10))
        ttk.Label(audio, text="AUDIO CAPTURE", style="PanelTitle.TLabel").pack(anchor="w")
        self.mic_var = tk.StringVar(value="Off")
        self.system_var = tk.StringVar(value="Off")
        ttk.Label(audio, text="Microphone", style="PanelText.TLabel").pack(anchor="w", pady=(7, 2))
        self.mic_box = ttk.Combobox(audio, textvariable=self.mic_var, values=["Off"], state="readonly")
        self.mic_box.pack(fill="x")
        ttk.Label(audio, text="System sound (Stereo Mix / loopback device)", style="PanelText.TLabel").pack(anchor="w", pady=(7, 2))
        self.system_box = ttk.Combobox(audio, textvariable=self.system_var, values=["Off"], state="readonly")
        self.system_box.pack(fill="x")
        ttk.Button(audio, text="Refresh audio devices", command=self.refresh_audio_devices).pack(anchor="w", pady=(8, 0))

        out = ttk.Frame(main, style="Panel.TFrame", padding=16)
        out.pack(fill="x", pady=(0, 12))
        ttk.Label(out, text="SAVE LOCATION", style="PanelTitle.TLabel").pack(anchor="w")
        row = ttk.Frame(out, style="Panel.TFrame")
        row.pack(fill="x", pady=(8, 0))
        self.path_var = tk.StringVar(value=str(Path.home() / "Videos"))
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(row, text="Browse", command=self.browse).pack(side="left", padx=(8, 0))

        audio = ttk.Frame(main, style="Panel.TFrame", padding=16)
        audio.pack(fill="x", pady=(0, 12))
        ttk.Label(audio, text="AUDIO CAPTURE", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(audio, text="Microphone (DirectShow input)", style="PanelText.TLabel").pack(anchor="w", pady=(8, 2))
        self.mic_var = tk.StringVar(value="Off")
        self.mic_combo = ttk.Combobox(audio, textvariable=self.mic_var, values=["Off"], state="readonly")
        self.mic_combo.pack(fill="x")
        ttk.Label(audio, text="System audio (Stereo Mix / loopback device)", style="PanelText.TLabel").pack(anchor="w", pady=(8, 2))
        self.sys_var = tk.StringVar(value="Off")
        self.sys_combo = ttk.Combobox(audio, textvariable=self.sys_var, values=["Off"], state="readonly")
        self.sys_combo.pack(fill="x")
        ttk.Button(audio, text="Refresh audio devices", command=self.refresh_audio_devices).pack(anchor="w", pady=(8, 0))

        status = ttk.Frame(main, style="Panel.TFrame", padding=16)
        status.pack(fill="x", pady=(0, 12))
        ttk.Label(status, text="RECORDER STATUS", style="PanelTitle.TLabel").pack(anchor="w")
        self.status_label = ttk.Label(status, text="Checking FFmpeg…", style="PanelText.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 3))
        self.timer_label = ttk.Label(status, text="00:00:00", background="#191f29",
                                     foreground="#ffffff", font=("Consolas", 22, "bold"))
        self.timer_label.pack(anchor="w")

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(2, 10))
        self.start_btn = ttk.Button(controls, text="●  Start recording", style="Accent.TButton",
                                    command=self.start_recording)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(controls, text="■  Stop recording", command=self.stop_recording, state="disabled")
        self.stop_btn.pack(side="left", padx=10)
        ttk.Button(controls, text="Open recordings", command=self.open_folder).pack(side="right")

        note = ("Low-overhead tips: start with 720p / 30 FPS / Auto. Hardware encoding can reduce CPU load "
                "when supported. Recording still uses system resources and may affect FPS.")
        ttk.Label(main, text=note, style="Sub.TLabel", wraplength=690, justify="left").pack(anchor="w")

    def set_status(self, msg, color=None):
        self.status_label.configure(text=msg, foreground=color or "#aeb9c9")

    def refresh_encoders(self):
        ff = ffmpeg_path()
        if not ff:
            self.set_status("FFmpeg missing. The packaged release should include ffmpeg.exe.", "#ffb86b")
            self.start_btn.configure(state="disabled")
            return
        try:
            res = run_hidden([ff, "-hide_banner", "-encoders"], timeout=20)
            txt = res.stdout + res.stderr
            self.encoders = txt
            self.set_status("FFmpeg ready • Choose settings and start recording", "#65d6a6")
        except Exception as e:
            self.encoders = ""
            self.set_status(f"FFmpeg check failed: {e}", "#ff8585")
            self.start_btn.configure(state="disabled")

    def refresh_audio_devices(self):
        ff = ffmpeg_path()
        if not ff:
            return
        try:
            result = run_hidden([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=15)
            devices = []
            in_audio = False
            for line in result.stderr.splitlines():
                if "DirectShow audio devices" in line:
                    in_audio = True
                    continue
                if "DirectShow video devices" in line:
                    in_audio = False
                if in_audio and '"' in line and "Alternative name" not in line:
                    match = re.search(r'"([^"]+)"', line)
                    if match and match.group(1) not in devices:
                        devices.append(match.group(1))
            self.mic_combo.configure(values=["Off"] + devices)
            # System sound is possible only if the driver exposes a loopback or Stereo Mix device.
            loopback = [x for x in devices if any(k in x.lower() for k in
                        ("stereo mix", "what u hear", "wave out mix", "loopback"))]
            self.sys_combo.configure(values=["Off"] + loopback)
            self.mic_var.set("Off")
            self.sys_var.set("Off")
            if not loopback:
                self.set_status("No Stereo Mix device detected; system audio unavailable with this capture method.", "#ffb86b")
        except Exception as exc:
            self.set_status(f"Audio device scan failed: {exc}", "#ffb86b")

    def refresh_audio_devices(self):
        ff = ffmpeg_path()
        if not ff:
            return
        try:
            # FFmpeg lists DirectShow audio device names on stderr.
            res = run_hidden([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"])
            devices = []
            in_audio = False
            for line in res.stderr.splitlines():
                if "DirectShow audio devices" in line:
                    in_audio = True
                    continue
                if "DirectShow video devices" in line:
                    in_audio = False
                if in_audio and '"' in line and "Alternative name" not in line:
                    match = re.search(r'"([^"]+)"', line)
                    if match and match.group(1) not in devices:
                        devices.append(match.group(1))
            self.audio_devices = devices
            self.mic_box.configure(values=["Off"] + devices)
            self.system_box.configure(values=["Off"] + devices)
            self.mic_var.set("Off")
            self.system_var.set("Off")
            self.set_status(f"Detected {len(devices)} DirectShow audio device(s). Stereo Mix may need enabling.")
        except Exception as e:
            self.set_status(f"Could not list audio devices: {e}", "#ff8585")

    def browse(self):
        p = filedialog.askdirectory(initialdir=self.path_var.get())
        if p:
            self.path_var.set(p)

    def open_folder(self):
        p = Path(self.path_var.get())
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))

    def choose_encoder(self):
        enc = self.enc_var.get()
        available = self.encoders
        choices = {
            "Intel Quick Sync": ("h264_qsv", "Intel Quick Sync"),
            "NVIDIA NVENC": ("h264_nvenc", "NVIDIA NVENC"),
            "AMD AMF": ("h264_amf", "AMD AMF"),
            "CPU (x264)": ("libx264", "CPU x264"),
        }
        if enc == "Auto (recommended)":
            for key, label in [("h264_qsv", "Intel Quick Sync"),
                               ("h264_nvenc", "NVIDIA NVENC"),
                               ("h264_amf", "AMD AMF")]:
                if key in available:
                    return key, label
            return "libx264", "CPU x264"
        key, label = choices[enc]
        if key not in available:
            raise RuntimeError(f"{label} encoder is not available on this PC/FFmpeg build. Choose Auto.")
        return key, label

    def start_recording(self):
        if self.proc and self.proc.poll() is None:
            return
        ff = ffmpeg_path()
        if not ff:
            messagebox.showerror(APP_TITLE, "ffmpeg.exe was not found beside the application.")
            return
        folder = Path(self.path_var.get())
        try:
            folder.mkdir(parents=True, exist_ok=True)
            encoder, label = self.choose_encoder()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return

        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        output = folder / f"NOTZYH_Recording_{stamp}.mp4"
        fps = int(self.fps_var.get())
        resolution = self.res_var.get()
        quality = self.quality_var.get()

        # gdigrab is broadly compatible on Windows 10. Keep capture simple and avoid
        # unnecessary filters; scaling is applied only when a fixed output size is chosen.
        cmd = [ff, "-hide_banner", "-y", "-f", "gdigrab", "-framerate", str(fps),
               "-draw_mouse", "1", "-i", "desktop"]
        mic = self.mic_var.get()
        system = self.sys_var.get()
        audio_inputs = []
        if mic != "Off":
            cmd += ["-thread_queue_size", "256", "-f", "dshow", "-i", f"audio={mic}"]
            audio_inputs.append("1:a")
        if system != "Off":
            cmd += ["-thread_queue_size", "256", "-f", "dshow", "-i", f"audio={system}"]
            audio_inputs.append(f"{len(audio_inputs) + 1}:a")
        if len(audio_inputs) == 2:
            cmd += ["-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest:dropout_transition=0[aout]",
                    "-map", "0:v:0", "-map", "[aout]"]
        elif len(audio_inputs) == 1:
            cmd += ["-map", "0:v:0", "-map", audio_inputs[0]]
        else:
            cmd += ["-map", "0:v:0"]
        if resolution != "Desktop (native)":
            cmd += ["-vf", f"scale={resolution.replace('x', ':')}:flags=fast_bilinear"]
        if encoder == "libx264":
            crf = {"Small file": "27", "Balanced": "23", "High quality": "19"}[quality]
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                    "-crf", crf, "-pix_fmt", "yuv420p"]
        elif encoder == "h264_qsv":
            q = {"Small file": "28", "Balanced": "24", "High quality": "20"}[quality]
            cmd += ["-c:v", "h264_qsv", "-global_quality", q, "-look_ahead", "0", "-pix_fmt", "nv12"]
        elif encoder == "h264_nvenc":
            preset = {"Small file": "p1", "Balanced": "p2", "High quality": "p4"}[quality]
            cmd += ["-c:v", "h264_nvenc", "-preset", preset, "-tune", "ll", "-rc", "vbr",
                    "-cq", {"Small file": "28", "Balanced": "23", "High quality": "19"}[quality],
                    "-pix_fmt", "yuv420p"]
        elif encoder == "h264_amf":
            q = {"Small file": "speed", "Balanced": "balanced", "High quality": "quality"}[quality]
            cmd += ["-c:v", "h264_amf", "-quality", q, "-pix_fmt", "nv12"]
        if audio_inputs:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
        # DirectShow microphone capture. System audio requires a real loopback
        # recording device such as Stereo Mix exposed by the Windows audio driver.
        # If both are selected, FFmpeg mixes them into one AAC track.
        mic = self.mic_var.get()
        system = self.system_var.get()
        selected = [d for d in [mic, system] if d != "Off"]
        if mic != "Off" and system != "Off" and mic == system:
            messagebox.showerror(APP_TITLE, "Choose different devices for microphone and system audio.")
            return
        if system != "Off" and not any(k in system.lower() for k in ("stereo mix", "loopback", "what u hear", "wave out")):
            if not messagebox.askyesno(APP_TITLE, "The selected system audio device is not clearly a loopback device. It may record a microphone instead. Continue?"):
                return
        for device in selected:
            cmd += ["-f", "dshow", "-i", f"audio={device}"]
        if len(selected) == 2:
            cmd += ["-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest:dropout_transition=0[aout]",
                    "-map", "0:v:0", "-map", "[aout]"]
        elif len(selected) == 1:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        if selected:
            cmd += ["-c:a", "aac", "-b:a", "96k", "-ar", "44100"]
        cmd += ["-movflags", "+faststart", str(output)]

        try:
            # Redirect FFmpeg output to a log file so no console window is needed.
            self.log_handle = open(folder / "notzyh_recorder_last.log", "w", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=self.log_handle,
                                         stderr=self.log_handle,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            time.sleep(0.8)
            if self.proc.poll() is not None:
                self.log_handle.close()
                messagebox.showerror(APP_TITLE, "FFmpeg could not start recording. Check notzyh_recorder_last.log in the recording folder.")
                return
            self.started_at = time.time()
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.set_status(f"RECORDING • {label} • {output.name}", "#ff6464")
            self.update_timer()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not start recording:\n{e}")

    def update_timer(self):
        if not self.proc or self.proc.poll() is not None:
            return
        elapsed = int(time.time() - self.started_at)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.timer_job = self.root.after(500, self.update_timer)

    def stop_recording(self):
        if not self.proc or self.proc.poll() is not None:
            self.finish_recording()
            return
        self.set_status("Stopping and finalizing MP4…", "#ffb86b")
        self.stop_btn.configure(state="disabled")
        def worker():
            try:
                self.proc.stdin.write(b"q\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=20)
            except Exception:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                except Exception:
                    pass
            self.root.after(0, self.finish_recording)
        threading.Thread(target=worker, daemon=True).start()

    def finish_recording(self):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        if hasattr(self, "log_handle") and not self.log_handle.closed:
            self.log_handle.close()
        self.proc = None
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.timer_label.configure(text="00:00:00")
        self.set_status("Recording stopped • MP4 saved to selected folder", "#65d6a6")

    def close(self):
        if self.proc and self.proc.poll() is None:
            if messagebox.askyesno(APP_TITLE, "A recording is active. Stop and close?"):
                self.stop_recording()
                self.root.after(1200, self.root.destroy)
                return
            return
        self.root.destroy()

def main():
    if os.name != "nt":
        print("This application is designed for Windows 10.")
        return
    root = tk.Tk()
    app = Recorder(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()

if __name__ == "__main__":
    main()
