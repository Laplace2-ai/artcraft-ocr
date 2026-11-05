# SPDX-License-Identifier: Apache-2.0
"""Checks that the interface actually runs.

Two failures this exists for, both shipped once:

* a syntax error in the page's script — nothing binds, so every button and menu
  is dead, and it looks like "the build is broken" rather than "one bad line";
* a handler bound to an API method that does not exist on the Python side, which
  fails only when clicked.

Runs without the app: the page is loaded in headless Chrome with a stub for
``window.pywebview``, then clicked through. Skipped when node or Chrome is absent.

Internal-context scan note: this file contains absolute paths, and they are
whitelisted for one reason — they are where a browser is installed on a Windows
machine, not where this project lives. Registered here because a whitelist entry
without a written reason is how a real leak gets waved through.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "APP" / "ui" / "index.html"

CHROME_CANDIDATES = [
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]

STUB = (
    "<script>window.pywebview={api:new Proxy({},{get:()=>async()=>({ok:true,"
    "paragraphs:[],lineItems:[],lines:0,seconds:0,written:0,failed:[],text:'x',"
    "host_dir:'C:/x',port:8125,busy:false,path:'C:/x/photocraft_OCR.bat'})})};</script>\n"
)

PROBE = """<script>
window.addEventListener("load", () => {
  const log = []; const $ = (id) => document.getElementById(id); const pop = $("popover");
  const ok = (n, c) => log.push((c ? "PASS " : "FAIL ") + n);
  try {
    document.querySelector('[data-menu="file"]').click();
    ok("file menu", pop.style.display === "block" && pop.children.length > 2);
    document.querySelector('[data-menu="help"]').click();
    ok("help menu", pop.style.display === "block");
    $("lang").click();
    ok("language list", pop.children.length === 3);
    $("anchor").click();
    ok("anchor list", pop.children.length === 6);
    const sizeFields = document.querySelectorAll(".mini-num");
    ok("per-paragraph size field",
       sizeFields.length >= 1 && sizeFields[0].min === "6" && sizeFields[0].max === "200");
    ok("no top-bar size preset", !document.getElementById("sizeInput"));
    $("btnClear").click();

    // A portrait picture used to run out of the bottom of the pane: the grid row
    // was content-sized, so max-height:100% resolved against an indefinite height
    // and the browser ignored it. width/height attributes give the element an
    // intrinsic size without waiting for a load, so this measures layout only.
    // Help → About used to throw "openAbout is not defined": the menu called a
    // function that was never written, and nothing clicked that menu before
    // shipping. This is the check that would have caught it.
    document.querySelector('[data-menu="help"]').click();
    const aboutItem = [...pop.children].find((el) => el.textContent.includes("About") ||
                                                    el.textContent.includes("关于"));
    aboutItem.click();
    ok("about panel opens", $("aboutDialog").style.display === "block");
    $("btnAboutClose").click();
    ok("about panel closes", $("aboutDialog").style.display === "none");

    const pane = $("preview");
    const tall = document.createElement("img");
    tall.width = 1000; tall.height = 3000;
    pane.appendChild(tall);
    const paneBox = pane.getBoundingClientRect();
    const tallBox = tall.getBoundingClientRect();
    ok("portrait image fits the pane",
       tallBox.height <= paneBox.height + 1 && tallBox.width <= paneBox.width + 1);
    tall.remove();
  } catch (e) { log.push("THREW " + e.message); }
  const bad = log.filter((l) => !l.startsWith("PASS"));
  document.title = bad.length ? "FAILED " + bad.join("; ") : "ALLPASS " + log.length;
});
</script>
"""


def chrome() -> str | None:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def main() -> int:
    source = PAGE.read_text(encoding="utf-8")
    blocks = re.findall(r"<script>(.*?)</script>", source, re.S)
    if not blocks:
        print("FAIL no script block found")
        return 1

    work = Path(tempfile.mkdtemp())
    script = work / "main.js"
    script.write_text(max(blocks, key=len), encoding="utf-8")

    node = shutil.which("node")
    if node:
        result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        if result.returncode != 0:
            print("FAIL javascript syntax:\n" + (result.stderr or "")[:600])
            return 1
        print("PASS javascript syntax")

    browser = chrome()
    if browser is None:
        print("SKIP dom probe (no Chrome or Edge found)")
        return 0

    for name in ("ui.css", "mark.png"):
        shutil.copy(ROOT / "APP" / "ui" / name, work / name)
    page = source.replace("<script>\nconst $ =", STUB + "<script>\nconst $ =", 1)
    page = page.replace("</body>", PROBE + "</body>")
    target = work / "index.html"
    target.write_text(page, encoding="utf-8")

    result = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=4000", "--dump-dom", target.as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    match = re.search(r"<title>([^<]*)</title>", result.stdout or "")
    outcome = match.group(1) if match else "no title"
    if outcome.startswith("ALLPASS"):
        print("PASS dom probe:", outcome)
        return 0
    print("FAIL dom probe:", outcome)
    return 1


if __name__ == "__main__":
    sys.exit(main())
