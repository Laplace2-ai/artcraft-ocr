# RELEASE CHECKLIST

> Every item is a gate, not a suggestion. A row is only "done" when the evidence column
> shows something a second person could re-run. If an item cannot be evidenced, it is not done.
>
> Items are ordered as they are checked, not by importance. Nothing ships with an open **Yes**.

## 1. Licence

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 1.1 | Every asset in the build has a row in `DOCS/LICENSES.md` | row exists, with source + clause | **Yes** |
| 1.2 | No third-party text is paraphrased — licence files ship verbatim in `THIRD-PARTY/` | `ls THIRD-PARTY/`, diff against the source files | **Yes** |
| 1.3 | Model weights are not committed; the build fetches them and verifies checksums | checksums in `LICENSES.md` §5 match the packaged files | **Yes** |
| 1.4 | `NOTICE` contains no invented attribution | read `NOTICE`; compare against the components that actually carry a NOTICE | **Yes** |
| 1.5 | No copyleft in the dependency tree | `importlib.metadata` licence scan of the build venv | **Yes** |

## 2. Internal-context scan

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 2.1 | Zero hits for internal identifiers in tracked files | scan command below, run on `git ls-files` | **Yes** |
| 2.2 | Zero hits in user-visible strings, not just files | AST extract of string literals, then scan those | **Yes** |
| 2.3 | No absolute local paths baked into code, config or launcher text | same scan, path pattern | **Yes** |

The token list itself is not stored here: a checklist that spelled it out would match itself and
defeat 2.1. That is not an excuse to leave the method vague — the method is below, in enough
detail that a new maintainer can rebuild the list without asking anyone.

### 2.4 What counts as an internal identifier

Derive the list from these five categories. Anything in them is a violation when it appears in a
tracked file:

1. **Organisational names** that are not the public copyright holder.
2. **Internal role names.** These are short capitalised two-letter tokens. Match them with word
   boundaries **and** case sensitivity — two-letter tokens collide constantly with real words,
   so an unbounded or case-insensitive pattern produces false hits that get dismissed, and a
   dismissed hit is how a real one slips through.
3. **Absolute local paths** from any maintainer's machine, in code, config or user-facing text.
4. **Internal script and directory names** that the release does not contain.
5. **Hardcoded internal port numbers** presented as if they were part of the product.

### 2.5 How to run it

```sh
# Mechanical categories (3-5) need no roster — these run as-is.
# The trailing [^\\/] is not decoration: without it, "https://" matches the drive-letter
# pattern and every URL in the documentation becomes a false hit.
git grep -n -I -E '[A-Za-z]:[\\/][^\\/]|127\.0\.0\.1:[0-9]{4}' -- .

# Identity names (1-2): build the alternation from the current roster, then:
git grep -n -I -w -F -e "NAME1" -e "NAME2" -- .

# User-visible strings (2.2): extract string literals first, then scan the extract,
# otherwise a name split across an f-string is invisible to a plain grep.
```

Rules for the patterns:

- **Word-bounded (`-w`, `\b`) and case-sensitive** for any token of three characters or fewer.
  Without this, a two-letter name matches inside ordinary words and the check becomes noise
  everyone learns to ignore.
- **Whitelist explicitly, and justify each entry.** A whitelist entry is a claim that the match
  is a real word, so it belongs in the commit message, not silently in a config. If an entry
  cannot be explained in one line, it is not a whitelist entry — it is a leak.
- **Two passes, both clean.** Scan, fix, scan again. One clean pass proves nothing: the first
  pass is what told you where to look.

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 2.4 | The scan fires on a known-positive control | plant one line containing a forbidden token, confirm it is reported, remove it | **Yes** |
| 2.5 | Two consecutive scans return zero hits | paste both outputs | **Yes** |
| 2.6 | Every whitelist entry has a one-line justification | commit message or `THIRD-PARTY/`-style note | **Yes** |

Two lessons this gate exists for, both real:

- An internal role name reached a document that ships with the public repository. The file tree
  looked clean; the string was inside prose.
- Help text pointed users at an internal launch script that the release does not contain.
  Deleting the script did not delete the instruction.
- **The scan reported "clean" twice while an internal absolute path sat in a file
  that ships inside the release binary.** The pattern was written in a way that
  did not match its own target, and a zero-hit result looks exactly like success.
  Hence 2.4: a scan that has never been shown to fire is evidence of nothing.
- A scan using an unbounded two-letter pattern reported a hit inside an ordinary English word.
  Had that been waved through as "obviously fine", the check would have been trained out of use
  within a week.


## 2.5 Editing a published document

