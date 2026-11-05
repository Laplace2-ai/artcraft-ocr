# SPDX-License-Identifier: Apache-2.0
"""Full-screen region picker.

A separate toolkit window rather than a WebView one: pywebview's window would be
created but never covered the desktop on this backend (two attempts, measured by
screen brightness before and after), so a selection made in it would have been
made blind.

The screenshot is dimmed before being drawn, and the rectangle under the cursor
is redrawn from the original. That keeps the selection readable without any
per-frame compositing.
"""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

DIM = 0.45


def pick_region() -> Image.Image | None:
    """Show the overlay and return the cropped region, or ``None`` if cancelled."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        vx = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        vh = user32.GetSystemMetrics(79)
    except Exception:
        vx = vy = 0
        vw, vh = 1920, 1080

    from PIL import ImageGrab

    full = ImageGrab.grab(all_screens=True).convert("RGB")

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{vw}x{vh}+{vx}+{vy}")
    root.configure(cursor="crosshair", bg="#000000")

    dimmed = Image.eval(full, lambda v: int(v * DIM))
    dim_photo = ImageTk.PhotoImage(dimmed)
    full_photo = ImageTk.PhotoImage(full)

    canvas = tk.Canvas(root, width=vw, height=vh, highlightthickness=0, bd=0, bg="#000000")
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, image=dim_photo, anchor="nw")
    bright = canvas.create_image(0, 0, image=full_photo, anchor="nw", state="hidden")

    hint = canvas.create_text(
        vw // 2, 40, text="拖动选择区域 · Esc 取消",
        fill="#ffdb92", font=("Microsoft YaHei", 16),
    )

    state: dict[str, object] = {"start": None, "rect": None, "done": False}

    def clamp(x: int, y: int) -> tuple[int, int]:
        return max(0, min(vw, x)), max(0, min(vh, y))

    def on_press(event: tk.Event) -> None:
        state["start"] = clamp(event.x, event.y)
        canvas.itemconfigure(bright, state="hidden")

    def on_drag(event: tk.Event) -> None:
        start = state.get("start")
        if not start:
            return
        x, y = clamp(event.x, event.y)
        x0, y0 = min(start[0], x), min(start[1], y)
        x1, y1 = max(start[0], x), max(start[1], y)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return
        patch = full.crop((x0, y0, x1, y1))
        photo = ImageTk.PhotoImage(patch)
        state["patch"] = photo  # keep a reference or Tk drops the image
        canvas.itemconfigure(bright, image=photo, state="normal")
        canvas.coords(bright, x0, y0)
        canvas.delete("box")
        canvas.create_rectangle(x0, y0, x1, y1, outline="#00f7ff", width=2, tags="box")
        state["rect"] = (x0, y0, x1, y1)

    def on_release(event: tk.Event) -> None:
        state["done"] = True
        root.destroy()

    def cancel(_event: tk.Event | None = None) -> None:
        state["rect"] = None
        state["done"] = True
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", cancel)
    canvas.focus_set()

    try:
        root.mainloop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    rect = state.get("rect")
    if not rect:
        return None
    x0, y0, x1, y1 = rect  # type: ignore[misc]
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return full.crop((x0, y0, x1, y1))
