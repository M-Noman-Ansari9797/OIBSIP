"""Task 2 - BMI Calculator (Advanced tier: tkinter GUI, multi-user, SQLite, matplotlib trend)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from bmi_core import (CATEGORY_COLOURS, BMIDatabase, DatabaseError, calculate_bmi,  # noqa: E402
                      classify_bmi, parse_positive_float, validate_ranges)


class BMIApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BMI Calculator")
        self.geometry("760x640")
        self.minsize(700, 600)

        try:
            self.db: BMIDatabase | None = BMIDatabase()
        except DatabaseError as err:
            self.db = None
            messagebox.showerror("Database error", f"{err}\n\nRecords cannot be saved this session.")

        self.last_result: tuple[float, float, float, str] | None = None
        self._build_ui()
        self._refresh_users()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        form = ttk.LabelFrame(self, text="Enter measurements")
        form.pack(fill="x", padx=12, pady=(12, 6))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="User name:").grid(row=0, column=0, sticky="w", **pad)
        self.user_var = tk.StringVar()
        self.user_box = ttk.Combobox(form, textvariable=self.user_var)
        self.user_box.grid(row=0, column=1, sticky="ew", **pad)
        self.user_box.bind("<<ComboboxSelected>>", lambda _e: self._show_history())

        ttk.Label(form, text="Weight (kg):").grid(row=1, column=0, sticky="w", **pad)
        self.weight_var = tk.StringVar()
        weight_entry = ttk.Entry(form, textvariable=self.weight_var)
        weight_entry.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(form, text="Height (m):").grid(row=2, column=0, sticky="w", **pad)
        self.height_var = tk.StringVar()
        height_entry = ttk.Entry(form, textvariable=self.height_var)
        height_entry.grid(row=2, column=1, sticky="ew", **pad)

        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(buttons, text="Calculate", command=self.calculate).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save Record", command=self.save_record).pack(side="left", padx=5)
        ttk.Button(buttons, text="Show Trend", command=self._show_history).pack(side="left", padx=5)
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left", padx=5)

        for entry in (weight_entry, height_entry):
            entry.bind("<Return>", lambda _e: self.calculate())

        # Colour-coded result panel
        self.result_frame = tk.Frame(self, bg="#ecf0f1", height=70)
        self.result_frame.pack(fill="x", padx=12, pady=6)
        self.result_frame.pack_propagate(False)
        self.result_label = tk.Label(self.result_frame, text="Enter your details and press Calculate",
                                     bg="#ecf0f1", fg="#2c3e50", font=("Segoe UI", 14, "bold"))
        self.result_label.pack(expand=True)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground="#c0392b").pack(fill="x", padx=14)

        # Chart
        chart_frame = ttk.LabelFrame(self, text="BMI trend")
        chart_frame.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.figure = Figure(figsize=(6.5, 3.2), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty_chart("Select a user to view their BMI history")

    # ------------------------------------------------------------ actions
    def _set_error(self, message: str) -> None:
        self.status_var.set(message)

    def calculate(self) -> bool:
        self.status_var.set("")
        try:
            weight = parse_positive_float(self.weight_var.get(), "Weight")
            height = parse_positive_float(self.height_var.get(), "Height")
            validate_ranges(weight, height)
        except ValueError as err:
            self.last_result = None
            self._set_error(str(err))
            return False

        bmi = calculate_bmi(weight, height)
        category = classify_bmi(bmi)
        self.last_result = (weight, height, bmi, category)
        colour = CATEGORY_COLOURS[category]
        self.result_frame.config(bg=colour)
        self.result_label.config(text=f"BMI {bmi:.2f}  -  {category}", bg=colour, fg="white")
        return True

    def save_record(self) -> None:
        if self.db is None:
            self._set_error("Database unavailable - record not saved.")
            return
        username = self.user_var.get().strip()
        if not username:
            self._set_error("Please enter a user name before saving.")
            return
        if not self.calculate():
            return
        weight, height, bmi, category = self.last_result  # type: ignore[misc]
        try:
            self.db.add_record(username, weight, height, bmi, category)
        except DatabaseError as err:
            self._set_error(str(err))
            messagebox.showerror("Save failed", str(err))
            return
        self.status_var.set("")
        self._refresh_users()
        self.user_var.set(username)
        self._show_history()

    def _refresh_users(self) -> None:
        if self.db is None:
            return
        try:
            self.user_box["values"] = self.db.users()
        except DatabaseError as err:
            self._set_error(str(err))

    def _show_history(self) -> None:
        username = self.user_var.get().strip()
        if not username:
            self._set_error("Choose or type a user name to see their trend.")
            return
        if self.db is None:
            self._set_error("Database unavailable.")
            return
        try:
            rows = self.db.history(username)
        except DatabaseError as err:
            self._set_error(str(err))
            return
        if not rows:
            self._draw_empty_chart(f"No saved records for '{username}' yet")
            return
        self.status_var.set("")
        self._draw_chart(username, rows)

    # -------------------------------------------------------------- chart
    def _draw_empty_chart(self, message: str) -> None:
        self.ax.clear()
        self.ax.text(0.5, 0.5, message, ha="center", va="center", transform=self.ax.transAxes,
                     color="#7f8c8d")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()

    def _draw_chart(self, username: str, rows: list[tuple]) -> None:
        labels = [r[0][5:16] for r in rows]  # "MM-DD HH:MM"
        values = [r[3] for r in rows]
        self.ax.clear()
        self.ax.axhspan(0, 18.5, color=CATEGORY_COLOURS["Underweight"], alpha=0.10)
        self.ax.axhspan(18.5, 25, color=CATEGORY_COLOURS["Normal"], alpha=0.10)
        self.ax.axhspan(25, 30, color=CATEGORY_COLOURS["Overweight"], alpha=0.10)
        self.ax.axhspan(30, 60, color=CATEGORY_COLOURS["Obese"], alpha=0.10)
        self.ax.plot(range(len(values)), values, marker="o", color="#2c3e50", linewidth=2)
        for x, v in enumerate(values):
            self.ax.annotate(f"{v:.1f}", (x, v), textcoords="offset points", xytext=(0, 8),
                             ha="center", fontsize=8)
        self.ax.set_xticks(range(len(values)))
        self.ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        low, high = min(values + [18.5]) - 2, max(values + [30]) + 2
        self.ax.set_ylim(low, high)
        self.ax.set_ylabel("BMI")
        self.ax.set_title(f"BMI trend - {username}")
        self.ax.grid(alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def clear(self) -> None:
        self.weight_var.set("")
        self.height_var.set("")
        self.status_var.set("")
        self.last_result = None
        self.result_frame.config(bg="#ecf0f1")
        self.result_label.config(text="Enter your details and press Calculate", bg="#ecf0f1",
                                 fg="#2c3e50")


if __name__ == "__main__":
    BMIApp().mainloop()
