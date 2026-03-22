#!/usr/bin/env python3
"""
convert.py — Extract device definitions from Python config files and output as JSON.

This script is called by the Go compiler. It walks the repository for config.py files,
imports them, extracts Device subclass definitions, and outputs a JSON array of device
configurations to stdout.

Usage: python3 convert.py <repo_dir>
"""
import sys
import json
import importlib.util
import os


def load_module(path):
    """Load a Python module from a file path."""
    # Add the repo root to sys.path so imports work
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(path)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    spec = importlib.util.spec_from_file_location("config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_devices(mod):
    """Extract Device subclass definitions from a loaded module."""
    from scadable.edge.device import Device

    devices = []
    for name in dir(mod):
        obj = getattr(mod, name)
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, Device) or obj is Device:
            continue

        # Instantiate the connection dataclass to get defaults
        try:
            conn = obj.connection()
        except Exception as e:
            print(f"Warning: failed to instantiate connection for {name}: {e}", file=sys.stderr)
            continue

        device = {
            "device_id": obj.id,
            "protocol": obj.protocol,
            "frequency": obj.frequency,
            "filter": getattr(obj, "filter", []) or [],
            "connection": {
                "host": getattr(conn, "host", "") or "",
                "port": getattr(conn, "port", 502),
                "slave_id": getattr(conn, "slave_id", 1),
                "timeout": getattr(conn, "timeout", 5.0),
                "retries": getattr(conn, "retries", 3),
                "serial_port": getattr(conn, "serial_port", None) or "",
                "baudrate": getattr(conn, "baudrate", 9600),
                "parity": getattr(conn, "parity", "N"),
                "stopbits": getattr(conn, "stopbits", 1),
            },
        }
        devices.append(device)

    return devices


def main():
    if len(sys.argv) < 2:
        print("Usage: convert.py <repo_dir>", file=sys.stderr)
        sys.exit(1)

    repo_dir = sys.argv[1]
    all_devices = []

    # Search directories for config.py files
    search_dirs = [
        os.path.join(repo_dir, "gateways"),
        os.path.join(repo_dir, "devices"),
    ]

    found_any = False
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue

        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f == "config.py":
                    path = os.path.join(root, f)
                    found_any = True
                    try:
                        mod = load_module(path)
                        devs = extract_devices(mod)
                        if devs:
                            all_devices.extend(devs)
                        else:
                            print(f"Warning: no Device subclasses found in {path}", file=sys.stderr)
                    except Exception as e:
                        error = {"error": str(e), "file": path}
                        print(json.dumps(error), file=sys.stderr)
                        sys.exit(1)

    if not found_any:
        print("Warning: no config.py files found in gateways/ or devices/", file=sys.stderr)

    print(json.dumps(all_devices))


if __name__ == "__main__":
    main()
