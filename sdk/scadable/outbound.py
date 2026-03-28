"""
Outbound base classes.

Docs: https://docs.scadable.com/docs/edge/outbound
"""
from .device import Device


class MQTTOutbound:
    """
    Scadable-managed MQTT outbound for telemetry data.

    Streams device readings to the cloud. The system handles
    endpoint, certificates, and topic routing automatically.

    Example:
        class SensorData(MQTTOutbound):
            id = "sensor-data"
            devices = []  # all devices
    """

    id: str = None
    devices: list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in ("MQTTOutbound", "S3Outbound"):
            return
        errors = []
        if not cls.id:
            errors.append(f"Outbound '{cls.__name__}' must define 'id'")
        if not isinstance(cls.devices, list):
            errors.append(f"Outbound '{cls.__name__}' - devices must be a list")
        else:
            for i, dev in enumerate(cls.devices):
                if not (isinstance(dev, type) and issubclass(dev, Device)):
                    errors.append(f"Outbound '{cls.__name__}' - devices[{i}] must be a Device subclass")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        dev_names = [d.__name__ for d in self.devices] if self.devices else ["all"]
        return f"<MQTTOutbound id={self.id!r} devices={dev_names}>"


class S3Outbound:
    """
    Scadable-managed S3 outbound for file uploads.

    Uploads files (images, binary data) from local storage to the cloud.
    The system handles bucket, presigned URLs, and retry automatically.

    Example:
        class Photos(S3Outbound):
            id = "high-temp-photos"
            devices = [FactoryCamera]
            storage = CameraImages
            prefix = "images/{date}/{device_id}/"
            max_age = "30d"
    """

    id: str = None
    devices: list = []
    storage = None
    prefix: str = ""
    max_age: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in ("MQTTOutbound", "S3Outbound"):
            return
        errors = []
        if not cls.id:
            errors.append(f"Outbound '{cls.__name__}' must define 'id'")
        if not isinstance(cls.devices, list):
            errors.append(f"Outbound '{cls.__name__}' - devices must be a list")
        else:
            for i, dev in enumerate(cls.devices):
                if not (isinstance(dev, type) and issubclass(dev, Device)):
                    errors.append(f"Outbound '{cls.__name__}' - devices[{i}] must be a Device subclass")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        dev_names = [d.__name__ for d in self.devices] if self.devices else ["all"]
        return f"<S3Outbound id={self.id!r} devices={dev_names}>"
