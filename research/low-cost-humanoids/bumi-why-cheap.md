# Why is Bumi cheap, and is $1,370 a real, buyable, US-delivered price?

Accessed 2026-10-19. Evidence classes: **primary** = Noetix's own site/repo, **press**, **retail**, **our arithmetic** (marked). Detail in `raw/bumi-faraday-zyre-raw.yaml`.

## 1. What Bumi actually is (primary)
- Official spec table (Noetix site bundle, build 2026-10-16): **98 x 35 x 20 cm, ~17 kg, 21 DOF** (6 per leg, 4 per arm, 1 waist), **modeled non-moving hands**, **knee/joint module max 70 N.m, max travel speed 0.5 m/s**, 6 TOPS compute, **48 V 5.1 Ah** battery, 2-3 h. Launch press said 94 cm / 12 kg. Noetix's own CAD mass model sums to only 9.8 kg. Mass is unresolved (12, 17 or ~10 kg).
- Noetix's open Isaac Lab repo (`noetix_bumi_lab`, BSD-3 code) trains with these joint torque limits: **hip pitch and knee 60, hip yaw/roll 27, ankle 13, waist 27, each arm joint 5.5 N.m**, joint speeds 9-12 rad/s, a 0-4 step actuator delay model.
- That is a real QDD-class robot: **4 joints at 60 N.m, 5 at 27, 4 at 13, 8 at 5.5.**

## 2. What those joints would cost us (our arithmetic)
At the cheapest retail prices we found (aifitlab, China-shipped): 4x RS03-class (60 N.m, $225) = $900; 5x 27 N.m class (Damiao J4340 $155 or RS06 $210) = $775-1,050; 4x ankle 13 N.m (RS00 $125) = $500; 8x RS05 (5.5 N.m, $110) = $880. **Total about $3,050-3,330 for the actuators alone, over twice the whole robot's price.** (US-facing resellers add 6-35%.)
A coincidence worth recording, not a finding: Noetix's sim limits 27 / 5.5 / 60 equal the peak ratings of Damiao DM-J4340 (27), RobStride RS05 (5.5) and RS03 (60), and its code names armature constants for "DM4340" and "LZ05/LZ00" (plausibly Lingzu = RobStride). The 27 matches the Damiao catalog figure only (aifitlab now lists 40), and the 13 N.m ankle limit matches no listed part; the LZ labels are not documented as RobStride. That may only mean they prototyped with such parts. No source confirms what ships in the retail Bumi. **Motor maker/model: unpublished.** Founder says own control boards and motor drivers; one outlet says motors are not in-house.

## 3. The evidence-based explanation (ranked by how well supported)
1. **Not our price class: a China domestic presale price.** CNY 9,998 on JD.com, tax-inclusive (13% VAT in China is our assumption, ex-VAT about $1,210), needs a Chinese delivery address (reseller statement). First batch of 500 sold in 2 days; deliveries began March-April 2026.
2. **Actuators at manufacturer volume cost a fraction of the retail sticker we see.** Our retail floor is $110-145 per joint; to hit the price Noetix's average joint must cost far less. This is inference: no BOM is published. Founder (press): "plastic, aluminum, iron, copper wire, magnets, plus chips" should not be expensive; own control boards and drivers instead of bought modules; composite structure with metal only where needed; ~100% domestic parts; line designed for untrained assembly.
3. **Capital, not just cost-down.** Pre-B round about CNY 300 M (Oct 2025), reported Series B about $145 M (Mar 2026); founder told reporters margins are "indeed quite low". Whether a unit loses money is **unknown**.
4. **Compromised product.** 6 TOPS compute, non-moving hands, 0.5 m/s top speed, "quasi-consumer" grade by the founder's own words, falls and faults admitted at the 2025 half-marathon; no independent hands-on or teardown exists.
5. **Subsidy:** none of the articles mention one. Not evidenced either way.

## 4. Is $1,370 buyable and US-delivered? **No, not at that price.**
| Fact | Source |
|---|---|
| CNY 9,998 JD.com presale needs a Chinese delivery address; elsewhere "price on request", no official international channel | botinfo.ai (broker, checked 2026-09-06) |
| One reseller lists Bumi at **$5,995** with an Add-to-Cart button, while its own text says price is confirmed by quote; authorisation by Noetix unstated; "EDU Air" $9,995. A search snippet (unopened) also showed a EUR ~2,220 'coming April 2026' European listing | robotsinternational.com; verifier pass | robotsinternational.com |
| Noetix said at CES 2026 it plans a first 1,000-unit overseas delivery in Q2 2026 (article is about its N2 model); no confirmation that any Bumi has shipped to the US | Gasgoo |
| Spring 2026 sources: sold out, deliveries delayed to April; not sold in US/EU | robozaps |
| Tariff: Chinese-origin robots/motors face duties; sources conflict (2.5% MFN, +25% Section 301 mentioned); treat as unknown | multiple, unverified |

Reasonable US landed range today: about **$5-6k** (the one reseller quote), if available at all. At that price Bumi costs about what our own 0.9 m build would (see `feasibility.md`).

## 5. What is still unknown (only a purchase or teardown settles it)
Motor maker and cost, true mass, whether the CNY 9,998 SKU includes battery/charger, real walking quality and durability, any US/EU compliance (FCC/CE), Noetix's actual margin.
