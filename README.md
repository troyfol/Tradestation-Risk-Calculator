# Trade Solver

A lightweight Windows desktop calculator for active traders. Given an entry price, stop loss, and dollar risk, Trade Solver computes position size, cost basis, and profit/loss at configurable R-multiple targets. It also supports **Smart Click** — click directly on a price in TradeStation (or any charting platform) and the app reads it via OCR, filling in Entry and Stop automatically.

---

## Features

- **Position sizing** — Enter any three of Entry, Stop, Risk $, and Shares; the fourth is calculated automatically.
- **Smart Click (OCR automation)** — Enable the checkbox, click on a price in your charting software, and the app captures the screen region around your click, reads the price with Tesseract OCR, and fills it into the next field (alternating Entry / Stop).
- **LFA (Long First Arrival)** — Adaptive OCR delay. Uses a longer capture delay when you first switch back to your charting platform (giving the chart time to render), then a shorter delay for subsequent clicks. Toggled via checkbox.
- **Configurable profit targets** — Define up to 10 R-multiple targets, each with a custom color. Default: 1R, 2R, 3R (green).
- **Settings window** — Adjust OCR timing (normal delay, LFA delay), OCR capture region (pixel offsets from click), and profit target definitions without cluttering the main interface.
- **Dark theme** — Low-distraction dark UI that stays on top of other windows.
- **Always on top** — The calculator floats above your charting platform.
- **DPI-aware** — Coordinates stay accurate on scaled displays.
- **Persistent config** — Window position/size, font size, Risk $ value, and all settings are saved to `window_config.json` and restored on next launch.
- **Adjustable font size** — `+` / `-` buttons to scale the UI.

## Requirements

### Running from source

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed at `C:\Program Files\Tesseract-OCR\` (required for Smart Click; the calculator works without it but OCR features are disabled)
- Python packages:
  - `pytesseract`
  - `Pillow`
  - `pynput`

Install dependencies:

```
pip install pytesseract Pillow pynput
```

### Running the standalone .exe

No Python installation or additional dependencies required. Tesseract is bundled inside the executable. Just run `trade_calc_v4.exe`.

## Usage

### Basic workflow

1. Set your **Risk $** (this persists across sessions and clears).
2. Choose **Long** or **Short** direction.
3. Enter an **Entry** price and a **Stop** price. The app calculates **Shares** and **Cost** automatically.
4. The output table shows P/L at your stop, entry, and each configured R-multiple target.

### Smart Click workflow

1. Check **Smart Click** and (optionally) **LFA**.
2. Click on a price in your charting software — the app OCR-reads the price and fills **Entry**.
3. Click on a second price — the app fills **Stop**, auto-detects Long/Short direction, and calculates everything.
4. Click **Clear** to reset for the next trade setup.

### Input scenarios

The calculator flexibly solves for the missing variable:

| Given                     | Computes       |
|---------------------------|----------------|
| Entry + Stop + Risk $     | Shares, Cost   |
| Entry + Stop + Shares     | Risk $, Cost   |
| Entry + Shares + Risk $   | Stop, Cost     |
| Entry + Cost (no Shares)  | Shares         |

### Settings

Click the **Settings** button to open the configuration window:

- **OCR Timing** — Normal Delay (default 0.1s) and LFA Delay (default 0.5s).
- **OCR Capture Region** — Pixel offsets from the click point (Left, Right, Above, Below). Adjust if OCR is reading the wrong area.
- **Profit Targets** — Add or remove R-multiple rows (1 to 10). Each target has a configurable R-multiple and color. Click the color swatch to pick a new color.

Settings are saved automatically and persist across sessions.

## Project structure

```
price_calc/
  price_calc_III.py       # Application source (single file)
  icon3.ico               # Application icon
  window_config.json      # Auto-generated settings/config (created on first close)
  trade_calc_v4.spec      # PyInstaller build spec
  dist/
    trade_calc_v4.exe     # Standalone executable
```

## Building the .exe

From the `price_calc/` directory with PyInstaller installed:

```
pyinstaller --onefile --noconsole --name trade_calc_v4 --icon icon3.ico ^
  --add-data "C:\Program Files\Tesseract-OCR;Tesseract-OCR" ^
  --add-binary "C:\python\Library\bin\tcl86t.dll;." ^
  --add-binary "C:\python\Library\bin\tk86t.dll;." ^
  --add-binary "C:\python\Library\bin\libmpdec-4.dll;." ^
  --add-binary "C:\python\Library\bin\liblzma.dll;." ^
  --add-binary "C:\python\Library\bin\libbz2.dll;." ^
  --add-binary "C:\python\Library\bin\ffi-8.dll;." ^
  --add-binary "C:\python\Library\bin\libexpat.dll;." ^
  --add-data "C:\python\Library\lib\tcl8.6;tcl/tcl8.6" ^
  --add-data "C:\python\Library\lib\tk8.6;tk/tk8.6" ^
  price_calc_III.py
```

Note: The `--add-binary` flags are required when building from a Conda-based Python environment where Tcl/Tk and other DLLs are stored in non-standard locations.

## Limitations

- **Windows only** — Uses `ctypes.windll` for DPI awareness and `ImageGrab` for screen capture, both Windows-specific.
- **Single monitor assumed** — OCR capture coordinates may not behave correctly across multi-monitor setups with mixed scaling.
- **OCR accuracy** — Tesseract reads the screen image around your click. Dark themes, unusual fonts, overlapping UI elements, or low contrast can cause misreads. The app includes preprocessing (grayscale, upscaling, contrast/sharpness enhancement) and regex filtering to improve reliability, but OCR is inherently imperfect.
- **No broker integration** — This is a standalone calculator. It does not connect to any brokerage, place orders, or access account data.
- **Static R-multiples** — Targets are fixed R-multiples of the initial risk-per-share. They do not account for trailing stops or dynamic exits.

---

## Disclaimer

**This software is provided for educational and informational purposes only. It is not financial advice, and nothing in this application constitutes a recommendation to buy, sell, or hold any security.**

- Calculations are based on simple arithmetic (entry price, stop price, and share count). They **do not account for slippage, commissions, fees, spread, partial fills, or market impact**.
- OCR-based price reading is a convenience feature and is **not guaranteed to be accurate**. Always verify prices visually before acting on them.
- The authors and contributors of this software accept **no liability** for any trading losses, errors, or damages arising from the use of this tool.
- **Use at your own risk.** You are solely responsible for your own trading decisions.

