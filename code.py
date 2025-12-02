import board
import time
import digitalio
import adafruit_matrixkeypad
import rgb1602
# import circuitpython_csv as csv

lcd = rgb1602.RGB1602(16, 2)  

digits = []

esp32s3_project_pins = {
    "NEOPIXEL": board.A0,      # GPIO18
    "COL0": board.A5,          # GPIO8
    "COL1": board.A4,          # GPIO14
    "COL2": board.A3,          # GPIO15
    "COL3": board.A2,          # GPIO16
    "ROW0": board.D13,         # GPIO13
    "ROW1": board.D12,         # GPIO12
    "ROW2": board.D11,         # GPIO11
    "ROW3": board.D10,         # GPIO10
    "ROW4": board.D9,          # GPIO9
    "I2C_SDA": board.SDA,      # GPIO3
    "I2C_SCL": board.SCL,      # GPIO4
}

# Key matrix layout (key numbers)
KEYS = (
    (0,  1,  2,  3),     # ROW0: 0*4+0, 0*4+1, 0*4+2, 0*4+3
    (4,  5,  6,  7),     # ROW1: 1*4+0, 1*4+1, 1*4+2, 1*4+3
    (8,  9,  10, None),  # ROW2: 2*4+0, 2*4+1, 2*4+2, (2,3) deleted
    (12, 13, 14, 15),    # ROW3: 3*4+0, 3*4+1, 3*4+2, 3*4+3
    (16, None, 18, None) # ROW4: 4*4+0, (4,1) deleted, 4*4+2, (4,3) deleted
)

# Key Number to Physical Key Mapping
KEY_LABELS = {
    0: "Num Lock",
    1: "*",
    2: "-",
    3: "/",
    4: "7",
    5: "8",
    6: "9",
    7: "+",
    8: "4",
    9: "5",
    10: "6",
    12: "1",
    13: "2",
    14: "3",
    15: "Enter",
    16: "0",
    18: ".",
}

rows = [digitalio.DigitalInOut(esp32s3_project_pins[f"ROW{i}"]) for i in range(5)]
cols = [digitalio.DigitalInOut(esp32s3_project_pins[f"COL{i}"]) for i in range(4)]

keypad = adafruit_matrixkeypad.Matrix_Keypad(rows, cols, KEYS)

current_digits = []
last_keys = set()


def show_number():
    lcd.write_text("".join(current_digits), row=0, clear_line=True)


while True:
    keys = set(keypad.pressed_keys)
    new_keys = keys - last_keys

    if new_keys:
        # Take the first new key press.
        key = new_keys.pop()
        label = KEY_LABELS.get(key)

        if label and label.isdigit():
            # Start a new entry if a previous 5-digit number was complete.
            if len(current_digits) == 5:
                current_digits = []
                lcd.clear()

            # Clear the display at the start of a new entry.
            if not current_digits:
                lcd.clear()

            if len(current_digits) < 5:
                current_digits.append(label)
                show_number()

    last_keys = keys
    time.sleep(0.05)
