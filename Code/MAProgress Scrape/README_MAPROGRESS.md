# R2AK MAProgress Tracker Data Exporter

Download, preserve, inspect, and export historical Race to Alaska tracker data from MAProgress.

The toolkit uses a browser to capture the source data once, then performs all inspection and conversion offline. It preserves the original MAProgress responses, creates normalized CSV and JSONL datasets, and generates one legacy-compatible JSON track file per tracker.

## Supported R2AK events

The following event viewers are known:

- R2AK 2022 Proving Ground: `https://r2ak2022provingground.maprogress.com/`
- R2AK 2022 full race: `https://r2ak2022.maprogress.com/`
- R2AK 2023 Proving Ground: `https://r2ak2023provingground.maprogress.com/`
- R2AK 2023 full race: `https://r2ak2023.maprogress.com/`

Suggested local race keys:

```text
r2ak2022-proving-ground
r2ak2022
r2ak2023-proving-ground
r2ak2023
```

These local keys identify directories and exported datasets. They are not credentials or MAProgress API keys.

## Why three scripts?

Retrieval is deliberately separated from inspection and conversion:

1. `01_capture_maprogress.py` opens the event viewer in Chromium and saves its browser-delivered responses.
2. `02_inspect_maprogress.py` inventories and validates the cached capture offline.
3. `03_export_maprogress_offline.py` converts the cached MAProgress data into normalized and legacy-compatible files offline.

Once an event has been captured, scripts 02 and 03 can be run repeatedly without contacting MAProgress again.

## Files

```text
01_capture_maprogress.py
02_inspect_maprogress.py
03_export_maprogress_offline.py
requirements_maprogress.txt
```

Use the current scripts from `maprogress_r2ak_toolkit_v2.zip`.

## Requirements

- Windows 10 or newer
- Miniconda or Anaconda
- A 64-bit Conda environment
- Python 3.12
- Playwright command-line tooling
- Playwright Python bindings
- Chromium installed through Playwright

Scripts 02 and 03 use only Python's standard library. Script 01 additionally requires Playwright and Chromium.

## Recommended Conda setup

The Conda packages `playwright` and `playwright-python` serve different roles:

- `playwright` provides command-line and browser tooling.
- `playwright-python` provides the importable Python API used by script 01.

Create a dedicated environment:

```bat
conda create -n r2ak-maprogress -c conda-forge python=3.12 playwright playwright-python
```

Activate it:

```bat
conda activate r2ak-maprogress
```

Install Chromium:

```bat
python -m playwright install chromium
```

Validate the Python bindings:

```bat
python -c "from playwright.sync_api import sync_playwright; print('Playwright Python import OK')"
```

Validate Chromium:

```bat
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); print('Chromium launch OK'); b.close(); p.stop()"
```

Expected output:

```text
Chromium launch OK
```

### Existing Conda environment

If the environment already contains `playwright` but Python reports:

```text
ModuleNotFoundError: No module named 'playwright'
```

install the separate Python bindings:

```bat
conda install -c conda-forge playwright-python
```

### Verify the active interpreter

```bat
where python
python -c "import sys; print(sys.executable)"
```

The first path should point into:

```text
...\\miniconda3\\envs\\r2ak-maprogress\\python.exe
```

## Quick start

Run these commands from the directory containing the scripts. The examples use Windows Command Prompt or Anaconda Prompt, where `^` continues a command onto the next line.

### 1. Capture the event once

#### R2AK 2022 Proving Ground

```bat
python 01_capture_maprogress.py ^
  --url "https://r2ak2022provingground.maprogress.com/" ^
  --dir ".\source_data\r2ak2022-proving-ground"
```

#### R2AK 2022 full race

```bat
python 01_capture_maprogress.py ^
  --url "https://r2ak2022.maprogress.com/" ^
  --dir ".\source_data\r2ak2022"
```

#### R2AK 2023 Proving Ground

```bat
python 01_capture_maprogress.py ^
  --url "https://r2ak2023provingground.maprogress.com/" ^
  --dir ".\source_data\r2ak2023-proving-ground"
```

#### R2AK 2023 full race

```bat
python 01_capture_maprogress.py ^
  --url "https://r2ak2023.maprogress.com/" ^
  --dir ".\source_data\r2ak2023"
```

The capture script waits 20 seconds after the initial page load so browser data requests can finish. To allow more time:

```bat
python 01_capture_maprogress.py ^
  --url "https://r2ak2023.maprogress.com/" ^
  --dir ".\source_data\r2ak2023" ^
  --wait 45
```

If `capture_manifest.json` already exists, the script refuses to overwrite it. To intentionally replace a capture, add:

```text
--force
```

Use `--force` sparingly.

