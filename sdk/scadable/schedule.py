"""
Schedule helper.

Docs: https://docs.scadable.com/docs/edge/device-config
"""
from .constants import SECONDS


def every(value, unit=SECONDS):
    """Define a polling or execution interval."""
    return {"interval": value, "unit": unit}
