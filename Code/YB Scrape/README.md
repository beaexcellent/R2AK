# R2AK YB Tracker Data Exporter

Download, decode, and export public Race to Alaska position data from the YB Tracking race viewer.

The tools preserve the original race metadata and binary position archive, produce analysis-friendly CSV and JSONL files, and create one legacy-compatible JSON track file per team.

## Supported races

The following YB race keys have been verified:

- `r2ak2024` — Race to Alaska 2024
- `r2ak2026` — Race to Alaska 2026

Stage or leg-specific YB race keys are not included here. If a separate race key becomes available, the same workflow can be run with that key.

## Why three scripts?

Retrieval and conversion are deliberately separated so that decoder development, re-exporting, and analysis do not repeatedly request the same archive from the tracking provider.

1. `01_download_r2ak.py` downloads and caches the original source files.
2. `02_inspect_r2ak_download.py` validates the cached files without using the network.
3. `03_export_r2ak_offline.py` decodes and exports the cached data without using the network.

Once a race has been downloaded, scripts 02 and 03 can be run repeatedly without contacting the server.

## Requirements

- Python 3.9 or newer
- No third-party Python packages

The scripts use only the Python standard library.

## Files

```text
01_download_r2ak.py
02_inspect_r2ak_download.py
03_export_r2ak_offline.py
```

## Quick start

The examples below use PowerShell. Run them from the directory containing the three scripts.

### 1. Download a race once

For R2AK 2026:

```powershell
python .\01_download_r2ak.py `
  --race r2ak2026 `
  --dir ".\source_data\r2ak2026"
```

For R2AK 2024:

```powershell
python .\01_download_r2ak.py `
  --race r2ak2024 `
  --dir ".\source_data\r2ak2024"
```

The downloader creates:

```text
source_data/
└── r2ak2026/
    ├── race_setup.json
    ├── all_positions3.bin
    └── download_manifest.json
```

Existing source files are preserved by default. This prevents an accidental repeat download.

To intentionally replace the cached files, add `--force`:

```powershell
python .\01_download_r2ak.py `
  --race r2ak2026 `
  --dir ".\source_data\r2ak2026" `
  --force
```

Use `--force` sparingly.

### 2. Inspect the cached files

```powershell
python .\02_inspect_r2ak_download.py `
  --dir ".\source_data\r2ak2026"
```

The inspector reports information such as:

- Race title and number of teams
- Source file size and SHA-256 hash
- Binary format flags
- Base timestamp
- First tracker ID and position count
- Whether the position response appears to be HTML, JSON, gzip, or YB binary data

The inspector accepts either `all_positions3.bin` or `all_positions3.txt`. Renaming the binary file to `.txt` does not change its contents, provided it is not opened and resaved by a text editor.

### 3. Export the race offline

```powershell
python .\03_export_r2ak_offline.py `
  --race r2ak2026 `
  --source ".\source_data\r2ak2026" `
  --output ".\data\r2ak2026"
```

For 2024, change all three race-specific values:

```powershell
python .\03_export_r2ak_offline.py `
  --race r2ak2024 `
  --source ".\source_data\r2ak2024" `
  --output ".\data\r2ak2024"
```

The exporter reads only the cached source files. It makes no network requests.

## Recommended repository layout

```text
R2AK/
├── Code/
│   └── YB Scrape/
│       ├── 01_download_r2ak.py
│       ├── 02_inspect_r2ak_download.py
│       └── 03_export_r2ak_offline.py
├── source_data/
│   ├── r2ak2024/
│   └── r2ak2026/
└── data/
    ├── r2ak2024/
    └── r2ak2026/
```

If the raw binary archives are committed to Git, consider using Git LFS. Otherwise, keep `source_data/` out of Git and publish the normalized exports plus their manifests.

## Exported files

A completed export has this structure:

```text
data/r2ak2026/
├── race_setup.json
├── all_positions3.bin
├── positions.csv
├── positions.jsonl
├── teams.csv
├── manifest.json
└── tracks/
    ├── 0-1.json
    ├── 0-2.json
    └── ...
```

### `race_setup.json`

Original YB race metadata, including team information, race timing, classes or tags, and course information when available.

### `all_positions3.bin`

Original YB `AllPositions3` binary archive. It is retained for reproducibility and future decoder improvements.

### `teams.csv`

One row per team. The `id` column is the key used to associate teams with position records and legacy track files.

### `positions.csv`

One normalized row per position fix.

Important columns include:

- `race_key`
- `team_id`
- `team_name`
- `status`
- `timestamp`
- `timestamp_utc`
- `latitude`
- `longitude`
- `distance_to_finish_nm`
- Optional YB fields such as `alt`, `lap`, and `pc`

### `positions.jsonl`

The normalized position records as newline-delimited JSON. Each line is an independent JSON object.