| # | Gate | Why |
|---|---|---|
| 2.5.1 | Before editing any release document, ask: **is this file inside the package?** If yes, rebuild, recompute the sha256, and treat the old value as void; if no, the repository alone is enough | Decided by *whether the file ships*, not by what kind of file it is. Measured 2026-11-05: `NOTICE` and `README.md` are copied into `ArtCraftOCR/` by `build.py`, so correcting a trademark sentence in the repo left the wrong sentence inside the download — the exact "the file says one thing, the package says another" failure this checklist exists for. The reviewer's first answer ("docs only, no need to repackage") was wrong for that reason |
| 2.5.2 | After the rebuild, grep the **package**, not the repository, for the corrected string | A rebuild that copies the old file forward looks identical from the repo side |

## 3. Packaging

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 3.0 | The build refuses to run on failing tests — the gate is mechanical, not a promise | `python PACKAGING/build.py --check-only` passes; break one test and confirm the build exits 1 **before** PyInstaller starts | **Yes** |
| 3.1 | No ArtCraft brand asset, no Windows system font | `git ls-files` + binary scan of the bundle | **Yes** |
| 3.2 | LGPL-free bundle: the FFmpeg DLL from `opencv-python` is excluded | `find dist -iname "*ffmpeg*"` returns nothing | **Yes** |
| 3.3 | Recognition still works after that exclusion | smoke run, output pasted, not "passed" | **Yes** |
| 3.4 | Notice bundle present and complete | `THIRD-PARTY/` matches `LICENSES.md` §7.3 | **Yes** |
| 3.5 | Missing WebView2 runtime exits with one readable line, not a stack trace | run on a machine/image without the runtime, or simulate its absence | **Yes** |

Gate 3.0 is the reason every build goes through `PACKAGING/build.py`. A rule that says
"run the tests before you build" is advice, and advice is skipped under time pressure
exactly when it matters. The script runs the unit tests and the interface check first
and exits 1 before PyInstaller is started, so the only way to produce a package is to
have green tests. The exit code is the verdict — grepping a build log for
"completed successfully" once hid a COLLECT failure and shipped a package with no
`APP/ui`, which opened to a 404.

## 4. Layout and display

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 4.1 | No hardcoded pixel size in the window-fit path | read the fit function; only measured values and DPI-scaled constants | **Yes** |
| 4.2 | Both axes are measured, not just width | width *and* height derived from widget requests | **Yes** |
| 4.3 | Bounds use the work area, not the full screen | clamp against work area (taskbar excluded), not screen size | **Yes** |
| 4.4 | The window opens on screen on a multi-monitor setup | run with a second display; position within the work area | **Yes** |

Item 4.3 is easy to get wrong and hard to notice: screen dimensions include the taskbar, so a
window clamped to "fits the screen" can still put its bottom row underneath it. A generous fixed
margin hides the mistake on some machines and not others.

## 5. Smoke run

| # | Case | Why it is in the list | Blocks? |
|---|---|---|---|
| 5.1 | Recognition, plain | baseline | **Yes** |
| 5.2 | Paragraph rebuild | multi-line input | **Yes** |
| 5.3 | Traditional Chinese | separate model, separate dictionary | **Yes** |
| 5.4 | Colour sampling | per-glyph ink colour | **Yes** |
| 5.5 | Large image | exercises the resize branch | **Yes** |
| 5.6 | Alpha PNG | user-path regression only — it does **not** exercise any cv2 alpha branch (our engine flattens to RGB first), so it must not be cited as one | No |

Record the actual output of each case in the release notes. A row that says "passed" is not
evidence.

## 6. Repository

| # | Gate | Evidence | Blocks? |
|---|---|---|---|
| 6.1 | Commit author is the intended identity, configured at repo level | `git log -1 --format='%an <%ae>'` matches the recorded identity | **Yes** |
| 6.2 | Global git config untouched | `git config --global --get user.name` unchanged | **Yes** |
| 6.3 | No credential, token or personal address in history | `git log -p` scan | **Yes** |

## 7. Handling other people's software

| # | Gate | Why |
|---|---|---|
| 7.1 | Never terminate or manipulate processes this project did not start | Someone's unsaved work is not recoverable; a layout bug is |
| 7.2 | Before any process action, print the exact target list (title + PID) first | A wrong target list is cheap to catch and expensive to discover afterwards |
| 7.3 | Ask before touching another person's application, even when it looks idle | "Looks idle" is a guess, and the cost of being wrong is theirs |
| 7.4 | Only kill a PID this project launched itself | Own what you start; leave the rest alone |

These four are not about licensing or quality. They are here because they were violated on this
project, and the rule belongs somewhere it will be read before the next release, not in a chat
log.
