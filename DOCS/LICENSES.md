# LICENSES — third-party assets, and what may ship

> Owner: the release maintainer. **No file enters the published repo until its row here is filled.**
> Every conclusion quotes a source (file path / URL + clause), never memory.
> Audit date: 2026-11-02. Each reference was opened and read on that date; the version or
> commit cited is the version the conclusion applies to.

> ## The Apache-2.0 license in `LICENSE` covers this project's own source code only.
>
> It grants no rights to any third-party asset — not to model weights, not to Python
> dependencies, not to fonts, not to the host applications. Each object below is licensed on
> its own terms, and a build may only ship it if that object's own row says so.

**Baseline:** the project license was decided on 2026-11-02 — **Apache-2.0, single license, no
MIT, no dual licensing** (decided by the project owner). Nothing in the dependency chain is copyleft, so nothing blocks
release. Three items still need an action before the first public release; see §8.

---

## 0. Object checklist

The six objects that must each be cleared separately, and where the answer is:

| Object | Verdict | § |
|---|---|---|
| Our OCR source code | **Apache-2.0** — decided | §1 |
| Host applications and their control channel | **Cleared** — we are an external client, not a plugin | §2 |
| OCR model weights | **Cleared for commercial use** — Apache-2.0 is the only grant that exists | §3 |
| Python dependencies | **Cleared** — all permissive, no copyleft | §4 |
| Model download source | **No runtime download** — weights pinned by checksum at build time | §5 |
| Fonts | **OFL-1.1 bundled font**, system font never redistributed | §6 |

---

## 1. Our own source code

| Part | License | Decided by | Date |
|---|---|---|---|
| `CORE/` + `ADAPTERS/` + `TESTS/` | **Apache-2.0** (SPDX: `Apache-2.0`) | project owner | 2026-11-02 |

Conventions that follow from the decision, applied to every source file as it is written:

- Every source file carries `SPDX-License-Identifier: Apache-2.0` in its header.
- `LICENSE` at the repo root holds the unmodified Apache-2.0 text (terms, §1–9, plus the
  appendix). It is canonical text — do not edit it, do not add a project name into it.
- `NOTICE` holds the project copyright line and nothing invented. Per Apache-2.0 §4(d) we only
  propagate attribution notices that a redistributed component actually carries; none does, so
  `NOTICE` says so rather than manufacturing entries.
- `README.md` states the license and points at this file for everything that is not ours.

Apache-2.0 was chosen over MIT for the express patent grant (§3) and the patent-litigation
termination clause. It permits commercial use and redistribution, which is the stated goal.

### 1.1 Code derived from the internal implementation

| Part | Origin | What changed | License |
|---|---|---|---|
| `CORE/textdata.py` | the rights holder's internal OCR tool, read 2026-11-03 | rewritten to this repository's model; schema id namespaced for publication; per-line geometry is dropped when the edited text no longer matches the recognised line | Apache-2.0 — same rights holder, no third-party obligation |

The internal tool is the same rights holder's work, so lifting code from it creates no
licensing question — but it does create a record-keeping one. **`NOTICE` and this table change
in the same commit as the code**, because the alternative is a repository that says it
contains no shared code while one of its files does, and the claim that survives is whichever
nobody re-read.

A derived file names its origin in its header (source, date read, what differs), so a reader
can tell an adaptation from an original without asking.

---

## 2. Host applications and their control channel

| App | Version tested | License | Third-party client allowed? | Source / clause |
|---|---|---|---|---|
| PhotoCraft | 0.20.2 (re-verified 2026-11-05: NOTICE still reads MIT OR Apache-2.0; LICENSE-MIT and LICENSE-APACHE present) | **MIT OR Apache-2.0** | **Yes** — explicitly | `ArtCraft/photocraft/NOTICE:2-4`; `README.md:437`; `LICENSE-MIT`, `LICENSE-APACHE` present |
| FilmCraft | 0.15.0 | **MIT OR Apache-2.0** | **Yes** — explicitly | `ArtCraft/filmcraft/NOTICE:2-4`; `README.md:233` |
| EffectCraft | 0.19.0 | **MIT OR Apache-2.0** | Yes | `ArtCraft/effectcraft/NOTICE:2-4` |
| VectorCraft | 0.19.0 | **MIT OR Apache-2.0** | Yes | `ArtCraft/vectorcraft/NOTICE:2-4` |

Quoted clause (identical in all four `NOTICE` files):

> Licensed under the MIT License or the Apache License, Version 2.0, at your option.

### 2.1 We are not a plugin, and there is no plugin SDK to check

