#!/usr/bin/env python3
"""
convert.py - Extract all resource definitions from a v1.0 Scadable SDK project.

Scans devices/, controllers/, storage/, outbound/ directories for Python files
containing Device, Controller, FileStorage, SQLiteStorage, MQTTOutbound, S3Outbound
subclasses. Outputs a single JSON object with all extracted configs to stdout.

Usage: python3 convert.py <repo_dir>
"""
import sys
import json
import importlib.util
import os
import inspect


def setup_paths(repo_dir):
    """Add repo root and SDK to sys.path so imports resolve."""
    if repo_dir not in sys.path:
        sys.path.insert(0, repo_dir)

    # If scadable isn't installed, check for bundled SDK next to this script
    try:
        import scadable
    except ImportError:
        sdk_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sdk")
        if os.path.isdir(sdk_dir) and sdk_dir not in sys.path:
            sys.path.insert(0, sdk_dir)


def load_module(path, module_name):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def find_py_files(directory):
    """Find all .py files in a directory (non-recursive)."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".py") and not f.startswith("_")
    )


def poll_to_seconds(poll):
    """Convert a poll/run dict to seconds."""
    if poll is None:
        return 0
    if isinstance(poll, dict):
        interval = poll.get("interval", 0)
        unit = poll.get("unit", "seconds")
        if unit == "minutes":
            return interval * 60
        elif unit == "hours":
            return interval * 3600
        return interval
    return int(poll)


def map_connection(conn):
    """Map SDK connection dict to edge-main ConnectionConfig fields."""
    if conn is None:
        return {}, ""

    conn_type = conn.get("type", "")
    result = {}

    if conn_type == "modbus-tcp":
        result["host"] = conn.get("host", "")
        result["port"] = conn.get("port", 502)
        result["slave_id"] = conn.get("slave", 1)
        result["timeout"] = conn.get("timeout", 5.0)
        result["retries"] = conn.get("retries", 3)

    elif conn_type == "modbus-rtu":
        result["serial_port"] = conn.get("port", "")
        result["baudrate"] = conn.get("baud", 9600)
        result["slave_id"] = conn.get("slave", 1)
        result["parity"] = conn.get("parity", "N")
        result["stopbits"] = conn.get("stopbits", 1)
        result["bytesize"] = conn.get("bytesize", 8)
        result["timeout"] = conn.get("timeout", 5.0)

    elif conn_type == "opcua":
        result["host"] = conn.get("host", "")
        result["port"] = conn.get("port", 4840)
        nodes = conn.get("nodes", [])
        result["node_ids"] = [n[1] for n in nodes] if nodes else []
        result["security_policy"] = conn.get("security", "None")
        result["username"] = conn.get("username", "")
        result["password"] = conn.get("password", "")

    elif conn_type == "serial":
        result["serial_port"] = conn.get("port", "")
        result["baudrate"] = conn.get("baud", 115200)
        result["parity"] = conn.get("parity", "N")
        result["stopbits"] = conn.get("stopbits", 1)
        result["bytesize"] = conn.get("bytesize", 8)
        result["timeout"] = conn.get("timeout", 5.0)

    elif conn_type == "ble":
        result["mac"] = conn.get("mac", "")
        result["service_uuid"] = conn.get("service", "")
        chars = conn.get("characteristics", [])
        result["characteristics"] = [{"name": c[0], "uuid": c[1]} for c in chars] if chars else []
        result["scan_timeout"] = conn.get("scan_timeout", 10.0)

    return result, conn_type


def build_decode(cls, conn_type, conn):
    """Build DecodeConfig from registers, fields, or OPC-UA nodes."""
    mappings = []

    # Modbus registers
    registers = getattr(cls, "registers", None)
    if registers:
        for reg in registers:
            mappings.append({
                "from": f"reg_{reg.address}",
                "to": reg.name,
                "scale": getattr(reg, "scale", 1.0) or 1.0,
                "offset": getattr(reg, "offset", 0.0) or 0.0,
            })

    # Serial fields
    fields = getattr(cls, "fields", None)
    if fields:
        for field in fields:
            mapping = {
                "from": f"field_{field.start}_{field.length}",
                "to": field.name,
                "scale": getattr(field, "scale", 1.0) or 1.0,
                "offset": getattr(field, "offset", 0.0) or 0.0,
                "field_type": getattr(field, "type", ""),
                "start": field.start,
                "length": field.length,
            }
            mappings.append(mapping)

    # OPC-UA node name mappings
    if conn_type == "opcua" and conn:
        nodes = conn.get("nodes", [])
        for name, node_id in (nodes or []):
            mappings.append({
                "from": node_id,
                "to": name,
                "scale": 1.0,
                "offset": 0.0,
            })

    if not mappings:
        return None

    return {
        "transform_type": "declarative",
        "mappings": mappings,
    }


def extract_devices(modules):
    """Extract Device subclasses from loaded modules."""
    from scadable.device import Device

    devices = []
    for mod in modules:
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type) or not issubclass(obj, Device) or obj is Device:
                continue

            conn_raw = getattr(obj, "connection", None)
            connection, conn_type = map_connection(conn_raw)
            frequency = poll_to_seconds(getattr(obj, "poll", None))
            decode = build_decode(obj, conn_type, conn_raw)

            device = {
                "device_id": obj.id,
                "protocol": conn_type,
                "frequency": frequency,
                "connection": connection,
            }
            if decode:
                device["decode"] = decode

            # Extract historian config if present
            historian = getattr(obj, "historian", None)
            if historian is not None:
                hist_config = {
                    "fields": historian.fields or [],
                    "condition": getattr(historian, "condition", "all") or "all",
                }
                hist_interval = getattr(historian, "interval", None)
                if hist_interval is not None:
                    hist_config["interval"] = poll_to_seconds(hist_interval)
                else:
                    hist_config["interval"] = frequency  # default to device poll rate
                device["historian"] = hist_config

            devices.append(device)

    return devices


def extract_storage(modules):
    """Extract FileStorage/SQLiteStorage subclasses."""
    from scadable.storage import FileStorage, SQLiteStorage

    results = []
    for mod in modules:
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if obj in (FileStorage, SQLiteStorage):
                continue

            if issubclass(obj, FileStorage):
                storage_type = "file"
            elif issubclass(obj, SQLiteStorage):
                storage_type = "sqlite"
            else:
                continue

            results.append({
                "id": obj.id,
                "storage_type": storage_type,
                "path": obj.path,
                "max_size": obj.max_size,
                "warning_threshold": getattr(obj, "warn_at", 80),
            })

    return results


def extract_outbound(modules):
    """Extract MQTTOutbound/S3Outbound subclasses."""
    from scadable.outbound import MQTTOutbound, S3Outbound
    from scadable.device import Device

    results = []
    for mod in modules:
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if obj in (MQTTOutbound, S3Outbound):
                continue

            if issubclass(obj, S3Outbound):
                outbound_type = "s3"
            elif issubclass(obj, MQTTOutbound):
                outbound_type = "mqtt"
            else:
                continue

            # Resolve device class references to IDs
            device_ids = []
            for dev in (obj.devices or []):
                if isinstance(dev, type) and issubclass(dev, Device):
                    device_ids.append(dev.id)
                elif isinstance(dev, str):
                    device_ids.append(dev)

            entry = {
                "id": obj.id,
                "outbound_type": outbound_type,
                "devices": device_ids,
            }

            # S3-specific fields
            if outbound_type == "s3":
                storage_cls = getattr(obj, "storage", None)
                if storage_cls and isinstance(storage_cls, type):
                    entry["storage"] = storage_cls.id
                else:
                    entry["storage"] = ""
                entry["prefix"] = getattr(obj, "prefix", "") or ""
                entry["max_age"] = getattr(obj, "max_age", "") or ""

            results.append(entry)

    return results


def extract_controllers(modules, base_dir):
    """Extract Controller subclasses."""
    from scadable.controller import Controller
    from scadable.device import Device

    results = []
    for mod in modules:
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type) or not issubclass(obj, Controller) or obj is Controller:
                continue

            # Resolve uses to device IDs
            use_ids = []
            for dev in (obj.uses or []):
                if isinstance(dev, type) and issubclass(dev, Device):
                    use_ids.append(dev.id)
                elif isinstance(dev, str):
                    use_ids.append(dev)

            interval = poll_to_seconds(getattr(obj, "run", None))

            # Get source file path relative to repo root
            source_file = ""
            mod_file = getattr(mod, "__file__", "")
            if mod_file and base_dir:
                source_file = os.path.relpath(mod_file, base_dir)

            results.append({
                "id": obj.id,
                "interval": interval,
                "uses": use_ids,
                "source_file": source_file,
            })

    return results


def load_directory(repo_dir, dirname):
    """Load all .py modules from a directory, returning the loaded modules."""
    directory = os.path.join(repo_dir, dirname)
    modules = []
    for path in find_py_files(directory):
        basename = os.path.splitext(os.path.basename(path))[0]
        module_name = f"{dirname}.{basename}"
        try:
            mod = load_module(path, module_name)
            modules.append(mod)
        except Exception as e:
            print(f"Error loading {path}: {e}", file=sys.stderr)
            raise
    return modules


def main():
    if len(sys.argv) < 2:
        print("Usage: convert.py <repo_dir>", file=sys.stderr)
        sys.exit(1)

    repo_dir = os.path.abspath(sys.argv[1])
    setup_paths(repo_dir)

    result = {
        "devices": [],
        "storage": [],
        "outbound": [],
        "controllers": [],
    }

    errors = []

    # Load modules from each directory
    # Order matters: devices first (controllers/outbound reference them)
    try:
        device_modules = load_directory(repo_dir, "devices")
        storage_modules = load_directory(repo_dir, "storage")
        outbound_modules = load_directory(repo_dir, "outbound")
        controller_modules = load_directory(repo_dir, "controllers")
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    # Extract
    try:
        result["devices"] = extract_devices(device_modules)
        result["storage"] = extract_storage(storage_modules)
        result["outbound"] = extract_outbound(outbound_modules)
        result["controllers"] = extract_controllers(controller_modules, repo_dir)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in result.values())
    if total == 0:
        print("Warning: no resource definitions found", file=sys.stderr)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
