# CHANGELOG

Newest first. Written by hand; the version here and the version in the window title are the
same string.

## 1.0.1 — 2026-11-06

- **Fixed: Help → About did nothing.** The menu called `openAbout()`, and that function had never
  been written — the dialog markup and the Python side were both there, so the click threw
  `ReferenceError: openAbout is not defined`. Now opens and closes (×, backdrop, Esc), the version
  is read from the program, GitHub opens the repository, License and Notices open the shipped files.
- The interface check now clicks Help → About and asserts the panel opens and closes. It was renamed
  to a no-op function as a negative control: the check fails, as it should.
- Docs: the 100 % view-scale requirement is now a callout where the capture step is described,
  not a line inside "known limits". FilmCraft and VectorCraft are marked *coming soon*.

## 1.0.0 — 2026-11-04

First release.

**Text recognition**

- Local recognition with RapidOCR; no network at runtime, no image leaves the machine.
- Simplified, Traditional and English. The traditional model ships as a separate weight.
- Paragraph grouping, per-line ink colour, and a size estimate taken from each line's box
  height (1.18 × for CJK, 0.93 × for all-caps Latin, both measured against the recogniser).

**Writing into PhotoCraft**

- Point text: one layer per line, placed on the recognised box.
- Area text: one frame per paragraph, grown downwards to hold its lines.
- Per-paragraph colour and size, editable in the result pane; the top bar no longer offers a
  size list, because a list can never match a recognised 13 or 15.
- Each import becomes one group (`OCRtext01`, `OCRtext02`, …), so an import stays separable
  from the user's own layers.
- Nothing is deleted on failure: a partial write is reported per block.

**Files**

- Open Image accepts PSD (the flattened composite) alongside PNG, JPEG, WebP, BMP and TIFF, so the
  file PhotoCraft saves can be recognised directly.
- 刷新 / Refresh re-reads the current file from disk. Unchanged text stays where it is; the blocks
  are cleared, because the picture underneath is what changed.

**Interface**

- HTML/CSS in a WebView. English on first run; the choice is saved in `settings.json`.
- Undo/redo over the last ten pictures — cropping replaces the image on drop, so a wrong
  drag used to cost a re-capture.
- Paste is plain text only: source formatting used to arrive as a black box and as broken
  line breaks.

**Text conversion**

- One Simplified ↔ Traditional button that alternates direction on each press (OpenCC tables,
  local).
- No machine translation ships. Two builds of Haidass-Translate-143M were measured — int8 and
  fp32 — and neither is good enough to put in front of a user: both invent details, and the fp32
  build turned "November 8 to March 1" into "11月8日至1月1日". Four times the download for a
  worse answer. The JSON round trip is the documented path instead.

**Export / import**

- File → Export Text Data (JSON): text, boxes in pixels and as fractions, alignment, colour,
  size, per-line scores. Geometry is dropped for lines whose text was edited.
- File → Import Text Data (JSON) puts text back into the blocks already on screen, by index.
  The intended loop is: recognise here, translate elsewhere, import, write.

**Known limits**

- Short text (one or two characters) on a large image can be missed; cropping tight usually
  recovers it.
- Sizes assume the host document is at 100 % zoom. At other zoom levels the screenshot's
  pixels are not the document's pixels, and nothing on this side can correct it.
- A host started by hand has no control channel; use the generated `photocraft_OCR.bat`.
- The window lands where the platform decides: position arguments are accepted and ignored.
- The build is unsigned, so Windows SmartScreen warns on first run.
