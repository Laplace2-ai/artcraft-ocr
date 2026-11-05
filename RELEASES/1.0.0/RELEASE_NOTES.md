# ArtCraft OCR 1.0.0

First public release.

**Download:** `ArtCraftOCR-1.0.0-win64.zip` (101.8 MB) — unzip anywhere, run `ArtCraftOCR.exe`.

SHA-256: see `SHA256SUMS.txt`.

## What it does

Reads text from an image and writes it back into PhotoCraft as real text layers. Everything runs
locally: no account, no upload, no network.

- Simplified Chinese, Traditional Chinese and English recognition.
- The result is editable before it is written: a blank line starts a new block, `+` / `×` add
  and remove blocks, colour and size can be changed per block.
- Two write modes: **point text** (one layer per line, on the position and size the original had)
  or **area text** (one text frame per block).
- Simplified ↔ Traditional is one alternating button, local and instant.
- Export the whole result as JSON, translate or rewrite it anywhere, import it back — the
  recommended way to translate. No machine translation is bundled: the 143M models we measured
  invented details and mangled dates.

## Requirements

- Windows 10 or 11, 64-bit. The Python runtime is inside the package — nothing to install.
- WebView2 runtime (built into Windows 11; on Windows 10 it comes with Edge).
- PhotoCraft for the write step; recognition, editing and export work without it.

## First run

1. **File → Settings…** → **Choose photocraft.exe…**
2. **Create photocraft_OCR.bat in the program folder**
3. Start PhotoCraft with that bat, then write from here.

PhotoCraft started by double-clicking `photocraft.exe` has no control channel, so nothing can
write to it. The script is what makes that visible.

## Unsigned build

There is no code signing certificate, so SmartScreen shows "Windows protected your PC" on first
run. **More info → Run anyway.** The source for this build is in this repository.

## Known limits

- Short text (one or two characters) on a big image can be missed; crop tighter to recover it.
- Font sizes assume the PhotoCraft document is at 100 % zoom.
- The window position is chosen by the platform.
- PhotoCraft is the only host with an adapter. FilmCraft and VectorCraft are planned.

## Notices

Source: Apache-2.0 (`LICENSE`). Third-party components and their licence texts travel with the
download in `THIRD-PARTY/`.
