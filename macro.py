import ctypes
import os
import sys
import re
import subprocess
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import threading
import time
import pyautogui
import keyboard
import json
import random
import math
import ast
import operator as op


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


try:
    import pydirectinput
    pydirect_available = True
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pydirectinput", "-q"])
        import pydirectinput
        pydirect_available = True
    except Exception:
        pydirect_available = False


def get_real_mouse_pos():
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class HelioMacro:
    DEFAULT_BUFFER = 50
    HOTKEYS_FILE = "hotkeys.json"
    RESERVED_TOKENS = {"ctrl", "left ctrl", "right ctrl", "esc", "escape"}

    HEX_TAG_RE = re.compile(r"(</?)(#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)(>)")

    PALETTES = {
        "light": {
            "bg": "#BCCECB", "sidebar": "#ACBEBB", "accent": "#9BB0AD",
            "text": "black", "subtext": "#66777F",
            "ok": "#A8E6CF", "danger": "#FF8B94",
            "warn_bg": "#FEECEC", "warn_border": "red", "warn_fg": "red",
            "accent_title": "#14424F",
            "entry_bg": "white", "entry_fg": "black",
            "success_fg": "green", "error_fg": "red",
            "calc_num": "#E1E1E1", "calc_fn": "#D1D9D9", "calc_eq": "#FFCCBC",
            "console_bg": "#1E2227", "console_fg": "#9FE6B0",
        },
        "dark": {
            "bg": "#22262B", "sidebar": "#2A2F36", "accent": "#3D4650",
            "text": "#E8EAED", "subtext": "#9AA0A6",
            "ok": "#3F7D63", "danger": "#A25259",
            "warn_bg": "#3A2E2E", "warn_border": "#FF6B6B", "warn_fg": "#FF6B6B",
            "accent_title": "#6BD6FF",
            "entry_bg": "#1A1D21", "entry_fg": "#E8EAED",
            "success_fg": "#7BD88F", "error_fg": "#FF6B6B",
            "calc_num": "#3A3F45", "calc_fn": "#31363C", "calc_eq": "#5C4646",
            "console_bg": "#16181C", "console_fg": "#9FE6B0",
        },
    }

    LEVEL_COLORS = [
        ("macro", "#9FE6B0"), ("step", "#8FA6B8"), ("ac", "#6BD6FF"),
        ("settings", "#C6A3FF"), ("warn", "#FFC46B"), ("error", "#FF6B6B"),
        ("input", "#FFD700"),
    ]

    def __init__(self):
        self.running = False
        self.ac_running = False
        self.filename = "macros.json"
        self.macros = self.load_macros()
        self.selected_macro = None
        self.dev_unlocked = False
        self.ac_pos = None


        self.dark_mode = bool(self.app_settings.get("dark_mode", False))
        self.C = dict(self.PALETTES["dark" if self.dark_mode else "light"])
        self._themed = [] 
        self._tag_colors = {}     


        self.hotkey_bindings = {}
        self._hk_handlers = {}
        self._capturing = False

        self.root = tk.Tk()
        self.root.title("HelioMCUtils V0.3")
        self.root.geometry("1580x980")
        self.root.configure(bg=self.C["bg"])

        self.use_dangerous_eval = tk.BooleanVar(value=False)
        self.use_random_sleep = tk.BooleanVar(value=True)
        self.click_at_cursor_var = tk.BooleanVar(value=False)

        self.console_buffer_var = tk.IntVar(
            value=max(5, int(self.app_settings.get("console_buffer", self.DEFAULT_BUFFER)))
        )
        self.console_buffer_var.trace_add("write", self._on_buffer_change)
        self._step_filter_var = tk.StringVar()
        self._step_filter_var.trace_add("write", self.refresh_steps_tree)   
        self.ac_interval_var = tk.StringVar(value="0.10")
        self.ac_interval_var.trace_add("write", lambda *a: self._update_cps()) 
        self.ac_jitter_var = tk.StringVar(value="0.02")
        self.ac_button_var = tk.StringVar(value="left")
        self.ac_mode_var = tk.StringVar(value="click")
        self.ac_key_var = tk.StringVar(value="f")
        self.ac_hold_dur_var = tk.StringVar(value="0.10")
        self.ac_use_fixed_var = tk.BooleanVar(value=False)
        self.ac_double_var = tk.BooleanVar(value=False)
        self.ac_infinite_var = tk.BooleanVar(value=True)
        self.ac_repeat_var = tk.StringVar(value="100")

        self.sidebar = tk.Frame(self.root, bg=self.C["sidebar"], width=160)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.track(self.sidebar, {"bg": "sidebar"})

        try:
            full_img = tk.PhotoImage(file=resource_path("logo.png"))
            self.logo_img = full_img.subsample(4, 4)
            lbl = tk.Label(self.sidebar, image=self.logo_img, bg=self.C["sidebar"])
            self.track(lbl, {"bg": "sidebar"})
            lbl.pack(pady=20)
        except Exception:
            self.label(self.sidebar, "HELIO", bg_role="sidebar",
                       font=("Arial", 12, "bold")).pack(pady=20)

        try:
            self.macro_icon_raw = tk.PhotoImage(file=resource_path("macrotab.png"))
            self.macro_icon = self.macro_icon_raw.subsample(4, 4)
            self.math_icon_raw = tk.PhotoImage(file=resource_path("mathtab.png"))
            self.math_icon = self.math_icon_raw.subsample(4, 4)
        except Exception:
            self.macro_icon = self.math_icon = None

        self.btn_macro = self.button(self.sidebar, " Macros", bg_role="sidebar",
                                     image=self.macro_icon, compound="left", font=("Arial", 10),
                                     anchor="w", relief="flat", padx=10,
                                     command=lambda: self.show_tab("macro"))
        self.btn_macro.pack(fill="x", pady=5)

        self.btn_math = self.button(self.sidebar, " Math", bg_role="sidebar",
                                    image=self.math_icon, compound="left", font=("Arial", 10),
                                    anchor="w", relief="flat", padx=10,
                                    command=lambda: self.show_tab("math"))
        self.btn_math.pack(fill="x", pady=5)

        self.btn_settings = self.button(self.sidebar, "⚙ Settings", bg_role="sidebar",
                                        font=("Arial", 10), anchor="w", relief="flat", padx=10,
                                        command=lambda: self.show_tab("settings"))

        self.theme_btn = self.button(self.sidebar, "Dark Mode", bg_role="sidebar",
                                     font=("Arial", 10), anchor="w", relief="flat", padx=10,
                                     command=self.toggle_dark_mode)
        self.theme_btn.pack(side="bottom", fill="x", pady=8, padx=4)

        # --- CONTENT ---
        self.container = tk.Frame(self.root, bg=self.C["bg"])
        self.container.pack(side="right", fill="both", expand=True)
        self.track(self.container, {"bg": "bg"})

        self.macro_tab = tk.Frame(self.container, bg=self.C["bg"])
        self.math_tab = tk.Frame(self.container, bg=self.C["bg"])
        self.settings_tab = tk.Frame(self.container, bg=self.C["bg"])
        for t in (self.macro_tab, self.math_tab, self.settings_tab):
            self.track(t, {"bg": "bg"})

        self.setup_macro_ui()
        self.setup_math_ui()
        self.setup_settings_ui()

        self.show_tab("macro")

        keyboard.add_hotkey('f6', lambda: self.root.after(0, self.start))
        keyboard.add_hotkey('f7', lambda: self.root.after(0, self.stop))
        keyboard.add_hotkey('f8', lambda: self.root.after(0, self.record_step, "left_click"))
        keyboard.add_hotkey('f9', lambda: self.root.after(0, self.record_step, "right_click"))
        keyboard.add_hotkey('f10', lambda: self.root.after(0, self.record_step, "hold_key"))
        keyboard.add_hotkey('f5', lambda: self.root.after(0, self.toggle_autoclicker))
        keyboard.add_hotkey('f11', lambda: self.root.after(0, self.capture_ac_pos))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


    def track(self, widget, option_roles):
        """Register a widget so apply_theme() can restyle it on mode switch."""
        self._themed.append((widget, option_roles))

    def label(self, parent, text=None, bg_role=None, fg_role=None, **kw):
        bg = self.C[bg_role] if bg_role else None
        fg = self.C[fg_role] if fg_role else None
        if bg is not None:
            kw["bg"] = bg
        if fg is not None:
            kw["fg"] = fg
        w = tk.Label(parent, text=text, **kw)
        self.track(w, {**({"bg": bg_role} if bg_role else {}),
                       **({"fg": fg_role} if fg_role else {})})
        return w

    def button(self, parent, text=None, bg_role=None, fg_role=None, **kw):
        bg = self.C[bg_role] if bg_role else None
        fg = self.C[fg_role] if fg_role else None
        if bg is not None:
            kw["bg"] = bg
        if fg is not None:
            kw["fg"] = fg
        w = tk.Button(parent, text=text, **kw)
        self.track(w, {**({"bg": bg_role} if bg_role else {}),
                       **({"fg": fg_role} if fg_role else {})})
        return w

    def frame(self, parent, role=None, **kw):
        if role:
            kw["bg"] = self.C[role]
        w = tk.Frame(parent, **kw)
        if role:
            self.track(w, {"bg": role})
        return w

    def labelframe(self, parent, text=None, **kw):
        w = tk.LabelFrame(parent, text=text, bg=self.C["bg"], **kw)
        self.track(w, {"bg": "bg"})
        return w

    def entry(self, parent, **kw):
        w = tk.Entry(parent, bg=self.C["entry_bg"], fg=self.C["entry_fg"],
                     insertbackground=self.C["text"], **kw)
        self.track(w, {"bg": "entry_bg", "fg": "entry_fg",
                       "insertbackground": "text"})
        return w

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.app_settings["dark_mode"] = self.dark_mode
        self.save_macros()
        self.apply_theme()

    def apply_theme(self):
        self.C = dict(self.PALETTES["dark" if self.dark_mode else "light"])
        self.root.configure(bg=self.C["bg"])
        for widget, roles in self._themed:
            try:
                opts = {opt: self.C[role] for opt, role in roles.items()}
                widget.configure(**opts)
            except tk.TclError:
                pass  
        try:
            self.theme_btn.config(text=("Light Mode" if self.dark_mode else "Dark Mode"))
        except tk.TclError:
            pass
        try:
            self.console.config(bg=self.C["console_bg"])
        except tk.TclError:
            pass
        try:
            self.console_input.config(bg=self.C["console_bg"], fg=self.C["console_fg"],
                                      insertbackground=self.C["console_fg"])
        except tk.TclError:
            pass

        try:
            self.console_bar.config(bg=self.C["sidebar"])
        except tk.TclError:
            pass
        self.log(f"theme -> {'dark' if self.dark_mode else 'light'} mode", "SETTINGS")

    def load_macros(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict) and "macros" in data:
                    self.app_settings = data.get("app_settings", {}) or {}
                    return data["macros"]
                self.app_settings = {}
                return data
            except Exception:
                pass
        self.app_settings = {}
        return {}

    def save_macros(self):
        with open(self.filename, 'w') as f:
            json.dump({"macros": self.macros, "app_settings": self.app_settings},
                      f, indent=4)

    def _on_buffer_change(self, *args):
        try:
            val = max(5, int(self.console_buffer_var.get()))
        except Exception:
            return
        if val == self.app_settings.get("console_buffer"):
            return
        self.app_settings["console_buffer"] = val
        self.save_macros()
        self.log(f"console buffer -> {val} lines", "SETTINGS")

    def update_status(self, text, color="black"):
        alias = {"black": "text", "red": "error_fg", "green": "success_fg"}
        color = self.C[alias.get(color, color)]
        self.status_label.config(text=text, fg=color)

    def show_tab(self, tab_name):
        self.macro_tab.pack_forget()
        self.math_tab.pack_forget()
        self.settings_tab.pack_forget()
        for b in (self.btn_macro, self.btn_math, self.btn_settings):
            b.config(bg=self.C["sidebar"])
        if tab_name == "macro":
            self.macro_tab.pack(fill="both", expand=True)
            self.btn_macro.config(bg=self.C["accent"])
        elif tab_name == "math":
            self.math_tab.pack(fill="both", expand=True)
            self.btn_math.config(bg=self.C["accent"])
        elif tab_name == "settings":
            self.settings_tab.pack(fill="both", expand=True)
            self.btn_settings.config(bg=self.C["accent"])

    def setup_macro_ui(self):
        self.macro_pane = tk.PanedWindow(self.macro_tab, orient="vertical", sashwidth=6,
                                         bg=self.C["sidebar"], relief="flat")
        self.macro_pane.pack(fill="both", expand=True, padx=10, pady=10)
        upper = self.frame(self.macro_pane, role="bg")
        console_zone = self.frame(self.macro_pane, role="bg")
        self.macro_pane.add(upper, minsize=380, stretch="first")
        self.macro_pane.add(console_zone, minsize=150, stretch="always")

        h_pane = tk.PanedWindow(upper, orient="horizontal", sashwidth=6,
                                bg=self.C["sidebar"], relief="flat")
        h_pane.pack(fill="both", expand=True)
        left_zone = self.frame(h_pane, role="bg")
        right_zone = self.frame(h_pane, role="bg")
        h_pane.add(left_zone, minsize=430, stretch="always")
        h_pane.add(right_zone, minsize=300, stretch="always")

        self.build_editor_zone(left_zone)
        self.setup_ac_ui(right_zone)
        self.setup_hotkey_ui(right_zone)
        self.build_console(console_zone)

    def build_editor_zone(self, parent):
        top_bar = self.frame(parent, role="bg")
        top_bar.pack(fill="x", pady=(5, 0))
        self.status_label = self.label(top_bar, "Status: Idle", bg_role="bg",
                                      fg_role="text", font=("Arial", 11, "bold"))
        self.status_label.pack(side="left", padx=5)
        self.label(top_bar, "Step Filter:", bg_role="bg").pack(side="right", padx=(0, 3))
        fe = self.entry(top_bar, width=14, font=("Consolas", 9))
        fe.configure(textvariable=self._step_filter_var)
        fe.pack(side="right")

        list_frame = self.labelframe(parent, " Saved Macros ")
        list_frame.pack(fill="x", padx=10, pady=5)
        list_row = self.frame(list_frame, role="bg")
        list_row.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_row, height=5, font=("Consolas", 10),
                                  exportselection=False,
                                  bg=self.C["entry_bg"], fg=self.C["text"],
                                  selectbackground=self.C["accent"])
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind('<Double-Button-1>', lambda e: self.select_macro_from_list())
        mgmt_col = self.frame(list_row, role="bg")
        mgmt_col.pack(side="right", padx=5)
        self.button(mgmt_col, "Select", width=12, bg_role="accent",
                    command=self.select_macro_from_list).pack(pady=2)
        self.button(mgmt_col, "New Macro", width=12,
                    command=self.add_new_macro).pack(pady=2)
        self.button(mgmt_col, "Delete Macro", width=12,
                    command=self.delete_macro).pack(pady=2)
        self.button(mgmt_col, "Toggle Loop", width=12,
                    command=self.toggle_loop).pack(pady=2)
        self.refresh_listbox()

        tree_frame = self.labelframe(parent, " Macro Editor ")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        cols = ("#", "type", "x", "y", "key", "delay", "dur")
        widths = (35, 85, 50, 50, 45, 55, 50)
        self.steps_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        for col, w in zip(cols, widths):
            self.steps_tree.heading(col, text=col.upper())
            self.steps_tree.column(col, width=w, anchor="center", stretch=True)
        self.steps_tree.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(tree_frame, command=self.steps_tree.yview)
        sb.pack(side="right", fill="y")
        self.steps_tree.config(yscrollcommand=sb.set)
        step_btns = self.frame(tree_frame, role="bg")
        step_btns.pack(fill="x", pady=(5, 0))
        self.button(step_btns, "Del Step", width=9,
                    command=self.delete_selected_step).pack(side="left", padx=3)
        self.button(step_btns, "Move Up", width=8,
                    command=lambda: self.move_step(-1)).pack(side="left", padx=3)
        self.button(step_btns, "Move Down", width=9,
                    command=lambda: self.move_step(1)).pack(side="left", padx=3)
        self.button(step_btns, "Edit Msg", width=8,
                    command=self.edit_msg).pack(side="left", padx=3)
        self.label(step_btns, "(empty = none)", bg_role="bg", fg_role="subtext",
                   font=("Arial", 8)).pack(side="right", padx=3)

        rec_frame = self.labelframe(parent, " Recording Controls ")
        rec_frame.pack(fill="x", padx=10, pady=5)
        ctl_row = self.frame(rec_frame, role="bg")
        ctl_row.pack(pady=2, anchor="w")
        self.button(ctl_row, "Add L-Click (F8)",
                    command=lambda: self.record_step("left_click")).pack(side="left", padx=3)
        self.button(ctl_row, "Add R-Click (F9)",
                    command=lambda: self.record_step("right_click")).pack(side="left", padx=3)
        cb = tk.Checkbutton(ctl_row, text="Ignore positions (cursor)",
                            variable=self.click_at_cursor_var, bg=self.C["bg"],
                            fg=self.C["text"],
                            selectcolor=self.C["entry_bg"],
                            font=("Arial", 9))
        self.track(cb, {"bg": "bg", "fg": "text"})
        cb.pack(side="left", padx=10)

        delay_row = self.frame(rec_frame, role="bg")
        delay_row.pack(pady=2, anchor="w")
        self.label(delay_row, "Step Delay (Sec):", bg_role="bg").pack(side="left")
        de = self.entry(delay_row, width=5)
        de.insert(0, "0.5")
        de.pack(side="left", padx=5)
        self.delay_entry = de

        hold_row = self.frame(rec_frame, role="bg")
        hold_row.pack(pady=2, anchor="w")
        self.label(hold_row, "Key:", bg_role="bg").pack(side="left")
        ke = self.entry(hold_row, width=4)
        ke.insert(0, "w")
        ke.pack(side="left", padx=2)
        self.key_entry = ke
        self.label(hold_row, "Dur:", bg_role="bg").pack(side="left")
        du = self.entry(hold_row, width=4)
        du.insert(0, "1.0")
        du.pack(side="left", padx=2)
        self.dur_entry = du
        self.button(hold_row, "Add Hold (F10)",
                    command=lambda: self.record_step("hold_key")).pack(side="left", padx=5)

        log_row = self.frame(rec_frame, role="bg")
        log_row.pack(pady=2, anchor="w")
        self.label(log_row, "Log text:", bg_role="bg").pack(side="left")
        self.log_text_entry = self.entry(log_row, width=32, font=("Consolas", 9))
        self.log_text_entry.pack(side="left", padx=5)
        self.log_text_entry.bind("<Return>", lambda e: self.add_log_line())
        self.button(log_row, "Add Log Line", command=self.add_log_line).pack(side="left", padx=3)

        run_frame = self.frame(parent, role="bg")
        run_frame.pack(fill="x", padx=10, pady=(5, 10))
        self.start_btn = self.button(run_frame, "START BOT (F6)", bg_role="ok",
                                     font=("Arial", 10, "bold"), height=2, command=self.start)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.track(self.start_btn, {"bg": "ok"})
        self.stop_btn = self.button(run_frame, "STOP BOT (F7)", bg_role="danger",
                                   font=("Arial", 10, "bold"), height=2, command=self.stop)
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=3)
        self.track(self.stop_btn, {"bg": "danger"})

    def setup_ac_ui(self, parent):
        self.label(parent, "AUTOCLICKER", bg_role="sidebar", fg_role="accent_title",
                   font=("Consolas", 10, "bold")).pack(fill="x", padx=10, pady=(2, 0))

        timing = self.labelframe(parent, " Timing ", padx=6, pady=3)
        timing.pack(fill="x", padx=8, pady=(2, 1))
        r1 = self.frame(timing, role="bg"); r1.pack(anchor="w")
        self.label(r1, "Interval (sec):", bg_role="bg", font=("Arial", 9)).pack(side="left")
        self.entry(r1, width=7, font=("Consolas", 9),
                   textvariable=self.ac_interval_var).pack(side="left", padx=3)
        self.label(r1, "~", bg_role="bg").pack(side="left", padx=(4, 1))
        self.ac_cps_label = self.label(r1, "-- cps", bg_role="bg", font=("Consolas", 8))
        self.ac_cps_label.pack(side="left")
        r2 = self.frame(timing, role="bg"); r2.pack(anchor="w")
        self.label(r2, "Rand width (+/-):", bg_role="bg", font=("Arial", 9)).pack(side="left")
        self.entry(r2, width=7, font=("Consolas", 9),
                   textvariable=self.ac_jitter_var).pack(side="left", padx=3)
        self.label(r2, "(>= 1ms)", bg_role="bg", fg_role="subtext",
                  font=("Arial", 7)).pack(side="left")

        action = self.labelframe(parent, " Action ", padx=6, pady=3)
        action.pack(fill="x", padx=8, pady=1)
        r3 = self.frame(action, role="bg"); r3.pack(anchor="w")
        self.label(r3, "Mode:", bg_role="bg", font=("Arial", 9)).pack(side="left")
        om1 = tk.OptionMenu(r3, self.ac_mode_var, "click", "hold", "press_key")
        om1.config(font=("Consolas", 8), bg=self.C["accent"], fg=self.C["text"])
        om1.pack(side="left", padx=2)
        self.track(om1, {"bg": "accent", "fg": "text"})
        self.label(r3, "Btn:", bg_role="bg", font=("Arial", 9)).pack(side="left", padx=(6, 1))
        om2 = tk.OptionMenu(r3, self.ac_button_var, "left", "right", "middle")
        om2.config(font=("Consolas", 8), bg=self.C["accent"], fg=self.C["text"])
        om2.pack(side="left", padx=2)
        self.track(om2, {"bg": "accent", "fg": "text"})
        r4 = self.frame(action, role="bg"); r4.pack(anchor="w")
        self.label(r4, "Key:", bg_role="bg", font=("Arial", 9)).pack(side="left")
        self.entry(r4, width=5, font=("Consolas", 9),
                   textvariable=self.ac_key_var).pack(side="left", padx=2)
        self.label(r4, "Dur:", bg_role="bg", font=("Arial", 9)).pack(side="left", padx=(6, 1))
        self.entry(r4, width=7, font=("Consolas", 9),
                   textvariable=self.ac_hold_dur_var).pack(side="left", padx=2)
        acb = tk.Checkbutton(action, text="Double click (click mode)",
                             variable=self.ac_double_var, bg=self.C["bg"], fg=self.C["text"],
                             selectcolor=self.C["entry_bg"], font=("Arial", 8))
        self.track(acb, {"bg": "bg", "fg": "text"})
        acb.pack(anchor="w")

        loc = self.labelframe(parent, " Location ", padx=6, pady=3)
        loc.pack(fill="x", padx=8, pady=1)
        r5a = self.frame(loc, role="bg"); r5a.pack(anchor="w")
        rb1 = tk.Radiobutton(r5a, text="At current cursor position",
                             variable=self.ac_use_fixed_var, value=False,
                             bg=self.C["bg"], fg=self.C["text"],
                             selectcolor=self.C["entry_bg"], font=("Arial", 8))
        self.track(rb1, {"bg": "bg", "fg": "text"})
        rb1.pack(side="left")
        r5b = self.frame(loc, role="bg"); r5b.pack(anchor="w")
        rb2 = tk.Radiobutton(r5b, text="Fixed:",
                             variable=self.ac_use_fixed_var, value=True,
                             bg=self.C["bg"], fg=self.C["text"],
                             selectcolor=self.C["entry_bg"], font=("Arial", 8))
        self.track(rb2, {"bg": "bg", "fg": "text"})
        rb2.pack(side="left")
        self.ac_pos_label = self.label(r5b, "(none)", bg_role="bg",
                                       font=("Consolas", 8), width=12, anchor="w")
        self.ac_pos_label.pack(side="left")
        self.button(r5b, "Capture (F11)", font=("Arial", 8),
                    command=self.capture_ac_pos).pack(side="left", padx=2)

        repeat = self.labelframe(parent, " Repeat ", padx=6, pady=3)
        repeat.pack(fill="x", padx=8, pady=1)
        r6 = self.frame(repeat, role="bg"); r6.pack(anchor="w")
        icb = tk.Checkbutton(r6, text="Infinite", variable=self.ac_infinite_var,
                             bg=self.C["bg"], fg=self.C["text"],
                             selectcolor=self.C["entry_bg"], font=("Arial", 8),
                             command=self._sync_repeat_state)
        self.track(icb, {"bg": "bg", "fg": "text"})
        icb.pack(side="left")
        self.label(r6, "Or N:", bg_role="bg", font=("Arial", 8)).pack(side="left", padx=(8, 1))
        self.ac_repeat_entry = self.entry(r6, width=7, font=("Consolas", 9),
                                          textvariable=self.ac_repeat_var)
        self.ac_repeat_entry.pack(side="left", padx=2)
        self._sync_repeat_state()
        self._update_cps()

        ac_run = self.frame(parent, role="bg")
        ac_run.pack(fill="x", padx=8, pady=(2, 2))
        self.ac_start_btn = self.button(ac_run, "START AUTOCLICKER (F5)", bg_role="ok",
                                        font=("Arial", 10, "bold"), height=1,
                                        command=self.toggle_autoclicker)
        self.ac_start_btn.pack(fill="x")
        self.track(self.ac_start_btn, {"bg": "ok"})
        self.ac_status_label = self.label(ac_run, "AutoClicker: Idle", bg_role="bg",
                                          fg_role="text", font=("Arial", 9, "bold"))
        self.ac_status_label.pack(pady=1)

    def _update_cps(self):
        try:
            iv = float(self.ac_interval_var.get())
            self.ac_cps_label.config(text=f"{1.0 / max(iv, 0.001):.1f} cps")
        except ValueError:
            self.ac_cps_label.config(text="-- cps")

    def _sync_repeat_state(self):
        self.ac_repeat_entry.config(state="disabled" if self.ac_infinite_var.get() else "normal")

    def capture_ac_pos(self):
        x, y = get_real_mouse_pos()
        self.ac_pos = (x, y)
        self.ac_pos_label.config(text=f"({x}, {y})")
        self.log(f"autoclicker position captured ({x},{y})", "AC")

    def toggle_autoclicker(self):
        if self.ac_running:
            self._ac_stop_ui()
            self.log("autoclicker stopped", "WARN")
        else:
            cfg = self._read_ac_config()
            if cfg is None:
                return
            if cfg["use_fixed"] and self.ac_pos is None:
                messagebox.showwarning("AutoClicker", "Capture a position first (F11) or use cursor mode.")
                return
            self.ac_running = True
            self.ac_status_label.config(text="AutoClicker: RUNNING", fg=self.C["success_fg"])
            self.ac_start_btn.config(text="STOP AUTOCLICKER (F5)", bg=self.C["danger"])
            self.log(f"autoclicker started: {cfg['mode']} every {cfg['interval']}s (+/- {cfg['jitter']})", "AC")
            threading.Thread(target=self.ac_loop, args=(cfg,), daemon=True).start()

    def _read_ac_config(self):
        try:
            interval = float(self.ac_interval_var.get())
            jitter = float(self.ac_jitter_var.get())
        except ValueError:
            messagebox.showerror("AutoClicker", "Interval and jitter must be numbers.")
            return None
        interval = max(0.001, interval)
        jitter = max(0.0, jitter)
        try:
            hold_dur = max(0.001, float(self.ac_hold_dur_var.get()))
        except ValueError:
            hold_dur = 0.1
        repeats = None
        if not self.ac_infinite_var.get():
            try:
                repeats = max(1, int(float(self.ac_repeat_var.get())))
            except ValueError:
                messagebox.showerror("AutoClicker", "Repeat count must be a number.")
                return None
        return {
            "interval": interval, "jitter": jitter, "mode": self.ac_mode_var.get(),
            "button": self.ac_button_var.get(), "key": self.ac_key_var.get().lower().strip() or "f",
            "hold_dur": hold_dur, "use_fixed": self.ac_use_fixed_var.get(),
            "double": self.ac_double_var.get(), "repeats": repeats,
        }

    def ac_loop(self, cfg):
        target = pydirectinput if pydirect_available else pyautogui
        try:
            count = 0
            while self.ac_running:
                x, y = self.ac_pos if cfg["use_fixed"] else get_real_mouse_pos()
                if cfg["mode"] == "click":
                    clicks = 2 if cfg["double"] else 1
                    target.click(x, y, clicks=clicks, button=cfg["button"])
                elif cfg["mode"] == "hold":
                    target.mouseDown(x, y, button=cfg["button"])
                    time.sleep(cfg["hold_dur"])
                    target.mouseUp(button=cfg["button"])
                elif cfg["mode"] == "press_key":
                    target.keyDown(cfg["key"])
                    time.sleep(cfg["hold_dur"])
                    target.keyUp(cfg["key"])
                count += 1
                self._safe_after(self.log, f"click #{count} @ ({x},{y})", "AC")
                if cfg["repeats"] is not None and count >= cfg["repeats"]:
                    self._safe_after(self.log, f"autoclicker finished ({count} repeats)", "AC")
                    self._safe_after(self._ac_stop_ui)
                    return
                delay = cfg["interval"] + random.uniform(-cfg["jitter"], cfg["jitter"])
                time.sleep(max(0.001, delay))
            try:
                target.mouseUp(button=cfg["button"])
                if cfg["mode"] == "press_key":
                    target.keyUp(cfg["key"])
            except Exception:
                pass
        except Exception as e:
            self._safe_after(self.log, f"autoclicker crashed: {e}", "ERROR")
            self._safe_after(self._ac_stop_ui)

    def _safe_after(self, fn, *args):
        """root.after that tolerates a destroyed window (clean shutdown)."""
        try:
            self.root.after(0, fn, *args)
        except tk.TclError:
            pass

    def _ac_stop_ui(self):
        self.ac_running = False
        self.ac_status_label.config(text="AutoClicker: Stopped", fg=self.C["error_fg"])
        self.ac_start_btn.config(text="START AUTOCLICKER (F5)", bg=self.C["ok"])

    def _hotkey_is_allowed(self, combo):
        tokens = [t.strip().lower() for t in combo.split("+")]
        for t in tokens:
            if t in self.RESERVED_TOKENS or "mouse" in t or "click" in t:
                return False
        return True

    def setup_hotkey_ui(self, parent):
        hk = self.labelframe(parent, " HOTKEY BINDER ", padx=8, pady=6)
        hk.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        list_row = self.frame(hk, role="bg")
        list_row.pack(fill="both", expand=True)
        self.hk_listbox = tk.Listbox(list_row, height=5, font=("Consolas", 9),
                                     exportselection=False,
                                     bg=self.C["entry_bg"], fg=self.C["text"],
                                     selectbackground=self.C["accent"])
        self.hk_listbox.pack(side="left", fill="both", expand=True)
        hk_btn_col = self.frame(list_row, role="bg")
        hk_btn_col.pack(side="right", padx=4)
        self.hk_bind_btn = self.button(hk_btn_col, "Bind Key", width=10,
                                       command=self.start_hotkey_capture)
        self.hk_bind_btn.pack(pady=2)
        self.button(hk_btn_col, "Remove", width=10,
                    command=self.remove_hotkey_binding).pack(pady=2)
        self.button(hk_btn_col, "Clear", width=10,
                    command=self.clear_hotkey_bindings).pack(pady=2)

        self.label(hk, "Bindings trigger the macro selected below:",
                   bg_role="bg", font=("Arial", 7), fg_role="subtext").pack(anchor="w")
        macro_row = self.frame(hk, role="bg")
        macro_row.pack(fill="x", pady=(1, 0))
        self.label(macro_row, "Macro:", bg_role="bg", font=("Arial", 8)).pack(side="left")
        self.hk_macro_var = tk.StringVar(value="(select a macro)")
        self.hk_macro_menu = tk.OptionMenu(macro_row, self.hk_macro_var, "(select a macro)")
        self.hk_macro_menu.config(font=("Consolas", 8), bg=self.C["accent"], fg=self.C["text"])
        self.hk_macro_menu.pack(side="left", fill="x", expand=True, padx=3)
        self.track(self.hk_macro_menu, {"bg": "accent", "fg": "text"})

        self.hk_bind_status = self.label(hk, "", bg_role="bg",
                                         font=("Consolas", 8), fg_role="accent_title")
        self.hk_bind_status.pack(anchor="w", pady=(2, 0))

        file_row = self.frame(hk, role="bg")
        file_row.pack(fill="x", pady=(3, 0))
        self.button(file_row, "Save Hotkeys", width=12,
                    command=self.save_hotkeys).pack(side="left", padx=2)
        self.button(file_row, "Load Hotkeys", width=12,
                    command=self.load_hotkeys_dialog).pack(side="left", padx=2)

        self.refresh_hotkey_listbox()
        self.refresh_hotkey_macro_menu()

    def refresh_hotkey_listbox(self):
        self.hk_listbox.delete(0, tk.END)
        for combo, macro in self.hotkey_bindings.items():
            self.hk_listbox.insert(tk.END, f"{combo}  ->  {macro}")

    def refresh_hotkey_macro_menu(self):
        menu = self.hk_macro_menu["menu"]
        menu.delete(0, "end")
        names = list(self.macros.keys())
        for name in names:
            menu.add_command(label=name,
                             command=lambda n=name: self.hk_macro_var.set(n))
        if names and self.hk_macro_var.get() not in self.macros:
            self.hk_macro_var.set(names[0])

    def start_hotkey_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self.hk_bind_btn.config(text="Press...", state="disabled")
        self.hk_bind_status.config(text="Press keys now (ESC cancels)")
        self.log("press the key combination to bind (ESC cancels)...", "SETTINGS")
        threading.Thread(target=self._capture_worker, daemon=True).start()

    def _capture_worker(self):
        try:
            combo = keyboard.read_hotkey(suppress=False)
        except Exception as e:
            combo = ""
            self._safe_after(self.log, f"capture failed: {e}", "ERROR")
        self._safe_after(self._finish_capture, combo)

    def _finish_capture(self, combo):
        self._capturing = False
        self.hk_bind_btn.config(text="Bind Key", state="normal")
        self.hk_bind_status.config(text="")
        if not combo or combo.lower() in ("esc", "escape"):
            self.log("binding cancelled", "SETTINGS")
            return
        if not self._hotkey_is_allowed(combo):
            self.log(f"'{combo}' is reserved (clicks / ctrl / esc) and cannot be bound", "WARN")
            return
        macro_name = self.hk_macro_var.get()
        if macro_name not in self.macros:
            self.update_status("Pick a macro in the binder dropdown first", "red")
            self.log(f"no macro selected for binding '{combo}'", "WARN")
            return
        if combo in self.hotkey_bindings:
            self._unregister_hotkey(combo)
        self.hotkey_bindings[combo] = macro_name
        self._register_hotkey(combo, macro_name)
        self.refresh_hotkey_listbox()
        self.log(f"bound {combo} -> {macro_name}", "MACRO")

    def _register_hotkey(self, combo, macro_name):
        try:
            handle = keyboard.add_hotkey(
                combo,
                lambda mn=macro_name: self._safe_after(self._hotkey_fired, mn))
            self._hk_handlers[combo] = handle
        except Exception as e:
            self.log(f"couldn't register {combo}: {e}", "ERROR")

    def _unregister_hotkey(self, combo):
        handle = self._hk_handlers.pop(combo, None)
        if handle is not None:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass

    def _hotkey_fired(self, macro_name):
        if not self.running:
            self.selected_macro = macro_name
            self.start()

    def remove_hotkey_binding(self):
        sel = self.hk_listbox.curselection()
        if not sel:
            return
        combo = self.hk_listbox.get(sel[0]).rsplit("  ->  ", 1)[0]
        self._unregister_hotkey(combo)
        self.hotkey_bindings.pop(combo, None)
        self.refresh_hotkey_listbox()
        self.log(f"removed binding {combo}", "SETTINGS")

    def clear_hotkey_bindings(self):
        for combo in list(self.hotkey_bindings.keys()):
            self._unregister_hotkey(combo)
        self.hotkey_bindings.clear()
        self.refresh_hotkey_listbox()
        self.log("cleared all hotkey bindings", "WARN")

    def save_hotkeys(self):
        try:
            with open(self.HOTKEYS_FILE, "w") as f:
                json.dump(self.hotkey_bindings, f, indent=4)
            self.log(f"saved {len(self.hotkey_bindings)} bindings to {self.HOTKEYS_FILE}", "SETTINGS")
        except Exception as e:
            self.log(f"couldn't save hotkeys: {e}", "ERROR")

    def load_hotkeys_dialog(self):
        if self._capturing:
            return
        if not os.path.exists(self.HOTKEYS_FILE):
            self.log(f"no {self.HOTKEYS_FILE} found yet", "WARN")
            return
        try:
            with open(self.HOTKEYS_FILE, "r") as f:
                loaded = json.load(f)
        except Exception as e:
            self.log(f"couldn't load hotkeys: {e}", "ERROR")
            return
        if not isinstance(loaded, dict):
            self.log(f"{self.HOTKEYS_FILE} is malformed", "ERROR")
            return
        for combo in list(self._hk_handlers.keys()):
            self._unregister_hotkey(combo)
        self.hotkey_bindings = {}
        skipped = []
        for combo, macro in loaded.items():
            if not self._hotkey_is_allowed(combo):
                skipped.append(f"{combo} (reserved)")
                continue
            if macro not in self.macros:
                skipped.append(f"{combo} (missing macro)")
                continue
            self.hotkey_bindings[combo] = macro
            self._register_hotkey(combo, macro)
        self.refresh_hotkey_listbox()
        msg = f"loaded {len(self.hotkey_bindings)} bindings from {self.HOTKEYS_FILE}"
        if skipped:
            msg += f" | skipped: {', '.join(skipped)}"
        self.log(msg, "SETTINGS")

    def build_console(self, parent):
        self.console_bar = self.frame(parent, role="sidebar")
        self.console_bar.pack(side="top", fill="x")
        self.label(self.console_bar, " MACRO CONSOLE ", bg_role="sidebar",
                   font=("Consolas", 10, "bold")).pack(side="left", padx=5, pady=2)
        self.console_level_var = tk.StringVar(value="ALL")
        self.label(self.console_bar, "Level:", bg_role="sidebar",
                   font=("Arial", 9)).pack(side="right", padx=(10, 2))
        tk.OptionMenu(self.console_bar, self.console_level_var, "ALL", "MACRO", "STEP",
                      "AC", "SETTINGS", "WARN", "ERROR", "INPUT").pack(side="right", padx=3)
        self.label(self.console_bar, "Buffer:", bg_role="sidebar",
                   font=("Arial", 9)).pack(side="right", padx=(10, 2))
        tk.Spinbox(self.console_bar, from_=10, to=1000, increment=10,
                   textvariable=self.console_buffer_var, width=6,
                   font=("Consolas", 9)).pack(side="right")

        self.console = tk.Text(parent, height=10, bg=self.C["console_bg"],
                               fg=self.C["console_fg"],
                               insertbackground=self.C["console_fg"],
                               font=("Consolas", 9), state="disabled",
                               relief="flat", wrap="none")
        self.console.pack(side="top", fill="both", expand=True, padx=2, pady=(0, 2))
        for lvl, col in self.LEVEL_COLORS:
            self.console.tag_config(lvl, foreground=col)

        input_row = self.frame(parent, role="bg")
        input_row.pack(side="top", fill="x", pady=(0, 4))
        self.console_input = self.entry(input_row, font=("Consolas", 9), relief="flat")
        self.console_input.configure(bg=self.C["console_bg"], fg=self.C["console_fg"])
        self.console_input.pack(side="left", fill="x", expand=True, padx=(2, 0), ipady=3)
        self.console_input.bind("<Return>", lambda e: self.push_to_console())
        self.push_btn = self.button(input_row, "PUSH", font=("Consolas", 9, "bold"),
                                    bg_role="accent", relief="flat", width=8,
                                    command=self.push_to_console)
        self.push_btn.pack(side="left", padx=(2, 2))

        self.log("console initialized", "MACRO")

    def push_to_console(self):
        msg = self.console_input.get().strip()
        if not msg:
            return
        self.console_input.delete(0, tk.END)
        self.log(msg, "INPUT")

    def _valid_hex(self, hx):
        """Returns normalized 6-digit hex ('#rrggbb') if valid, else None."""
        m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", hx)
        if not m:
            return None
        digits = m.group(1)
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        return "#" + digits.lower()

    def _insert_styled(self, text):
        """Insert text into the console, honoring <#hex>...</#hex> segments.
        Invalid colors render literally (as plain text)."""
        idx = 0
        active_tag = None
        for m in self.HEX_TAG_RE.finditer(text):
            seg = text[idx:m.start()]
            if seg:
                self.console.insert("end", seg, active_tag)
            closing, hexpart, _close_bracket = m.group(1) == "</", m.group(2), None
            norm = self._valid_hex(hexpart)
            if norm is None:
                self.console.insert("end", m.group(0), active_tag)
            elif closing:
                active_tag = None
            else:
                tag = f"hx_{norm[1:]}"
                if tag not in self._tag_colors:
                    try:
                        self.console.tag_config(tag, foreground=norm)
                        self._tag_colors[tag] = norm
                    except tk.TclError:
                        self.console.insert("end", m.group(0), active_tag)
                        continue
                active_tag = tag
            idx = m.end()
        tail = text[idx:]
        if tail:
            self.console.insert("end", tail, active_tag)

    def log(self, msg, level="STEP"):
        if not hasattr(self, "console"):
            return
        try:
            buf = max(5, int(self.console_buffer_var.get()))
        except Exception:
            buf = self.DEFAULT_BUFFER
        ts = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        try:
            lvl_filter = self.console_level_var.get()
        except Exception:
            lvl_filter = "ALL"
        if lvl_filter != "ALL" and level != lvl_filter and level not in ("WARN", "ERROR"):
            return
        lvl_tag = level.lower()
        if lvl_tag not in [name for name, _ in self.LEVEL_COLORS]:
            lvl_tag = "step"
        self.console.config(state="normal")
        prefix = f"[{ts}] [{level}] "
        self.console.insert("end", prefix, lvl_tag)
        self._insert_styled(msg)
        self.console.insert("end", "\n", lvl_tag)
        line_count = int(self.console.index("end-1c").split(".")[0])
        if line_count > buf:
            self.console.delete("1.0", f"{line_count - buf}.0")
        self.console.see("end")
        self.console.config(state="disabled")

    def refresh_steps_tree(self, *_):
        if not hasattr(self, "steps_tree"):
            return
        self.steps_tree.delete(*self.steps_tree.get_children())
        if not self.selected_macro:
            return
        needle = self._step_filter_var.get().strip().lower()
        for i, step in enumerate(self.macros[self.selected_macro].get("steps", [])):
            pos = step.get("pos", ("-", "-"))
            if isinstance(pos, (tuple, list)) and len(pos) == 2:
                x_s, y_s = str(pos[0]), str(pos[1])
            else:
                x_s = y_s = "-"
            row = (str(i + 1), step["type"], x_s, y_s,
                   str(step.get("key", "")), str(step.get("delay", "")),
                   str(step.get("duration", step.get("message", ""))))
            if needle and not any(needle in cell.lower() for cell in row):
                continue
            self.steps_tree.insert("", "end", iid=str(i), values=row)

    def get_selected_step_index(self):
        sel = self.steps_tree.selection()
        return int(sel[0]) if sel else None

    def delete_selected_step(self):
        if not self.selected_macro:
            return
        idx = self.get_selected_step_index()
        if idx is None:
            return
        steps = self.macros[self.selected_macro]["steps"]
        if 0 <= idx < len(steps):
            deleted = steps.pop(idx)
            self.save_macros()
            self.refresh_steps_tree()
            self.log(f"deleted step {idx + 1} ({deleted['type']})", "WARN")

    def move_step(self, delta):
        idx = self.get_selected_step_index()
        if idx is None or not self.selected_macro:
            return
        steps = self.macros[self.selected_macro]["steps"]
        new_idx = idx + delta
        if 0 <= new_idx < len(steps):
            steps[idx], steps[new_idx] = steps[new_idx], steps[idx]
            self.save_macros()
            self.refresh_steps_tree()
            self.steps_tree.selection_set(str(new_idx))

    def edit_msg(self):
        idx = self.get_selected_step_index()
        if idx is None or not self.selected_macro:
            return
        step = self.macros[self.selected_macro]["steps"][idx]
        if step["type"] != "log":
            return
        msg = simpledialog.askstring("Edit Log Message", "Message:",
                                     initialvalue=step.get("message", ""))
        if msg is not None:
            step["message"] = msg
            self.save_macros()
            self.refresh_steps_tree()
            self.log(f"log step {idx + 1} edited", "SETTINGS")

    def add_log_line(self):
        if not self.selected_macro:
            self.update_status("Select a macro first", "red")
            return
        msg = self.log_text_entry.get().strip()
        if not msg:
            msg = simpledialog.askstring("Log Line", "Message to print during execution:")
            msg = msg.strip() if msg else ""
        if msg:
            self.macros[self.selected_macro]["steps"].append({"type": "log", "message": msg})
            self.save_macros()
            self.refresh_steps_tree()
            self.log(f'added log step "{msg}"', "MACRO")
            self.log_text_entry.delete(0, tk.END)

    def toggle_loop(self):
        if not self.selected_macro:
            return
        cur = self.macros[self.selected_macro].get("settings", {}).get("loop", True)
        self.macros[self.selected_macro]["settings"]["loop"] = not cur
        self.save_macros()
        self.refresh_listbox()
        self.log(f"loop -> {not cur}", "SETTINGS")

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in self.macros.keys():
            loop_str = "[LOOP]" if self.macros[name].get("settings", {}).get("loop", True) else "[ONCE]"
            self.listbox.insert(tk.END, f"{loop_str} {name}")
        if hasattr(self, "hk_macro_menu"):
            self.refresh_hotkey_macro_menu()

    def select_macro_from_list(self):
        selection = self.listbox.curselection()
        if not selection:
            self.update_status("Highlight a macro in the list first", "red")
            return
        raw_name = self.listbox.get(selection[0])
        name = raw_name.split(" ", 1)[1] if raw_name.startswith("[") else raw_name
        self.selected_macro = name
        self.update_status(f"Selected: {name}", "black")
        self.refresh_steps_tree()
        self.log(f"selected '{name}'", "MACRO")

    def record_step(self, action_type):
        if not self.selected_macro:
            self.update_status("Select a macro first", "red")
            return
        x, y = get_real_mouse_pos()
        try:
            delay = float(self.delay_entry.get())
        except ValueError:
            delay = 0.5
        step = {"type": action_type, "pos": [x, y], "delay": delay}
        if action_type == "hold_key":
            k = self.key_entry.get().lower().strip()
            try:
                d = float(self.dur_entry.get())
            except ValueError:
                d = 1.0
            step["key"] = k if k else "w"
            step["duration"] = d
        self.macros[self.selected_macro]["steps"].append(step)
        self.save_macros()
        self.root.after(0, self.refresh_steps_tree)
        self.log(f"recorded {action_type} @ ({x},{y}) delay={delay}s", "MACRO")

    def start(self):
        if not self.running and self.selected_macro:
            self.running = True
            self.root.after(0, self.update_status, f"RUNNING: {self.selected_macro}", "green")
            self.log(f"starting '{self.selected_macro}'", "MACRO")
            threading.Thread(target=self.loop_logic, daemon=True).start()

    def stop(self):
        if self.running:
            self.log("macro stopped", "WARN")
        self.running = False
        self.root.after(0, self.update_status, "Status: Stopped", "red")

    def loop_logic(self):
        try:
            macro_data = self.macros.get(self.selected_macro, {})
            should_loop = macro_data.get("settings", {}).get("loop", True)
            steps = list(macro_data.get("steps", []))
            total = len(steps)
            while self.running:
                for i, step in enumerate(steps):
                    if not self.running:
                        break
                    target = pydirectinput if pydirect_available else pyautogui
                    stype = step["type"]
                    at_cursor = bool(self.click_at_cursor_var.get())
                    if stype in ("left_click", "right_click"):
                        button = 'right' if stype == "right_click" else 'left'
                        if at_cursor:
                            target.click(button=button)
                        else:
                            target.click(step["pos"][0], step["pos"][1], button=button)
                    elif stype == "hold_key":
                        target.keyDown(step["key"])
                        time.sleep(step["duration"])
                        target.keyUp(step["key"])
                    elif stype == "log":
                        self.root.after(0, self.log, step.get("message", ""), "MACRO")
                        continue
                    self.root.after(0, self.log, f"step {i + 1}/{total} -> {stype}", "STEP")
                    base_delay = max(0.01, step.get("delay", 0.5))
                    if self.use_random_sleep.get():
                        time.sleep(max(0.001, base_delay + random.uniform(-0.02, 0.02)))
                    else:
                        time.sleep(base_delay)
                if not should_loop:
                    break
                time.sleep(0.5)
            self.root.after(0, self.stop)
        except Exception as e:
            self._safe_after(self.log, f"crashed: {e}", "ERROR")
            self._safe_after(self.stop)

    def add_new_macro(self):
        name = simpledialog.askstring("New Macro", "Enter macro name:")
        if name:
            if name in self.macros:
                messagebox.showwarning("Exists", f"A macro named '{name}' already exists.")
                return
            do_loop = messagebox.askyesno("Looping", "Loop continuously?")
            self.macros[name] = {"settings": {"loop": do_loop}, "steps": []}
            self.save_macros()
            self.refresh_listbox()
            self.log(f"created macro '{name}'", "SETTINGS")

    def delete_macro(self):
        if self.selected_macro:
            name = self.selected_macro
            del self.macros[name]
            self.selected_macro = None
            self.save_macros()
            self.refresh_listbox()
            self.refresh_steps_tree()
            for combo, macro in list(self.hotkey_bindings.items()):
                if macro == name:
                    self._unregister_hotkey(combo)
                    self.hotkey_bindings.pop(combo, None)
            self.refresh_hotkey_listbox()
            self.log(f"deleted macro '{name}'", "WARN")

    def setup_math_ui(self):
        self.label(self.math_tab, "Secure Calculator", font=("Arial", 14, "bold"),
                   bg_role="bg").pack(pady=15)
        calc_container = self.frame(self.math_tab, role="bg")
        calc_container.pack(pady=10)
        self.calc_display = self.entry(calc_container, font=("Consolas", 20),
                                       borderwidth=5, relief="flat", justify='right')
        self.calc_display.grid(row=0, column=0, columnspan=5, pady=10, ipady=10, padx=10)
        buttons = ['sqrt', '^', '(', ')', 'CE', '7', '8', '9', '/', 'C', '4', '5', '6', '*', '=',
                   '1', '2', '3', '-', '+', '0', '.']
        row_val, col_val = 1, 0
        for btn_text in buttons:
            if btn_text == '=':
                btn_bg = self.C["calc_eq"]
                role = "calc_eq"
            elif btn_text in ['C', 'CE']:
                btn_bg = self.C["calc_eq"]
                role = "calc_eq"
            elif btn_text in ['sqrt', '^', '(', ')']:
                btn_bg = self.C["calc_fn"]
                role = "calc_fn"
            else:
                btn_bg = self.C["calc_num"]
                role = "calc_num"
            b = tk.Button(calc_container, text=btn_text, width=5, height=2,
                          font=("Arial", 11, "bold"), bg=btn_bg,
                          command=lambda x=btn_text: self.on_calc_click(x))
            b.grid(row=row_val, column=col_val, padx=3, pady=3)
            self.track(b, {"bg": role})
            col_val += 1
            if col_val > 4:
                col_val = 0
                row_val += 1

    def secure_eval(self, expr):
        operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
                     ast.Pow: op.pow, ast.USub: op.neg}
        def eval_(node):
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](eval_(node.left), eval_(node.right))
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](eval_(node.operand))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'sqrt':
                return math.sqrt(eval_(node.args[0]))
            raise TypeError(f"Unsupported: {type(node)}")
        return eval_(ast.parse(expr.replace('^', '**'), mode='eval').body)

    def on_calc_click(self, char):
        current_text = self.calc_display.get()
        if char == '=':
            if current_text.strip() == "DEVMENU":
                if not self.dev_unlocked:
                    self.dev_unlocked = True
                    self.btn_settings.pack(fill="x", pady=5)
                    messagebox.showinfo("Unlocked", "Developer Settings Unlocked!!!1!")
                self.calc_display.delete(0, tk.END)
                return
            try:
                if self.use_dangerous_eval.get():
                    expr = current_text.replace('^', '**').replace('sqrt', 'math.sqrt')
                    result = str(eval(expr, {"math": math, "__builtins__": None}))
                else:
                    result = str(self.secure_eval(current_text))
                self.calc_display.delete(0, tk.END)
                self.calc_display.insert(0, result)
            except Exception:
                messagebox.showerror("Error", "Invalid Expression")
                self.calc_display.delete(0, tk.END)
        elif char == 'CE':
            self.calc_display.delete(0, tk.END)
        elif char == 'C':
            self.calc_display.delete(len(current_text) - 1, tk.END)
        elif char == 'sqrt':
            self.calc_display.insert(tk.END, "sqrt(")
        else:
            self.calc_display.insert(tk.END, char)

    def setup_settings_ui(self):
        self.label(self.settings_tab, "Application Settings", font=("Arial", 14, "bold"),
                   bg_role="bg").pack(pady=15)
        console_frame = self.labelframe(self.settings_tab, " Console Settings ", padx=10, pady=10)
        console_frame.pack(fill="x", padx=20, pady=5)
        buffer_row = self.frame(console_frame, role="bg")
        buffer_row.pack(anchor="w")
        self.label(buffer_row, "Console Buffer (lines):", bg_role="bg").pack(side="left")
        tk.Spinbox(buffer_row, from_=10, to=1000, increment=10,
                   textvariable=self.console_buffer_var, width=6,
                   font=("Consolas", 10)).pack(side="left", padx=5)

        self.label(self.settings_tab, "Developer Settings", font=("Arial", 14, "bold"),
                   bg_role="bg").pack(pady=15)
        warn_frame = tk.Frame(self.settings_tab, bg=self.C["warn_bg"], padx=10, pady=10,
                              highlightbackground=self.C["warn_border"], highlightthickness=1)
        self.track(warn_frame, {"bg": "warn_bg", "highlightbackground": "warn_border"})
        warn_frame.pack(fill="x", padx=20, pady=10)
        self.label(warn_frame, "CAUTION: Advanced features can be dangerous.",
                   bg_role="warn_bg", fg_role="warn_fg",
                   font=("Arial", 10, "bold")).pack()
        for text, var, pady in [
            ("Use Default Eval(), DANGEROUS", self.use_dangerous_eval, (20, 5)),
            ("Enable Random Sleep Variance (+/- 0.02s)", self.use_random_sleep, (5, 20)),
        ]:
            cb = tk.Checkbutton(self.settings_tab, text=text, variable=var,
                                bg=self.C["bg"], fg=self.C["text"],
                                selectcolor=self.C["entry_bg"], font=("Arial", 11))
            self.track(cb, {"bg": "bg", "fg": "text"})
            cb.pack(pady=pady, padx=20, anchor="w")

    def on_close(self):
        self.running = False
        self.ac_running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    HelioMacro().root.mainloop()