An earlier version of this audit was framed as "do the apps allow third-party plugins". That
question has no object: **none of these apps has a plugin interface.**

| App | Plugin surface | Evidence |
|---|---|---|
| PhotoCraft | none — listed as a *gap* | `photocraft/README.md:312`: "The biggest gaps are … and **plug-in compatibility**." |
| FilmCraft | none | `filmcraft/README.md:303`: "**No plugins.** No VST3 / Audio Units or OpenFX hosting." |
| EffectCraft | After Effects SDK only, unsupported | `effectcraft/README.md:239`: "…and After Effects SDK plug-ins are not supported." |
| VectorCraft | none stated | no plugin section in `vectorcraft/README.md` |

There is therefore **no separate SDK or API agreement to accept, and no additional terms beyond
the app license itself.** What we build is a separate executable that drives the app through its
documented local control channel (`--control` + `<app>-cli mcp --bridge`, or the stdio MCP
server). The host publishes that channel as the intended integration route and endorses agent
control:

- `photocraft/README.md:249` — "The desktop app also offers an authenticated, loopback-only
  control channel (`photocraft --control`) for inspecting UI state, driving tools with pointer
  events, and taking offscreen screenshots." (protocol documented in `docs/control-protocol.md`)
- `photocraft/README.md:230` — "anything you can click, a script or an AI agent can do too."
- `filmcraft/README.md:233` — "a JSON control channel and an **MCP server** … so Claude or any
  agent can cut, trim, grade, mix and export exactly the way a person does."

Consequences, all favourable:

1. We create no derivative work of the host, so the host's license is not the operative
   constraint on our code.
2. We ship no host binary, so there is no redistribution question at all.
3. Even the conservative reading is safe: MIT and Apache-2.0 both permit third-party clients,
   forking, and commercial distribution, so no clause had to be "found" to clear this.
4. No EULA, terms of service, or usage restriction exists in any of the four packages. Grepped
   all four `README.md`, `NOTICE`, `portable.txt` for `EULA|terms of|restrict|prohibit`: zero
   hits other than FilmCraft's "No plugins" line, which describes capability, not permission.

### 2.2 What IS restricted: the trademarks

The one real host-side constraint, and it is a **branding** rule, not a license rule.

- `photocraft/NOTICE:6-8` — "The ArtCraft name, wordmark and logos in docs/brand/ are
  trademarks of the ArtCraft Team. They are not open source and are not covered by the license
  above."
- `photocraft/README.md:445-448` — "They may be used only unmodified, and only as part of this
  repository and PhotoCraft … **Forks and modified versions must remove them.**"

| Do | Don't |
|---|---|
| Say "works with PhotoCraft" — a factual compatibility statement | Use the ArtCraft wordmark, the kitsune app icon, or any file from `docs/brand/` in our UI, README, installer or store page |
| Name the app we talk to | Imply the ArtCraft Team endorses, sponsors or maintains us |
| Use our own name and icon | Ship their brand assets "unmodified" and argue the clause covers us — it only covers copies inside their own repo |

Inherited from `photocraft/README.md:450`: the Adobe disclaimer. If our README mentions
Photoshop or After Effects compatibility, it needs the same kind of "not affiliated with Adobe"
sentence.

---

## 3. OCR model weights

Weights are **not** committed here. `MODELS/` carries download source and checksum only.

| Model | Role | Source | License | Redistribution |
|---|---|---|---|---|
| `ch_PP-OCRv3_det_infer.onnx` | text detection | bundled in `rapidocr-onnxruntime` 1.2.3 | Apache-2.0 (PaddleOCR) | Yes |
| `ch_PP-OCRv3_rec_infer.onnx` | simplified Chinese recognition | same | Apache-2.0 (PaddleOCR) | Yes |
| `ch_ppocr_mobile_v2.0_cls_infer.onnx` | 0°/180° orientation | same | Apache-2.0 (PaddleOCR) | Yes |
| `chinese_cht_PP-OCRv3_rec_mobile.onnx` | traditional Chinese recognition | ModelScope `RapidAI/RapidOCR`, path `onnx/PP-OCRv4/rec/` | Apache-2.0 (RapidOCR repo) | Yes |

**Evidence, and its limits.** This is the object the project owner singled out, so the reasoning is spelled
out rather than asserted:

