# SPDX-License-Identifier: Apache-2.0
"""ArtCraft OCR — desktop shell.

A WebView window over the engine. The interface is HTML/CSS in ``ui/``; this file
is the seam: it owns the window, the file dialogs and the long-running calls, and
exposes them to the page as a small API.

Nothing here parses a rectangle or measures a glyph — that is what CORE and the
adapters are for, and keeping this file thin is what makes them testable.
"""

from __future__ import annotations

import base64
import io as _io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import Any

FROZEN = bool(getattr(sys, "frozen", False))
# When frozen, code and data live under _MEIPASS (the onedir _internal folder),
# but anything the user can change — settings — belongs next to the executable.
RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
EXE_DIR = Path(sys.executable).resolve().parent if FROZEN else RES
ROOT = RES
sys.path.insert(0, str(ROOT))

from CORE.convert import convert as convert_text  # noqa: E402
from CORE.metrics import estimate_size  # noqa: E402
from CORE.model import Box, Line  # noqa: E402
from CORE.segment import group_paragraphs, paragraphs_to_text  # noqa: E402

VERSION = "1.0.0"


APP_DIR = ROOT / "APP"
UI_DIR = APP_DIR / "ui"
SETTINGS = EXE_DIR / "settings.json"

DEFAULT_SETTINGS = {
    # Empty on purpose: a path from the development machine must not be compiled
    # into a release build. The user points this at their own install, either in
    # settings.json next to the executable or through ARTCRAFT_HOST_DIR.
    "host_dir": "",
    "port": 8125,
    "token": "",
    "lang": "ch",
    # First run opens in English: someone who cannot read Chinese cannot find the
    # switch that would turn it into English. Chinese users can read English.
    "ui_lang": "en",
    "font": "Microsoft YaHei",
    "scale": 100,
    "anchor": "原位置",
    "follow_colour": True,
}


def load_settings() -> dict:
    env_host = os.environ.get("ARTCRAFT_HOST_DIR")
    if env_host:
        merged = dict(DEFAULT_SETTINGS)
        if SETTINGS.exists():
            try:
                merged.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
        merged["host_dir"] = env_host
        return merged
    if SETTINGS.exists():
        try:
            merged = dict(DEFAULT_SETTINGS)
            merged.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
            return merged
        except (OSError, json.JSONDecodeError):
            pass
    return dict(DEFAULT_SETTINGS)


