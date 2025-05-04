import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import os
import time

SETTINGS_FILE = "serial_settings.json"
FONT = ("Courier", 10)
THEME = {
    "bg": "#1a1a2e",
    "fg": "#e0b3ff",
    "entry_bg": "#2e2e48",
    "entry_fg": "#ffffff",
    "text_bg": "#14142b",
    "text_fg": "#c3c3ff"
}

class SerialMonitor:
    def __init__(self, master):
        self.master = master
        self.master.title("Multi Serial Monitor")

        self.serials = []
        self.threads = []
        self.settings = self.load_settings()

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=True, fill="both")

        self.frames, self.text_areas = [], []
        self.port_vars, self.baud_vars = [], []
        self.connected_vars, self.hex_view_vars = [], []
        self.command_entries, self.connect_buttons = [], []

        num_tabs = self.settings.get("tab_count", 3)
        for i in range(num_tabs):
            self.add_tab(i)

        self.btn_frame = tk.Frame(master, bg=THEME["bg"])
        self.btn_frame.pack(fill="x", pady=4)

        tk.Button(self.btn_frame, text="Connect All", command=self.connect_all).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="Disconnect All", command=self.disconnect_all).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame, text="+ Add Tab", command=self.add_tab).pack(side=tk.RIGHT, padx=5)
        tk.Button(self.btn_frame, text="× Close Tab", command=self.close_current_tab).pack(side=tk.RIGHT, padx=5)

        self.set_dark_theme(master)

    def set_dark_theme(self, widget):
        widget.configure(bg=THEME["bg"])
        for child in widget.winfo_children():
            cls = child.__class__.__name__
            if cls in ("Frame", "LabelFrame"):
                self.set_dark_theme(child)
            elif cls == "Label":
                child.configure(bg=THEME["bg"], fg=THEME["fg"], font=FONT)
            elif cls == "Entry":
                child.configure(bg=THEME["entry_bg"], fg=THEME["entry_fg"], insertbackground=THEME["entry_fg"], font=FONT)
            elif cls == "Text":
                child.configure(bg=THEME["text_bg"], fg=THEME["text_fg"], insertbackground=THEME["entry_fg"], font=FONT)
            elif cls == "Checkbutton":
                child.configure(bg=THEME["bg"], fg=THEME["fg"], font=FONT, activebackground=THEME["bg"])
            elif cls == "Button":
                child.configure(bg="#351c75", fg="#ffffff", font=FONT, activebackground="#2f1c4e", relief=tk.RAISED)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_settings(self):
        self.settings["tab_count"] = len(self.frames)
        for i in range(len(self.frames)):
            self.settings[f"port{i}"] = self.port_vars[i].get()
            self.settings[f"baud{i}"] = self.baud_vars[i].get()
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f)

    def add_tab(self, index=None):
        i = len(self.frames) if index is None else index

        frame = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(frame, text=f"Device {i+1}")
        self.frames.append(frame)

        top = tk.Frame(frame, bg=THEME["bg"])
        top.pack(fill="x")

        port_var = tk.StringVar(value=self.settings.get(f"port{i}", "COM1"))
        baud_var = tk.StringVar(value=self.settings.get(f"baud{i}", "9600"))
        connected_var = tk.BooleanVar(value=False)
        hex_view_var = tk.BooleanVar(value=False)

        self.port_vars.append(port_var)
        self.baud_vars.append(baud_var)
        self.connected_vars.append(connected_var)
        self.hex_view_vars.append(hex_view_var)

        tk.Label(top, text="Port:").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=port_var, width=10).pack(side=tk.LEFT)
        tk.Label(top, text="Baud:").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=baud_var, width=10).pack(side=tk.LEFT)

        tk.Checkbutton(top, text="Connected", variable=connected_var, state=tk.DISABLED).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(top, text="Hex View", variable=hex_view_var).pack(side=tk.LEFT, padx=10)

        connect_btn = tk.Button(top, text="Connect", command=lambda idx=i: self.toggle_connection(idx))
        connect_btn.pack(side=tk.LEFT, padx=5)
        self.connect_buttons.append(connect_btn)

        text_area = tk.Text(frame, wrap=tk.WORD)
        text_area.pack(expand=True, fill="both", pady=2)
        self.text_areas.append(text_area)

        send_frame = tk.Frame(frame, bg=THEME["bg"])
        send_frame.pack(fill="x", pady=2)

        cmd_entry = tk.Entry(send_frame)
        cmd_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(2, 0))
        self.command_entries.append(cmd_entry)

        tk.Button(send_frame, text="Send", command=lambda idx=i: self.send_command(idx)).pack(side=tk.LEFT, padx=5)

        self.serials.append(None)
        self.threads.append(None)

        self.set_dark_theme(frame)

    def toggle_connection(self, idx):
        if self.serials[idx] and self.serials[idx].is_open:
            self.disconnect(idx)
            self.connect_buttons[idx].config(text="Connect")
        else:
            self.connect(idx)
            self.connect_buttons[idx].config(text="Disconnect")

    def close_current_tab(self):
        idx = self.notebook.index(self.notebook.select())
        self.disconnect(idx)
        self.notebook.forget(idx)
        for lst in [self.frames, self.text_areas, self.port_vars, self.baud_vars,
                    self.connected_vars, self.hex_view_vars, self.command_entries,
                    self.connect_buttons, self.serials, self.threads]:
            del lst[idx]
        self.save_settings()

    def connect_all(self):
        self.save_settings()
        for i in range(len(self.frames)):
            self.connect(i)
            self.connect_buttons[i].config(text="Disconnect")

    def disconnect_all(self):
        for i in range(len(self.frames)):
            self.disconnect(i)
            self.connect_buttons[i].config(text="Connect")

    def connect(self, i):
        try:
            port = self.port_vars[i].get()
            baud = int(self.baud_vars[i].get())
            ser = serial.Serial(port, baud, timeout=0)
            self.serials[i] = ser
            self.connected_vars[i].set(True)
            self.threads[i] = threading.Thread(target=self.read_serial, args=(i,), daemon=True)
            self.threads[i].start()
        except Exception as e:
            messagebox.showerror("Error", f"Device {i+1}: {e}")

    def disconnect(self, i):
        if self.serials[i] and self.serials[i].is_open:
            self.serials[i].close()
        self.serials[i] = None
        self.connected_vars[i].set(False)

    def read_serial(self, idx):
        ser = self.serials[idx]
        while ser and ser.is_open:
            try:
                data = ser.read(ser.in_waiting or 1)
                if data:
                    if self.hex_view_vars[idx].get():
                        line = " ".join(f"{b:02X}" for b in data)
                    else:
                        line = data.decode(errors='ignore').strip()
                    self.master.after(0, self.safe_insert, idx, line + "\n")
                else:
                    time.sleep(0.01)
            except Exception:
                break

    def safe_insert(self, idx, text):
        self.text_areas[idx].insert(tk.END, text)
        self.text_areas[idx].see(tk.END)

    def send_command(self, idx):
        ser = self.serials[idx]
        if ser and ser.is_open:
            msg = self.command_entries[idx].get()
            try:
                ser.write(msg.encode())
                self.command_entries[idx].delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send: {e}")

    def on_close(self):
        self.disconnect_all()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
