# Adam live quotes and delivered totals (T-0002, checked 2026-10-19)

Read-only research: nothing was bought, carted or signed in to. Ship-to: contiguous US, ZIP unknown. Answers challenge-2 row 14.
Numbers in this file come from `catalog/**.yaml` (prices, vendors[], notes) and `variants/adam/sourcing/totals.py` (run it to regenerate the totals).

## 0. Bottom line

1. **No candidate fits the $550 cap at verified prices.** Cheapest-credible delivered totals with 10% contingency: A $1064, B $1079, C $1405, D $1064 (duck-like reference E $752). Fast-US: A $1300, B $1188, C $1613, D $1300, E $821.
2. **Even the floor misses.** Stripping the gamepad, spares, sales tax, shipping and contingency, and taking the cheapest in-stock prices: A $742, B $755, C $977, D $742, E $499. A would still be $583 with WowRobo's $13.99 servos, which are sold out and unconfirmed. Only the 14-DOF duck-like reference gets under $550, and only as a bare sticker price (E floor $499). With tax, shipping and 10% contingency but no spares and no gamepad it is $656.
3. **The servos are 55-70% of the problem.** 23 x $20.90 = $481 (Seeed, 10+ tier) before spares. The previous catalog assumed $16 each. The rest of the old BOM drifted up too: Pi 5 $60 -> $110, STS3250 $32 -> $74, BNO085 $15 -> $29.50, camera $25 -> $29.25, LiPo 1300 mAh $20 -> $27.
4. **Maintainer question 3 in challenge-2 is now live:** with servos near $21, a 23-DOF robot is roughly $1000 delivered. Something has to give (DOF, the cap, or the "all-in" definition).
5. **Pi Zero 2 W is out of stock at every US vendor read.** A, B, D and E all depend on it.

Limits of this pass (research-evidence skill): WebFetch is a summarizer. Amazon, Micro Center, HobbyKing, GetFPV, Mouser, McMaster, AliExpress, Alibaba, eBay item pages and the Elegoo/Sunlu stores were unreachable (403/404/empty). Shipping cost and ETA were readable at only a handful of vendors; where not, the cell says "not visible". Prices from search snippets are labelled "snippet". Nothing was cart-tested, so "in stock" means what the page said.

## 1. Delivered totals per concept candidate

