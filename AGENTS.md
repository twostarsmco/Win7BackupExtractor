# AGENTS.md

This repository contains a Python 3.x script to extract and reconstruct files from Windows 7 backup ZIP sets named `Backup files N.zip`. Use this document as the source of truth for future updates and maintenance.

## Scope

- Applies to the entire repository.
- Governs code style, behavior, and expectations for `winbak_extract.py`, `README.md`.

## Core Requirements

- Language: Python 3.x (stdlib only; no external dependencies).
- Overwrite policy: If the final post-merge output path already exists, the operation must fail and skip that file; never overwrite.
- Dedupe behavior: When identical files appear across ZIPs at the same relative path, always treat them as parts and concatenate (intentional duplication).
- Logging: Produce a timestamped text summary log (`winbak_extract_summary_YYYYMMDDTHHMMSS.txt`) listing merges, part counts, skipped items, and errors.
- Performance: Prefer clear, concise, maintainable code. Keep processing serial; avoid parallelization.
- Path length: Support Windows extended-length paths (use `\\?\` for open/replace/unlink operations).
- Temporary naming: Use a dedicated temp directory under `<dest>\\.winbak_tmp\\...` for staging part files and merge outputs. Prune empty folders under <dest>\\.winbak_tmp on completion (even on failure). Remove the root if the tree is entirely empty.

## Code Layout

- `winbak_extract.py`: Main script providing CLI and core logic.
  - CLI options:
    - `--dir <folder>`: Directory containing backup ZIPs (`Backup files N.zip`).
    - `--files <zip1> <zip2> ...`: Explicit ZIP paths.
    - `--set <folder>`: Parent folder containing multiple "Backup Files" folders. Only immediate children are scanned.
    - `--encoding <codec>`: Filename decoding when ZIP entries are not UTF-8.
  - Modules used: `argparse`, `pathlib`, `zipfile`, `shutil`, `subprocess`, `os`, `sys`.
  - Long path helper: `to_long_path(Path)` must be used for file operations.
  - Summary logging: `SummaryLog` collects merged outputs, skips, and errors, writing timestamped `winbak_extract_summary_YYYYMMDDTHHMMSS.txt` to each processed folder.
- `README.md`: Usage, behavior, path length notes, exit codes, examples.

## Behavior & Algorithm

- Input filtering: Only process files named `Backup files N.zip` (case-insensitive). Ignore all others.
- Ordering: Natural sort ZIPs by integer `N` in the filename; parts are concatenated in that ZIP order.
- Extraction:
  - Do not extract directly to final destinations.
  - Stream each entry to a staged part under `<dest>\\.winbak_tmp\\<internal_path>\\<name>.part_0001...`.
  - Group parts by case-insensitive relative path key (Windows semantics).
- Merging:
  - Construct final path `<dest>\\<internal_path>\\<name>`.
  - Enforce overwrite policy: if final exists, record a skip + error and continue.
  - Prefer `copy /b` with explicit plus-separated part names (no wildcards). If it fails or size mismatch occurs, fallback to Python concatenation.
  - Verify merged size equals the sum of part sizes before moving to final.
  - Single-part optimization: when only one part exists, move it directly to final (with size verification) instead of running copy /b.
  - On success, delete staged part files; leave temp files if a failure occurs.

## Error Handling

- Continue on per-ZIP extraction errors; record them in the summary log.
- Fail merges on validation issues (existing final path, size mismatch, command failure).
- Return non-zero exit code if any errors were recorded.

### Filename Decoding

- `--encoding <codec>` option controls filename decoding when the ZIP entry is not marked UTF-8.
- Decoding rules:
  - If flag bit 11 (UTF-8) is set, use UTF-8.
  - If not set and `--encoding` is provided, decode with that codec.
  - If not set and `--encoding` is omitted, use CP437 per ZIP spec.
- Use `ZipInfo.orig_filename` to reconstruct bytes for decoding. `ZipInfo.filename` normalizes backslashes to forward slashes, which corrupts the original byte sequence for code pages like CP932 (Shift_JIS). `orig_filename` preserves the pre-normalization name, allowing correct byte recovery and decoding.

## Path Length & Windows Notes

- Use `\\?\` prefix for long paths when opening, replacing, and unlinking files.
- If long paths still fail, ensure Windows long paths are enabled (system policy/registry change may be required).

## Performance & I/O

- Serial processing only.
- Stream I/O (`shutil.copyfileobj`) with reasonable buffer sizes (e.g., 1 MiB).
- Avoid loading entire files into memory.

## Coding Conventions

- Keep changes minimal and focused on the task.
- Maintain current structure and naming in `winbak_extract.py`.
- Use `pathlib` consistently for path manipulations.
- Do not introduce external dependencies.
- Do not weaken the overwrite policy or dedupe behavior unless the requirements are explicitly updated.

## Contact & Tools

- Use Python standard library documentation for `zipfile`, `pathlib`, and Windows path behavior.
- If using assistant tooling, prefer clear plans and patches; validate against these requirements.
- Use Context7 MCP to refer to correct documentation (e.g., Python stdlib). Resolve library IDs and fetch docs via Context7 tools where needed.

## Maintenance Guidelines

- Update the README if CLI or behavior changes.
- Preserve temp directory naming and structure under `<dest>\\.winbak_tmp`.
- Preserve logging format and file naming.
- Document any new options in `README.md` and reflect them in this file.

## Non-Goals

- No support for other backup formats beyond Windows 7 ZIP scheme.
- No parallel processing.