### 2. Inspect the cached capture

```bat
python 02_inspect_maprogress.py ^
  --dir ".\source_data\r2ak2023"
```

The inspector reports:

- Event title and source URL
- Number of captured responses
- MAProgress base timestamp (`fms`)
- Number of tracker records in the latest-position payload
- Number of history segments and position points
- Number of tracker-to-team member records
- A sample of tracker IDs and team names

A validated 2023 full-race capture produced output resembling:

```text
title: Race to Alaska 2023 - MAProgress
responses: 27
latest-position payload: raw/0009_mapl.txt fms=1686250800 trackers=30
history payload: raw/0023_maph.txt trackers=137 points=45,571
member records: 29
```

Multiple history responses may contain identical data. The exporter identifies duplicate history responses by SHA-256 hash and processes only one copy.

### 3. Export the event offline

#### R2AK 2023 full race

```bat
python 03_export_maprogress_offline.py ^
  --race-key "r2ak2023" ^
  --source ".\source_data\r2ak2023" ^
  --output ".\data\r2ak2023"
```

#### R2AK 2023 Proving Ground

```bat
python 03_export_maprogress_offline.py ^
  --race-key "r2ak2023-proving-ground" ^
  --source ".\source_data\r2ak2023-proving-ground" ^
  --output ".\data\r2ak2023-proving-ground"
```

#### R2AK 2022 full race

```bat
python 03_export_maprogress_offline.py ^
  --race-key "r2ak2022" ^
  --source ".\source_data\r2ak2022" ^
  --output ".\data\r2ak2022"
```

#### R2AK 2022 Proving Ground

```bat
python 03_export_maprogress_offline.py ^
  --race-key "r2ak2022-proving-ground" ^
  --source ".\source_data\r2ak2022-proving-ground" ^
  --output ".\data\r2ak2022-proving-ground"
```

Script 03 makes no network requests.

## Recommended repository layout

```text
R2AK/
├── Code/
│   └── MAProgress Scrape/
│       ├── 01_capture_maprogress.py
│       ├── 02_inspect_maprogress.py
│       ├── 03_export_maprogress_offline.py
│       └── README.md
├── source_data/
│   ├── r2ak2022-proving-ground/
│   ├── r2ak2022/
│   ├── r2ak2023-proving-ground/
│   └── r2ak2023/
└── data/
    ├── r2ak2022-proving-ground/
    ├── r2ak2022/
    ├── r2ak2023-proving-ground/
    └── r2ak2023/
```

## Raw capture output

Each source directory contains:

```text
source_data/r2ak2023/
├── capture_manifest.json
├── rendered_page.html
└── raw/
    ├── 0000_index.txt
    ├── 0009_mapl.txt
    ├── 0013_mapm.txt
    ├── 0023_maph.txt
    └── ...
```

### `capture_manifest.json`

Records the capture's provenance, including:

- Original event URL
- Final browser URL
- Page title
- Capture time
- Saved response filenames
- Original response URLs
- HTTP status
- Browser resource type
- Content type
- Byte count
- SHA-256 hash

### `rendered_page.html`

The browser-rendered event page after the capture wait period.

### `raw/`

Preserves browser-delivered source responses. Important MAProgress payloads commonly include:

- `mapl`: latest tracker positions and event timing metadata
- `mapm`: member and team metadata
- `maph`: complete historical tracker positions

The exact numeric prefixes may differ between captures. Scripts 02 and 03 identify payloads by their contents rather than depending on fixed filenames.

## MAProgress source format

MAProgress historical positions are embedded in JavaScript calls rather than ordinary JSON files:

```javascript
mp.group.locations.addHistory(...)
```

A history point is represented as an array:

```text
[latitude, longitude, seconds_from_base_time, value_1, value_2]
```

The absolute timestamp is calculated as:

```text
timestamp = fms + seconds_from_base_time
```

where `fms` is the event's Unix base timestamp from the `mapl` payload.

The final two source values are preserved without assigning unsupported meanings to them.

## Exported files

A completed export contains:

```text
data/r2ak2023/
├── manifest.json
├── positions.csv
├── positions.jsonl
├── teams.csv
└── tracks/
    ├── 0-56004.json
    ├── 0-56005.json
    └── ...
```

### `positions.csv`

One normalized row per unique position fix.

Columns:

- `race_key`
- `team_id`
- `team_name`
- `status`
- `timestamp`
- `timestamp_utc`
- `latitude`
- `longitude`
- `maprogress_time_offset_s`
- `maprogress_value_1`
- `maprogress_value_2`

### `positions.jsonl`

The same normalized position records as newline-delimited JSON. Each line is an independent JSON object.

### `teams.csv`

One row per tracker ID found in the history data.

