#!/usr/bin/env python3
"""Inspect a cached MAProgress browser capture without network access."""
import argparse, json, re
from pathlib import Path

def js_object(text):
    start=text.find('(')+1 if 'addHistory(' in text else text.find('=')+1
    candidate=text[start:].lstrip()
    candidate=re.sub(r'([{,])([A-Za-z_$][\w$]*):',r'\1"\2":',candidate)
    return json.JSONDecoder().raw_decode(candidate)[0]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dir',type=Path,required=True); args=ap.parse_args()
    manifest=json.loads((args.dir/'capture_manifest.json').read_text(encoding='utf-8'))
    print('title:',manifest.get('title')); print('source:',manifest.get('source_url')); print('responses:',len(manifest['responses']))
    histories=[]; members={}; fms=None
    for rec in manifest['responses']:
        p=args.dir/rec['file']; text=p.read_text(encoding='utf-8',errors='replace')
        if 'mp.l=' in text:
            try:
                obj=js_object(text); fms=obj.get('fms'); print(f"latest-position payload: {rec['file']} fms={fms} trackers={len(obj.get('ls',[]))}")
            except Exception as e: print('could not parse',rec['file'],e)
        if 'addHistory(' in text:
            try:
                obj=js_object(text); locations=obj.get('l',[]); count=sum(len(x.get('p') or []) for x in locations)
                histories.append((rec['file'],len(locations),count))
            except Exception as e: print('could not parse',rec['file'],e)
        if 'mp.m=' in text:
            pat=re.compile(r'Ft:(?P<ft>-?\d+(?:\.\d+)?),h:[^,]*,H:[^,]*,i:(?P<id>\d+).*?,t:"(?P<name>(?:\\.|[^"])*)"')
            members.update({m.group('id'):json.loads('"'+m.group('name')+'"') for m in pat.finditer(text)})
    for file,trackers,points in histories: print(f"history payload: {file} trackers={trackers} points={points:,}")
    print('member records:',len(members)); print('sample:',list(members.items())[:5])
    if not histories: raise SystemExit('No MAProgress addHistory payload was found.')
    if fms is None: print('WARNING: base timestamp fms was not found.')
if __name__=='__main__': main()
