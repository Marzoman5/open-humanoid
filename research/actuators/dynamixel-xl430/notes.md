# XL430-W250 notes (accessed 2026-10-19)
- Rated 11.1V; Niryo reported its 12V bundled adapter caused overheating damage in prolonged operation (fixed in units after Nov 2018) [report](https://blog.zhaw.ch/icclab/?p=12411) (via search summary; NOT re-verified in adversarial pass).
- Hardware error/overload shutdown exists (Shutdown register 63, Hardware Error Status 70); default temp limit 72 C. Repeatedly resetting overload errors without removing cause reportedly burns drivers (AX-12 experience) [ROS answer](https://answers.ros.org/answers/239226/revisions).
- Temperature sensor is on the PCB, far from motor on MX series; shock/stall can damage before it reads hot [Poppy forum](https://poppy.discourse.group/t/faults-in-or-improvements-that-can-be-made-to-dynamixel-firmware/2143) (MX/older, not XL430-specific).
- Bus: up to 4.5 Mbps TTL; ID range 0-252 (per XM430 page; XL430 same family). Max servos per bus before latency: null.
- Torque/speed strongly voltage dependent: 1.0 / 1.4 / 1.5 N.m at 9 / 11.1 / 12 V.
- Nulls: backlash, continuous-torque measured data, plastic-gear failure reports (none found). Gear material is engineering plastic per e-Manual (verified); plastic gears are the weak point under impact.
