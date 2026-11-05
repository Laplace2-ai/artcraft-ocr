# HOST API — what PhotoCraft actually does

> Measured 2026-11-03 against the local build, by driving it, not by reading its docs.
> Every number here came out of a running instance.

## Launching a controllable instance

```sh
photocraft.exe --control <PORT> --control-token-file <PATH>
```

Verified: the app listens on PORT and **creates the token file itself** if the path does not
exist. So the launcher does not generate a token — it nominates a path and reads what appears.
That is why the control parameters are ours to choose and never need discovering.

Check the port by connecting; the window is not a reliable signal.

## Talking to it

```
photocraft-cli.exe mcp --bridge 127.0.0.1:<PORT> --control-token-file <PATH>
```

> Re-verified against PhotoCraft **0.20.2** on 2026-11-05: the host answers
> `doc_inspect` and `command_list` (965 commands), and every command this adapter
> sends — `type.create`, `type.setStyle`, `type.info`, `layer.select`,
> `layer.groupLayers` — is present. The 0.20.1 → 0.20.2 step changed nothing here.

Plain JSON-RPC over stdin/stdout, **one JSON object per line**, no Content-Length framing.
Sequence: `initialize` → `tools/list` → `tools/call`.

Two things that cost time:

- **`command_run` takes `{ "id": ..., "params": {...} }`, not `args`.** Passing `args` returns
  `unknown argument 'args'`, which reads like the command is wrong rather than the envelope.
- **Do not `select()` on the child's stdout on Windows.** Pipes are not sockets there; use a
  reader thread and a queue.

26 tools are exposed. The ones that matter for writing: `doc_new`, `doc_open`, `doc_inspect`,
`command_run`, `doc_place`, `doc_select`, `doc_close`, plus `ui_*` for driving the interface.

## Command ids

Tools wrap commands; the command table is available from `command_list` and each entry carries
its own parameter spec. Text work uses `type.create`, `type.edit`, `type.setStyle`, `type.info`,
`type.rasterize`, `type.fonts`.

`type.create` parameter note:

| Field | Meaning |
|---|---|
| `x`, `y` | **baseline anchor** for point text, not the top-left |
| `box` | `[x, y, w, h]` — switches the layer to paragraph text |
| `size` | points |
| `color` | `#rrggbb` |

Measured: `y=300, size=24` produced a box with `top=280`, i.e. `top ≈ y - 0.83*size`. Consistent
with the engine note's `y = top + size*0.86`; treat the coefficient as approximate and always
read the box back.

## The bounds trap — two formats, one layer

This is the single most expensive detail in the integration, so it is recorded with the
measurement rather than a warning:

```text
command_run type.create  →  {"bounds": [700, 280, 798, 304], "layer": 3}
doc_inspect              →  {"bounds": [700, 280,  98,  24], ...}
type.info                →  {"bounds": [700, 280, 798, 304], ...}
```

Same layer, same moment:

| Source | Format |
|---|---|
| `type.create`, `type.setStyle`, `type.info` | `[x0, y0, x1, y1]` |
| `doc_inspect` | `[x, y, w, h]` |

Read `798` as a width and the scale factor becomes 8×; read `98` as an x1 and the text shrinks.
Neither raises an error. `[x,y,w,h]` is also what `type.create` **accepts** for `box`, so the same
list means different things on the way in and on the way out.

**Rule: parse at the boundary.** Adapters convert to `CORE.model.Box` immediately and nothing
downstream ever sees an array. The type makes the mix-up impossible instead of relying on a
comment.

## Placement loop — measured end to end

Target from a real page: a 472×64 box at (800, 232), text set at 71 pt.

| Step | Result |
|---|---|
| `type.create` at `y = top + 0.86*size` (293) | box top came back **233**, i.e. 1 px below target |
| width read back | 521 px vs 472 wanted (10 % over) |
| one resize to `71 * 472/521 = 64` | width **470** px, 0.4 % under |
| `layer.translate` by (1, −7) | final box **[800, 232, 470, 64]** |
| error | left **0 px**, top **0 px**, width **−2 px**, height **0 px** |

So the loop in the engine note is sound and one resize round is enough in practice: the 0.86
baseline coefficient, `[x,y,w,h]` from `doc_inspect` for measuring, and `layer.translate` for the
final nudge.

Two details worth keeping:

- **`layer.translate` takes integer `dx`/`dy` only.** Sub-pixel placement is not available, so
  final position is always ±1 px; do not chase exactness with floats.
- Resize by **width**, not by height. Height follows from the font metrics and rounding it
  directly fights the metrics; 2 px of width error is invisible at these sizes.

## Not yet verified

- Writing to `VectorCraft` (same flow, real bounds available).
- Anchor translation to a canvas corner (left / right / centre / bottom) — the uniformly applied
  `layer.translate` is proven, the offset arithmetic for each anchor is not.
- Behaviour when the document is closed mid-write.
- Paragraph text (the `box` parameter) rather than point text.
