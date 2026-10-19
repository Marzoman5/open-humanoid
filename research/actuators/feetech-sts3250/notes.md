# STS3250 notes (accessed 2026-10-19)
- Vendor rated torque is 16 vs 50 kg.cm stall at 12V (~32%) [rcdrone](https://rcdrone.top/ja/products/feetech-sts3250-servo-motor). Same ~1/3 ratio as STS3215.
- Stall current 4.2 A at 12V; a bus supply must handle this per servo; 12V stalls draw ~50 W.
- Gear ratio 345 only on the C002 listing [openelab](https://openelab.io/products/feetech-sts3250-c002-servo-12v); weight 74.5 g vs 55 g for STS3215 (+35%).
- Steel gears + aluminium case claimed; no failure reports, thermal data, or teardown found. Same STS protocol/quirks as STS3215 (see its notes).
- Nulls: backlash, PID defaults, measured data, counterfeits.
