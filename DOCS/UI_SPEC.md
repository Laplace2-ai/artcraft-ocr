# UI SPEC — Lp2 visual system for ARTCRAFT_OCR

> Maintainer: the release maintainer. Implemented by the internal line, mirrored here.
> Source of the palette: the Lp2 theme stylesheet supplied by the project owner.
> This document, not the screenshots, is what other apps reuse.

## 0. Framework decision

`theme.css` is CSS. tkinter cannot load it, and — the part that decides the question — **it is
not a component library**: it styles Markdown blocks in an editor (headings, callouts, inline
code, checkboxes, scrollbar). There are no buttons, inputs, selects, tabs or panels in it.

So porting the tokens to Python constants would still leave every component to be drawn by hand,
using a toolkit with no rounded borders, no per-widget transitions and no custom scrollbar. The
result would be a *themed* Tk window, which is the thing being replaced.

**Decision: HTML + CSS in a WebView (pywebview / WebView2), Python keeps the engine.**

| | tkinter + Python tokens | HTML/CSS in WebView |
|---|---|---|
| Token fidelity | re-express by hand | the stylesheet already is CSS |
| Rounded corners, transitions, custom scrollbars | not available | native |
| Components to author | all of them | all of them, in CSS |
| Reusable by the other three apps | a Python module per app | the same CSS file |
| New runtime dependency | none | WebView2 (present on Windows 10/11 by default) |

The dependency is the only cost, and it buys the thing the brief actually asks for: one visual
system, four apps. If WebView2 is missing the app must say so in one line and exit — not fail
with a stack trace.

The mockups in this repository are written in the same HTML/CSS those builds will ship, so an
approved mockup is not a picture to be re-implemented; it is the starting point.

## 1. Colour tokens

Taken from the Lp2 theme. `(t)` = value taken from the theme; `(d)` = derived, because an
application needs states a Markdown editor never had.

| Token | Value | Source | Use |
|---|---|---|---|
| `--bg-canvas` | `#170f16` | t | window background |
| `--bg-panel` | `#0b1625` | t | result pane, title bar, bottom bar |
| `--bg-panel-alt` | `#31202d` | t | raised areas, never behind an image |
| `--bg-preview` | `#141414` | d | image canvas |
| `--bg-field` | `#07140c` | t | inputs, selects, kbd |
| `--bg-field-focus` | `#0e2117` | t | focused field |
| `--fg` | `#ffdb92` | t | primary text |
| `--fg-muted` | `#99fdff` | t | secondary text, tags |
| `--fg-faint` | `#b88ab6` | t | meta, labels, placeholders |
| `--fg-inverse` | `#1e0000` | t | text on accent |
| `--accent` | `#d60064` | t | primary action, active marker |
| `--accent-hover` | `#ff0077` | t | hover, brand mark |
| `--accent-strong` | `#f6344f` | t | reserved, high-emphasis moments |
| `--ok` | `#00f7ff` | t | connected state |
| `--warn` | `#ffd166` | t | degraded, non-blocking |
| `--danger` | `#ff5a5a` | t | failure |
| `--border` | `rgba(101,94,98,.55)` | t | structural lines |
| `--border-quiet` | `rgba(101,94,98,.28)` | d | separators inside a panel |
| `--border-strong` | `#ff0077` | t | focus ring, active border |

Rules:

- **Solid accent fill is reserved for the primary action.** Exactly one element on a screen may be a
  filled accent block. Everything else that needs emphasis uses accent *text* plus a wash and a
  2 px edge — which still reads as selected, without competing for the same attention.

  Counting accents by pixel area is the wrong test, and it passed a design that failed: mark,
  selected segment and primary button were individually small, but they sat in three different
  corners and read as a frame around the content. Judge by placement and by what the eye lands on
  first, not by how much ink was used. Since the mark is decorative and never clicked, it is the
  first thing to demote.
- **No glow except the connection dot.** The theme ships glow keyframes; using them on text or
  panels produces the "cheap cyberpunk" the brief rules out.
