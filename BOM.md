# Split-Flap Display BOM (Bill of Materials)

## Project Overview
A modular split-flap display system with 64 characters per module, controllable via RS485 from a Raspberry Pi. Designed by Adam G Makes.

**YouTube Video:** https://www.youtube.com/watch?v=-C8_AtxEEQc

**YouTube Channel:** https://www.youtube.com/@AdamGMakes

---

## PCB / Electronics BOM (Per Driver Board)

| Comment | Designator | Footprint | JLCPCB Part # |
|---------|-----------|-----------|---------------|
| ATtiny1616-MNR | U1 | VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm | C507118 |
| 470n | C3, C8, C6, C2 | C_0603_1608Metric | C1623 |
| ULN2003ADR | U2 | SOIC-16W_5.3x10.2mm_P1.27mm | C7512 |
| HallEffect | J4 | PinHeader_1x03_P2.54mm_Vertical | C131339 |
| 100u | C1 | C_Elec_5x5.4 | C3347 |
| 100n | C7 | C_0603_1608Metric | C14663 |
| 0R | R1 | R_0805_2012Metric | C17477 |
| LED | D1 | LED_0201_0603Metric | C3646923 |
| StepperConnector | J3 | JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical | C157991 |
| SN65HVD72DR | U3 | SOIC-8_5.3x6.2mm_P1.27mm | C48125 |
| 60R | R2 | R_0201_0603Metric | C88957 |
| SPX3819M5-L-3-3 | U5 | SOT-23-5 | C20617301 |
| SPX3819M5-L-5-0 | U6 | SOT-23-5 | C20617302 |
| 10u | C5, C9, C4 | C_0603_1608Metric | C19702 |

---

## Module BOM

### 3D Printed Parts

| Part | Qty per Module | Qty (45 Modules) |
|------|---------------|-----------------|
| Enclosure Body | 1 | 45 |
| Enclosure Right Cover | 1 | 45 |
| Enclosure Left Cover | 1 | 45 |
| Drum Body | 1 | 45 |
| Drum Cap | 1 | 45 |
| DIN Rail Mount | 1 | 45 |
| Motor Gear | 1 | 45 |
| Center Gear | 1 | 45 |
| Gear Plate | 1 | 45 |
| Wire Retainer | 1 | 45 |
| Flap | 64 | 2880 |

### Other Parts

| Part | Qty per Module | Qty (45 Modules) |
|------|---------------|-----------------|
| M3 Nuts | 12 | 540 |
| M3 x 8mm Socket Head Screw | 4 | 180 |
| M3 x 30mm Socket Head Screw | 4 | 180 |
| M3 x 40mm Socket Head Screw | 4 | 180 |
| A3200 Hall Effect Sensor | 1 | 45 |
| 28BYJ-48 12V Stepper Motor | 1 | 45 |
| Driver Board | 1 | 45 |
| Pogo Pins | 4 | 180 |
| 3-Pin JST Connector | 1 | 45 |

---

## Other Components (System-Level)

| Qty | Component | Notes |
|-----|-----------|-------|
| 1 | Raspberry Pi | Controller |
| 1 | USB-RS485 Dongle | PC/RPi to RS485 adapter |
| 1 | 12V Power Supply | Module power |
| 1 | C14 Power Connector | Panel-mount inlet |
| 1 | Power Switch | Main power switch |
| 1 | C14 Power Cable | IEC mains cable |
