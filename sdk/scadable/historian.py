"""Historian configuration for device telemetry storage.

The Historian defines which device fields are persisted to the
configured storage destination (webhook, database, or S3). Fields
not listed are still available in the live WebSocket stream but
are not stored long-term.

The historian config is compiled and used by the cloud platform
to filter incoming telemetry. The gateway sends everything - the
cloud decides what to keep.
"""


class Historian:
    """Configure which device fields are stored in the data historian.

    Args:
        fields: List of field names to store. Must match register,
            characteristic, or field names defined on the device.
        interval: How often to store readings. Defaults to the device
            poll rate if not specified. Use every(N, UNIT) syntax.
        condition: When to store. Options:
            - "all" (default): store every reading at the interval
            - "on_change": only store when the value changes
            - "> N" or "< N": only store when value exceeds threshold

    Examples:
        # Store temperature and humidity every 5 minutes
        historian = Historian(
            fields=["temperature", "humidity"],
            interval=every(5, MINUTES),
        )

        # Store sound level every 30 seconds, only when it changes
        historian = Historian(
            fields=["sound_level"],
            interval=every(30, SECONDS),
            condition="on_change",
        )

        # Store all fields at the device poll rate (simplest)
        historian = Historian(fields=["temperature", "humidity", "pressure"])
    """

    def __init__(self, fields=None, interval=None, condition="all"):
        self.fields = fields or []
        self.interval = interval
        self.condition = condition
