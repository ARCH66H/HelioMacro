import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
import time
import pyautogui
import keyboard
import ctypes
import json
import os
import sys
import random

# Attempt to auto-install pydirectinput
try:
    import pydirectinput
    pydirect_available = True
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pydirectinput", "-q"])
        import pydirectinput
        pydirect_available = True
    except:
        pydirect_available = False

# DPI Awareness for crisp UI and pixel-perfect clicks
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class HelioMacro:
    def __init__(self):
        self.running = False
        self.filename = "macros.json"
        self.macros = self.load_macros()
        self.selected_macro = None

        self.root = tk.Tk()
        self.root.title("HelioMacro V0.1")
        self.root.geometry("450x600") # Increased height so the list stays visible
        self.root.configure(bg="#BCCECB")

        # --- STATUS ---
        self.status_label = tk.Label(self.root, text="Status: Idle", bg="#BCCECB", font=("Arial", 11, "bold"))
        self.status_label.pack(pady=10)

        # --- MACRO LIST (THE MISSING LIST) ---
        list_frame = tk.LabelFrame(self.root, text=" Saved Macros ", bg="#BCCECB", padx=10, pady=10)
        list_frame.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, height=5, font=("Consolas", 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        self.refresh_listbox()
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # --- MACRO MGMT BUTTONS ---
        mgmt_frame = tk.Frame(self.root, bg="#BCCECB")
        mgmt_frame.pack(pady=5)
        tk.Button(mgmt_frame, text="New Macro", width=12, command=self.add_new_macro).grid(row=0, column=0, padx=5)
        tk.Button(mgmt_frame, text="Delete Macro", width=12, command=self.delete_macro).grid(row=0, column=1, padx=5)

        # --- RECORDING INPUTS ---
        rec_frame = tk.LabelFrame(self.root, text=" Recording Controls ", bg="#BCCECB", padx=10, pady=10)
        rec_frame.pack(pady=10, padx=20, fill=tk.X)

        # Click Buttons
        click_btn_frame = tk.Frame(rec_frame, bg="#BCCECB")
        click_btn_frame.pack()
        tk.Button(click_btn_frame, text="Add L-Click (F8)", command=lambda: self.record_step("left_click")).grid(row=0, column=0, padx=5)
        tk.Button(click_btn_frame, text="Add R-Click (F9)", command=lambda: self.record_step("right_click")).grid(row=0, column=1, padx=5)

        # Hold Key Inputs
        hold_frame = tk.Frame(rec_frame, bg="#BCCECB")
        hold_frame.pack(pady=10)
        
        tk.Label(hold_frame, text="Key:", bg="#BCCECB").grid(row=0, column=0)
        self.key_entry = tk.Entry(hold_frame, width=5)
        self.key_entry.insert(0, "w")
        self.key_entry.grid(row=0, column=1, padx=2)

        tk.Label(hold_frame, text="Sec:", bg="#BCCECB").grid(row=0, column=2, padx=(5,0))
        self.dur_entry = tk.Entry(hold_frame, width=5)
        self.dur_entry.insert(0, "1.0")
        self.dur_entry.grid(row=0, column=3, padx=2)

        tk.Button(hold_frame, text="Add Hold (F10)", command=lambda: self.record_step("hold_key")).grid(row=0, column=4, padx=5)

        # --- EXECUTION ---
        self.start_btn = tk.Button(self.root, text="START BOT (F6)", bg="#A8E6CF", font=("Arial", 10, "bold"), height=2, command=self.start)
        self.start_btn.pack(fill=tk.X, padx=40, pady=5)

        tk.Button(self.root, text="STOP BOT (F7)", bg="#FF8B94", font=("Arial", 10, "bold"), command=self.stop).pack(fill=tk.X, padx=40, pady=5)

        # --- HOTKEYS ---
        keyboard.add_hotkey('f6', self.start)
        keyboard.add_hotkey('f7', self.stop)
        keyboard.add_hotkey('f8', lambda: self.record_step("left_click"))
        keyboard.add_hotkey('f9', lambda: self.record_step("right_click"))
        keyboard.add_hotkey('f10', lambda: self.record_step("hold_key"))

    def load_macros(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_macros(self):
        with open(self.filename, 'w') as f:
            json.dump(self.macros, f, indent=4)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in self.macros.keys():
            self.listbox.insert(tk.END, name)

    def on_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            self.selected_macro = self.listbox.get(selection[0])
            self.status_label.config(text=f"Selected: {self.selected_macro}", fg="black")

    def add_new_macro(self):
        name = simpledialog.askstring("New Macro", "Enter macro name:")
        if name:
            self.macros[name] = []
            self.save_macros()
            self.refresh_listbox()

    def record_step(self, action_type):
        if not self.selected_macro:
            messagebox.showwarning("Warning", "Select a macro first!")
            return
        
        x, y = pyautogui.position()
        step = {"type": action_type, "pos": (x, y), "delay": 0.5}
        
        if action_type == "hold_key":
            key_to_hold = self.key_entry.get().lower().strip()
            try:
                duration = float(self.dur_entry.get())
            except ValueError:
                messagebox.showerror("Error", "Duration must be a number!")
                return
            step["key"] = key_to_hold if key_to_hold else "w"
            step["duration"] = duration
            
        self.macros[self.selected_macro].append(step)
        self.save_macros()
        print(f"Recorded {action_type} for {self.selected_macro}")

    def loop(self):
        try:
            for i in range(3, 0, -1):
                if not self.running: return
                self.status_label.config(text=f"Starting in {i}s...", fg="blue")
                time.sleep(1)

            while self.running:
                steps = self.macros.get(self.selected_macro, [])
                for step in steps:
                    if not self.running: break
                    
                    action = step["type"]
                    wait = step.get("delay", 0.5) + random.uniform(-0.03, 0.03)

                    if action == "left_click":
                        if pydirect_available: pydirectinput.click(step["pos"][0], step["pos"][1])
                        else: pyautogui.click(step["pos"])
                    
                    elif action == "right_click":
                        if pydirect_available: pydirectinput.click(step["pos"][0], step["pos"][1], button='right')
                        else: pyautogui.rightClick(step["pos"])

                    elif action == "hold_key":
                        k = step.get("key", "w")
                        dur = step.get("duration", 1.0)
                        if pydirect_available:
                            pydirectinput.keyDown(k)
                            time.sleep(dur)
                            pydirectinput.keyUp(k)
                        else:
                            pyautogui.keyDown(k)
                            time.sleep(dur)
                            pyautogui.keyUp(k)
                
                    time.sleep(max(0.05, wait))
                time.sleep(0.5) 
        except Exception as e:
            print(f"Error: {e}")
            self.root.after(0, self.stop)

    def delete_macro(self):
        if self.selected_macro:
            del self.macros[self.selected_macro]
            self.selected_macro = None
            self.save_macros()
            self.refresh_listbox()

    def start(self):
        if not self.running and self.selected_macro:
            self.running = True
            self.status_label.config(text=f"RUNNING: {self.selected_macro}", fg="green")
            threading.Thread(target=self.loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.status_label.config(text="Status: Stopped", fg="red")

if __name__ == "__main__":
    HelioMacro().root.mainloop()