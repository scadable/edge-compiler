"""
Device base class.

Docs: https://docs.scadable.com/docs/edge/device-config
"""


class Device:
    """
    Base class for all devices.

    Define a device by subclassing and setting:
        id         - unique identifier (short, lowercase, with hyphens)
        connection - use modbus_tcp(), modbus_rtu(), opcua(), or serial_uart()
        poll       - use every(5, SECONDS)
        registers  - list of Register() for Modbus devices
        fields     - list of Field() for Serial/UART devices

    Example:
        class TempSensor(Device):
            id = "temp-sensor"
            connection = modbus_tcp(host="192.168.1.100")
            poll = every(5, SECONDS)
            registers = [
                Register(40001, "temperature", scale=0.1),
            ]
    """

    id: str = None
    name: str = ""
    connection = None
    poll = None
    registers: list = []
    fields: list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ == "Device":
            return
        errors = []
        if not cls.id:
            errors.append(f"Device '{cls.__name__}' must define 'id'")
        if cls.connection is None:
            errors.append(f"Device '{cls.__name__}' must define 'connection'")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        proto = self.connection.get("type", "unknown") if isinstance(self.connection, dict) else "unknown"
        return f"<Device id={self.id!r} protocol={proto}>"
