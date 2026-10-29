#!/usr/bin/env python3
"""Capture one MAProgress event's browser-delivered data exactly once."""
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit("Install Playwright first: pip install playwright && playwright install chromium")

def safe_name(url, index, content_type):
    path=urlparse(url).path.rstrip('/').split('/')[-1] or 'index'
    path=re.sub(r'[^A-Za-z0-9._-]+','_',path)[:80]
    ext='.json' if 'json' in content_type else '.txt'
    if '.' not in path: path += ext
    return f"{index:04d}_{path}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',required=True)
    ap.add_argument('--dir',type=Path,required=True)
    ap.add_argument('--wait',type=int,default=20,help='seconds to wait after page load')
    ap.add_argument('--force',action='store_true')
    args=ap.parse_args()
    marker=args.dir/'capture_manifest.json'
    if marker.exists() and not args.force:
        raise SystemExit(f"Capture already exists at {args.dir}. Use --force only to replace it.")
    args.dir.mkdir(parents=True,exist_ok=True); raw=args.dir/'raw'; raw.mkdir(exist_ok=True)
    records=[]
    with sync_playwright() as p:
        try: browser=p.chromium.launch(headless=True)
        except Exception:
            try: browser=p.chromium.launch(headless=True,channel='chrome')
            except Exception as exc:
                raise SystemExit("No Playwright browser found. Run: playwright install chromium") from exc
        context=browser.new_context(user_agent='Mozilla/5.0 R2AK research archive')
        page=context.new_page()
        def save_response(response):
            ctype=response.headers.get('content-type','').lower()
            rtype=response.request.resource_type
            if rtype not in {'xhr','fetch','document'} and not any(x in ctype for x in ('json','javascript','text/plain')):
                return
            try: body=response.body()
            except Exception: return
            if not body: return
            i=len(records); name=safe_name(response.url,i,ctype)
            (raw/name).write_bytes(body)
            records.append({'file':f'raw/{name}','url':response.url,'status':response.status,'resource_type':rtype,'content_type':ctype,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
        page.on('response',save_response)
        page.goto(args.url,wait_until='domcontentloaded',timeout=120000)
        page.wait_for_timeout(args.wait*1000)
        (args.dir/'rendered_page.html').write_text(page.content(),encoding='utf-8')
        title=page.title(); final_url=page.url
        browser.close()
    manifest={'source_url':args.url,'final_url':final_url,'title':title,'captured_at_utc':datetime.now(timezone.utc).isoformat(),'responses':records}
    marker.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"Captured {len(records)} responses in {args.dir}")
if __name__=='__main__': main()
