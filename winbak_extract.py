#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Constants
ZIP_NAME_PREFIX = "Backup files "
TMP_DIR_NAME = ".winbak_tmp"

class SummaryLog:
    def __init__(self) -> None:
        self.merged: List[Tuple[str, int]] = []
        self.skipped_existing: List[str] = []
        self.errors: List[str] = []
        self.extracted_parts_count: int = 0
        self.zips_processed: int = 0

    def write(self, dest: Path) -> None:
        try:
            lines = []
            lines.append("Windows 7 Backup Extract Summary")
            lines.append(f"ZIPs processed: {self.zips_processed}")
            lines.append(f"Part files extracted: {self.extracted_parts_count}")
            lines.append("")
            lines.append("Merged outputs:")
            for path, count in self.merged:
                if count > 1:
                    lines.append(f"- {path} (parts={count})")
            lines.append("")
            if self.skipped_existing:
                lines.append("Skipped (final already exists):")
                for p in self.skipped_existing:
                    lines.append(f"- {p}")
                lines.append("")
            if self.errors:
                lines.append("Errors:")
                for e in self.errors:
                    lines.append(f"- {e}")
                lines.append("")
            ts = datetime.now().astimezone().isoformat(timespec="seconds")
            ts_std = ts.replace("-", "").replace(":", "")
            log_name = f"winbak_extract_{ts_std}.txt"
            (dest / log_name).write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:
            print(f"Failed to write summary log: {exc}", file=sys.stderr)

# Windows extended-length path helper
# Note: Path operations with \\?\ prefix require absolute paths.

def to_long_path(p: Path) -> str:
    p_abs = p.resolve(strict=False)
    s = str(p_abs)
    if os.name == "nt":
        if not s.startswith("\\\\?\\"):
            # Convert to extended-length form
            if s.startswith("\\\\"):
                # UNC path
                return "\\\\?\\UNC" + s[1:]
            else:
                return "\\\\?\\" + s
    return s

# Natural sort for ZIPs by trailing integer after prefix

def zip_sort_key(p: Path) -> Tuple[int, str]:
    name = p.name
    try:
        if name.lower().startswith(ZIP_NAME_PREFIX.lower()):
            suffix = name[len(ZIP_NAME_PREFIX):]
            num = int(Path(suffix).stem)  # handles "N.zip"
            return (num, name)
    except Exception:
        pass
    return (sys.maxsize, name)

# CLI parsing

def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Windows 7 Backup ZIP Extractor")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dir", type=str, help="Folder containing 'Backup files N.zip'")
    g.add_argument("--files", nargs="+", help="Explicit ZIP paths")
    g.add_argument("--set", type=str, help="Parent folder containing multiple 'Backup Files' folders")
    ap.add_argument("--encoding", type=str, help="Filename encoding to use when ZIP is not UTF-8 (e.g., 'cp932')")
    return ap.parse_args(argv)

# Enumerate and validate ZIPs

def enumerate_zips(args: argparse.Namespace) -> List[Path]:
    zips: List[Path] = []
    if getattr(args, 'dir', None):
        root = Path(args.dir)
        if not root.is_dir():
            raise FileNotFoundError(f"Directory not found: {root}")
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() == ".zip" and p.name.lower().startswith(ZIP_NAME_PREFIX.lower()):
                zips.append(p)
    else:
        for f in getattr(args, 'files', []) or []:
            p = Path(f)
            if p.is_file() and p.suffix.lower() == ".zip" and p.name.lower().startswith(ZIP_NAME_PREFIX.lower()):
                zips.append(p)
    zips.sort(key=zip_sort_key)
    return zips

# Helpers

# Filename decoding per flags and user encoding

def _decode_zip_name(info: zipfile.ZipInfo, user_encoding: str | None) -> str:
    if info.flag_bits & 0x800:
        return info.orig_filename
    try:
        raw = info.orig_filename.encode('cp437')
    except Exception:
        return info.orig_filename
    if user_encoding:
        try:
            return raw.decode(user_encoding)
        except Exception:
            pass
    try:
        return raw.decode('cp437')
    except Exception:
        return info.orig_filename

# Extraction staging under temp directory

