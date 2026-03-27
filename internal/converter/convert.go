package converter

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

// ConvertResult holds all extracted resources from a v1.0 SDK project.
type ConvertResult struct {
	Devices     []DeviceConfig     `json:"devices"`
	Storage     []StorageConfig    `json:"storage"`
	Outbound    []OutboundConfig   `json:"outbound"`
	Controllers []ControllerConfig `json:"controllers"`
}

// DeviceConfig represents a device extracted from Python.
type DeviceConfig struct {
	DeviceID   string           `json:"device_id" yaml:"device_id"`
	Protocol   string           `json:"protocol" yaml:"protocol"`
	Frequency  int              `json:"frequency" yaml:"frequency"`
	Filter     []string         `json:"filter,omitempty" yaml:"filter,omitempty"`
	Connection ConnectionConfig `json:"connection" yaml:"connection"`
	Decode     *DecodeConfig    `json:"decode,omitempty" yaml:"decode,omitempty"`
}

// ConnectionConfig represents device connection parameters.
type ConnectionConfig struct {
	// Modbus TCP
	Host    string  `json:"host,omitempty" yaml:"host,omitempty"`
	Port    int     `json:"port,omitempty" yaml:"port,omitempty"`
	Timeout float64 `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Retries int     `json:"retries,omitempty" yaml:"retries,omitempty"`

	// Shared (Modbus TCP + RTU)
	SlaveID int `json:"slave_id,omitempty" yaml:"slave_id,omitempty"`

	// Serial / Modbus RTU
	SerialPort string `json:"serial_port,omitempty" yaml:"serial_port,omitempty"`
	Baudrate   int    `json:"baudrate,omitempty" yaml:"baudrate,omitempty"`
	Parity     string `json:"parity,omitempty" yaml:"parity,omitempty"`
	Stopbits   int    `json:"stopbits,omitempty" yaml:"stopbits,omitempty"`
	Bytesize   int    `json:"bytesize,omitempty" yaml:"bytesize,omitempty"`

	// OPC-UA
	NodeIDs        []string `json:"node_ids,omitempty" yaml:"node_ids,omitempty"`
	SecurityPolicy string   `json:"security_policy,omitempty" yaml:"security_policy,omitempty"`
	Username       string   `json:"username,omitempty" yaml:"username,omitempty"`
	Password       string   `json:"password,omitempty" yaml:"password,omitempty"`

	// BLE
	MAC             string              `json:"mac,omitempty" yaml:"mac,omitempty"`
	ServiceUUID     string              `json:"service_uuid,omitempty" yaml:"service_uuid,omitempty"`
	Characteristics []BLECharacteristic `json:"characteristics,omitempty" yaml:"characteristics,omitempty"`
	ScanTimeout     float64             `json:"scan_timeout,omitempty" yaml:"scan_timeout,omitempty"`
}

// BLECharacteristic represents a BLE GATT characteristic to read.
type BLECharacteristic struct {
	Name string `json:"name" yaml:"name"`
	UUID string `json:"uuid" yaml:"uuid"`
}

// DecodeConfig describes how to transform raw device data.
type DecodeConfig struct {
	TransformType string         `json:"transform_type" yaml:"transform_type"`
	Mappings      []FieldMapping `json:"mappings" yaml:"mappings"`
	WasmModule    string         `json:"wasm_module,omitempty" yaml:"wasm_module,omitempty"`
}

// FieldMapping is a single field transform rule.
type FieldMapping struct {
	From      string  `json:"from" yaml:"from"`
	To        string  `json:"to" yaml:"to"`
	Scale     float64 `json:"scale" yaml:"scale"`
	Offset    float64 `json:"offset" yaml:"offset"`
	FieldType string  `json:"field_type,omitempty" yaml:"field_type,omitempty"`
	Start     *int    `json:"start,omitempty" yaml:"start,omitempty"`
	Length    *int    `json:"length,omitempty" yaml:"length,omitempty"`
}

// StorageConfig represents a storage backend extracted from Python.
type StorageConfig struct {
	ID               string `json:"id" yaml:"id"`
	StorageType      string `json:"storage_type" yaml:"storage_type"`
	Path             string `json:"path" yaml:"path"`
	MaxSize          uint64 `json:"max_size" yaml:"max_size"`
	WarningThreshold int    `json:"warning_threshold" yaml:"warning_threshold"`
}

// OutboundConfig represents an outbound destination extracted from Python.
type OutboundConfig struct {
	ID           string   `json:"id" yaml:"id"`
	OutboundType string   `json:"outbound_type" yaml:"outbound_type"`
	Devices      []string `json:"devices" yaml:"devices"`
	Storage      string   `json:"storage,omitempty" yaml:"storage,omitempty"`
	Prefix       string   `json:"prefix,omitempty" yaml:"prefix,omitempty"`
	MaxAge       string   `json:"max_age,omitempty" yaml:"max_age,omitempty"`
}

// ControllerConfig represents a controller extracted from Python.
type ControllerConfig struct {
	ID         string   `json:"id" yaml:"id"`
	Interval   int      `json:"interval" yaml:"interval"`
	Uses       []string `json:"uses" yaml:"uses"`
	SourceFile string   `json:"source_file" yaml:"source_file"`
}

// ConvertPython runs the Python conversion script and returns all resource configs.
func ConvertPython(repoDir string) (*ConvertResult, error) {
	scriptPath := findScript()
	if scriptPath == "" {
		return nil, fmt.Errorf("convert.py not found")
	}

	cmd := exec.Command("python3", scriptPath, repoDir)
	cmd.Stderr = os.Stderr

	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("python conversion failed: %w", err)
	}

	var result ConvertResult
	if err := json.Unmarshal(out, &result); err != nil {
		return nil, fmt.Errorf("failed to parse converter output: %w (output: %s)", err, string(out))
	}

	// Validate devices
	for i, d := range result.Devices {
		if d.DeviceID == "" {
			return nil, fmt.Errorf("device %d: device_id is required", i)
		}
		if d.Protocol == "" {
			return nil, fmt.Errorf("device %d (%s): protocol is required", i, d.DeviceID)
		}
		if d.Frequency <= 0 {
			return nil, fmt.Errorf("device %d (%s): frequency must be > 0", i, d.DeviceID)
		}
		switch d.Protocol {
		case "modbus-tcp":
			if d.Connection.Host == "" {
				return nil, fmt.Errorf("device %s: modbus-tcp requires connection.host", d.DeviceID)
			}
		case "modbus-rtu", "serial":
			if d.Connection.SerialPort == "" {
				return nil, fmt.Errorf("device %s: %s requires connection.serial_port", d.DeviceID, d.Protocol)
			}
		case "opcua":
			if d.Connection.Host == "" {
				return nil, fmt.Errorf("device %s: opcua requires connection.host", d.DeviceID)
			}
		case "ble":
			// BLE can scan by MAC or service UUID, both optional
		}
	}

	// Validate storage
	for i, s := range result.Storage {
		if s.ID == "" {
			return nil, fmt.Errorf("storage %d: id is required", i)
		}
		if s.Path == "" {
			return nil, fmt.Errorf("storage %d (%s): path is required", i, s.ID)
		}
		if s.MaxSize == 0 {
			return nil, fmt.Errorf("storage %d (%s): max_size must be > 0", i, s.ID)
		}
	}

	// Validate outbound
	for i, o := range result.Outbound {
		if o.ID == "" {
			return nil, fmt.Errorf("outbound %d: id is required", i)
		}
		if o.OutboundType != "mqtt" && o.OutboundType != "s3" {
			return nil, fmt.Errorf("outbound %d (%s): outbound_type must be 'mqtt' or 's3'", i, o.ID)
		}
	}

	// Validate controllers
	for i, c := range result.Controllers {
		if c.ID == "" {
			return nil, fmt.Errorf("controller %d: id is required", i)
		}
		if c.Interval <= 0 {
			return nil, fmt.Errorf("controller %d (%s): interval must be > 0", i, c.ID)
		}
	}

	return &result, nil
}

// DriverName maps a protocol to its driver binary name.
func DriverName(protocol string) string {
	switch protocol {
	case "modbus-tcp", "modbus-rtu":
		return "driver-modbus"
	case "opcua":
		return "driver-opcua"
	case "serial":
		return "driver-serial"
	case "ble":
		return "driver-ble"
	case "mqtt":
		return "driver-mqtt"
	default:
		return "driver-" + protocol
	}
}

// findScript locates convert.py by checking multiple paths.
func findScript() string {
	candidates := []string{
		"/usr/local/bin/convert.py",
		"scripts/convert.py",
	}

	// Also check relative to this source file (for tests run from subdirectories)
	_, thisFile, _, ok := runtime.Caller(0)
	if ok {
		root := filepath.Dir(filepath.Dir(filepath.Dir(thisFile)))
		candidates = append(candidates, filepath.Join(root, "scripts", "convert.py"))
	}

	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}
