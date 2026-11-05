# HANDOVER

State of ARTCRAFT_OCR for whoever picks this up next. Read this first, then
`DOCS/HOST_API.md` and `DOCS/UI_SPEC.md` — those carry the measured facts.

Last updated: 2026-11-04 · version 1.0.0 · 81 unit tests + 1 interface check, all green.

## What this is

A desktop tool that recognises text in an image or a screen region and places it
into a host editing application as real text layers, one group per import.

Python for the engine, HTML/CSS in a WebView for the interface. No network at
runtime; images never leave the machine.

## Shape of the repository

| Path | What lives there |
|---|---|
| `CORE/` | host-agnostic engine: lines, paragraphs, ink colour, size, edit alignment, conversion. No OCR library, no toolkit. |
| `ADAPTERS/` | rapidocr backend and the PhotoCraft writer. The only place third-party services are touched. |
| `APP/` | desktop shell: pywebview window, the HTML interface, the region overlay. |
| `PACKAGING/` | PyInstaller spec. `dist`/`out` are build output and ignored. |
| `DOCS/` | the audit, the interface spec, measured host behaviour, the release checklist. |
| `TESTS/` | 46 unit tests, plus `check_ui.py` which clicks the real page. |

## Running it

```sh
python APP/main.py                      # from the repository root
python -m unittest discover -s TESTS    # engine and adapter behaviour
python TESTS/check_ui.py                # interface: parses, and the controls respond
```

Build (output is a folder, not an installer):

```sh
python -m PyInstaller --clean --noconfirm \
    --distpath PACKAGING/out --workpath PACKAGING/build2 \
    PACKAGING/artcraft-ocr.spec
```

Then `PACKAGING/out/ArtCraftOCR/ArtCraftOCR.exe`. Its `--selftest <image> <out.json>`
runs the recogniser inside the built executable and writes the result to a file —
that is the only way to verify a frozen build, since the interesting failures
(short-name imports, missing weights, excluded binaries) all appear at runtime.

## Decisions worth not re-litigating

Each of these cost something to learn; the reasoning is in the linked document.

| Decision | Why | Where |
|---|---|---|
| HTML in a WebView, not tkinter | the brand stylesheet is CSS, and the visual ambition exceeds what ttk can draw | `DOCS/UI_SPEC.md` §0 |
| Region overlay is a toolkit window | a WebView window never covered the desktop; the selection would have been made blind | `APP/overlay.py` |
| Bounds are a `Box`, never a list | the host returns two different array layouts for the same layer, and the wrong one silently scales the font | `DOCS/HOST_API.md` |
| 点文字 = one layer per line | point text means a line; treating a paragraph as one block shrank 138pt to 44pt | `ADAPTERS/photocraft.py` |
| Font size comes from the line box height alone — 1.18 × for CJK, 0.93 × for Latin, both measured | the box is the *line* box, not the ink; and the box is loose in width too, so fitting to it turned 28 pt into 38 pt | `CORE/metrics.py` |
| Geometry follows the line's text, not its position in the list | inserting or deleting a paragraph shifted every later line onto the wrong box | `CORE/plan.py` |
| No layer is ever deleted on failure | a partial write is reported; deleting is the user's decision, and a duplicate is visible while a silent deletion is not | same file |
| Apache-2.0, single licence | patent grant and redistribution are wanted; dual licensing is not | `LICENSES.md` §1 |
| Icon is the letter A on a 16×16 grid, open (no crossbar) | chosen from a size comparison; the crossbar version was offered and declined | `DOCS/UI_SPEC.md` §7 |

## Known limitations, honestly

- **Short text can be missed.** A one- or two-character line on a large image is
  below the detector's floor. Cropping tight makes the image small, which triggers
  the enlargement path and usually works. This is a model constraint, not a bug
  waiting to be fixed here.
- **Sizes assume the host document is at 100% zoom.** At other zoom levels the
  screenshot's pixels are not the document's pixels. The 框选截图 button carries a
  tooltip saying so; nothing on this side can correct it.
- **A manually started host has no control channel.** It only exists when the
  process is started with the parameters, so the app writes `photocraft_OCR.bat`
  beside the executable and the user launches from there.
- **The window lands where the platform decides.** `create_window(x=, y=)`,
  `window.move()` and `window.maximize()` are all accepted and ignored on this
  backend.
- **Group counters live in `settings.json`** beside the executable; delete the file
  and names restart at `OCRtext01`.

## Open items

| # | Item | Notes |
|---|---|---|
| 1 | FilmCraft target | SRT import, original timing preserved, no auto-wrap |
| 2 | VectorCraft target | paragraph text needs `area:{width, fit:"autoHeight"}` |
| 3 | Installer or portable zip | current output is an unsigned folder; SmartScreen will warn |
| 4 | Bilingual interface | the page is Chinese-only; the repository is English |

## Working agreements that outlive this session

- Reuse before rewriting, and if rewriting, the reason is one of: missing
  capability, incompatible architecture, dependency conflict, licence restriction.
  "Different interface" is not a reason — adapting interfaces is what an adapter
  is for.
- If code is lifted from the internal implementation, `NOTICE` and `LICENSES.md`
  change **in the same commit**. The two states cannot coexist.
- Every conclusion in `DOCS/` cites a measurement or a file:line. Anything that
  cannot be evidenced does not belong there.
