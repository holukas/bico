# Data blocks

This folder holds the data-driven format specs that tell `bico` how to convert a
binary raw-data stream into ASCII. Each instrument/logging variant is one
`.dblock` file; adding support for a new format means adding a `.dblock` file, not
changing code.

- **`*.dblock`** — the machine-readable spec used during conversion. Each line
  defines one variable (byte count, struct format, gain/offset, units, conversion
  type) as a Python dict literal.
- **`*.md`** — human-readable documentation for the companion `.dblock`: what each
  variable means, history, and binary-format notes.
- **[`_help_bico_settings.md`](_help_bico_settings.md)** — explains every variable
  property used inside a `.dblock` (`order`, `bytes`, `format`, `gain_on_signal`,
  `apply_gain`, `conversion`, …). Start here to read or author a `.dblock`.
- **[`header/wecom3.py`](header/wecom3.py)** — the logger header (`WECOM3`) that
  precedes each data block in the binary stream.

A measurement is configured by picking a logger header plus up to three
instrument data blocks (a sonic anemometer and one or two gas analyzers); see the
site `bico.settings` files and the conversion core in
[`bico/ops/bin.py`](../../ops/bin.py).

## Logger header

| Header | Spec |
|--------|------|
| WECOM3 | [wecom3.py](header/wecom3.py) |

## Sonic anemometers

| Data block | Description | Spec | Docs |
|------------|-------------|------|------|
| HS100-A | Gill HS-100 | [.dblock](HS100-A.dblock) | [.md](HS100-A.md) |
| HS50-A | Gill HS-50 | [.dblock](HS50-A.dblock) | [.md](HS50-A.md) |
| HS50-B | Gill HS-50 (variant) | [.dblock](HS50-B.dblock) | [.md](HS50-B.md) |
| R2-A | Gill R2 | [.dblock](R2-A.dblock) | [.md](R2-A.md) |
| R350-A | Gill R3-50 | [.dblock](R350-A.dblock) | [.md](R350-A.md) |
| R350-B | Gill R3-50 (variant) | [.dblock](R350-B.dblock) | [.md](R350-B.md) |

## Gas analyzers — IRGA (infrared)

| Data block | Description | Spec | Docs |
|------------|-------------|------|------|
| IRGA72-A | LI-COR LI-7200 | [.dblock](IRGA72-A.dblock) | [.md](IRGA72-A.md) |
| IRGA72-A-GN1 | LI-COR LI-7200 (GN1 variant) | [.dblock](IRGA72-A-GN1.dblock) | [.md](IRGA72-A-GN1.md) |
| IRGA72-B | LI-COR LI-7200 (variant) | [.dblock](IRGA72-B.dblock) | [.md](IRGA72-B.md) |
| IRGA72-B-GN1 | LI-COR LI-7200 (B, GN1 variant) | [.dblock](IRGA72-B-GN1.dblock) | [.md](IRGA72-B-GN1.md) |
| IRGA75-A | LI-COR LI-7500 | [.dblock](IRGA75-A.dblock) | [.md](IRGA75-A.md) |
| IRGA75-A-GN1 | LI-COR LI-7500 (GN1 variant) | [.dblock](IRGA75-A-GN1.dblock) | [.md](IRGA75-A-GN1.md) |

## Gas analyzers — QCL (Aerodyne quantum cascade laser)

| Data block | Description | Spec | Docs |
|------------|-------------|------|------|
| QCL-A | Aerodyne QCL | [.dblock](QCL-A.dblock) | [.md](QCL-A.md) |
| QCL-A2 | Aerodyne QCL (variant) | [.dblock](QCL-A2.dblock) | [.md](QCL-A2.md) |
| QCL-A3 | Aerodyne QCL (variant) | [.dblock](QCL-A3.dblock) | [.md](QCL-A3.md) |
| QCL-A4 | Aerodyne QCL (variant) | [.dblock](QCL-A4.dblock) | [.md](QCL-A4.md) |
| QCL-B | Aerodyne QCL (variant) | [.dblock](QCL-B.dblock) | [.md](QCL-B.md) |
| QCL-C | Aerodyne QCL (variant) | [.dblock](QCL-C.dblock) | [.md](QCL-C.md) |
| QCL-C2 | Aerodyne QCL (variant) | [.dblock](QCL-C2.dblock) | [.md](QCL-C2.md) |
| QCL-C3 | Aerodyne QCL (variant) | [.dblock](QCL-C3.dblock) | — |
| QCL-D | Aerodyne QCL (variant) | [.dblock](QCL-D.dblock) | [.md](QCL-D.md) |
| QCL-ISO | Aerodyne QCL (isotopes) | [.dblock](QCL-ISO.dblock) | [.md](QCL-ISO.md) |
| QCL-L | Aerodyne QCL (variant) | [.dblock](QCL-L.dblock) | [.md](QCL-L.md) |
| QCL-L2 | Aerodyne QCL (variant) | [.dblock](QCL-L2.dblock) | [.md](QCL-L2.md) |

## Gas analyzers — LGR (Los Gatos Research)

| Data block | Description | Spec | Docs |
|------------|-------------|------|------|
| LGR-A | Los Gatos Research analyzer | [.dblock](LGR-A.dblock) | [.md](LGR-A.md) |

## Instrument manuals

Original manufacturer documentation for the logged instruments (in
[`docs/`](../../../docs)):

- [Gill R3-50 sonic anemometer](../../../docs/r3-50-manual_200502.pdf)
- [`sonicread` logging script](../../../docs/sonicread_20190503.pdf)
- [Aerodyne QCL](../../../docs/qcldoc_20200515.pdf)
- [Los Gatos Research (LGR) analyzer](../../../docs/lgrdoc_20180601.pdf)

## Reference-only docs (no `.dblock`)

Documentation for older/legacy formats kept for reference; these have no
companion `.dblock` and are not selectable for conversion.

- [HS50-R1.md](HS50-R1.md)
- [R350-R1.md](R350-R1.md)
- [IRGA72-R1.md](IRGA72-R1.md)
- [IRGA72-R2.md](IRGA72-R2.md)
- [IRGA75-R1.md](IRGA75-R1.md)
- [IRGA75-R2.md](IRGA75-R2.md)
