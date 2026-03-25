package converter

import (
	"encoding/json"
	"fmt"
	"os"
	"testing"

	"gopkg.in/yaml.v3"
)

// ============================================================
// JSON Parsing Tests - verify all struct fields deserialize
// ============================================================

func TestParseFullConvertResult(t *testing.T) {
	raw := fullExampleJSON()

	var result ConvertResult
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		t.Fatalf("failed to parse: %v", err)
	}

	if len(result.Devices) != 3 {
		t.Errorf("devices = %d, want 3", len(result.Devices))
	}
	if len(result.Storage) != 2 {
		t.Errorf("storage = %d, want 2", len(result.Storage))
	}
	if len(result.Outbound) != 2 {
		t.Errorf("outbound = %d, want 2", len(result.Outbound))
	}
	if len(result.Controllers) != 1 {
		t.Errorf("controllers = %d, want 1", len(result.Controllers))
	}
}

func TestParseModbusTCPDevice(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"temp-sensor","protocol":"modbus-tcp","frequency":5,
		"connection":{"host":"192.168.1.100","port":502,"slave_id":1,"timeout":5.0,"retries":3},
		"decode":{"transform_type":"declarative","mappings":[
			{"from":"reg_40001","to":"temperature","scale":0.1,"offset":0.0},
			{"from":"reg_40002","to":"pressure","scale":0.01,"offset":-10.0}
		]}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	dev := r.Devices[0]
	assertEqual(t, "device_id", dev.DeviceID, "temp-sensor")
	assertEqual(t, "protocol", dev.Protocol, "modbus-tcp")
	assertEqualInt(t, "frequency", dev.Frequency, 5)
	assertEqual(t, "host", dev.Connection.Host, "192.168.1.100")
	assertEqualInt(t, "port", dev.Connection.Port, 502)
	assertEqualInt(t, "slave_id", dev.Connection.SlaveID, 1)

	if dev.Decode == nil {
		t.Fatal("decode is nil")
	}
	assertEqual(t, "transform_type", dev.Decode.TransformType, "declarative")
	assertEqualInt(t, "mappings count", len(dev.Decode.Mappings), 2)

	m0 := dev.Decode.Mappings[0]
	assertEqual(t, "mapping[0].from", m0.From, "reg_40001")
	assertEqual(t, "mapping[0].to", m0.To, "temperature")
	assertEqualFloat(t, "mapping[0].scale", m0.Scale, 0.1)
	assertEqualFloat(t, "mapping[0].offset", m0.Offset, 0.0)

	m1 := dev.Decode.Mappings[1]
	assertEqualFloat(t, "mapping[1].offset", m1.Offset, -10.0)
}

func TestParseModbusRTUDevice(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"energy-meter","protocol":"modbus-rtu","frequency":10,
		"connection":{"serial_port":"/dev/ttyUSB1","baudrate":9600,"slave_id":2,"parity":"E","stopbits":1,"bytesize":8,"timeout":3.0}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	dev := r.Devices[0]
	assertEqual(t, "protocol", dev.Protocol, "modbus-rtu")
	assertEqual(t, "serial_port", dev.Connection.SerialPort, "/dev/ttyUSB1")
	assertEqualInt(t, "baudrate", dev.Connection.Baudrate, 9600)
	assertEqualInt(t, "slave_id", dev.Connection.SlaveID, 2)
	assertEqual(t, "parity", dev.Connection.Parity, "E")
	assertEqualInt(t, "stopbits", dev.Connection.Stopbits, 1)
	assertEqualInt(t, "bytesize", dev.Connection.Bytesize, 8)
}

func TestParseOPCUADevice(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"siemens-plc","protocol":"opcua","frequency":5,
		"connection":{
			"host":"192.168.1.50","port":4840,
			"node_ids":["ns=2;s=Channel1.Temp","ns=2;s=Channel1.Pressure"],
			"security_policy":"Basic256Sha256","username":"admin","password":"secret"
		},
		"decode":{"transform_type":"declarative","mappings":[
			{"from":"ns=2;s=Channel1.Temp","to":"temperature","scale":1.0,"offset":0.0},
			{"from":"ns=2;s=Channel1.Pressure","to":"pressure","scale":1.0,"offset":0.0}
		]}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	dev := r.Devices[0]
	assertEqual(t, "protocol", dev.Protocol, "opcua")
	assertEqual(t, "host", dev.Connection.Host, "192.168.1.50")
	assertEqualInt(t, "port", dev.Connection.Port, 4840)
	assertEqualInt(t, "node_ids count", len(dev.Connection.NodeIDs), 2)
	assertEqual(t, "node_ids[0]", dev.Connection.NodeIDs[0], "ns=2;s=Channel1.Temp")
	assertEqual(t, "security_policy", dev.Connection.SecurityPolicy, "Basic256Sha256")
	assertEqual(t, "username", dev.Connection.Username, "admin")
	assertEqual(t, "password", dev.Connection.Password, "secret")
}

