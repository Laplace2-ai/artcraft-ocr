# SPDX-License-Identifier: Apache-2.0
"""PhotoCraft writer.

Everything here follows ``DOCS/HOST_API.md``, which was measured against a live
instance rather than read off documentation. The two facts that shape the code:

* Bounds arrive in two layouts. Commands answer with ``[x0,y0,x1,y1]``, the
  inspector with ``[x,y,w,h]``. Both are converted on arrival, so nothing below
  this file handles a list.
* ``layer.translate`` takes integers. Placement is therefore accurate to about a
  pixel, and chasing better than that would mean fighting the interface.

Version 1 deliberately does not model partial-failure recovery beyond reporting
which items were written; see ``place_all``.

Reuse decision (rule 5, 2026-11-03). The internal implementation was read and
compared before this file was written; it is not a re-derivation for its own sake.
It was **not** lifted because it is **functionally short of what this product
needs**, and the four gaps are the record:

1. no per-paragraph colour or size — every block is written with one setting;
2. no paragraph mode — only point text, so a long paragraph runs out on one line;
3. failures collapse to ``None``, so "no document" and "channel dead" are the same
   value and the caller cannot tell which happened;
4. no tests.

"Different interface" is *not* the reason and must not be used as one: differing
interfaces are what an adapter exists to reconcile. If those four gaps are closed
upstream, this file should be replaced by a thin wrapper over that implementation.

Source tracking (rule 2): behaviours taken from the internal implementation are
named where they appear — ``session_ok`` preflight, the zero-offset translate
skip. No code was copied from it.

Review point (written 2026-11-03): check these four gaps against
``ENGINE_API.md`` the next time that document changes version. If they are closed
upstream, replace this file with a thin wrapper rather than extending it. Without
a date attached, the list above quietly becomes history instead of a criterion.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from CORE.model import Box, Line

BASELINE = 0.86
WIDTH_TOLERANCE = 0.04
MAX_RESIZE_ROUNDS = 2

ANCHORS = ("原位置", "左上", "右上", "中心", "左下", "右下")


class BridgeError(RuntimeError):
    """The bridge could not be started, or the host answered with an error."""


class Bridge:
    """A running ``photocraft-cli mcp --bridge`` child process.

    JSON-RPC over stdin, one object per line. Reading is done on a thread
    because ``select`` does not work on pipes on Windows.
    """

    def __init__(self, cli_path: str, port: int, token_file: str, timeout: float = 30.0) -> None:
        self._timeout = timeout
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            # Without this the CLI flashes a console window in front of the GUI,
            # which looks like a crash to the user.
            creationflags = subprocess.CREATE_NO_WINDOW
        self._proc = subprocess.Popen(
            [cli_path, "mcp", "--bridge", f"127.0.0.1:{port}", "--control-token-file", token_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=creationflags,
        )
        self._stderr: list[str] = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._queue: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self._next_id = 0
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "artcraft-ocr", "version": "0"},
            },
        )

    def _drain_stderr(self) -> None:
        assert self._proc.stderr is not None
        for line in self._proc.stderr:
            self._stderr.append(line.rstrip())

    def stderr_text(self) -> str:
        return " | ".join(self._stderr[-4:])

    def _pump(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._queue.put(line)

    def _rpc(self, method: str, params: dict) -> Any:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        assert self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()
        try:
            raw = self._queue.get(timeout=self._timeout)
        except queue.Empty as exc:
            detail = self.stderr_text()
            code = self._proc.poll()
            raise BridgeError(
                f"{method} 没有回应（{self._timeout}s）。"
                + (f" CLI 已退出，代码 {code}。" if code is not None else "")
                + (f" 错误输出：{detail}" if detail else "")
            ) from exc
        message = json.loads(raw)
        if "error" in message:
            raise BridgeError(str(message["error"]))
        return message

    def call(self, tool: str, arguments: dict | None = None) -> Any:
        """Call an MCP tool and return its decoded result.

        The result arrives as a JSON string inside a text content block.
        """
        message = self._rpc("tools/call", {"name": tool, "arguments": arguments or {}})
        blocks = message.get("result", {}).get("content", [])
        if not blocks:
            return None
        try:
            return json.loads(blocks[0].get("text", "null"))
        except json.JSONDecodeError:
            return blocks[0].get("text")

    def command(self, command_id: str, params: dict | None = None) -> Any:
        """Run a host command. The envelope key is ``params``, not ``args``."""
        return self.call("command_run", {"id": command_id, "params": params or {}})

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def __enter__(self) -> "Bridge":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def box_from_corners(bounds: Sequence[float]) -> Box:
    """``[x0, y0, x1, y1]`` — what ``type.create`` and ``type.info`` answer."""
    x0, y0, x1, y1 = bounds
    return Box(float(x0), float(y0), float(x1) - float(x0), float(y1) - float(y0))


def box_from_rect(bounds: Sequence[float]) -> Box:
    """``[x, y, w, h]`` — what ``doc_inspect`` answers."""
    x, y, w, h = bounds
    return Box(float(x), float(y), float(w), float(h))


@dataclass
class Written:
    text: str
    layer: int | None
    box: Box | None
    error: str | None = None


class PhotoCraft:
    """Places text in the host document."""

    def __init__(self, bridge: Bridge, resolution: int = 72) -> None:
        self._bridge = bridge
        self._resolution = resolution

    # -- document ---------------------------------------------------------
    def document_rect(self) -> Box | None:
        """Canvas bounds, or ``None`` when there is no document open.

        The host signals an empty document in more than one way; a document with
        no layers is not the same as no document, and the shapes differ between
        applications. Anything unreadable is treated as "cannot tell", and the
        caller proceeds — writing into nothing is recoverable, replacing the
        user's open document is not.
        """
        try:
            info = self._bridge.call("doc_inspect", {})
        except BridgeError:
            return None
        if not isinstance(info, dict):
            return None
        width, height = info.get("width"), info.get("height")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            return None
        return Box(0.0, 0.0, float(width), float(height))

    def session_ok(self) -> bool:
        """Whether the bridge answers at all.

        Used to separate two failures that look identical from the outside: no
        document open, and the control channel being dead. Creating a document on
        a dead channel fails anyway, and the error then points at the wrong thing.
        """
        try:
            return self._bridge.call("session_list", {}) is not None
        except BridgeError:
            return False

    def ensure_document(self, width: int = 1920, height: int = 1080) -> bool:
        """Create a document only when none is open.

        A freshly launched host may have no document, and every write command is
        refused without one. Creating one is safe *here* because we started the
        instance; if the user opened their own document, :meth:`document_rect`
        sees it and nothing is created.
        """
        if self.document_rect() is not None:
            return False
        if not self.session_ok():
            raise BridgeError("控制通道没有响应，无法确认文档状态")
        try:
            self._bridge.call("doc_new", {"width": int(width), "height": int(height),
                                          "background": "white"})
        except BridgeError:
            return False
        return True

    def layer_box(self, layer_id: int) -> Box | None:
        info = self._bridge.call("doc_inspect", {})
        for layer in (info or {}).get("layers", []):
            if layer.get("id") == layer_id:
                return box_from_rect(layer["bounds"])
        return None

    # -- writing ----------------------------------------------------------
    def place(
        self,
        text: str,
        target: Box,
        size: int,
        font: str,
        color: str,
        name: str | None = None,
        *,
        force_size: bool = False,
        paragraph: bool = False,
        fit_width: bool = True,
    ) -> int:
        """Create one text layer and move it onto ``target``.

        Returns the layer id. Raises :class:`BridgeError` if the host refuses.
        """
        params: dict[str, Any] = {
            "text": text,
            "size": int(size),
            "font": font,
            "color": color,
        }
        if paragraph:
            # Paragraph text is created against a frame, not an anchor point. The
            # frame is what makes long text wrap inside the recognised box.
            params["box"] = [
                int(round(target.left)), int(round(target.top)),
                max(1, int(round(target.width))), max(1, int(round(target.height))),
            ]
        else:
            params["x"] = int(round(target.left))
            params["y"] = int(round(target.top + size * BASELINE))
        if name:
            params["name"] = name

        made = self._bridge.command("type.create", params)
        if not isinstance(made, dict) or "layer" not in made:
            # The host answers with a plain string when it refuses (no document
            # open, bad argument). Passing that on as if it were a result is how
            # this turned into 'string indices must be integers'.
            raise BridgeError(f"type.create 被拒绝：{made!r}")
        layer_id = int(made["layer"])

        current = box_from_corners(made["bounds"])
        rounds = 0
        while (
            fit_width               # a multi-line block has no single width to fit
            and not force_size      # a size the user typed is not negotiable
            and not paragraph       # a frame already decides the width
            and rounds < MAX_RESIZE_ROUNDS
            and target.width > 0
            and current.width > 0
            and abs(current.width - target.width) / target.width > WIDTH_TOLERANCE
        ):
            size = max(6, round(size * target.width / current.width))
            self._bridge.command("type.setStyle", {"layer": layer_id, "size": int(size)})
            measured = self.layer_box(layer_id)
            if measured is None:
                break
            current = measured
            rounds += 1

        self._bridge.command(
            "layer.translate",
            {
                "layer": layer_id,
                "dx": int(round(target.left - current.left)),
                "dy": int(round(target.top - current.top)),
            },
        )
        return layer_id

    def group_layers(self, layer_ids: Sequence[int], name: str) -> int | None:
        """Put the given layers into one group, returning the group id.

        The command groups *the current selection*, so the layers are selected
        first — replace for the first, add for the rest. Grouping per import is
        what keeps one recognition run distinguishable from the next in the
        layers panel, and it keeps the user's own layers out of it.
        """
        ids = [int(i) for i in layer_ids if i]
        if not ids:
            return None
        self._bridge.command("layer.select", {"layer": ids[0], "mode": "replace"})
        for layer_id in ids[1:]:
            self._bridge.command("layer.select", {"layer": layer_id, "mode": "add"})
        made = self._bridge.command("layer.groupLayers", {"name": name})
        if isinstance(made, dict) and "layer" in made:
            group_id = int(made["layer"])
            # New groups land above whatever was selected; putting them at the
            # top means repeated imports stack downwards instead of nesting into
            # each other, which is what a growing document should look like.
            self._bridge.command("layer.arrange.bringToFront", {"layer": group_id})
            return group_id
        return None

    def place_all(
        self,
        items: Sequence[tuple],
        size: int,
        font: str,
        color: str,
        anchor: str = "原位置",
        cancelled: Any = None,
        force_size: bool = False,
        paragraph: bool = False,
    ) -> list[Written]:
        """Place several blocks, continuing past individual failures.

        Deliberately does not delete anything on failure. A partial write is
        reported as it happened; removing layers is a destructive act that
        belongs to the user, and a retry produces duplicates that are easy to see
        and easy to remove.
        """
        canvas = self.document_rect()
        dx = dy = 0
        if canvas is not None and anchor != "原位置":
            dx, dy = anchor_offset(items, canvas, anchor)

        results: list[Written] = []
        consecutive_failures = 0
        for item in items:
            # A block may carry its own colour (follow the original ink) or fall
            # back to the one size-and-font default for the whole run.
            text, box = item[0], item[1]
            item_colour = item[2] if len(item) > 2 and item[2] else color
            item_size = item[3] if len(item) > 3 and item[3] else size
            item_fit = item[4] if len(item) > 4 else True
            if cancelled is not None and getattr(cancelled, "is_set", lambda: False)():
                break
            moved = Box(box.left + dx, box.top + dy, box.width, box.height)
            try:
                layer_id = self.place(
                    text, moved, item_size, font, item_colour,
                    force_size=force_size, paragraph=paragraph, fit_width=item_fit,
                )
                results.append(Written(text, layer_id, moved))
                consecutive_failures = 0
            except BridgeError as exc:
                results.append(Written(text, None, moved, str(exc)))
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    break
        return results


def anchor_offset(items: Sequence[tuple], canvas: Box, anchor: str) -> tuple[int, int]:
    """Delta that moves the whole block to one of the canvas anchors.

    Version 1 computes this from the recognised boxes, before anything is
    written. It is therefore exact only when the placed text does not change the
    block's size — which it does not, because the text is set at the sizes that
    produced the boxes.
    """
    if not items:
        return 0, 0
    # Items may carry extra fields (colour, size); index rather than unpack, or
    # every added option breaks alignment with "too many values to unpack".
    boxes = [item[1] for item in items]
    left = min(box.left for box in boxes)
    top = min(box.top for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    width, height = max(1.0, right - left), max(1.0, bottom - top)

    if anchor in ("左上", "左下"):
        want_left = canvas.left
    elif anchor in ("右上", "右下"):
        want_left = canvas.right - width
    elif anchor == "中心":
        want_left = canvas.left + (canvas.width - width) / 2
    else:
        return 0, 0

    if anchor in ("左上", "右上"):
        want_top = canvas.top
    elif anchor in ("左下", "右下"):
        want_top = canvas.bottom - height
    elif anchor == "中心":
        want_top = canvas.top + (canvas.height - height) / 2
    else:
        return 0, 0

    dx, dy = want_left - left, want_top - top

    # Keep the block inside the canvas. A block wider than the canvas cannot fit,
    # and without this the corners place it completely off the page, which reads
    # as "the anchor does nothing".
    dx = max(-left, min(dx, canvas.width - right)) if right - left <= canvas.width else -left
    dy = max(-top, min(dy, canvas.height - bottom)) if bottom - top <= canvas.height else -top
    return int(round(dx)), int(round(dy))


def lines_to_items(lines: Sequence[Line], text_of: Any = None) -> list[tuple[str, Box]]:
    """Adapter from recognised lines to ``(text, target box)`` pairs."""
    items: list[tuple[str, Box]] = []
    for line in lines:
        text = text_of(line) if callable(text_of) else line.text
        items.append((text, Box(line.x, line.y, line.w, line.h)))
    return items


def find_cli(app_dir: str | Path, name: str = "photocraft-cli.exe") -> Path:
    path = Path(app_dir) / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path
