#!/usr/bin/env python3
"""
Tests for convert.py using the example-simple-setup project as a fixture.

Run: python3 -m pytest scripts/test_convert.py -v
"""
import json
import os
import subprocess
import sys
import tempfile
import shutil

import pytest

CONVERT_SCRIPT = os.path.join(os.path.dirname(__file__), "convert.py")
EXAMPLE_PROJECT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "example-simple-setup")


def run_convert(repo_dir):
    """Run convert.py and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, CONVERT_SCRIPT, repo_dir],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"convert.py failed: {result.stderr}")
    return json.loads(result.stdout)


@pytest.fixture
def example_project():
    """Path to the example-simple-setup project."""
    if not os.path.isdir(EXAMPLE_PROJECT):
        pytest.skip("example-simple-setup not found")
    return EXAMPLE_PROJECT


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    d = tempfile.mkdtemp(prefix="test-project-")
    for subdir in ("devices", "controllers", "storage", "outbound"):
        os.makedirs(os.path.join(d, subdir))
    yield d
    shutil.rmtree(d)


# --- Example project tests ---

class TestExampleProject:
    def test_full_extraction(self, example_project):
        """All resource types are extracted from the example project."""
        result = run_convert(example_project)
        assert len(result["devices"]) == 2
        assert len(result["storage"]) == 1
        assert len(result["outbound"]) == 2
        assert len(result["controllers"]) == 1

    def test_modbus_tcp_device(self, example_project):
        """TempSensor extracted with correct Modbus TCP config."""
        result = run_convert(example_project)
        sensor = next(d for d in result["devices"] if d["device_id"] == "temp-sensor")

        assert sensor["protocol"] == "modbus-tcp"
        assert sensor["frequency"] == 5
        assert sensor["connection"]["host"] == "${SENSOR_HOST}"
        assert sensor["connection"]["port"] == 502
        assert sensor["connection"]["slave_id"] == 1

    def test_modbus_tcp_decode_mappings(self, example_project):
        """Registers are converted to decode field mappings."""
        result = run_convert(example_project)
        sensor = next(d for d in result["devices"] if d["device_id"] == "temp-sensor")

        assert sensor["decode"]["transform_type"] == "declarative"
        mappings = sensor["decode"]["mappings"]
        assert len(mappings) == 2

        temp = next(m for m in mappings if m["to"] == "temperature")
        assert temp["from"] == "reg_40001"
        assert temp["scale"] == 0.1

        pressure = next(m for m in mappings if m["to"] == "pressure")
        assert pressure["from"] == "reg_40002"
        assert pressure["scale"] == 0.01

    def test_serial_device(self, example_project):
        """Camera extracted with correct serial config."""
        result = run_convert(example_project)
        camera = next(d for d in result["devices"] if d["device_id"] == "factory-camera")

        assert camera["protocol"] == "serial"
        assert camera["frequency"] == 30
        assert camera["connection"]["serial_port"] == "/dev/ttyUSB0"
        assert camera["connection"]["baudrate"] == 921600
        assert "decode" not in camera or camera.get("decode") is None

    def test_file_storage(self, example_project):
        """ImageStore extracted with correct storage config."""
        result = run_convert(example_project)
        storage = result["storage"][0]

        assert storage["id"] == "image-store"
        assert storage["storage_type"] == "file"
        assert storage["path"] == "/var/data/images"
        assert storage["max_size"] == 1073741824  # GB_1
        assert storage["warning_threshold"] == 80

    def test_mqtt_outbound(self, example_project):
        """Readings MQTT outbound extracted correctly."""
        result = run_convert(example_project)
        mqtt = next(o for o in result["outbound"] if o["id"] == "readings")

        assert mqtt["outbound_type"] == "mqtt"
        assert mqtt["devices"] == []

    def test_s3_outbound(self, example_project):
        """Photos S3 outbound extracted with device and storage references resolved."""
        result = run_convert(example_project)
        s3 = next(o for o in result["outbound"] if o["id"] == "photos")

        assert s3["outbound_type"] == "s3"
        assert s3["devices"] == ["factory-camera"]
        assert s3["storage"] == "image-store"
        assert s3["prefix"] == "alerts/{date}/"
        assert s3["max_age"] == "30d"

    def test_controller(self, example_project):
        """TempMonitor controller extracted with device references resolved."""
        result = run_convert(example_project)
        ctrl = result["controllers"][0]

        assert ctrl["id"] == "temp-monitor"
        assert ctrl["interval"] == 5
        assert "temp-sensor" in ctrl["uses"]
        assert "factory-camera" in ctrl["uses"]
        assert ctrl["source_file"].endswith("temp_monitor.py")


# --- Synthetic project tests ---

class TestSyntheticDevices:
    def test_modbus_rtu_device(self, temp_project):
        """Modbus RTU device maps port->serial_port and baud->baudrate."""
        with open(os.path.join(temp_project, "devices", "meter.py"), "w") as f:
            f.write("""
from scadable import Device, modbus_rtu, every, Register, SECONDS

class Meter(Device):
    id = "energy-meter"
    connection = modbus_rtu(port="/dev/ttyUSB1", baud=9600, slave=2)
    poll = every(10, SECONDS)
    registers = [Register(30001, "power", scale=0.1)]
