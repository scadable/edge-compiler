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


class Node:
    """
    OPC-UA node definition.

    Defines a single node to read from an OPC-UA server. The gateway
    subscribes to this node and exposes the value as a named attribute
    in controllers.

    Args:
        name: Human-readable name (becomes the attribute name in controllers).
        namespace: OPC-UA namespace index (default 2).
        path: String node identifier (e.g. "Tank/Temperature"). For string-based nodes.
        identifier: Numeric node identifier (e.g. 1001). For numeric nodes.

    Examples:
        Node("temperature", namespace=2, path="Channel1/Device1/Temperature")
        Node("pump_speed", namespace=2, identifier=1001)
    """

    def __init__(self, name, namespace=2, path=None, identifier=None):
        self.name = name
        self.namespace = namespace
        self.path = path
        self.identifier = identifier

    @property
    def node_id(self):
        """Generate the OPC-UA node ID string (e.g. 'ns=2;s=Tank/Temp')."""
        if self.path:
            return f"ns={self.namespace};s={self.path}"
        elif self.identifier is not None:
            return f"ns={self.namespace};i={self.identifier}"
        return f"ns={self.namespace};s={self.name}"

    def __repr__(self):
        if self.path:
            return f"Node({self.name!r}, namespace={self.namespace}, path={self.path!r})"
        return f"Node({self.name!r}, namespace={self.namespace}, identifier={self.identifier})"


class Characteristic:
    """
    BLE GATT characteristic definition.

    Defines a single data point to read from a BLE device. The gateway
    subscribes to this characteristic and exposes the value as a named
    attribute in controllers.

    Args:
        name: Human-readable name (becomes the attribute name in controllers).
        uuid: BLE characteristic UUID (e.g. "0x2A37" for Heart Rate Measurement).

    Examples:
        Characteristic("heart_rate", uuid="0x2A37")
        Characteristic("spo2", uuid="0x2A5E")
    """

    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid

    def __repr__(self):
        return f"Characteristic({self.name!r}, uuid={self.uuid!r})"
