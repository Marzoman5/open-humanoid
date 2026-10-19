# STS3250 vendor CAD (T-20261019-f6e2, 2026-10-19)

Feetech publishes **no STEP** for the ST-3250-C001 ("STEP / 3D model: to be supplemented" on its wiki page) and the datasheet PDF link timed
out. The dimension drawing (`ST-3250-C001-drawing.webp`, https://ftservo.github.io/ftservo-wiki/products/models/st-3250-c001/images/drawing.webp,
33,916 B, "Copyright (c) FEETECH", no licence: kept local, gitignored) prints the same case as the ST-3215-C018 drawing:
45.22 x 24.72 x 35, 29 mm at the output, spline 3.4 above that face, Ø6 back boss 4.1 below it (36.5 overall), 25T spline with an M3 x 6
centre screw, 4 x M2 face holes, 2 x 5264/2.54 3-pin connectors on the back face starting 12.5 mm from the axis. Mass 74.5 +- 1 g (wiki).

The catalog block (`catalog/actuators/sts3250-12v.yaml` `mechanical:`) therefore reuses the STS3215 numbers measured from the Waveshare
STEP; see `../../feetech-sts3215/vendor-cad/README.md` for the table of changes.
