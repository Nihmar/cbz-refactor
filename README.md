# CBZ Refactor Tool

A Python utility to reorganize and batch CBZ (Comic Book ZIP) files into multi‑volume archives according to a simple CSV configuration.  
It processes each series folder, combines individual chapter CBZs into volumes, moves specials to a dedicated subfolder, and optionally deletes the original files.

## Features

- **Batch‑based volume creation** – Combine several CBZ files into a single volume with consecutive page numbering.
- **Flexible batch sizes** – Specify a repeating batch size (e.g., `5`) or a fixed sequence (e.g., `3,4,5,3`) per series.
- **Special file detection** – Files matching `SP01`, `SP02` (case‑insensitive) are automatically moved to a `Specials` subfolder.
- **Volume detection** – Files already named `V001`, `V123` can be skipped to avoid overwriting existing volumes.
- **In‑memory processing** – All page data is held in memory; no temporary files are written.
- **CSV‑driven configuration** – One row per series with full control over batch sizes, flags, and ignoring.
- **Safe logging** – Detailed logs are written to a timestamped file in the base directory.

## Requirements

- Python 3.6 or higher (uses `pathlib`, f‑strings, and `zipfile`)
- No external dependencies – only the Python standard library is used.

## Installation

1. Download `cbz_refactor.py` to your computer.
2. Make sure Python 3.6+ is installed and available in your PATH.
3. (Optional) Create a virtual environment – not required, but can be used for isolation.

## Usage

```bash
python cbz_refactor.py /path/to/your/comics/library
```

The script expects a file named **`to_refactor.csv`** in the given directory.  
Each row in the CSV defines how a subfolder (series) should be processed.

## CSV Configuration

Create `to_refactor.csv` with the following columns (comma‑separated, UTF‑8 encoding):

| Column | Name              | Description                                                                 | Default |
|--------|-------------------|-----------------------------------------------------------------------------|---------|
| 1      | `folder_name`     | Name of the subfolder inside the base directory (e.g., `MySeries`).        | *required* |
| 2      | `batch_sizes`     | Batch size(s) – either a single number (repeated) or a comma‑separated list (used exactly). | *required* |
| 3      | `no_extra`        | If `True`, leftover files after the defined batches stay as individual CBZs; if `False`, they are merged using the average batch size. | `True` |
| 4      | `avoid_volumes`   | If `True`, skip files that already match the `Vxxx` pattern (e.g., `V001.cbz`) and continue numbering after the highest existing volume. | `True` |
| 5      | `delete_originals`| If `True`, delete the original CBZ files after they have been merged.       | `True` |
| 6      | `ignore`          | If `True`, the series is completely ignored (nothing is processed).         | `False` |

**Boolean values** can be given as: `true`/`false`, `yes`/`no`, `1`/`0`, `t`/`f`, `y`/`n` (case‑insensitive).  
Empty cells use the default value.

### Example CSV

```csv
folder_name,batch_sizes,no_extra,avoid_volumes,delete_originals,ignore
Akira,5,false,true,true,false
"Blame!","3,4,5,3",true,true,false,false
"Nausicaa",3,true,false,true,false
```

- **Akira** – Combine every 5 chapters into one volume; if there are leftovers (e.g., 2 extra chapters), they will **also** be merged into a final volume because `no_extra=false`.  
- **Blame!** – Use exactly batches of 3, 4, 5, and 3 chapters (total 15 chapters). Any remaining chapters are left as individual CBZs (`no_extra=true`).  
- **Nausicaa** – Repeat batch size 3; overwrite any existing `Vxxx` files (`avoid_volumes=false`) and **do not** delete originals.

## How It Works

1. The script reads `to_refactor.csv` from the base directory.
2. For each series folder (e.g., `base/Akira`):
   - Lists all `*.cbz` files.
   - **Special files** (e.g., `SP01.cbz`) are moved into a `Specials` subfolder.
   - If `avoid_volumes` is `True`, any file already named with a volume pattern (`V001.cbz`) is **not** touched; the next volume number is determined by scanning these files.
   - Remaining “regular” files are grouped into batches according to the `batch_sizes` and `no_extra` rules.
   - For each batch:
     - All contained CBZ files are extracted in‑memory, their images collected, sorted, and then re‑packed into a new CBZ with pages named `page_001.jpg`, `page_002.png`, etc.
     - The new file is named `SeriesName Vxxx.cbz` (e.g., `Akira V001.cbz`).
     - If `delete_originals` is `True`, the original chapter CBZs are deleted after successful creation.
3. A detailed log file (`cbz_refactor_YYYYMMDD_HHMMSS.log`) is written to the base directory.

## Important Notes

- **Page ordering** – Within each original CBZ, images are sorted alphabetically by filename. All batches preserve this order, and pages are numbered consecutively across the whole batch.
- **XML metadata** – `ComicInfo.xml` and any other `.xml` files inside the CBZ archives are **ignored** and not included in the new volumes.
- **Image formats** – Supported: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp` (case‑insensitive).
- **Special detection** – The regex `SP\d{2}` (case‑insensitive) identifies specials. Adjust the code if your naming differs.
- **Volume detection** – The regex `V\d+` (case‑insensitive) identifies existing volume files. When `avoid_volumes=True`, numbering continues from the highest found volume +1.
- **Memory usage** – All images of a batch are held in RAM simultaneously. For very large batches (hundreds of high‑resolution pages), ensure your system has enough memory.
- **No dry‑run** – The script performs actual file moves and deletions. Test on a copy of your data first.

## Logging

The logger writes both to the console and to a file in the base directory. The log file contains timestamps and detailed messages about every action (moves, creations, deletions). Example output:

```
INFO - Processing: Akira (batch: 5, no-extra: False, avoid-volumes: True, delete: True)
INFO - Moved to Specials: SP01.cbz
INFO - Will create 3 volumes with sizes: [5, 5, 2]
INFO - Processing batch 1 (5 files)...
INFO - Extracted to memory: chap01.cbz (24 images)
...
INFO - Created: Akira V001.cbz (120 pages)
INFO - Deleted: chap01.cbz
...
INFO - Left 0 files as individual CBZ files
```

## License

This script is provided as‑is, without warranty. Feel free to modify and distribute.

---

**Happy comic organizing!**
