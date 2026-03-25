"""
Scadable Edge SDK

Write simple Python classes. The SDK handles everything else.

    from scadable import Device, modbus_tcp, every, Register, SECONDS

    class TempSensor(Device):
        id = "temp-sensor"
        connection = modbus_tcp(host="192.168.1.100")
        poll = every(5, SECONDS)
        registers = [Register(40001, "temperature", scale=0.1)]
"""

from .device import Device
from .controller import Controller
from .storage import FileStorage, SQLiteStorage
from .outbound import MQTTOutbound, S3Outbound
from .connections import modbus_tcp, modbus_rtu, opcua, serial_uart
from .fields import Register, Field
from .schedule import every
from .actions import route, actuate, alert, now
from . import system
from .constants import (
    SECONDS, MINUTES, HOURS,
    MB_64, MB_128, MB_256, MB_512, GB_1, GB_2, GB_5,
    INT16, UINT16, INT32, UINT32, FLOAT32, FLOAT64,
    FLOAT, UINT8, INT8,
    SECURITY_NONE, SECURITY_BASIC256, SECURITY_BASIC128,
)
