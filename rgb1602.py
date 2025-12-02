"""CircuitPython driver for a Grove RGB 16x2 LCD (LCD1602) over I2C.

The module exposes the :class:`RGB1602` class, which provides a handful of
high-level helpers to write text, move the cursor, and adjust the RGB
backlight. Typical usage::

    import rgb1602

    lcd = rgb1602.RGB1602(16, 2)  # 16 columns, 2 rows
    lcd.set_backlight(0, 120, 255)
    lcd.write_text("Hello, world!", row=0)
    lcd.write_text("Line two", row=1, clear_line=True)

This is a lightweight port of the vendor MicroPython example to CircuitPython,
using :mod:`adafruit_bus_device` helpers for I2C access.
"""
from time import sleep
import board
import busio
from adafruit_bus_device.i2c_device import I2CDevice

__all__ = ["RGB1602"]

LCD_ADDRESS = 0x7C >> 1
RGB_ADDRESS = 0xC0 >> 1

REG_RED = 0x04
REG_GREEN = 0x03
REG_BLUE = 0x02
REG_MODE1 = 0x00
REG_MODE2 = 0x01
REG_OUTPUT = 0x08

LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x8DOTS = 0x00


def _default_i2c() -> busio.I2C:
    """Create an I2C instance at 400kHz using the board default pins."""
    return busio.I2C(board.SCL, board.SDA, frequency=400_000)


class RGB1602:
    """Minimal CircuitPython driver for the RGB 16x2 LCD.

    Parameters
    ----------
    col
        Number of columns on the display.
    row
        Number of rows on the display.
    i2c
        Optional :class:`busio.I2C` instance. If omitted, the default board I2C
        bus is used at 400 kHz.
    """

    def __init__(self, col: int, row: int, i2c: busio.I2C | None = None) -> None:
        self._row = row
        self._col = col
        self._i2c = i2c or _default_i2c()
        self._lcd = I2CDevice(self._i2c, LCD_ADDRESS)
        self._rgb = I2CDevice(self._i2c, RGB_ADDRESS)

        self._showfunction = LCD_4BITMODE | LCD_1LINE | LCD_5x8DOTS
        self._showcontrol = LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF
        self._showmode = LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT

        self.begin(self._row, self._col)

    def _write_lcd(self, control: int, data: int) -> None:
        with self._lcd as lcd:
            lcd.write(bytes([control, data & 0xFF]))

    def command(self, cmd: int) -> None:
        self._write_lcd(0x80, cmd)

    def write(self, data: int) -> None:
        self._write_lcd(0x40, data)

    def _set_reg(self, reg: int, data: int) -> None:
        with self._rgb as rgb:
            rgb.write(bytes([reg & 0xFF, data & 0xFF]))

    def setRGB(self, r: int, g: int, b: int) -> None:
        """Set backlight color using raw 0-255 RGB values."""

        self._set_reg(REG_RED, r)
        self._set_reg(REG_GREEN, g)
        self._set_reg(REG_BLUE, b)

    def set_backlight(self, r: int, g: int, b: int) -> None:
        """User-friendly alias for :meth:`setRGB`."""

        self.setRGB(r, g, b)

    def setCursor(self, col: int, row: int) -> None:
        """Move the cursor to a column/row location."""

        col = col & 0xFF
        if row == 0:
            col |= 0x80
        else:
            col |= 0xC0
        with self._lcd as lcd:
            lcd.write(bytes([0x80, col]))

    def clear(self) -> None:
        """Clear the display and reset the cursor position."""

        self.command(LCD_CLEARDISPLAY)
        sleep(0.002)
        self.home()

    def home(self) -> None:
        """Return the cursor to the origin (0, 0)."""

        self.command(LCD_RETURNHOME)
        sleep(0.002)

    def printout(self, arg) -> None:  # noqa: ANN001 - keep compatibility
        """Write the raw string representation starting at the current cursor."""

        text = str(arg)
        for byte in text.encode("utf-8"):
            self.write(byte)

    def write_text(
        self,
        text: str,
        *,
        col: int | None = None,
        row: int | None = None,
        clear_line: bool = False,
    ) -> None:
        """Write text at an optional position.

        Parameters
        ----------
        text
            The string to display.
        col, row
            Optional zero-based position. If provided, the cursor is moved to
            the given location before writing.
        clear_line
            If ``True``, the remainder of the line is blanked after writing.
        """

        if col is not None or row is not None:
            self.setCursor(col or 0, row or 0)

        self.printout(text)

        if clear_line and row is not None:
            # Pad with spaces to erase the rest of the line.
            remaining = max(self._col - (col or 0) - len(text), 0)
            if remaining:
                self.printout(" " * remaining)

    def display(self) -> None:
        """Turn the display on."""

        self._showcontrol |= LCD_DISPLAYON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def no_display(self) -> None:
        """Turn the display off (backlight unaffected)."""

        self._showcontrol &= ~LCD_DISPLAYON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def show_cursor(self) -> None:
        """Enable the underline cursor."""

        self._showcontrol |= LCD_CURSORON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def hide_cursor(self) -> None:
        """Disable the underline cursor."""

        self._showcontrol &= ~LCD_CURSORON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def blink_on(self) -> None:
        """Enable cursor blinking."""

        self._showcontrol |= LCD_BLINKON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def blink_off(self) -> None:
        """Disable cursor blinking."""

        self._showcontrol &= ~LCD_BLINKON
        self.command(LCD_DISPLAYCONTROL | self._showcontrol)

    def begin(self, cols: int, lines: int) -> None:
        """Initialize LCD and backlight state.

        This is automatically invoked during construction, but can be called
        again if the LCD is power-cycled while the microcontroller remains
        running.
        """

        if lines > 1:
            self._showfunction |= LCD_2LINE
        self._numlines = lines
        self._currline = 0

        sleep(0.05)
        self.command(LCD_FUNCTIONSET | self._showfunction)
        sleep(0.005)
        self.command(LCD_FUNCTIONSET | self._showfunction)
        sleep(0.005)
        self.command(LCD_FUNCTIONSET | self._showfunction)
        self.command(LCD_FUNCTIONSET | self._showfunction)

        self.display()
        self.command(LCD_ENTRYMODESET | self._showmode)
        self.clear()

        self._set_reg(REG_MODE1, 0)
        self._set_reg(REG_OUTPUT, 0xFF)
        self._set_reg(REG_MODE2, 0x20)
        self.setColorWhite()

    def setColorWhite(self) -> None:
        """Set the backlight to white."""

        self.setRGB(255, 255, 255)