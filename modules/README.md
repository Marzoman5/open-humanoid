# Modules

Reusable building blocks: joints, limbs, hands, heads, feet, attachments (gutter scoop, camera mast…), and software plugins that come with hardware.

A module is a folder `modules/<kind>/<id>/` containing:

```
module.yaml        # what it is, where it's valid, its interfaces (schema: see _template/module.yaml)
cad/               # source (any backend) + export/ per the CAD export contract
README.md          # what it does, how to build it, photos
software/          # optional: driver/plugin code it needs
```

## Validity ranges are mandatory

Modules don't scale forever. Each one declares where it works, e.g. `valid: { height_m: [0.4, 0.7], actuator_family: [feetech_sts] }`. Tools refuse to place a module outside its range.

## Modular vs integrated variants

- `architecture.style: modular`: variants are assembled from modules that meet [INTERFACE.md](INTERFACE.md) (standard mount, connector, bus).
- `architecture.style: integrated`: the variant's own CAD may merge modules into optimized monolithic parts. It doesn't have to expose the standard interfaces, but it still meets the CAD export contract.

## Kinds

`joint/` · `leg/` · `arm/` · `hand/` · `head/` · `torso/` · `foot/` · `attachment/` · `sensor/`
