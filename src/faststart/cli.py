"""Command line: ``faststart check`` and ``faststart fix``."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List

from . import __version__
from .atoms import read_layout

EXTENSIONS = {".mp4", ".m4v", ".mov", ".m4a", ".3gp"}


def expand(paths: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.suffix.lower() in EXTENSIONS and f.is_file())
        elif p.is_file():
            out.append(p)
        else:
            print(f"skip: {p} (not found)", file=sys.stderr)
    return out


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def status(path: Path) -> str:
    try:
        layout = read_layout(path)
    except (OSError, ValueError) as e:
        return f"error ({e})"
    if not layout.has_moov:
        return "error (no moov atom, not an MP4/MOV?)"
    if layout.is_faststart:
        return "ok"
    moov = layout.offset_of("moov") or 0
    return f"slow (index at {human(moov)} of {human(path.stat().st_size)})"


def cmd_check(args: argparse.Namespace) -> int:
    files = expand(args.paths)
    slow = 0
    for f in files:
        s = status(f)
        slow += s != "ok"
        if s != "ok" or not args.quiet:
            print(f"{s:<12.12} {f}" if s == "ok" else f"{s}  {f}")
    print(f"\n{len(files)} checked, {slow} need fixing", file=sys.stderr)
    return 1 if slow else 0


def remux(src: Path, dst: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("faststart fix needs ffmpeg on your PATH (brew install ffmpeg / apt install ffmpeg)")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-map", "0", "-c", "copy", "-movflags", "+faststart", str(dst)],
        check=True,
    )


def cmd_fix(args: argparse.Namespace) -> int:
    if not args.in_place and not args.out_dir:
        raise SystemExit("choose where fixed files go: --in-place or --out-dir DIR")
    failures = 0
    for f in expand(args.paths):
        if status(f) == "ok":
            print(f"ok      {f}")
            continue
        if args.dry_run:
            print(f"would fix {f}")
            continue
        try:
            with tempfile.TemporaryDirectory(dir=f.parent) as tmp:
                out = Path(tmp) / f.name
                remux(f, out)
                if not read_layout(out).is_faststart:
                    raise RuntimeError("remux did not move the index")
                if args.in_place:
                    out.replace(f)
                    target = f
                else:
                    target = Path(args.out_dir) / f.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(out), target)
            print(f"fixed   {target}")
        except (subprocess.CalledProcessError, RuntimeError, OSError) as e:
            failures += 1
            print(f"failed  {f}: {e}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: "List[str] | None" = None) -> int:
    p = argparse.ArgumentParser(prog="faststart", description="Find and fix MP4/MOV files that start slowly on the web.")
    p.add_argument("--version", action="version", version=f"faststart {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="report files whose index is at the end (exit 1 if any)")
    c.add_argument("paths", nargs="+", help="files or folders (searched recursively)")
    c.add_argument("-q", "--quiet", action="store_true", help="only print files that need fixing")
    c.set_defaults(func=cmd_check)

    x = sub.add_parser("fix", help="move the index to the front (lossless, no re-encode; needs ffmpeg)")
    x.add_argument("paths", nargs="+")
    where = x.add_mutually_exclusive_group()
    where.add_argument("--in-place", action="store_true", help="replace each file after verifying the result")
    where.add_argument("-o", "--out-dir", help="write fixed copies here")
    x.add_argument("-n", "--dry-run", action="store_true")
    x.set_defaults(func=cmd_fix)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
