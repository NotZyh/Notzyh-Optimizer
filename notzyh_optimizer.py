"""
NOTZYH Optimizer
Windows 10 gaming-focused optimizer.
Uses reversible, narrowly-scoped settings; it does not bulk-disable Windows services.
Run with Python 3.10+ on Windows 10. Standard-library GUI (tkinter).
"""

import ctypes
import json
import os
import platform
import subprocess
import sys
import threading
import time
import winreg
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "NOTZYH Optimizer"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NOTZYHOptimizer"
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

REGISTRY_TWEAKS = [
    {
        "label": "Disable Xbox Game DVR background capture",
        "hive": winreg.HKEY_CURRENT_USER,
        "path": r"System\GameConfigStore",
        "name": "GameDVR_Enabled",
        "value": 0,
        "type": winreg.REG_DWORD,
        "description": "Stops Windows Game DVR background recording. Xbox Game Bar itself remains available."
    },
    {
        "label": "Disable automatic game capture",
        "hive": winreg.HKEY_CURRENT_USER,
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
        "name": "AppCaptureEnabled",
        "value": 0,
        "type": winreg.REG_DWORD,
        "description": "Turns off automatic app/game capture. You can still use third-party recording tools."
    },
]

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def run_command(args, timeout=20):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

def get_active_power_plan():
    try:
        result = run_command(["powercfg", "/getactivescheme"])
        if result.returncode == 0:
            import re
            match = re.search(r"([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})", result.stdout)
            return match.group(1) if match else None
    except Exception:
        pass
    return None

def create_restore_point():
    # Best effort: System Protection must already be enabled on the system drive.
    script = ("Checkpoint-Computer -Description 'NOTZYH Optimizer before gaming tweaks' "
              "-RestorePointType 'MODIFY_SETTINGS'")
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

def read_registry_value(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
            value, value_type = winreg.QueryValueEx(key, name)
            return {"exists": True, "value": value, "type": value_type}
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        return {"exists": False}

def write_registry_value(hive, path, name, value, value_type):
    with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, value_type, value)

