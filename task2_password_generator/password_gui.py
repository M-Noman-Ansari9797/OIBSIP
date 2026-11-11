"""Task 3 - Random Password Generator (Advanced tier: tkinter GUI, secrets, pyperclip)."""

from __future__ import annotations

import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk

try:
    import pyperclip
except ImportError:  # pragma: no cover
    pyperclip = None

from password_core import CHARSETS, MAX_LENGTH, MIN_LENGTH, generate_password, strength

STRENGTH_COLOURS = {"Weak": "#e74c3c", "Medium": "#f39c12", "Strong": "#2ecc71"}


class PasswordApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Secure Password Generator")
        self.geometry("520x560")
        self.resizable(False, False)

        self.history: deque[str] = deque(maxlen=5)   # session only - never written to disk
        self.length_var = tk.IntVar(value=16)
        self.type_vars = {name: tk.BooleanVar(value=True) for name in CHARSETS}
        self.exclude_var = tk.BooleanVar(value=False)
        self.password_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build_ui()
        self.generate()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=14)
        main.pack(fill="both", expand=True)

        # Length controls: slider + spinbox kept in sync
        length_box = ttk.LabelFrame(main, text="Length", padding=10)
        length_box.pack(fill="x")
        self.scale = ttk.Scale(length_box, from_=MIN_LENGTH, to=64, orient="horizontal",
                               command=self._on_scale)
        self.scale.set(self.length_var.get())
        self.scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.spin = ttk.Spinbox(length_box, from_=MIN_LENGTH, to=MAX_LENGTH, width=5,
                                textvariable=self.length_var, command=self._on_spin)
        self.spin.pack(side="left")
        self.spin.bind("<KeyRelease>", lambda _e: self._on_spin())

        # Character types
        types_box = ttk.LabelFrame(main, text="Character types (select at least 2)", padding=10)
        types_box.pack(fill="x", pady=10)
        for i, name in enumerate(CHARSETS):
            ttk.Checkbutton(types_box, text=name.capitalize(), variable=self.type_vars[name]
                            ).grid(row=i // 2, column=i % 2, sticky="w", padx=10, pady=2)
        ttk.Checkbutton(types_box, text="Exclude ambiguous characters (0 O o 1 l I |)",
                        variable=self.exclude_var).grid(row=2, column=0, columnspan=2,
                                                        sticky="w", padx=10, pady=(6, 0))

        # Output
        out_box = ttk.LabelFrame(main, text="Your password", padding=10)
        out_box.pack(fill="x")
        entry = ttk.Entry(out_box, textvariable=self.password_var, font=("Consolas", 14),
                          state="readonly", justify="center")
        entry.pack(fill="x", pady=(0, 8))

        self.strength_canvas = tk.Canvas(out_box, height=14, bg="#ecf0f1", highlightthickness=0)
        self.strength_canvas.pack(fill="x")
        self.strength_label = ttk.Label(out_box, text="", font=("Segoe UI", 10, "bold"))
        self.strength_label.pack(pady=(4, 0))

        buttons = ttk.Frame(main)
        buttons.pack(pady=12)
        ttk.Button(buttons, text="Generate", command=self.generate).pack(side="left", padx=6)
        ttk.Button(buttons, text="Copy to Clipboard", command=self.copy).pack(side="left", padx=6)

        ttk.Label(main, textvariable=self.status_var, foreground="#c0392b",
                  wraplength=480).pack(fill="x")

        hist_box = ttk.LabelFrame(main, text="Last 5 passwords (this session only)", padding=8)
        hist_box.pack(fill="both", expand=True, pady=(6, 0))
        self.hist_list = tk.Listbox(hist_box, height=5, font=("Consolas", 10), activestyle="none")
        self.hist_list.pack(fill="both", expand=True)
        self.hist_list.bind("<Double-Button-1>", self._copy_from_history)

    # ------------------------------------------------------------- events
    def _on_scale(self, value: str) -> None:
        self.length_var.set(int(float(value)))

    def _on_spin(self) -> None:
        try:
            value = int(self.length_var.get())
        except (tk.TclError, ValueError):
            return
        if MIN_LENGTH <= value <= 64:
            self.scale.set(value)

    def _selected(self) -> list[str]:
        return [name for name, var in self.type_vars.items() if var.get()]

    def generate(self) -> None:
        self.status_var.set("")
        try:
            length = int(self.length_var.get())
        except (tk.TclError, ValueError):
            self.status_var.set("Length must be a whole number.")
            return
        try:
            password = generate_password(length, self._selected(), self.exclude_var.get())
        except ValueError as err:
            self.status_var.set(str(err))
            return

        self.password_var.set(password)
        self._update_strength(password)
        self.history.appendleft(password)
        self._refresh_history()
        self._copy_to_clipboard(password, announce=False)

    def _update_strength(self, password: str) -> None:
        label, score = strength(password)
        colour = STRENGTH_COLOURS[label]
        self.update_idletasks()
        width = self.strength_canvas.winfo_width() or 460
        self.strength_canvas.delete("all")
        self.strength_canvas.create_rectangle(0, 0, width * score / 100, 14, fill=colour, width=0)
        self.strength_label.config(text=f"Strength: {label}  ({score}/100)", foreground=colour)

    def _refresh_history(self) -> None:
        self.hist_list.delete(0, "end")
        for pw in self.history:
            self.hist_list.insert("end", pw)

    def _copy_to_clipboard(self, text: str, announce: bool = True) -> None:
        if pyperclip is None:
            self.status_var.set("Install pyperclip to enable clipboard copy (pip install pyperclip).")
            return
        try:
            pyperclip.copy(text)
            if announce:
                self.status_var.set("")
                messagebox.showinfo("Copied", "Password copied to clipboard.")
        except pyperclip.PyperclipException:
            self.status_var.set("Clipboard is not available on this system.")

    def copy(self) -> None:
        if self.password_var.get():
            self._copy_to_clipboard(self.password_var.get())

    def _copy_from_history(self, _event: tk.Event) -> None:
        selection = self.hist_list.curselection()
        if selection:
            self._copy_to_clipboard(self.hist_list.get(selection[0]))


if __name__ == "__main__":
    PasswordApp().mainloop()
