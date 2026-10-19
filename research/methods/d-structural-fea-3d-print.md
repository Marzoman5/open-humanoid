# D. Structural / FEA practice for 3D-printed robot parts

Access date for all links: 2026-10-19. "Derived" = arithmetic done here from cited inputs. Material table: `print_materials.yaml`.

## 1. Material properties (summary)
Vendor datasheets (100% infill, ISO 527) give XY tensile 34-52 MPa for PLA/PETG/ABS/ASA and ~72 MPa for PA12-CF; Z is lower (see yaml). Vendors state values are "for reference and comparison only, not for design" ([Polymaker PolyMax PLA](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polymax-tm-pla)).

| Material (vendor) | XY MPa | Z MPa | Z/XY (derived) | Z elong. % | Source |
|---|---|---|---|---|---|
| PLA (PolyMax) | 41.3 | 32.4 | 0.78 | 4.7 | [link](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polymax-tm-pla) |
| PLA Pro (PolyLite) | 49.8 | 36.5 | 0.73 | 2.4 | [link](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polylite-tm-pla-pro) |
| PETG (PolyMax) | 37.9 | 29.4 | 0.78 | 3.10 | [link](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/petg-pet/polymax-tm-petg) |
| ASA | 43.8 | 32.0 | 0.73 | 1.65 | [link](https://wiki.polymaker.com/polymaker-wiki-pt/produtos-polymaker/mais-sobre-nossos-produtos/documentos/fichas-tecnicas/abs-asa/polymaker-tm-asa) |
| PA12-CF10 (product page, annealing unstated) | 71.6 | 43.3 | 0.60 | null (unverified) | [link](https://polymaker.com/product/polymide-pa12-cf/) |
| PA12-CF10 (TDS V1.1, dry, annealed 100 C/16 h) | 77.4 | 52.2 | 0.67 | 5.0 | [PDF](https://fiberon.polymaker.com/wp-content/uploads/TDS_FIBERON-PA12-CF10_V1.1_EN.pdf) |
| PA12-CF10 (TDS V1.1, wet, annealed) | 71.7 | 42.1 | 0.59 | 5.3 | same PDF |

Key point: Z **elongation** collapses more than Z strength (ASA 6.7 -> 1.65 %, PETG notched Charpy 11.6 -> 2.4 kJ/m2) -> Z-loaded parts fail brittle by delamination. TPU95: modulus 33.6 MPa, 551 % elongation ([link](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/tpu/polyflex-tm-tpu95)).
Independent test (ASTM D638 Type I): X-build beat Z-build by ~25 % PLA, ~42 % ABS, ~128 % PETG ([CSUS thesis](https://scholars.csus.edu/esploro/outputs/graduate/Mechanical-and-FEA-comparison-of-FDM/99258311232901671); verified against the thesis abstract page: 24.63 %, 42 %, 127.9 %; abstract only). Vendors disagree: Prusament PETG (TDS v1.1, 2022, ISO 527-1, MK3, 100% rectilinear) shows tensile yield vertical (xz) 50 vs horizontal 47 MPa, notched Charpy 3 vs 6 kJ/m2 ([Prusa TDS](https://www.3dprintergear.com.au/assets/files/technical-data-sheet%20(1).pdf)). ABS caveat: the Polymaker ABS wiki page lists tensile twice, both labelled X-Y (33.4 and 29.7); we read 29.7 as Z, so the 0.89 ratio is low-confidence. Conclusion: coupons from your own printer beat any datasheet.

## 2. Anisotropy and knockdown for FEA
- Recommended practice: orthotropic material, strong in the raster plane, weak across layers; a universal model is "nearly impossible" because slicer settings change it ([ERAU poster](https://commons.erau.edu/db-srs/2025/poster-session/200)). Orthotropic moduli for FDM PLA have been measured ([Bejaia 2026](https://univ-bejaia.dz/revue/baj/article/view/1138)).
- No published design-allowable knockdown was found (searched). Defensible derived approach: use datasheet Z/XY ratio (0.6-0.8 above), then additionally cut for infill and non-ideal printing; evaluate the **weakest direction** at each location. Printed hobby-grade infill knockdown: null (no primary source found; measure).
- Stiffness is much less anisotropic than strength (PLA modulus Z/XY 0.92, PETG 0.95, PA12-CF 0.55, derived from yaml values), so isotropic E with orthotropic strength check is a workable first pass for PLA/PETG/ASA, but not for CF-nylon.

## 3. Fall impact loads for small humanoids
No standard method found for sub-1 m humanoids (searched). Physics method (derived, not sourced):
1. Impact speed v = sqrt(2 g h). Example h = 0.30 m (e.g. toppling from standing hip/CoM height) -> v = 2.4 m/s (sqrt(5.886) = 2.43).
2. Average deceleration a = v^2 / (2 d), d = effective stopping distance (flex of part + foam/TPU + servo back-drive). d = 5 mm -> 60 g; d = 2 mm -> 150 g (derived; a/g = h/d exactly). Static equivalent factor n = a/g; F = m a.
3. Peak exceeds average; apply a peak/average factor from your own drop-test accelerometer data (null in literature).
Literature anchors: life-size humanoid fall impacts exceeded 100 g peak, airbag cut to 20-30 g ([Kajita et al., Humanoids 2016](https://unit.aist.go.jp/jrl-22022/assets/bib/kajita_humanoids_2016.bib); abstract via search summary; IEEE Spectrum reports HRP-2Kai 82-113 g); analytic fall model for predicting impact acceleration ([Olivieri & Braghin 2019](https://re.public.polimi.it/handle/11311/1163447)); Darwin-OP arm stiffness vs impact force ([Calderon 2016](https://www.ais.uni-bonn.de/robocup.de/2016/papers/RoboCup_Symposium_2016_Calderon.pdf)).
Small robots benefit from scaling: energy ~ m g h, and impact stress scales with mass/area; a 0.5 m robot is far milder than life size, but the deceleration distance is also smaller, so g-loads are comparable. Prefer energy-absorbing design (TPU bumpers, compliant shell) over strength; validate with an accelerometer drop test.

## 4. Fatigue of printed parts
- Reference PLA S-N: inverse slope 5.5, endurance limit at 2e6 cycles = 10 % of UTS (Pf > 95 %), build direction "little effect" ([Ezeh & Susmel 2018](https://eprints.whiterose.ac.uk/id/eprint/133457/); abstract read; a reference curve for use when no test data exist, mean-stress effect modelled via max stress in the cycle; load ratio not in abstract, so treat as a screening value).
- ASA 25 % (8 MPa), Nylon 12 17 % (7.4 MPa), PC 7 %, PC-ABS 15 % of tensile strength, R = 0.05 ([Rodrigues et al. 2026, Polymers 18(2):302](https://api.crossref.org/works/10.3390/polym18020302), abstract read). The earlier cited eprint 150845 is a PLA paper and does not contain these numbers.
- PETG S-N exists ([Martins et al. 2024, PLA and PETG, R = 0.2, 45 deg raster](https://pmc.ncbi.nlm.nih.gov/articles/PMC11243948/); full text blocked by captcha); fraction: null.
- Implication: walking cyclic loads should stay <10 % of UTS (~3-4 MPa for PLA) at stress concentrations, or use PETG/nylon and fillets.

## 5. Screws and heat-set inserts
- CNC Kitchen test: M3 direct screw, heat-set insert and Helicoil all failed around ~120 kg-force; a bottom-pocket location was stronger (160+ kg) than side (~85 kg) ([summary](https://www.embedded-computing.com/home-page/3d-printed-fasteners-part-1-inserts); UNVERIFIED this pass, page returned 403). (The article mixes torque-out and pull-out; treat as indicative.)
- Cavity example for M3: depth 3.8 mm, 5.1-5.31 mm diameter; keep >=2 mm material around the insert ([Markforged](https://markforged.com/blog/heat-set-inserts); UNVERIFIED this pass, 403). Tune hole diameter empirically with test parts ([CNC Kitchen](https://www.cnckitchen.com/blog/tipps-amp-tricks-fr-gewindeeinstze-im-3d-druck-3awey)).
- Sculpteo: larger inserts pull out higher (M2 ~477 N short to >1,800 N M5/M6) in MJF PA12, not FDM ([Sculpteo](https://www.sculpteo.com/en/3d-learning-hub/design-guidelines/pull-out-resistance-of-threaded-inserts-testing-and-results/)). M3 FDM pull-out N values: null.
- Orient insert axis in the XY plane's strong direction: screw load along Z layers pulls layers apart.

## 6. Free/accessible FEA tools
- FreeCAD FEM + CalculiX (default solver; linear/nonlinear static, dynamic, thermal; also Elmer, Mystran) ([FreeCAD wiki](https://wiki.freecad.org/FEM_CalculiX)). Isotropic out of box; orthotropic via CalculiX input edits - verify.
- Onshape Simulation, SolidWorks Simulation (user's CAD tools): built-in, easy setup ([comparison](https://www.g2.com/compare/freecad-vs-solidworks-solidworks-simulation)); orthotropic support and licence tier: null (not found; check vendor docs).
- scikit-fem: Python FEM library for custom orthotropic or scripted studies; no source fetched in this session (null).
Use FEA for stiffness/stress hot spots; use drop tests for impact.

## 7. Typical safety factors
No FDM-specific SF standard found (searched). Guidance: apply the SF to the weakest-direction (Z) strength, not bulk data ([QSpace thesis](https://qspace.library.queensu.ca/items/4a28f61d-0cf6-4083-8577-e24378aced22); [zbotic](https://zbotic.in/3d-printed-robot-parts-structural-design-considerations-for-strength-and-durability/)). Numbers for Open Humanoid are a judgement call (suggested below), not sourced.

## Recommendation for Open Humanoid
Treat datasheet XY values as ceilings and design with Z strength (0.6-0.8 x XY, then a further infill penalty measured from your own coupons) in the weakest direction at every stress hot spot; orient layers along the main load and never put screw tension or bending across layer lines. Seed FEA with PETG/ASA/PLA Pro numbers from `print_materials.yaml`, but gate the design on a printed-coupon tensile and drop test (accelerometer, 0.3 m) rather than FEA alone, because impact stopping distance and peak/average factors have no published values. Use a suggested SF of >=3 on Z-direction static strength and keep cyclic stress below ~10 % of UTS at features (fillet everything). Prefer PETG (or PA12-CF for stiff load paths, noting Z is only 0.60-0.67 of XY) for structure, TPU for bumpers/feet, M3 heat-set inserts in bottom/side pockets with 2 mm walls, and FreeCAD+CalculiX or the Onshape/SolidWorks tools the user already owns for the first-pass stress check.
