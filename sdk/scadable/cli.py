"""
Scadable Edge SDK CLI

Usage:
    scadable init [name]
    scadable add device modbus-tcp|modbus-rtu|opcua|serial <name>
    scadable add controller <name>
    scadable add storage file|sqlite <name>
    scadable add outbound mqtt|s3 <name>
    scadable list [devices|controllers|storage|outbound]
    scadable validate
"""

import argparse
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_class_name(name: str) -> str:
    """Convert kebab-case name to PascalCase class name.

    Examples:
        temp-sensor  -> TempSensor
        my_device    -> MyDevice
        simple       -> Simple
    """
    return "".join(word.capitalize() for word in re.split(r"[-_]", name))


def _ensure_project() -> dict:
    """Load scadable.json from the current directory or exit."""
    if not os.path.exists("scadable.json"):
        print("Error: scadable.json not found. Run 'scadable init' first.", file=sys.stderr)
        sys.exit(1)
    with open("scadable.json") as f:
        return json.load(f)


def _write_file(directory: str, name: str, content: str) -> str:
    """Write a component file into *directory*/<name>.py and return the path."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.py")
    if os.path.exists(path):
        print(f"Error: {path} already exists.", file=sys.stderr)
        sys.exit(1)
    with open(path, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "device": {
        "modbus-tcp": """\
from scadable import Device, modbus_tcp, every, Register, SECONDS


class {class_name}(Device):
    id = "{name}"
    connection = modbus_tcp(host="${{DEVICE_HOST}}", port=502, slave=1)
    poll = every(5, SECONDS)
    registers = [
        Register(40001, "value_1", scale=0.1),
        Register(40002, "value_2", scale=0.01),
    ]
    # historian = Historian(fields=["value_1"], interval=every(5, MINUTES))
""",
        "modbus-rtu": """\
from scadable import Device, modbus_rtu, every, Register, SECONDS


class {class_name}(Device):
    id = "{name}"
    connection = modbus_rtu(port="/dev/ttyUSB0", baud=9600, slave=1)
    poll = every(10, SECONDS)
    registers = [
        Register(30001, "value_1", scale=0.1),
    ]
""",
        "opcua": """\
from scadable import Device, opcua, every, Node, SECONDS


class {class_name}(Device):
    id = "{name}"
    connection = opcua(
        host="${{OPCUA_HOST}}",
        port=4840,
        nodes=[
            Node("value_1", namespace=2, path="Channel1/Device1/Value1"),
            Node("value_2", namespace=2, path="Channel1/Device1/Value2"),
        ]
    )
    poll = every(5, SECONDS)
""",
        "serial": """\
from scadable import Device, serial_uart, every, Field, SECONDS, UINT16, FLOAT32


class {class_name}(Device):
    id = "{name}"
    connection = serial_uart(port="/dev/ttyUSB0", baud=115200)
    poll = every(1, SECONDS)
    fields = [
        Field("value_1", start=0, length=4, type=FLOAT32, scale=0.01),
        Field("value_2", start=4, length=2, type=UINT16),
    ]
""",
        "ble": """\
from scadable import Device, ble, every, Characteristic, SECONDS


class {class_name}(Device):
    id = "{name}"
    connection = ble(
        mac="${{DEVICE_MAC}}",
        service="0x180D",  # Heart Rate Service
        characteristics=[
            Characteristic("heart_rate", uuid="0x2A37"),
            Characteristic("body_sensor_location", uuid="0x2A38"),
        ]
    )
    poll = every(1, SECONDS)
""",
    },
    "controller": {
        "_default": """\
from scadable import Controller, every, route, alert, SECONDS


class {class_name}(Controller):
    id = "{name}"
    run = every(5, SECONDS)
    uses = []  # add Device classes here

    def execute(self, data):
        # Access device data: data.DeviceName.field_name
        # Send to outbound:   route("outbound-id", {{"key": value}})
        # Send alert:         alert("warning", "message")
        pass
""",
    },
    "storage": {
        "file": """\
from scadable import FileStorage, GB_1


