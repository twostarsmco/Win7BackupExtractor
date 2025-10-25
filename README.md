# Windows 7 Backup ZIP Extractor

A simple, maintainable Python 3.x script to extract and reconstruct files from Windows 7 backup ZIP sets named `Backup files N.zip`. It preserves internal paths, concatenates split parts in correct order, and writes a text summary log.

## Requirements

- Python 3.x on Windows.
- No external dependencies (stdlib only).

## Usage

Run from this folder or provide full paths.

- From a directory of backup ZIPs:
  `python winbak_extract.py --dir "C:\\Backups"`

- From explicit ZIP paths:
  `python winbak_extract.py --files "C:\\Backups\\Backup files 1.zip" "C:\\Backups\\Backup files 2.zip"`

- Optional filename encoding (used when ZIP entries aren't UTF-8):
  `python winbak_extract.py --encoding cp932 --dir "C:\\Backups"`
  - If UTF-8 flag is set in a ZIP entry, UTF-8 is used regardless.
  - If UTF-8 flag is not set and `--encoding` is provided, that codec is used. Refer to [Standard Encodings on Python documentation](https://docs.python.org/3/library/codecs.html#standard-encodings) for available codecs.
  - If UTF-8 flag is not set and `--encoding` is omitted, CP437 is used per ZIP spec.

## Behavior

- Filters only files named `Backup files N.zip` (case-insensitive), natural-sorting by `N`.
- Extracts each ZIP entry to a dedicated temp directory: `<dest>\\.winbak_tmp\\<internal_path>\\<name>.part_0001...`.
- Groups occurrences of the same relative path (case-insensitive on Windows) and treats them as parts.
- Merges parts in natural ZIP order using `copy /b` with a Python fallback if needed.
- Overwrite policy: triggers failure and skips if the final output already exists.
- Dedupe behavior: identical duplicates are always treated as parts and concatenated.
- Deletes staged part files after a successful merge.
- Optimized single-part handling: if only one part exists, it is moved directly to the final destination (size-verified) instead of re-copying.
- Writes timestamped summary logs `winbak_extract_summary_YYYYMMDDTHHMMSS.txt` (merged files, part counts, skips, errors) to each processed folder.
- Serial processing; streams I/O; avoids loading entire files into memory.

## Path Length

- Supports extended-length Windows paths using the `\\?\\` prefix for open/replace/unlink operations.
- If very long paths still fail, ensure Windows long paths are enabled (may require registry change and policy updates).

## Exit Codes

- `0`: Completed without errors.
- `1`: One or more errors occurred (see summary log).

## Notes

- Aligns with the manual guidance for combining split parts using `copy /b`, but avoids wildcard patterns and enforces explicit order.
- Final outputs are written under `<dest>\\<internal_path>\\<name>`; temp artifacts live under `<dest>\\.winbak_tmp`.
- On completion (even if failures occurred), empty directories under .winbak_tmp are pruned bottom-up; the root is removed if the tree is empty.

## Examples

- Basic directory processing:
  `python winbak_extract.py --dir "D:\\Win7Backup"`

- Process a Backup Set folder (immediate children only):
  `python winbak_extract.py --set "D:\\Win7BackupSet"`

- Explicit files:
  `python winbak_extract.py --files "D:\\Win7Backup\\Backup files 1.zip" "D:\\Win7Backup\\Backup files 2.zip"`
