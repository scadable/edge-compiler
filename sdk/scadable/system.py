"""
System-level gateway operations.

These control the gateway itself, not individual devices.
All operations are executed by the edge-main runtime.
"""


def restart():
    """Restart the gateway service."""
    raise NotImplementedError("restart() is executed by the edge-main runtime")


def halt():
    """Stop all services and power down the gateway."""
    raise NotImplementedError("halt() is executed by the edge-main runtime")


def sleep(seconds):
    """Wait for the specified seconds before the next operation."""
    raise NotImplementedError("sleep() is executed by the edge-main runtime")