- **No gradients on surfaces.** The theme uses them in a Markdown editor where content is dense;
  an application surface with a wash reads as decoration.
- Cyan is a *text* colour here, not a surface colour. `#00f7ff` at full strength on a large area
  is unreadable.
- **The image canvas is neutral grey (`--bg-preview`), never a brand tint.** Two reasons, one
  functional: a coloured surround shifts how the eye judges the ink colour in the image, and when
  the source came from a screen capture it can put the tint inside the sampled region. Image
  editors settled on neutral grey for exactly this. Brand colour belongs on frames and state,
  not behind content the user is measuring.

## 2. Type

| Token | Value | Use |
|---|---|---|
| `--font-ui` | Segoe UI Variable Text, Segoe UI, system-ui | all running text |
| `--font-display` | Cascadia Mono, Consolas, ui-monospace | section labels, brand, step numbers |
| `--font-mono` | Cascadia Mono, Consolas, ui-monospace | numbers, coordinates, hex, timing |
| `--fs-xs` 11px | | label uppercase, badges |
| `--fs-sm` 12px | | meta rows, status bar |
| `--fs-md` 13px | | buttons, inputs, menus |
| `--fs-base` 15px | | recognised text, body |
| `--fs-lg` 17px | | empty-state lead |
| `--fs-xl` 22px | | reserved |

- Section labels are uppercase with `letter-spacing: .16em`. That tracking is what makes the
  retro reference read as typography rather than as a costume.
- **Numbers are always mono.** Timing, size, coordinates, hex. Proportional figures in a
  technical tool look sloppy and are harder to compare.
- The theme asks for `Chicago` and `computer`. Neither ships with Windows. Until an OFL display
  face is chosen and bundled (see `LICENSES.md` §6), the display stack falls back to a mono.
  Do not silently substitute a serif.

## 3. Geometry and motion

| Token | Value |
|---|---|
| `--r-s` / `--r-m` / `--r-l` | 6 / 10 / 14 px |
| border width | 1.5 px |
| `--fast` / `--med` / `--slow` | 120 / 180 / 260 ms |

- 1.5 px is deliberate: at 1 px the frames disappear on a dark panel, at 2 px they read as
  boxes. Keep it.
- Interaction feedback uses `--fast`. Anything above 260 ms feels laggy in a tool used hourly.

## 4. Layout

```
┌──────────────────────────────────────────────────────────┐
│ brand │ 文件 编辑 帮助 │ … │ source · size · target group │ 46
├───────────────────────────────┬──────────────────────────┤
│ SOURCE                        │ RESULT                    │ 34
│                               │                           │
│        canvas / image         │      paragraph blocks     │  flex
│                               │                           │
├───────────────────────────────┴──────────────────────────┤
│ 目标 语种 字体 比例 写入 [点|段] □跟随原文字色              │ params
│ [粘贴][打开][框选]  ① [识别] [复制] [简→繁] [繁→简]  ② [写入]│ actions
│ ● 已连接 · 127.0.0.1:49733 │ 识别完成 3 段 / 12 行 · 1.9s  │ status
└──────────────────────────────────────────────────────────┘
```

- Source 54% / result 46%. The result pane is where the user works; it does not get less than
  46% because the image is only being looked at.
- Two bottom rows, never one: parameters above actions. Mixing them makes the row unreadable at
  1280 px, which is the width that actually breaks layouts.
- Status bar always last, always one line. Connection state on the left, facts in the middle,
  actions on the right.

## 5. Components

| Component | Idle | Hover | Active / selected | Disabled |
|---|---|---|---|---|
| `.btn` | transparent, `--border` | bg +4% white, border `--fg-faint` | — | 38% opacity |
| `.btn.primary` | `--accent` fill, inverse text | `--accent-hover` | — | field bg, no fill |
| `.select` / `.num` | `--bg-field`, `--border` | border `--border-strong` | bg `--bg-field-focus` | — |
| `.seg` | track `--field` | item hover | item: accent fill, inverse text | — |
| `.block` | transparent, 2 px transparent left edge | +2.5% white | accent left edge + 6% accent wash | — |
| `.dot` | `--fg-faint` | — | `--ok` connected / `--danger` failed | — |

