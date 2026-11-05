# SPDX-License-Identifier: Apache-2.0
"""Build ArtCraft OCR — and refuse to build when the tests fail.

The reason this exists rather than a documented command: a command in a document
is a thing a person can skip, and the skip is invisible afterwards. Here the
tests run first, and a failure exits before PyInstaller is ever started, so a
broken build cannot be produced by following the instructions.

Run it with the build interpreter, from anywhere:

    .venv-build\\Scripts\\python.exe PACKAGING\\build.py

``--check-only`` runs the gates without packaging, for a quick answer.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "PACKAGING" / "out"
WORK = ROOT / "PACKAGING" / "build2"

GATES = [
    ("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "TESTS"]),
    ("interface check", [sys.executable, "TESTS/check_ui.py"]),
    # The tests exercise CORE and the adapters; none of them import the shell.
    # An indentation error in APP/main.py therefore passed every gate and left a
    # build that could not start — found only by launching it by hand.
    ("shell imports", [sys.executable, "-c", "import APP.main"]),
]


def run_gate(name: str, command: list[str], *, no_skips: bool = False) -> bool:
    print(f"[gate] {name}: {' '.join(command[1:])}")
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    output = (done.stdout or "") + (done.stderr or "")
    print(output.rstrip())
    if done.returncode != 0:
        print(f"[gate] FAILED — {name} exited {done.returncode}. No package was built.")
        return False
    if no_skips:
        skipped = re.search(r"skipped=(\d+)", output)
        if skipped and int(skipped.group(1)) > 0:
            # A skipped test is an unverified path, and the build interpreter has
            # every dependency, so here it can only mean the gate ran somewhere it
            # should not have. Reporting green on 43 tests of 46 is the same
            # failure as reporting green on none.
            print(f"[gate] FAILED — {skipped.group(1)} test(s) skipped under "
                  f"{sys.executable}.\n"
                  "        Run the build with the build venv:\n"
                  "        .venv-build\\Scripts\\python.exe PACKAGING\\build.py")
            return False
    print(f"[gate] ok — {name}")
    return True


def publish(stage: Path, out: Path) -> int:
    """Swap the finished package into place, or leave both alone.

    Renaming a directory that holds a running executable fails on Windows — which
    is the point: the caller gets a complete build in the staging folder and the
    user keeps the package they were running, instead of a half-deleted one.
    """
    if not out.exists():
        stage.rename(out)
        print(f"[build] ok — {out}")
        return 0

    previous = out.with_name(out.name + ".previous")
    if previous.exists():
        shutil.rmtree(previous, ignore_errors=True)
    try:
        out.rename(previous)
    except OSError:
        print(f"[build] built, but {out.name} is in use (a running ArtCraftOCR.exe).")
        print(f"        The new package is complete at: {stage}")
        print("        Close the running copy, then run this again.")
        return 1
    stage.rename(out)
    shutil.rmtree(previous, ignore_errors=True)
    print(f"[build] ok — {out}")
    return 0


def main(argv: list[str]) -> int:
    check_only = "--check-only" in argv

    for name, command in GATES:
        if not run_gate(name, command, no_skips=(name == "unit tests")):
            return 1

    if check_only:
        print("[build] gates passed; nothing packaged (--check-only)")
        return 0

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] PyInstaller is not installed in this interpreter.\n"
              "        Use the build venv: .venv-build\\Scripts\\python.exe PACKAGING\\build.py")
        return 1

    # Build beside `out`, never into it. PyInstaller deletes the dist directory
    # before it writes anything, so a build that then fails — a running exe holds
    # ArtCraftOCR.exe open — leaves the user with a half-emptied package that
    # starts to "界面文件缺失". That happened on 2026-11-05. Staging makes the
    # swap the only step that can fail, and it fails with `out` intact.
    stage = ROOT / "PACKAGING" / ".stage"
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)

    command = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--distpath", str(stage), "--workpath", str(WORK),
        str(ROOT / "PACKAGING" / "artcraft-ocr.spec"),
    ]
    print("[build] " + " ".join(command[1:]))
    # The exit code is the result. Grepping the log for "completed successfully"
    # once hid a COLLECT failure and shipped a package with no APP/ui in it.
    code = subprocess.run(command, cwd=ROOT).returncode
    if code != 0:
        print(f"[build] FAILED — PyInstaller exited {code}. {OUT.name} was not touched.")
        return code

    exe = stage / "ArtCraftOCR" / "ArtCraftOCR.exe"
    if not (stage / "ArtCraftOCR" / "_internal" / "APP" / "ui" / "index.html").exists():
        print("[build] FAILED — the package has no APP/ui; it would start to a 404 window.")
        return 1
    # A shippable folder is not just the binary: the licence, the notice, the third-party
    # bundle and the two READMEs have to travel with it, or the zip goes out incomplete —
    # which is exactly what happened the first time this was zipped by hand.
    for item in ("LICENSE", "NOTICE", "README.md", "README.zh-CN.md", "CHANGELOG.md",
                 "THIRD-PARTY", "DOCS/images"):
        source = ROOT / item
        target = stage / "ArtCraftOCR" / item
        if not source.exists():
            print(f"[build] FAILED — {item} is missing; it belongs in the release folder.")
            return 1
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)

    print(f"[build] ok — {exe}")
    return publish(stage, OUT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