func TestParseSerialDevice(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"esp32","protocol":"serial","frequency":1,
		"connection":{"serial_port":"/dev/ttyUSB0","baudrate":115200},
		"decode":{"transform_type":"declarative","mappings":[
			{"from":"field_0_4","to":"temperature","scale":0.01,"offset":0.0,"field_type":"float32","start":0,"length":4},
			{"from":"field_4_2","to":"humidity","scale":1.0,"offset":0.0,"field_type":"uint16","start":4,"length":2}
		]}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	dev := r.Devices[0]
	assertEqual(t, "protocol", dev.Protocol, "serial")
	assertEqual(t, "serial_port", dev.Connection.SerialPort, "/dev/ttyUSB0")
	assertEqualInt(t, "baudrate", dev.Connection.Baudrate, 115200)

	if dev.Decode == nil {
		t.Fatal("decode is nil for serial device")
	}
	assertEqualInt(t, "mappings count", len(dev.Decode.Mappings), 2)

	m0 := dev.Decode.Mappings[0]
	assertEqual(t, "field_type", m0.FieldType, "float32")
	if m0.Start == nil || *m0.Start != 0 {
		t.Errorf("start = %v, want 0", m0.Start)
	}
	if m0.Length == nil || *m0.Length != 4 {
		t.Errorf("length = %v, want 4", m0.Length)
	}
}

func TestParseDeviceNoDecodeIsNil(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"camera","protocol":"serial","frequency":30,
		"connection":{"serial_port":"/dev/ttyUSB0","baudrate":921600}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	if r.Devices[0].Decode != nil {
		t.Error("expected decode to be nil for device without registers/fields")
	}
}