def delete_registry_value(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass

class OptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("900x650")
        self.root.minsize(820, 590)
        self.root.configure(bg="#101318")
        self.backup = None
        self.busy = False

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#101318")
        self.style.configure("Panel.TFrame", background="#191f29")
        self.style.configure("TLabel", background="#101318", foreground="#e8edf5", font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground="#ffffff")
        self.style.configure("Sub.TLabel", foreground="#9da9ba", font=("Segoe UI", 10))
        self.style.configure("PanelTitle.TLabel", background="#191f29", foreground="#ffffff",
                             font=("Segoe UI Semibold", 12))
        self.style.configure("PanelText.TLabel", background="#191f29", foreground="#aeb9c9",
                             font=("Segoe UI", 9))
        self.style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(14, 9),
                             background="#27364b", foreground="#ffffff")
        self.style.map("TButton", background=[("active", "#344966"), ("disabled", "#242a33")])
        self.style.configure("Accent.TButton", background="#3478f6", foreground="#ffffff")
        self.style.map("Accent.TButton", background=[("active", "#4b8aff")])
        self.style.configure("TCheckbutton", background="#191f29", foreground="#e8edf5")
        self.style.configure("Horizontal.TProgressbar", troughcolor="#242c38", background="#3478f6")

        self.build_ui()
        self.log("Ready. No changes have been made.")
        self.refresh_status()

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="NOTZYH", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  OPTIMIZER", foreground="#65a0ff",
                  background="#101318", font=("Segoe UI Semibold", 12)).pack(side="left", pady=(10, 0))
        self.admin_label = ttk.Label(header, text="Checking permissions…", style="Sub.TLabel")
        self.admin_label.pack(side="right", pady=(12, 0))

        ttk.Label(outer, text="Windows 10 • Gaming-focused tuning • Reversible changes",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 18))

        cards = ttk.Frame(outer)
        cards.pack(fill="x", pady=(0, 16))
        self.make_card(cards, "PERFORMANCE PROFILE",
                       "Applies a High Performance power plan where available.",
                       "power").pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.make_card(cards, "GAME CAPTURE",
                       "Turns off Windows background DVR capture to reduce unwanted recording activity.",
                       "capture").pack(side="left", fill="both", expand=True, padx=8)
        self.make_card(cards, "RESTORE CENTER",
                       "Creates a backup of the settings changed by this app and can restore them.",
                       "restore").pack(side="left", fill="both", expand=True, padx=(8, 0))

        options = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        options.pack(fill="x", pady=(0, 14))
        ttk.Label(options, text="GAMING OPTIMIZATION", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(options, text="Choose the reversible tweaks you want to apply.",
                  style="PanelText.TLabel").pack(anchor="w", pady=(3, 12))
        self.power_var = tk.BooleanVar(value=True)
        self.dvr_var = tk.BooleanVar(value=True)
        self.restore_point_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Use Windows High Performance power plan (if available)",
                        variable=self.power_var).pack(anchor="w", pady=3)
        ttk.Checkbutton(options, text="Disable Windows Game DVR background capture",
                        variable=self.dvr_var).pack(anchor="w", pady=3)
        ttk.Checkbutton(options, text="Attempt to create a Windows restore point first (recommended)",
                        variable=self.restore_point_var).pack(anchor="w", pady=3)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 14))
        self.apply_btn = ttk.Button(buttons, text="Apply gaming optimizations",
                                    style="Accent.TButton", command=self.apply)
        self.apply_btn.pack(side="left")
        self.restore_btn = ttk.Button(buttons, text="Restore last backup", command=self.restore)
        self.restore_btn.pack(side="left", padx=10)
        ttk.Button(buttons, text="Refresh status", command=self.refresh_status).pack(side="right")

        status_panel = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        status_panel.pack(fill="x", pady=(0, 14))
        ttk.Label(status_panel, text="SYSTEM STATUS", style="PanelTitle.TLabel").pack(anchor="w")
        self.status_text = ttk.Label(status_panel, text="Loading…", style="PanelText.TLabel")
        self.status_text.pack(anchor="w", pady=(6, 0))

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        log_panel.pack(fill="both", expand=True)
        ttk.Label(log_panel, text="ACTIVITY LOG", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.log_box = tk.Text(log_panel, height=8, bg="#0d1117", fg="#cbd5e1",
                               insertbackground="white", relief="flat", wrap="word",
                               font=("Consolas", 9), padx=10, pady=8)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

        footer = ttk.Label(outer, text="Safety: this app does not bulk-disable services, disable Windows Defender, or modify Windows Update.",
                           style="Sub.TLabel")
        footer.pack(anchor="w", pady=(10, 0))

    def make_card(self, parent, title, description, kind):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        ttk.Label(frame, text=title, style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text=description, style="PanelText.TLabel",
                  wraplength=205, justify="left").pack(anchor="w", pady=(7, 0))
        return frame

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def refresh_status(self):
        if platform.system() != "Windows":
            self.status_text.configure(text="Unsupported operating system.")
            return
        version = platform.version()
        build = platform.release()
        plan = get_active_power_plan() or "Unable to read"
        self.admin_label.configure(text="Administrator" if is_admin() else "Not running as administrator")
        self.status_text.configure(
            text=f"Windows {build} • Build {version} • Active power plan: {plan}\n"
                 f"Administrator permissions: {'Yes' if is_admin() else 'No'}"
        )

    def set_busy(self, value):
        self.busy = value
        self.apply_btn.configure(state="disabled" if value else "normal")
        self.restore_btn.configure(state="disabled" if value else "normal")

    def apply(self):
        if self.busy:
            return
        if platform.system() != "Windows":
            messagebox.showerror(APP_NAME, "This application only supports Windows.")
            return
        if not is_admin():
            messagebox.showwarning(APP_NAME, "Please close the app and run it as Administrator.")
            return
        if not self.power_var.get() and not self.dvr_var.get():
            messagebox.showinfo(APP_NAME, "Select at least one optimization.")
            return
        if not messagebox.askyesno(APP_NAME,
                "Apply the selected gaming optimizations?\n\nA backup will be saved first."):
            return
        self.set_busy(True)
        threading.Thread(target=self._apply_worker, daemon=True).start()

    def _apply_worker(self):
        try:
            snapshot = {
                "created": datetime.now().isoformat(timespec="seconds"),
                "active_power_plan": get_active_power_plan(),
                "registry": [],
                "applied": []
            }

            if self.restore_point_var.get():
                self.root.after(0, lambda: self.log("Attempting to create a Windows restore point…"))
                try:
                    rp = create_restore_point()
                    if rp.returncode == 0:
                        self.root.after(0, lambda: self.log("Windows restore point created."))
                    else:
                        self.root.after(0, lambda: self.log("Restore point unavailable; continuing with app backup."))
                except Exception:
                    self.root.after(0, lambda: self.log("Could not create restore point; continuing with app backup."))

            if self.dvr_var.get():
                for tweak in REGISTRY_TWEAKS:
                    old = read_registry_value(tweak["hive"], tweak["path"], tweak["name"])
                    snapshot["registry"].append({
                        "path": tweak["path"], "name": tweak["name"], "old": old
                    })
                    write_registry_value(tweak["hive"], tweak["path"], tweak["name"],
                                         tweak["value"], tweak["type"])
                    snapshot["applied"].append(tweak["label"])
                    self.root.after(0, lambda label=tweak["label"]: self.log(f"Applied: {label}"))

            if self.power_var.get():
                result = run_command(["powercfg", "/setactive", HIGH_PERFORMANCE_GUID])
                if result.returncode == 0:
                    snapshot["applied"].append("Set High Performance power plan")
                    self.root.after(0, lambda: self.log("Applied: High Performance power plan."))
                else:
                    self.root.after(0, lambda: self.log("High Performance plan unavailable; skipped."))

            filename = BACKUP_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filename.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            (APP_DIR / "last_backup.txt").write_text(str(filename), encoding="utf-8")
            self.root.after(0, lambda: self.log(f"Backup saved: {filename}"))
            self.root.after(0, lambda: messagebox.showinfo(APP_NAME,
                "Selected optimizations applied.\n\nYour backup is saved in:\n" + str(filename)))
        except Exception as exc:
            self.root.after(0, lambda err=str(exc): messagebox.showerror(APP_NAME, f"Could not complete optimization:\n{err}"))
            self.root.after(0, lambda err=str(exc): self.log(f"ERROR: {err}"))
        finally:
            self.root.after(0, lambda: self.set_busy(False))
            self.root.after(0, self.refresh_status)

    def restore(self):
        if self.busy:
            return
        if not is_admin():
            messagebox.showwarning(APP_NAME, "Please close the app and run it as Administrator.")
            return
        marker = APP_DIR / "last_backup.txt"
        if not marker.exists():
            messagebox.showinfo(APP_NAME, "No backup was found yet.")
            return
        try:
            path = Path(marker.read_text(encoding="utf-8").strip())
            if not path.exists():
                raise FileNotFoundError(path)
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not read backup:\n{exc}")
            return
        if not messagebox.askyesno(APP_NAME, "Restore the settings from the most recent backup?"):
            return
        self.set_busy(True)
        threading.Thread(target=self._restore_worker, args=(snapshot,), daemon=True).start()

    def _restore_worker(self, snapshot):
        try:
            for item in snapshot.get("registry", []):
                old = item.get("old", {})
                if old.get("exists"):
                    write_registry_value(winreg.HKEY_CURRENT_USER, item["path"], item["name"],
                                         old["value"], old["type"])
                else:
                    delete_registry_value(winreg.HKEY_CURRENT_USER, item["path"], item["name"])
                self.root.after(0, lambda p=item["path"], n=item["name"]: self.log(f"Restored registry value: {p}\\{n}"))

            old_plan = snapshot.get("active_power_plan")
            if old_plan:
                result = run_command(["powercfg", "/setactive", old_plan])
                if result.returncode == 0:
                    self.root.after(0, lambda: self.log("Restored previous power plan."))
                else:
                    self.root.after(0, lambda: self.log("Could not restore previous power plan."))

            self.root.after(0, lambda: messagebox.showinfo(APP_NAME,
                "Restore completed. Some changes may require a restart or sign-out to fully take effect."))
        except Exception as exc:
            self.root.after(0, lambda err=str(exc): messagebox.showerror(APP_NAME, f"Restore failed:\n{err}"))
            self.root.after(0, lambda err=str(exc): self.log(f"RESTORE ERROR: {err}"))
        finally:
            self.root.after(0, lambda: self.set_busy(False))
            self.root.after(0, self.refresh_status)

def main():
    if platform.system() != "Windows":
        print("NOTZYH Optimizer only runs on Windows 10.")
        return
    if platform.release() != "10":
        print("This build is intended for Windows 10.")
    root = tk.Tk()
    app = OptimizerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
