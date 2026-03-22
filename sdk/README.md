# Scadable Edge SDK

Python SDK for defining devices on the Scadable IoT platform.

## Installation

```bash
pip install scadable-cli
```

## Usage

Create a `config.py` for your device:

```python
from scadable.edge import Device, ModbusConnection
from scadable.edge.constants import MODBUS_TCP, FIVE_SEC
from dataclasses import dataclass

@dataclass
class Connection(ModbusConnection):
    host: str = "${DEVICE_HOST}"
    port: int = 502
    slave_id: int = 1

class MyPLC(Device):
    id = "device-001"
    protocol = MODBUS_TCP
    connection = Connection
    frequency = FIVE_SEC
```

## Project Structure

```
gateways/
    gateway-001/
        device-001/
            config.py
        device-002/
            config.py
```
