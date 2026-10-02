import os
import sys
import json
import base64
import ctypes
import hashlib
import threading
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox
from ctypes import wintypes

RULE_NAME = "Block Internet"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".internet_lock_config.json")
PS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", wintypes.LPVOID),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE)
    ]

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_elevated_hidden(executable: str, params: str) -> bool:
    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.hwnd = None
    sei.lpVerb = "runas"
    sei.lpFile = executable
    sei.lpParameters = params
    sei.lpDirectory = None
    sei.nShow = SW_HIDE

    if ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        if sei.hProcess:
            ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 0xFFFFFFFF)
            code = wintypes.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(sei.hProcess)
            return code.value == 0
        return True
    return False


def elevate_process():
    params = " ".join([f'"{arg}"' for arg in sys.argv])
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if ret > 32:
        sys.exit(0)


def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex(), pwd_hash.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        _, check_hash = hash_password(password, salt)
        return check_hash == hash_hex
    except Exception:
        return False


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def run_ps_fast(command: str) -> bool:
    if is_admin():
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass",
            "-Command", command
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, creationflags=PS_FLAGS)
            return res.returncode == 0
        except Exception:
            return False
    else:
        encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
        params = f"-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded}"
        return run_elevated_hidden("powershell.exe", params)


def check_firewall_locked() -> bool:
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-WindowStyle", "Hidden",
        "-Command",
        f"if (Get-NetFirewallRule -Name '{RULE_NAME}' -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, creationflags=PS_FLAGS)
        return res.returncode == 0
    except Exception:
        return False


def apply_firewall_lock() -> bool:
    cmd = (
        f'New-NetFirewallRule -Name "{RULE_NAME}" '
        f'-DisplayName "Block Internet access" '
        f'-Description "Used to block all internet access" '
        f'-Enabled True -Direction Outbound -Action Block '
        f'-InterfaceType Any -RemoteAddress Internet'
    )
    return run_ps_fast(cmd)


def remove_firewall_lock() -> bool:
    cmd = f'Remove-NetFirewallRule -Name "{RULE_NAME}" -ErrorAction SilentlyContinue'
    return run_ps_fast(cmd)


class UnlockModal(tk.Toplevel):
    def __init__(self, parent, salt: str, pwd_hash: str):
        super().__init__(parent)
        self.salt = salt
        self.pwd_hash = pwd_hash
        self.success = False

        self.title("Unlock")
        self.geometry("280x170")
        self.resizable(False, False)
        self.configure(bg="#1E1E2E")
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 280) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 170) // 2
        self.geometry(f"+{x}+{y}")

        tk.Label(
            self,
            text="🔓 Enter Password",
            font=("Segoe UI", 11, "bold"),
            fg="#CDD6F4",
            bg="#1E1E2E"
        ).pack(pady=(16, 4))

        self.pwd_var = tk.StringVar()
        self.entry = tk.Entry(
            self,
            textvariable=self.pwd_var,
            show="●",
            font=("Segoe UI", 11),
            bg="#313244",
            fg="#CDD6F4",
            insertbackground="#CDD6F4",
            relief="flat",
            bd=3
        )
        self.entry.pack(padx=24, fill="x", pady=6)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self.verify())

        self.err_lbl = tk.Label(self, text="", font=("Segoe UI", 8), fg="#F38BA8", bg="#1E1E2E")
        self.err_lbl.pack()

        btn_box = tk.Frame(self, bg="#1E1E2E")
        btn_box.pack(pady=(6, 12))

        tk.Button(
            btn_box,
            text="Unlock",
            font=("Segoe UI", 9, "bold"),
            bg="#A6E3A1",
            fg="#11111B",
            activebackground="#94E2D5",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=3,
            command=self.verify
        ).pack(side="left", padx=4)

        tk.Button(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#45475A",
            fg="#CDD6F4",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=3,
            command=self.destroy
        ).pack(side="left", padx=4)

    def verify(self):
        entered = self.pwd_var.get()
        if verify_password(entered, self.salt, self.pwd_hash):
            self.success = True
            self.destroy()
        else:
            self.err_lbl.configure(text="Incorrect password")
            self.pwd_var.set("")


