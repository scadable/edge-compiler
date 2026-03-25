#!/usr/bin/env python3
"""
End-to-end test: compile example-simple-setup and verify generated YAML configs
match what edge-main expects.

This simulates the full compiler pipeline locally (without MinIO/Git clone).
"""
import json
import os
import subprocess
import sys
import tempfile
import shutil

import yaml
import pytest

CONVERT_SCRIPT = os.path.join(os.path.dirname(__file__), "convert.py")
EXAMPLE_PROJECT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "example-simple-setup")


def run_convert(repo_dir):
    """Run convert.py and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, CONVERT_SCRIPT, repo_dir],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"convert.py failed:\n{result.stderr}"
    return json.loads(result.stdout)


def write_yaml_configs(result, output_dir):
    """Simulate what the Go packager does: write YAML config files."""
    for device in result["devices"]:
        device_dir = os.path.join(output_dir, "devices", device["device_id"])
        os.makedirs(device_dir, exist_ok=True)
        with open(os.path.join(device_dir, "config.yaml"), "w") as f:
            yaml.dump(device, f, default_flow_style=False)

    for storage in result["storage"]:
        storage_dir = os.path.join(output_dir, "storage", storage["id"])
        os.makedirs(storage_dir, exist_ok=True)
        with open(os.path.join(storage_dir, "config.yaml"), "w") as f:
            yaml.dump(storage, f, default_flow_style=False)

    for outbound in result["outbound"]:
        outbound_dir = os.path.join(output_dir, "outbound", outbound["id"])
        os.makedirs(outbound_dir, exist_ok=True)
        with open(os.path.join(outbound_dir, "config.yaml"), "w") as f:
            yaml.dump(outbound, f, default_flow_style=False)

    for controller in result["controllers"]:
        ctrl_dir = os.path.join(output_dir, "controllers", controller["id"])
        os.makedirs(ctrl_dir, exist_ok=True)
        with open(os.path.join(ctrl_dir, "config.yaml"), "w") as f:
            yaml.dump(controller, f, default_flow_style=False)

    # Generate manifest
    manifest = {
        "project_id": "test-project",
        "release_tag": "v1.0.0",
        "commit_hash": "abc123",
        "compiled_at": "2026-03-25T12:00:00Z",
        "devices": [
            {"device_id": d["device_id"], "protocol": d["protocol"],
             "config_path": f"devices/{d['device_id']}/config.yaml"}
            for d in result["devices"]
        ],
        "storage": [
            {"id": s["id"], "config_path": f"storage/{s['id']}/config.yaml"}
            for s in result["storage"]
        ],
        "outbound": [
            {"id": o["id"], "config_path": f"outbound/{o['id']}/config.yaml"}
            for o in result["outbound"]
        ],
        "controllers": [
            {"id": c["id"], "config_path": f"controllers/{c['id']}/config.yaml",
             "source_path": f"controllers/{c['id']}/source.py"}
            for c in result["controllers"]
        ],
        "drivers_needed": list(set(
            "driver-modbus" if d["protocol"] in ("modbus-tcp", "modbus-rtu") else f"driver-{d['protocol']}"
            for d in result["devices"]
        )),
    }
    with open(os.path.join(output_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


@pytest.fixture
def compiled_output():
    """Run the full compile pipeline and return (result_json, output_dir)."""
    if not os.path.isdir(EXAMPLE_PROJECT):
        pytest.skip("example-simple-setup not found")

    result = run_convert(EXAMPLE_PROJECT)
    output_dir = tempfile.mkdtemp(prefix="e2e-compiled-")
    manifest = write_yaml_configs(result, output_dir)
    yield result, output_dir, manifest
    shutil.rmtree(output_dir)


# ============================================================
# End-to-End: Verify compiled output structure
# ============================================================

class TestCompiledStructure:
    def test_directory_structure(self, compiled_output):
        """Compiled output has the expected directory structure."""
        _, out_dir, _ = compiled_output
        assert os.path.isfile(os.path.join(out_dir, "manifest.json"))
        assert os.path.isfile(os.path.join(out_dir, "devices", "temp-sensor", "config.yaml"))
        assert os.path.isfile(os.path.join(out_dir, "devices", "factory-camera", "config.yaml"))
        assert os.path.isfile(os.path.join(out_dir, "storage", "image-store", "config.yaml"))
        assert os.path.isfile(os.path.join(out_dir, "outbound", "readings", "config.yaml"))
        assert os.path.isfile(os.path.join(out_dir, "outbound", "photos", "config.yaml"))
        assert os.path.isfile(os.path.join(out_dir, "controllers", "temp-monitor", "config.yaml"))

    def test_manifest_completeness(self, compiled_output):
        """Manifest lists all resources and drivers."""
        _, out_dir, manifest = compiled_output
        assert len(manifest["devices"]) == 2
        assert len(manifest["storage"]) == 1
        assert len(manifest["outbound"]) == 2
        assert len(manifest["controllers"]) == 1
        assert "driver-modbus" in manifest["drivers_needed"]
        assert "driver-serial" in manifest["drivers_needed"]


# ============================================================
# End-to-End: Verify device config YAML matches edge-main format
# ============================================================

class TestDeviceConfigs:
    def test_temp_sensor_yaml(self, compiled_output):
        """temp-sensor config.yaml is valid for edge-main."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "devices", "temp-sensor", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        # Required fields that edge-main DeviceConfig expects
        assert cfg["device_id"] == "temp-sensor"
        assert cfg["protocol"] == "modbus-tcp"
        assert cfg["frequency"] == 5
        assert isinstance(cfg["connection"], dict)
        assert cfg["connection"]["host"] == "${SENSOR_HOST}"
        assert cfg["connection"]["port"] == 502
        assert cfg["connection"]["slave_id"] == 1
        assert cfg["connection"]["timeout"] == 5.0
        assert cfg["connection"]["retries"] == 3

    def test_temp_sensor_decode(self, compiled_output):
        """temp-sensor decode mappings are valid for edge-main DeclarativeDecoder."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "devices", "temp-sensor", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        decode = cfg["decode"]
        assert decode["transform_type"] == "declarative"
        assert len(decode["mappings"]) == 2

        # Verify mapping format matches edge-main FieldMapping struct
        m0 = decode["mappings"][0]
        assert "from" in m0  # edge-main: pub from: String
        assert "to" in m0    # edge-main: pub to: String
        assert "scale" in m0  # edge-main: pub scale: f64
        assert "offset" in m0  # edge-main: pub offset: f64
        assert isinstance(m0["scale"], (int, float))
        assert isinstance(m0["offset"], (int, float))

        # Verify the actual register-to-field mappings
        temp_mapping = next(m for m in decode["mappings"] if m["to"] == "temperature")
        assert temp_mapping["from"] == "reg_40001"
        assert temp_mapping["scale"] == 0.1

        pressure_mapping = next(m for m in decode["mappings"] if m["to"] == "pressure")
        assert pressure_mapping["from"] == "reg_40002"
        assert pressure_mapping["scale"] == 0.01

    def test_camera_yaml(self, compiled_output):
        """factory-camera config.yaml is valid for edge-main."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "devices", "factory-camera", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        assert cfg["device_id"] == "factory-camera"
        assert cfg["protocol"] == "serial"
        assert cfg["frequency"] == 30
        assert cfg["connection"]["serial_port"] == "/dev/ttyUSB0"
        assert cfg["connection"]["baudrate"] == 921600

        # Camera has no registers/fields, so no decode section
        assert cfg.get("decode") is None

    def test_device_yaml_has_no_extra_fields(self, compiled_output):
        """Device YAML only contains fields that edge-main knows about."""
        _, out_dir, _ = compiled_output
        allowed_device_keys = {"device_id", "protocol", "frequency", "filter", "connection", "decode"}
        allowed_connection_keys = {
            "host", "port", "slave_id", "timeout", "retries",
            "serial_port", "baudrate", "parity", "stopbits", "bytesize",
            "node_ids", "security_policy", "username", "password",
        }
        allowed_decode_keys = {"transform_type", "mappings", "wasm_module"}
        allowed_mapping_keys = {"from", "to", "scale", "offset", "field_type", "start", "length"}

        for device_id in ("temp-sensor", "factory-camera"):
            with open(os.path.join(out_dir, "devices", device_id, "config.yaml")) as f:
                cfg = yaml.safe_load(f)

            extra_device = set(cfg.keys()) - allowed_device_keys
            assert not extra_device, f"{device_id}: unexpected keys {extra_device}"

            extra_conn = set(cfg["connection"].keys()) - allowed_connection_keys
            assert not extra_conn, f"{device_id}: unexpected connection keys {extra_conn}"

            if cfg.get("decode"):
                extra_decode = set(cfg["decode"].keys()) - allowed_decode_keys
                assert not extra_decode, f"{device_id}: unexpected decode keys {extra_decode}"
                for m in cfg["decode"].get("mappings", []):
                    extra_map = set(m.keys()) - allowed_mapping_keys
                    assert not extra_map, f"{device_id}: unexpected mapping keys {extra_map}"


