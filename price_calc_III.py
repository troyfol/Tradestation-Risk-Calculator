import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import json
import os
import threading
import time
import re
import sys  # Required for the .exe to find files
import copy

# --- AUTOMATION SETUP ---
try:
    import pytesseract
    from PIL import ImageGrab, ImageOps, ImageEnhance, Image
    from pynput import mouse
    
    # DETERMINE TESSERACT PATH
    # If running as a bundled .exe (Frozen), look in the temp folder (_MEIPASS).
    # If running as a script, look in Program Files.
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        TESSERACT_PATH = os.path.join(base_path, 'Tesseract-OCR', 'tesseract.exe')
    else:
        TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        AUTOMATION_AVAILABLE = True
    else:
        AUTOMATION_AVAILABLE = False
        print(f"Warning: Tesseract not found at {TESSERACT_PATH}")

except ImportError:
    AUTOMATION_AVAILABLE = False

# Resolve config path relative to the .exe or script location, not CWD
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_APP_DIR, "window_config.json")

# --- COLOR PALETTE ---
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
ENTRY_BG = "#333333"
ENTRY_FG = "#ffffff"
ACCENT_COLOR = "#4a4a4a"
HIGHLIGHT = "#007acc"

class TradeSolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Trade Solver")
        self.root.attributes('-topmost', True)
        self.root.configure(bg=BG_COLOR)

        self.vars = {
            "Entry": tk.StringVar(),
            "Stop": tk.StringVar(),
            "Risk $": tk.StringVar(),
            "Shares": tk.StringVar(),
            "Cost": tk.StringVar()
        }
        self.direction_var = tk.StringVar(value="Long")
        self.smart_click_enabled = tk.BooleanVar(value=False)
        
        # LOGIC TOGGLE: True = Next Click is Entry; False = Next Click is Stop
        self.entry_turn = True
        self._ocr_lock = threading.Lock()  # Prevents overlapping OCR clicks
        self._ocr_thread = None
        self._closing = False

        # LFA (Long First Arrival): use longer OCR delay after window switch
        self.lfa_enabled = tk.BooleanVar(value=True)
        self._app_lost_focus = False

        # Settings (overwritten by load_config if saved values exist)
        self._DEFAULT_SETTINGS = {
            "normal_delay": 0.1,
            "lfa_delay": 0.5,
            "ocr_left": 20,
            "ocr_above": 400,
            "ocr_right": 300,
            "ocr_below": 20,
            "targets": [
                {"r_multiple": 1.0, "color": "#69db7c"},
                {"r_multiple": 2.0, "color": "#69db7c"},
                {"r_multiple": 3.0, "color": "#69db7c"},
            ]
        }
        self.settings = copy.deepcopy(self._DEFAULT_SETTINGS)

        # Load Config
        self.load_config()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- STYLING ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=BG_COLOR)
        self.style.configure("TLabelframe", background=BG_COLOR, foreground=FG_COLOR, bordercolor=ACCENT_COLOR)
        self.style.configure("TLabelframe.Label", background=BG_COLOR, foreground=FG_COLOR)
        self.style.configure("TButton", background=ACCENT_COLOR, foreground=FG_COLOR, borderwidth=1)
        self.style.map("TButton", background=[("active", HIGHLIGHT)])
        self.style.configure("TRadiobutton", background=BG_COLOR, foreground=FG_COLOR, indicatorcolor=ENTRY_BG)
        self.style.map("TRadiobutton", indicatorcolor=[("selected", HIGHLIGHT)], background=[("active", BG_COLOR)])
        self.style.configure("TCheckbutton", background=BG_COLOR, foreground=FG_COLOR)
        self.style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=ENTRY_FG, bordercolor=ACCENT_COLOR)
        self.style.configure("Treeview", background=BG_COLOR, foreground=FG_COLOR, fieldbackground=BG_COLOR, borderwidth=0)
        self.style.configure("Treeview.Heading", background=ACCENT_COLOR, foreground=FG_COLOR, relief="flat")
        self.style.map("Treeview", background=[("selected", HIGHLIGHT)])

        self.apply_font_sizing() 

        # --- GUI LAYOUT ---
        
        # Top Frame: Direction + Smart Click
        top_frame = ttk.Frame(root)
        top_frame.pack(fill="x", padx=15, pady=(10, 0))

        # Direction Radio Buttons
        r_long = ttk.Radiobutton(top_frame, text="Long", variable=self.direction_var, value="Long", command=self.calculate)
        r_short = ttk.Radiobutton(top_frame, text="Short", variable=self.direction_var, value="Short", command=self.calculate)
        r_long.pack(side="left", padx=(0, 10))
        r_short.pack(side="left")

        # Smart Click + LFA Checkboxes
        if AUTOMATION_AVAILABLE:
            chk_lfa = ttk.Checkbutton(top_frame, text="LFA", variable=self.lfa_enabled)
            chk_lfa.pack(side="right", padx=(0, 5))
            chk_smart = ttk.Checkbutton(top_frame, text="Smart Click", variable=self.smart_click_enabled, command=self.toggle_listener)
            chk_smart.pack(side="right")
            # Track when calculator loses focus (user switched to TradeStation)
            self.root.bind("<FocusOut>", self._on_focus_out)
        else:
            lbl_err = ttk.Label(top_frame, text="(Tesseract Not Found)", foreground="#888")
            lbl_err.pack(side="right")

        # Input Frame
        input_frame = ttk.LabelFrame(root, text=" Trade Inputs ", padding="10")
        input_frame.pack(fill="x", padx=10, pady=5)

        row = 0
        standard_inputs = ["Entry", "Stop", "Risk $"]
        for label in standard_inputs:
            ttk.Label(input_frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            entry = ttk.Entry(input_frame, textvariable=self.vars[label], width=15)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
            entry.bind('<Return>', self.calculate)
            row += 1

        ttk.Label(input_frame, text="Shares").grid(row=row, column=0, sticky="w", pady=5)
        shares_entry = ttk.Entry(input_frame, textvariable=self.vars["Shares"], width=15)
        shares_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        shares_entry.bind('<Return>', self.calculate)

        ttk.Label(input_frame, text="Cost").grid(row=row, column=2, sticky="w", pady=5, padx=(10,5))
        cost_entry = ttk.Entry(input_frame, textvariable=self.vars["Cost"], width=12)
        cost_entry.grid(row=row, column=3, padx=5, pady=5, sticky="w")
        cost_entry.bind('<Return>', self.calculate)

        # Buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=5)
        
        calc_btn = ttk.Button(btn_frame, text="Calculate", command=self.calculate)
        calc_btn.pack(side="left", padx=5)
        
        clear_btn = ttk.Button(btn_frame, text="Clear", command=self.clear_inputs)
        clear_btn.pack(side="left", padx=5)

        sep = ttk.Label(btn_frame, text="|")
        sep.pack(side="left", padx=5)
        
        btn_minus = ttk.Button(btn_frame, text="-", width=3, command=lambda: self.change_font_size(-1))
        btn_minus.pack(side="left", padx=2)
        
        btn_plus = ttk.Button(btn_frame, text="+", width=3, command=lambda: self.change_font_size(1))
        btn_plus.pack(side="left", padx=2)

        sep2 = ttk.Label(btn_frame, text="|")
        sep2.pack(side="left", padx=5)

        settings_btn = ttk.Button(btn_frame, text="Settings", command=self.open_settings)
        settings_btn.pack(side="left", padx=5)

        # Output Table
        self.tree = ttk.Treeview(root, columns=("Level", "Price", "PnL"), show="headings", height=6)
        self.tree.heading("Level", text="Level")
        self.tree.heading("Price", text="Price")
        self.tree.heading("PnL", text="P/L ($)")
        
        self.tree.column("Level", width=80, anchor="center")
        self.tree.column("Price", width=80, anchor="center")
        self.tree.column("PnL", width=80, anchor="center")
        
        self.tree.pack(padx=10, pady=10, fill="both", expand=True)

        self.tree.tag_configure('stop', foreground='#ff6b6b')
        self.tree.tag_configure('entry', foreground='#4dabf7')
        self._apply_target_tags()

        # Status bar for user feedback
        self.status_label = ttk.Label(root, text="", foreground="#888888", background=BG_COLOR)
        self.status_label.pack(padx=10, pady=(0, 5))
        self._status_after_id = None

        # Start the listener thread if available
        self.listener = None
        if AUTOMATION_AVAILABLE:
            self.start_listener()

    # --- AUTOMATION LOGIC ---
    def start_listener(self):
        self.listener = mouse.Listener(on_click=self.on_click)
        self.listener.start()

    def toggle_listener(self):
        """Listener runs continuously; on_click checks smart_click_enabled.
        Restarting pynput listeners repeatedly can cause resource leaks on Windows."""
        pass

    def _on_focus_out(self, event):
        """Fires when the calculator window loses focus (user clicked to TradeStation)."""
        self._app_lost_focus = True

    def on_click(self, x, y, button, pressed):
        if not pressed or not self.smart_click_enabled.get() or self._closing:
            return
        if not self._ocr_lock.acquire(blocking=False):
            return  # Already processing a previous click

        # INSTANT UI FEEDBACK: Show "..." so the app feels instantly responsive
        self.root.after(0, self.indicate_loading)

        # Run OCR in a separate thread to not block the mouse
        self._ocr_thread = threading.Thread(target=self.process_click, args=(x, y))
        self._ocr_thread.start()

    def indicate_loading(self):
        """Instantly puts a '...' in the box we are about to fill."""
        if self.entry_turn:
            self.vars["Entry"].set("...")
        else:
            self.vars["Stop"].set("...")

    def _get_ocr_delay(self):
        """Determine OCR delay. Use longer delay on first arrival back to TradeStation."""
        if not self.lfa_enabled.get():
            return self.settings["normal_delay"]
        # Basic: both fields empty = cold start of a new trade
        fields_empty = not self.vars["Entry"].get() or self.vars["Entry"].get() == "..."
        fields_empty = fields_empty and (not self.vars["Stop"].get() or self.vars["Stop"].get() == "...")
        # Advanced: calculator just lost focus (user switched to TradeStation)
        if fields_empty or self._app_lost_focus:
            self._app_lost_focus = False
            return self.settings["lfa_delay"]
        return self.settings["normal_delay"]

    def process_click(self, x, y):
        try:
            # 1. DELAY: Adaptive — longer on first click after window switch (LFA)
            delay = self._get_ocr_delay()
            time.sleep(delay)

            # 2. OPTIMIZED BBOX: Clamped to non-negative, configurable via settings
            s = self.settings
            bbox = (max(0, x - s["ocr_left"]), max(0, y - s["ocr_above"]),
                    x + s["ocr_right"], y + s["ocr_below"])

            screen = ImageGrab.grab(bbox=bbox)

            # --- IMAGE PROCESSING ---
            # Order optimized: Grayscale FIRST is faster before resizing
            screen = ImageOps.grayscale(screen)

            width, height = screen.size
            screen = screen.resize((width * 3, height * 3), Image.Resampling.LANCZOS)

            enhancer = ImageEnhance.Contrast(screen)
            screen = enhancer.enhance(2.0)

            enhancer = ImageEnhance.Sharpness(screen)
            screen = enhancer.enhance(2.0)

            # Read Text
            text = pytesseract.image_to_string(screen, config='--psm 6')

            # Regex to find Price
            match = re.search(r'(?:Price|Close|High|Low)[^0-9]*?(\d+\.\d{2,})', text, re.IGNORECASE)

            if not match:
                fallback_matches = re.findall(r'\b(\d+\.\d{2})\b', text)
                if fallback_matches:
                    match = fallback_matches[-1]  # Last number is most likely the price

            if match:
                price = match.group(1) if hasattr(match, 'group') else match
                price_val = float(price)
                if 0.01 <= price_val <= 999999:
                    if not self._closing:
                        self.root.after(0, self.auto_fill_price, price)
                    return
            # If no valid price found, fall through to finally for cleanup

        except Exception as e:
            print(f"OCR error: {e}")
        finally:
            if not self._closing:
                self.root.after(0, self._ensure_unlock)

    def _ensure_unlock(self):
        """Guaranteed cleanup: clear '...' and release OCR lock."""
        if self.vars["Entry"].get() == "...":
            self.vars["Entry"].set("")
        if self.vars["Stop"].get() == "...":
            self.vars["Stop"].set("")
        if self._ocr_lock.locked():
            self._ocr_lock.release()

    def auto_fill_price(self, price):
        # 1. Only clear Shares/Cost on the second click (filling Stop)
        if not self.entry_turn:
            self.vars["Shares"].set("")
            self.vars["Cost"].set("")

        # 2. Alternating Logic
        if self.entry_turn:
            self.vars["Entry"].set(price)
            self.entry_turn = False  # Next click will be STOP
        else:
            self.vars["Stop"].set(price)
            self.entry_turn = True  # Next click will be ENTRY

        # 3. Calculate immediately (auto_infer_direction=True for OCR fills)
        self.calculate(auto_infer_direction=True)
        # Lock is released by _ensure_unlock (scheduled in process_click's finally block)

    # --- SETTINGS LOGIC ---
    def _apply_target_tags(self):
        """Create/update Treeview tags for each target with its configured color."""
        for i, t in enumerate(self.settings["targets"]):
            self.tree.tag_configure(f"target_{i}", foreground=t["color"])
        # Adjust treeview height: STOP + ENTRY + N targets
        self.tree.configure(height=2 + len(self.settings["targets"]))

    def _apply_settings(self):
        """Push current settings into the live app."""
        self._apply_target_tags()
        # Re-render the table if data is present
        try:
            v_entry = self.vars["Entry"].get()
            v_stop = self.vars["Stop"].get()
            v_shares = self.vars["Shares"].get()
            if v_entry and v_stop and v_shares:
                self.update_table(float(v_entry), float(v_stop), float(v_shares))
        except (ValueError, TypeError):
            pass

    def open_settings(self):
        """Open a modal settings window."""
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=BG_COLOR)
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        # Working copy of settings so Cancel discards changes
        working = copy.deepcopy(self.settings)

        # --- OCR Timing ---
        timing_frame = ttk.LabelFrame(win, text=" OCR Timing ", padding="10")
        timing_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(timing_frame, text="Normal Delay (s):").grid(row=0, column=0, sticky="w", pady=3)
        var_normal = tk.StringVar(value=str(working["normal_delay"]))
        ttk.Entry(timing_frame, textvariable=var_normal, width=10).grid(row=0, column=1, padx=5, pady=3)

        ttk.Label(timing_frame, text="LFA Delay (s):").grid(row=1, column=0, sticky="w", pady=3)
        var_lfa = tk.StringVar(value=str(working["lfa_delay"]))
        ttk.Entry(timing_frame, textvariable=var_lfa, width=10).grid(row=1, column=1, padx=5, pady=3)

        # --- OCR Capture Region ---
        region_frame = ttk.LabelFrame(win, text=" OCR Capture Region (px from click) ", padding="10")
        region_frame.pack(fill="x", padx=10, pady=5)

        ocr_vars = {}
        for i, (label, key) in enumerate([("Left:", "ocr_left"), ("Right:", "ocr_right"),
                                           ("Above:", "ocr_above"), ("Below:", "ocr_below")]):
            r, c = divmod(i, 2)
            ttk.Label(region_frame, text=label).grid(row=r, column=c * 2, sticky="w", pady=3)
            v = tk.StringVar(value=str(working[key]))
            ttk.Entry(region_frame, textvariable=v, width=8).grid(row=r, column=c * 2 + 1, padx=5, pady=3)
            ocr_vars[key] = v

        # --- Profit Targets ---
        targets_frame = ttk.LabelFrame(win, text=" Profit Targets ", padding="10")
        targets_frame.pack(fill="x", padx=10, pady=5)

        # Scrollable target rows container
        target_rows_frame = ttk.Frame(targets_frame)
        target_rows_frame.pack(fill="x")

        # Header row
        ttk.Label(target_rows_frame, text="#", width=3).grid(row=0, column=0, pady=2)
        ttk.Label(target_rows_frame, text="R-Multiple", width=10).grid(row=0, column=1, pady=2)
        ttk.Label(target_rows_frame, text="Color", width=10).grid(row=0, column=2, pady=2)

        target_widgets = []  # List of (r_var, color_var, color_btn) per target

        def add_target_row(r_val=1.0, color_val="#69db7c"):
            idx = len(target_widgets)
            if idx >= 10:
                return
            row_num = idx + 1  # Row 0 is header

            ttk.Label(target_rows_frame, text=str(idx + 1), width=3).grid(row=row_num, column=0, pady=2)

            r_var = tk.StringVar(value=str(r_val))
            ttk.Entry(target_rows_frame, textvariable=r_var, width=10).grid(row=row_num, column=1, padx=5, pady=2)

            color_var = tk.StringVar(value=color_val)
            color_btn = tk.Button(target_rows_frame, width=8, bg=color_val, activebackground=color_val,
                                  relief="flat", cursor="hand2")

            def pick_color(cv=color_var, cb=color_btn):
                result = colorchooser.askcolor(color=cv.get(), parent=win, title="Pick Target Color")
                if result and result[1]:
                    cv.set(result[1])
                    cb.configure(bg=result[1], activebackground=result[1])

            color_btn.configure(command=pick_color)
            color_btn.grid(row=row_num, column=2, padx=5, pady=2)

            target_widgets.append((r_var, color_var, color_btn))

        def remove_target_row():
            if len(target_widgets) <= 1:
                return
            target_widgets.pop()
            # Destroy widgets in the last row
            row_num = len(target_widgets) + 1
            for widget in target_rows_frame.grid_slaves(row=row_num):
                widget.destroy()

        # Populate existing targets
        for t in working["targets"]:
            add_target_row(t["r_multiple"], t["color"])

        # Add / Remove buttons
        btn_row = ttk.Frame(targets_frame)
        btn_row.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_row, text="+ Add Target", command=add_target_row).pack(side="left", padx=5)
        ttk.Button(btn_row, text="- Remove Last", command=remove_target_row).pack(side="left", padx=5)

        # --- Save / Cancel ---
        bottom_frame = ttk.Frame(win)
        bottom_frame.pack(pady=10)

        def on_save():
            try:
                new_settings = {
                    "normal_delay": float(var_normal.get()),
                    "lfa_delay": float(var_lfa.get()),
                    "ocr_left": int(float(ocr_vars["ocr_left"].get())),
                    "ocr_above": int(float(ocr_vars["ocr_above"].get())),
                    "ocr_right": int(float(ocr_vars["ocr_right"].get())),
                    "ocr_below": int(float(ocr_vars["ocr_below"].get())),
                    "targets": []
                }
                for r_var, color_var, _ in target_widgets:
                    rm = float(r_var.get())
                    if rm <= 0:
                        messagebox.showwarning("Invalid Target", "R-multiples must be positive.", parent=win)
                        return
                    new_settings["targets"].append({"r_multiple": rm, "color": color_var.get()})

                if new_settings["normal_delay"] <= 0 or new_settings["lfa_delay"] <= 0:
                    messagebox.showwarning("Invalid Delay", "Delays must be positive.", parent=win)
                    return

                self.settings = new_settings
                self._apply_settings()
                win.destroy()
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers.", parent=win)

        ttk.Button(bottom_frame, text="Save", command=on_save).pack(side="left", padx=10)
        ttk.Button(bottom_frame, text="Cancel", command=win.destroy).pack(side="left", padx=10)

        # Center the settings window over the main window
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # --- CALCULATION LOGIC ---
    def apply_font_sizing(self):
        default_font = ("Segoe UI", self.font_size)
        bold_font = ("Segoe UI", self.font_size, "bold")
        self.style.configure(".", font=default_font)
        self.style.configure("Treeview.Heading", font=bold_font)
        self.style.configure("Treeview", rowheight=int(self.font_size * 2.5), font=default_font)

    def change_font_size(self, delta):
        new_size = self.font_size + delta
        if 8 <= new_size <= 24:
            self.font_size = new_size
            self.apply_font_sizing()

    def _show_status(self, msg, duration_ms=3000):
        """Display a transient message in the status bar."""
        if self._status_after_id:
            self.root.after_cancel(self._status_after_id)
        self.status_label.config(text=msg)
        self._status_after_id = self.root.after(duration_ms, lambda: self.status_label.config(text=""))

    def calculate(self, event=None, auto_infer_direction=False):
        try:
            v_entry = self.vars["Entry"].get()
            v_stop = self.vars["Stop"].get()
            v_risk = self.vars["Risk $"].get()
            v_shares = self.vars["Shares"].get()
            v_cost = self.vars["Cost"].get()
            mode = self.direction_var.get()

            def to_num(val):
                if not val or val == "...":
                    return None
                try:
                    return float(val)
                except ValueError:
                    return None

            entry, stop, risk, shares, cost = to_num(v_entry), to_num(v_stop), to_num(v_risk), to_num(v_shares), to_num(v_cost)

            # Check for non-numeric input in non-empty fields
            for label, raw in [("Entry", v_entry), ("Stop", v_stop), ("Risk $", v_risk), ("Shares", v_shares)]:
                if raw and raw != "..." and to_num(raw) is None:
                    self._show_status(f"Invalid input in {label}")
                    return

            # Early exit: Entry and Stop cannot be equal
            if entry and stop and entry == stop:
                self._show_status("Entry and Stop cannot be equal")
                return

            # Scenario: Cost + Entry (No shares yet)
            if entry and cost and not shares and entry != 0:
                shares = int(cost / entry)
                self.vars["Shares"].set(str(shares))

            # Scenario A: Entry + Stop + Risk (Calculate Shares)
            if entry and stop and risk and not shares:
                risk_per_share = abs(entry - stop)
                if risk_per_share > 0:
                    shares = int(risk / risk_per_share)
                    self.vars["Shares"].set(str(shares))

            # Scenario B: Entry + Stop + Shares (Calculate Risk)
            elif entry and stop and shares and not risk:
                risk_per_share = abs(entry - stop)
                risk = risk_per_share * shares
                self.vars["Risk $"].set(f"{risk:.2f}")

            # Scenario C: Entry + Shares + Risk (Calculate Stop)
            elif entry and shares and risk and not stop:
                if shares > 0:
                    risk_per_share = risk / shares
                    stop = entry - risk_per_share if mode == "Long" else entry + risk_per_share
                    self.vars["Stop"].set(f"{stop:.2f}")

            # Final updates for Cost and Table
            if self.vars["Entry"].get() and self.vars["Shares"].get():
                entry = float(self.vars["Entry"].get())
                shares = float(self.vars["Shares"].get())
                self.vars["Cost"].set(f"{entry * shares:.2f}")

            if self.vars["Entry"].get() and self.vars["Stop"].get() and self.vars["Shares"].get():
                entry = float(self.vars["Entry"].get())
                stop = float(self.vars["Stop"].get())
                shares = float(self.vars["Shares"].get())

                # Only auto-infer direction during OCR auto-fill, not manual Calculate
                if auto_infer_direction:
                    if entry > stop:
                        self.direction_var.set("Long")
                    elif entry < stop:
                        self.direction_var.set("Short")

                self.update_table(entry, stop, shares)

        except ValueError:
            self._show_status("Invalid input -- enter numeric values")
        except ZeroDivisionError:
            self._show_status("Entry and Stop cannot be equal")
        except TypeError:
            self._show_status("Unexpected error -- check inputs")

    def update_table(self, entry, stop, shares):
        for i in self.tree.get_children():
            self.tree.delete(i)
        risk_per_share = abs(entry - stop)
        direction = 1 if self.direction_var.get() == "Long" else -1

        # Build levels: STOP + ENTRY + dynamic targets from settings
        levels = [{"r": -1, "label": "STOP", "tag": "stop"},
                  {"r": 0,  "label": "ENTRY", "tag": "entry"}]
        for i, t in enumerate(self.settings["targets"]):
            rm = t["r_multiple"]
            label = f"{rm}R" if rm != int(rm) else f"{int(rm)}R"
            levels.append({"r": rm, "label": f"Target {label}", "tag": f"target_{i}"})

        for lv in levels:
            price = entry + (risk_per_share * lv["r"] * direction)
            pnl = lv["r"] * risk_per_share * shares
            pnl_str = f"+${pnl:.0f}" if pnl > 0 else f"${pnl:.0f}"
            if pnl == 0:
                pnl_str = "$0"
            self.tree.insert("", "end", values=(lv["label"], f"{price:.2f}", pnl_str), tags=(lv["tag"],))

    def clear_inputs(self):
        """Clears trade-specific inputs. Risk $ is intentionally preserved (persistent preference)."""
        self.vars["Entry"].set("")
        self.vars["Stop"].set("")
        self.vars["Shares"].set("")
        self.vars["Cost"].set("")
        self.entry_turn = True
        for i in self.tree.get_children():
            self.tree.delete(i)

    def load_config(self):
        self.font_size = 10
        geometry = "360x550"
        saved_risk = ""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    geometry = data.get("geometry", "360x550")
                    self.font_size = data.get("font_size", 10)
                    saved_risk = data.get("risk_value", "")
                    # Merge saved settings over defaults (forward-compatible)
                    saved_settings = data.get("settings", {})
                    merged = copy.deepcopy(self._DEFAULT_SETTINGS)
                    for key in merged:
                        if key in saved_settings:
                            merged[key] = saved_settings[key]
                    self.settings = merged
            except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
                print(f"Warning: Config reset due to: {e}")
                try:
                    os.remove(CONFIG_FILE)
                except OSError:
                    pass
        self.root.geometry(geometry)
        self.vars["Risk $"].set(saved_risk)

    def on_close(self):
        self._closing = True
        if self._ocr_thread and self._ocr_thread.is_alive():
            self._ocr_thread.join(timeout=1.0)
        if self.listener:
            self.listener.stop()
        
        data = {
            "geometry": self.root.geometry(),
            "font_size": self.font_size,
            "risk_value": self.vars["Risk $"].get(),
            "settings": self.settings
        }
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(data, f)
        except (OSError, TypeError) as e:
            print(f"Warning: Could not save config: {e}")
        self.root.destroy()

if __name__ == "__main__":
    # DPI awareness so pynput coords and ImageGrab coords agree on scaled displays
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass

    root = tk.Tk()
    app = TradeSolverApp(root)
    root.mainloop()