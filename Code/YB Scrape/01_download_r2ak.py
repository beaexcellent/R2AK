#!/usr/bin/env python3
"""Download R2AK source files once. Existing files are never overwritten unless --force is used."""
import argparse, hashlib, json, random, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://yb.tl"
UA = "r2ak-position-archiver/1.1 (+public research/archive)"

def fetch(url, attempts=6):
    req = Request(url, headers={"User-Agent": UA, "Referer": "https://r2ak.com/tracker/", "Accept": "*/*"})
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=60) as response:
                body = response.read()
                return body, dict(response.headers), response.status
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt == attempts - 1 or getattr(exc, "code", 500) not in {429,500,502,503,504}:
                raise
            time.sleep(min(30, 2 ** attempt) + random.random()/4)

def save(path, body):
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--race", default="r2ak2026")
    ap.add_argument("--dir", type=Path, default=Path("source_data"))
    ap.add_argument("--force", action="store_true")
    args=ap.parse_args(); args.dir.mkdir(parents=True, exist_ok=True)
    specs=[("race_setup.json",f"{BASE}/JSON/{args.race}/RaceSetup"),("all_positions3.bin",f"{BASE}/BIN/{args.race}/AllPositions3")]
    manifest={"race":args.race,"downloaded_at_utc":datetime.now(timezone.utc).isoformat(),"files":{}}
    for name,url in specs:
        path=args.dir/name
        if path.exists() and not args.force:
            print(f"Keeping existing {path} ({path.stat().st_size:,} bytes)")
            body=path.read_bytes(); headers={}; status="cached"
        else:
            print(f"Downloading {url}")
            body,headers,status=fetch(url); save(path,body)
            print(f"Saved {path} ({len(body):,} bytes)")
        manifest["files"][name]={"url":url,"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest(),"status":status,"content_type":headers.get("Content-Type")}
    (args.dir/"download_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
