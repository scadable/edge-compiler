"""
Controller base class.

Docs: https://docs.scadable.com/docs/edge/decode-encode
"""
from .device import Device


def on_startup(func):
    """Mark a controller method to run when the gateway starts.

    The decorated method is called once after all devices are initialized,
    before the normal execute() loop begins.

    Example:
        @on_startup
        def boot(self):
            broadcast("Gateway online")
    """
    func._lifecycle = "startup"
    return func


def on_shutdown(func):
    """Mark a controller method to run before the gateway shuts down.

    The decorated method is called when the gateway receives SIGTERM
    or SIGINT, before drivers are stopped. Use this to send a
    system.shutdown() with an expected return time.

    Example:
        @on_shutdown
        def goodbye(self):
            system.shutdown(duration=2, HOURS)
    """
    func._lifecycle = "shutdown"
    return func


def on_message(message_type):
    """Mark a controller method to run when a command is received.

    The decorated method is called when the gateway receives a command
    of the specified type from the cloud (via MQTT or gRPC).

    Args:
        message_type: String identifier for the command type (e.g., "halt", "capture").

    Example:
        @on_message("halt")
        def handle_halt(self, message):
            system.shutdown(duration=message.get("duration", 2), HOURS)
    """
    def decorator(func):
        func._lifecycle = "message"
        func._message_type = message_type
        return func
    return decorator


class Controller:
    """
    Base class for controllers.

    Controllers run logic that spans multiple devices. They execute
    on a schedule and receive the latest data from all declared devices.

    Define a controller by subclassing and setting:
        id   - unique identifier
        run  - use every(5, SECONDS)
        uses - list of Device classes this controller reads from

    Override execute(self, data) with your logic.
    Access device data via data.DeviceClassName.field_name.

    Example:
        class TempMonitor(Controller):
            id = "temp-monitor"
            run = every(5, SECONDS)
            uses = [TempSensor, PressureSensor]

            def execute(self, data):
                temp = data.TempSensor.temperature
                if temp > 75:
                    alert("warning", f"High temp: {temp}")
    """

    id: str = None
    run = None
    uses: list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ == "Controller":
            return
        errors = []
        if not cls.id:
            errors.append(f"Controller '{cls.__name__}' must define 'id'")
        if not isinstance(cls.uses, list):
            errors.append(f"Controller '{cls.__name__}' - uses must be a list")
        else:
            for i, dev in enumerate(cls.uses):
                if not (isinstance(dev, type) and issubclass(dev, Device)):
                    errors.append(f"Controller '{cls.__name__}' - uses[{i}] must be a Device subclass")
        if errors:
            raise TypeError("\n".join(errors))

    def __repr__(self):
        dev_names = [d.__name__ for d in self.uses]
        return f"<Controller id={self.id!r} uses={dev_names}>"

    def execute(self, data):
        """Override this with your logic."""
        raise NotImplementedError("Override execute() with your controller logic")

    def get_storage(self, storage_id: str):
        """Get a storage backend by id. Executed by the edge-main runtime."""
        raise NotImplementedError("get_storage() is executed by the edge-main runtime")
