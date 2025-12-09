import board
import keypad
import rgb1602

lcd = rgb1602.RGB1602(16, 2)  

digits = []
BLOCK = 1

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

class Menu: 
    def __init__(self, title, items):
        self.title = title
        self.items = items 
        #items is [(label, action/menu), ...]
    def render(self, lcd, scroll, cursor):
        lcd.clear()
        visible = self.items[scroll:scroll+2]
        # pad if fewer than two items remain
        while len(visible) < 2:
            visible.append(("", None))

        for row, (label, action) in enumerate(visible):
            trimmed = label[:15]
            suffix = "<" if row == cursor else " "
            lcd.write_text(trimmed + " "*(15-len(trimmed)) + suffix, row=row, clear_line=True)
    def activate(self, lcd, keyboard):
        scroll = 0
        cursor = 0
        self.render(lcd, scroll, cursor)
        while True:
            event = keyboard.events.get()
            if not (event and event.pressed):
                continue
            if event.key_number == 5:      # up
                if cursor > 0:
                    cursor -= 1
                elif scroll > 0:
                    scroll -= 1
                self.render(lcd, scroll, cursor)
            elif event.key_number == 13:   # down
                if cursor < 1 and scroll + cursor + 1 < len(self.items):
                    cursor += 1
                elif scroll + 2 < len(self.items):
                    scroll += 1
                self.render(lcd, scroll, cursor)
            elif event.key_number == 15:   # enter
                label, target = self.items[scroll + cursor]
                if isinstance(target, Menu):
                    target.activate(lcd, keyboard)
                    self.render(lcd, scroll, cursor)  # redraw on return
                elif callable(target):
                    if target():
                        break
                    self.render(lcd, scroll, cursor)
                else:
                    return
            elif event.key_number == 0:    # Num Lock as Back
                return

def upload_allowlist():
    return(True)

def set_block():
    global BLOCK
    input_block = ""
    lcd.clear()
    lcd.write_text("What block?", row=0)
    while 1:
        event = keyboard.events.get()
        if event and event.pressed:
            key = KEY_LABELS.get(event.key_number, None)
            if key and key.isdigit():
                if 1<= int(key) <= 4 and not input_block:
                    input_block = key
                    lcd.write_text(input_block, row=1, clear_line=True)
            elif key == "Num Lock":
                input_block = ""
                lcd.write_text(input_block, row=1, clear_line=True)
            elif key == "Enter":
                if input_block:
                    BLOCK = int(input_block)
                    return(True)


def set_a_or_b_day(output):
    return(True) 

def set_day_type(output):
    return(True)

day_type_menu = Menu("Day Type?", [
    ("Regular Day", lambda: set_day_type("Norm")),
    ("Assembly", lambda: set_day_type("Assy")),
    ("Wednesday", lambda: set_day_type("Weds"))
])

a_or_b_day_menu = Menu("A or B Day?", [
    ("A Day", lambda: (set_a_or_b_day("A"), day_type_menu.activate(lcd, keyboard), True)[-1]),
    ("B Day", lambda: (set_a_or_b_day("B"), day_type_menu.activate(lcd, keyboard), True)[-1])
])

settings = Menu("Settings", [
    ("Set day", a_or_b_day_menu), 
    ("Set block", set_block),
    ("Upload Allowlist", upload_allowlist)
])





rows = [esp32s3_project_pins[f"ROW{i}"] for i in range(5)]
cols = [esp32s3_project_pins[f"COL{i}"] for i in range(4)]

keyboard = keypad.KeyMatrix(rows, cols)

pin_digits = []
input_prefix = "Student ID:"
while True:
    event = keyboard.events.get()
    if event: 
        if event.pressed:
            key = KEY_LABELS.get(event.key_number, None)
            if key and key.isdigit():
                if len(pin_digits) < 5:
                    pin_digits.append(key)
                    lcd.write_text((input_prefix + "".join(pin_digits)), row=0, clear_line=True)
            elif key == "Enter":
                if len(pin_digits) == 5:
                    lcd.clear()
                    pin_digits = []
                    lcd.write_text(input_prefix, row=0, clear_line=True)
            elif key == "Num Lock":
                pin_digits.pop() if pin_digits else None
                lcd.write_text((input_prefix + "".join(pin_digits)), row=0, clear_line=True)
            elif key == "*":
                settings.activate(lcd, keyboard)
                pin_digits = []
                lcd.clear()
