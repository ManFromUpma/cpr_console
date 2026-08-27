"""Shared helpers for the MacBook tinkering utilities."""
from __future__ import annotations
import argparse, json, os, platform, shutil, subprocess, sys
from pathlib import Path
from typing import Any, Iterable

IS_MACOS = platform.system() == "Darwin"

def add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

def emit(value: Any, as_json: bool = False) -> None:
    try:
        if as_json:
            print(json.dumps(value, indent=2, default=str, sort_keys=True))
        elif isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2, default=str))
        else:
            print(value)
    except BrokenPipeError:
        # Normal when a user intentionally pipes a long report into `head`.
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)

def command_exists(name: str) -> bool:
    return shutil.which(name) is not None

def run_command(args: list[str], timeout: int = 20, input_text: str | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s: {' '.join(args)}"
    except OSError as exc:
        return 1, "", str(exc)

def mac_command(name: str, args: list[str] | None = None, timeout: int = 20) -> dict[str, Any]:
    if not IS_MACOS:
        return {"available": False, "reason": "This command is macOS-specific; run it on a MacBook."}
    code, out, err = run_command([name] + (args or []), timeout=timeout)
    return {"available": code == 0, "returncode": code, "stdout": out, "stderr": err}

def human_bytes(value: int | float) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(n) < 1024 or unit == "PiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"

def parse_bytes(text: str) -> int:
    units = {"b": 1, "k": 1024, "kb": 1024, "kib": 1024, "m": 1024**2, "mb": 1024**2, "mib": 1024**2, "g": 1024**3, "gb": 1024**3, "gib": 1024**3, "t": 1024**4, "tb": 1024**4, "tib": 1024**4}
    raw = text.strip().lower().replace(" ", "")
    number = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    suffix = raw[len(number):] or "b"
    return int(float(number) * units.get(suffix, 1))

def iter_files(root: Path, include_hidden: bool = False, max_files: int = 100_000) -> Iterable[Path]:
    count = 0
    if root.is_file():
        yield root
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if include_hidden or not d.startswith(".")]
        for name in files:
            if not include_hidden and name.startswith("."):
                continue
            path = Path(base) / name
            try:
                if path.is_file():
                    yield path
                    count += 1
                    if count >= max_files:
                        return
            except OSError:
                continue

def path_record(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {"path": str(path), "size": stat.st_size, "size_human": human_bytes(stat.st_size), "modified": stat.st_mtime, "mode": oct(stat.st_mode & 0o777), "is_symlink": path.is_symlink()}
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}

def explain_unavailable(name: str) -> int:
    print(f"{name} is not available on this operating system. Run it on macOS for full results.", file=sys.stderr)
    return 2

def common_path_arg(parser: argparse.ArgumentParser, default: str = ".") -> None:
    parser.add_argument("path", nargs="?", default=default, help="File or folder to inspect (default: current folder).")
