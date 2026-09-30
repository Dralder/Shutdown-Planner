import sys
import os
import json
import math
import queue
import ctypes
import threading
import subprocess
import tkinter
from datetime import datetime

import customtkinter as ctk

APP_NAME = "Shutdown Planner"
CNW = 0x08000000
WIDTH = 460

BG = "#202020"
CARD = "#2A2A2D"
TXT = "#E0E0E0"
MUT = "#8A8A8A"
PUR = "#7B2CBF"
PURH = "#9D4EDD"
LAV = "#A78BFA"
DIS = "#575757"
GREEN = "#7CFC5A"
AMBER = "#D4A94A"
RED = "#B83232"
REDH = "#D04040"

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "shut.ico")
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Dralder")
CFG_PATH = os.path.join(CFG_DIR, "shutdown_planner.js")
CFG_LOCK = threading.Lock()

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        params = " ".join(f'"{a}"' for a in [os.path.abspath(sys.argv[0])] + sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def dark_titlebar(win):
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        for attr, val in ((20, 1), (34, 0x202020), (35, 0x202020), (36, 0xE0E0E0)):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd), attr, ctypes.byref(ctypes.c_int(val)), 4
            )
    except Exception:
        pass


def set_icon(win):
    try:
        win.iconbitmap(ICON_PATH)
    except Exception:
        pass


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=CNW)


def load_config():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_config(data):
    with CFG_LOCK:
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            tmp = CFG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, CFG_PATH)
        except Exception:
            pass


