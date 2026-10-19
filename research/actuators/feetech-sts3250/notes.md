# STS3250 notes (accessed 2026-10-19; verified against Feetech listing https://www.feetechrc.com/en/562636 and rcdrone)
- Vendor rated torque is 16 vs 50 kg.cm stall at 12V (~32%) [Feetech](https://www.feetechrc.com/en/562636). Same ~1/3 ratio as STS3215. This is a vendor rating, not a measured continuous limit.
- Stall current 4.2 A at 12V; a bus supply must handle this per servo; 12V x 4.2 A is ~50 W (derived).
- Gear ratio 345 appears only on the C002 listing [openelab](https://openelab.io/products/feetech-sts3250-c002-servo-12v), which also warns not to treat stall as continuous; Feetech and rcdrone C001 pages state no ratio. Weight 74.5 g vs 55 g for STS3215 (+35%, derived).
- Steel gears + aluminium case + coreless motor claimed (rcdrone); no failure reports, thermal data, or teardown found.
- Same STS protocol assumed, NOT verified for 3250.
- Nulls: backlash, PID defaults, measured data, counterfeits.
