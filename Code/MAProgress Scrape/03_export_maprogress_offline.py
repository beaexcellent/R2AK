#!/usr/bin/env python3
"""Decode cached MAProgress JavaScript payloads into normalized and legacy R2AK data."""
import argparse,csv,hashlib,json,math,re
from datetime import datetime,timezone
from pathlib import Path

def js_object(text):
    start=text.find('(')+1 if 'addHistory(' in text else text.find('=')+1
    candidate=text[start:].lstrip()
    candidate=re.sub(r'([{,])([A-Za-z_$][\w$]*):',r'\1"\2":',candidate)
    return json.JSONDecoder().raw_decode(candidate)[0]

def distance_bearing(a,b):
    p1,p2=map(math.radians,(a['latitude'],b['latitude'])); dl=math.radians(b['longitude']-a['longitude']); dp=p2-p1
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    nm=3440.065*2*math.asin(min(1,math.sqrt(h))); y=math.sin(dl)*math.cos(p2); x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return nm,int(round((math.degrees(math.atan2(y,x))+360)%360))%360

def parse_capture(source):
    manifest=json.loads((source/'capture_manifest.json').read_text(encoding='utf-8'))
    fms=None; histories=[]; members={}; history_hashes=set()
    member_re=re.compile(r'Ft:(?P<ft>-?\d+(?:\.\d+)?),h:[^,]*,H:[^,]*,i:(?P<id>\d+).*?,t:"(?P<name>(?:\\.|[^"])*)"')
    for rec in manifest['responses']:
        path=source/rec['file']; text=path.read_text(encoding='utf-8',errors='replace')
        if 'mp.l=' in text:
            try: fms=js_object(text).get('fms',fms)
            except Exception: pass
        if 'mp.m=' in text:
            for m in member_re.finditer(text): members[m.group('id')]={'id':m.group('id'),'name':json.loads('"'+m.group('name')+'"'),'status':'active'}
        if 'addHistory(' in text:
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in history_hashes: continue
            history_hashes.add(digest)
            histories.extend(js_object(text).get('l',[]))
    if fms is None: raise SystemExit('Could not find MAProgress fms base timestamp in the captured mapl response.')
    if not histories: raise SystemExit('Could not find a MAProgress addHistory payload in the capture.')
    return manifest,int(fms),histories,members

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--race-key',required=True); args=ap.parse_args()
    manifest,fms,histories,members=parse_capture(args.source); rows=[]
    for hist in histories:
        tid=str(hist.get('u')); team=members.get(tid,{'id':tid,'name':'','status':'active'})
        for point in hist.get('p') or []:
            if len(point)<3 or point[0] is None or point[1] is None or point[2] is None: continue
            lat,lon=float(point[0]),float(point[1])
            if not (-90<=lat<=90 and -180<=lon<=180): continue
            ts=fms+int(float(point[2]))
            rows.append({'race_key':args.race_key,'team_id':tid,'team_name':team['name'],'status':team['status'],'timestamp':ts,'timestamp_utc':datetime.fromtimestamp(ts,timezone.utc).isoformat().replace('+00:00','Z'),'latitude':lat,'longitude':lon,'maprogress_time_offset_s':point[2],'maprogress_value_1':point[3] if len(point)>3 else None,'maprogress_value_2':point[4] if len(point)>4 else None})
    rows=list({(r['team_id'],r['timestamp'],r['latitude'],r['longitude']):r for r in rows}.values()); rows.sort(key=lambda r:(r['team_id'],r['timestamp']))
    if not rows: raise SystemExit('No valid MAProgress position records were decoded.')
    args.output.mkdir(parents=True,exist_ok=True); tracks=args.output/'tracks'; tracks.mkdir(exist_ok=True)
    fields=list(rows[0]);
    with (args.output/'positions.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    with (args.output/'positions.jsonl').open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    groups={}
    for r in rows: groups.setdefault(r['team_id'],[]).append(r)
    team_rows=[]
    for tid,fixes in groups.items():
        team=members.get(tid,{'id':tid,'name':'','status':'active'}); payload=[]
        for i,r in enumerate(fixes):
            if len(fixes)>1:
                a,b=(fixes[0],fixes[1]) if i==0 else (fixes[i-1],r); nm,heading=distance_bearing(a,b); hours=(b['timestamp']-a['timestamp'])/3600; speed=nm/hours if hours>0 else 0
            else: speed,heading=0,0
            payload.append({'ts':r['timestamp'],'lt':round(r['latitude'],5),'ln':round(r['longitude'],5),'s':round(speed,1),'h':heading,'stat':'active','dstat':'Active'})
        filename=f'0-{tid}.json'; (tracks/filename).write_text(json.dumps({'error':None,'message':'Requested completed successfully.','payload':payload},separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8')
        team_rows.append({'id':tid,'name':team['name'],'status':team['status'],'track_file':filename,'positions':len(fixes)})
    with (args.output/'teams.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=['id','name','status','track_file','positions']); w.writeheader(); w.writerows(team_rows)
    out={'race_key':args.race_key,'source_url':manifest.get('source_url'),'maprogress_fms':fms,'exported_at_utc':datetime.now(timezone.utc).isoformat(),'counts':{'teams':len(team_rows),'positions':len(rows),'track_files':len(team_rows)},'capture_manifest_sha256':hashlib.sha256((args.source/'capture_manifest.json').read_bytes()).hexdigest()}
    (args.output/'manifest.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