- PaddleOCR's official documentation states the project license covers the release, models
  included: "本项目的发布受 Apache 2.0 license 许可认证"
  (<https://paddlepaddle.github.io/PaddleOCR/v2.10.0>).
- RapidOCR — the actual distributor of the wheel and of the `chinese_cht` weight — is
  Apache-2.0 (`rapidocr_onnxruntime-1.2.3.dist-info/METADATA`: `License: Apache-2.0`,
  Home-page <https://github.com/RapidAI/RapidOCR>). The wheel redistributes all four weights
  inside an Apache-2.0 package, which is the operative grant for what we install.
- **There is no separate weights EULA to cite for any of the four.** Apache-2.0 is the only
  grant that exists, applied by the publisher. That is the basis every commercial PaddleOCR
  deployment relies on, and it is why "the code is Apache-2.0" and "the weights are Apache-2.0"
  are two conclusions rather than one.

Residual risks, recorded rather than hidden:

| # | Risk | Severity | Handling |
|---|---|---|---|
| M1 | Training data for PP-OCRv3 is undisclosed; we rely on the publisher's grant, not a chain of title | Low | Accept. Note it in the README's third-party section. |
| M2 | The `chinese_cht` file sits under an `onnx/PP-OCRv4/` path but is named `PP-OCRv3` — provenance is ambiguous by name alone | Low | Pin the exact commit/tag in §5. Ship what the checksum says, not what the filename says. |
| M3 | No upstream will sign an indemnity | Low | Posture is "AS IS", already implied by Apache-2.0. Do not promise indemnity in our terms. |

### 3.1 Character-conversion tables

| File | Source | License | Evidence |
|---|---|---|---|
| `STCharacters.txt` | opencc-python-reimplemented 0.1.7, `opencc/dictionary/` | Apache-2.0 | wheel `LICENSE.txt` is the Apache-2.0 text; the data files themselves carry **no** header in this distribution |
| `TSCharacters.txt` | same wheel | Apache-2.0 | same — no per-file header |

These files carry **no license header of their own** in the wheel they come from, so nothing is
satisfied by shipping them "as-is": the Apache-2.0 text has to ship alongside. `CORE/data/README.txt`
records the source and says not to edit them; the tests assert behaviour these exact tables
produce, so an edit would be caught but would also be a fork.

---

## 4. Python dependencies

Read from installed distribution metadata (`importlib.metadata`) in the dev venv on 2026-11-02.
**No GPL, LGPL or AGPL anywhere in the tree.**

| Package | Version | License | Commercial | Obligation when bundling |
|---|---|---|---|---|
| rapidocr-onnxruntime | 1.2.3 | Apache-2.0 | Yes | **ships no LICENSE file** — we must add the text; see §7.1 |
| onnxruntime | 1.31.1 | MIT | Yes | ship `onnxruntime/LICENSE` + `onnxruntime/ThirdPartyNotices.txt` |
| opencv-python | 5.0.0.93 | Apache-2.0 | Yes | ship `cv2/LICENSE.txt` + `cv2/LICENSE-3RD-PARTY.txt`, **minus FFmpeg**; see §7.2 |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Yes | attribution only |
| pillow | 13.0.0 | MIT-CMU | Yes | attribution only |
| shapely | 2.2.0 | BSD-3-Clause | Yes | attribution only |
| pyclipper | 1.4.0 | MIT | Yes | attribution only |
| protobuf | 7.36.2 | BSD-3-Clause | Yes | attribution only |
| flatbuffers | 25.12.19 | Apache-2.0 | Yes | attribution only |
| PyYAML | 6.0.3 | MIT | Yes | attribution only |
| six | 1.17.0 | MIT | Yes | attribution only |
| packaging / urllib3 | 26.3 / 2.8.0 | Apache-2.0 OR BSD-2.0 / MIT | Yes | attribution only |
| pyperclip | 1.11.0 | BSD | Yes | **unused — must not be bundled** |

`pip` appears in the venv only because the venv built itself. It is not a runtime dependency and
must not be bundled.

---

### 4.1 Native runtimes the interpreter brings

PyInstaller collects what CPython itself links against, and those are shipped inside the package
without ever appearing in a `requirements.txt`:

| Component | Where it comes from | Licence | Notice |
|---|---|---|---|
| Tcl / Tk 8.6 | `tcl86t.dll`, `tk86t.dll`, `_tcl_data/` | BSD-style | `THIRD-PARTY/tcl-tk-LICENSE.txt` |
| OpenSSL 3.0.16 | `libcrypto-3.dll`, `libssl-3.dll` | Apache-2.0 | `THIRD-PARTY/Apache-2.0.txt` |
| libffi | `libffi-8.dll` | MIT | declared only; the wheel ships no text |
| setuptools | `_internal/setuptools/` | MIT | declared only; the installed copy ships no text |
| MSVC runtime | `msvcp140.dll`, `vcruntime140.dll` | Microsoft redistributable | no separate notice required |

Checked 2026-11-05 by listing `_internal/` against this audit — this row set was missing until
then, which is exactly the kind of gap a `pip freeze` audit cannot see.

## 5. Model download source

| Question | Answer |
|---|---|
| Does the app download weights at runtime? | **No.** All four weights ship inside the distribution. The product is offline by design. |
| Is redistribution of the weights permitted? | Yes — Apache-2.0, per §3. |
| Is automatic download permitted? | Moot, and deliberately not used. A runtime downloader would put a network call and a license hand-off in the user's path for no benefit. |
| Where do the bytes come from? | Build time only, from the pinned sources below, verified against these checksums before anything is packaged. |

Checksums as installed on 2026-11-02 — these are what `MODELS/` must pin:

```
779656d044ce388045e02ea9244724616194e63928606436cdfc6dc3c9528cc6  chinese_cht_PP-OCRv3_rec_mobile.onnx
3439588c030faea393a54515f51e983d8e155b19a2e8aba7891934c1cf0de526  ch_PP-OCRv3_det_infer.onnx
897a3ededb38fee0dae2c1ccee38241f37df202c9509e3abca02e9217c5ee615  ch_PP-OCRv3_rec_infer.onnx
e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c  ch_ppocr_mobile_v2.0_cls_infer.onnx
```

Open item M2: the `chinese_cht` entry still needs a commit or tag, not just a path, before the
download script is written.

---

## 6. Fonts

| Use | Decision | License |
|---|---|---|
| UI and inserted-text default | **Noto Sans SC** — bundled | **OFL-1.1** |
| System CJK fallback | read at runtime, **never bundled** | — |

**Why bundle one at all:** OCR does not recover the source font, so we substitute. If we
substitute a system font, the same document lands differently on every machine, and the default
differs between a Chinese Windows install and an English one. A bundled font makes insertion
reproducible, which is the whole point of the feature.

**Why Noto Sans SC:** OFL-1.1 explicitly permits bundling inside a larger work — its preamble
says the fonts "can be bundled, embedded, redistributed and/or sold with any software provided
that any reserved names are not used by derivative works" (`OFL-noto-sans-cjk-sc.txt:20-32`,
shipped by the host apps). It is also the same family the host applications already ship, so the
attribution pattern is established in this family rather than invented here.

OFL-1.1 obligations we accept:

- Ship the OFL text **as distributed with the font file**, which carries the copyright
  statement — not a generic copy. The file the host apps ship (`OFL-noto-sans-cjk-sc.txt`) is
  the bare licence text with no copyright line, so it is not sufficient on its own; take ours
  from the font package itself.
- Do not sell the font on its own, and do not imply it is ours.
- If we subset or otherwise modify it, the result still ships under OFL-1.1. **Subsetting is a
  modification**, so whether we may keep the name depends on the font's own Reserved Font Name
  declaration — check it when vendoring, and rename the family if one is declared. Record the
  answer in `THIRD-PARTY/README.md`, not here.

What we still must not do, unchanged from the earlier audit: **never redistribute a Windows
system font.** Bundling `Microsoft YaHei` is a redistribution we have no right to make. Calling
it at runtime as a *fallback* is fine and is not redistribution.

---

## 7. Obligations this audit creates

### 7.1 `rapidocr-onnxruntime` ships no license file

Its `dist-info` contains `INSTALLER`, `METADATA`, `RECORD`, `REQUESTED`, `WHEEL`,
`entry_points.txt`, `top_level.txt` — and no `LICENSE`. Apache-2.0 §4(a) requires us to give
recipients a copy of the license, so "it was already in the wheel" is not a defence.

Fix: `THIRD-PARTY/` carries `Apache-2.0.txt`, and the release lists
`rapidocr-onnxruntime 1.2.3 — Apache-2.0 — https://github.com/RapidAI/RapidOCR` as a covered
component. Same for the four weights, since they arrive through that package.

### 7.2 Drop the bundled FFmpeg DLL from the build

`opencv-python` ships `cv2/opencv_videoio_ffmpeg500_64.dll`, and `cv2/LICENSE-3RD-PARTY.txt:243`
states: "FFmpeg is redistributed within all opencv-python packages." Those FFmpeg builds pull in
LGPL components, and LGPL on a shipped binary means written-offer/source-availability
obligations we do not want.

We never touch video I/O — our code imports `numpy` and `PIL`, not `cv2`; `cv2` is reached only
through rapidocr's image path. And that path is narrower than it looks: verified on 2026-11-02,
**rapidocr calls no codec at runtime.**

| Claim | Evidence |
|---|---|
| No video I/O at all | `grep -rn "VideoCapture\|VideoWriter" rapidocr_onnxruntime/` — 0 hits |
| No `imread` at runtime | all three are inside `if __name__ == "__main__":` blocks (`text_detect.py:129/139`, `text_recognize.py:103/112`, `text_cls.py:99/109`) |
| No `imdecode` at runtime | `ch_ppocr_v3_det/utils.py:43` lives in `DecodeImage`, which the hardcoded `pre_process_list` in `text_detect.py:29-45` never instantiates — it lists only `DetResizeForTest / NormalizeImage / ToCHWImage / KeepKeys` |
| Decoding is PIL's | `utils.py:114-126` `load_img()` — `Image.open()` for paths and bytes; ndarrays pass through untouched |

Runtime cv2 surface, then, is only `resize`, `cvtColor`, `getPerspectiveTransform`,
`warpPerspective`, `split/merge/bitwise_*/add` — all imgproc/core.

**Runtime confirmation (2026-11-02).** The source-level argument was checked against a live
process: load the engine, recognise three sample images (simplified, traditional, colour), then
enumerate the process's loaded modules with `CreateToolhelp32Snapshot`.

| Stage | FFmpeg DLL loaded? |
|---|---|
| interpreter start | no |
| after `RapidOCR()` | no |
| after recognising all three samples | no |

Only `cv2.pyd` appears among the cv2 modules (80 loaded in total). A library that is never
loaded is not a dependency, so this is stronger evidence than the grep: it is the same claim,
measured instead of read.

What it does not prove: that no code path *ever* loads it. Our three entry points are paste,
open file and screen capture — all images. If a video path is ever added, re-run this check.

So: **exclude the DLL in the PyInstaller spec** and verify OCR still runs, then the 3,617-line
third-party file reduces to attribution only. Note the exclusion cannot be done by pruning
submodules — `cv2.pyd` is one monolithic binary, so the win here is purely legal (the LGPL
notice obligation), not size.

One trap when testing this: do **not** claim the RGBA path was exercised. `utils.py:130-141`
`cvt_four_to_three` splits and re-composites alpha in cv2, but our engine flattens first
(`ocr_engine.py:71` does `image.convert("RGB")`) and `load_img()` returns ndarrays untouched, so
that branch is unreachable from our code. An alpha PNG is still worth a test as a *user-path*
regression, but it proves nothing about cv2.

### 7.3 Notices bundle

Minimum set to ship in `THIRD-PARTY/` next to the binary:

- `Apache-2.0.txt` (rapidocr, PaddleOCR weights, OpenCC tables, opencv, flatbuffers, packaging)
- `onnxruntime-LICENSE.txt` + `onnxruntime-ThirdPartyNotices.txt`
- `opencv-LICENSE.txt` + `opencv-LICENSE-3RD-PARTY.txt` (with §7.2 landed the third-party file
  is attribution-only, but ship it anyway — dropping it would be a claim we cannot make)
- `OpenCC-LICENSE.txt`
- `OFL-NotoSansSC.txt`
- MIT text (onnxruntime, pyclipper, PyYAML, six, urllib3, Pillow's MIT-CMU)
- BSD-3-Clause text (numpy, shapely, protobuf)
- A `THIRD-PARTY/README.md` table naming every row of §4 and §3 with version and URL

### 7.4 Must not reach the release tree

- Any ArtCraft brand asset (§2.2), including the app icon.
- Any bundled Windows system font (§6).
- `pyperclip` (unused).
- `dev/` scripts and `*.bat` (internal paths), per the handoff. Note: the `.bat` is not simply
  deleted — its function moves into the app. The release build starts the host itself, choosing
  a free control port and a token file inside our own data directory, so neither the script nor
  its hardcoded path survives.

---

## 8. Open items

| # | Item | Blocks release? | Owner |
|---|---|---|---|
| 1 | ~~Copyright holder name for `NOTICE`~~ — **settled 2026-11-02**: the public copyright holder is `Laplace2-ai`, a GitHub organization account and Studio brand (not a legal entity). `NOTICE` reads `Copyright © 2026 Laplace2-ai`; no "company / corporation / legal entity" wording appears anywhere in the repo. | No | closed |
| 2 | Confirm the §7.2 DLL exclusion does not degrade recognition | **Yes** — do it before the first build | maintainer |
| 3 | Pin the `chinese_cht` weight to a commit and record it (M2) | No | maintainer |
| 4 | Vendor the Noto Sans SC weight: record its checksum, and read its Reserved Font Name declaration before subsetting | No, but needed before the font can be shipped | maintainer |