class SplashScreen(tk.Toplevel):
    def __init__(self, parent, on_ready_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_ready_callback = on_ready_callback
        self.overrideredirect(True)
        self.geometry("420x430")
        self.configure(bg="#1E1E2E")
        self.attributes("-topmost", True)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"420x430+{(sw - 420) // 2}+{(sh - 430) // 2}")

        card = tk.Frame(self, bg="#181825", bd=1, relief="solid")
        card.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(card, text="🌐", font=("Segoe UI", 44), bg="#181825").pack(pady=(36, 4))
        tk.Label(card, text="INTERNET LOCK", font=("Segoe UI", 18, "bold"), fg="#CDD6F4", bg="#181825").pack()
        tk.Label(card, text="Secure Internet Controller", font=("Segoe UI", 10), fg="#89B4FA", bg="#181825").pack(pady=(4, 32))

        self.status_heading = tk.Label(
            card,
            text="Checking system security",
            font=("Segoe UI", 11),
            fg="#BAC2DE",
            bg="#181825"
        )
        self.status_heading.pack(pady=(0, 12))

        self.canvas = tk.Canvas(card, width=280, height=6, bg="#313244", highlightthickness=0)
        self.canvas.pack(pady=(0, 10))
        self.bar = self.canvas.create_rectangle(0, 0, 0, 6, fill="#89B4FA", width=0)

        self.substatus_lbl = tk.Label(
            card,
            text="Initializing...",
            font=("Segoe UI", 9),
            fg="#A6ADC8",
            bg="#181825"
        )
        self.substatus_lbl.pack(pady=(0, 20))

        tk.Label(
            card,
            text="Windows Firewall Protection",
            font=("Segoe UI", 9),
            fg="#585B70",
            bg="#181825"
        ).pack(side="bottom", pady=(0, 24))

        self.progress_ms = 0
        self.total_duration_ms = 1200
        self.initial_status = False
        self.check_finished = False

        self.bind("<Button-1>", lambda e: self._skip_to_main())
        card.bind("<Button-1>", lambda e: self._skip_to_main())

        threading.Thread(target=self._background_check, daemon=True).start()
        self.after(30, self._tick)

    def _skip_to_main(self):
        if self.check_finished:
            self.attributes("-topmost", False)
            self.destroy()
            self.on_ready_callback(self.initial_status)

    def _background_check(self):
        self.initial_status = check_firewall_locked()
        self.check_finished = True

    def _tick(self):
        self.progress_ms += 30
        pct = min(1.0, self.progress_ms / self.total_duration_ms)

        self.canvas.coords(self.bar, 0, 0, int(280 * pct), 6)

        if pct < 0.35:
            self.status_heading.configure(text="Checking system security")
            self.substatus_lbl.configure(text="Initializing environment...")
        elif pct < 0.70:
            self.status_heading.configure(text="Verifying Windows Defender Firewall")
            self.substatus_lbl.configure(text="Scanning firewall rules...")
        elif pct < 0.90:
            self.status_heading.configure(text="Preparing security controller")
            self.substatus_lbl.configure(text="Loading credentials...")
        else:
            self.status_heading.configure(text="System Protected")
            self.substatus_lbl.configure(text="Ready")

        if self.progress_ms >= self.total_duration_ms and self.check_finished:
            self.attributes("-topmost", False)
            self.destroy()
            self.on_ready_callback(self.initial_status)
        else:
            self.after(30, self._tick)