# ============================================================
# End-to-End: Verify storage config YAML matches edge-main format
# ============================================================

class TestStorageConfigs:
    def test_image_store_yaml(self, compiled_output):
        """image-store config.yaml is valid for edge-main StorageConfig."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "storage", "image-store", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        # Required fields that edge-main StorageConfig expects
        assert cfg["id"] == "image-store"
        assert cfg["storage_type"] == "file"
        assert cfg["path"] == "/var/data/images"
        assert cfg["max_size"] == 1073741824  # 1 GB
        assert cfg["warning_threshold"] == 80

    def test_storage_yaml_has_no_extra_fields(self, compiled_output):
        """Storage YAML only contains fields that edge-main knows about."""
        _, out_dir, _ = compiled_output
        allowed_keys = {"id", "storage_type", "path", "max_size", "warning_threshold"}

        with open(os.path.join(out_dir, "storage", "image-store", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        extra = set(cfg.keys()) - allowed_keys
        assert not extra, f"unexpected storage keys {extra}"


# ============================================================
# End-to-End: Verify outbound config YAML matches edge-main format
# ============================================================

class TestOutboundConfigs:
    def test_readings_mqtt_yaml(self, compiled_output):
        """readings outbound config.yaml is valid for edge-main OutboundConfig."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "outbound", "readings", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        assert cfg["id"] == "readings"
        assert cfg["outbound_type"] == "mqtt"
        assert cfg["devices"] == []

    def test_photos_s3_yaml(self, compiled_output):
        """photos S3 outbound config.yaml has all required fields."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "outbound", "photos", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        assert cfg["id"] == "photos"
        assert cfg["outbound_type"] == "s3"
        assert cfg["devices"] == ["factory-camera"]
        assert cfg["storage"] == "image-store"
        assert cfg["prefix"] == "alerts/{date}/"
        assert cfg["max_age"] == "30d"

    def test_outbound_device_ids_are_strings(self, compiled_output):
        """Device references in outbound are resolved to string IDs, not class names."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "outbound", "photos", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        for dev_id in cfg["devices"]:
            assert isinstance(dev_id, str), f"device reference should be string, got {type(dev_id)}"
            assert not dev_id[0].isupper(), f"device id '{dev_id}' looks like a class name, should be an id"

    def test_outbound_storage_is_id_not_classname(self, compiled_output):
        """Storage reference in S3 outbound is resolved to string ID."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "outbound", "photos", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        assert cfg["storage"] == "image-store"
        assert cfg["storage"] != "ImageStore"  # must not be class name


# ============================================================
# End-to-End: Verify controller config YAML
# ============================================================

class TestControllerConfigs:
    def test_temp_monitor_yaml(self, compiled_output):
        """temp-monitor controller config.yaml has correct metadata."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "controllers", "temp-monitor", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        assert cfg["id"] == "temp-monitor"
        assert cfg["interval"] == 5
        assert "temp-sensor" in cfg["uses"]
        assert "factory-camera" in cfg["uses"]
        assert cfg["source_file"].endswith("temp_monitor.py")

    def test_controller_uses_are_device_ids(self, compiled_output):
        """Controller uses field contains device IDs, not class names."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "controllers", "temp-monitor", "config.yaml")) as f:
            cfg = yaml.safe_load(f)

        for use in cfg["uses"]:
            assert isinstance(use, str)
            assert not use[0].isupper(), f"uses '{use}' looks like a class name"


# ============================================================
# End-to-End: Cross-reference integrity
# ============================================================

class TestCrossReferences:
    def test_outbound_devices_exist(self, compiled_output):
        """All device IDs referenced in outbound configs exist as actual devices."""
        result, _, _ = compiled_output
        device_ids = {d["device_id"] for d in result["devices"]}

        for outbound in result["outbound"]:
            for dev_id in outbound["devices"]:
                assert dev_id in device_ids, \
                    f"outbound '{outbound['id']}' references device '{dev_id}' which doesn't exist"

    def test_outbound_storage_exists(self, compiled_output):
        """Storage IDs referenced in S3 outbound configs exist as actual storage."""
        result, _, _ = compiled_output
        storage_ids = {s["id"] for s in result["storage"]}

        for outbound in result["outbound"]:
            storage_ref = outbound.get("storage", "")
            if storage_ref:
                assert storage_ref in storage_ids, \
                    f"outbound '{outbound['id']}' references storage '{storage_ref}' which doesn't exist"

    def test_controller_uses_exist(self, compiled_output):
        """All device IDs in controller uses exist as actual devices."""
        result, _, _ = compiled_output
        device_ids = {d["device_id"] for d in result["devices"]}

        for ctrl in result["controllers"]:
            for dev_id in ctrl["uses"]:
                assert dev_id in device_ids, \
                    f"controller '{ctrl['id']}' uses device '{dev_id}' which doesn't exist"

    def test_manifest_device_configs_exist(self, compiled_output):
        """All config_paths in manifest point to actual files."""
        _, out_dir, manifest = compiled_output

        for device in manifest["devices"]:
            path = os.path.join(out_dir, device["config_path"])
            assert os.path.isfile(path), f"manifest device config not found: {device['config_path']}"

        for storage in manifest["storage"]:
            path = os.path.join(out_dir, storage["config_path"])
            assert os.path.isfile(path), f"manifest storage config not found: {storage['config_path']}"

        for outbound in manifest["outbound"]:
            path = os.path.join(out_dir, outbound["config_path"])
            assert os.path.isfile(path), f"manifest outbound config not found: {outbound['config_path']}"

        for ctrl in manifest["controllers"]:
            path = os.path.join(out_dir, ctrl["config_path"])
            assert os.path.isfile(path), f"manifest controller config not found: {ctrl['config_path']}"


# ============================================================
# End-to-End: Verify YAML is re-parseable (no corruption)
# ============================================================

class TestYAMLIntegrity:
    def test_all_yamls_are_valid(self, compiled_output):
        """Every generated YAML file can be parsed without errors."""
        _, out_dir, _ = compiled_output
        yaml_count = 0

        for root, dirs, files in os.walk(out_dir):
            for f in files:
                if f.endswith(".yaml"):
                    path = os.path.join(root, f)
                    with open(path) as fh:
                        data = yaml.safe_load(fh)
                    assert data is not None, f"empty YAML: {path}"
                    assert isinstance(data, dict), f"YAML not a dict: {path}"
                    yaml_count += 1

        assert yaml_count == 6, f"expected 6 YAML files, found {yaml_count}"

    def test_manifest_is_valid_json(self, compiled_output):
        """manifest.json is valid JSON with expected structure."""
        _, out_dir, _ = compiled_output
        with open(os.path.join(out_dir, "manifest.json")) as f:
            manifest = json.load(f)

        assert "devices" in manifest
        assert "storage" in manifest
        assert "outbound" in manifest
        assert "controllers" in manifest
        assert "drivers_needed" in manifest
        assert "project_id" in manifest
        assert "release_tag" in manifest
