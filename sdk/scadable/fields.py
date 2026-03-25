"""
Register and Field definitions for device data models.

Docs: https://docs.scadable.com/docs/edge/protocols
"""
from .constants import UINT16


class Register:
    """
    Modbus register definition with built-in decoding.

    The gateway reads the raw register value, applies scale and offset,
    and exposes it as a named attribute in controllers.

    Args:
        address: Modbus register address (e.g. 40001 for holding register 1).
        name: Human-readable name (becomes the attribute name in controllers).
        unit: Display unit (e.g. "°C", "bar", "V"). For documentation.
        scale: Multiply raw value by this (e.g. 0.1 to convert 235 to 23.5).
        offset: Add this after scaling (e.g. -40 for Celsius offset sensors).
        type: Register data type. Use constants: UINT16, INT16, FLOAT32, etc.
    """

    def __init__(self, address, name, unit="", scale=1.0, offset=0.0, type=UINT16):
        self.address = address
        self.name = name
        self.unit = unit
        self.scale = scale
        self.offset = offset
        self.type = type

    def __repr__(self):
        return f"Register({self.address}, {self.name!r}, scale={self.scale})"


class Field:
    """
    Serial/UART byte field definition.

    The gateway reads raw bytes from the serial port, extracts this field
    at the given offset, and exposes it as a named attribute in controllers.

    Args:
        name: Human-readable name (becomes the attribute name in controllers).
        start: Byte offset in the frame (0-based).
        length: Number of bytes for this field.
        type: Data type. Use constants: FLOAT32, UINT16, INT16, etc.
        scale: Multiply raw value by this.
        offset: Add this after scaling.
        unit: Display unit. For documentation.
    """

    def __init__(self, name, start, length, type=UINT16, scale=1.0, offset=0.0, unit=""):
        self.name = name
        self.start = start
        self.length = length
        self.type = type
        self.scale = scale
        self.offset = offset
        self.unit = unit

    def __repr__(self):
        return f"Field({self.name!r}, start={self.start}, length={self.length})"
