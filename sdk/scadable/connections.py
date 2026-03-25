"""
Connection helpers. Each returns a simple config dict.
No dataclasses, no boilerplate.

Docs: https://docs.scadable.com/docs/edge/protocols
"""
from .constants import SECURITY_NONE


def modbus_tcp(host, port=502, slave=1, timeout=5.0, retries=3):
    """Modbus TCP connection to a PLC, power meter, VFD, etc."""
    return {
        "type": "modbus-tcp",
        "host": host,
        "port": port,
        "slave": slave,
        "timeout": timeout,
        "retries": retries,
    }


def modbus_rtu(port, baud=9600, slave=1, parity="N", stopbits=1, bytesize=8, timeout=5.0):
    """Modbus RTU connection over RS-485 serial."""
    return {
        "type": "modbus-rtu",
        "port": port,
        "baud": baud,
        "slave": slave,
        "parity": parity,
        "stopbits": stopbits,
        "bytesize": bytesize,
        "timeout": timeout,
    }


def opcua(host, port=4840, nodes=None, security=SECURITY_NONE, username="", password=""):
    """OPC-UA connection to Ignition, Kepware, Siemens, etc."""
    return {
        "type": "opcua",
        "host": host,
        "port": port,
        "nodes": nodes or [],
        "security": security,
        "username": username,
        "password": password,
    }


def serial_uart(port, baud=115200, parity="N", stopbits=1, bytesize=8, timeout=5.0):
    """Serial/UART connection to ESP32, Arduino, custom devices."""
    return {
        "type": "serial",
        "port": port,
        "baud": baud,
        "parity": parity,
        "stopbits": stopbits,
        "bytesize": bytesize,
        "timeout": timeout,
    }