func TestParseFileStorage(t *testing.T) {
	raw := `{"devices":[],"storage":[{
		"id":"image-store","storage_type":"file","path":"/var/data/images",
		"max_size":1073741824,"warning_threshold":80
	}],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	s := r.Storage[0]
	assertEqual(t, "id", s.ID, "image-store")
	assertEqual(t, "storage_type", s.StorageType, "file")
	assertEqual(t, "path", s.Path, "/var/data/images")
	if s.MaxSize != 1073741824 {
		t.Errorf("max_size = %d, want 1073741824", s.MaxSize)
	}
	assertEqualInt(t, "warning_threshold", s.WarningThreshold, 80)
}

func TestParseSQLiteStorage(t *testing.T) {
	raw := `{"devices":[],"storage":[{
		"id":"cache-db","storage_type":"sqlite","path":"/var/data/cache.db",
		"max_size":268435456,"warning_threshold":90
	}],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	s := r.Storage[0]
	assertEqual(t, "storage_type", s.StorageType, "sqlite")
	if s.MaxSize != 268435456 {
		t.Errorf("max_size = %d, want 268435456", s.MaxSize)
	}
	assertEqualInt(t, "warning_threshold", s.WarningThreshold, 90)
}

func TestParseMQTTOutbound(t *testing.T) {
	raw := `{"devices":[],"storage":[],"outbound":[{
		"id":"readings","outbound_type":"mqtt","devices":[]
	}],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	o := r.Outbound[0]
	assertEqual(t, "id", o.ID, "readings")
	assertEqual(t, "outbound_type", o.OutboundType, "mqtt")
	assertEqualInt(t, "devices count", len(o.Devices), 0)
	assertEqual(t, "storage", o.Storage, "")
}

func TestParseS3Outbound(t *testing.T) {
	raw := `{"devices":[],"storage":[],"outbound":[{
		"id":"photos","outbound_type":"s3","devices":["factory-camera"],
		"storage":"image-store","prefix":"alerts/{date}/","max_age":"30d"
	}],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	o := r.Outbound[0]
	assertEqual(t, "id", o.ID, "photos")
	assertEqual(t, "outbound_type", o.OutboundType, "s3")
	assertEqualInt(t, "devices count", len(o.Devices), 1)
	assertEqual(t, "devices[0]", o.Devices[0], "factory-camera")
	assertEqual(t, "storage", o.Storage, "image-store")
	assertEqual(t, "prefix", o.Prefix, "alerts/{date}/")
	assertEqual(t, "max_age", o.MaxAge, "30d")
}

func TestParseMQTTOutboundWithDevices(t *testing.T) {
	raw := `{"devices":[],"storage":[],"outbound":[{
		"id":"filtered","outbound_type":"mqtt","devices":["sensor-1","sensor-2","plc-01"]
	}],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	assertEqualInt(t, "devices count", len(r.Outbound[0].Devices), 3)
	assertEqual(t, "devices[2]", r.Outbound[0].Devices[2], "plc-01")
}

func TestParseController(t *testing.T) {
	raw := `{"devices":[],"storage":[],"outbound":[],"controllers":[{
		"id":"temp-monitor","interval":5,
		"uses":["temp-sensor","factory-camera"],
		"source_file":"controllers/temp_monitor.py"
	}]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	c := r.Controllers[0]
	assertEqual(t, "id", c.ID, "temp-monitor")
	assertEqualInt(t, "interval", c.Interval, 5)
	assertEqualInt(t, "uses count", len(c.Uses), 2)
	assertEqual(t, "uses[0]", c.Uses[0], "temp-sensor")
	assertEqual(t, "source_file", c.SourceFile, "controllers/temp_monitor.py")
}

func TestParseEmptyResult(t *testing.T) {
	raw := `{"devices":[],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	assertEqualInt(t, "devices", len(r.Devices), 0)
	assertEqualInt(t, "storage", len(r.Storage), 0)
	assertEqualInt(t, "outbound", len(r.Outbound), 0)
	assertEqualInt(t, "controllers", len(r.Controllers), 0)
}

// ============================================================
// YAML Round-Trip Tests - verify configs survive serialize/deserialize
// ============================================================

func TestYAMLRoundTripDevice(t *testing.T) {
	start := 0
	length := 4
	dev := DeviceConfig{
		DeviceID:  "test-device",
		Protocol:  "modbus-tcp",
		Frequency: 5,
		Connection: ConnectionConfig{
			Host:    "10.0.0.1",
			Port:    502,
			SlaveID: 1,
		},
		Decode: &DecodeConfig{
			TransformType: "declarative",
			Mappings: []FieldMapping{
				{From: "reg_40001", To: "temp", Scale: 0.1, Offset: -40.0},
				{From: "field_0_4", To: "humid", Scale: 1.0, FieldType: "float32", Start: &start, Length: &length},
			},
		},
	}

	data, err := yaml.Marshal(dev)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var got DeviceConfig
	if err := yaml.Unmarshal(data, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	assertEqual(t, "device_id", got.DeviceID, "test-device")
	assertEqual(t, "host", got.Connection.Host, "10.0.0.1")
	assertEqualInt(t, "mappings", len(got.Decode.Mappings), 2)
	assertEqualFloat(t, "offset", got.Decode.Mappings[0].Offset, -40.0)
	assertEqual(t, "field_type", got.Decode.Mappings[1].FieldType, "float32")
}

func TestYAMLRoundTripStorage(t *testing.T) {
	s := StorageConfig{
		ID: "test-store", StorageType: "sqlite",
		Path: "/var/data/test.db", MaxSize: 268435456, WarningThreshold: 90,
	}

	data, err := yaml.Marshal(s)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var got StorageConfig
	if err := yaml.Unmarshal(data, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	assertEqual(t, "id", got.ID, "test-store")
	assertEqual(t, "storage_type", got.StorageType, "sqlite")
	if got.MaxSize != 268435456 {
		t.Errorf("max_size = %d, want 268435456", got.MaxSize)
	}
}

func TestYAMLRoundTripOutbound(t *testing.T) {
	o := OutboundConfig{
		ID: "photos", OutboundType: "s3",
		Devices: []string{"camera-1"}, Storage: "image-store",
		Prefix: "images/{date}/", MaxAge: "30d",
	}

	data, err := yaml.Marshal(o)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var got OutboundConfig
	if err := yaml.Unmarshal(data, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	assertEqual(t, "prefix", got.Prefix, "images/{date}/")
	assertEqual(t, "max_age", got.MaxAge, "30d")
	assertEqual(t, "storage", got.Storage, "image-store")
}

func TestYAMLRoundTripController(t *testing.T) {
	c := ControllerConfig{
		ID: "monitor", Interval: 10,
		Uses: []string{"sensor-1", "sensor-2"}, SourceFile: "controllers/monitor.py",
	}

	data, err := yaml.Marshal(c)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var got ControllerConfig
	if err := yaml.Unmarshal(data, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	assertEqual(t, "id", got.ID, "monitor")
	assertEqualInt(t, "interval", got.Interval, 10)
	assertEqualInt(t, "uses count", len(got.Uses), 2)
	assertEqual(t, "source_file", got.SourceFile, "controllers/monitor.py")
}

// ============================================================
// Validation Tests - ensure bad inputs are caught
// ============================================================

func TestValidateDeviceMissingID(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		Protocol: "modbus-tcp", Frequency: 5,
		Connection: ConnectionConfig{Host: "10.0.0.1"},
	})
	assertValidationFails(t, r, "device_id is required")
}

func TestValidateDeviceMissingProtocol(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Frequency: 5,
		Connection: ConnectionConfig{Host: "10.0.0.1"},
	})
	assertValidationFails(t, r, "protocol is required")
}

func TestValidateDeviceZeroFrequency(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "modbus-tcp", Frequency: 0,
		Connection: ConnectionConfig{Host: "10.0.0.1"},
	})
	assertValidationFails(t, r, "frequency must be > 0")
}

func TestValidateDeviceNegativeFrequency(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "modbus-tcp", Frequency: -1,
		Connection: ConnectionConfig{Host: "10.0.0.1"},
	})
	assertValidationFails(t, r, "frequency must be > 0")
}

func TestValidateModbusTCPMissingHost(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "modbus-tcp", Frequency: 5,
		Connection: ConnectionConfig{},
	})
	assertValidationFails(t, r, "requires connection.host")
}

func TestValidateModbusRTUMissingSerialPort(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "modbus-rtu", Frequency: 5,
		Connection: ConnectionConfig{},
	})
	assertValidationFails(t, r, "requires connection.serial_port")
}

func TestValidateSerialMissingSerialPort(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "serial", Frequency: 1,
		Connection: ConnectionConfig{},
	})
	assertValidationFails(t, r, "requires connection.serial_port")
}

func TestValidateOPCUAMissingHost(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "opcua", Frequency: 5,
		Connection: ConnectionConfig{},
	})
	assertValidationFails(t, r, "requires connection.host")
}

func TestValidateStorageMissingID(t *testing.T) {
	r := makeResult()
	r.Storage = append(r.Storage, StorageConfig{
		StorageType: "file", Path: "/data", MaxSize: 100,
	})
	assertValidationFails(t, r, "id is required")
}

func TestValidateStorageMissingPath(t *testing.T) {
	r := makeResult()
	r.Storage = append(r.Storage, StorageConfig{
		ID: "test", StorageType: "file", MaxSize: 100,
	})
	assertValidationFails(t, r, "path is required")
}

func TestValidateStorageZeroSize(t *testing.T) {
	r := makeResult()
	r.Storage = append(r.Storage, StorageConfig{
		ID: "test", StorageType: "file", Path: "/data", MaxSize: 0,
	})
	assertValidationFails(t, r, "max_size must be > 0")
}

func TestValidateOutboundMissingID(t *testing.T) {
	r := makeResult()
	r.Outbound = append(r.Outbound, OutboundConfig{
		OutboundType: "mqtt",
	})
	assertValidationFails(t, r, "id is required")
}

func TestValidateOutboundInvalidType(t *testing.T) {
	r := makeResult()
	r.Outbound = append(r.Outbound, OutboundConfig{
		ID: "test", OutboundType: "kafka",
	})
	assertValidationFails(t, r, "must be 'mqtt' or 's3'")
}

func TestValidateControllerMissingID(t *testing.T) {
	r := makeResult()
	r.Controllers = append(r.Controllers, ControllerConfig{
		Interval: 5, Uses: []string{"test"},
	})
	assertValidationFails(t, r, "id is required")
}

func TestValidateControllerZeroInterval(t *testing.T) {
	r := makeResult()
	r.Controllers = append(r.Controllers, ControllerConfig{
		ID: "test", Interval: 0,
	})
	assertValidationFails(t, r, "interval must be > 0")
}

func TestValidateValidResult(t *testing.T) {
	r := makeResult()
	r.Devices = append(r.Devices, DeviceConfig{
		DeviceID: "test", Protocol: "modbus-tcp", Frequency: 5,
		Connection: ConnectionConfig{Host: "10.0.0.1"},
	})
	r.Storage = append(r.Storage, StorageConfig{
		ID: "store", StorageType: "file", Path: "/data", MaxSize: 1000,
	})
	r.Outbound = append(r.Outbound, OutboundConfig{
		ID: "out", OutboundType: "mqtt",
	})
	r.Controllers = append(r.Controllers, ControllerConfig{
		ID: "ctrl", Interval: 5, Uses: []string{"test"},
	})

	if err := validateResult(&r); err != nil {
		t.Errorf("expected valid result, got error: %v", err)
	}
}

// ============================================================
// DriverName Tests
// ============================================================

func TestDriverName(t *testing.T) {
	tests := []struct {
		protocol string
		want     string
	}{
		{"modbus-tcp", "driver-modbus"},
		{"modbus-rtu", "driver-modbus"},
		{"opcua", "driver-opcua"},
		{"serial", "driver-serial"},
		{"mqtt", "driver-mqtt"},
		{"custom-proto", "driver-custom-proto"},
	}

	for _, tt := range tests {
		t.Run(tt.protocol, func(t *testing.T) {
			got := DriverName(tt.protocol)
			if got != tt.want {
				t.Errorf("DriverName(%q) = %q, want %q", tt.protocol, got, tt.want)
			}
		})
	}
}

// ============================================================
// Environment Variable Passthrough Test
// ============================================================

func TestEnvVarPassthrough(t *testing.T) {
	raw := `{"devices":[{
		"device_id":"test","protocol":"modbus-tcp","frequency":5,
		"connection":{"host":"${DEVICE_HOST}","port":502}
	}],"storage":[],"outbound":[],"controllers":[]}`

	var r ConvertResult
	mustParse(t, raw, &r)

	// Env vars should be passed through as-is, not resolved
	assertEqual(t, "host", r.Devices[0].Connection.Host, "${DEVICE_HOST}")
}

// ============================================================
// Integration Test (requires example-simple-setup)
// ============================================================

func TestConvertPythonIntegration(t *testing.T) {
	exampleDir := "../../../example-simple-setup"
	if _, err := os.Stat(exampleDir); os.IsNotExist(err) {
		t.Skip("example-simple-setup not found")
	}

	result, err := ConvertPython(exampleDir)
	if err != nil {
		t.Fatalf("ConvertPython failed: %v", err)
	}

	// Devices
	assertEqualInt(t, "devices count", len(result.Devices), 2)

	var sensor, camera *DeviceConfig
	for i := range result.Devices {
		switch result.Devices[i].DeviceID {
		case "temp-sensor":
			sensor = &result.Devices[i]
		case "factory-camera":
			camera = &result.Devices[i]
		}
	}

	if sensor == nil {
		t.Fatal("temp-sensor not found")
	}
	assertEqual(t, "sensor protocol", sensor.Protocol, "modbus-tcp")
	assertEqualInt(t, "sensor frequency", sensor.Frequency, 5)
	assertEqual(t, "sensor host", sensor.Connection.Host, "${SENSOR_HOST}")
	if sensor.Decode == nil || len(sensor.Decode.Mappings) != 2 {
		t.Error("sensor should have 2 decode mappings")
	}

	if camera == nil {
		t.Fatal("factory-camera not found")
	}
	assertEqual(t, "camera protocol", camera.Protocol, "serial")
	assertEqualInt(t, "camera frequency", camera.Frequency, 30)

	// Storage
	assertEqualInt(t, "storage count", len(result.Storage), 1)
	assertEqual(t, "storage id", result.Storage[0].ID, "image-store")
	assertEqual(t, "storage type", result.Storage[0].StorageType, "file")

	// Outbound
	assertEqualInt(t, "outbound count", len(result.Outbound), 2)

	// Controllers
	assertEqualInt(t, "controllers count", len(result.Controllers), 1)
	ctrl := result.Controllers[0]
	assertEqual(t, "controller id", ctrl.ID, "temp-monitor")
	assertEqualInt(t, "controller interval", ctrl.Interval, 5)
	assertEqualInt(t, "controller uses count", len(ctrl.Uses), 2)
}

// ============================================================
// Helpers
// ============================================================

func mustParse(t *testing.T, raw string, v interface{}) {
	t.Helper()
	if err := json.Unmarshal([]byte(raw), v); err != nil {
		t.Fatalf("failed to parse JSON: %v", err)
	}
}

func assertEqual(t *testing.T, name, got, want string) {
	t.Helper()
	if got != want {
		t.Errorf("%s = %q, want %q", name, got, want)
	}
}

func assertEqualInt(t *testing.T, name string, got, want int) {
	t.Helper()
	if got != want {
		t.Errorf("%s = %d, want %d", name, got, want)
	}
}

func assertEqualFloat(t *testing.T, name string, got, want float64) {
	t.Helper()
	if got != want {
		t.Errorf("%s = %f, want %f", name, got, want)
	}
}

func makeResult() ConvertResult {
	return ConvertResult{}
}

// validateResult runs the same validation as ConvertPython
func validateResult(r *ConvertResult) error {
	for i, d := range r.Devices {
		if d.DeviceID == "" {
			return fmt.Errorf("device %d: device_id is required", i)
		}
		if d.Protocol == "" {
			return fmt.Errorf("device %d (%s): protocol is required", i, d.DeviceID)
		}
		if d.Frequency <= 0 {
			return fmt.Errorf("device %d (%s): frequency must be > 0", i, d.DeviceID)
		}
		switch d.Protocol {
		case "modbus-tcp":
			if d.Connection.Host == "" {
				return fmt.Errorf("device %s: modbus-tcp requires connection.host", d.DeviceID)
			}
		case "modbus-rtu", "serial":
			if d.Connection.SerialPort == "" {
				return fmt.Errorf("device %s: %s requires connection.serial_port", d.DeviceID, d.Protocol)
			}
		case "opcua":
			if d.Connection.Host == "" {
				return fmt.Errorf("device %s: opcua requires connection.host", d.DeviceID)
			}
		}
	}
	for i, s := range r.Storage {
		if s.ID == "" {
			return fmt.Errorf("storage %d: id is required", i)
		}
		if s.Path == "" {
			return fmt.Errorf("storage %d (%s): path is required", i, s.ID)
		}
		if s.MaxSize == 0 {
			return fmt.Errorf("storage %d (%s): max_size must be > 0", i, s.ID)
		}
	}
	for i, o := range r.Outbound {
		if o.ID == "" {
			return fmt.Errorf("outbound %d: id is required", i)
		}
		if o.OutboundType != "mqtt" && o.OutboundType != "s3" {
			return fmt.Errorf("outbound %d (%s): outbound_type must be 'mqtt' or 's3'", i, o.ID)
		}
	}
	for i, c := range r.Controllers {
		if c.ID == "" {
			return fmt.Errorf("controller %d: id is required", i)
		}
		if c.Interval <= 0 {
			return fmt.Errorf("controller %d (%s): interval must be > 0", i, c.ID)
		}
	}
	return nil
}

func assertValidationFails(t *testing.T, r ConvertResult, wantSubstr string) {
	t.Helper()
	err := validateResult(&r)
	if err == nil {
		t.Errorf("expected validation error containing %q, got nil", wantSubstr)
		return
	}
	if !contains(err.Error(), wantSubstr) {
		t.Errorf("error %q does not contain %q", err.Error(), wantSubstr)
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && searchString(s, substr)
}

func searchString(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

func fullExampleJSON() string {
	return `{
		"devices": [
			{"device_id":"temp-sensor","protocol":"modbus-tcp","frequency":5,"connection":{"host":"192.168.1.100","port":502,"slave_id":1},"decode":{"transform_type":"declarative","mappings":[{"from":"reg_40001","to":"temperature","scale":0.1,"offset":0.0}]}},
			{"device_id":"camera","protocol":"serial","frequency":30,"connection":{"serial_port":"/dev/ttyUSB0","baudrate":921600}},
			{"device_id":"plc","protocol":"opcua","frequency":5,"connection":{"host":"10.0.0.1","port":4840,"node_ids":["ns=2;s=Temp"],"security_policy":"None"}}
		],
		"storage": [
			{"id":"images","storage_type":"file","path":"/var/data/images","max_size":1073741824,"warning_threshold":80},
			{"id":"cache","storage_type":"sqlite","path":"/var/data/cache.db","max_size":268435456,"warning_threshold":90}
		],
		"outbound": [
			{"id":"readings","outbound_type":"mqtt","devices":[]},
			{"id":"photos","outbound_type":"s3","devices":["camera"],"storage":"images","prefix":"alerts/{date}/","max_age":"30d"}
		],
		"controllers": [
			{"id":"monitor","interval":5,"uses":["temp-sensor","camera"],"source_file":"controllers/monitor.py"}
		]
	}`
}