- **A disabled primary must lose its fill.** A faded magenta button still reads as the thing to
  press; a neutral one reads as "not yet".
- Write state belongs on the block, not in a modal: the user needs to see *which* paragraph
  failed, in place. Failure carries one line of reason and one action ("重试失败段"), never a
  dialog.
- **Where the block lands is a choice, not a side effect.** The anchor selector offers 原位置 /
  左上 / 右上 / 中心 / 左下 / 右下, and it sits next to scale because both answer the same
  question: how does this text relate to the canvas. 原位置 must stay the default — a page
  captured from a document is usually meant to go back where it came from, and landing at a
  corner by default would silently move the user's content.
- **A write button never hardcodes the host name.** Its label follows the target selector:
  `② 写入 {目标}`. A button that says one app while the dropdown says another is the kind of
  inconsistency a user reports as "it wrote to the wrong app" when it did not.
- **Partial writes are not rolled back, so re-writing duplicates.** After any partial failure the
  primary action becomes "重试失败段", never a plain "写入" again, and the banner states the
  consequence in one short line. A second full write is allowed but has to be an explicit choice,
  because the duplicate layers are the user's to clean up, not ours to delete.
- **Abort is a distinct state from "some failed".** Writing continues past a single failure, but
  stops after three consecutive failures or on a connection-level error. The banner says which
  one happened — "1 段没写进去" and "已停止：连续失败" are different situations and the user acts
  differently on them.
- Anything that can fail per-item reports per-item. A single global "写入完成" toast hides the
  one paragraph that did not land.

## 6. Screens

Maintained as HTML next to this file, so the spec and the picture cannot drift:

| State | File |
|---|---|
| Empty / waiting for an image | `mockup/01-main.html` |
| Recognised, paragraphs listed | `mockup/02-result.html` |
| Writing, with one paragraph failed | `mockup/03-writing.html` |

## 7. Brand assets

The name and the icon are trademark assets and are **not** covered by the code licence — the same
rule this project relies on when it talks to the host applications. See `LICENSES.md` §2.2 and
`NOTICE`.

The icon is drawn, not traced: a 16×16 pixel grid in `build/icon/make_icon_final.py`, exported at
16/24/32/48/64/96/128/256/512 plus a multi-resolution `artcraft-ocr.ico` for the Windows build.

| Token | Value | Use |
|---|---|---|
| tile | `#000F29` | icon background |
| letter | `#FFFFFF` | the A |
| apex | `#FF6BD3` | the top row of the A only |

Rules that are not stylistic:

- **The A is open: no crossbar.** This was chosen from a size comparison, so it is deliberate.
  Note the consequence rather than re-arguing it: at 16 px the shape reads as an arch, and the
  wordmark beside it is what identifies the product at that size.
- **Full-bleed square output, rounding in CSS.** Baking a radius into the bitmap turns the 16 px
  export to mush; the OS masks app icons and the browser can round a `<div>`.
- **Pink is the apex only.** One row of the A. Spreading it across the icon makes it a logo for
  a colour rather than for the product.
- The tile colour is deliberately almost identical to `--bg-panel` (#0B1625). At title-bar size
  the tile disappears and the A appears to float; that is the intent, not an accident.

`--brand-pink` (#FF6BD3) is the identity accent used by the wordmark and the icon. It is not the
interaction accent (`--accent` #D60064 / `--accent-hover` #FF0077); controls never use it.

The Lp2 circular mark appears in one place: the foot of the About panel, as the Studio's own
signature. It is shipped for that purpose only — it is a trademark of the project owner, it is
not covered by the code licence, and it must not be reused elsewhere in the interface or in
exported material.