class {class_name}(FileStorage):
    id = "{name}"
    path = "/var/data/{name}"
    max_size = GB_1
    warn_at = 80
""",
        "sqlite": """\
from scadable import SQLiteStorage, MB_256


class {class_name}(SQLiteStorage):
    id = "{name}"
    path = "/var/data/{name}.db"
    max_size = MB_256
    warn_at = 80
""",
    },
    "outbound": {
        "mqtt": """\
from scadable import MQTTOutbound


class {class_name}(MQTTOutbound):
    id = "{name}"
    devices = []  # all devices
""",
        "s3": """\
from scadable import S3Outbound


class {class_name}(S3Outbound):
    id = "{name}"
    devices = []
    storage = None   # set to a Storage class
    prefix = ""
    max_age = ""
""",
    },
}

# Map of resource type -> (directory, base class names for validation)
RESOURCE_TYPES = {
    "devices": ("devices", ["Device"]),
    "controllers": ("controllers", ["Controller"]),
    "storage": ("storage", ["FileStorage", "SQLiteStorage"]),
    "outbound": ("outbound", ["MQTTOutbound", "S3Outbound"]),
}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    """Initialise a new Scadable project."""
    name = args.name or os.path.basename(os.getcwd())

    if os.path.exists("scadable.json"):
        print("Error: scadable.json already exists in this directory.", file=sys.stderr)
        sys.exit(1)

    config = {
        "name": name,
        "version": "1.0.0",
        "sdk": "scadable-edge-sdk",
    }
    with open("scadable.json", "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    for d in ("devices", "controllers", "storage", "outbound"):
        os.makedirs(d, exist_ok=True)

    print(f"Initialised project '{name}'")
    print("  created scadable.json")
    print("  created devices/")
    print("  created controllers/")
    print("  created storage/")
    print("  created outbound/")


def cmd_add(args):
    """Add a component to the project."""
    _ensure_project()

    resource = args.resource
    name = args.name

    if resource == "device":
        subtype = args.subtype
        if subtype not in TEMPLATES["device"]:
            print(f"Error: unknown device type '{subtype}'. "
                  f"Choose from: {', '.join(TEMPLATES['device'].keys())}", file=sys.stderr)
            sys.exit(1)
        template = TEMPLATES["device"][subtype]
        directory = "devices"
    elif resource == "controller":
        template = TEMPLATES["controller"]["_default"]
        directory = "controllers"
    elif resource == "storage":
        subtype = args.subtype
        if subtype not in TEMPLATES["storage"]:
            print(f"Error: unknown storage type '{subtype}'. "
                  f"Choose from: {', '.join(TEMPLATES['storage'].keys())}", file=sys.stderr)
            sys.exit(1)
        template = TEMPLATES["storage"][subtype]
        directory = "storage"
    elif resource == "outbound":
        subtype = args.subtype
        if subtype not in TEMPLATES["outbound"]:
            print(f"Error: unknown outbound type '{subtype}'. "
                  f"Choose from: {', '.join(TEMPLATES['outbound'].keys())}", file=sys.stderr)
            sys.exit(1)
        template = TEMPLATES["outbound"][subtype]
        directory = "outbound"
    else:
        print(f"Error: unknown resource type '{resource}'.", file=sys.stderr)
        sys.exit(1)

    class_name = to_class_name(name)
    content = template.format(class_name=class_name, name=name)
    path = _write_file(directory, name, content)
    print(f"Created {path}  ({class_name})")


def cmd_list(args):
    """List project components."""
    _ensure_project()

    if args.type:
        types_to_show = [args.type]
    else:
        types_to_show = list(RESOURCE_TYPES.keys())

    for rtype in types_to_show:
        if rtype not in RESOURCE_TYPES:
            print(f"Error: unknown type '{rtype}'. "
                  f"Choose from: {', '.join(RESOURCE_TYPES.keys())}", file=sys.stderr)
            sys.exit(1)
        directory, _ = RESOURCE_TYPES[rtype]
        files = sorted(f for f in os.listdir(directory) if f.endswith(".py")) if os.path.isdir(directory) else []
        print(f"{rtype}/ ({len(files)})")
        for f in files:
            print(f"  {f}")


def cmd_validate(args):
    """Validate all project components."""
    _ensure_project()

    errors = 0
    checked = 0

    for rtype, (directory, base_classes) in RESOURCE_TYPES.items():
        if not os.path.isdir(directory):
            continue
        files = sorted(f for f in os.listdir(directory) if f.endswith(".py"))
        for filename in files:
            filepath = os.path.join(directory, filename)
            checked += 1
            try:
                with open(filepath) as f:
                    source = f.read()
                # Check for syntax errors first
                try:
                    compile(source, filepath, 'exec')
                except SyntaxError as e:
                    print(f"  ERROR {filepath} - syntax error on line {e.lineno}: {e.msg}")
                    errors += 1
                    continue
                # Check that the file contains a class inheriting from one of the expected base classes
                pattern = r"class\s+\w+\((" + "|".join(base_classes) + r")\)"
                if not re.search(pattern, source):
                    print(f"  ERROR {filepath} - no subclass of {'/'.join(base_classes)} found")
                    errors += 1
                    continue

                # For devices, validate historian fields match register/characteristic/field names
                if rtype == "device" and "historian" in source and "Historian" in source:
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location("_validate_mod", filepath)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        for attr_name in dir(mod):
                            cls = getattr(mod, attr_name)
                            if isinstance(cls, type) and hasattr(cls, 'historian') and cls.historian is not None:
                                # Collect valid field names from registers, fields, and characteristics
                                valid_names = set()
                                for r in getattr(cls, 'registers', []):
                                    valid_names.add(r.name)
                                for f in getattr(cls, 'fields', []):
                                    valid_names.add(f.name)
                                for c in getattr(cls, 'characteristics', []):
                                    valid_names.add(c.name)
                                # Check each historian field
                                for hf in cls.historian.fields:
                                    if hf not in valid_names:
                                        avail = ", ".join(sorted(valid_names)) if valid_names else "none"
                                        print(f"  ERROR {filepath} - historian field '{hf}' not found in device registers (available: {avail})")
                                        errors += 1
                    except Exception:
                        pass  # Import errors are OK here - syntax was already validated

                print(f"  ok   {filepath}")
            except Exception as e:
                print(f"  ERROR {filepath} - {e}")
                errors += 1

    if checked == 0:
        print("No component files found.")
    else:
        print(f"\nChecked {checked} file(s), {errors} error(s).")

    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scadable",
        description="Scadable Edge SDK CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Initialise a new project")
    p_init.add_argument("name", nargs="?", default=None, help="Project name (defaults to directory name)")

    # add
    p_add = sub.add_parser("add", help="Add a component")
    p_add.add_argument("resource", choices=["device", "controller", "storage", "outbound"])
    p_add.add_argument("subtype", nargs="?", default=None,
                       help="Sub-type (e.g. modbus-tcp, file, mqtt). Required for device/storage/outbound.")
    p_add.add_argument("name", nargs="?", default=None, help="Component name")

    # list
    p_list = sub.add_parser("list", help="List components")
    p_list.add_argument("type", nargs="?", default=None,
                        choices=list(RESOURCE_TYPES.keys()),
                        help="Filter by type")

    # validate
    sub.add_parser("validate", help="Validate all components")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "add":
        # For resources that need a subtype, the positional args shift:
        # "add device modbus-tcp temp-sensor" -> resource=device, subtype=modbus-tcp, name=temp-sensor
        # "add controller monitor"            -> resource=controller, subtype=monitor, name=None
        # For controller, subtype is actually the name (no subtype needed).
        if args.resource == "controller":
            # subtype holds the name, name is None
            if args.subtype is None:
                print("Error: name is required. Usage: scadable add controller <name>", file=sys.stderr)
                sys.exit(1)
            args.name = args.subtype
            args.subtype = None
        else:
            # device, storage, outbound all require subtype + name
            if args.subtype is None or args.name is None:
                print(f"Error: subtype and name are required. "
                      f"Usage: scadable add {args.resource} <type> <name>", file=sys.stderr)
                sys.exit(1)
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