### `manifest.json`

Records provenance and validation details, including:

- Race key and title
- Source endpoints
- Export time
- Decoder flags
- Team, tracker, position, and legacy-file counts
- Position time range
- SHA-256 hashes for the original source files

### `tracks/*.json`

One legacy-compatible JSON file per tracker. These follow the compact structure used by the earlier R2AK/Swiftsure scrape data.

Example:

```json
{
  "error": null,
  "message": "Requested completed successfully.",
  "payload": [
    {
      "ts": 1433434500,
      "lt": 48.3924,
      "ln": -123.3441,
      "s": 5.7,
      "h": 301,
      "stat": "active",
      "dstat": "Active"
    }
  ]
}
```

Legacy fields:

- `ts` — Unix timestamp in seconds
- `lt` — latitude in decimal degrees
- `ln` — longitude in decimal degrees
- `s` — calculated speed in knots
- `h` — calculated course over ground in degrees
- `stat` — normalized lowercase team status
- `dstat` — display-form team status

Speed and heading are derived from consecutive timestamped positions because those values are not directly exposed in the decoded position records. The first fix uses the first-to-second segment. A track containing only one fix receives speed `0.0` and heading `0`.

## Associating track files with teams

The number after `0-` in a track filename is the YB team ID.

```text
tracks/0-37.json
         └─ team ID 37
```

Match it to the `id` column in `teams.csv`:

```text
tracks/0-<team_id>.json  ↔  teams.csv[id]
```

The leading `0` is retained for compatibility with the legacy filename convention. It is not part of the team ID.

A quick Python lookup:

```python
import csv
from pathlib import Path

export_dir = Path("data/r2ak2026")

with (export_dir / "teams.csv").open(encoding="utf-8", newline="") as file:
    teams = {
        str(row["id"]): row["name"]
        for row in csv.DictReader(file)
    }

for track in sorted((export_dir / "tracks").glob("*.json")):
    team_id = track.stem.split("-", 1)[1]
    print(f"{track.name}: {teams.get(team_id, 'UNKNOWN TEAM')}")
```

## Using another YB race

A YB viewer address generally contains the race key as its final path component. For example, the race key in a viewer ending in `/r2ak2024` is `r2ak2024`.

Once the race key is known, use it consistently in all three steps:

```powershell
python .\01_download_r2ak.py --race RACE_KEY --dir ".\source_data\RACE_KEY"
python .\02_inspect_r2ak_download.py --dir ".\source_data\RACE_KEY"
python .\03_export_r2ak_offline.py --race RACE_KEY --source ".\source_data\RACE_KEY" --output ".\data\RACE_KEY"
```

Do not repeatedly guess keys with the downloader. Confirm that the corresponding public viewer exists first.

## Stage and leg data

The verified 2024 and 2026 YB keys represent yearly race archives. The exporter does not currently split a yearly archive into Stage 1 and Stage 2.

If separate stage-specific race keys are provided by the organizer, run the normal three-script workflow once for each key and give each one its own source and output directories.

If no separate keys exist, stage splitting should be implemented as an additional offline transformation using the decoded records, race timing, team metadata, and official stage definitions. It should not require downloading the yearly archive again.

## Character encoding

Some `RaceSetup` responses contain names encoded as Latin-1 rather than UTF-8. The inspector and exporter try UTF-8 first and then fall back to Latin-1.

## Troubleshooting

### `UnicodeDecodeError` while reading `race_setup.json`

Use the current versions of scripts 02 and 03. They include the Latin-1 fallback.

### `Team 0 starts with a delta record`

This usually indicates binary decoder misalignment or use of an older script. Confirm that you are running:

```text
03_export_r2ak_offline.py
```

The offline script begins with messages such as:

```text
Reading cached metadata: ...
Reading cached positions: ...
```

It should not print `Downloading metadata` or `Downloading positions`.

### The exporter cannot find the source files

Confirm the source directory contains:

```text
race_setup.json
all_positions3.bin
```

The position archive may alternatively be named:

```text
all_positions3.txt
```

Then pass the containing directory through `--source`.

### The downloaded position file begins with HTML or JSON

Run the inspector. A proxy, authentication page, service error, or blocked request may have been saved instead of the binary archive. Do not attempt to decode that response. Preserve it for diagnosis or intentionally redownload with `--force` after resolving the access issue.

## Data integrity and responsible use

The downloader records file sizes and SHA-256 hashes so cached source files can be identified and compared. The exporter also preserves the original responses alongside normalized output.

Before redistributing tracker histories, review applicable race-organizer and tracking-provider terms. Historical position data may warrant additional consideration even when it is available through a public race viewer.

## License

No license is assigned by these scripts to third-party race or tracker data. Choose a software license for the code separately, and document any terms or attribution that apply to the exported data.