def stage_extract(zips: List[Path], dest_root: Path, log: SummaryLog, user_encoding: str | None = None) -> Dict[str, List[Path]]:
    parts_map: Dict[str, List[Path]] = {}
    tmp_root = dest_root / TMP_DIR_NAME
    tmp_root.mkdir(parents=True, exist_ok=True)

    for zp in zips:
        try:
            with zipfile.ZipFile(to_long_path(zp)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    fixed_name = _decode_zip_name(info, user_encoding or None)
                    rel = Path(fixed_name)
                    key = str(rel).lower()  # case-insensitive grouping
                    part_list = parts_map.setdefault(key, [])
                    idx = len(part_list) + 1
                    part_name = rel.name + f".part_{idx:04d}"
                    part_dir = tmp_root / rel.parent
                    part_dir.mkdir(parents=True, exist_ok=True)
                    part_path = part_dir / part_name
                    with zf.open(info, "r") as src, open(to_long_path(part_path), "wb", buffering=1024 * 1024) as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                    part_list.append(part_path)
                    log.extracted_parts_count += 1
        except Exception as exc:
            log.errors.append(f"Failed to extract from {zp}: {exc}")
    return parts_map

# Python fallback concatenation to avoid cmd copy /b limitations

def concat_parts_python(parts: List[Path], tmp_merge: Path) -> None:
    tmp_merge.parent.mkdir(parents=True, exist_ok=True)
    with open(to_long_path(tmp_merge), 'wb', buffering=1024*1024) as out:
        for p in parts:
            with open(to_long_path(p), 'rb', buffering=1024*1024) as inp:
                shutil.copyfileobj(inp, out, length=1024*1024)

# Merge parts using copy /b, verify size, handle overwrite policy

def merge_parts(parts_map: Dict[str, List[Path]], dest_root: Path, log: SummaryLog) -> None:
    tmp_root = dest_root / TMP_DIR_NAME
    for key, parts in parts_map.items():
        first_part = parts[0]
        original_name = first_part.name.rsplit(".part_", 1)[0]
        # final directory mirrors the internal path under dest_root
        final_dir = dest_root / (first_part.parent.relative_to(tmp_root))
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / original_name

        # Overwrite policy: fail if final exists
        if final_path.exists():
            log.skipped_existing.append(str(final_path))
            log.errors.append(f"Final already exists (overwrite not allowed): {final_path}")
            continue

        # Fast path: single staged part, avoid extra copy
        if len(parts) == 1:
            try:
                expected = sum(p.stat().st_size for p in parts)
                actual = first_part.stat().st_size
                if actual != expected:
                    raise ValueError(f"Merged size mismatch in single-part: expected={expected}, actual={actual}")
                os.replace(to_long_path(first_part), to_long_path(final_path))
                log.merged.append((str(final_path), 1))
                continue
            except Exception:
                # Fall through to normal merge path
                pass

        # tmp merge file lives under the temp directory to avoid collisions
        tmp_merge = first_part.parent / (original_name + ".__merge_tmp")
        try:
            # Prepare plus-separated list for copy /b
            parts_cmd = "+".join([f'"{to_long_path(p)}"' for p in parts])
            cmd = f"cmd /c copy /b {parts_cmd} \"{to_long_path(tmp_merge)}\""
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Verify or fallback
            expected = sum(p.stat().st_size for p in parts)
            actual = Path(tmp_merge).stat().st_size if Path(tmp_merge).exists() else 0
            if proc.returncode != 0 or actual != expected:
                try:
                    Path(tmp_merge).unlink(missing_ok=True)
                except Exception:
                    pass
                concat_parts_python(parts, tmp_merge)
                actual = Path(tmp_merge).stat().st_size if Path(tmp_merge).exists() else 0
                if actual != expected:
                    raise ValueError(f"Merged size mismatch after fallback: expected={expected}, actual={actual}")

            # Move into place
            os.replace(to_long_path(tmp_merge), to_long_path(final_path))
            log.merged.append((str(final_path), len(parts)))

            # Cleanup parts
            for p in parts:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as exc:
            log.errors.append(f"Failed to merge {final_path}: {exc}")
            try:
                Path(tmp_merge).unlink(missing_ok=True)
            except Exception:
                pass

# Core processing from a list of zips

def process_zips(zips: List[Path], user_encoding: str | None) -> int:
    dest_root = Path(zips[0]).resolve().parent
    dest_root.mkdir(parents=True, exist_ok=True)
    log = SummaryLog()
    ret = 0
    try:
        log.zips_processed = len(zips)
        if not zips:
            return 0
        parts_map = stage_extract(zips, dest_root, log, user_encoding)
        merge_parts(parts_map, dest_root, log)
    except Exception as exc:
        log.errors.append(f"Fatal error: {exc}")
        ret = 1
    finally:
        try:
            tmp_root = dest_root / TMP_DIR_NAME
            if tmp_root.exists():
                # Prune empty subdirectories bottom-up
                dirs = sorted((d for d in tmp_root.rglob('*') if d.is_dir()), key=lambda d: len(d.relative_to(tmp_root).parts), reverse=True)
                for d in dirs:
                    try:
                        if not any(d.iterdir()):
                            os.rmdir(to_long_path(d))
                    except Exception:
                        pass
                has_files = any(p.is_file() for p in tmp_root.rglob('*'))
                has_dirs = any(p.is_dir() for p in tmp_root.rglob('*'))
                if not has_files and not has_dirs:
                    shutil.rmtree(to_long_path(tmp_root), ignore_errors=True)
        except Exception:
            pass
        log.write(dest_root)
    if log.errors:
        ret = 1
    return ret

# Wrapper to process a directory containing zips

def process_dir(dir_root: Path, user_encoding: str | None) -> int:
    zips: List[Path] = []
    if dir_root.is_dir():
        for p in dir_root.iterdir():
            if p.is_file() and p.suffix.lower() == ".zip" and p.name.lower().startswith(ZIP_NAME_PREFIX.lower()):
                zips.append(p)
    zips.sort(key=zip_sort_key)
    return process_zips(zips, user_encoding)

# Main

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    ret = 0
    if args.set:
        set_root = Path(args.set)
        if not set_root.is_dir():
            print(f"Backup Set folder not found: {set_root}", file=sys.stderr)
            return 1
        for child in set_root.iterdir():
            if not child.is_dir():
                continue
            child_ret = process_dir(child, args.encoding)
            if child_ret != 0:
                ret = 1
        return ret
    elif args.dir:
        return process_dir(Path(args.dir), args.encoding)
    else:
        zips = enumerate_zips(args)
        if not zips:
            print("No matching ZIPs provided.", file=sys.stderr)
            return 1
        return process_zips(zips, args.encoding)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
    