Columns:

- `id`
- `name`
- `status`
- `track_file`
- `positions`

Some tracker histories may not have corresponding member metadata. Those tracks are retained with a blank `name` rather than discarded.

### `manifest.json`

Records:

- Local race key
- Source event URL
- MAProgress `fms` base timestamp
- Export time
- Team, position, and track-file counts
- SHA-256 hash of the capture manifest

### `tracks/*.json`

One legacy-compatible JSON file per tracker. The filename uses the MAProgress tracker ID:

```text
tracks/0-56004.json
         └─ tracker ID 56004
```

Match that ID to the `id` column in `teams.csv`.

Example track file:

```json
{
  "error": null,
  "message": "Requested completed successfully.",
  "payload": [
    {
      "ts": 1686570871,
      "lt": 48.63131,
      "ln": -123.34381,
      "s": 5.7,
      "h": 301,
      "stat": "active",
      "dstat": "Active"
    }
  ]
}
```

Legacy fields:

- `ts`: Unix timestamp in seconds
- `lt`: latitude in decimal degrees
- `ln`: longitude in decimal degrees
- `s`: calculated speed in knots
- `h`: calculated course over ground in degrees
- `stat`: normalized status
- `dstat`: display-form status

Speed and heading are calculated from consecutive timestamped positions. The first point uses the segment from the first point to the second. A one-point track receives speed `0.0` and heading `0`.

## Data processing details

### Duplicate responses

Browser loading can request the same history payload more than once. Script 03 hashes history responses and ignores byte-identical duplicates.

### Duplicate fixes

The exporter deduplicates fixes using:

```text
team_id + timestamp + latitude + longitude
```

### History segments

The number of MAProgress history objects can exceed the number of racers because one tracker may appear in multiple history segments or record groups. The exporter consolidates all segments by tracker ID.

### Invalid coordinates

Records outside valid latitude and longitude ranges are not exported.

### Unknown raw values

`maprogress_value_1` and `maprogress_value_2` preserve source fields whose definitions were not established from the captured data. They are intentionally not relabeled as speed, elevation, distance, or another metric without supporting documentation.

## Troubleshooting

### `ModuleNotFoundError: No module named 'playwright'`

Confirm both Conda packages are installed:

```bat
conda list playwright
conda list playwright-python
```

Install the Python bindings if necessary:

```bat
conda install -c conda-forge playwright-python
```

Then test:

```bat
python -c "from playwright.sync_api import sync_playwright; print('Playwright Python import OK')"
```

### `Microsoft Visual C++ 14.0 or greater is required`

This typically means pip attempted to compile `greenlet` from source. Prefer the precompiled Conda packages in a clean Python 3.12 environment rather than installing Playwright with pip.

### Conda reports that the SSL module is unavailable

First test the active Python directly:

```bat
python -c "import ssl; print(ssl.OPENSSL_VERSION)"
```

If this succeeds but Conda fails, deactivate to `(base)` and install into the target environment by name:

```bat
conda deactivate
conda install -n r2ak-maprogress -c conda-forge playwright-python
```

### Script 01 cannot find Chromium

```bat
python -m playwright install chromium
```

Then run the Chromium validation command in the setup section.

### Script 02 reports no latitude or longitude fields

Use the current version of script 02 from toolkit v2. MAProgress stores coordinates positionally inside `addHistory` arrays, not in objects labeled `lat` and `lon`.

### Script 03 cannot find `fms`

Confirm the capture contains a `mapl` response and that script 01 was allowed enough time to finish loading. A new capture with a longer wait may be needed:

```bat
python 01_capture_maprogress.py ^
  --url "EVENT_URL" ^
  --dir ".\source_data\EVENT_KEY" ^
  --wait 45 ^
  --force
```

### Some teams have blank names

A history may include tracker IDs that are absent from the captured member metadata. The exporter preserves those histories and leaves the name blank in `teams.csv`.

## Git considerations

The raw capture can contain large JavaScript and history payloads. Options include:

- Keep `source_data/` out of Git and commit normalized exports plus manifests.
- Commit the raw capture using Git LFS.
- Archive one ZIP per event outside the main repository while retaining its manifest and SHA-256 hashes.

Do not edit raw capture files after collection. Keeping the original bytes allows hashes to remain useful and makes future parser improvements reproducible.

## Responsible use

The toolkit is intended for historical research, analysis, and preservation of publicly displayed race-tracker data. Before redistributing tracker histories, review any applicable race-organizer and tracking-provider terms and consider whether historical participant locations warrant additional handling.

## License

No license is assigned by these scripts to third-party MAProgress or Race to Alaska data. Choose a software license for the scraper code separately, and document any terms or attribution that apply to exported data.
