package converter

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
)

// DeviceConfig represents a device configuration extracted from Python.
type DeviceConfig struct {
	DeviceID   string           `json:"device_id" yaml:"device_id"`
	Protocol   string           `json:"protocol" yaml:"protocol"`
	Frequency  int              `json:"frequency" yaml:"frequency"`
	Filter     []string         `json:"filter,omitempty" yaml:"filter,omitempty"`
	Connection ConnectionConfig `json:"connection" yaml:"connection"`
}

// ConnectionConfig represents device connection parameters.
type ConnectionConfig struct {
	Host       string  `json:"host,omitempty" yaml:"host,omitempty"`
	Port       int     `json:"port,omitempty" yaml:"port,omitempty"`
	SlaveID    int     `json:"slave_id,omitempty" yaml:"slave_id,omitempty"`
	Timeout    float64 `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Retries    int     `json:"retries,omitempty" yaml:"retries,omitempty"`
	SerialPort string  `json:"serial_port,omitempty" yaml:"serial_port,omitempty"`
	Baudrate   int     `json:"baudrate,omitempty" yaml:"baudrate,omitempty"`
	Parity     string  `json:"parity,omitempty" yaml:"parity,omitempty"`
	Stopbits   int     `json:"stopbits,omitempty" yaml:"stopbits,omitempty"`
}

// ConvertPythonToDevices runs the Python conversion script and returns device configs.
func ConvertPythonToDevices(repoDir string) ([]DeviceConfig, error) {
	// The convert.py script is bundled at /usr/local/bin/convert.py in the Docker image.
	// For local dev, check if it exists alongside the binary.
	scriptPath := "/usr/local/bin/convert.py"
	if _, err := os.Stat(scriptPath); os.IsNotExist(err) {
		// Try relative path for local development
		scriptPath = "scripts/convert.py"
		if _, err := os.Stat(scriptPath); os.IsNotExist(err) {
			return nil, fmt.Errorf("convert.py not found at /usr/local/bin/convert.py or scripts/convert.py")
		}
	}

	cmd := exec.Command("python3", scriptPath, repoDir)
	cmd.Stderr = os.Stderr

	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("python conversion failed: %w", err)
	}

	var devices []DeviceConfig
	if err := json.Unmarshal(out, &devices); err != nil {
		return nil, fmt.Errorf("failed to parse converter output: %w (output: %s)", err, string(out))
	}

	// Validate
	for i, d := range devices {
		if d.DeviceID == "" {
			return nil, fmt.Errorf("device %d: device_id is required", i)
		}
		if d.Protocol == "" {
			return nil, fmt.Errorf("device %d (%s): protocol is required", i, d.DeviceID)
		}
		if d.Frequency <= 0 {
			return nil, fmt.Errorf("device %d (%s): frequency must be > 0", i, d.DeviceID)
		}
		// Protocol-specific validation
		switch d.Protocol {
		case "modbus-tcp":
			if d.Connection.Host == "" {
				return nil, fmt.Errorf("device %s: modbus-tcp requires connection.host", d.DeviceID)
			}
		case "modbus-rtu":
			if d.Connection.SerialPort == "" {
				return nil, fmt.Errorf("device %s: modbus-rtu requires connection.serial_port", d.DeviceID)
			}
		}
	}

	return devices, nil
}

// DriverName maps a protocol to its driver binary name.
func DriverName(protocol string) string {
	switch protocol {
	case "modbus-tcp", "modbus-rtu":
		return "driver-modbus"
	case "opcua":
		return "driver-opcua"
	case "mqtt":
		return "driver-mqtt"
	default:
		return "driver-" + protocol
	}
}
