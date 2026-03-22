PAYLOAD_SCHEMA = {
    "device_id": str,
    "protocol": str,
    "timestamp": int,
    "payload": dict,
}


class Device:
    """
    Base class for all gateway devices.
    Subclass this in your config.py to define a device.

    Required class variables:
        id         — unique identifier for this device
        protocol   — use a constant from scadable.edge.constants
        connection — subclass of ModbusConnection (or other protocol connection)
        frequency  — polling interval in seconds, use constants: FIVE_SEC, TEN_SEC etc

    Optional class variables:
        filter     — list of register names to pull (empty = pull all)

    Usage:
        class MyPLC(Device):
            id = "device-001"
            protocol = MODBUS_TCP
            connection = Connection
            frequency = FIVE_SEC
            filter = []  # empty = pull all registers
    """

    id: str = None
    protocol: str = None
    connection = None
    frequency: int = 10
    filter: list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Skip validation for intermediate base classes
        if cls.__name__ == "Device":
            return
        errors = []
        if not cls.id:
            errors.append(f"Device subclass '{cls.__name__}' must define 'id'")
        if not cls.protocol:
            errors.append(f"Device subclass '{cls.__name__}' must define 'protocol'")
        if cls.connection is None:
            errors.append(f"Device subclass '{cls.__name__}' must define 'connection'")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        return (
            f"<Device id={self.id!r} protocol={self.protocol!r} "
            f"connection={self.connection.__name__} frequency={self.frequency}s>"
        )

    def read(self, *args, **kwargs):
        raise NotImplementedError("read() will be implemented by the WASM runtime")

    def write(self, *args, **kwargs):
        raise NotImplementedError("write() will be implemented by the WASM runtime")
