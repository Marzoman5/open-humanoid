# XM430 notes (accessed 2026-10-19)
- Metal gears, coreless, 15 arcmin backlash (vendor) [W350](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/). Min input 10 V: below it not specified.
- Defaults: temperature limit 80 C, current limit 1193 (~3.2 A), position P 800 / I 0 / D 0 (KPP=v/128, KPI=v/65536, KPD=v/16).
- Manual text swaps Max/Min Voltage Limit descriptions vs table (addr 32 max, 34 min) - verify on device.
- Poppy forum: on MX-series the temp sensor is on the PCB far from the motor; shock-induced overheating may not be caught [forum](https://poppy.discourse.group/t/faults-in-or-improvements-that-can-be-made-to-dynamixel-firmware/2143) (MX, not XM-specific).
- Stall at 12V: W350 4.1 N.m @2.3 A; W210 3.0 N.m @2.3 A.
- e-Manual (verified 2026-10-19): no continuous/rated torque figure; states stall rating "is different from it's continuous output rating" and max torque on the performance graph is less than stall. Standby current 40 mA; radial load 40 N, axial 20 N.
- Nulls: measured continuous torque, thermal time constants, W350 identification, counterfeits.
