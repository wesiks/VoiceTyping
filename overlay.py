import math
import random
import tkinter as tk
import ctypes

SW_SHOWNOACTIVATE = 4
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

class FloatingOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Transparent background color for Windows
        self.bg_trans = "#000001"
        self.root.attributes("-transparentcolor", self.bg_trans)
        self.root.config(bg=self.bg_trans)
        
        # Dimensions & Compact Pill Geometry
        self.width = 480
        self.height = 50
        self.radius = 25  # Perfect pill
        
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        
        self.pos_x = (self.screen_w - self.width) // 2
        self.target_y = self.screen_h - self.height - 58  # Floats just above Windows taskbar
        self.hidden_y = self.screen_h + 10                # Hidden below monitor edge
        
        self.current_y = self.hidden_y
        self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.hidden_y}")
        
        # Canvas for ultra-smooth anti-aliased graphics
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.bg_trans,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Prevent window from ever stealing active focus
        self._setup_no_activate()
        
        # Animation states
        self._anim_job = None
        self._wave_job = None
        self._hide_timer = None
        self._is_visible = False
        self._state = "idle"  # "recording", "processing", "done"
        
        # Initialize graphical elements
        self._init_graphics()
        
        # Hide initially
        self.root.withdraw()

    def _setup_no_activate(self):
        """Ensures the floating overlay never steals cursor focus."""
        try:
            hwnd = self.root.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE)
        except Exception:
            pass

    def _round_pill_points(self, x1, y1, x2, y2, r):
        """Generates smooth rounded polygon points for a capsule / pill."""
        return (
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1
        )

    def _init_graphics(self):
        """Draws the base pill layers: shadow, outer border, inner glass body, and indicators."""
        w, h, r = self.width, self.height, self.radius
        
        # Outer glow / subtle border
        pts_glow = self._round_pill_points(2, 2, w - 2, h - 2, r)
        self.glow_id = self.canvas.create_polygon(
            pts_glow,
            fill="#18181E",
            outline="#33333F",
            width=1.5,
            smooth=True
        )
        
        # Main inner capsule body (deep luxury matte obsidian)
        pts_body = self._round_pill_points(3, 3, w - 3, h - 3, r - 1)
        self.body_id = self.canvas.create_polygon(
            pts_body,
            fill="#0B0B0F",
            outline="",
            smooth=True
        )
        
        # Specular top highlight line (glass refraction effect)
        self.highlight_id = self.canvas.create_line(
            r + 8, 4, w - r - 8, 4,
            fill="#2A2A38",
            width=1
        )
        
        # Animated voice waveform bars (left indicator)
        self.bars = []
        bar_x = 24
        bar_colors = ["#F43F5E", "#FB7185", "#F43F5E"]
        for i in range(3):
            line = self.canvas.create_line(
                bar_x + (i * 6), 25 - 4,
                bar_x + (i * 6), 25 + 4,
                fill=bar_colors[i],
                width=2.5,
                capstyle="round"
            )
            self.bars.append(line)
        
        # Status icon / glyph (for processing / done states)
        self.badge_id = self.canvas.create_text(
            30, 25,
            text="",
            fill="#38BDF8",
            font=("Segoe UI", 11, "bold"),
            anchor="center"
        )
        
        # Live text label
        self.text_id = self.canvas.create_text(
            52, 25,
            text="Слушаю...",
            fill="#71717A",
            font=("Segoe UI Variable Text", 11, "normal"),
            anchor="w"
        )

    # ------------------ ANIMATIONS ------------------ #

    def _slide_animation(self, from_y, to_y, duration_ms=150, callback=None):
        """Buttery smooth ease-out sliding animation."""
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None

        steps = 14
        step_delay = max(1, duration_ms // steps)
        step_idx = 0

        def _step():
            nonlocal step_idx
            step_idx += 1
            progress = step_idx / steps
            
            # Ease-out cubic: 1 - (1 - t)^3
            ease = 1.0 - math.pow(1.0 - progress, 3)
            current_y = int(from_y + (to_y - from_y) * ease)
            
            self.current_y = current_y
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{current_y}")
            self.root.update_idletasks()

            if step_idx < steps:
                self._anim_job = self.root.after(step_delay, _step)
            else:
                self._anim_job = None
                self.current_y = to_y
                if callback:
                    callback()

        _step()

    def _start_wave_animation(self):
        """Animates dynamic audio bars while user is speaking."""
        if self._wave_job:
            self.root.after_cancel(self._wave_job)

        def _animate():
            if self._state != "recording":
                return
            
            # Random subtle heights simulating real speech amplitude
            h1 = random.randint(4, 11)
            h2 = random.randint(7, 16)
            h3 = random.randint(3, 10)
            heights = [h1, h2, h3]
            
            bar_x = 24
            for i, h in enumerate(heights):
                self.canvas.coords(
                    self.bars[i],
                    bar_x + (i * 6), 25 - h,
                    bar_x + (i * 6), 25 + h
                )
            
            self._wave_job = self.root.after(75, _animate)

        _animate()

    def _stop_wave_animation(self):
        if self._wave_job:
            self.root.after_cancel(self._wave_job)
            self._wave_job = None
        # Reset bars
        bar_x = 24
        for i in range(3):
            self.canvas.coords(self.bars[i], bar_x + (i * 6), 25 - 4, bar_x + (i * 6), 25 + 4)

    # ------------------ PUBLIC UI METHODS ------------------ #

    def show_recording(self):
        """Slides up smoothly from bottom of monitor into view."""
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None

        self._state = "recording"
        
        # Reset styling to recording state (Crimson/Rose Glow)
        self.canvas.itemconfig(self.glow_id, outline="#E11D48", fill="#230A10")
        self.canvas.itemconfig(self.body_id, fill="#0B0B0F")
        self.canvas.itemconfig(self.badge_id, text="")
        for b in self.bars:
            self.canvas.itemconfig(b, state="normal")
        
        self.canvas.itemconfig(self.text_id, text="Слушаю...", fill="#71717A")

        # Make visible at start position if not already
        if not self._is_visible:
            self._is_visible = True
            self.root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.hidden_y}")
            self.root.deiconify()
            try:
                hwnd = self.root.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            except Exception:
                pass

        # Animate smoothly up from monitor bottom edge
        self._slide_animation(self.current_y, self.target_y, duration_ms=160)
        self._start_wave_animation()

    def update_live_text(self, text: str):
        """Updates recognized text word-by-word in real time."""
        if not text:
            return

        display_text = text.strip()
        # Keep the latest words visible if text exceeds pill width
        if len(display_text) > 42:
            display_text = "…" + display_text[-39:]

        self.canvas.itemconfig(self.text_id, text=display_text, fill="#FFFFFF")
        self.root.update_idletasks()

    def show_processing(self):
        """Switches to processing state (Sky/Cyan Glow)."""
        self._state = "processing"
        self._stop_wave_animation()
        
        # Hide bars, show AI spinner/glyph
        for b in self.bars:
            self.canvas.itemconfig(b, state="hidden")
            
        self.canvas.itemconfig(self.badge_id, text="✦", fill="#38BDF8")
        self.canvas.itemconfig(self.glow_id, outline="#0284C7", fill="#071926")
        self.root.update_idletasks()

    def show_done(self, final_text: str):
        """Shows final formatted text with emerald checkmark and slides down."""
        self._state = "done"
        self._stop_wave_animation()
        
        for b in self.bars:
            self.canvas.itemconfig(b, state="hidden")
            
        self.canvas.itemconfig(self.badge_id, text="✓", fill="#10B981")
        self.canvas.itemconfig(self.glow_id, outline="#059669", fill="#062117")
        
        display_text = final_text.strip()
        if len(display_text) > 42:
            display_text = "…" + display_text[-39:]
            
        self.canvas.itemconfig(self.text_id, text=display_text, fill="#FFFFFF")
        self.root.update_idletasks()

        # Schedule smooth slide down into screen after 750ms
        self._hide_timer = self.root.after(750, self.hide)

    def hide(self):
        """Slides down smoothly back into monitor edge and withdraws."""
        self._hide_timer = None
        self._state = "idle"
        self._stop_wave_animation()

        def _on_hidden():
            self._is_visible = False
            self.root.withdraw()

        # Slide down into bottom edge
        self._slide_animation(self.current_y, self.hidden_y, duration_ms=140, callback=_on_hidden)