Candidate part lists come from `variants/adam/concepts/*.yaml` and `variants/adam/generated/concept/*/report.json` (cost rows and structure kg: 0.758 kg PLA+ for A-D, 0.616 kg for E). Added to every candidate (the challenge's missing lines): 65 W USB-C PD supply for the charger, 20 A inline fuse, gamepad, spare servos, shipping, US sales tax. Camera candidates also get the 22-to-15-pin camera cable. B and E use the Pololu D24V22F5 regulator because the DFR0831 needs 7 V in and a 2S pack sags to about 6 V.

- **FAST** = fastest US-stocked or duty-included source (servos from OpenELAB).
- **CHEAP** = cheapest source with a visible, in-stock price (servos from Seeed at the 10+ tier). Sold-out prices are excluded.
- Tax 7.53% (population-weighted US average, Tax Foundation, 1 Jul 2026, https://taxfoundation.org/data/all/state/2026-sales-tax-rates-midyear/). It is 0 in OR/NH/MT/DE/AK.
- Shipping is an ESTIMATE (FAST $45 and CHEAP $60: about five small orders at $9, plus $15 for the Seeed servo order). Only OpenELAB's rates were read: free over $55.
- "Fits" tests the contingency-inclusive total against $550.

| Candidate | Scenario | Parts | of which ESTIMATE lines | Spares | Tax | Ship (est) | Delivered | **+10% contingency** | Fits $550? | Without spares and gamepad (+10%) | Tariff exposure if servos are not DDP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A 3S/12V STS3215 | FAST | $974 | $170 | $84 | $80 | $45 | $1182 | **$1300** | NO | $1155 | $0 (OpenELAB is DDP) |
| A 3S/12V STS3215 | CHEAP | $781 | $153 | $63 | $64 | $60 | $967 | **$1064** | NO | $944 | +$206 (worst $1290) |
| B 2S/7.4V STS3215 | FAST | $891 | $186 | $72 | $72 | $45 | $1080 | **$1188** | NO | $1057 | $0 |
| B 2S/7.4V STS3215 | CHEAP | $793 | $169 | $63 | $64 | $60 | $981 | **$1079** | NO | $959 | +$207 (worst $1306) |
| C 3S + 2x STS3250 + Pi 5 | FAST | $1192 | $170 | $130 | $100 | $45 | $1467 | **$1613** | NO | $1414 | $0 |
| C 3S + 2x STS3250 + Pi 5 | CHEAP | $1016 | $153 | $116 | $85 | $60 | $1277 | **$1405** | NO | $1222 | +$182 (worst $1605) |
| D 3S/12V + transmissions | FAST | $974 | $170 | $84 | $80 | $45 | $1182 | **$1300** | NO | $1155 | $0 |
| D 3S/12V + transmissions | CHEAP | $781 | $153 | $63 | $64 | $60 | $967 | **$1064** | NO | $944 | +$206 (worst $1290) |
| E duck-like 14 DOF (reference, not a candidate) | FAST | $604 | $145 | $48 | $49 | $45 | $747 | **$821** | NO | $719 | $0 |
| E duck-like 14 DOF (reference) | CHEAP | $538 | $131 | $42 | $44 | $60 | $683 | **$752** | NO | $656 | +$128 (worst $892) |

D equals A because the concept files give the same parts; D's transmissions (pushrods, 4-bars) are printed structure and are not priced here.

Floor sticker (cheapest in-stock prices, no gamepad, no spares, no tax, no shipping, no contingency):

| Candidate | Floor | With WowRobo $13.99 servos (sold out, unconfirmed) |
|---|---|---|
| A | $742 | $583 |
| B | $755 | $594 |
| C | $977 | $832 |
| D | $742 | $583 |
| E | $499 | $401 |

Tariff note. A tariff is already inside the price for US-warehouse stock and for OpenELAB (it states "Duties & Customs Fees Included"). For Seeed, Waveshare and any China-direct order I could not establish whether duty is included. Secondary sources (tariffstool.com, updated 2026-10-09; tarifftax.org, 2026-04-17) say the IEEPA tariffs were struck down on 2026-02-20 and that Chinese electronics now face about 25% legacy Section 301 plus a 12.5% replacement tier, about 37.5%, with no de minimis exemption. I did not confirm this against CBP or the Federal Register. The last column applies 37.5% to servos and the Waveshare adapter in CHEAP, as a worst case.

Previous baseline for reference: `oh bom adam` (17 x STS3215-12V at the old $16) printed $419.32 typical; with the new catalog it prints $526.10 typical (range $361-$745), 10/13 lines still unverified. `oh size adam` still returns FEASIBLE at 0.53 m with the same 17 servos and cost now $526 (was $419), and its "what stops it being taller" line moved from "over budget: $661 > $550" to "$1356 > $550". The baseline spec stays under the cap only because it carries 17 servos and none of the adders in section 4. The regenerated `variants/adam/generated/*` files were NOT committed (outside this task's paths).

## 2. Servos

Verified live pages: Seeed (both), OpenELAB (12 V and 7.4 V, fetched twice), WowRobo 12 V. Others are from the sourcing sub-agent's reads and snippets.

### 2a. STS3215 12 V (30 kg.cm @12 V, 1:345)

| Vendor | SKU as listed | Qty 1 | Qty 10 | Qty 25 | Shipping, ETA | Ships from, stock, duty | Link |
|---|---|---|---|---|---|---|---|
| **Seeed Studio** | 108090003, "ST3215-C047 12V 30Kg" | $22.00 | $20.90 | **$20.90** ($522.50 for 25) | not visible. Late-2025 promo post: US warehouse USPS Priority 3-5 d, Ground 6-9 d | US, China or Germany warehouse (default not visible). "In stock". Duty not stated. 2 horns + 18 screws in the box per the C047 datasheet | https://www.seeedstudio.com/STS3215-30KG-Serial-Servo-p-6340.html |
| **OpenELAB** | Feetech-STS3215-C018 | $27.99 | $27.99 | **$27.99** ($699.75) | Free over $55. US warehouse: USPS Ground 3-7 bd, Priority $13.99-15.99, 1-4 bd. China: YunExpress 8-15 bd | US (Somerset NJ) or Shenzhen "depending on stock". Add-to-cart shown, SKU-level US stock not confirmed, backorder 10-20 d. **Duty included (DDP)**. Bulk by RFQ form only | https://openelab.com/products/feetech-sts3215-c018-servo-12v |
| Waveshare | 22414, "ST3215 30kg.cm@12V" | $21.99 | $20.63 | $20.63 (tiers 21.19/20.79/20.63 seen, thresholds unlabelled) | not visible (shipping page 404) | assumed Shenzhen, stock not shown | https://www.waveshare.com/st3215-servo.htm?sku=22414 |
| DigiKey (DFRobot) | SER0070 | $24.88 | n/a | n/a | not visible | 0 in stock, 1 expected 2026-11-09 | https://www.digikey.com/en/products/detail/dfrobot/SER0070/28531107 |
| RobotShop | RB-Fit-155 | $31.71 (fetch) or $49.22 "includes tariffs" (snippets) | n/a | n/a | not visible | backorder | https://robotshop.com/products/feetech-12v-30kgcm-magnetic-encoding-servo-sts3215 |
| WowRobo | C018 12V 30KG | $15.99 | $13.99 | $13.99 | calculated at checkout | **SOLD OUT** on the product page | https://shop.wowrobo.com/products/feetech-sts3215-servo-12v-30kg-high-torque-servo-for-so-arm100 |
| AIFitLab | ST-3215-C018 | $26.00 | n/a | n/a | dynamic | China, backordered | https://aifitlab.com/products/feetech-sts3215-servo-motor |
| Amazon (B0FMY17QRT, B0FMXVR77Y 2-pack, B0GXTHX4HF 6-pack) | listing titles say "STS3215" / "30KG" | not visible | | | | pages unreadable; the 6-pack snippet names a LewanSoul HX-30HM clone, so check the brand | https://www.amazon.com/dp/B0FMY17QRT |

### 2b. STS3215 7.4 V (19.5 kg.cm @7.4 V, 1:345, "C001")

| Vendor | SKU | Qty 1 | Qty 10 | Qty 25 | Shipping, ETA | Ships from, stock, duty | Link |
|---|---|---|---|---|---|---|---|
| **Seeed Studio** | 108090023, "ST3215 C001 Servo 7.4V" | $21.99 | $20.99 | **$20.99** ($524.75) | not visible | US or China warehouse, "In stock", duty not stated | https://www.seeedstudio.com/STS3215-19kg-cm-7-4V-Serial-Servo-p-6338.html |
| **OpenELAB** | Feetech-STS3215-C001 | $23.99 | $23.99 | **$23.99** ($599.75) | free over $55; YunExpress 8-15 bd (page also quotes USPS 3-7 d) | warehouse label says China, pre-order notice 10-20 working days. DDP | https://openelab.com/products/feetech-sts3215-c001-servo-7 |
| Waveshare | 33014 "ST3215-7.4V 19.5kg.cm@7.4V" | $16.99 | $16.31 | $16.31 (tiers unlabelled) | not visible | assumed Shenzhen; the page's torque selector text was inconsistent, confirm the cart line says 7.4 V | https://www.waveshare.com/st3215-servo.htm?sku=33014 |
| RobotShop | RB-Fit-111 | $34.32 | n/a | n/a | not visible | out of stock (fetch) | https://www.robotshop.com/products/magnetic-encoding-servo-sts3215-74v-19kgcm |
| WowRobo | C001 7.4V | $15.99 | $13.99 | $13.99 | at checkout | SOLD OUT | https://shop.wowrobo.com/products/feetech-sts3215-c001-servo-7-4v-19-5kg-high-torque-servo-for-so-arm100-101 |

C044 (1:191) and C046 (1:147) are different parts at about $20-24 (Seeed, OpenELAB). Do not buy those for this project.

### 2c. STS3250 12 V (50 kg.cm)

| Vendor | SKU | Qty 1 | Qty 2 / 23 | Notes | Link |
|---|---|---|---|---|---|
| OpenELAB | Feetech-STS3250-C002 | $73.99 | $147.98 / $1701.77 (no tiers) | free over $55, YunExpress 8-15 bd, DDP, pre-order 10-20 working days | https://openelab.com/products/feetech-sts3250-c002-servo-12v |
| AIFitLab | ST-3250-C001/C002 | $97.00 ("from $88") | none | C001 backordered | https://aifitlab.com/products/feetech-sts3250-servo-motor |
| rcdrone.top | ST-3250-C001 | $125.00 | none | sold out | https://rcdrone.top/ja/products/feetech-sts3250-servo-motor |
| WowRobo | STS3250 C002 | $43.00 | n/a | SOLD OUT | https://shop.wowrobo.com/products/feetech-sts3250-c002-servo-12v-50kg-1-345-servo |

The old catalog price was $32. Not found at Seeed, RobotShop, Waveshare, DigiKey or Mouser.

### 2d. Shortlists

| | 12 V STS3215 at qty 25 | 7.4 V STS3215 at qty 25 | Why |
|---|---|---|---|
| **Cheapest credible** | Seeed **$20.90** each = $522.50 | Seeed **$20.99** each = $524.75 | Only vendor with a printed 10+ tier, in stock, page read twice. Duty and shipping cost not visible: budget the 37.5% exposure until a cart shows otherwise |
| Cheaper on paper, not credible yet | WowRobo $13.99 (sold out), Waveshare $20.63 (tier thresholds unlabelled, China ship) | WowRobo $13.99 (sold out), Waveshare $16.31 | Re-check before dismissing. Waveshare 7.4 V at $16.31 x 25 = $408 would save $117 if the tier is real |
| **Fastest** | OpenELAB **$27.99** each = $699.75, duty included, US warehouse USPS 3-7 bd (1-4 bd Priority) if the SKU is stocked there | OpenELAB **$23.99** = $599.75, but its page labels this SKU's warehouse as China (8-15 bd) | OpenELAB is the only vendor that publishes US-warehouse rates and includes duty. Seeed also lists a US warehouse at lower prices, but no rates |

At 7.4 V the saving over 12 V is only $0 (Seeed) to $4 (OpenELAB) per servo, so the 2S route does not buy a meaningful price advantage at these prices. B's remaining savings are the pack and regulator, and it needs the pricier D24V22F5.

### 2e. Datasheet check

Sources: Feetech wiki spec table https://ftservo.github.io/ftservo-wiki/products/datasheets/st/ , https://www.feetechrc.com/en/2020-05-13_56655.html , Waveshare wiki https://www.waveshare.com/wiki/ST3215_Servo , OpenELAB and Seeed listings. A Feetech-hosted PDF datasheet was not reachable.

| Item | STS3215 12 V | STS3215 7.4 V | STS3250 12 V |
|---|---|---|---|
| Stall torque | 30 kg.cm @12 V (2.942 N.m) ok | 19.5 kg.cm @7.4 V (1.912 N.m) ok; 16.5 @6 V | 50 kg.cm @12 V (4.903 N.m) ok |
| Rated torque | 10 kg.cm @12 V | 5 kg.cm @7.4 V | 16 kg.cm @12 V |
| No-load speed | 0.222 s/60 deg = 45 rpm = 4.71 rad/s ok | 0.192 s/60 deg = 52 rpm = **5.445 rad/s (catalog had 4.72, corrected)** | 0.133 s/60 deg = 75 rpm = **7.854 rad/s (catalog had 6.98, corrected)** |
| Stall current | 2.7 A | 2.5 A | 4.2 A |
| Voltage | 9-12.6 (Feetech wiki), 6-12.6 (Waveshare), 4-14 (OpenELAB, Seeed): disputed, catalog keeps 9-12.6 | 4-7.4 or 6-7.4 listed. Catalog's 8.4 V upper bound (full 2S charge) is above every listed rating | 6-12 (OpenELAB) |
| Mass | 55 g ok (Waveshare's 89/70 g is unreliable) | 55 g | **74.5 g (catalog had 72 g, corrected)** |
| Size, ratio | 45.2 x 24.7 x 35 mm, 1:345 | same | 45.22 x 24.72 x 35, 1:345 |
| Price | catalog $16 -> **$20.90** | $14 -> **$20.99** | $32 -> **$73.99** |

Red flags: listings call 30 kg.cm "rated" (Waveshare) or write "19kg" for the 19.5 kg.cm part. The 12 V's real rated torque is 10 kg.cm; 30 is locked-rotor. Case and gear materials contradict across listings. WowRobo and Waveshare sit 30-40% under peers (WowRobo is sold out); no counterfeit evidence was found, only the price gap. Seeed's C047 and OpenELAB's C018 are listed with identical specs but nobody states they are identical parts. Verify the model register on arrival. The Amazon 6-pack snippet shows a LewanSoul HX-30HM clone under an STS3215 title.

Not found anywhere: a vendor selling idler bearings or back-shaft supports with the servo, and any horn-and-bearing bundle. Only Seeed's C047 states horns in the box (2 horns, 18 screws, 1 JST wire per servo, from the C047 datasheet https://store.comet.bg/download-file.php?id=31780). Pololu sells a 25T aluminium horn (#3433) with no STS3215 fit claim.

## 3. Everything else

All prices are unit prices, checked 2026-10-19. "snippet" = read from a search result, page not fetched.

| Part (catalog id) | Vendor | SKU | Price | Shipping, ETA | Stock, ship-from | Link |
|---|---|---|---|---|---|---|
| Pi Zero 2 W (`rpi-zero-2w`) | PiShop.us | 1799 / SC1146 | $17.25 (limit 1) | not visible | no Add to Cart; "ships fast from USA" | https://www.pishop.us/product/raspberry-pi-zero-2-w/ |
| | CanaKit | board only | $16.35 | not visible | SOLD OUT | https://www.canakit.com/raspberry-pi-zero-2-w.html |
| | Vilros | RPZW2 | $17.43 | free in USA, ETA not visible | SOLD OUT | https://vilros.com/products/raspberry-pi-zero-2-w |
| | Adafruit | 5291 | $19.05 | UPS/USPS 2-8 d, cost not visible | out of stock | https://www.adafruit.com/product/5291 |
| | SparkFun | DEV-18713 | $19.00 (limit 1) | not visible | out of stock | https://www.sparkfun.com/raspberry-pi-zero-2-w.html |
| | Digi-Key | SC0721 | $18.00 | not visible | 0; 420 expected 2027-06-07 | https://www.digikey.com/en/products/detail/raspberry-pi/SC0721/24627135 |
| Pi 5 4 GB (`rpi-5-4gb`) | PiShop.us | 4GB-9024 | **$110.00** (max 10) | not visible | **IN STOCK** | https://www.pishop.us/product/raspberry-pi-5-4gb/ |
| | Adafruit | 5812 | $130.00 (max 2) | "ships today" | in stock, Brooklyn NY | https://www.adafruit.com/product/5812 |
| | SparkFun | DEV-23550 | $110.00 | not visible | out of stock | https://www.sparkfun.com/raspberry-pi-5-4gb.html |
| microSD 32 GB (`microsd-32gb`) | CDW (snippet) | SanDisk Ultra | $9.97 | not visible | 759 | https://cdwg.com/product/sandisk-ultra-flash-memory-card-32-gb-microsdhc-uhs-i/6400259 |
| | PiShop.us (snippet) | SanDisk Ultra / official A2 | $14.95 / $19.95 | not visible | not visible | https://www.pishop.us/product/raspberry-pi-sd-card-32gb/ |
| Bus adapter (`waveshare-bus-servo-adapter`) | Waveshare | 25514 | **$4.99** (catalog $8) | not visible | Add to Cart shown | https://www.waveshare.com/bus-servo-adapter-a.htm |
| | eBay (snippet) | same board | $11.30 | not visible | China | https://www.ebay.com/itm/266416385826 |
| | Sunsky (snippet) | 25514 | $4.30 | not confirmed | n/a | https://www.sunsky-online.com/p/TBD06006922/Waveshare-25514-Serial-Bus-Servo-Driver-Board-for-ST-SC-Series-Serial-Bus-Servos.htm |
| BNO085 (`imu-bno085`) | Adafruit | 4754 | **$29.50** (catalog $15; $26.55 at 10+) | UPS Ground/USPS 2-8 d, cost not visible | in stock, ships today, Brooklyn NY | https://www.adafruit.com/product/4754 |
| | SparkFun (BNO086, a likely drop-in) | SEN-22857 | $34.95 | not visible | in stock | https://www.sparkfun.com/sparkfun-vr-imu-breakout-bno086-qwiic.html |
| | Digi-Key bare chip | 1888-1006-2-ND | $12.29 | not visible | 0; 3,369 due 2026-10-26 | https://www.digikey.com/en/products/detail/ceva-technologies-inc/BNO085/9445940 |
| Camera Module 3 (`cam-rpi-v3`) | Adafruit | 5657 | $29.25 | as above | in stock | https://www.adafruit.com/product/5657 |
| | PiShop.us | 46-1 | $29.25 | not visible | in stock | https://www.pishop.us/product/raspberry-pi-camera-module-3/ |
| | SparkFun | SEN-21331 | $32.95 | not visible | in stock | https://www.sparkfun.com/raspberry-pi-camera-module-3.html |
| Zero camera cable (`cam-cable-zero-22pin`) | Adafruit | 3157 (150 mm) / 5819 (300 mm, Pi 5) | $5.95 / $3.16 | as above | in stock | https://www.adafruit.com/product/3157 |
| LiPo 3S 2300 (`lipo-3s-2300-tattu`) | Aloft Hobbies | Tattu 3S 2300 XT60 | **$27.60** | at checkout; free over $99; ground only | Sold Out button vs "In stock" text | https://alofthobbies.com/products/tattu-3s-2300mah-45c-xt60 |
| | Rotorama (EU) | | EUR 25.59 | EU | in stock | https://www.rotorama.com/product/tattu-2300mah-3s-75c |
| | Gens Ace DE (EU, manufacturer) | | EUR 24.99, ~163 g | EU | "unavailable" | https://gensace.de/products/tattu-2300mah-11-1v-75c-3s1p-lipo-battery-pack-with-xt60 |
| LiPo 3S 1300 (`lipo-3s-1300-tattu`) | RaceDayQuads | | $26.99 | ground only | in stock | https://www.racedayquads.com/products/tattu-11-1v-3s-1300mah-75c-lipo-micro-battery-xt60 |
| | WREKD | | $26.99 | USPS Ground Advantage only, free over $199 | FL warehouse | https://wrekd.com/products/tattu-11-1v-3s-1300mah-75c-lipo-battery-xt60 |
| | Genstattu (maker) | | $19.59, 72x36x22 mm | | out of stock | https://genstattu.com/tattu-1300mah-75c-3s1p-lipo-battery-pack-with-xt60-plug.html |
| LiPo 2S 2200 (`lipo-2s-2200-turnigy`) | HobbyKing | Turnigy 2200 2S 40C | **no price read** (403), 122 g, 106x35x16 | | | https://hobbyking.com/turnigy-2200mah-2s-40c-lipo-pack-w-xt60.html |
| | Red Wolf Airsoft (2S 1200 nano-tech, Tamiya plug) | | $9.89-10.99 | | stock unconfirmed | https://www.redwolfairsoft.com/turnigy-nano-tech-7-4v-1200mah-2s-25-50c-lipo-airsoft-pack-tamiya.html |
| B6 Neo (`charger-skyrc-b6neo`) | WREKD | SK-100198 | $39.99 | free over $199 | SOLD OUT | https://wrekd.com/products/skyrc-b6-neo-200w-10a-1-6s-dc-smart-charger-xt60-choose-color |
| | Evike | | $49.95 (snippet) | free lower 48 over $149 | not visible | https://www.evike.com/products/112273/SkyRC-B6Neo-Smart-Balance-Charger-Discharger/ |
| | RadioMaster (snippet) | | $39.99 | | | https://www.radiomasterrc.com/zh/products/skyrc-b6-neo-200w-dc-charger-with-dc-pd-dual-input |
| Buck, 3S (`buck-5v-5a`, DFR0831, 4 A, 7-24 V in) | DFRobot | DFR0831 | $4.90 ($4.50 at 10+) | not visible | in stock | https://www.dfrobot.com/product-2240.html |
| | RobotShop | | $6.21 | not visible | in stock (2026-10-14) | https://www.robotshop.com/products/dfrobot-dc-dc-buck-converter-7-24v-to-5v-4a |
| Buck, 2S (`buck-pololu-d24v22f5`, 5.3-36 V in, 2.2 A) | Pololu | 2858 | $26.95 | not visible | rationed | https://www.pololu.com/product/2858 |
| Buck, Pi 5 (`buck-pololu-d36v50f5`) | Pololu | 4091 | $39.95 ($36.75 at 5+; one snippet said $34.95) | "same-day shipping" | rationed, backorders allowed | https://www.pololu.com/product/4091 |
| | RobotShop | | $39.95 | not visible | in stock (2026-10-15) | https://www.robotshop.com/products/5v-55a-step-down-voltage-regulator-d36v50f5 |
| Servo cables | Waveshare 5264-3PIN 6-pack | | $1.99-3.99 per 6 (variant mapping unclear) | | 300 mm or 900 mm only | https://www.waveshare.com/sr-cable-5264-3pin.htm |
| XT60 pigtail | RaceDayQuads | | $2.49 | | in stock | https://www.racedayquads.com/products/xt60-pigtail-14awg-4 |
| Power switch | REV Robotics | REV-31-1387 (XT30, >20 A) | $13.00 | | in stock | https://www.revrobotics.com/rev-31-1387/ |
| Fasteners, inserts | VXB (snippet) | 170-pc M2/M3 brass insert kit | $49.98 | | | https://vxb.com/fr/products/heat-set-inserts-for-plastic-3d-printing-kit-with |
| Bearings | Open Duck Mini BOM | 3 x 6804ZZ (20x32x7), EUR 3.50 each | | | not servo idlers | https://www.amazon.fr/dp/B0CXXSVFTV |
| Magnets | Total Element (snippet) | 6x2 mm N52, 150 pack | $23.79 | | | https://totalelement.com/products/6mm-x-2mm-neodymium-rare-earth-permanent-disc-magnets-n52-150-pack |
| PLA+ 1 kg | MatterHackers (snippet) | Polymaker PolyLite | $21.99 | | | https://matterhackers.com/store/l/polymaker-polylite-pla-red-175mm-1kg/sk/MDN80MSL |
| TPU 95A 1 kg | Woodartsupply (snippet) | Overture | $20.69 sale | | | https://woodartsupply.com/products/overture-tpu-filament-1-75mm-flexible-tpu-roll-95a-soft-3d-printer-filament-1kg-spool-2-2-lbs-dimensional-accuracy-0-02-mm-tpu-black |
| PETG 1 kg | camelcamelcamel (Sunlu) | | $20.99 (2026-08-04) | | | https://camelcamelcamel.com/product/B0F4L31P2K |

Magnets: no catalog entry. Open Duck Mini's guide and BOM list none, so none are priced into the candidates. Bearings: no source confirms the STS3215 back-shaft bearing size, so measure it on the bench servo.

### Spec corrections made in the catalog
- 7.4 V servo: no-load speed 4.72 -> 5.445 rad/s. STS3250: speed 6.98 -> 7.854 rad/s, mass 72 -> 74.5 g.
- Tattu 3S 1300 mAh: 75x35x22 -> 72x36x22 mm. Tattu 3S 2300 mAh: mass 0.18 -> 0.172 kg (seller weights 163-220 g).
- SkyRC B6 Neo: height 32 -> 31 mm. Its DC input is **10-28 V on an XT60 connector** (not a barrel jack); the PD port accepts only 12-20 V.
- `buck-5v-5a`: reference module is 4 A (5 A only with heat dissipation), minimum input **7 V**; `max_current_a: 4.0` now set (the engine defaulted to 5.0).
- Waveshare adapter price $8 -> $4.99. BNO085 $15 -> $29.50. Camera $25 -> $29.25. Pi 5 $60 -> $110.

## 4. Missing BOM lines (challenge-2 row 14)

| Line | Recommendation | Price | Source and status |
|---|---|---|---|
| **DC supply for the charger** | The B6 Neo takes 10-28 V DC on **XT60**, or USB-C PD at 12-20 V up to 80 W. Cheapest credible: a 65 W USB-C PD brick that offers 20 V (`psu-usbc-pd-65w`) | $29.99 (deal-site snapshot; range $22-35) | Estimate, not a live page. Check the listing says UL/ETL. Alternatives: official Pi 27 W supply, $14.40 at MCCI on backorder (https://store.mcci.com/products/raspberry-pi-27w-usb-c-power-supply), usable only through its 12 V/2.25 A or 15 V/1.8 A profile, about 2 A into a 3S pack, and the B6 Neo's negotiation with it is NOT verified. Adafruit #352 12 V 5 A UL ($24.95, out of stock) needs a barrel-to-XT60 adaptor I could not find |
| **Spare servos** | **3 spares for a 23-servo build (2 for the 14-DOF duck), bought in the same order so the qty-25 tier applies.** For C: 2 x STS3215 + 1 x STS3250 | 3 x $20.90 = $63 (Seeed) or 3 x $27.99 = $84 (OpenELAB) | A judgment, see section 6 |
| **Inline fuse** | 20 A ATC/ATO blade fuse in a 14 AWG inline holder (`fuse-atc-20a-inline`). A 15 A ATO survives a 16 A burst of about 1 s only just (107% of rating, I2t 256 vs 340 A2s minimum) and derates about 25% in a hot enclosure; 20 A opens in 0.15-5 s at 40 A. It protects the 14 AWG wire and XT60 (about 30 A), not the servos. On 2S, recheck against the R10 peak current: the same power draws about 1.6x the current | $4.50 | Estimate: Del City 78332 holder $3.25 (https://www.delcity.net/store/fuses-fuse-accessories/holders-circuit-taps/atc-ato-blade/inline-with-led/78332/) plus a fuse. Time-current bands read second-hand from the Littelfuse 257 ATO datasheet (PDF 403). Eaton Shortstop 15 A breaker $3.40 (Waytek): trip curve not verified |
| **Gamepad** | Logitech F710 2.4 GHz dongle or 8BitDo SN30 Pro / Pro 2 (`gamepad-bluetooth`). R9 allows "gamepad and/or phone", so a phone makes this $0 | $38.68 | Estimate: SHI listing https://texas.gs.shi.com/product/22038825/Logitech-Wireless-Gamepad-F710. 8BitDo's page lists Raspberry Pi as supported; not tested |
| **Camera cable** | Pi Zero (22-pin 0.5 mm) to Camera Module 3 (15-pin 1 mm): the camera's own cable does not fit | $5.95 (Adafruit 3157) | `cam-cable-zero-22pin` |
| **Shipping** | ESTIMATE $45 (FAST) / $60 (CHEAP). Read facts: OpenELAB free over $55; Aloft free over $99; WREKD free over $199; Evike free over $149; LiPos are ground-only | | Not measured: only carts show the real figure |
| **Sales tax** | 7.53% US average on parts and spares | | Tax Foundation 2026-07-06. 0% in five states |
| **Tariffs** | Zero extra on US stock and OpenELAB (DDP). Up to +37.5% on non-DDP China-origin lines | $128-207 exposure on the servo orders | Secondary sources only, see section 1 |

## 5. Charger and power observations

- B6 Neo, 70 x 50 x 31 mm, 82 g, 200 W DC / 80 W PD, 0.2-10 A, 1-6S (https://www.skyrc.com/b6neo). The only manual found covers the B6neo+ (5-30 V DC), not this model.
- Cheapest verified route is a 20 V PD brick. A 3S 2.3 Ah pack at 2.3 A needs about 29 W, so the 27 W Pi supply caps near 2 A.
- The B6 Neo plus its supply is about $70 of a $550 budget, 13%. A cheaper balance charger (`charger-b3-3s`, about $9) exists in the catalog but is slow; not re-quoted.
- Pi Zero 2 W has a real UART path to the Waveshare adapter (jumper A = UART, RX-RX, TX-TX), but the pin labels were not readable.
- Waveshare adapter input is 9-12.6 V. The 2S candidates (B, E) run at 6.0-8.4 V; Waveshare says 5-8.4 V "can also be input" without stating it is supported. Check on the bench.

## 6. Spare-servo evidence

Unknown fleet sizes mean no failure rate can be computed. What exists:
- HomeBrew Robotics Club thread, 16 Aug 2026: one SO-101 builder reports gears stripping on stalls above about 15% of the torque limit and 3 servos burned out; a reply says internal MOSFETs fail before gears (https://groups.google.com/g/hbrobotics/c/wMPp7it97i4). Two posts, voltage and SKU not given.
- Robonine, one 12 V unit: overload protection tripped at 20 kg.cm after several cycles, reached 71 C in a +/-90 deg oscillation, torque cut to about 20% under prolonged load (https://robonine.com/testing-of-feetech-sts3215-servomotor-backlash-repeatability-and-torque/).
- LeRobot issue 2819: 1 SO-101 gripper servo stiffened and failed, attributed to a blocked gripper (https://github.com/huggingface/lerobot/issues/2819). Hiwonder forum and Arduino forum: 1 dead unit each (snippets only).
- tomwhipple/biped-robot issue 73 bench-tested a spare STS3215 and moved hips to STS3250 for stiffness (https://github.com/tomwhipple/biped-robot/issues/73).
- Waveshare warns that screws pressing on the servo body can spike current and burn it.
- No N-of-M counts exist at Open Duck Mini, ToddlerBot or Reddit.

Recommendation: **3 spares per 23 servos (about 13%) and 2 per 14**. Basis: documented failures are mostly stall and overload events, a 23-joint biped walking and falling will have many of them, and a replacement ordered later may miss the 10+ tier and wait 1-3 weeks. This is a judgment; the bench test's overload and thermal results should replace it.

## 7. Surprises

1. Pi 5 4 GB is $110, not $60 (two 2026 memory-driven rises). C pays for it.
2. Pi Zero 2 W: zero in-stock US vendors. Digi-Key says 54 weeks. Pi's own Feb 2026 post says Zero prices were not raised, so this is supply, not price.
3. STS3250 is $74, not $32, and every cheaper listing is sold out. C's two knees cost $148.
4. 2S saves almost nothing on servos ($0-4 each), while its regulator costs $22 more than the 3S one.
5. DFR0831 (the cheapest 5 V buck) needs 7 V in; a 2S pack sags below that.
6. The 7.4 V servo's rating tops out at 7.4 V (some listings 4-7.4 V). A full 2S charge is 8.4 V.
7. The B6 Neo cannot run from a barrel supply: DC is XT60 at 10-28 V.
8. Catalog speed errors: the 7.4 V servo carried the 12 V speed.
9. RobotShop's page shows $31.71 to a fetcher and $49.22 "includes tariffs" in snippets: US retail may already carry tariffs.

## 8. Purchase list: the two bench servos only (maintainer to act; nothing was bought)

Challenge-2 row 3 asks for one 12 V (C018/C047) and one 7.4 V (C001) STS3215. Select the **US warehouse** in the cart, and confirm the cart line shows the voltage.

| Option | 12 V | 7.4 V | Items total | Shipping | Why |
|---|---|---|---|---|---|
| **A. Seeed (cheapest, in stock)** | https://www.seeedstudio.com/STS3215-30KG-Serial-Servo-p-6340.html , SKU 108090003 (C047), **$22.00**, includes 2 horns + 18 screws | https://www.seeedstudio.com/STS3215-19kg-cm-7-4V-Serial-Servo-p-6338.html , SKU 108090023 (C001), **$21.99** | **$43.99** | not visible; promo-era table: US warehouse USPS Priority 3-5 d, Ground 6-9 d | Cheapest, both "In stock" with a US warehouse listed |
| **B. OpenELAB (documented US rates, duty included)** | https://openelab.com/products/feetech-sts3215-c018-servo-12v , SKU Feetech-STS3215-C018, **$27.99** | https://openelab.com/products/feetech-sts3215-c001-servo-7 , SKU Feetech-STS3215-C001, **$23.99** | **$51.98** | USPS Ground $7.99, 3-7 bd, or Priority $15.99, 1-4 bd (under the $55 free line). About $59.97 by Ground before tax | The only vendor that publishes a US-warehouse rate table. The C001 page labels its warehouse as China (8-15 bd): check the cart. Adding about $3.03 of anything reaches the free-shipping line |
| Cheapest, slow (China) | https://www.waveshare.com/st3215-servo.htm?sku=22414 ($21.99) | https://www.waveshare.com/st3215-servo.htm?sku=33014 ($16.99) | $38.98 | not visible | Likely China shipping and possible duty on delivery |
| Sold-out price (watch) | WowRobo $15.99 | WowRobo $15.99 | $31.98 | | Product pages say sold out |

Bench extras not asked for but required to run the test: a bus adapter (Waveshare 25514, $4.99 direct; fastest US source not confirmed) and a bench supply. No vendor sells idler bearings or back-shaft supports; measure the back-shaft boss on arrival.
Recommended order: **A**, fall back to **B** if Seeed shows China-only or a long ETA at checkout.

## 9. Not verified and why

- Amazon, Micro Center, HobbyKing, GetFPV, Mouser, McMaster, AliExpress, Alibaba, eBay item pages, Elegoo and Sunlu stores: unreachable. Filament, fasteners, magnets, wire, cables and bearings are snippet/secondary only and stay `verified: false`.
- Shipping costs and ETAs at nearly every vendor; Seeed's duty terms; Waveshare's US shipping; the Waveshare tier thresholds.
- A Feetech-hosted PDF datasheet (the 12 V/7.4 V values rest on the Feetech wiki table plus vendor listings; the STS3250 only on vendor listings).
- Whether the B6 Neo negotiates 12 V/15 V from the Pi 27 W supply; UL listing of any PD brick; Bussmann breaker curves; DFR0831 holding 3 A across 8.4-12.6 V.
- STS3215 mounting/horn screw sizes, back-shaft bearing size, Pi 5 mass and height, Pi Zero mass, Camera Module 3 official mass.
- Real current tariff rates (secondary sources only).

Catalog `verified: true` (9 parts): sts3215-12v, sts3215-7v4, rpi-zero-2w (price and spec only; no stock), rpi-5-4gb, cam-rpi-v3, buck-5v-5a, buck-pololu-d36v50f5, lipo-3s-1300-tattu, charger-skyrc-b6neo. The rule used: at least two live vendor rows read and a manufacturer or standards-body spec match. Everything else stays false with the reason in `source`.
