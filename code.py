import board
import keypad
import rgb1602
import allowlist_reader
import time
#import adafruit_bus_device
import adafruit_max1704x
#import alarm
import digitalio

lcd = rgb1602.RGB1602(16, 2)  

monitor = adafruit_max1704x.MAX17048(board.I2C())


digits = []
BLOCK = 1
DAYAB = "A"
DAYTYPE = "Norm"
BRIGHTNESS = 1

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

# Asterisk key is row 0 / col 1 in this matrix; diodes are row->column.
ASTERISK_ROW_PIN = esp32s3_project_pins["ROW0"]
ASTERISK_COL_PIN = esp32s3_project_pins["COL1"]


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

rows = [esp32s3_project_pins[f"ROW{i}"] for i in range(5)]
cols = [esp32s3_project_pins[f"COL{i}"] for i in range(4)]

keyboard = keypad.KeyMatrix(rows, cols)

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
def bat_state():
    #monitor.wake()
    lcd.clear()
    lcd.write_text("Battery:", row=0)
    percentage = f"{monitor.cell_percent:.1f} %"
    lcd.write_text(percentage, row=1, clear_line=True)
    #monitor.hibernate()
    time.sleep(2)
    return(True)


def upload_allowlist():
    return(True)

def brightness_set():
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
    global DAYAB
    DAYAB = output
    return(True) 

def set_day_type(output):
    global DAYTYPE
    DAYTYPE = output
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


def go_deep_sleep():
    monitor.hibernate()
    lcd.clear()
    lcd.setRGB(0,0,0)
    raise SystemExit



settings = Menu("Settings", [
    ("Set day", a_or_b_day_menu),
    ("Set block", set_block),
    ("Upload Allowlist", upload_allowlist),
    ("Battery State", bat_state),
    ("Power off", go_deep_sleep),
])

def get_student_info(stid):
    row = allowlist_reader.lookup_student(stid)
    if row is None:
        lcd.write_text("ID not found", row=0, clear_line=True)
        lcd.setRGB(255, 0, 0)
        time.sleep(1)
        lcd.setRGB(255*BRIGHTNESS, 255*BRIGHTNESS, 255*BRIGHTNESS)
        return

    # Normalize row values and label
    if isinstance(row, dict):
        a_val = _to_int(row.get("A"))
        b_val = _to_int(row.get("B"))
        label = row.get("STUDENT_NAME") or row.get("STUDENT_PIN") or str(stid)
    else:
        print("Err fetch csv")
        lcd.write_text("Data error", row=0, clear_line=True)
        lcd.setRGB(255, 0, 0)
        time.sleep(1)
        lcd.setRGB(255*BRIGHTNESS, 255*BRIGHTNESS, 255*BRIGHTNESS)
        lcd.write_text("", row=0, clear_line=True)
        return
    ok = False
    if DAYAB == "A" and a_val is not None and a_val <= int(BLOCK):
        ok = True
    elif DAYAB == "B" and b_val is not None and b_val <= int(BLOCK):
        ok = True

    if ok:
        lcd.write_text(f"{label}", row=0, clear_line=True)
        lcd.write_text(f"OK - {DAYAB} DAY, P{BLOCK}", row=1, clear_line=True)
        lcd.setRGB(0, 255, 0)
    else:
        lcd.write_text(label, row=0, clear_line=True)
        lcd.write_text(f"Not Allowed-{DAYAB},P{BLOCK}", row=1, clear_line=True)
        lcd.setRGB(255, 0, 0)
    time.sleep(2)
    lcd.setRGB(255*BRIGHTNESS, 255*BRIGHTNESS, 255*BRIGHTNESS)
    lcd.write_text("", row=0, clear_line=True)
    lcd.write_text("", row=1, clear_line=True)


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None

lcd.write_text("Booting...", row=0, clear_line=True)
time.sleep(.5)
lcd.clear()

pin_digits = []
input_prefix = "Student ID:"
lcd.write_text(input_prefix, row=0, clear_line=True)
lcd.write_text(f"{DAYAB} Day, Block{BLOCK}", row=1, clear_line=True)
while True:
    if monitor.active_alert:
        if monitor.SOC_low_alert:
            lcd.clear()
            lcd.write_text("LOW BATTERY", row=0, clear_line=True)
            lcd.setRGB(255, 0, 0)
            time.sleep(2)
            lcd.setRGB(0,0,0)
            lcd.clear()

    event = keyboard.events.get()
    if not event:
        time.sleep(0.05)  # brief idle to avoid a tight polling loop
        continue
    if event: 
        if event.pressed:
            key = KEY_LABELS.get(event.key_number, None)
            if key and key.isdigit():
                if len(pin_digits) < 5:
                    pin_digits.append(key)
                    lcd.write_text((input_prefix + "".join(pin_digits)), row=0, clear_line=True)
            elif key == "Enter":
                if len(pin_digits) == 5:
                    student_id = "".join(pin_digits)
                    lcd.clear()
                    get_student_info(student_id)
                    pin_digits = []
                    lcd.clear()
                    lcd.write_text(input_prefix, row=0, clear_line=True)
                    lcd.write_text(f"{DAYAB} Day, Block {BLOCK}", row=1, clear_line=True)

            elif key == "Num Lock":
                pin_digits.pop() if pin_digits else None
                lcd.write_text((input_prefix + "".join(pin_digits)), row=0, clear_line=True)
            elif key == "*":
                settings.activate(lcd, keyboard)
                pin_digits = []
                lcd.clear()
                lcd.write_text(input_prefix, row=0, clear_line=True)
                lcd.write_text(f"{DAYAB} Day, Block {BLOCK}", row=1, clear_line=True)
