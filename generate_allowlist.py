import csv
import random

PIN_COUNT = 200
PIN_PREFIX = 1  # first digit must be 1
PIN_LENGTH = 5


def generate_pins(count):
    """Return a list of unique 5-digit PINs starting with 1."""
    start = PIN_PREFIX * 10 ** (PIN_LENGTH - 1)
    end = start + 10 ** (PIN_LENGTH - 1)
    population = range(start, end)
    return random.sample(list(population), count)


def main():
    pins = generate_pins(PIN_COUNT)
    with open("Allowlist.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PIN", "A", "B", "log"])
        for pin in pins:
            writer.writerow([pin, random.randint(1, 4), random.randint(1, 4), ""])


if __name__ == "__main__":
    main()
