"""
USB Ring LED Light Controller (GPIO)
====================================
Switches high-output 5V USB Ring LED on Raspberry Pi 5 via GPIO 18.

Why a switching circuit?
- Raspberry Pi GPIO pins output 3.3V and can safely source a maximum of ~16mA per pin.
- A USB Ring LED operates at 5V and draws between 300mA and 1500mA (1.5W to 7.5W).
- Connecting the LED directly to a GPIO pin would permanently damage the Raspberry Pi's SoC!
- Therefore, GPIO 18 drives the Base of an NPN transistor (e.g. 2N2222) through a 1kΩ resistor
  or the Gate of an N-Channel Logic MOSFET (e.g. IRLZ44N, AO3400, or a 5V optocoupler relay module).
"""

import logging
import threading

logger = logging.getLogger("SmartWasteSentinel.LED")

class LEDController:
    """Thread-safe controller for the USB Ring LED light."""

    def __init__(self, pin: int = 18, simulate_if_missing: bool = True):
        self.pin = pin
        self.simulate_if_missing = simulate_if_missing
        self.is_simulated = False
        self._state = False  # False = OFF, True = ON
        self._lock = threading.Lock()
        self._device = None

        self._initialize_hardware()

    def _initialize_hardware(self):
        """Attempts to initialize gpiozero OutputDevice on the specified pin."""
        try:
            from gpiozero import OutputDevice
            # Active high: True sets GPIO high (3.3V), saturating the NPN/MOSFET gate
            self._device = OutputDevice(self.pin, active_high=True, initial_value=False)
            self.is_simulated = False
            self._state = False
            logger.info("GPIO LED Controller initialized on BCM pin %d", self.pin)
        except Exception as e:
            if self.simulate_if_missing:
                self.is_simulated = True
                self._device = None
                self._state = False
                logger.warning("GPIO hardware not available (%s). Active: SIMULATION MODE.", e)
            else:
                raise RuntimeError(f"Failed to initialize GPIO pin {self.pin}: {e}")

    def turn_on(self):
        """Turns the Ring LED ON."""
        with self._lock:
            if not self._state:
                if self._device is not None:
                    try:
                        self._device.on()
                    except Exception as e:
                        logger.error("Failed to write to GPIO pin %d: %s", self.pin, e)
                self._state = True
                logger.info("Ring LED turned ON (Night Mode active)")

    def turn_off(self):
        """Turns the Ring LED OFF."""
        with self._lock:
            if self._state:
                if self._device is not None:
                    try:
                        self._device.off()
                    except Exception as e:
                        logger.error("Failed to write to GPIO pin %d: %s", self.pin, e)
                self._state = False
                logger.info("Ring LED turned OFF (Daylight sufficient)")

    def toggle(self) -> bool:
        """Toggles the current LED state."""
        if self._state:
            self.turn_off()
        else:
            self.turn_on()
        return self._state

    def is_on(self) -> bool:
        """Returns True if the LED is currently illuminated."""
        with self._lock:
            return self._state

    def cleanup(self):
        """Releases GPIO resources."""
        with self._lock:
            if self._device is not None:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None
            self._state = False