class InternetLockCompact(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Internet Lock")
        self.geometry("310x350")
        self.resizable(False, False)
        self.configure(bg="#1E1E2E")

        self.update_idletasks()
        sx = (self.winfo_screenwidth() - 310) // 2
        sy = (self.winfo_screenheight() - 350) // 2
        self.geometry(f"310x350+{sx}+{sy}")

        self.withdraw()

        self.is_locked = False
        self.show_pwd = False

        self.build_ui()
        SplashScreen(self, self.on_splash_complete)

    def on_splash_complete(self, initial_locked_state: bool):
        self.is_locked = initial_locked_state
        self.update_ui_state()
        self.deiconify()

    def build_ui(self):
        tk.Label(
            self,
            text="🌐 Internet Lock",
            font=("Segoe UI", 13, "bold"),
            fg="#CDD6F4",
            bg="#1E1E2E"
        ).pack(pady=(16, 8))

        self.icon_lbl = tk.Label(self, text="🔓", font=("Segoe UI", 36), bg="#1E1E2E")
        self.icon_lbl.pack()

        self.status_lbl = tk.Label(
            self,
            text="Internet Active",
            font=("Segoe UI", 12, "bold"),
            fg="#A6E3A1",
            bg="#1E1E2E"
        )
        self.status_lbl.pack(pady=(2, 14))

        self.action_btn = tk.Button(
            self,
            text="🔒 LOCK INTERNET",
            font=("Segoe UI", 10, "bold"),
            bg="#F38BA8",
            fg="#11111B",
            activebackground="#EBA0AC",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self.on_action_click
        )
        self.action_btn.pack(padx=32, fill="x")

        self.mid_frame = tk.Frame(self, bg="#1E1E2E", height=70)
        self.mid_frame.pack(fill="x", padx=28, pady=(16, 0))
        self.mid_frame.pack_propagate(False)

        self.pwd_container = tk.Frame(self.mid_frame, bg="#1E1E2E")
        pwd_row = tk.Frame(self.pwd_container, bg="#1E1E2E")
        pwd_row.pack(fill="x")

        tk.Label(
            pwd_row,
            text="🔐 Password:",
            font=("Segoe UI", 9),
            fg="#BAC2DE",
            bg="#1E1E2E"
        ).pack(side="left")

        self.pwd_var = tk.StringVar()
        self.pwd_entry = tk.Entry(
            pwd_row,
            textvariable=self.pwd_var,
            show="●",
            font=("Segoe UI", 10),
            bg="#313244",
            fg="#CDD6F4",
            insertbackground="#CDD6F4",
            relief="flat",
            bd=2
        )
        self.pwd_entry.pack(side="left", fill="x", expand=True, padx=(6, 4))
        self.pwd_entry.bind("<Return>", lambda e: self.on_action_click())
        self.pwd_var.trace_add("write", lambda *args: self.msg_lbl.configure(text=""))

        self.eye_btn = tk.Button(
            pwd_row,
            text="👁",
            font=("Segoe UI", 8),
            bg="#45475A",
            fg="#CDD6F4",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=5,
            command=self.toggle_eye
        )
        self.eye_btn.pack(side="left")

        self.locked_subtext = tk.Label(
            self.mid_frame,
            text="Password protected",
            font=("Segoe UI", 9),
            fg="#A6ADC8",
            bg="#1E1E2E"
        )

        self.msg_lbl = tk.Label(self, text="", font=("Segoe UI", 8), fg="#F38BA8", bg="#1E1E2E")
        self.msg_lbl.pack(pady=(4, 0))

        bottom_bar = tk.Frame(self, bg="#1E1E2E")
        bottom_bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))

        self.pwd_indicator = tk.Label(
            bottom_bar,
            text="Password ✓",
            font=("Segoe UI", 9),
            fg="#A6E3A1",
            bg="#1E1E2E"
        )
        self.pwd_indicator.pack(side="left")

        self.gear_btn = tk.Button(
            bottom_bar,
            text="⚙",
            font=("Segoe UI", 12),
            bg="#1E1E2E",
            fg="#A6ADC8",
            activebackground="#1E1E2E",
            activeforeground="#CDD6F4",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.open_settings_menu
        )
        self.gear_btn.pack(side="right")

    def toggle_eye(self):
        self.show_pwd = not self.show_pwd
        self.pwd_entry.configure(show="" if self.show_pwd else "●")
        self.eye_btn.configure(text="🙈" if self.show_pwd else "👁")

    def update_ui_state(self):
        self.msg_lbl.configure(text="")
        cfg = load_config()
        has_pwd = "salt" in cfg and "hash" in cfg

        if self.is_locked:
            self.icon_lbl.configure(text="🔒")
            self.status_lbl.configure(text="Internet Blocked", fg="#F38BA8")
            self.action_btn.configure(
                text="🔓 UNLOCK",
                bg="#A6E3A1",
                activebackground="#94E2D5",
                fg="#11111B"
            )
            self.pwd_container.pack_forget()
            self.locked_subtext.configure(
                text="Password protected" if has_pwd else "No password set",
                fg="#A6ADC8" if has_pwd else "#FAB387"
            )
            self.locked_subtext.pack(pady=14)
            self.pwd_indicator.pack_forget()
        else:
            self.icon_lbl.configure(text="🔓")
            self.status_lbl.configure(text="Internet Active", fg="#A6E3A1")
            self.action_btn.configure(
                text="🔒 LOCK INTERNET",
                bg="#F38BA8",
                activebackground="#EBA0AC",
                fg="#11111B"
            )
            self.locked_subtext.pack_forget()
            self.pwd_container.pack(fill="x", pady=12)
            self.pwd_indicator.pack(side="left")
            if has_pwd:
                self.pwd_indicator.configure(text="Password ✓", fg="#A6E3A1")
            else:
                self.pwd_indicator.configure(text="No password", fg="#FAB387")

    def on_action_click(self):
        if not self.is_locked:
            cfg = load_config()
            new_pwd = self.pwd_var.get().strip()

            if not new_pwd:
                self.msg_lbl.configure(text="⚠️ Password is required to lock!", fg="#F38BA8")
                self.pwd_entry.focus_set()
                self.pwd_entry.configure(bg="#452735")
                self.after(500, lambda: self.pwd_entry.configure(bg="#313244"))
                return

            salt, pwd_hash = hash_password(new_pwd)
            cfg["salt"] = salt
            cfg["hash"] = pwd_hash
            save_config(cfg)
            self.pwd_var.set("")

            success = apply_firewall_lock()
            if success:
                self.is_locked = True
                self.update_ui_state()
            else:
                self.msg_lbl.configure(text="Failed to lock. Admin privileges required.", fg="#F38BA8")
        else:
            cfg = load_config()
            has_pwd = "salt" in cfg and "hash" in cfg

            if has_pwd:
                modal = UnlockModal(self, cfg["salt"], cfg["hash"])
                self.wait_window(modal)
                if not modal.success:
                    return

            success = remove_firewall_lock()
            if success:
                self.is_locked = False
                self.update_ui_state()
            else:
                self.msg_lbl.configure(text="Failed to unlock. Admin privileges required.")

    def open_settings_menu(self):
        menu = tk.Menu(self, tearoff=0, bg="#313244", fg="#CDD6F4", activebackground="#45475A", activeforeground="#CDD6F4", relief="flat")
        menu.add_command(label="🔄 Refresh Status", command=self.manual_refresh)
        menu.add_command(label="🔑 Change Password", command=self.change_password_dialog)
        if not is_admin():
            menu.add_separator()
            menu.add_command(label="🛡️ Relaunch as Admin", command=elevate_process)
        menu.add_separator()
        menu.add_command(label="ℹ️ About", command=lambda: messagebox.showinfo("About", "Internet Lock\nVersion 1.0"))

        x = self.gear_btn.winfo_rootx()
        y = self.gear_btn.winfo_rooty() - 100
        menu.tk_popup(x, y)

    def manual_refresh(self):
        self.is_locked = check_firewall_locked()
        self.update_ui_state()

    def change_password_dialog(self):
        cfg = load_config()
        has_pwd = "salt" in cfg and "hash" in cfg

        if has_pwd:
            old = simpledialog.askstring("Verify", "Enter current password:", show="●", parent=self)
            if not old or not verify_password(old, cfg["salt"], cfg["hash"]):
                messagebox.showerror("Error", "Incorrect current password.")
                return

        new_p = simpledialog.askstring("New Password", "Enter new password (or blank to clear):", show="●", parent=self)
        if new_p is not None:
            if new_p.strip():
                salt, pwd_hash = hash_password(new_p.strip())
                cfg["salt"] = salt
                cfg["hash"] = pwd_hash
                save_config(cfg)
                messagebox.showinfo("Success", "Password updated successfully!")
            else:
                cfg.pop("salt", None)
                cfg.pop("hash", None)
                save_config(cfg)
                messagebox.showinfo("Success", "Password removed.")
            self.update_ui_state()


def run_cli():
    arg = sys.argv[1].lower()

    if arg in ("--status", "-s"):
        locked = check_firewall_locked()
        if locked:
            print("[Internet Lock] Status: 🔒 Internet Blocked (Firewall rule active)")
            sys.exit(1)
        else:
            print("[Internet Lock] Status: 🔓 Internet Active (Traffic allowed)")
            sys.exit(0)

    elif arg in ("--remove", "-r", "--emergency-remove"):
        print("[Internet Lock] Emergency Recovery: Removing firewall rule...")
        success = remove_firewall_lock()
        if success:
            print("[Internet Lock] SUCCESS: 'Block Internet' firewall rule removed. Internet restored.")
            sys.exit(0)
        else:
            print("[Internet Lock] ERROR: Failed to remove rule. Please run as Administrator.")
            sys.exit(1)

    elif arg in ("--help", "-h", "/?"):
        print("""Usage:
  python internet_lock.py
  python internet_lock.py --status
  python internet_lock.py --remove
""")
        sys.exit(0)

    else:
        print(f"Unknown option '{sys.argv[1]}'. Use --help for available options.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        app = InternetLockCompact()
        app.mainloop()
