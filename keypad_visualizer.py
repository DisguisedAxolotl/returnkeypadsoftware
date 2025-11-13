#!/usr/bin/env python3
"""
Host-side visualization for the CircuitPython keypad demo.

Run this script on your computer while the board runs `code.py`. It listens to
the serial console, consumes JSON events, and paints a window that mirrors the
on-device TFT layout (number input, title, key display, and status text).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import pygame
import serial
import serial.tools.list_ports

Color = Tuple[int, int, int]


# --------------------------------------------------------------------------- #
# Configuration helpers
# --------------------------------------------------------------------------- #


def guess_serial_port(preferred: Optional[str]) -> Optional[str]:
    """Try to auto-detect the CircuitPython board's CDC serial port."""
    if preferred:
        return preferred

    candidates = list(serial.tools.list_ports.comports())
    for port in candidates:
        desc = f"{port.description} {port.manufacturer}".lower()
        if "circuitpython" in desc or "circuit playground" in desc or "adafruit" in desc:
            return port.device

    return candidates[0].device if len(candidates) == 1 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mirror the CircuitPython keypad TFT.")
    parser.add_argument("-p", "--port", help="Serial port path (auto-detected if omitted).")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Serial baud rate (default: 115200).")
    parser.add_argument("--fps", type=int, default=30, help="Target frame rate for the pygame display (default: 30).")
    parser.add_argument(
        "--scale",
        type=float,
        default=4.0,
        help="Scale factor applied to the device resolution for the host window (default: 4.0).",
    )
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# Display state model
# --------------------------------------------------------------------------- #


def hex_to_rgb(value: int) -> Color:
    """Convert 0xRRGGBB integer to (R, G, B)."""
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


@dataclass
class DisplayState:
    display_width: int = 135
    display_height: int = 240
    rotation: int = 270
    background_color: Color = (0, 0, 0)
    accent_color: Color = (0, 0, 255)
    text_color: Color = (255, 255, 255)
    highlight_color: Color = (0, 255, 0)
    number_text: str = "_____"
    title_text: str = "NUMPAD"
    key_text: str = "---"
    status_text: str = "Waiting for board..."
    dirty_layout: bool = False
    extras: Dict[str, str] = field(default_factory=dict)

    def apply_layout(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        rotation: Optional[int] = None,
        colors: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Update layout/appearance fields. Returns True if window size changed."""
        changed = False
        if width and width != self.display_width:
            self.display_width = width
            changed = True
        if height and height != self.display_height:
            self.display_height = height
            changed = True
        if rotation is not None:
            self.rotation = rotation
        if colors:
            if "background" in colors:
                self.background_color = hex_to_rgb(colors["background"])
            if "accent" in colors:
                self.accent_color = hex_to_rgb(colors["accent"])
            if "text" in colors:
                self.text_color = hex_to_rgb(colors["text"])
            if "highlight" in colors:
                self.highlight_color = hex_to_rgb(colors["highlight"])
        return changed

    def apply_display(self, target: str, text: str) -> None:
        """Update a text element reported by the device."""
        if target == "number_input":
            self.number_text = text
        elif target == "title":
            self.title_text = text
        elif target == "key_display":
            self.key_text = text
        elif target == "status":
            self.status_text = text
        else:
            # Track any other target for debugging.
            self.extras[target] = text


# --------------------------------------------------------------------------- #
# Serial helpers
# --------------------------------------------------------------------------- #


def open_serial(port: str, baud: int) -> serial.Serial:
    try:
        return serial.Serial(port, baudrate=baud, timeout=0.1)
    except serial.SerialException as exc:
        print(f"Failed to open serial port {port}: {exc}", file=sys.stderr)
        sys.exit(2)


def read_serial_line(ser: serial.Serial) -> Optional[str]:
    try:
        data = ser.readline()
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        sys.exit(3)
    if not data:
        return None
    return data.decode("utf-8", errors="ignore").strip()


def process_event(line: str, state: DisplayState) -> bool:
    """
    Parse a JSON event from the device.
    Returns True if a layout change requires the window to be resized.
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        print(f"[WARN] Non-JSON line from device: {line}", file=sys.stderr)
        state.status_text = "Host: bad data"
        return False

    event_type = event.get("type")
    if event_type == "display":
        target = event.get("target")
        text = event.get("text", "")
        if target:
            state.apply_display(target, text)
    elif event_type == "layout":
        return state.apply_layout(
            width=event.get("width"),
            height=event.get("height"),
            rotation=event.get("rotation"),
            colors=event.get("colors"),
        )
    elif event_type == "log":
        message = event.get("message")
        if message:
            print(message)
    elif event_type == "key":
        # Key events are already mirrored through the display updates,
        # but we keep the latest for potential debugging overlays.
        state.extras["last_key"] = f"{event.get('key')}:{event.get('action')}"
    elif event_type == "number":
        value = event.get("value")
        action = event.get("action")
        if action and value:
            state.extras["last_number"] = f"{action}:{value}"
    else:
        state.extras["last_event"] = str(event)
    return False


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def build_fonts(scale: float) -> Dict[str, pygame.font.Font]:
    base = max(int(12 * scale), 12)
    mono = "Courier New"
    return {
        "title": pygame.font.SysFont("Arial", max(int(base * 1.1), 12), bold=True),
        "number": pygame.font.SysFont(mono, max(int(base * 2.0), 14), bold=True),
        "key": pygame.font.SysFont(mono, max(int(base * 3.0), 18), bold=True),
        "status": pygame.font.SysFont(mono, max(int(base * 1.0), 12)),
    }


def desired_window_size(state: DisplayState, scale: float) -> Tuple[int, int]:
    return (int(state.display_width * scale), int(state.display_height * scale))


def render_center(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    pos: Tuple[int, int],
    color: Color,
) -> None:
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=pos)
    surface.blit(rendered, rect)


