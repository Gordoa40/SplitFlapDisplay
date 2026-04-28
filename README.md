# Split-Flap Display

A modular, 3D-printed split-flap display controllable over RS485 from a Raspberry Pi. Each module holds 64 characters and modules can be chained together to build a display of any width.

**YouTube Build Video:** https://www.youtube.com/watch?v=-C8_AtxEEQc

---

## How It Works

Each module contains:
- A 3D-printed drum that holds 64 individual flaps (one per character)
- A stepper motor driving the drum through a gear train
- A Hall effect sensor for homing
- A custom driver PCB (ATtiny1616 + RS485 transceiver + ULN2003 stepper driver)

Modules communicate over a shared RS485 bus. A Raspberry Pi running a Python web interface sends commands over USB-RS485 to each module individually by address.

---

## Repository Structure

```
CAD/                              - 3D printable parts (Bambu Lab profiles included)
SplitFlapDriverATtiny1616 V2 KiCad/  - Driver PCB KiCad that I used in the video, for my build
SplitFlapDriverATtiny1616V3       - Updated Driver PCB KiCad project, which should be slightly cheaper to manufacture
SplitFlapBusBoard KiCad/          - Bus board KiCad project
SplitFlapFirmware/                - Arduino firmware for the PCBs
SplitFlap-RPI-FRONTEND/           - Raspberry Pi Python web frontend
Reference Docs/                   - Component datasheets
BOM.md                            - Bill of materials

---

## Parts List

See [BOM.md](BOM.md) for the complete bill of materials, broken into three sections:

- **PCB / Electronics** — all SMD components with JLCPCB part numbers for easy ordering
- **Module BOM** — 3D printed parts and hardware per module, with quantities scaled to 45 modules
- **Other Components** — system-level parts (Raspberry Pi, power supply, C14 connector, etc.)

---

## Ordering the PCB from JLCPCB

The driver board is designed to be ordered from JLCPCB with their PCB Assembly (PCBA) service so the SMD components arrive pre-soldered.

### Step 1 — Export Gerbers from KiCad

1. Open the project in `SplitFlapDriverATtiny1616 V2 KiCad/`
2. In KiCad PCB editor, go to **File → Fabrication Outputs → Gerbers**
3. Export to a folder, then zip the contents
4. Also export the drill file from the same menu

Alternatively, pre-exported Gerber and PCBA files are already be present in the KiCad project folder.

### Step 2 — Upload to JLCPCB

1. Go to [jlcpcb.com](https://jlcpcb.com) and click **Order Now**
2. Upload the Gerber zip file
3. Set your desired quantity (minimum 5)
4. Leave most settings at default; adjust PCB colour if desired

### Step 3 — Enable PCB Assembly (PCBA)

1. Toggle **PCB Assembly** on
2. Select **Standard PCBA** and set the assembly side to **Top Side**
3. Click **Confirm**

### Step 4 — Upload BOM and CPL Files

1. Upload the **BOM file** from the KiCad project folder — this maps component values to JLCPCB part numbers. The part numbers in `BOM.md` match what is in this file.
2. Upload the **CPL (Component Placement List)** file — this tells JLCPCB where each component sits on the board
3. Review the component matches on the next screen. All parts should auto-match using the C-numbers in [BOM.md](BOM.md). Confirm any that need manual review.

### Step 5 — Review and Order

1. Check the parts list — confirm quantities and part numbers match the [BOM.md](BOM.md) PCB section
2. Proceed through the review screens and place your order

> **Note:** A few through-hole parts (pin headers, JST connectors) are not included in PCBA. These are listed in the BOM and will need to be soldered by hand.

---

## 3D Printing

All printable files are in the `CAD/` folder. A Bambu Lab print profile is included in `CAD/64FlapsWithLetters/` for the flaps. Print the flaps in the correct colour for each character — see the video for details on the full 64-character set.

Parts per module:
- Enclosure Body, Right Cover, Left Cover
- Drum Body, Drum Cap
- Motor Gear, Center Gear, Gear Plate
- DIN Rail Mount, Wire Retainer
- 64 Flaps

---

## Firmware

Located in `SplitFlapFirmware/`. The firmware is Arduino-based and targets the ATtiny1616.

- Flash via UPDI programmer (see https://github.com/SpenceKonde/AVR-Guidance/blob/master/UPDI/jtag2updi.md if you need to make one)
- Each module needs a unique address (0–44) stored in EEPROM. Be sure to edit this between flashes.

---

## Frontend

Located in `SplitFlap-RPI-FRONTEND/`. A Python web interface running on a Raspberry Pi sends display commands over USB-RS485 at 115200 baud.

Need a USB-serial dongle. I used this one: https://www.adafruit.com/product/5994

---

## License

This project is licensed under [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/).

You are free to share and adapt this project for non-commercial purposes, as long as you give appropriate credit to Adam G Makes and distribute any derivatives under the same license.
