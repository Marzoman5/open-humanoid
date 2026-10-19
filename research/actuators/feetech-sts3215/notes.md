# STS3215 notes (accessed 2026-10-19)

**Vendor rated vs stall (key finding).** Vendor listings give "rated" torque of ~1/3 of stall: 6.5 vs 19.5 kg.cm (7.4V variant) [evelta](https://evelta.com/st3215-7-4v-19kg-1-345-gear-dual-axis-ttl-string-servo-motor/), 10 vs 30 kg.cm at 12V [evelta C018](https://evelta.com/sts3215-c018-12v-30kg-cm-dual-shaft-ttl-serial-servo-metal-gears-magnetic-encoder/); STS3250 16 vs 50 [rcdrone](https://rcdrone.top/ja/products/feetech-sts3250-servo-motor). Another seller advises continuous use <=50% of max [rcdrone](https://rcdrone.top/products/feetech-sts3215-20kg-servo). So even the vendor says continuous ~33%, not 40%. No independent thermal-limit measurement found.

**Spec conflicts.** 19.5 kg.cm is labelled @7.4V by Feetech/servodatabase but @6V by evelta; treat 7.4V = 19.5, 6V = 16.5 as most likely. 7.4V stall current is not published (2.0 A @6V). Operating voltage range differs per seller (6-7.4 vs 4-14). Retailer pages are not the Feetech datasheet.

**Overload/thermal protection.** Vendor: protection when blocked >80% of locked-rotor torque for 2 s; resend position command to clear; both configurable. Overheat is an alarm/flag, with register default max temp 70 C ([wiki](https://aifitlab-wiki.super.site/feetech-servo-motor-docs/feetech-sts-servo-memory-table-analysis)). One seller says torque is disabled >70 C; unresolved whether hard cut.

**Gear/MOSFET failures (anecdotal).** HomeBrew Robotics Club thread (Aug 2026): SO101 STS3215 (30 kg.cm) gears stripped on stalls above ~15% of max torque limit (~4.5 kg.cm); 3 servos burned out. Another poster reports internal MOSFETs blowing before gears stripped; advice: fuses, lower voltage during debug, soft ramps. [thread](https://groups.google.com/g/hbrobotics/c/wMPp7it97i4). Single anecdote, unverified.

**Variants.** SO-ARM101: C001 1:345 (7.4V), C044 1:191, C046 1:147; 12V C018/C047 ~30 kg.cm with different gear materials [horndeer README](https://github.com/horndeer/SO-ARM101-LeRobot), [servodatabase](https://servodatabase.com/servo/feetech/sts3215). Mixed lineups are sold; a 1:145 typo exists on one Seeed page.

**Bus.** 1 Mbps default, 38.4k-1M, half-duplex TTL, ID 0-253 [waveshare](https://www.waveshare.com/wiki/ST3215_Servo). Max servos per bus before latency limits: null (not found). EEPROM must be unlocked (lock reg 55) to persist settings; torque-enable reg 40 value 128 = calibrate midpoint. Multi-byte values little-endian. Sign handling of position/speed in STS uses a sign bit (not verified here).

**Sim-model pitfall.** Popular MJCF has kp 998 / kv 2.7 / +-2.94 vs upstream kp 17.8; stiff gains saturate at 0.17 deg error [blog](https://mcobzarenco-fontaine-blog.static.hf.space/posts/2026-08-11-sim-servo-sysid.html). Real servo lags commands ~2.2 deg mean at 30 Hz.

**Counterfeits/QC.** No STS3215 clone teardown found (null). Listings disagree on motor type (coreless vs cored) and gear material (metal/steel/copper) [servodatabase](https://servodatabase.com/servo/feetech/sts3215). Buy from Feetech distributors; verify with register readout.

**Not found:** voltage-sag behavior, per-variant 1:191/1:147 speed/current, backlash measured.