def draw(state: DisplayState, screen: pygame.Surface, fonts: Dict[str, pygame.font.Font], scale: float) -> None:
    screen.fill(state.background_color)
    width = screen.get_width()
    height = screen.get_height()

    def anchor(x: float, y: float) -> Tuple[int, int]:
        return (int(x * scale), int(y * scale))

    # Outline to mimic the hardware bezel
    pygame.draw.rect(screen, state.accent_color, screen.get_rect(), width=max(2, int(1.5 * scale)))

    # Number input (top)
    render_center(screen, fonts["number"], state.number_text, anchor(state.display_width / 2, 25), state.highlight_color)

    # Title
    render_center(screen, fonts["title"], state.title_text, anchor(state.display_width / 2, 60), state.text_color)

    # Key display (center)
    key_y = state.display_height / 2 + 20
    render_center(screen, fonts["key"], state.key_text, anchor(state.display_width / 2, key_y), state.highlight_color)

    # Status (bottom)
    render_center(
        screen,
        fonts["status"],
        state.status_text,
        anchor(state.display_width / 2, state.display_height - 30),
        state.text_color,
    )

    # Optional debug overlay at the bottom left
    if "last_key" in state.extras:
        debug_font = fonts["status"]
        text = f"last key: {state.extras['last_key']}"
        debug_surface = debug_font.render(text, True, state.accent_color)
        screen.blit(debug_surface, (int(6 * scale), height - debug_surface.get_height() - int(6 * scale)))


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #


def main() -> None:
    args = parse_args()
    port = guess_serial_port(args.port)
    if not port:
        print("Unable to auto-detect the CircuitPython serial port. Use --port to specify it.", file=sys.stderr)
        sys.exit(1)

    ser = open_serial(port, args.baud)
    print(f"Listening on {port} @ {args.baud} baud.")

    pygame.init()
    pygame.display.set_caption("CircuitPython Keypad Visualizer")

    state = DisplayState()
    scale = max(args.scale, 1.0)
    screen = pygame.display.set_mode(desired_window_size(state, scale))
    fonts = build_fonts(scale)
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        line = read_serial_line(ser)
        if line:
            layout_changed = process_event(line, state)
            if layout_changed:
                screen = pygame.display.set_mode(desired_window_size(state, scale))

        draw(state, screen, fonts, scale)
        pygame.display.flip()
        clock.tick(args.fps)

    ser.close()
    pygame.quit()


if __name__ == "__main__":
    main()