""")
        result = run_convert(temp_project)
        dev = result["devices"][0]

        assert dev["device_id"] == "energy-meter"
        assert dev["protocol"] == "modbus-rtu"
        assert dev["frequency"] == 10
        assert dev["connection"]["serial_port"] == "/dev/ttyUSB1"
        assert dev["connection"]["baudrate"] == 9600
        assert dev["connection"]["slave_id"] == 2

    def test_opcua_device(self, temp_project):
        """OPC-UA device extracts node_ids and decode mappings from nodes."""
        with open(os.path.join(temp_project, "devices", "plc.py"), "w") as f:
            f.write("""
from scadable import Device, opcua, every, SECONDS

class Plc(Device):
    id = "siemens-plc"
    connection = opcua(
        host="192.168.1.50",
        port=4840,
        nodes=[
            ("temperature", "ns=2;s=Channel1.Temp"),
            ("pressure", "ns=2;s=Channel1.Pressure"),
        ]
    )
    poll = every(5, SECONDS)
""")
        result = run_convert(temp_project)
        dev = result["devices"][0]

        assert dev["device_id"] == "siemens-plc"
        assert dev["protocol"] == "opcua"
        assert dev["connection"]["host"] == "192.168.1.50"
        assert dev["connection"]["port"] == 4840
        assert dev["connection"]["node_ids"] == [
            "ns=2;s=Channel1.Temp",
            "ns=2;s=Channel1.Pressure",
        ]
        # Decode from nodes
        assert dev["decode"]["transform_type"] == "declarative"
        mappings = dev["decode"]["mappings"]
        assert len(mappings) == 2
        assert mappings[0]["from"] == "ns=2;s=Channel1.Temp"
        assert mappings[0]["to"] == "temperature"

    def test_serial_with_fields(self, temp_project):
        """Serial device with Field definitions generates decode mappings."""
        with open(os.path.join(temp_project, "devices", "sensor.py"), "w") as f:
            f.write("""
from scadable import Device, serial_uart, every, Field, SECONDS, FLOAT32, UINT16

class Sensor(Device):
    id = "uart-sensor"
    connection = serial_uart(port="/dev/ttyUSB0", baud=115200)
    poll = every(1, SECONDS)
    fields = [
        Field("temperature", start=0, length=4, type=FLOAT32, scale=0.01),
        Field("humidity", start=4, length=2, type=UINT16),
    ]
""")
        result = run_convert(temp_project)
        dev = result["devices"][0]

        assert dev["decode"]["transform_type"] == "declarative"
        mappings = dev["decode"]["mappings"]
        assert len(mappings) == 2

        temp = mappings[0]
        assert temp["from"] == "field_0_4"
        assert temp["to"] == "temperature"
        assert temp["scale"] == 0.01
        assert temp["field_type"] == "float32"
        assert temp["start"] == 0
        assert temp["length"] == 4

    def test_sqlite_storage(self, temp_project):
        """SQLiteStorage extracted with correct type."""
        with open(os.path.join(temp_project, "storage", "cache.py"), "w") as f:
            f.write("""
from scadable import SQLiteStorage, MB_256

class Cache(SQLiteStorage):
    id = "cache-db"
    path = "/var/data/cache.db"
    max_size = MB_256
    warn_at = 90
""")
        result = run_convert(temp_project)
        s = result["storage"][0]

        assert s["id"] == "cache-db"
        assert s["storage_type"] == "sqlite"
        assert s["path"] == "/var/data/cache.db"
        assert s["max_size"] == 256 * 1024 * 1024
        assert s["warning_threshold"] == 90

    def test_minutes_interval(self, temp_project):
        """Poll interval in MINUTES converts to seconds correctly."""
        with open(os.path.join(temp_project, "devices", "slow.py"), "w") as f:
            f.write("""
from scadable import Device, modbus_tcp, every, MINUTES

class Slow(Device):
    id = "slow-device"
    connection = modbus_tcp(host="10.0.0.1")
    poll = every(5, MINUTES)
""")
        result = run_convert(temp_project)
        assert result["devices"][0]["frequency"] == 300


class TestEdgeCases:
    def test_empty_project(self, temp_project):
        """Empty project returns empty arrays, no error."""
        result = run_convert(temp_project)
        assert result["devices"] == []
        assert result["storage"] == []
        assert result["outbound"] == []
        assert result["controllers"] == []

    def test_missing_id_raises(self, temp_project):
        """Device without id raises validation error at import time."""
        with open(os.path.join(temp_project, "devices", "bad.py"), "w") as f:
            f.write("""
from scadable import Device, modbus_tcp, every, SECONDS

class Bad(Device):
    connection = modbus_tcp(host="10.0.0.1")
    poll = every(5, SECONDS)
""")
        # SDK validation raises TypeError in __init_subclass__
        with pytest.raises(RuntimeError, match="failed"):
            run_convert(temp_project)

    def test_syntax_error_raises(self, temp_project):
        """Bad Python syntax reports the error."""
        with open(os.path.join(temp_project, "devices", "broken.py"), "w") as f:
            f.write("class Broken(Device:\n")  # syntax error
        with pytest.raises(RuntimeError, match="failed"):
            run_convert(temp_project)
