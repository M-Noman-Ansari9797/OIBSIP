"""Task 2 - BMI Calculator (Beginner tier: command-line version)."""

from bmi_core import calculate_bmi, classify_bmi, parse_positive_float, validate_ranges


def ask_number(prompt: str, field: str) -> float:
    """Keep asking until the user enters a valid positive number."""
    while True:
        try:
            return parse_positive_float(input(prompt), field)
        except ValueError as err:
            print(f"  Invalid input: {err}")


def main() -> None:
    print("=== BMI Calculator ===")
    while True:
        weight = ask_number("Enter your weight in kilograms (e.g. 70): ", "Weight")
        height = ask_number("Enter your height in metres (e.g. 1.75): ", "Height")
        try:
            validate_ranges(weight, height)
        except ValueError as err:
            print(f"  Invalid input: {err}\n")
            continue

        bmi = calculate_bmi(weight, height)
        print(f"\nYour BMI is {bmi:.2f}  ->  {classify_bmi(bmi)}\n")

        again = input("Calculate another? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Stay healthy! Goodbye.")
            break
        print()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nProgram closed. Goodbye.")
