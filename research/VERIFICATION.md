# VERIFICATION: second-pass audit of the evidence base (2026-10-19)

Every claim in `SUMMARY.md` and the numbers behind it were re-checked against the cited source by independent agents. Status: **verified** (exact number and context confirmed), **corrected** (number or context fixed in the files), **unsupported** (no source found; removed or nulled), **unreachable** (source blocked; not kept as confirmed). Caveat: verifiers are model agents using WebFetch; sources behind 403s or image-only PDFs stayed unconfirmed.

## What changed in SUMMARY.md after verification
| Item | Change |
|---|---|
| 1 | "33%" softened to 26–33% vendor-rated; Robotis "20%" rule and "≤50% seller advice" unsupported (404/403) and dropped; Robonine bench added |
| 2 | Fit updated 18.2·h^2.26 → 18.5·h^2.28 (R² 0.93) after R1/Asimov/Poppy fixes; still 3.8 kg at 0.5 m |
| 3 | 1.9 N·m is the **7.4 V** figure (not 6 V); 12 V part is 2.94 N·m |
| 4 (old) | "Open Duck Mini uses BAM" unsupported; removed |
| 5 | BAM numbers verified; "7.4 V" is a directory name, supply voltage not documented |
| 6 | Open Duck active values corrected (kp 13.37, ±3.23, 0.56, 0.068, 0.027); 108 vs 998 claim verified but belongs to the blog fit |
| 7 | Action delay 0–2 steps (≤40 ms), not 0–60 ms |
| 8 | "trips at 70 °C and overcurrent ~2 A/2 s" corrected: 70 °C is a register default; the 2 A/2 s claim is unsupported |
| new | 7.4 V vs 12 V ambiguity resolved; PID defaults, backlash, Robonine bench added |

## Resolved ambiguity
19.5 kg·cm is the **7.4 V** C001 figure (16.5 at 6 V); Evelta's "19.5 @6V" is a labelling error. 30 kg·cm is the 12 V C018/C047. Both 1:345. Sources: feetechrc.com product page, Waveshare ST3215 page, Evelta, Seeed.

## Detailed claim tables
Each table: claim | file | status | evidence.


---

### Feetech verification (accessed 2026-10-19)

Status: verified / corrected / unsupported / unreachable. "Quotes" are exact or near-exact page text.

#### SKU table (primary + retailer sources)

| SKU | V | ratio | stall | rated | no-load | stall I | source |
|---|---|---|---|---|---|---|---|
| C001 | 7.4 | 1:345 | 19.5 kg.cm @7.4V | not on Feetech page; 6.5 @6V (Evelta), 5 (Seeed) | 52 rpm @7.4V (0.192 s/60) | 2.5 A @7.4V (Waveshare); 2.0 A @6V | feetechrc.com/en/2020-05-13_56655.html; waveshare.com/st3215-servo.htm; seeedstudio p-6338 |
| C018 (12V) | 12 | 1:345 | 30 kg.cm | 10 kg.cm | 45 rpm (0.222 s/60) | 2.7 A | evelta C018; waveshare; openelab; Robonine |
| C047 (12V) | 12 | 1:345 | 30 | 10 | n/a | n/a | seeedstudio p-6340 |
| C044 | 7.4 | 1:191 | null | null | null | null | horndeer README (leader arm) |
| C046 | 7.4 | 1:147 | null (14.4 unsupported) | null | null | null | horndeer README; eckstein lists only "20KG" |
| STS3250 C001/C002 | 12 | C002: 345 | 50 | 16 | 75 rpm (0.133 s/60) | 4.2 A | feetechrc.com/en/562636; rcdrone; openelab |

Answers: 19.5 kg.cm = 7.4 V (Feetech: "Stall Torque：19.5kg.cm@7.4V"); 16.5 @6V. 30 kg.cm = 12 V ("30kg.cm@12V", Waveshare/Evelta). Evelta/rcdrone/core-electronics labelling 19.5 as @6V conflicts with Feetech: treated as label error. 7.4 V part kt 7.8 kg.cm/A vs 12 V part 11 kg.cm/A: different motors.

3S LiPo on 7.4V variants: Waveshare "4V ~ 7.4V" for the 7.4V SKU; Evelta/rcdrone "6-7.4V". 12.6 V exceeds rating; no failure report found, no tolerance evidence. 12V part: "6 ~ 12.6 V" (Waveshare) so 3S full is in range.

#### Claims