def port_open(port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_port(port: int, timeout: float = 40.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.4)
    return False


MSG = {
    "no_host": {"zh": "还没指定目标程序。打开 文件 → 设置…，选择 photocraft.exe。",
                "en": "No target program set. Open File → Settings… and choose photocraft.exe."},
    "no_dir": {"zh": "这个目录不存在：{path}", "en": "That folder does not exist: {path}"},
    "no_exe": {"zh": "这个目录里没有 photocraft.exe：{path}",
               "en": "There is no photocraft.exe in {path}"},
    "manual": {"zh": "PhotoCraft 已经开着，但它没有控制口；手动双击打开的实例不会监听控制口。请关掉它，改用本程序生成的 photocraft_OCR.bat 启动。",
               "en": "PhotoCraft is running without a control channel; an instance opened by hand does not listen on one. Close it, then start it with photocraft_OCR.bat."},
    "port_late": {"zh": "启动后控制口 {port} 没有就绪", "en": "The control port {port} never came up"},
    "port_dead": {"zh": "控制口 {port} 开着，但找不到它的 token 文件：{path}。如果那个实例是用别的 token 启动的，请关掉它，改用本程序生成的启动脚本。",
                  "en": "Port {port} is open but its token file is not at {path}. If that instance was started with another token, close it and use the generated launch script."},
    "need_dir": {"zh": "先设置好程序目录", "en": "Set the program folder first"},
    "bat_write": {"zh": "写不了启动脚本：{err}", "en": "Cannot write the launch script: {err}"},
    "no_content": {"zh": "没有内容可写", "en": "Nothing to write"},
    "only_pc": {"zh": "这个版本只能写入 PhotoCraft，{target} 还没有适配器",
                "en": "This build writes to PhotoCraft only; {target} has no adapter yet"},
    "export_empty": {"zh": "没有内容可导出", "en": "Nothing to export"},
    "file_write": {"zh": "写不了文件：{err}", "en": "Cannot write the file: {err}"},
    "no_undo": {"zh": "没有可撤销的操作", "en": "Nothing to undo"},
    "no_redo": {"zh": "没有可重做的操作", "en": "Nothing to redo"},
    "github": {"zh": "GitHub 仓库尚未发布", "en": "The GitHub repository is not published yet"},
    "file_missing": {"zh": "找不到文件：{path}", "en": "File not found: {path}"},
    "cannot_reload": {"zh": "这张图不是从文件读进来的，没有可刷新的来源",
                      "en": "This picture did not come from a file, so there is nothing to reload"},
    "psd_locked": {"zh": "这个 PSD 读不了：文件可能没有保存合并图（Photoshop 的“最大兼容”），或者正被独占占用",
                   "en": "This PSD cannot be read: it may have been saved without a merged composite (\"Maximize Compatibility\"), or the file is locked"},
}


def host_folder(value: str | Path | None) -> Path:
    """The host's directory, whether the stored value is the folder or the exe.

    The settings dialog shows the full path to ``photocraft.exe`` because that is
    what the owner picked, and saving that string as ``host_dir`` produced
    ``...\\photocraft.exe\\photocraft.exe`` — the "这个目录里没有 photocraft.exe"
    error, with a path that looked mangled. Accepting both shapes means an
    already-saved bad value heals itself instead of needing a settings reset.
    """
    path = Path(str(value or ""))
    if path.suffix.lower() == ".exe" or (path.exists() and path.is_file()):
        return path.parent
    return path


class ShortcutError(RuntimeError):
    """A desktop shortcut could not be created."""


_SHORTCUT_SCRIPT = """$OutputEncoding = [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
$desktop = [Environment]::GetFolderPath('Desktop')
$path = Join-Path $desktop '{name}.lnk'
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($path)
$s.TargetPath = '{target}'
$s.WorkingDirectory = '{workdir}'
$s.Description = '{description}'
{extra}
$s.Save()
Write-Output $path
"""


def _ps_quote(value: str) -> str:
    """Single-quoted PowerShell literal: the only escape needed is doubling '."""
    return str(value).replace("'", "''")


def make_desktop_shortcut(name: str, target: str | Path, workdir: str | Path | None = None,
                          icon: str = "", description: str = "") -> Path:
    """Create ``<Desktop>/<name>.lnk`` pointing at ``target``.

    Built through ``WScript.Shell`` because there is no stdlib writer for a .lnk,
    and the alternative — a compiled helper — is a dependency for one small job.
    The script travels as ``-EncodedCommand``: quoting a path through a command
    line is where this would otherwise break on a folder with spaces or an
    apostrophe in its name.
    """
    if sys.platform != "win32":
        raise ShortcutError("桌面快捷方式只在 Windows 上支持")
    target = Path(target)
    if not target.exists():
        raise ShortcutError(f"目标不存在：{target}")
    script = _SHORTCUT_SCRIPT.format(
        name=_ps_quote(name),
        target=_ps_quote(target),
        workdir=_ps_quote(workdir or target.parent),
        description=_ps_quote(description or name),
        extra=(f"$s.IconLocation = '{_ps_quote(icon)}'" if icon else ""),
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=30, creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ShortcutError(str(exc)) from exc
    # Bytes, not text=True: PowerShell's redirected stdout is in the console
    # codepage (GBK here), and letting subprocess decode it as UTF-8 throws in a
    # reader thread — with a path that is pure ASCII the shortcut still appears,
    # so the failure stays invisible until someone's desktop folder is Chinese.
    out = (done.stdout or b"").decode("utf-8", "replace")
    err = (done.stderr or b"").decode("utf-8", "replace")
    if done.returncode != 0:
        detail = (err or out).strip().replace("\n", " ")[:300]
        raise ShortcutError(detail or f"退出码 {done.returncode}")
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    path = Path(lines[-1]) if lines else None
    if path is None or not path.exists():
        raise ShortcutError("快捷方式没有生成")
    return path


class Api:
    """Everything the page can call. Each method returns JSON-safe data."""

    def __init__(self) -> None:
        self.settings = load_settings()
        self._image = None          # PIL image currently loaded
        self._history: list[tuple] = []   # 撤销栈，每项是一张完整画面的快照
        self._future: list[tuple] = []    # 重做栈
        self._image_name = ""
        self._image_path = ""       # where it came from, "" for a capture
        self._lines = []
        self._colour_of: dict[int, str] = {}
        self._paragraphs: list[list] = []
        self._line_items: list[dict] = []
        self._engine = None
        self._app_proc: subprocess.Popen | None = None
        self._overlay = None
        self._pending = None
        self._origin = (0, 0)
        self._main_window = None
        self._port: int | None = None
        self._token: str | None = None

    # -- helpers ----------------------------------------------------------
    def _m(self, key: str, **kw) -> str:
        """User-facing message in the interface language."""
        lang = self.settings.get("ui_lang", "en")
        template = MSG[key][lang] if lang in MSG[key] else MSG[key]["zh"]
        return template.format(**kw) if kw else template

    def _engine_for(self, lang: str):
        """One engine per language, built on demand.

        The traditional model is a separate file, so switching language is a new
        engine rather than a setting.
        """
        if self._engine is not None and self._engine_lang == lang:
            return self._engine

        from ADAPTERS.rapidocr_engine import RapidOcrEngine

        rec = None
        if lang == "cht":
            candidate = ROOT / "MODELS" / "chinese_cht_PP-OCRv3_rec_mobile.onnx"
            if not candidate.exists():
                raise FileNotFoundError(
                    f"繁体模型不在 MODELS/ 下：{candidate.name}（可先用简体识别）"
                )
            rec = str(candidate)

        self._engine = RapidOcrEngine(rec_model_path=rec)
        self._engine_lang = lang
        return self._engine

    # -- undo / redo ------------------------------------------------------
    def _snapshot(self) -> tuple:
        return (self._image, self._image_name, self._image_path, self._origin)

    def _remember(self) -> None:
        """Push the current picture before it is replaced.

        框选会立刻把图裁掉，一次拖错就得重新截一次 —— 撤销栈是这套交互唯一
        合理的补救。存的是完整位图而不是裁剪矩形：裁剪点进去以后再裁一次，
        几何已经叠过了，回放矩形比存图更容易出错。
        """
        if self._image is None:
            return
        image, name, path, origin = self._snapshot()
        self._history.append((image.copy(), name, path, origin))
        del self._history[:-10]
        self._future.clear()

    def _restore(self, state: tuple) -> dict:
        image, name, path, origin = state
        self._image, self._image_name, self._image_path, self._origin = (
            image, name, path, origin)
        return {"ok": True, "name": name, "width": image.width, "height": image.height,
                "preview": self._preview_uri(image),
                "undo": len(self._history), "redo": len(self._future)}

    def undo_image(self) -> dict:
        if not self._history:
            return {"ok": False, "error": self._m("no_undo")}
        if self._image is not None:
            self._future.append(self._snapshot())
        return self._restore(self._history.pop())

    def redo_image(self) -> dict:
        if not self._future:
            return {"ok": False, "error": self._m("no_redo")}
        if self._image is not None:
            self._history.append(self._snapshot())
        return self._restore(self._future.pop())

    # -- image ------------------------------------------------------------
    def open_image(self) -> dict:
        import webview

        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            # PSD included on purpose: PhotoCraft writes PSD, and PIL reads the
            # flattened composite, so the picture can be refreshed while the
            # design is still being worked on elsewhere.
            file_types=("Images (*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tif;*.tiff;*.psd;*.psb)",
                        "All files (*.*)"),
        )
        if not result:
            return {"ok": False}
        return self._load_image(result[0])

    def reload_image(self) -> dict:
        """Re-read the picture from disk — the file may have changed under us.

        PSD is the case that matters: PhotoCraft saves it while the user keeps
        editing, and the point of opening the PSD was to stay in step with that.
        """
        path = getattr(self, "_image_path", "") or ""
        if not path or not Path(path).exists():
            return {"ok": False, "error": self._m("cannot_reload")}
        return self._load_image(path)

    def paste_image(self) -> dict:
        from PIL import ImageGrab

        grabbed = ImageGrab.grabclipboard()
        if grabbed is None:
            return {"ok": False, "error": "剪贴板里没有图片"}
        names = [n for n in getattr(grabbed, "keys", lambda: [])()]
        if names:
            return self._load_image(names[0])
        # 剪贴板里的位图没有文件名，只能先落到磁盘再读回。读完立刻删掉：
        # 一个每次粘贴都在 %TEMP% 留一份文件的程序，用户迟早会问"这是谁写的"。
        path = Path(tempfile.gettempdir()) / "artcraft-clipboard.png"
        grabbed.save(path)
        try:
            return self._load_image(str(path))
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    def _load_image(self, path: str) -> dict:
        from PIL import Image

        try:
            image = Image.open(path)
            image.load()
        except OSError as exc:
            suffix = Path(path).suffix.lower()
            if suffix in (".psd", ".psb"):
                return {"ok": False, "error": self._m("psd_locked")}
            return {"ok": False, "error": f"{Path(path).name}: {exc}"}
        self._remember()
        self._image = image.convert("RGB")
        self._image_name = Path(path).name
        self._image_path = str(path)
        return {"ok": True, "name": self._image_name,
                "width": self._image.width, "height": self._image.height,
                "reloadable": bool(getattr(self, "_image_path", "")),
                "preview": self._preview_uri(self._image)}

    @staticmethod
    def _preview_uri(image, longest: int = 1400) -> str:
        """Inline preview.

        A ``file://`` URI cannot be shown by the page: the document is itself a
        file URL, and the WebView refuses to load another file from a different
        directory. Passing the bytes avoids the permission question entirely, and
        the image is downscaled so a 6000px photo does not cross the bridge.
        """
        thumb = image.copy()
        thumb.thumbnail((longest, longest))
        buffer = _io.BytesIO()
        thumb.convert("RGB").save(buffer, "PNG", optimize=True)
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{payload}"

    def grab_screen(self) -> dict:
        """Capture the screen so a region can be picked on the preview."""
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        self._remember()
        self._image = image.convert("RGB")
        self._image_name = "screen.png"
        return {"ok": True, "name": self._image_name,
                "width": self._image.width, "height": self._image.height,
                "reloadable": bool(getattr(self, "_image_path", "")),
                "preview": self._preview_uri(self._image)}

    def grab_region(self) -> dict:
        """Pick a region on a real full-screen overlay.

        The overlay is a toolkit window, not a WebView one: pywebview's second
        window never covered the desktop here, so a drag in it would have been
        made on something invisible.
        """
        from APP.overlay import pick_region

        # Hide first: the overlay photographs the screen, and our own window in
        # that photograph is the one thing the user never wants in the crop.
        hidden = False
        if self._main_window is not None:
            try:
                self._main_window.hide()
                hidden = True
                time.sleep(0.25)     # let the compositor actually remove it
            except Exception:
                hidden = False
        try:
            region = pick_region()
        finally:
            if hidden:
                try:
                    self._main_window.show()
                except Exception:
                    pass
        if region is None:
            return {"ok": False, "cancelled": True}
        self._remember()
        self._image = region
        self._image_name = "screen.png"
        return {"ok": True, "name": self._image_name,
                "width": self._image.width, "height": self._image.height,
                "reloadable": bool(getattr(self, "_image_path", "")),
                "preview": self._preview_uri(self._image)}

    def crop_to(self, left: float, top: float, width: float, height: float,
                source_width: float, source_height: float) -> dict:
        """Crop the loaded image to a rectangle given in preview coordinates."""
        if self._image is None:
            return {"ok": False, "error": "还没有图片"}
        if width < 8 or height < 8:
            return {"ok": False, "error": "选区太小"}
        scale_x = self._image.width / max(1.0, source_width)
        scale_y = self._image.height / max(1.0, source_height)
        box = (int(left * scale_x), int(top * scale_y),
               int((left + width) * scale_x), int((top + height) * scale_y))
        origin_x, origin_y = getattr(self, "_origin", (0, 0))
        self._remember()
        self._origin = (origin_x + int(left * scale_x), origin_y + int(top * scale_y))
        self._image = self._image.crop(box)
        self._image_name = f"{self._image_name} (裁剪)"
        return {"ok": True, "name": self._image_name,
                "width": self._image.width, "height": self._image.height,
                "reloadable": bool(getattr(self, "_image_path", "")),
                "preview": self._preview_uri(self._image)}

    # -- recognise --------------------------------------------------------
    def recognize(self, lang: str | None = None) -> dict:
        if self._image is None:
            return {"ok": False, "error": "还没有图片"}
        lang = lang or self.settings.get("lang", "cht")
        try:
            engine = self._engine_for(lang)
            started = time.time()
            lines = engine.run(self._image)
            elapsed = time.time() - started
        except Exception as exc:  # surfaced to the page, not swallowed
            return {"ok": False, "error": str(exc)}

        from CORE.color import colors_for

        import numpy as np

        # Sample the ink before the coordinates are shifted: the sampler reads
        # the image at the line's own position, and the offset moves it off.
        colours = colors_for(np.array(self._image), lines)

        # 裁剪出来的图，坐标是相对裁剪框的。加回原点，用户选“原位置”时
        # 文字才会回到它在屏幕上的位置，而不是图片左上角。
        ox, oy = getattr(self, "_origin", (0, 0))
        if ox or oy:
            lines = [Line(text=l.text, x=l.x + ox, y=l.y + oy, w=l.w, h=l.h, score=l.score)
                     for l in lines]

        self._lines = lines
        self._paragraphs = group_paragraphs(lines)

        # Keyed by identity *after* the rebuild. Keying the colours by the line
        # objects that existed before it meant every lookup missed, and every
        # line came out black — but only on a cropped image, which is the path
        # the 框选截图 button takes.
        colour_of = {id(line): colour for line, colour in zip(lines, colours) if colour}
        self._colour_of = colour_of

        line_items = []
        for index, line in enumerate(lines):
            line_items.append({
                "text": line.text.strip(),
                "size": estimate_size(line),
                "box": [line.x, line.y, line.w, line.h],
                "lines": 1,
                "colour": colour_of.get(id(line), "#000000"),
            })

        out = []
        for para in self._paragraphs:
            text = paragraphs_to_text([para])
            box = Box.union_of([Box(l.x, l.y, l.w, l.h) for l in para])
            inked = [colour_of[id(l)] for l in para if id(l) in colour_of]
            out.append({
                "text": text,
                "size": max(estimate_size(l) for l in para),
                "box": [box.left, box.top, box.width, box.height],
                "lines": len(para),
                "colour": inked[0] if inked else "#000000",
            })
        self._line_items = line_items
        return {"ok": True, "paragraphs": out, "lineItems": line_items,
                "seconds": round(elapsed, 1), "lines": len(lines)}

    # -- text tools -------------------------------------------------------
    def export_json(self, paragraphs: list[dict], options: dict | None = None) -> dict:
        """Write the text, its geometry, its ink colour and its size as JSON.

        The payload is the interface between this app and an agent that cannot
        look at the picture, so it carries two copies of every box — pixels and
        a 0-1 fraction — and says ``null`` for anything it does not actually
        know. See ``CORE/textdata.py`` for the schema.

        Text comes from the page, not from the recogniser: what the user edited
        is what gets exported. A line's geometry is only carried when its text
        still matches the recognised line, because geometry attached to text
        that has changed is a wrong answer that looks like a right one.
        """
        from CORE.textdata import build_payload, save as save_payload

        options = options or {}
        items = [p for p in paragraphs if (p.get("text") or "").strip()]
        if not items:
            return {"ok": False, "error": self._m("export_empty")}

        rows: list[dict] = []
        for index, para in enumerate(paragraphs):
            text = (para.get("text") or "").strip()
            if not text:
                continue
            box = para.get("box")
            origin = self._paragraphs[index] if index < len(self._paragraphs) else []
            lines = []
            for number, line_text in enumerate(text.split("\n")):
                source = origin[number] if number < len(origin) else None
                # Same sentence on both sides is the only condition under which
                # the recognised box still describes this text.
                same = source is not None and source.text.strip() == line_text.strip()
                lines.append({
                    "text": line_text,
                    "bbox": (source.x, source.y, source.w, source.h) if same else None,
                    "score": getattr(source, "score", None) if same else None,
                    "color": self._colour_of.get(id(source)) if same else None,
                })
            rows.append({
                "text": text,
                "bbox": tuple(box) if box else None,
                "color": para.get("colour"),
                "font_size_px": para.get("size") or None,
                "lines": lines,
            })

        lang = options.get("lang") or self.settings.get("lang", "cht")
        model = ("chinese_cht_PP-OCRv3_rec_mobile.onnx" if lang == "cht"
                 else "rapidocr-onnxruntime bundled models")
        width, height = (self._image.width, self._image.height) if self._image else (0, 0)
        payload = build_payload(
            source=self._image_name, image_size=(width, height), lang=lang,
            model=model, paragraphs=rows, image_path=self._image_path,
        )

        path = options.get("path")
        if not path:
            import webview

            stem = Path(self._image_name).stem if self._image_name else "ocr_textdata"
            chosen = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG, save_filename=f"{stem or 'ocr_textdata'}.json",
                file_types=("JSON (*.json)", "All files (*.*)"))
            if isinstance(chosen, (list, tuple)):
                chosen = chosen[0] if chosen else None
            if not chosen:
                return {"ok": False, "cancelled": True}
            path = chosen
        try:
            save_payload(payload, str(path))
        except OSError as exc:
            return {"ok": False, "error": self._m("file_write", err=exc)}
        return {"ok": True, "path": str(path),
                "paragraphs": payload["counts"]["paragraphs"],
                "lines": payload["counts"]["lines"]}

    def convert(self, text: str, direction: str) -> dict:
        try:
            out, changed = convert_text(text, direction)
            return {"ok": True, "text": out, "changed": changed}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def import_textdata(self) -> dict:
        """Read a text-data JSON and hand its blocks back to the page.

        The point of this menu is the workflow where the text is translated
        elsewhere: export here, translate in whatever the user prefers, import
        back, write. Only the text is taken — the geometry belongs to the picture
        that is still loaded, so a JSON without boxes is enough.
        """
        import webview

        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("Text data (*.json)", "所有文件 (*.*)"),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        path = result[0] if isinstance(result, (list, tuple)) else result
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": f"读不了这个文件：{exc}"}

        blocks = data.get("paragraphs") if isinstance(data, dict) else data
        if not isinstance(blocks, list):
            return {"ok": False, "error": "这个 JSON 里没有 paragraphs 数组"}

        texts: list[str] = []
        for item in blocks:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                texts.append(str(item.get("text", "")))
            else:
                texts.append("")
        return {"ok": True, "texts": texts, "path": str(path)}

    # -- host -------------------------------------------------------------
    @staticmethod
    def process_running(image_name: str) -> bool:
        """True when a process with this executable name exists.

        Matched on the image name, not on window titles. An earlier version
        looked for the word in window titles, and a File Explorer window sitting
        in a folder called "photocraft" was enough to make the app claim the
        program was already running.
        """
        import ctypes
        from ctypes import wintypes

        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == wintypes.HANDLE(-1).value:
            return False

        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                return False
            wanted = image_name.lower()
            while True:
                if entry.szExeFile.lower() == wanted:
                    return True
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    return False
        finally:
            kernel32.CloseHandle(snapshot)
        return False

    def connect(self) -> dict:
        """Make a control channel available and return its port.

        Whoever opened it, the parameters are the same: a fixed port and a token
        file recorded in settings. So an instance the user started from the
        generated ``_OCR.bat`` is used as-is, and only when nothing is listening
        do we start one ourselves.
        """
        raw = (self.settings.get("host_dir") or "").strip()
        if not raw:
            return {"ok": False,
                    "error": self._m("no_host")}
        host_dir = host_folder(raw)
        if not host_dir.exists():
            return {"ok": False, "error": self._m("no_dir", path=host_dir)}
        exe = host_dir / "photocraft.exe"
        if not exe.exists():
            return {"ok": False,
                    "error": self._m("no_exe", path=host_dir)}

        port = int(self.settings.get("port") or 8125)
        token = self.settings.get("token") or str(EXE_DIR / "control.token")

        if port_open(port):
            if Path(token).exists():
                self._port, self._token = port, token
                return {"ok": True, "port": port, "attached": True}
            return {
                "ok": False,
                "error": (
                    "控制口 " + str(port) + " 开着，但找不到它的 token 文件：" + str(token) + "\n"
                    "如果那个实例是用别的 token 启动的，请关掉它，改用本程序生成的启动脚本。"
                ),
            }

        if self._app_proc is not None and self._app_proc.poll() is None:
            self._port, self._token = port, token
            return {"ok": True, "port": port}

        if self.process_running("photocraft.exe"):
            return {
                "ok": False,
                "error": (
                    "PhotoCraft 已经开着，但它没有控制口 —— 手动双击打开的实例不会监听"
                    "控制口，任何程序都连不上。\n"
                    "请关掉它，然后双击本程序生成的 photocraft_OCR.bat 再试。"
                ),
            }

        Path(token).parent.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._app_proc = subprocess.Popen(
            [str(exe), "--control", str(port), "--control-token-file", token],
            creationflags=flags,
        )
        if not wait_for_port(port):
            return {"ok": False, "error": self._m("port_late", port=port)}
        self._port, self._token = port, token
        return {"ok": True, "port": port, "started": True}

    def generate_launch_script(self, desktop: bool = True) -> dict:
        """Write a .bat next to the host that starts it with the control channel.

        Three reasons this beats starting the process from inside this app: the
        user keeps a visible shortcut to their own install, no second instance is
        ever started behind their back, and the parameters are written down where
        they can be inspected instead of living in a settings blob.

        With ``desktop`` the same script also gets a shortcut on the desktop —
        the folder it lives in is one the user should never have to visit.
        """
        host_dir = host_folder(self.settings.get("host_dir"))
        exe = host_dir / "photocraft.exe"
        if not exe.exists():
            return {"ok": False, "error": self._m("need_dir")}

        port = int(self.settings.get("port") or 8125)
        token = self.settings.get("token") or str(EXE_DIR / "control.token")
        bat = host_dir / "photocraft_OCR.bat"
        lines = [
            "@echo off",
            "chcp 65001 >nul",
            f'start "" "{exe}" --control {port} --control-token-file "{token}"',
        ]
        body = "\r\n".join(lines) + "\r\n"
        try:
            with bat.open("w", encoding="utf-8", newline="") as handle:
                handle.write(body)
        except OSError as exc:
            return {"ok": False, "error": self._m("bat_write", err=exc)}

        result: dict = {"ok": True, "path": str(bat), "port": port,
                        "name": bat.name}
        if desktop:
            try:
                shortcut = make_desktop_shortcut(
                    "PhotoCraft_OCR", bat, workdir=host_dir,
                    # The host's own icon, so the desktop entry looks like the
                    # application it starts rather than a cmd window.
                    icon=str(exe),
                    description="以控制端口启动 PhotoCraft，供 ArtCraft OCR 写入")
                result["shortcut"] = str(shortcut)
                result["shortcut_name"] = shortcut.name
            except ShortcutError as exc:
                # The script is the part that matters; the shortcut is a
                # convenience. Say so instead of failing the whole action.
                result["warning"] = f"启动脚本已生成，桌面快捷方式没建成：{exc}"
        return result

    def create_own_shortcut(self) -> dict:
        """Put this program on the desktop.

        The build output is a folder with no installer, so without this the only
        way back to the app is remembering where it was unpacked.
        """
        exe = Path(sys.executable).resolve()
        try:
            path = make_desktop_shortcut(
                "ArtCraftOCR", exe, workdir=exe.parent,
                icon=str(exe), description="ArtCraft OCR")
        except ShortcutError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(path), "name": path.name}

    def write(self, paragraphs: list[dict], options: dict | None = None) -> dict:
        if not paragraphs:
            return {"ok": False, "error": self._m("no_content")}
        # One adapter exists. Saying so is better than accepting the name and
        # writing into PhotoCraft anyway, which is what the old selector did.
        target = (options or {}).get("target", "PhotoCraft")
        if target != "PhotoCraft":
            return {"ok": False,
                    "error": self._m("only_pc", target=target)}
        connected = self.connect()
        if not connected.get("ok"):
            return connected

        from ADAPTERS.photocraft import Bridge, PhotoCraft, find_cli

        host_dir = host_folder(self.settings.get("host_dir"))
        options = options or {}
        scale = float(options.get("scale", self.settings.get("scale", 100))) / 100.0
        font = options.get("font", self.settings.get("font", "Microsoft YaHei"))
        anchor = options.get("anchor", self.settings.get("anchor", "原位置"))
        follow = bool(options.get("follow_colour", True))
        note = ""
        no_geometry = not any(p.get("box") for p in paragraphs)
        if no_geometry:
            # 手打的文字没有原图坐标，锚点偏移（左上/右下…）无从算起 —— 之前这里
            # 把锚点改成「左上」，结果仍会去算偏移，而零尺寸的框让右上/右下算出一个
            # 把整段推到画布外的量。没有坐标，就按堆叠位置写，不做任何偏移。
            anchor = "原位置"
            note = "这些文字没有原图位置（手打的），从左上逐段往下排。"
        forced_size = int(options.get("size") or 0)
        paragraph = options.get("mode") == "para"
        default_colour = options.get("colour", "#000000")

        from CORE.plan import plan_items

        items, custom_size_used = plan_items(
            paragraphs, self._paragraphs, self._colour_of,
            scale=scale, forced_size=forced_size, para_mode=paragraph,
            follow=follow, default_colour=default_colour,
            font=self.settings.get("font", "Microsoft YaHei"),
        )

        try:
            with Bridge(str(find_cli(host_dir)), self._port, self._token) as bridge:
                pc = PhotoCraft(bridge)
                # 没有文档时所有写入都会被拒；有文档时这里什么也不做。
                pc.ensure_document(1920, 1080)

                if paragraph:
                    # A frame of zero width comes from text that was typed rather
                    # than recognised; giving it a real frame is the difference
                    # between a paragraph and an invisible sliver.
                    canvas = pc.document_rect() or Box(0, 0, 1920, 1080)
                    fixed = []
                    for text, box, colour, size, fit in items:
                        if box.width <= 0 or box.height <= 0:
                            width = max(120.0, canvas.width - 2 * 40)
                            box = Box(box.left, box.top, width, max(size * 1.8, 40.0))
                        fixed.append((text, box, colour, size, fit))
                    items = fixed
                written_ids: list[int] = []
                done = pc.place_all(
                    items,
                    size=int(round((forced_size or paragraphs[0].get("size", 12)) * scale)),
                    font=font,
                    color=default_colour,
                    anchor=anchor,
                    # A size the user picked anywhere is not negotiable by the
                    # width-fitting loop.
                    force_size=bool(forced_size or custom_size_used),
                    paragraph=paragraph,
                )
                written_ids = [d.layer for d in done if d.error is None and d.layer]
                group_name = None
                if written_ids:
                    index = int(self.settings.get("group_index", 0)) + 1
                    self.settings["group_index"] = index
                    group_name = f"OCRtext{index:02d}"
                    try:
                        pc.group_layers(written_ids, group_name)
                    except Exception:
                        group_name = None
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "port": self._port,
            "group": group_name,
            "note": note,
            "written": sum(1 for d in done if d.error is None),
            "failed": [{"text": d.text, "error": d.error} for d in done if d.error],
        }

    def fonts(self) -> dict:
        """Fonts offered in the picker.

        A fixed list rather than an enumeration: these are the faces a Chinese
        desktop Windows install always has, plus the one a build may bundle.
        Listing every installed font would need a platform call for no benefit.
        """
        return {"ok": True, "fonts": [
            "Microsoft YaHei", "SimSun", "SimHei", "KaiTi", "FangSong",
            "Noto Sans SC", "Segoe UI",
        ]}

    def open_doc(self, kind: str) -> dict:
        """Show a document the About panel points at.

        License and notices open the files that ship beside the program; GitHub
        has no address until the repository is published, and saying so is better
        than opening a page that does not exist.
        """
        targets = {
            "license": ROOT / "LICENSE",
            "notices": ROOT / "DOCS" / "LICENSES.md",
        }
        if kind == "github":
            return {"ok": False, "error": self._m("github")}
        path = targets.get(kind)
        if path is None or not path.exists():
            return {"ok": False, "error": self._m("file_missing", path=path or kind)}
        try:
            os.startfile(str(path))  # noqa: S606 - opening our own shipped file
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(path)}

    def about(self) -> dict:
        """Where this copy runs from — the only reliable way to tell builds apart."""
        return {"ok": True,
                "text": "ArtCraft OCR " + VERSION + "\n程序：" + sys.executable}

    def current_settings(self) -> dict:
        return {"ok": True,
                "host_dir": str(host_folder(self.settings.get("host_dir"))),
                "host_exe": str(host_folder(self.settings.get("host_dir")) / "photocraft.exe"),
                "port": self.settings.get("port", 8125),
                "token": self.settings.get("token") or str(EXE_DIR / "control.token"),
                "lang": self.settings.get("lang", "ch"),
                "ui_lang": self.settings.get("ui_lang", "en"),
                "font": self.settings.get("font", "Microsoft YaHei"),
                "busy": self.process_running("photocraft.exe")}

    def save_settings(self, values: dict) -> dict:
        for key in ("host_dir", "port", "token", "ui_lang"):
            if key in values and values[key] not in (None, ""):
                self.settings[key] = (str(host_folder(values[key]))
                                      if key == "host_dir" else values[key])
        try:
            self.settings["port"] = int(self.settings.get("port", 8125))
        except (TypeError, ValueError):
            self.settings["port"] = 8125
        try:
            SETTINGS.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"写不了设置文件：{exc}"}
        return {"ok": True, "host_dir": str(host_folder(self.settings.get("host_dir"))),
                "port": self.settings["port"]}

    def pick_host(self) -> dict:
        """Ask for the host executable, not its folder.

        A file picker lets the owner point straight at ``photocraft.exe``; the
        stored value stays the directory, because every later path is built as
        ``host_dir / "photocraft.exe"``.
        """
        import webview

        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            # The filter must be "Description (*.ext)" — a description without a
            # wildcard makes the Windows dialog fail to parse it, which arrives
            # in the page as 内部错误 instead of a file picker.
            file_types=("PhotoCraft (*.exe)", "所有文件 (*.*)"),
        )
        if not result:
            return {"ok": False}
        path = result[0] if isinstance(result, (list, tuple)) else result
        folder = str(Path(path).parent)
        self.settings["host_dir"] = folder
        try:
            SETTINGS.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        except OSError:
            pass
        return {"ok": True, "host_dir": folder, "exe": path}

    def clear(self) -> dict:
        """Reset everything, image included.

        Clearing only the text left an image on screen with nothing recognised
        from it, which reads as "the clear button did not work".
        """
        self._image = None
        self._image_name = ""
        self._lines = []
        self._paragraphs = []
        self._origin = (0, 0)
        return {"ok": True}

    def quit_app(self) -> dict:
        import webview

        for window in list(getattr(webview, "windows", []) or []):
            try:
                window.destroy()
            except Exception:
                pass
        return {"ok": True}

    def shutdown(self) -> None:
        if self._app_proc and self._app_proc.poll() is None:
            self._app_proc.terminate()
        for window in getattr(sys.modules.get("webview"), "windows", []) or []:
            window.destroy()


