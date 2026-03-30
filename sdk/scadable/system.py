"""System-level functions for gateway lifecycle management.

These functions are stubs in the SDK. The actual implementation runs
in the edge-main gateway runtime. The SDK defines the interface so
controllers can reference them and the compiler can extract metadata.
"""


def shutdown(duration=None, unit=None):
    """Graceful shutdown with optional expected return time.

    The gateway sends a SessionEnd message to the cloud before exiting.
    If duration and unit are provided, the cloud expects the gateway
    to reconnect within that window and alerts if it does not.

    Args:
        duration: How long until the gateway is expected back. None = indefinite.
        unit: Time unit (SECONDS, MINUTES, HOURS from scadable.constants).

    Examples:
        system.shutdown()                     # Shutdown indefinitely
        system.shutdown(duration=2, HOURS)    # Back in 2 hours
        system.shutdown(duration=30, MINUTES) # Back in 30 minutes
    """
    raise NotImplementedError("Executed by edge-main runtime")


def restart():
    """Restart the gateway service."""
    raise NotImplementedError("Executed by edge-main runtime")


def broadcast(message, metadata=None):
    """Send a message to all notification-enabled users in the namespace.

    Broadcasts bypass individual notification preferences - all users
    with active notifications receive the message.

    Args:
        message: Human-readable message string.
        metadata: Optional dict of key-value pairs.
    """
    raise NotImplementedError("Executed by edge-main runtime")