class Dialog(ctk.CTkToplevel):
    def __init__(self, parent, text, question=False):
        super().__init__(parent)
        self.result = False
        self.title(APP_NAME)
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.transient(parent)
        font = ctk.CTkFont(family="Consolas", size=13)
        bold = ctk.CTkFont(family="Consolas", size=13, weight="bold")
        ctk.CTkLabel(self, text=text, font=font, text_color=TXT, wraplength=300, justify="center").pack(
            padx=20, pady=(20, 12)
        )
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=(0, 16), fill="x")
        if question:
            row.grid_columnconfigure((0, 1), weight=1, uniform="b")
            self.btn(row, "Yes", bold, self.yes).grid(row=0, column=0, padx=(0, 4), sticky="ew")
            self.btn(row, "No", bold, self.no).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        else:
            self.btn(row, "OK", bold, self.no).pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.no)
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        tkinter.Wm.wm_geometry(self, f"+{max(x, 0)}+{max(y, 0)}")
        self.after(250, lambda: (set_icon(self), dark_titlebar(self)))
        self.after(60, self.take_focus)

    def btn(self, parent, text, font, cmd):
        return ctk.CTkButton(
            parent, text=text, font=font, command=cmd, height=34, corner_radius=5,
            fg_color=PUR, hover_color=PURH, text_color="#FFFFFF"
        )

    def take_focus(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass

    def yes(self):
        self.result = True
        self.destroy()

    def no(self):
        self.result = False
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title(APP_NAME)
        self.configure(fg_color=BG)
        self.resizable(False, False)

        self.font = ctk.CTkFont(family="Consolas", size=13)
        self.font_b = ctk.CTkFont(family="Consolas", size=13, weight="bold")
        self.font_t = ctk.CTkFont(family="Consolas", size=26, weight="bold")

        self.q = queue.Queue()
        self.running = False
        self.loading = False
        self.target = None
        self.mode = None
        self.adapter = None
        self.tick_job = None
        self.save_job = None
        self.names = []
        self.cfg = load_config()
        self.sel_adapter = self.cfg.get("adapter")

        self.v_pc = ctk.IntVar(value=0 if self.cfg.get("action") == "net" else 1)
        self.v_net = ctk.IntVar(value=1 if self.cfg.get("action") == "net" else 0)
        self.v_cmd = ctk.IntVar(value=0 if self.cfg.get("method") == "app" else 1)
        self.v_app = ctk.IntVar(value=1 if self.cfg.get("method") == "app" else 0)

        pad = 14
        self.label(self, "SELECT METHOD").pack(padx=pad, pady=(pad, 6))
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(padx=pad)
        self.cb_pc = self.check(top, "Turn off the PC", self.v_pc, lambda: self.pick_action("pc"))
        self.cb_net = self.check(top, "Turn off the Internet", self.v_net, lambda: self.pick_action("net"))
        self.cb_pc.pack(side="left", padx=(0, 22))
        self.cb_net.pack(side="left")

        self.dyn = ctk.CTkFrame(self, fg_color="transparent")
        self.dyn.pack(padx=pad, pady=(12, 0), fill="x")

        self.mode_box = ctk.CTkFrame(self.dyn, fg_color="transparent")
        self.label(self.mode_box, "SELECT OPTION").pack(pady=(0, 6))
        mrow = ctk.CTkFrame(self.mode_box, fg_color="transparent")
        mrow.pack()
        self.cb_cmd = self.check(mrow, "CMD schedule shutdown", self.v_cmd, lambda: self.pick_method("cmd"))
        self.cb_app = self.check(mrow, "App shutdown", self.v_app, lambda: self.pick_method("app"))
        self.cb_cmd.pack(side="left", padx=(0, 22))
        self.cb_app.pack(side="left")

        self.net_box = ctk.CTkFrame(self.dyn, fg_color="transparent")
        nhead = ctk.CTkFrame(self.net_box, fg_color="transparent")
        nhead.pack(fill="x", pady=(0, 6))
        self.label(nhead, "SELECT OPTION").pack(side="left", expand=True, padx=(70, 0))
        self.btn_refresh = ctk.CTkButton(
            nhead, text="Refresh", width=70, height=24, corner_radius=5, font=self.font_b,
            fg_color=PUR, hover_color=PURH, text_color="#FFFFFF", text_color_disabled=MUT,
            command=self.load_adapters
        )
        self.btn_refresh.pack(side="right")
        lf = ctk.CTkFrame(self.net_box, fg_color=BG, border_width=1, border_color=DIS, corner_radius=5)
        lf.pack(fill="x")
        self.lb = tkinter.Listbox(
            lf, height=2, bg=BG, fg=TXT, selectbackground=PUR, selectforeground="#FFFFFF",
            highlightthickness=0, borderwidth=0, activestyle="none", exportselection=False,
            font=("Consolas", 10), disabledforeground=MUT
        )
        sb = ctk.CTkScrollbar(lf, command=self.lb.yview, fg_color=BG, button_color=DIS,
                              button_hover_color=PURH, width=12)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.lb.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        self.lb.bind("<<ListboxSelect>>", self.on_select)

        now = datetime.now()
        d = {"day": now.day, "month": now.month, "year": now.year,
             "hour": now.hour % 12 or 12, "minute": now.minute, "ampm": "PM" if now.hour >= 12 else "AM"}
        try:
            c = self.cfg
            saved = datetime(int(c["year"]), int(c["month"]), int(c["day"]),
                             (int(c["hour"]) % 12) + (12 if c["ampm"] == "PM" else 0), int(c["minute"]))
            if saved > now:
                d = {"day": saved.day, "month": saved.month, "year": saved.year,
                     "hour": int(c["hour"]), "minute": saved.minute, "ampm": c["ampm"]}
        except Exception:
            pass

        years = [str(now.year + i) for i in range(3)]

        self.label(self, "TIME").pack(padx=pad, pady=(12, 6))
        trow = ctk.CTkFrame(self, fg_color="transparent")
        trow.pack(padx=pad)
        self.c_hour = self.combo(trow, [str(i) for i in range(1, 13)], 70, (1, 12, False, None))
        self.c_min = self.combo(trow, [f"{i:02d}" for i in range(60)], 70, (0, 59, True, None))
        self.c_ampm = self.combo(trow, ["AM", "PM"], 76)
        self.c_hour.pack(side="left")
        ctk.CTkLabel(trow, text=":", font=self.font_b, text_color=TXT, width=14).pack(side="left")
        self.c_min.pack(side="left", padx=(0, 8))
        self.c_ampm.pack(side="left")

        self.label(self, "DATE").pack(padx=pad, pady=(12, 6))
        drow = ctk.CTkFrame(self, fg_color="transparent")
        drow.pack(padx=pad)
        self.c_day = self.combo(drow, [str(i) for i in range(1, 32)], 70, (1, 31, False, None))
        self.c_month = self.combo(drow, MONTHS, 80)
        self.c_year = self.combo(drow, years, 90, (0, 0, False, years))
        self.num_combos = [self.c_hour, self.c_min, self.c_day, self.c_year]
        self.c_day.pack(side="left", padx=(0, 8))
        self.c_month.pack(side="left", padx=(0, 8))
        self.c_year.pack(side="left")

        self.c_day.set(str(d["day"]))
        self.c_month.set(MONTHS[d["month"] - 1])
        self.c_year.set(str(d["year"]) if str(d["year"]) in years else str(now.year))
        self.c_hour.set(str(d["hour"]))
        self.c_min.set(f"{d['minute']:02d}")
        self.c_ampm.set(d["ampm"])
        for c in self.num_combos:
            c.last = c.get()

        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        card.pack(padx=pad, pady=(10, 0), fill="x")
        self.lbl_status = ctk.CTkLabel(card, text="READY", font=self.font_b, text_color=GREEN, height=18)
        self.lbl_status.pack(pady=(8, 0))
        self.lbl_timer = ctk.CTkLabel(card, text="00:00:00", font=self.font_t, text_color=AMBER, height=32)
        self.lbl_timer.pack()
        self.lbl_info = ctk.CTkLabel(card, text="No task scheduled", font=self.font, text_color=TXT,
                                     wraplength=400, justify="center", height=18)
        self.lbl_info.pack(pady=(0, 8))

        self.btn_run = ctk.CTkButton(
            self, text="Run", height=40, corner_radius=5, font=self.font_b,
            fg_color=PUR, hover_color=PURH, text_color="#FFFFFF", command=self.toggle
        )
        self.btn_run.pack(padx=pad, pady=(10, 0), fill="x")

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(pady=(6, 8))
        ctk.CTkLabel(foot, text="Made by ", font=ctk.CTkFont(family="Consolas", size=11),
                     text_color=MUT, height=14).pack(side="left")
        ctk.CTkLabel(foot, text="Dralder", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                     text_color=PUR, height=14).pack(side="left")
        ctk.CTkLabel(foot, text=" v1.0.0", font=ctk.CTkFont(family="Consolas", size=11),
                     text_color=MUT, height=14).pack(side="left")

        self.update_view()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll)
        self.after(250, lambda: (set_icon(self), dark_titlebar(self)))

    def label(self, parent, text):
        return ctk.CTkLabel(parent, text=text, text_color=LAV, height=16,
                            font=ctk.CTkFont(family="Consolas", size=12))

    def check(self, parent, text, var, cmd):
        return ctk.CTkCheckBox(
            parent, text=text, variable=var, command=cmd, onvalue=1, offvalue=0,
            checkbox_width=20, checkbox_height=20, corner_radius=5, border_width=2,
            border_color=DIS, fg_color=PUR, hover_color=PURH, checkmark_color="#FFFFFF",
            text_color=TXT, text_color_disabled=MUT, font=self.font
        )

    def combo(self, parent, values, width, spec=None):
        c = ctk.CTkComboBox(
            parent, values=values, width=width, height=32, corner_radius=5, border_width=1,
            border_color=DIS, fg_color=BG, button_color=PUR, button_hover_color=PURH,
            dropdown_fg_color=CARD, dropdown_hover_color=PUR, dropdown_text_color=TXT,
            text_color=TXT, text_color_disabled=MUT, font=self.font, dropdown_font=self.font,
            state="normal" if spec else "readonly"
        )
        c.spec = spec
        c.last = ""
        c.configure(command=lambda v, c=c: self.picked(c))
        if spec:
            lo, hi, pad2, allowed = spec

            def valid(p, hi=hi, allowed=allowed):
                if p == "":
                    return True
                if not (p.isascii() and p.isdigit()):
                    return False
                if allowed is not None:
                    return len(p) <= 4 and any(a.startswith(p) for a in allowed)
                return len(p) <= 2 and int(p) <= hi

            c._entry.configure(validate="key", validatecommand=(self.register(valid), "%P"))
            c._entry.bind("<FocusOut>", lambda e, c=c: self.commit(c))
            c._entry.bind("<Return>", lambda e, c=c: self.commit(c))
        return c

    def picked(self, c):
        c.last = c.get()
        self.changed()

    def normalize(self, c):
        if not c.spec:
            return
        lo, hi, pad2, allowed = c.spec
        t = c.get().strip()
        if allowed is not None:
            val = t if t in allowed else c.last
        elif t.isascii() and t.isdigit():
            n = min(max(int(t), lo), hi)
            val = f"{n:02d}" if pad2 else str(n)
        else:
            val = c.last
        if c.get() != val:
            c.set(val)
        c.last = val

    def commit(self, c):
        self.normalize(c)
        self.changed()

    def commit_all(self):
        for c in self.num_combos:
            self.normalize(c)

    def fit(self):
        self.update_idletasks()
        h = self.winfo_reqheight()
        try:
            s = self._get_window_scaling()
        except Exception:
            s = 1.0
        self.geometry(f"{WIDTH}x{int(h / s)}")

    def pick_action(self, which):
        self.v_pc.set(1 if which == "pc" else 0)
        self.v_net.set(1 if which == "net" else 0)
        self.update_view()
        self.changed()

    def pick_method(self, which):
        self.v_cmd.set(1 if which == "cmd" else 0)
        self.v_app.set(1 if which == "app" else 0)
        self.changed()

    def update_view(self):
        self.mode_box.pack_forget()
        self.net_box.pack_forget()
        if self.v_net.get():
            self.net_box.pack(fill="x")
            if not self.names and not self.loading:
                self.load_adapters()
        else:
            self.mode_box.pack()
        self.fit()

    def changed(self):
        if self.save_job:
            try:
                self.after_cancel(self.save_job)
            except Exception:
                pass
        self.save_job = self.after(400, self.flush)

    def collect(self):
        self.commit_all()
        return {
            "action": "net" if self.v_net.get() else "pc",
            "method": "app" if self.v_app.get() else "cmd",
            "adapter": self.sel_adapter,
            "day": self.c_day.get(),
            "month": MONTHS.index(self.c_month.get()) + 1,
            "year": self.c_year.get(),
            "hour": self.c_hour.get(),
            "minute": self.c_min.get(),
            "ampm": self.c_ampm.get(),
        }

    def flush(self):
        self.save_job = None
        data = self.collect()
        threading.Thread(target=write_config, args=(data,), daemon=True).start()

    def set_status(self, text, color):
        self.lbl_status.configure(text=text, text_color=color)

    def on_select(self, _e=None):
        sel = self.lb.curselection()
        if sel and sel[0] < len(self.names):
            self.sel_adapter = self.names[sel[0]]
            self.changed()

    def load_adapters(self):
        self.loading = True
        self.btn_refresh.configure(state="disabled", fg_color=DIS)

        def work():
            data = []
            try:
                out = run_cmd([
                    "powershell", "-NoProfile", "-Command",
                    "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status | ConvertTo-Json -Compress"
                ]).stdout.strip()
                data = json.loads(out) if out else []
                if isinstance(data, dict):
                    data = [data]
            except Exception:
                data = []
            self.q.put(("adapters", data))

        threading.Thread(target=work, daemon=True).start()

    def fill_adapters(self, data):
        self.loading = False
        self.lb.configure(state="normal")
        self.lb.delete(0, "end")
        self.names = []
        for a in data:
            name = a.get("Name", "")
            self.names.append(name)
            self.lb.insert("end", f"{name} [{a.get('Status', '')}] {a.get('InterfaceDescription', '')}")
        self.lb.configure(height=max(1, min(len(self.names), 8)))
        if self.sel_adapter in self.names:
            i = self.names.index(self.sel_adapter)
            self.lb.selection_set(i)
            self.lb.see(i)
        if self.running:
            self.lb.configure(state="disabled")
        else:
            self.btn_refresh.configure(state="normal", fg_color=PUR)
        self.fit()

    def poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "adapters":
                    self.fill_adapters(item[1])
                elif item[0] == "netdone":
                    ok, msg = item[1], item[2]
                    self.reset_ui("DONE" if ok else "FAILED", GREEN if ok else RED)
                    self.lbl_info.configure(text=msg)
                    self.names = []
                    self.load_adapters()
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def target_dt(self):
        self.commit_all()
        try:
            h = int(self.c_hour.get()) % 12
            if self.c_ampm.get() == "PM":
                h += 12
            return datetime(int(self.c_year.get()), MONTHS.index(self.c_month.get()) + 1,
                            int(self.c_day.get()), h, int(self.c_min.get()), 0)
        except Exception:
            return None

    def lock(self, locked):
        st = "disabled" if locked else "normal"
        for c in (self.cb_pc, self.cb_net, self.cb_cmd, self.cb_app):
            c.configure(state=st)
        for c in (self.c_day, self.c_month, self.c_year, self.c_hour, self.c_min, self.c_ampm):
            c.configure(state="disabled" if locked else ("normal" if c.spec else "readonly"),
                        button_color=DIS if locked else PUR)
        self.lb.configure(state=st)
        self.btn_refresh.configure(state=st, fg_color=DIS if locked else PUR)

    def set_run_button(self, stop):
        if stop:
            self.btn_run.configure(text="Cancel", fg_color=RED, hover_color=REDH)
        else:
            self.btn_run.configure(text="Run", fg_color=PUR, hover_color=PURH)

    def ask(self, text, question=False):
        dlg = Dialog(self, text, question)
        self.wait_window(dlg)
        return dlg.result

    def toggle(self):
        if self.running:
            self.cancel()
        else:
            self.start()

    def start(self):
        target = self.target_dt()
        if target is None:
            self.ask("Selected date is invalid.")
            return
        secs = math.ceil((target - datetime.now()).total_seconds())
        if secs <= 0:
            self.ask("Selected time is in the past. Choose a future time.")
            return
        if self.v_net.get():
            if not self.sel_adapter or self.sel_adapter not in self.names:
                self.ask("Select a network adapter first.")
                return
            self.adapter = self.sel_adapter
            self.mode = "net"
            info = f"Disable adapter: {self.adapter}"
        else:
            self.adapter = None
            if self.v_cmd.get():
                self.mode = "cmd"
                run_cmd(["shutdown", "/a"])
                r = run_cmd(["shutdown", "/s", "/t", str(secs)])
                if r.returncode != 0:
                    msg = (r.stderr or r.stdout or "Unknown error").strip()
                    self.ask(f"Could not schedule shutdown:\n{msg}")
                    return
                info = "PC shutdown (CMD schedule)"
            else:
                self.mode = "app"
                info = "PC shutdown (forced, App)"
        self.target = target
        self.running = True
        self.lock(True)
        self.set_run_button(True)
        self.set_status("ACTIVE", GREEN)
        self.lbl_info.configure(text=f"{info} - {target.strftime('%d %b %I:%M %p')}")
        self.tick()

    def cancel(self):
        if self.tick_job:
            self.after_cancel(self.tick_job)
            self.tick_job = None
        if self.mode == "cmd":
            run_cmd(["shutdown", "/a"])
        self.reset_ui("CANCELLED", RED)

    def reset_ui(self, status, color):
        self.running = False
        self.target = None
        self.lock(False)
        self.set_run_button(False)
        self.set_status(status, color)
        self.lbl_timer.configure(text="00:00:00")
        self.lbl_info.configure(text="No task scheduled")

    def tick(self):
        self.tick_job = None
        if not self.running or not self.target:
            return
        rem = (self.target - datetime.now()).total_seconds()
        if rem <= 0:
            self.fire()
            return
        s = math.ceil(rem)
        dd, r = divmod(s, 86400)
        h, r = divmod(r, 3600)
        m, sec = divmod(r, 60)
        prefix = f"{dd}d " if dd else ""
        self.lbl_timer.configure(text=f"{prefix}{h:02d}:{m:02d}:{sec:02d}")
        self.tick_job = self.after(200, self.tick)

    def fire(self):
        self.lbl_timer.configure(text="00:00:00")
        if self.mode == "app":
            self.set_status("SHUTTING DOWN", RED)
            threading.Thread(
                target=lambda: run_cmd(["shutdown", "/s", "/f", "/t", "0"]), daemon=True
            ).start()
        elif self.mode == "cmd":
            self.set_status("SHUTTING DOWN", RED)
        else:
            self.set_status("DISABLING ADAPTER", AMBER)
            name = self.adapter

            def work():
                safe = name.replace("'", "''")
                r = run_cmd([
                    "powershell", "-NoProfile", "-Command",
                    f"Disable-NetAdapter -Name '{safe}' -Confirm:$false"
                ])
                if r.returncode == 0:
                    self.q.put(("netdone", True, f"Adapter disabled: {name}"))
                else:
                    err = (r.stderr or r.stdout or "Unknown error").strip().splitlines()
                    self.q.put(("netdone", False, err[0][:80] if err else "Unknown error"))

            threading.Thread(target=work, daemon=True).start()

    def on_close(self):
        if self.running and self.mode != "cmd":
            if not self.ask("A task is running. Closing will cancel it. Close anyway?", True):
                return
        write_config(self.collect())
        self.destroy()


def main():
    if os.name == "nt" and not is_admin():
        relaunch_as_admin()
        sys.exit(0)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dralder.shutdown.planner")
    except Exception:
        pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()