def work_area() -> tuple[int, int, int, int]:
    """Primary monitor work area, taskbar excluded.

    A window centred on the full screen can end up under the taskbar, and letting
    the platform choose the position puts it on whichever monitor it likes — both
    have been seen on this project. Asking Windows for the work area is the only
    answer that accounts for the taskbar.
    """
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    return 0, 0, 1920, 1080


def selftest(image_path: str, out_path: str) -> int:
    """Run the engine headlessly and write the outcome.

    Exists because a frozen build can pass every import check and still fail when
    the recogniser is first used: rapidocr resolves its stage modules by short
    name. Writing to a file rather than stdout keeps this usable in a windowed
    build, where there is no console.
    """
    api = Api()
    api._main_window = None
    try:
        api._load_image(image_path)
        result = api.recognize("ch")
    except Exception as exc:  # noqa: BLE001 - the point is to report it
        Path(out_path).write_text(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
                                  encoding="utf-8")
        return 1
    # Packaging risk that only shows up at runtime: the region overlay needs
    # tkinter, and a build that dropped it fails the first time someone presses
    # 框选截图 rather than at startup.
    try:
        from APP import overlay  # noqa: F401

        result["overlay"] = True
    except Exception as exc:  # noqa: BLE001
        result["overlay"] = f"unavailable: {exc}"

    # Same class of risk for 简↔繁: the tables are data files, and a build that
    # dropped them converts nothing while looking like it ran.
    try:
        _, changed = convert_text("龙", "s2t")
        result["convert"] = "ok" if changed == 1 else f"changed {changed}"
    except Exception as exc:  # noqa: BLE001
        result["convert"] = f"unavailable: {exc}"

    Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0 if result.get("ok") else 1