| claim | file | status | evidence |
|---|---|---|---|
| C001 gear ratio 345 | sts3215/datasheet | verified | feetechrc.com/en/2020-05-13_56655.html "1:345 copper Gear combination" |
| nominal 7.4V | sts3215/datasheet | verified | same page "7.4V 19KG.CM ..." |
| stall 19.5 @7.4V | sts3215/datasheet | verified | Feetech "Stall Torque：19.5kg.cm@7.4V" |
| stall 16.5 @6V | sts3215/datasheet | verified (aggregator) | servodatabase "6.0 V: 16.53 kg-cm"; switch-science 16.5@6V |
| evelta "19.5 @6V" | sts3215/datasheet | corrected (label conflict) | evelta "Peak stall torque 19.5 kg·cm @ 6 V" vs Feetech @7.4V |
| voltage range 6-7.4 (evelta); 4-14 (servodatabase) | sts3215/datasheet | corrected | servodatabase 4-14 is generic entry; Waveshare 7.4V SKU "4V ~ 7.4V"; 12V SKU "6 ~ 12.6 V" |
| rated 6.5 @6V | sts3215/datasheet | verified as retailer figure; Seeed says 5 | evelta "6.5 kg·cm @ 6 V"; seeed "Rated torque 5 kg·cm" |
| no-load 52 rpm @7.4V | sts3215/datasheet | verified | waveshare "0.192sec/60°(52RPM)@7.4V"; Feetech calls it "Stall Speed 52RPM@7.4V" |
| 42 rpm @6V | sts3215/datasheet | verified | evelta "0.238 sec/60° @ 6 V (about 42 RPM)" |
| stall current "2.0-2.7 A" | sts3215/datasheet | corrected | 7.4V: 2.5 A (Waveshare "2.5A"); 6V: 2000 mA (evelta); range is mixed variants |
| no-load current 150 mA @6V | sts3215/datasheet | verified (also 150 @7.4V Waveshare; switch-science says 130 @6V) | evelta "150 mA @ 6 V" |
| running current 650 mA @7.4V | sts3215/datasheet | unsupported -> null | not on servodatabase page on re-fetch |
| C046 14.4 kg.cm | sts3215/datasheet | unsupported -> null | eckstein C046: "20KG"/"19kg", no ratio |
| C044 191, C046 147 | sts3215/datasheet | verified | horndeer README "1/191", "1/147", 7.4V |
| C018 gear ratio null | sts3215/datasheet | corrected -> 345 | seeed C047 "1:345"; openelab C018; Robonine "1:345" |
| C018 30 @12V, rated 10 | sts3215/datasheet | verified | evelta "Peak Stall Torque 30kg.cm @12V; Rated 10kg.cm @12V" |
| 12V 45 rpm, 2.7 A | sts3215/datasheet | verified | waveshare "0.222sec/60°（45RPM）@12V"; "Locked-rotor Current: 2.7 A"; Robonine measured 45.6 rpm |
| 12V no-load 180 / 200 mA | sts3215/datasheet | verified | evelta "180 mA @12V"; waveshare table "200mA" |
| weight 55±1 g | sts3215/datasheet | verified | evelta "55 ± 1 g" |
| size 45.2x24.7x35 | sts3215/datasheet | verified | servodatabase |
| encoder 12-bit, 4096, 0.088° | sts3215/datasheet | verified (Robonine); Feetech page extract silent | robonine "12-bit, 4096 steps/rev (0.088°)" |
| backlash 0.87° (aggregator, "unverified") | sts3215/datasheet | verified as servodatabase figure; independently measured on 1 C018 | servodatabase "0.870°"; robonine "≈0.87°", datasheet "≤ 0.5°" |
| baud 38400-1M, default 1M | sts3215/datasheet | verified | robonine "38400 bps to 1 Mbps"; waveshare "Baudrate: 1Mbps" |
| IDs 0-253 half-duplex | sts3215/datasheet | verified | commanderfun register ref "Range 0-253"; RobotShop summary |
| operating temp -20..60 | sts3215/datasheet | verified | servodatabase "-20–60 °C"; evelta C001 "-15 to 70" |
| max temp register 70 | sts3215/datasheet | verified | commanderfun reg 13 default 70 |
| overload "80% locked-rotor for 2 s, clears on new command" | sts3215/datasheet | corrected | regs: Overload_Torque 80 (%), Protection_Time 200, Protective_Torque 20 (commanderfun); rcdrone "unloading force lasts 2S (20% of default blocking force)"; "clears on new command" unsupported; core-electronics PDF image-only (unreachable) |
| "continuous <=50% of max" (rcdrone) | sts3215/datasheet | unreachable -> null | rcdrone page HTTP 403; sw-language page has no such text |
| current unit 6.5 mA | sts3215/datasheet | verified | Feetech page "1 = 6.5mA" |
| addresses (id5 ... current69) | sts3215/datasheet | verified | LeRobot v0.4.0 tables.py STS_SMS_SERIES_CONTROL_TABLE |
| max_torque 1000, overload 80, max_temp 70 | sts3215/datasheet | verified | aifitlab wiki, commanderfun |
| protection_current default 511 | sts3215/datasheet | conflict -> unconfirmed | aifitlab "511"; commanderfun "0" (x6.5 mA) |
| min_voltage default 40 (0.1V) | sts3215/datasheet | conflict -> unconfirmed | commanderfun min 50, max 140; its sample read 4.0-14.0 V |
| Kp/Kd defaults null | sts3215/datasheet | corrected -> P32 D32 I0 | commanderfun "P 32, D 32, I 0"; tomwhipple "Factory values are P 32 and D 32" |
| LeRobot overrides | sts3215/datasheet (new) | verified | config_so_follower.py p=16 i=0 d=32; gripper Max_Torque 500, Protection_Current 250, Overload_Torque 25 |
| baud codes 5=76.8k, 6=57.6k, 7=38.4k | sts3215/datasheet | corrected | LeRobot: 4=115.2k 5=57.6k 6=38.4k 7=19.2k |
| BAM m1/m6 params | sts3215/measured | verified | raw m1.json, m6.json match |
| BAM voltage 7.4V | sts3215/measured | partly verified | only directory name "feetech_sts3215_7_4V"; abstract/README silent on voltage |
| BAM "waveshare_st3025" in BAM | sts3250/measured | **CORRECTED 2026-10-19 (challenge #1, row 17): exists.** The earlier "unsupported" verdict checked only the README. `bam/params/` contains `waveshare_st3025` (12 V Feetech-class; `bam/waveshare/actuator.py` reuses the STS3215 error gain and fits its own error_gain_ratio). It is the only published 12 V Feetech-class firmware-level model, so use it to size 12 V uncertainty | https://github.com/Rhoban/bam/tree/main/bam/params ; https://github.com/Rhoban/bam/blob/main/bam/waveshare/actuator.py |
| mcobzarenco fit values | sts3215/measured | verified | blog "kp 108.18, kv 13.377, forcerange ±3.478 ..." ; fit on six servos, applied to twelve; lag 2.19° |
| "no independent torque/thermal data exists" | sts3215/measured, notes | corrected | Robonine (12V C018): stall ~35 kg.cm, 71 °C after ~110 min at 15 kg.cm oscillation |
| HBRC gear-strip anecdote | sts3215/notes | verified (anecdote) | "gears strip when there is a stall of over 15% of the max torque limit" |
| MOSFET anecdote | sts3215/notes | verified (anecdote) | "I'd blow the MOSFETs on the internal PCBs before I'd strip the gears" |
| "SO101" and "(30 kg.cm)" in thread | sts3215/notes | unsupported (4.5 kg.cm stated, implies 30) | thread names neither SKU nor voltage |
| counterfeit/QC | sts3215/notes | unsupported (none found) | searched; only listing inconsistencies |
| STS3250 50/16/0.133 s/280 mA/4.2 A/74.5 g | sts3250/datasheet | verified | feetechrc.com/en/562636 same values |
| STS3250 range 6-12V, steel gears | sts3250/datasheet | verified | feetechrc/rcdrone |
| STS3250 ratio 345 (C002 only) | sts3250/datasheet | verified | openelab "345:1" |
| STS3250 coreless, alu case, 0-4096 encoder | sts3250/datasheet | verified (rcdrone) | rcdrone table |
| STS3250 backlash/PID/registers | sts3250/datasheet | null kept | not found |

#### SUMMARY.md items (recommended edits; I was not allowed to edit SUMMARY)

| item | status | evidence / fix |
|---|---|---|
| 1 "~33% of stall, not 40%" | partly verified | vendor rated 10/30 (Evelta, Seeed C047), 6.5 or 5 /19.5 (26-33%). But Robonine (12V, 1 unit): 15 kg.cm = 50% held +15 °C/10 min, 48 °C static >1 h, 71 °C after ~110 min oscillating. Soften: vendor-rated is 26-33%; one independent test tolerated 50% for ~1-2 h; thermal limit still unmeasured at 7.4 V. "One seller advises <=50%" is unverified (page 403). |
| 3 "1.9 N·m at 6 V" | corrected | 19.5 kg.cm = 1.91 N·m is at 7.4 V; 6 V = 16.5 kg.cm = 1.62 N·m. 12 V 30 kg.cm = 2.94 N·m ok. Ambiguity is resolved (see above). 3S 12.6 V is within the 12V part's rating, outside the 7.4V part's. |
| 5 "model exists only at 7.4 V" | partly verified | BAM m4 numbers match (kt 1.2653, R 2.4724, armature 0.02336, delay 4.9 ms, vmax 5.071). The "7.4 V" is only the directory name; supply voltage not documented. No 12V BAM set: verified. |
| 8 "trips at 70 °C and overcurrent ~2 A for 2 s" | corrected | 70 °C is the Max_Temperature_Limit register default; Robonine saw an overheat flag at 70 °C but no active shutdown at 71 °C. "~2 A for 2 s overcurrent" unsupported (2 A is the 6V stall current; overcurrent defaults conflict). Overload default: 80 % torque, protection time 200 (unit unconfirmed), then torque cut to ~20 %. |
| 8 "derate to ~50% load" | not supported as stated | Robonine 15 of 30 kg.cm survived ~1-2 h; derating figure is a judgement, not sourced. |
| 9 gears/MOSFET anecdotes | verified (2 posts, Aug 2026) | quotes above; no SKU/voltage |

#### New findings
- Robonine independent bench (12V C018): backlash 0.87°, repeatability ~0.17°, static stall ~35 kg.cm, 20 kg.cm trips overload, 15 kg.cm thermal data, 45.6 rpm, ~2° position error under 10 kg.cm. https://robonine.com/testing-of-feetech-sts3215-servomotor-backlash-repeatability-and-torque/
- 7.4V and 12V parts differ in kt (7.8 vs 11 kg.cm/A), stall current (2.5 vs 2.7 A): Waveshare comparison table.
- Factory PID is P32/D32/I0; LeRobot lowers P to 16 (SO-ARM). Community stiffness study: tomwhipple issue 73 (P128 ~3.5x stiffness, shakes ~15 Hz).
- LeRobot gripper protection: Max_Torque_Limit 500, Protection_Current 250, Overload_Torque 25.
- Earlier baud-code table was wrong (LeRobot code above is authoritative).
- Waveshare lists the 7.4V SKU voltage as 4-7.4 V while sellers say 6-7.4 V.

#### Remaining unknowns (measure only)
- Real continuous/thermal limit of the 7.4V C001 and of the 12V part at 3S pack voltages and robot duty cycle.
- Whether a 7.4V part survives 12.6 V (do not test on purchased units without a spare).
- Protection_Time unit, Protection_Current default, min/max voltage defaults, overload/overcurrent trip actually observed.
- C001 backlash; C044/C046 torque, speed, current; STS3250 registers, backlash, measured torque.
- Torque-enable 128 midpoint calibration, byte order, sign-bit handling (not verified here).
- Voltage-sag behaviour, max servos per bus at 1 Mbps.
- Counterfeit/clone prevalence.

---

### Verification: robots/benchmarks (2026-10-19)

| claim | file | status | evidence |
|---|---|---|---|
| ToddlerBot 0.56 m, 3.4 kg (3484 g), 30 DOF (6/leg, 7/arm, neck 2, waist 2) | benchmarks.yaml | verified | https://arxiv.org/html/2502.00893v4 |
| ToddlerBot motors/torques: knee XM430-W210 3.0 Nm stall, hip pitch/roll 2XC430 1.8, hip yaw XC330 1.0; est. need knee 2.35 | yaml/md | verified | same arXiv Table 2 |
| ToddlerBot <$6k, Orin NX 16GB, 14.8 V options, 75 Wh/h, zero-shot walking, 7 falls, 19 min | yaml | verified | same |
| ToddlerBot walking speed null | yaml | verified null (not stated) | same |
| Open Duck Mini v2 0.42 m, BOM "under $400" | yaml | verified (target, not measured) | https://github.com/apirrone/Open_Duck_Mini ("about 42 centimeters", "under $400") |
| ODM 14x STS3215 7.4 V, 2S 3000 mAh, Pi Zero 2W | yaml | verified (reseller only; reseller page itself inconsistent on Pi Zero vs Pi 5) | https://aifitlab.com/products/openduckmini-open-source-version-of-the-bdx-droid ; reseller kit price $910 |
| ODM mass | yaml | unsupported -> stays null | README, prepare_robot.md, reseller: no mass |
| ODM sim2real only partial | yaml/md | verified | README only has "Big progress on sim2real" (07/02/2025) and "Working hard on sim2real!" (24/02/2025); no success claim. Note both dates are old; later status not checked |
| Zeroth 16 vs 18 servos | yaml | corrected: 16 (secondary), 18 not found | https://circuitdigest.com/news/zeroth-bot-an-opensource-risc-v-powered-humanoid-robot "16 STS3215/50"; repo READMEs silent; docs.zeroth.bot, docs.kscale.dev unreachable |
| Zeroth 5 DOF/leg, 4/arm | yaml | unsupported -> nulled | not in repo or circuitdigest |
| Zeroth BOM from $350 | yaml | verified | github.com/kscalelabs/zeroth-bot |
| Zeroth status | yaml | corrected: kscalelabs README "Public Beta"; zeroth-robotics README "Public Alpha" | both GitHub pages |
| K-Scale "wound down" Nov 2025 | yaml/md | verified (secondary, consistent) | https://eu.36kr.com/en/p/3657117189890433 : Nov 2025, financing failed, ~$400k left, refunds, tech to be open-sourced |
| BH Lite 0.8 m, 16 kg, 10x6512+12x5010, 6S 4000 mAh ~30 min, BOM $4,312/$3,236, zero-shot PPO, 30% torque, 0.0229 rad backlash | yaml | verified; abstract says "under $5,000" (added) | https://arxiv.org/html/2504.17249 |
| BH Lite leg DOF null, no peak torque | yaml | verified null | same |
| Berkeley Humanoid 0.85 m, 16 kg w/o arms (22 kg with), 62.6/81.1 Nm, $9,955, DJI TB50, 0.051/0.058 m/s, 38 falls/2 damage | yaml | verified | https://arxiv.org/html/2407.21781 |
| OP3 0.51 m, 3.5 kg no skin, 20 DOF, XM430-W350-R, 11.1 V 3300 mAh, NUC i3 | yaml | verified | https://emanual.robotis.com/docs/en/platform/op3/introduction/ |
| G1 1.32 m, 35 kg, 23 DOF, knee 90 (EDU 120), 9000 mAh ~2 h, $13.5k | yaml | verified (90 Nm = strongest joint) | https://www.unitree.com/g1 |
| H1 1.8 m, 47 kg, knee 360, 864 Wh, 3.3 m/s, 5/leg 4/arm | yaml | verified; $90k price secondary, not on vendor page | https://www.unitree.com/h1 |
| R1 1.21 m, 25 kg | yaml | corrected -> 1.23 m, 29 kg (R1 AIR 27 kg, $4,900); $5,900 verified | https://www.unitree.com/R1 |
| Booster T1 1.18 m, 30 kg, 23 DOF (head 2, arm 4 each, waist 1, leg 6 each), knee 130, AGX Orin | yaml | verified (reseller + RoboCup spec sheets); $30k single reseller, Generation Robots from EUR 32,500, T1 reportedly discontinued | https://www.generationrobots.com/blog/en/booster-t1-the-humanoid-development-platform-for-researchers-and-developers/ |
| Asimov 1.2 m, 35 kg, 25 joints (6/5, waist 1, neck 2), 13S4P, Radxa CM5+Pi5 | yaml | verified | https://docs.menlo.ai/asimov/1 |
| Asimov $20,000 | yaml | corrected -> ~$15,000 (secondary) | https://interestingengineering.com/ai-robotics/bipedal-humanoid-robot-kit-asimov ; docs list no price |
| Poppy 0.84 m, ~$11k (2013) | yaml/md | unsupported -> nulled (generationrobots page has neither; fabbaloo 403) | not in any fit |
| AiNex specs | yaml/md | partly filled, retailer-only: 2.45 kg Standard / 2.25 Starter, 24/20 DOF, HX-35H/HX-35HM servos, 11.1 V 3500 mAh, 21 cm/s, 193x135x415 mm (axis unlabeled); height left null | robotshop/openelab listings (via search); hiwonder.com not retrievable |
| Fits (mass vs height) | md | recomputed | N=9, k=18.5, n=2.28, R2=0.93, 0.5 m -> 3.8 kg; without BH N=8 k=18.0 n=2.31 R2=0.93 3.6 kg; n=3: k=18.8, R2=0.84, 2.35 kg; <1 m N=4 n=3.42 R2=0.96 2.8 kg; BH at 22 kg: n=2.25 R2=0.90 4.0 kg. Change vs prior is tiny (R1 correction) |
| Fit (knee torque vs height) | md | recomputed, unchanged | N=5 k=51.1 n=3.73 R2=0.85 -> 3.9 Nm at 0.5 m; n=3 -> 6.7 Nm; without ToddlerBot N=4 n=1.86 R2=0.72 -> ~25 Nm (garbage extrapolation) |

#### New findings
- Real robots near 0.5 m: OP3 3.5 kg at 0.51 m, ToddlerBot 3.4 kg at 0.56 m. Fit at 0.5 m is 3.8 kg (free n) or 2.35 kg (n=3); the real robots favour ~3.5 kg, so the n=3 / ~1.7 kg Adam target is optimistic. Only 2 points sit in the 0.5 m neighbourhood, none between 0.56 and 0.8 m.
- Knee torque fit is driven by the single ToddlerBot point at the small end; 5 points mixing stall and peak; indicative only. ToddlerBot's own estimated need is 2.35 Nm knee at 0.56 m.
- K-Scale closure corroborated by 36kr (Nov 2025, refunds, IP open-sourced) - Zeroth still usable as a design reference.
- Hamburg Bit-Bots Wolfgang (search summary of 2024 RoboCup spec sheet, PDF not parsed): 825 mm, 7.1 kg. Not added to fits.
- BH Lite arxiv abstract cost is "under $5,000"; BOM $4,312.
- ODM reseller kit price is $910, vs $400 BOM target.

#### Remaining unknowns
- Bez / HR-OS: could not identify (only a Toronto UTRA "Bez" RoboSoccer humanoid, no data). Ask the user what was meant.
- Zeroth height, mass, DOF split, definitive servo count (docs sites unreachable).
- ODM v1/v2 mass; later (post Feb 2025) sim2real status; walking speed.
- AiNex official height; official Hiwonder page is JS-rendered.
- Booster T1 official price/mass from booster.tech (site lists T2/K1 only).
- Poppy height/mass/cost; Disney/BD-1 not attempted.
- H1 price only secondary.

---

### Verification: methods a, b, c, DR yaml, SUMMARY items 4-7 (2026-10-19)

All sources opened via WebFetch (raw GitHub/arXiv/API). No commit SHAs available; all against main/master HEAD of 2026-10-19. Line numbers in fetch summaries are approximate.

| claim | file | status | evidence |
|---|---|---|---|
| BAM supports STS3215, Apache-2.0 | a | verified | github.com/Rhoban/bam README: "Feetech STS3215"; `license = {Apache-2.0}` |
| BAM STS3215 m1 params (kt 1.178, R 2.479, arm 0.0261, delay 1.05 ms) | a | verified | bam/params/feetech_sts3215_7_4V/m1.json |
| m4 params (kt 1.265, R 2.472, armature 0.0234, vmax 5.07, delay 4.94 ms, friction_base 0.0519, load 0.208, viscous 0.0338) | a, SUMMARY 5 | verified | m4.json same folder; "model": "m4" |
| m6 params | a | verified | m6.json: kt 1.2753, R 2.7534, delay 0.00498 |
| 'm4' = Stribeck + load-dependent friction | a | verified | arXiv 2410.08650 Sec. III table |
| STS3215 voltage 7.4 V only; vin 7.4, kp 32, error_gain 0.166, max_pwm 0.97 | a | verified | bam/feetech/actuator.py; default vmax 5.22 (file said 5.21, corrected) |
| Experiment supply voltage for identification | a | unsupported -> null | not stated in files read |
| BAM paper error reductions MX-64 2.93x, MX-106 2.02x, eRob80:100 2.34x, :50 1.51x | a | verified (best-model labels for MX inferred) | arXiv html 2410.08650; per-model MAE only in Fig. 5 |
| Param counts 5/3/7/9/11 | a | unverified (M3=3 odd) | flagged in file |
| "backlash not covered" as stated limitation | a | corrected | limitations are temperature, radial forces, dwell time only |
| STS3215 error reduction in paper | a | unsupported (null) | paper does not mention STS3215 |
| Open Duck "kp 17.8, +-3.35, damping 0.60, frictionloss 0.052, armature 0.028" | a, SUMMARY 6 | corrected | values exist in joints_properties.xml but ACTIVE scene (open_duck_mini_v2.xml) uses kp 13.37, +-3.23, 0.56, 0.068, 0.027; backlash xml kp 17.11, same 0.56/0.068/0.027, with 17.8/3.35/0.60/0.052/0.028 commented out |
| Backlash +-0.5 deg joint, damping 0.01, armature 0.01 | a | verified | joints_properties.xml; backlash class |
| Action delay 0-3 steps (0-60 ms) | a, b, yaml, SUMMARY 7 | corrected | `maxval=3` in jax.random.randint is exclusive -> 0-2 steps (<=~40 ms); config says 0-3 |
| Open Duck randomize.py: friction 0.5-1.0, frictionloss 0.9-1.1, armature 1.0-1.05, CoM +-0.05, mass 0.9-1.1, torso +-0.1, qpos0 +-0.03, kp 0.9-1.1 | b, yaml | verified | randomize.py source read in full |
| Open Duck obs noise & push 0.1-1.0 / 5-10 s, cmd ranges 0.15/0.2 | b, c, yaml | verified; linvel noise commented out (added) | joystick.py |
| Open Duck Mini uses BAM | SUMMARY 4 | unsupported | no BAM mention in Playground README or XML; search found no source. Needs SUMMARY edit (not in my write scope) |
| SO-ARM100 blog fit kp ~108 vs stock 998 | SUMMARY 6 | unsupported | not in methods/a at all; search found nothing. Needs SUMMARY edit |
| ToddlerBot DR defaults (friction 0.4-1.0, damping/armature/frictionloss 0.8-1.2, kp/kd/tau 0.9-1.1, passive_active 0.5-1.5, backlash 0.02-0.1, push 1-3 f, 0.2 s/2 s) | b, yaml | verified (lines off by 1) | mjx_config.py DomainRandConfig |
| gin override | b, yaml | partly checked | walk.gin: add_head_pose True, add_push off, no range overrides; 14 other gin files not checked |
| ToddlerBot XC330 Table 3 values, 1.3 deg, ratio 3 (58%), backlash 0.25 deg, Table 7 walk errors | a | verified | arxiv.org/html/2502.00893 |
| Playground Berkeley/G1/T1 DR values and noise/push | b, yaml | verified; T1 "kd" corrected to dof_damping on 4 ankle DOFs | randomize.py/joystick.py each; comments disagree with code for T1 friction and G1 frictionloss |
| Berkeley Humanoid paper Table 6, no PD randomisation, latency negligible 0.5-2 ms | b, yaml | verified | arxiv 2407.21781 |
| Berkeley Humanoid Lite env_cfg values | b, yaml | verified; push magnitude +-1 not verified (removed) | env_cfg.py (friction 0.4-1.2, mass -1..2, stiffness/damping 0.8-1.2, ext force +-2) |
| BHL backlash 0.0229 rad "SD 0.0042" | a | corrected | 0.0229 is maximum observed; SD 0.0042 separate; policy 25 Hz and 30% torque verified |
| K-Scale ZBot DR values | b, yaml | verified; push units and line anchors removed; path is branch `master` | walking.py: friction 0.1-2.0, static 0.5-1.5, damping 0.95-1.05, Top_Brace +-0.5, push force_range 0-0.5 |
| ksim library defaults | b | verified | ksim/randomization.py |
| Kajita ICRA 2003 citation | c | corrected | Kajita, Kanehiro, Kaneko, Fujiwara, Harada, Yokoi, Hirukawa; Taipei 2003; DOI 10.1109/ROBOT.2003.1241826; pages null; IEEE page unfetchable |
| ToddlerBot zmp_walk (constant CoM height, 0.05 step, 0.02 dt, analytic IK) | c | verified; no Kajita cite in file | zmp_walk.py |
| Open Duck reference generator licence "none stated" | c, SUMMARY | verified | no LICENSE in repo root; API licence null; 123 stars, push 2026-02-09 |
| Open Duck Playground "Apache-2.0" | c | corrected | repo has no LICENSE; only per-file Apache headers |
| Playground/brax/MuJoCo Warp/mujoco_mpc/Crocoddyl licences, stars, pushes, MJX claims | c | verified | GitHub API; mujoco_mpc README: Windows untested, research prototype; arXiv 2502.08844 abstract |
| Placo MIT | c | verified | GitHub API |

#### New findings
- BAM ships `waveshare_st3025` (Waveshare ST3025, 12 V, vin=12.0, m1-m6). It is a different servo, not STS3215; m4: kt 1.666, R 3.326, armature 0.00399. No 12 V STS3215 identification exists in BAM.
- Open Duck Playground carries inconsistent servo parameter sets; active ones are kp 13.37/17.11 with +-3.23 N.m.
- Playground T1/G1 source comments disagree with code.
- Search snippets claimed the BAM docs say "only m1 identified" for STS3215; current docs page and repo (m1-m6 JSON) do not show this.

#### Remaining unknowns
- SUMMARY items 4 and 6 need edits (BAM link to Open Duck; SO-ARM100 claim; kp 17.8 not the active value); not in my write scope.
- Index-to-delay mapping for Open Duck action delay; whether Open Duck values derive from BAM.
- Units of BAM kt/friction; actual identification voltage; ZBot servo type; other 14 ToddlerBot gin files; Kajita page numbers.

---

### Verification: print/FEA, power/thermal, Dynamixel, RobStride (2026-10-19)

Status: verified / corrected / unsupported / unreachable. Quotes are table rows from the cited page.

| claim | file | status | evidence |
|---|---|---|---|
| PLA (PolyMax) XY 41.3 / Z 32.4, ratio 0.78 | d, yaml | verified | wiki.polymaker.com polymax-tm-pla: "41.3 ± 2.2", "32.4 ± 1.2" (ISO 527; specimens 230 C, 100% infill) |
| PLA Pro XY 49.8 / Z 36.5, 0.73; Z elong 2.4 | d, yaml | verified | polylite-tm-pla-pro: "49.8 ± 0.4", "36.5 ±0.6", settings 210 C/25 C/4 layers |
| PETG (PolyMax) 37.9 / 29.4, 0.78; Charpy 11.6 / 2.4 | d, yaml | verified | polymax-tm-petg: "37.9 ± 1.4", "29.4 ± 1.0", "2.4 ± 0.6 kJ/m2" |
| ASA 43.8 / 32.0, 0.73; Z elong 1.65 | d, yaml | verified | polymaker-tm-asa: "43.8 ± 0.8", "32 ± 1.8", "1.65 ± 0.2 %" |
| ABS 33.4 / 29.7, ratio 0.89 | d, yaml | corrected (low confidence) | polylite-tm-abs lists tensile twice, both "X-Y" (33.4, 29.7); 29.7 only inferred as Z. Density 1.12 on wiki vs 1.04 at-a-glance; "newer revision" explanation unsupported |
| PA12-CF10 XY 71.6 / Z 43.3, 0.60 | d, yaml | corrected | Product page 403. TDS V1.1 PDF (dry, annealed 100 C/16 h): XY 77.4, Z 52.2 -> 0.67; wet 71.7/42.1 -> 0.59. Ratio 0.59-0.67 depending on state |
| PA12-CF elong XY 3.5 / Z 3.3 | yaml | unsupported -> null | TDS V1.1 says 4.2 / 5.0 (dry), 5.3 / 5.3 (wet) |
| PA12-CF annealing 80 C 6 h vs 100 C 16 h conflict | yaml | verified | TDS V1.1: "100 C/16H" annealing, drying 100 C/10H |
| PA12-CF Charpy 9.9 notched XY | yaml | verified | TDS V1.1 "9.9 ± 0.7 kJ/m2" |
| Prusament PETG vertical 50 vs horizontal 47 | d, yaml | verified | Prusa TDS v1.1 PDF (pdftotext): "47 ± 2 | 50 ± 1", ISO 527-1, MK3, 100% rectilinear, 250 C |
| Prusament PETG notched Charpy 6 / 3, HDT 68 (0.45 and 1.8 MPa), density 1.27, filament 46 | yaml | verified | same PDF: "68 ISO 75" twice, "6 ± 1 | 3 ± 1" |
| Bambu PLA Basic 35 MPa, 12.2 %, 1.24 | yaml | verified (retailer) | filament2print: "35 MPa ISO 527", "12.2%" |
| TPU95 modulus 33.6, elong 551.2, stresses 11.1-25.8 | d, yaml | verified | polyflex-tpu95 wiki: "33.6 ± 0.9", "551.2 ± 23.5%". Legacy V4 sheet (29.0 / 330.1) not re-fetched |
| CSUS thesis X over Z: 25/42/128 % | d, yaml | verified | scholars.csus.edu abstract: 24.63 %, 42 %, 127.9 %, ASTM D638 Type I |
| PLA endurance limit ~10% of UTS | d, yaml, SUMMARY 10 | verified (caveat) | eprints 133457 abstract: "equal to 10% of the material ultimate tensile strength", slope 5.5. Reference curve for when test data are absent; load ratio not given |
| ASA 25 %, PA12 17 % fatigue limit | d, yaml | corrected | Cited eprint 150845 is a PLA paper. Real source: Rodrigues 2026 Polymers 18(2):302: ASA 8 MPa (25%), Nylon 12 7.4 MPa (17%), R=0.05 |
| PETG S-N exists (Martins 2024) | d, yaml | corrected | URL pointed to the ASA paper; PETG paper is PMC11243948 (R=0.2, 45 deg). Fraction null; full text blocked (captcha) |
| Fall arithmetic: v=2.4 m/s; 59 g at 5 mm; 147 g at 2 mm | d | corrected | a/g = h/d: 0.30/0.005 = 60 g; 0.30/0.002 = 150 g (old numbers used rounded v=2.4) |
| Kajita 2016: >100 g life-size humanoid | d | verified (abstract, via search) | "over 100G at the impact"; airbag 20-30 G; Spectrum: HRP-2Kai 82-113 g |
| CNC Kitchen M3 ~120 kgf; Markforged M3 cavity | d | unreachable | embeddedcomputing.com 403; markforged.com 403 |
| Bambu PAHT-CF / PET-CF datasheet | yaml | partial / unreachable | store.bambulab.com 402. Retailer table (filament2print): tensile 92, modulus 3860, elong 8.4, flex 125, Charpy 22.8 (ISO 527/178/179), no XY/Z split. PET-CF null. Added as secondary |
| Pi Zero 2 W idle ~125 mA, tuned 75 mA, 4-core ~624 mA, 1.35 A peak | e | verified (nuance) | CNX: "120 mA at 5 V" (125 with UART+SSH), "74.5 mA", "624 to 635 mA", "1.35 A" under stress-ng+es2gears+iozone+USB drive (not "USB HDD stress") |
| Foundation PSU 2.5 A | e | corrected | Official docs power table: "Zero 2 W | 2A | ... | 350mA" (recommended PSU 2 A, typical active 350 mA); product brief lists 5 V 2.5 A; CNX cites 2.5 A |
| Robotis suggests continuous ~20% of stall | e, SUMMARY 1 | unsupported | robotis.us/robotis-blog/torque-ratings 404 (both URLs); search extract describes a formula but gives no %. Only the forum "<=20%" remains |
| Robotis ~10 A ceiling; U2D2 Power Hub 10 A, 3.5-24 V | e | verified | emanual u2d2_power_hub: "3.5V ~ 24.0V", "10.0A"; 10 A ceiling via search extract of robotis.us powering-dynamixel (page 404 direct) |
| Flite Test 3S 2200 mAh ~20 mOhm | e | corrected | 20 mOhm is a reader comment, not article text |
| XL430 spec: 57.2 g, 258.5:1, 1.0/1.4/1.5 N.m @ 9/11.1/12 V with 1.0/1.3/1.4 A, 47/57/61 rpm, 6.5-12 V, -5..72 C | xl430 | verified | emanual xl430-w250 spec table, exact |
| XL430 gear material, standby | xl430 | filled | "Engineering plastic"; standby 52 mA |
| XL430 control defaults (72 C, PWM 885, voltage limits 140/60) | xl430 | verified | table; manual itself inconsistent on min voltage (60 vs 6.5 V description) |
| XM430-W350 3.8/4.1/4.8 N.m at 11.1/12/14.8 V, 2.1/2.3/2.7 A; 43/46/57 rpm; 353.5; 82 g; 15 arcmin; 10-14.8 V; -5..80 C; 40 mA | xm430 | verified | emanual xm430-w350 |
| XM430-W210 2.7/3.0/3.7 N.m, 2.1/2.3/2.7 A, 70/77/95 rpm, 212.6 | xm430 | verified | emanual xm430-w210 |
| XM430 defaults: temp 80, current limit 1193 (2.69 mA/unit = 3.21 A), P 800 | xm430 | verified | w350 control table |
| No continuous torque figure in manuals | xl430, xm430 | verified | XM430: stall "is different from it's continuous output rating"; XL430: real-world "closer to the performance graph" |
| ToddlerBot XM430-W210 tau_max 1.61 N.m (qdot_max 7.63, brake 3.70, damping 0.0056, armature 0.0022, friction 0.025) | xm430 measured | verified | arxiv 2502.00893 Table 3 row. Test voltage not stated (only Table 2 footnote: vendor stall "at 12 V"). 1.61/3.0 = 54%. 2XL430 0.94 and XC430 1.32 rows also verified |
| RS02: 6/17 N.m, 48 V (24-60), 410/360 rpm, 7/23 A pk, 0.5 A, Kt 1.22, 0.58 ohm, 7.75:1, 405 g, 78.5x78.5x45.5, $145 | robstride-02 | verified (retailer) | aifitlab table; pakronics: 6/17, 170 W, 7.75, 405 g |
| RS02 IP67 variant 490 g | robstride-02 | unsupported -> null | not on pakronics or aifitlab |
| RS03: 20/60 N.m, 15-60 V, 195/180 rpm, 12/43 A pk, Kt 2.36, 0.39 ohm, 0.275 mH, 9:1, 880 g, $225, 380 W, IP52 | robstride-03 | verified (retailer) | aifitlab + pakronics; no-load 0.6 A added |
| RS04: 40/120 N.m, 15-60 V, 200/167 rpm, 27/90 A pk, Kt 2.1, 0.16 ohm, 0.211 mH, 9:1, 1420 g, $255 | robstride-04 | verified (retailer) | aifitlab; 700 W/IP52 and 1.5 kg conflict not re-fetched |
| RobStride official spec | all | unreachable | robstride.com returns only the title; every number is retailer-reproduced |

#### New findings
- Fiberon TDS V1.1 (PDF read with pdftotext) gives PA12-CF10 dry/annealed Z/XY = 0.67 and wet 0.59; Z elongation exceeds XY there (5.0 vs 4.2), contradicting the "Z brittle" framing for CF-nylon.
- Prusament PETG vertical tensile and modulus exceed horizontal; only notched Charpy halves (6 -> 3).
- Stall-torque ratios for RobStride are rated/peak 1:3 on all three.
- Bambu PAHT-CF has one retailer-quoted tensile (92 vs 88 MPa conflict) with no orientation.
- The TPU95 wiki page contained embedded "agent instructions" text addressed to the fetcher. It was ignored and has no bearing on the data.
- SUMMARY item 1 ("Robotis rates ~20%") rests on the unconfirmed 20% figure; owner of item 1 should soften.

#### Remaining unknowns
- Official Bambu PAHT-CF / PET-CF TDS with XY/Z; Martins 2024 PETG fatigue fraction; Prusament PETG 2023 TDS (image-only PDF).
- CNC Kitchen insert strengths, Markforged cavity dimensions (403).
- Robotis 20% rule; STS3215 RobotShop numbers (403); 70 C Dynamixel default claim; Niryo/ZHAW overheating report; Poppy forum claim.
- RobStride official manuals; openelab RS03 21 N.m / 900 g conflict; RS04 700 W.
- ABS Z-direction tensile (needs unambiguous vendor row).
