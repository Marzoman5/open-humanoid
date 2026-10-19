<!-- prompt: sourcing/part-sourcing · version: 0.1 · tested-on: (not yet run) · tier: light (search) + mid (judgement) -->
# Part sourcing & price verification

> Paste below the line. Fill the scope.

---

You are verifying and sourcing parts for Open Humanoid.

**Scope:** ____ (e.g. "all lines in variants/adam/generated/bom.md", or "catalog/actuators/sts3215-12v.yaml", or "find a ≥40 N·m continuous actuator under $600")
**Ship-to region:** ____ (e.g. US) · **Quantity:** ____ (affects bulk pricing)

## Procedure (per part)
1. Read the catalog file. Note the claimed specs and price.
2. Search at least **3 vendors** across channel types where they exist: manufacturer/official store, a Western distributor (Amazon, Digikey, Robotshop, Adafruit…), and a direct-from-China channel (AliExpress, Taobao agents, the brand's own store).
3. For each vendor record: URL, unit price at the target quantity, shipping to the region, stock, date checked, and the exact variant/SKU (e.g. 12 V vs 7.4 V versions of the same servo).
4. Check specs against the **manufacturer datasheet**, not a listing title: stall torque *with voltage*, no-load speed *with voltage*, mass, voltage range, feedback type. Listing titles often inflate torque.
5. Update the catalog YAML:
   - `price_usd.typical` = median landed unit price; `low`/`high` = min/max seen; `as_of` = today
   - `vendors:` list with name/url/price/checked
   - `verified: true` only if ≥ 2 vendors are live **and** specs match a datasheet; put the datasheet URL in `source`
   - fix any spec that was wrong, and say so in the commit message
6. Watch for red flags: counterfeit Dynamixels and Feetechs, "kg" ratings without voltage, a price far below peers, "compatible" clones. Record them in `notes:`.

## Outputs
- Updated `catalog/**.yaml` files (stay within the catalog: claim task paths `catalog/`)
- Re-run `oh size <variant>` and `oh bom <variant>`. Report how the total moved and whether any selection changed.
- A short summary: parts verified, parts still unverified (why), biggest price surprises, and any recommended substitutions (as suggestions, not edits to specs).

## Never
- Never buy, add to cart, sign in, or enter payment details. Sourcing is read-only research.
- Never mark `verified: true` from memory or from a single listing.
