# PrinterMax M58 — Bluetooth Thermal Printer Control

Web-based control panel for the **PrinterMax M58** 58mm Bluetooth thermal receipt printer.
Runs a small Flask server on your PC that talks to the printer over a Bluetooth COM port using the ESC/POS protocol.

![stack](https://img.shields.io/badge/Python-3-blue) ![flask](https://img.shields.io/badge/Flask-2.3+-green) ![license](https://img.shields.io/badge/license-MIT-orange)

## Features

- **Connect / disconnect** to any Bluetooth COM port with adjustable baud rate
- **Text printing** — alignment, bold, underline, 2x width/height, feed control, live receipt preview
- **Image printing** — drag-and-drop PNG/JPG/BMP, auto-converted to 1-bit B&W at full 384px (203 DPI) width
- **Barcode printing** — UPC-A/E, EAN13/8, CODE39/93/128, ITF, CODABAR with height & HRI position
- **QR code printing** — configurable module size
- **Combo Builder** — stack Text / Image / Barcode / QR / Feed / Cut blocks into a single receipt
- **Maintenance tools**
  - Head cleaning (prints solid/striped black bands to scrub the thermal head)
  - Alignment / diagnostic test page (grids, margins, checkerboard, barcode + QR)
  - Printer status reader (paper & online sensors via `DLE EOT`)
- **Quick actions** — feed paper, auto-cut

## Device specs

| Spec | Value |
|---|---|
| Paper | 58mm thermal roll (react/receipt or self-adhesive label) |
| Printable width | 48mm · 384 dots |
| Resolution | 203 DPI (8 dots/mm) |
| Interface | Bluetooth Serial (virtual COM port), PIN `1234` |
| Protocol | ESC/POS |

## Requirements

- Windows (primary), macOS/Linux work too with a paired BT serial device
- Python 3.8+
- Dependencies: `flask`, `pyserial`, `Pillow` (installed automatically by `start.bat`)

## Setup

### 1. Pair the printer

1. Turn the printer on.
2. In Windows **Bluetooth settings** → *Add Bluetooth device*, pair the M58 (PIN: `1234`).
3. Note the **COM port** Windows assigns (e.g. `COM7`).

### 2. Run the app

**Easiest (Windows):**

```bat
python\start.bat
```

**Manually:**

```sh
cd python
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

### 3. Connect

1. Pick your Bluetooth COM port (use **Refresh** if it's missing).
2. Leave baud rate at `115200` if it defaults there.
3. Click **Connect** — the status indicator turns green.

> **Tip:** if printing fails or output is garbled, try lower baud rates (`9600` / `19200`).

## Usage

Each tab handles one job type:

| Tab | What it does |
|---|---|
| Text | Type multi-line content, set alignment/style/size, print with live preview |
| Image | Drop an image; it is dithered to B&W and printed full width |
| Barcode | Pick a symbology, set height & HRI text position |
| QR Code | Enter any text/URL, choose module size |
| Combo | Build a multi-block receipt (text + logo + QR + barcode + cut) |
| Tools | Head cleaning, alignment test page, status diagnostics |

## API

| Method | Endpoint | Body / Notes |
|---|---|---|
| GET | `/api/ports` | List COM ports |
| POST | `/api/connect` | `{port, baudrate}` |
| POST | `/api/disconnect` | — |
| GET | `/api/status` | `{connected}` |
| POST | `/api/feed` | `{lines}` |
| POST | `/api/cut` | — |
| POST | `/api/print/text` | `{text, bold, underline, align, width, height, feed_lines}` |
| POST | `/api/print/image` | `{image}` (base64 data URL) |
| POST | `/api/print/barcode` | `{content, type, height, hri_position}` |
| POST | `/api/print/qrcode` | `{content, size}` |
| POST | `/api/print/combo` | `{items: [{type, ...}], cut, feed_after}` |
| POST | `/api/tools/clean` | `{sheets, pattern}` |
| POST | `/api/tools/test` | — |
| GET | `/api/tools/status` | Paper / online sensor values (best-effort) |

## Project structure

```
printermax-m58/
├── python/
│   ├── app.py            # Flask backend + all ESC/POS logic
│   ├── start.bat         # Windows launcher (installs deps + runs server)
│   ├── requirements.txt
│   └── templates/
│       └── index.html    # Single-page web UI (HTML/CSS/JS)
├── LICENSE
└── README.md
```

## Maintenance notes

- **Faint or streaky prints?** Use the *Head Cleaning* tool (solid black pattern). For stubborn residue, power off, open the cover, and gently wipe the thermal head with a cotton swab dipped in 90%+ isopropyl alcohol.
- **Misaligned content?** Print the *Test Page* and compare the margin columns / grid against the 48mm printable area.

## Troubleshooting

- **No ports shown** — printer not paired yet, or Bluetooth driver missing. Pair in Windows first, then Refresh.
- **"Printer not connected"** — connect first, then verify the COM port is the one Windows assigned.
- **Garbled output** — wrong baud rate. Lower it via the dropdown.
- **Server already running** — port 5000 busy; stop the other instance or change `app.py` (`port=5000`).

## License

Released under the [MIT License](LICENSE).