import board
import time
import json
from digitalio import DigitalInOut
import adafruit_matrixkeypad
import displayio
import terminalio
from adafruit_display_text import label

# Pin definitions
esp32s3_project_pins = {
    "NEOPIXEL": "A0",      # GPIO18
    "COL0": "A5",          # GPIO8
    "COL1": "A4",          # GPIO14
    "COL2": "A3",          # GPIO15
    "COL3": "A2",          # GPIO16
    "ROW0": "D13",         # GPIO13
    "ROW1": "D12",         # GPIO12
    "ROW2": "D11",         # GPIO11
    "ROW3": "D10",         # GPIO10
    "ROW4": "D9",          # GPIO9
    "I2C_SDA": "SDA",      # GPIO3
    "I2C_SCL": "SCL",      # GPIO4
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

status_label = None  # Assigned after display objects are created


def send_event(event_type, **data):
    """
    Emit a JSON-formatted event for the host visualizer.
    """
    payload = {"type": event_type}
    payload.update(data)
    print(json.dumps(payload))


def send_display_event(target, text):
    """
    Notify the host mirror to update a particular on-screen element.
    """
    send_event("display", target=target, text=text)


def update_status(text):
    """
    Update the onboard status label and notify the host display.
    """
    global status_label
    if status_label is not None:
        status_label.text = text
    send_display_event("status", text)

def scan_keys(keypad, currently_pressed, text_area, number_input_label, number_buffer):
    """
    Scan the key matrix and handle press/release events
    Returns updated set of currently pressed keys
    """
    pressed_keys = keypad.pressed_keys
    pressed_set = set(pressed_keys) if pressed_keys else set()

    # Handle newly pressed keys
    newly_pressed = pressed_set - currently_pressed
    for key in newly_pressed:
        if key is not None and key in KEY_LABELS:
            key_label = KEY_LABELS[key]
            send_event("key", action="press", key=key_label, key_number=key)
            # Update main key display
            text_area.text = key_label
            send_display_event("key_display", key_label)

            # Handle number input
            # Numbers 0-9 and decimal point
            if key_label in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.']:
                if len(number_buffer) < 5:
                    number_buffer.append(key_label)
                    update_number_display(number_input_label, number_buffer)
                    update_status("Typing")

            # Enter key - could process the number
            elif key_label == "Enter":
                if number_buffer:
                    entered_value = ''.join(number_buffer)
                    send_event("number", action="entered", value=entered_value)
                    update_status(f"Entered {entered_value}")
                    # Clear buffer after enter
                    number_buffer.clear()
                    update_number_display(number_input_label, number_buffer)
                else:
                    update_status("Enter (empty)")

            # Minus key - clear the buffer
            elif key_label == "-":
                number_buffer.clear()
                update_number_display(number_input_label, number_buffer)
                update_status("Cleared")
            else:
                update_status(f"Pressed {key_label}")

    # Handle newly released keys
    newly_released = currently_pressed - pressed_set
    for key in newly_released:
        if key is not None and key in KEY_LABELS:
            key_label = KEY_LABELS[key]
            send_event("key", action="release", key=key_label, key_number=key)
            update_status(f"Released {key_label}")

    return pressed_set


def update_number_display(number_input_label, number_buffer):
    """
    Update the number input display with current buffer contents
    Shows up to 5 characters, padded with underscores
    """
    buffer_str = ''.join(number_buffer)
    # Pad with underscores to always show 5 characters
    display_str = buffer_str.ljust(5, '_')
    number_input_label.text = display_str
    send_display_event("number_input", display_str)


# Initialization
# Define columns (COL0, COL1, COL2, COL3)
cols = [DigitalInOut(x) for x in (
    getattr(board, esp32s3_project_pins["COL0"]),
    getattr(board, esp32s3_project_pins["COL1"]),
    getattr(board, esp32s3_project_pins["COL2"]),
    getattr(board, esp32s3_project_pins["COL3"]),
)]

# Define rows (ROW0, ROW1, ROW2, ROW3, ROW4)
rows = [DigitalInOut(x) for x in (
    getattr(board, esp32s3_project_pins["ROW0"]),
    getattr(board, esp32s3_project_pins["ROW1"]),
    getattr(board, esp32s3_project_pins["ROW2"]),
    getattr(board, esp32s3_project_pins["ROW3"]),
    getattr(board, esp32s3_project_pins["ROW4"]),
)]

# Initialize the keypad
keypad = adafruit_matrixkeypad.Matrix_Keypad(rows, cols, KEYS)

# Track currently pressed keys
currently_pressed = set()

# Number input buffer (stores up to 5 digits)
number_buffer = []

# ============================================================================
# DISPLAY LAYOUT CONFIGURATION
# ============================================================================
# Initialize the display (1.14" 240x135 TFT, set up vertically)
display = board.DISPLAY
display.rotation = 270  # Rotate for vertical orientation (portrait mode)
                        # After rotation: 135px wide x 240px tall

# Display dimensions after rotation
DISPLAY_WIDTH = display.width   # 135
DISPLAY_HEIGHT = display.height # 240

# Color scheme
BACKGROUND_COLOR = 0x000000  # Black
ACCENT_COLOR = 0x0000FF      # Blue
TEXT_COLOR = 0xFFFFFF        # White
HIGHLIGHT_COLOR = 0x00FF00   # Green

send_event(
    "layout",
    width=DISPLAY_WIDTH,
    height=DISPLAY_HEIGHT,
    rotation=display.rotation,
    colors={
        "background": BACKGROUND_COLOR,
        "accent": ACCENT_COLOR,
        "text": TEXT_COLOR,
        "highlight": HIGHLIGHT_COLOR,
    },
)

# Layout positions - customize these to arrange elements
# Number input display (top section - shows up to 5 numbers)
NUMBER_INPUT_X = DISPLAY_WIDTH // 2
NUMBER_INPUT_Y = 25
NUMBER_INPUT_SCALE = 2

# Title
TITLE_X = DISPLAY_WIDTH // 2
TITLE_Y = 60
TITLE_SCALE = 1

# Main key display (center)
KEY_DISPLAY_X = DISPLAY_WIDTH // 2
KEY_DISPLAY_Y = DISPLAY_HEIGHT // 2 + 20
KEY_DISPLAY_SCALE = 3

# Status (bottom)
STATUS_X = DISPLAY_WIDTH // 2
STATUS_Y = DISPLAY_HEIGHT - 30
STATUS_SCALE = 1

# ============================================================================
# DISPLAY INITIALIZATION
# ============================================================================
# Create the display context
splash = displayio.Group()
display.root_group = splash

# Create background
color_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
color_palette = displayio.Palette(1)
color_palette[0] = BACKGROUND_COLOR

bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
splash.append(bg_sprite)

# Create number input display (shows up to 5 numbers typed)
number_input_label = label.Label(
    terminalio.FONT,
    text="_____",  # 5 underscores as placeholder
    color=HIGHLIGHT_COLOR,
    scale=NUMBER_INPUT_SCALE
)
number_input_label.anchor_point = (0.5, 0.5)  # Center anchor
number_input_label.anchored_position = (NUMBER_INPUT_X, NUMBER_INPUT_Y)
splash.append(number_input_label)
send_display_event("number_input", number_input_label.text)

# Create title label
title_label = label.Label(
    terminalio.FONT,
    text="NUMPAD",
    color=TEXT_COLOR,
    scale=TITLE_SCALE
)
title_label.anchor_point = (0.5, 0.5)  # Center anchor
title_label.anchored_position = (TITLE_X, TITLE_Y)
splash.append(title_label)
send_display_event("title", title_label.text)

# Create main key display area (shows current key pressed)
key_display_label = label.Label(
    terminalio.FONT,
    text="---",
    color=HIGHLIGHT_COLOR,
    scale=KEY_DISPLAY_SCALE
)
key_display_label.anchor_point = (0.5, 0.5)  # Center anchor
key_display_label.anchored_position = (KEY_DISPLAY_X, KEY_DISPLAY_Y)
splash.append(key_display_label)
send_display_event("key_display", key_display_label.text)

# Create status label (bottom)
status_label = label.Label(
    terminalio.FONT,
    text="Ready",
    color=TEXT_COLOR,
    scale=STATUS_SCALE
)
status_label.anchor_point = (0.5, 0.5)  # Center anchor
status_label.anchored_position = (STATUS_X, STATUS_Y)
splash.append(status_label)
update_status(status_label.text)

# Reference to the main text area for key updates
text_area = key_display_label

send_event("log", message="Numpad initialized! Press keys to test...")
send_event("log", message="-" * 40)

# Main loop
while True:
    currently_pressed = scan_keys(keypad, currently_pressed, text_area, number_input_label, number_buffer)
    time.sleep(0.01)  # 10ms scan delay
