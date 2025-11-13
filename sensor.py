"""
sensor.py
Sensor reading abstraction for HC-SR04 (ultrasonic) with RPi.GPIO support.
If RPi.GPIO isn't available (e.g., developing on your PC), it falls back to a simulator.
"""

import time
import random

try:
    import RPi.GPIO as GPIO
    IS_RPI = True
except Exception:
    # Not running on Raspberry Pi or RPi.GPIO not installed
    IS_RPI = False

class UltrasonicSensor:
    """
    Simple HC-SR04 reader.
    - trig_pin: GPIO pin number for TRIG
    - echo_pin: GPIO pin number for ECHO
    - max_distance_cm: max measurable distance to interpret as 'empty'
    """
    def __init__(self, trig_pin=23, echo_pin=24, max_distance_cm=50):
        self.trig = trig_pin
        self.echo = echo_pin
        self.max_distance = max_distance_cm

        if IS_RPI:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.trig, GPIO.OUT)
            GPIO.setup(self.echo, GPIO.IN)
            GPIO.output(self.trig, False)
            time.sleep(0.5)

    def get_distance_cm(self):
        """Return measured distance in cm. If not on RPi, return simulated value."""
        if not IS_RPI:
            # Simulated random distance between 2cm and max_distance
            return random.uniform(2.0, float(self.max_distance))

        # Trigger pulse
        GPIO.output(self.trig, True)
        time.sleep(0.00001)  # 10us
        GPIO.output(self.trig, False)

        pulse_start = time.time()
        timeout = pulse_start + 0.04  # 40ms timeout

        # wait for echo to go high
        while GPIO.input(self.echo) == 0 and time.time() < timeout:
            pulse_start = time.time()

        pulse_end = time.time()
        # wait for echo to go low
        while GPIO.input(self.echo) == 1 and time.time() < timeout:
            pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start
        # speed of sound ~34300 cm/s => distance = (pulse_duration * 34300)/2
        distance_cm = (pulse_duration * 34300.0) / 2.0
        # If measurement fails or is greater than max_distance, clamp
        if distance_cm <= 0 or distance_cm > 400:
            return float(self.max_distance)
        return min(distance_cm, float(self.max_distance))

    def get_fill_level_percent(self, bin_height_cm):
        """
        Convert distance reading to % fill.
        bin_height_cm: physical height from sensor to bottom (or maximum measurable distance)
        0% -> empty (distance == bin_height), 100% -> full (distance == near 0)
        """
        dist = self.get_distance_cm()
        # Cap to bin height
        effective_dist = min(dist, bin_height_cm)
        # fill = (1 - distance/height) * 100
        fill = (1.0 - (effective_dist / float(bin_height_cm))) * 100.0
        # clamp
        fill = max(0.0, min(100.0, fill))
        return round(fill, 1)

    def cleanup(self):
        if IS_RPI:
            GPIO.cleanup()
