"""Measured actuator models for the concept engine (ADR 0012): BAM-style STS3215 plus datasheet-anchored variants.

    from openhumanoid.actuators import servo_spec, ServoBank, ThermalBank
    spec = servo_spec("sts3215-7v4")          # BAM-identified, 7.4 V
    spec12 = servo_spec("sts3215-12v")        # extrapolated: datasheet-anchored, dynamics borrowed from the 7.4 V fit
    spec.tau_available(w=2.0, vin=7.4)        # N*m available at 2 rad/s (conservative stall cap)
"""
from .servo import (ServoBank, ServoSpec, ThermalBank, bam_models_available, bam_params, bam_source, friction_budget,
                    known_servo_ids, servo_spec)

__all__ = ["ServoBank", "ServoSpec", "ThermalBank", "bam_models_available", "bam_params", "bam_source",
           "friction_budget", "known_servo_ids", "servo_spec"]
