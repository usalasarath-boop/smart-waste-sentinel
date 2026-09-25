"""
BH1750 Ambient Light Sensor Driver (I2C)
========================================
Measures ambient illuminance in Lux via the I2C bus on Raspberry Pi 5.

Why BH1750?
- Operating range: 1 to 65,535 Lux (matches human eye spectral sensitivity).
- High resolution: 1 Lux resolution in Continuously High-Resolution Mode.
- Direct digital output over I2C eliminates analog-to-digital converter (ADC) requirements.
- Critical for autonomous day/night switching of the USB Ring LED light.

I2C Communication Principle:
- Standard Address: 0x23 (when ADDR pin connected to GND).
- Power On Opcode: 0x01.
- Reset Opcode: 0x07.
- Continuous High-Resolution Mode: 0x10.
- Illuminance calculation: Lux = ((MSB << 8) | LSB) / 1.2
"""

import time
import logging
import random

logger = logging.getLogger("SmartWasteSentinel.BH1750")

# I2C Command Opcodes for BH1750
CMD_POWER_DOWN = 0x00
CMD_POWER_ON = 0x01
CMD_RESET = 0x07
CMD_CONTINUOUS_HIGH_RES_MODE = 0x10  # 1 lx resolution, measurement time ~120ms
CMD_CONTINUOUS_HIGH_RES_MODE_2 = 0x11  # 0.5 lx resolution, measurement time ~120ms
CMD_CONTINUOUS_LOW_RES_MODE = 0x13  # 4 lx resolution, measurement time ~16ms

class BH1750Sensor:
    """Interface to BH1750 digital ambient light sensor with hardware and simulation fallback."""

    def __init__(self, bus_number: int = 1, address: int = 0x23, simulate_if_missing: bool = True):
        self.bus_number = bus_number
        self.address = address
        self.simulate_if_missing = simulate_if_missing
        self.is_simulated = False
        self.bus = None
        self._manual_simulated_lux = None  # Allows manual testing override

        self._initialize_hardware()

    def _initialize_hardware(self):
        """Attempts to open I2C bus and configure sensor; falls back to simulation if unavailable."""
        try:
            import smbus2
            self.bus = smbus2.SMBus(self.bus_number)
            # Power up the sensor
            self.bus.write_byte(self.address, CMD_POWER_ON)
            time.sleep(0.02)
            # Set continuous high-resolution mode
            self.bus.write_byte(self.address, CMD_CONTINUOUS_HIGH_RES_MODE)
            time.sleep(0.18)  # Wait for first conversion
            self.is_simulated = False
            logger.info("BH1750 hardware detected on I2C bus %d at address 0x%02X", self.bus_number, self.address)
        except Exception as e:
            if self.simulate_if_missing:
                self.is_simulated = True
                self.bus = None
                logger.warning("BH1750 hardware not detected (%s). Active: SIMULATION MODE.", e)
            else:
                raise RuntimeError(f"Failed to initialize BH1750 hardware on I2C bus {self.bus_number}: {e}")

    def read_lux(self) -> float:
        """
        Reads ambient light level from BH1750 in Lux.
        
        Returns:
            float: Illuminance in Lux rounded to 2 decimal places.
        """
        if self._manual_simulated_lux is not None:
            return round(self._manual_simulated_lux, 2)

        if self.is_simulated:
            # Generate realistic fluctuating ambient light reading
            base = 45.0  # Around dusk threshold
            noise = random.uniform(-4.0, 4.0)
            return round(max(0.0, base + noise), 2)

        try:
            # Read 2-byte word from I2C bus
            data = self.bus.read_i2c_block_data(self.address, CMD_CONTINUOUS_HIGH_RES_MODE, 2)
            # Combine MSB and LSB
            raw_value = (data[0] << 8) | data[1]
            # Convert raw counts to Lux according to ROHM datasheet
            lux = raw_value / 1.2
            return round(lux, 2)
        except Exception as e:
            logger.error("Error reading from BH1750 at 0x%02X: %s", self.address, e)
            # Re-attempt power cycle on bus error
            try:
                self._initialize_hardware()
            except Exception:
                pass
            return 0.0

    def set_simulation_lux(self, lux: float = None):
        """Allows test suites or web UI to simulate daytime or nighttime lighting on demand."""
        self._manual_simulated_lux = lux
        logger.info("Manual Lux simulation set to: %s", lux)

    def close(self):
        """Closes the I2C bus handle."""
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