def _fatal(message: str) -> int:
    """Show a readable failure in a windowed build.

    Without a console, the only alternative is whatever the toolkit shows, and
    pywebview answers a missing page with a 404 in a browser-like view — which
    tells the user nothing about which file is missing.
    """
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "ArtCraft OCR", 0x10)
    except Exception:
        pass
    return 1


def main() -> int:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        return selftest(sys.argv[index + 1], sys.argv[index + 2])

    if not (UI_DIR / "index.html").exists():
        return _fatal(
            "界面文件缺失，程序无法启动。\n\n"
            "缺少：" + str(UI_DIR / "index.html") + "\n\n"
            "打包时 APP/ui 没有被复制进产物，请重新打包。"
        )

    import webview

    api = Api()
    api._main_window = None
    window = webview.create_window(
        f"ArtCraft OCR {VERSION}",
        str(UI_DIR / "index.html"),
        js_api=api,
        width=1580,
        height=1050,
        min_size=(1200, 760),
        background_color="#170f16",
    )
    api._main_window = window

    if os.environ.get("ARTCRAFT_AUTOSETTINGS"):
        def _open_settings() -> None:
            time.sleep(4)
            report = Path(tempfile.gettempdir()) / "artcraft-open-settings.txt"
            try:
                window.evaluate_js("openSettings()")
                time.sleep(1.5)   # openSettings is async; give it a turn
                shown = window.evaluate_js("document.getElementById('dialog').style.display")
                report.write_text(f"dialog display={shown}", encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                report.write_text(f"error: {exc}", encoding="utf-8")

        threading.Thread(target=_open_settings, daemon=True).start()

    if os.environ.get("ARTCRAFT_AUTOREGION"):
        def _auto() -> None:
            time.sleep(3)
            api.grab_region()

        threading.Thread(target=_auto, daemon=True).start()

    webview.start(debug=bool(os.environ.get("ARTCRAFT_DEBUG")))
    api.shutdown()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # one readable line for a missing runtime, not a stack trace
        traceback.print_exc()
        raise SystemExit(1)
