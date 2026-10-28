#!/usr/bin/env python3
"""Inspect cached YB files without contacting the server."""
import argparse, gzip, hashlib, json, struct
from datetime import datetime, timezone
from pathlib import Path

def preview(data, start=0, n=48): return data[start:start+n].hex(" ")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dir",type=Path,default=Path("source_data")); args=ap.parse_args()
    setup=args.dir/"race_setup.json"; binary=args.dir/"all_positions3.bin"
    if not binary.exists(): binary=args.dir/"all_positions3.txt"
    print(f"setup: {setup} ({setup.stat().st_size:,} bytes)")
    raw=setup.read_bytes()
    try: text=raw.decode("utf-8-sig")
    except UnicodeDecodeError: text=raw.decode("latin-1")
    obj=json.loads(text); print(f"title: {obj.get('title')}  teams: {len(obj.get('teams',[]))}")
    data=binary.read_bytes(); print(f"binary: {binary} ({len(data):,} bytes) sha256={hashlib.sha256(data).hexdigest()}")
    if data[:2]==b'\x1f\x8b': print("gzip wrapper detected"); data=gzip.decompress(data)
    print("first bytes:",preview(data))
    if data[:1] in (b'<',b'{',b'['): raise SystemExit("ERROR: positions file looks like text/HTML/JSON, not YB binary")
    if len(data)<9: raise SystemExit("ERROR: positions file is too short")
    flags=data[0]; base=struct.unpack_from(">I",data,1)[0]; team,count=struct.unpack_from(">HH",data,5)
    print(f"flags=0x{flags:02x} base={base} ({datetime.fromtimestamp(base,timezone.utc).isoformat()}) first_team={team} first_count={count}")
    if flags & ~0x0f: print("WARNING: unknown flag bits are set")
if __name__=="__main__": main()
