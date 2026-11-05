# PACKAGING

> What a build has to do, and the two places it silently breaks. Both were hit for real on
> 2026-11-02 while proving the pipeline; neither is visible from a development environment.

Target: Windows, PyInstaller **onedir**, UPX off. One directory, not a single file — startup
time and antivirus behaviour both matter more than the convenience of one file.

## Measured reference point

| Property | Value | Conditions |
|---|---|---|
| Bundle size | **211 MB** | rapidocr-onnxruntime 1.2.3, Pillow 13.0.0, onnxruntime, opencv-python, pywebview 6.2.1 + pythonnet, no FFmpeg DLL, no UPX |
| Model files in bundle | 3 ONNX | under `_internal/rapidocr_onnxruntime/models/` |
| Recognition after packaging | works | `--selftest` inside the built exe: 7 lines → 3 paragraphs, 1.3 s, identical to running from source |

The traditional model for Chinese is **not** in that count when it is vendored separately —
add it and its checksum from `LICENSES.md` §5.

## Pitfall 1 — rapidocr imports its stages by short name

**Symptom.** The packaged app dies on startup:

```
AttributeError: module 'ch_ppocr_v3_det' has no attribute 'TextDetector'
```

**Cause.** `rapidocr_onnxruntime/rapid_ocr_api.py` appends its own package directory to
`sys.path` (line 17) and then calls `importlib.import_module("ch_ppocr_v3_det")` — an
unqualified name. Unfrozen that works, because the directory is on disk with `.py` files in it.
Frozen, the sources live inside the PYZ, so what remains on disk is a directory with no code:
Python imports it as an **empty namespace package**. The import succeeds, the attribute does not
exist, and the error points at the consumer rather than the cause.

**Fix, both halves required.** Bundling the subpackages is not enough, because the runtime name
is still unqualified:

1. In the spec, add them to `hiddenimports`:
   `rapidocr_onnxruntime.ch_ppocr_v3_det`, `rapidocr_onnxruntime.ch_ppocr_v3_rec`,
   `rapidocr_onnxruntime.ch_ppocr_v2_cls`.
2. In the entry point, alias the short names onto the real modules before constructing
   `RapidOCR()`:

```python
import sys
import rapidocr_onnxruntime.ch_ppocr_v3_det as _det
sys.modules["ch_ppocr_v3_det"] = _det
# …same for _rec and _cls
```

Do this in one place, early, and comment why. Anyone who "cleans up" the alias will reintroduce
a crash that only appears after packaging.

## Pitfall 2 — opencv-python ships an FFmpeg DLL

`opencv-python` puts `opencv_videoio_ffmpeg500_64.dll` in `cv2/`, and its own
`LICENSE-3RD-PARTY.txt:243` says FFmpeg is redistributed in every wheel. That DLL drags LGPL
obligations into the product for a code path this project never uses.

The exclusion cannot be done by pruning submodules — `cv2.pyd` is one monolithic binary. Filter
the collected binaries instead:

```python
a.binaries = [b for b in a.binaries if "ffmpeg" not in b[0].lower()]
```

Verify with `find dist -iname "*ffmpeg*"` returning nothing, then run recognition: the point is
that dropping it changes nothing. `LICENSES.md` §7.2 has the measurement showing the DLL is
never loaded during recognition, and states what that measurement does not cover.

## Verifying a build

The four checks that actually caught something, in the order they caught it:

1. Does the packaged binary start at all? (pitfall 1 appears here, nowhere earlier)
2. `find dist -iname "*ffmpeg*"` empty, and recognition still works (pitfall 2)
3. Are the model files inside the bundle, at the path the code expects
4. Record the bundle size — a jump of tens of MB usually means a dependency crept in

Do not record "works" as a result. Record the lines recognised, the exit code, and the size,
so a later build can be compared rather than trusted.

## Pitfall 3 — pywebview fails to install, and it is not a Python 3.13 problem

**Symptom.** `pip install pywebview` dies while installing build dependencies for
`proxy_tools`, with `IncompleteRead(...)` from the package index. It looks like the package does
not support the interpreter.

**Cause.** Build isolation spins up a subprocess that fetches its own build requirements. On a
flaky or mirrored index that download can truncate, and the error surfaces as a build failure of
an unrelated tiny package.

**Fix.** Install that one dependency without isolation first, then the rest:

```sh
python -m pip install --no-build-isolation proxy_tools
python -m pip install --no-build-isolation pywebview
```

**Verified configuration** (2026-11-02, Windows, Python 3.13.3):

| Piece | Version / state |
|---|---|
| WebView2 runtime (Edge WebView) | present, 156.x |
| pywebview | 6.2.1 |
| pythonnet | 3.2.1 — `import clr` OK |
| WinForms backend | importable |

Record this before changing the UI stack: the first failure looks exactly like an
unsupported-interpreter error and invites a rewrite that is not needed.

**Ship-time check.** The WebView2 runtime is present by default on Windows 10 and 11, but not
guaranteed (LTSC, Server, stripped images). The application must detect it and exit with one
readable line, not a stack trace. Add that check to the build verification list.

## Verifying a build without a human

The interface cannot be clicked from a script, but the risky half can be:

```sh
ArtCraftOCR.exe --selftest <image> <out.json>
```

It loads the recogniser inside the frozen process and writes the outcome to a file
(stdout is not available in a windowed build). Exit code 0 means the engine came up.

This is the check that matters: every packaging failure found on this project so far
— the short-name imports, a missing model, the FFmpeg exclusion — only appears at
runtime, and two of the three would look like "nothing happens" to a user.
