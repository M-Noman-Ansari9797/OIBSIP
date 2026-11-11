# Task 2 – BMI Calculator (Python)

Calculates Body Mass Index and classifies it into health categories. Both tiers are included:
a **command-line** program (Beginner) and a **tkinter GUI** with multi-user history, SQLite storage
and a matplotlib trend chart (Advanced).

## Features

### Beginner tier – `bmi_cli.py`
- Prompts for weight (kg) and height (m)
- BMI = weight / height²
- Categories: Underweight (< 18.5), Normal (18.5–24.9), Overweight (25–29.9), Obese (≥ 30)
- Shows BMI rounded to 2 decimals plus the category
- Input validation: rejects text, empty input, zero and negative numbers, `nan`/`inf`, and
  catches common slips such as entering height in centimetres (e.g. `175`)
- Option to calculate again without restarting

### Advanced tier – `bmi_gui.py`
- tkinter window, no command line needed
- Labelled input fields and a **Calculate** button (Enter key works too)
- Colour-coded result panel: blue = underweight, green = normal, orange = overweight, red = obese
- **Multi-user** support: type a new name or pick an existing one from the drop-down
- Records saved to an **SQLite** database (`bmi_records.db`, created automatically)
- **Trend chart** (matplotlib line chart) with shaded category bands and value labels
- Database errors (cannot open / read / write) are caught and shown in the window and a dialog

## Setup & run

```bash
pip install -r requirements.txt

python bmi_cli.py      # command-line version
python bmi_gui.py      # GUI version
```
tkinter ships with the standard Python installer on Windows and macOS.
On Debian/Ubuntu install it with `sudo apt install python3-tk`.

## Using the GUI
1. Enter a **user name**, **weight** and **height**, then press **Calculate**.
2. Press **Save Record** to store the reading (it also refreshes the chart).
3. Select a name in the drop-down (or press **Show Trend**) to see that person's BMI over time.

## Testing
```bash
python -m unittest test_bmi -v
```
12 tests cover the formula, every category boundary, input validation, multi-user storage,
history ordering, deleting a user, SQL-injection safety (parameterised queries) and database
failure handling.

## Design notes
- `bmi_core.py` holds all logic and the database layer, so the CLI and GUI share one tested
  implementation.
- All SQL uses parameterised queries.
- BMI is a screening indicator only and does not account for muscle mass, age or sex.
  It is not medical advice.

## Project structure
```
task2_bmi_calculator/
├── bmi_core.py        calculation, validation, SQLite layer
├── bmi_cli.py         Beginner tier (command line)
├── bmi_gui.py         Advanced tier (tkinter + matplotlib)
├── test_bmi.py        unit tests
├── requirements.txt
└── README.md
```
