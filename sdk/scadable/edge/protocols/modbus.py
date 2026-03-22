from dataclasses import dataclass
from typing import Optional
from .base import Protocol
from ..constants import MODBUS_TCP, MODBUS_RTU

@dataclass
class ModbusConnection:
    """
    Base Modbus connection config.
    Subclass this in your config.py and override the fields you need.

    Usage:
        @dataclass
        class Connection(ModbusConnection):
            host: str = "192.168.1.100"
            port: int = 502
            slave_id: int = 1
    """
    host: str = ""
    port: int = 502
    slave_id: int = 1
    timeout: float = 5.0
    retries: int = 3
    # RTU only — leave None for TCP
    serial_port: Optional[str] = None
    baudrate: int = 9600
    parity: str = "N"     # N=none, E=even, O=odd
    stopbits: int = 1
    bytesize: int = 8

class ModbusProtocol(Protocol):
    def read(self, *args, **kwargs):
        raise NotImplementedError

    def write(self, *args, **kwargs):
        raise NotImplementedError
