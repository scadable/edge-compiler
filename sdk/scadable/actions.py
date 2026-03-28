"""
Runtime actions for controllers.

These are stubs. The edge-main runtime provides the real implementations
when controllers execute on the gateway.
"""
import time


def route(outbound_id, data, metadata=None):
    """
    Send data to an outbound destination.

    Args:
        outbound_id: The id of the outbound (e.g. "sensor-data").
        data: Dict of values, or bytes for file uploads.
        metadata: Optional dict of metadata (for S3 uploads).
    """
    raise NotImplementedError("route() is executed by the edge-main runtime")


def actuate(device, action=None, register=None, value=None):
    """
    Send a command to a device.

    Args:
        device: Device class or device id string.
        action: Action name (e.g. "capture", "reset").
        register: Modbus register address (for direct writes).
        value: Value to write.
    """
    raise NotImplementedError("actuate() is executed by the edge-main runtime")


def alert(level, message, devices=None):
    """
    Send an alert.

    Args:
        level: "info", "warning", or "critical".
        message: Alert message string.
        devices: Optional list of device ids to associate with the alert.
    """
    raise NotImplementedError("alert() is executed by the edge-main runtime")


def now():
    """Current unix timestamp in seconds."""
    return int(time.time())
