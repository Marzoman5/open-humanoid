# Low-cost humanoids compared (accessed 2026-10-19)

Source of truth: `humanoids.yaml` (per-field basis and URLs) and `raw/*.yaml` (full notes). **Vendor** = manufacturer claim, **press** = news repeating company claims, **retail** = reseller. Null means not found. Nobody here bought, signed in, or watched a robot walk; "walking evidence" is only what is public.

## The three links the maintainer sent

| Link | What it is | Finding |
|---|---|---|
| interestingengineering.com (Bumi) | Press, 2025-10-23 | Repeats launch claims: CNY 9,998 (~$1,370), 94 cm, 12 kg, preorders in China. No DOF or actuators. Real robot, but this is a **China presale price**. |
| techrepublic.com (FF Nova) | HTTP 403, not read; facts taken from four other outlets | FF Nova is **0.50 m, 2.8 kg, 20 DOF, $2,490**, walks 0.1 m/s (company claim), 100 invitation-only units. It is smaller and dearer than Adam, not a "3 ft cheap humanoid". |
| zyrestore.com | Shopify dropship page | **Not credible.** $44.99 "RC smart robot", no height/mass/servo/battery data, "Sold out" next to Add-to-cart, tracking link to another domain, spec text that echoes the NAO research robot. Treat as a toy. |

## Table (sorted by build/sale price; robots under about $7k)

| Robot | Height / mass | DOF | Actuators (in-house?) | Price (basis) | Where / how sold | Walking evidence | Open? |
|---|---|---|---|---|---|---|---|
| Zyre "smart robot" | null | "25 joints" | null | $44.99 (retail) | Shopify store | none | no |
| FF Nova | 0.50 m / 2.8 kg | 20 | null | $2,490 + $390 pkg (vendor) | FF.com/Amazon, 100 invite-only units, 20 in stock | 0.1 m/s, claim | ROS 2, SDK (claimed) |
| Hiwonder AiNex | 0.42 m / 2.45 kg | 24 | 3.4 N.m bus servos | ~$1,046 (retail) | RobotShop etc. | vendor claim | ROS2/Python |
| **Noetix Bumi** | **0.98 m / ~17 kg** (press 0.94 / 12) | **21** | joint modules, 70 N.m max knee; maker unpublished | **CNY 9,998 (~$1,370)** China; **$5,995** at one US reseller (press / retail) | China JD.com; deliveries from ~Mar-Apr 2026; overseas on quote | demo video, Gala, Isaac Lab AMP task published; 0.5 m/s max | SDK + sim repo BSD-3; hardware closed |
| Swancor Qiyuan Q1 | 0.88 m / 15 kg | null | null | CNY 19,999 (press) | China, shipping from 2026-10-01 | news only | null |
| Berkeley Humanoid Lite | 0.8 m / 16 kg | 22 | printed cycloidal + drone BLDC, DIY | **$4,312 BOM** (paper) | DIY | 1 zero-shot walk, no speed data | MIT code, CC BY-SA assets |
| Unitree R1 AIR | 1.23 m / 27 kg | 20 | in-house PMSM | $4,900 excl. tax+shipping (vendor) | Unitree store, AliExpress (~$6.8k) | demos only | dev access on EDU only |
| EngineAI SA01 | null / 40 kg | 12 (legs) | null | ~$5,250 (2024) | China | none found | null |
| Unitree R1 | 1.23 m / 29 kg | 26 | in-house | $5,900 excl. tax+shipping; ~$8.1k AliExpress | same | demos, 1 qualitative review | EDU only |
| Booster K1 Geek | 0.95 m / 19.5 kg | 22 | 60 N.m peak, maker null | "from $5,999" (retail, unverified) | booster.tech + resellers | partial: RoboCup team says real walk barely supported | Apache-2.0 SDK |
| ToddlerBot 2.0 | 0.56 m / 3.4 kg | 30 | Dynamixel | <$6,000 (paper) | DIY | zero-shot walk (paper) | MIT |
| AGILOped | 1.10 m / 14.5 kg | 10 (legs) | MyActuator X6-40 40 N.m, $545 each | $6,380 (paper) | DIY | real, grass | files, licence unnamed |
| HighTorque Mini Pi+ | 0.68 m / 14.8 kg | 22 | closed | $6,750 (vendor) | direct | null | SDK |
| Roboto Origin | ~1.25 m / ~34 kg | 23 | Damiao 4340P x14 + 10010L x9 | own BOM ~$7,000 | DIY (Taobao BOM) | README GIFs only | CERN-OHL-W / GPL-3 |
| K-Scale K-Bot | ~1.4 m / ~34 kg | ~20 | RobStride (secondary) | $8,999 pre-sale | **company closed Nov 2025** | repo videos | MIT code, CERN-OHL-S hw |
| Berkeley Humanoid | 0.85 m / 16 kg | 12 (legs) | in-house planetary $422-676 each | $9,955 | research | **strongest**: grass, stairs, 364 m | no licence in paper |
| Asimov 1 | 1.2 m / 35 kg | 25 | undisclosed | $20,000 kit | Menlo | policy "upcoming" | CERN-OHL-S, GPL-2 |
| Duke Humanoid | 1.0 m / 30 kg | 10 | Motorevo planetary | null | research | 0.3 m/s tethered | released |

Over the range or not buyable: Unitree G1 $13.5k, H2 $29.9k, Booster T1/T2 ~$30k+, Fourier GR-3 and EngineAI PM01 (tens of thousands), AgiBot Q1 (no price), UBTech (toy-scale Yanshee only), Xiaomi (nothing on sale). K-Scale Z-Bot ($999 announced) never shipped.

## What this table says

1. **Only Bumi is both about 1 m and listed under $2k, and only in China.** Everything else at 0.8-1.25 m that you can actually obtain costs $4.3k (BHL BOM) to $7k (Roboto Origin BOM).
2. **Open builds at 0.8-1.25 m land at $4.3-7k** whether they use printed drone-motor actuators (BHL), Damiao (Roboto Origin), or MyActuator (AGILOped). That is a second, independent cross-check on `feasibility.md`.
3. **Sub-$1k "humanoids" (AiNex, Nova Mini, Z-Bot, Zyre) are 0.4-0.5 m servo toys,** the same class as Adam.
4. **Walking claims are mostly marketing.** Only the Berkeley Humanoid (legs-only) has serious third-party-style evidence; the Booster K1's own RoboCup users call real walking immature.
5. **Prices hide shipping and customs.** Unitree R1's $4,900/$5,900 exclude tax, shipping ($300-1,200) and customs; its AliExpress price is $6.8-8.1k.

## Limits
Search summaries came from a summarising fetcher, so every decision-relevant number was sent to a second pass (see `VERIFICATION.md`). Booster's store, unitree.com/h2 and techrepublic.com were unreachable. JD.com listings were not reachable, so the current Bumi price is not confirmed first-hand.
