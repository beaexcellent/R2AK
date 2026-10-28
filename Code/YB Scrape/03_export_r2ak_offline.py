#!/usr/bin/env python3
"""Download and decode public YB Tracking race-position data.

Default race: Race to Alaska 2026 (r2ak2026)
Outputs:
  race_setup.json        original race/team metadata
  all_positions3.bin     original binary track archive
  positions.csv          one normalized row per fix
  positions.jsonl        same records as newline-delimited JSON
  teams.csv              one row per team
  manifest.json          provenance, hashes, and row counts
  tracks/0-<team_id>.json legacy Swiftsure/R2AK-compatible file per racer

Use responsibly. Confirm the event operator's terms before republishing data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://yb.tl"
USER_AGENT = "r2ak-position-archiver/1.0 (+public research/archive)"


class DecodeError(RuntimeError):
    pass


def fetch(url: str, attempts: int = 6, timeout: int = 60) -> bytes:
    """Fetch a public URL with bounded exponential backoff."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,*/*;q=0.8",
        "Referer": "https://r2ak.com/tracker/",
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            status = getattr(exc, "code", None)
            if status is not None and status not in {429, 500, 502, 503, 504}:
                raise
            if attempt == attempts - 1:
                break
            delay = min(30.0, 1.0 * (2**attempt)) + random.uniform(0, 0.25)
            print(f"Fetch failed ({exc}); retrying in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def decode_json(raw: bytes) -> dict[str, Any]:
    for encoding in ("utf-8", "latin-1"):
        try:
            value = json.loads(raw.decode(encoding))
            if not isinstance(value, dict):
                raise ValueError("RaceSetup was not a JSON object")
            return value
        except UnicodeDecodeError:
            continue
    raise ValueError("RaceSetup could not be decoded")


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read(self, fmt: str) -> int:
        size = struct.calcsize(fmt)
        if self.remaining() < size:
            raise DecodeError(
                f"Unexpected EOF at byte {self.pos}; needed {size}, had {self.remaining()}"
            )
        value = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += size
        return int(value)

    def peek_u8(self) -> int:
        if not self.remaining():
            raise DecodeError("Unexpected EOF")
        return self.data[self.pos]


def decode_all_positions3(data: bytes) -> tuple[int, int, list[dict[str, Any]]]:
    """Decode YB's big-endian AllPositions3 stream.

    The common R2AK feed carries DTF (flag 0x02). Other documented optional
    fields are retained when present. Unknown flag bits fail loudly so a
    format change cannot silently corrupt an archive.
    """
    r = Reader(data)
    if r.remaining() < 5:
        raise DecodeError("AllPositions3 is too short")

    flags = r.read(">B")
    base_timestamp = r.read(">I")
    if flags & ~0x0F:
        raise DecodeError(f"Unsupported flag bits: 0x{flags:02x}")

    trackers: list[dict[str, Any]] = []
    while r.remaining():
        if r.remaining() < 4:
            raise DecodeError(f"Trailing {r.remaining()} byte(s) at offset {r.pos}")
        team_id = r.read(">H")
        count = r.read(">H")
        moments: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None

        for _ in range(count):
            compressed = bool(r.peek_u8() & 0x80)
            if compressed:
                if previous is None:
                    raise DecodeError(f"Team {team_id} starts with a delta record")
                delta_seconds = r.read(">H") & 0x7FFF
                moment: dict[str, Any] = {
                    "at": previous["at"] - delta_seconds,
                    "lat_raw": previous["lat_raw"] + r.read(">h"),
                    "lon_raw": previous["lon_raw"] + r.read(">h"),
                }
                if flags & 0x01:
                    # Altitude is encoded as an int16 value, not a delta.
                    moment["alt"] = r.read(">h")
                if flags & 0x02:
                    moment["dtf_raw"] = previous.get("dtf_raw", 0) + r.read(">h")
                    if flags & 0x04:
                        # Lap is a one-byte absolute value and is present only with DTF.
                        moment["lap"] = r.read(">B")
                if flags & 0x08:
                    # PC is a scaled delta from the previous value.
                    moment["pc"] = previous.get("pc", 0.0) + r.read(">h") / 32000.0
            else:
                moment = {
                    "at": base_timestamp + r.read(">I"),
                    "lat_raw": r.read(">i"),
                    "lon_raw": r.read(">i"),
                }
                if flags & 0x01:
                    # YB uses int16 altitude in both absolute and compressed records.
                    moment["alt"] = r.read(">h")
                if flags & 0x02:
                    moment["dtf_raw"] = r.read(">i")
                    if flags & 0x04:
                        moment["lap"] = r.read(">B")
                if flags & 0x08:
                    moment["pc"] = r.read(">i") / 21000000.0

            previous = moment
            decoded: dict[str, Any] = {
                "timestamp": moment["at"],
                "timestamp_utc": datetime.fromtimestamp(
                    moment["at"], tz=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "latitude": moment["lat_raw"] / 100000.0,
                "longitude": moment["lon_raw"] / 100000.0,
            }
            if "dtf_raw" in moment:
                decoded["distance_to_finish_nm"] = moment["dtf_raw"] / 1000.0
            for key in ("alt", "lap", "pc"):
                if key in moment:
                    decoded[key] = moment[key]
            moments.append(decoded)

        moments.sort(key=lambda item: item["timestamp"])
        trackers.append({"team_id": team_id, "moments": moments})

    return flags, base_timestamp, trackers


def distance_and_bearing(a: dict[str, Any], b: dict[str, Any]) -> tuple[float, int]:
    """Return great-circle distance in nautical miles and initial bearing."""
    lat1 = math.radians(float(a["latitude"]))
    lat2 = math.radians(float(b["latitude"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["longitude"]) - float(a["longitude"]))
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance_nm = 3440.065 * 2 * math.asin(min(1.0, math.sqrt(hav)))
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = int(round((math.degrees(math.atan2(y, x)) + 360.0) % 360.0)) % 360
    return distance_nm, bearing


def legacy_status(team: dict[str, Any]) -> tuple[str, str]:
    """Map YB team status to the compact legacy status fields."""
    raw = str(team.get("status") or "active").strip()
    normalized = raw.lower()
    if normalized in {"racing", "started"}:
        normalized = "active"
    display = normalized.replace("_", " ").title()
    return normalized, display


def legacy_payload(moments: list[dict[str, Any]], team: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert one chronologically sorted track to the legacy compact schema."""
    stat, dstat = legacy_status(team)
    result: list[dict[str, Any]] = []
    for index, moment in enumerate(moments):
        if len(moments) < 2:
            speed, heading = 0.0, 0
        else:
            left = index - 1 if index else 0
            right = index if index else 1
            a, b = moments[left], moments[right]
            elapsed_hours = (int(b["timestamp"]) - int(a["timestamp"])) / 3600.0
            distance_nm, heading = distance_and_bearing(a, b)
            speed = distance_nm / elapsed_hours if elapsed_hours > 0 else 0.0
        result.append({
            "ts": int(moment["timestamp"]),
            "lt": round(float(moment["latitude"]), 5),
            "ln": round(float(moment["longitude"]), 5),
            "s": round(speed, 1),
            "h": heading,
            "stat": stat,
            "dstat": dstat,
        })
    return result


def write_legacy_tracks(
    output_dir: Path,
    trackers: list[dict[str, Any]],
    team_by_id: dict[int, dict[str, Any]],
    filename_prefix: int = 0,
) -> int:
    """Write one tracks/<prefix>-<team_id>.json file per tracker."""
    tracks_dir = output_dir / "tracks"
    tracks_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for tracker in trackers:
        team_id = int(tracker["team_id"])
        document = {
            "error": None,
            "message": "Requested completed successfully.",
            "payload": legacy_payload(tracker["moments"], team_by_id.get(team_id, {})),
        }
        path = tracks_dir / f"{filename_prefix}-{team_id}.json"
        path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        count += 1
    return count


def scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_outputs(output_dir: Path, race_key: str, setup_raw: bytes, positions_raw: bytes) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    setup = decode_json(setup_raw)
    flags, base_timestamp, trackers = decode_all_positions3(positions_raw)

    (output_dir / "race_setup.json").write_bytes(setup_raw)
    (output_dir / "all_positions3.bin").write_bytes(positions_raw)

    teams = setup.get("teams", [])
    team_by_id = {int(team["id"]): team for team in teams if "id" in team}
    legacy_file_count = write_legacy_tracks(output_dir, trackers, team_by_id)

    team_fields = sorted({key for team in teams for key in team.keys()})
    with (output_dir / "teams.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=team_fields)
        writer.writeheader()
        writer.writerows({key: scalar(team.get(key)) for key in team_fields} for team in teams)

    fields = [
        "race_key", "team_id", "team_name", "status", "timestamp",
        "timestamp_utc", "latitude", "longitude", "distance_to_finish_nm",
        "alt", "lap", "pc",
    ]
    row_count = 0
    min_ts: int | None = None
    max_ts: int | None = None

    with (output_dir / "positions.csv").open("w", newline="", encoding="utf-8") as csv_file, \
         (output_dir / "positions.jsonl").open("w", encoding="utf-8") as jsonl_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for tracker in trackers:
            team = team_by_id.get(tracker["team_id"], {})
            for moment in tracker["moments"]:
                row = {
                    "race_key": race_key,
                    "team_id": tracker["team_id"],
                    "team_name": team.get("name", ""),
                    "status": team.get("status", ""),
                    **moment,
                }
                writer.writerow(row)
                jsonl_file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                ts = int(moment["timestamp"])
                min_ts = ts if min_ts is None else min(min_ts, ts)
                max_ts = ts if max_ts is None else max(max_ts, ts)
                row_count += 1

    manifest = {
        "race_key": race_key,
        "race_title": setup.get("title") or (setup.get("pro") or {}).get("name"),
        "source_viewer": f"{BASE_URL}/{race_key}",
        "source_setup": f"{BASE_URL}/JSON/{race_key}/RaceSetup",
        "source_positions": f"{BASE_URL}/BIN/{race_key}/AllPositions3",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decoder": {"format": "AllPositions3", "flags": flags, "base_timestamp": base_timestamp},
        "counts": {"teams": len(teams), "trackers": len(trackers), "positions": row_count, "legacy_track_files": legacy_file_count},
        "time_range_utc": {
            "first": datetime.fromtimestamp(min_ts, timezone.utc).isoformat().replace("+00:00", "Z") if min_ts else None,
            "last": datetime.fromtimestamp(max_ts, timezone.utc).isoformat().replace("+00:00", "Z") if max_ts else None,
        },
        "sha256": {
            "race_setup.json": hashlib.sha256(setup_raw).hexdigest(),
            "all_positions3.bin": hashlib.sha256(positions_raw).hexdigest(),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert cached YB files without network access")
    parser.add_argument("--race", default="r2ak2026")
    parser.add_argument("--source", type=Path, default=Path("source_data"))
    parser.add_argument("--output", type=Path, default=Path("data") / "r2ak2026")
    args = parser.parse_args()
    setup_path = args.source / "race_setup.json"
    positions_path = args.source / "all_positions3.bin"
    if not positions_path.exists():
        positions_path = args.source / "all_positions3.txt"
    if not setup_path.exists() or not positions_path.exists():
        raise SystemExit("Missing cached input. Run 01_download_r2ak.py first.")
    setup_raw = setup_path.read_bytes()
    positions_raw = positions_path.read_bytes()
    print(f"Reading cached metadata: {setup_path} ({len(setup_raw):,} bytes)", file=sys.stderr)
    print(f"Reading cached positions: {positions_path} ({len(positions_raw):,} bytes)", file=sys.stderr)
    try:
        write_outputs(args.output, args.race, setup_raw, positions_raw)
    except DecodeError as exc:
        print(f"\nDECODE ERROR: {exc}", file=sys.stderr)
        print("The cached files were preserved. Run 02_inspect_r2ak_download.py and share its output,", file=sys.stderr)
        print("or attach source_data/all_positions3.bin so the format can be examined offline.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
