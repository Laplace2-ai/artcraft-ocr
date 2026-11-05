# THIRD-PARTY

Everything this program includes that was not written for it, and where the licence text lives.

The program itself is Apache-2.0 (`../LICENSE`). This folder ships beside the executable so the
notices travel with it; nothing here is needed at runtime.

## Runtime components

| Component | Version | Licence | Text in this folder |
|---|---|---|---|
| CPython | 3.13 | PSF-2.0 | `python-LICENSE.txt` |
| onnxruntime | 1.31.1 | MIT | `onnxruntime-LICENSE.txt`, `onnxruntime-ThirdPartyNotices.txt` |
| numpy | 2.5.4 | BSD-3-Clause | `numpy-LICENSE.txt` |
| opencv-python | 5.0.0.93 | Apache-2.0 | `opencv_python-LICENSE.txt`, `opencv_python-LICENSE-3RD-PARTY.txt` |
| Pillow | 13.0.0 | MIT-CMU | `pillow-LICENSE.txt` |
| rapidocr-onnxruntime | 1.2.3 | Apache-2.0 | **package ships none** — see note 1 |
| pywebview | 6.2.1 | BSD-3-Clause | `pywebview-LICENSE.txt` |
| pythonnet | 3.2.1 | MIT | `pythonnet-LICENSE.txt` |
| clr-loader | 0.3.1 | MIT | `clr_loader-LICENSE.txt` |
| flatbuffers | 25.12.19 | Apache-2.0 | `Apache-2.0.txt` |
| protobuf | 7.36.2 | BSD-3-Clause | `protobuf-LICENSE.txt` |
| pyclipper | 1.4.0 | MIT | `pyclipper-LICENSE.txt` |
| PyYAML | 6.0.3 | MIT | `pyyaml-LICENSE.txt` |
| Shapely | 2.2.0 | BSD-3-Clause | `shapely-LICENSE.txt` |
| six | 1.17.0 | MIT | `six-LICENSE.txt` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | `packaging-LICENSE.txt` |
| bottle | 0.13.4 | MIT | `bottle-LICENSE.txt` |
| proxy_tools | 0.1.0 | MIT | **package ships none** — see note 1 |
| cffi | 2.1.1 | MIT | `cffi-LICENSE.txt` |
| pycparser | 3.12 | BSD-3-Clause | `pycparser-LICENSE.txt` |
| typing_extensions | 4.16.0 | PSF-2.0 | `typing_extensions-LICENSE.txt` |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | `pywin32_ctypes-LICENSE.txt` |
| Tcl / Tk | 8.6 | BSD-style (Regents of the University of California et al.) | `tcl-tk-LICENSE.txt` |
| OpenSSL | 3.0.16 | Apache-2.0 | `Apache-2.0.txt` |
| libffi | 3.4 (bundled as `libffi-8.dll`) | MIT | **package ships none** — see note 1 |
| setuptools | bundled copy | MIT | **package ships none** — see note 1 |
| Microsoft Visual C++ runtime | `msvcp140.dll`, `vcruntime140.dll` | Microsoft redistributable | shipped as part of CPython's required runtime; no separate notice text |
| pefile | 2024.8.26 | MIT | `pefile-LICENSE.txt` (build-time only) |

Note 1 — `rapidocr-onnxruntime`, `proxy_tools`, `libffi` and the bundled `setuptools` copy
distribute no licence file with the build.
Their package metadata declares Apache-2.0 and MIT respectively; the Apache text is in
`Apache-2.0.txt`, and the MIT text is the standard one. This is recorded rather than papered over:
`DOCS/LICENSES.md` §7.1 raised it before release and the answer was to ship the declaration and
say so.

## Models

| File | Origin | Licence |
|---|---|---|
| `chinese_cht_PP-OCRv3_rec_mobile.onnx` | PaddleOCR, converted for onnxruntime | Apache-2.0 |

The Simplified Chinese and English recognisers ship inside `rapidocr-onnxruntime` and are covered
by its entry above.

## Data

| File | Origin | Licence |
|---|---|---|
| `CORE/data/STCharacters.txt`, `TSCharacters.txt` | OpenCC (`STCharacters` / `TSCharacters`) | Apache-2.0 |

## Not included

- **No font file ships.** The program asks the system for a UI font and passes a font *name* to the
  host application; neither is a redistributed file.
- **No ffmpeg / `opencv_videoio_ffmpeg*.dll`.** The build excludes it; recognition does not decode
  video.
- **No ArtCraft brand assets.** The icon and wordmark are trademarks of the project owner and are
  not covered by the code licence.
- **No telemetry and no network calls.** Recognition and conversion run in-process.
