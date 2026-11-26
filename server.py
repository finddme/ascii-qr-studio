"""Loopback-only studio API. No destination URLs are fetched."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
import uuid
import warnings
import zipfile
from datetime import datetime, timezone
from PIL import Image, ImageOps
from ascii_qr import create_project, validate_url

ROOT = Path(__file__).parent
STATIC={'/':'index.html','/app.js':'app.js','/fx.js':'fx.js','/style.css':'style.css','/fonts/Galmuri11-Bold.woff2':'fonts/Galmuri11-Bold.woff2'}
DATA = Path(os.environ.get('ASCII_DATA_DIR', ROOT/'dev'))
MAX_BODY = 18 * 1024 * 1024
BUSY = threading.Lock()
JOB_ID = re.compile(r'^[0-9a-f]{32}$')
Image.MAX_IMAGE_PIXELS = 24_000_000


def settings(payload):
    url = validate_url(str(payload.get('url', '')))
    result = {'url': url}
    for name, default, low, high in [('columns',64,16,128),('min_version',6,1,10)]:
        value = payload.get(name,default)
        if type(value) is not int or not low <= value <= high: raise ValueError(f'{name}: {low}–{high}')
        result[name] = value
    for name, default, values in [('fit','cover',('cover','contain')),('theme','dark',('dark','light'))]:
        value=payload.get(name,default)
        if value not in values: raise ValueError(f'Invalid {name}')
        result[name]=value
    crop=payload.get('crop')
    if crop is not None:
        if not isinstance(crop,list) or len(crop)!=4 or any(type(v) not in (int,float) or not 0<=v<=1 for v in crop): raise ValueError('Invalid crop')
        if not (crop[0]<crop[2] and crop[1]<crop[3]): raise ValueError('Crop must have positive area')
    result['crop']=crop
    return result


def job_path(job_id):
    if not JOB_ID.fullmatch(job_id): raise ValueError('Invalid job ID')
    return DATA/'jobs'/job_id


def run_job(payload):
    opts=settings(payload)
    if payload.get('reuse'):
        source=job_path(str(payload['reuse']))/'input.png'
        raw=source.read_bytes()
    else:
        raw=base64.b64decode(payload.get('image',''),validate=True)
    if not raw or len(raw)>12*1024*1024: raise ValueError('Image must be 1 byte–12 MB')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.width*opened.height>24_000_000: raise ValueError('Image exceeds 24 megapixels')
            image=ImageOps.exif_transpose(opened).convert('RGBA')
            background=Image.new('RGBA',image.size,'white' if opts['theme']=='light' else 'black')
            image=Image.alpha_composite(background,image).convert('RGB')
    identifier=uuid.uuid4().hex
    folder=job_path(identifier); folder.mkdir(parents=True)
    image.save(folder/'input.png')
    info={'id':identifier,'created':datetime.now(timezone.utc).isoformat(), 'status':'running',
          'settings':opts, 'version':(ROOT/'VERSION').read_text().strip(),
          'input_sha256':hashlib.sha256((folder/'input.png').read_bytes()).hexdigest()}
    (folder/'job.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    try:
        report=create_project(image,output=folder/'result',**opts)
        info['status']='ready' if report['selected'] else 'failed'
        info['selected']=report['selected']
        info['checks']=next((sum(c['passed'] for check in x['checks'].values() for c in check['cases']) for x in report['candidates'] if x['name']==report['selected']),0)
        info['qr_modules']=report['qr_modules']
        info['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder/'result').glob('selected-*.png')}
    except Exception:
        info['status']='error'
        (folder/'job.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
        raise
    (folder/'job.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    return info


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # URLs and filenames stay out of server logs.
    def send_bytes(self,data,ctype='application/json; charset=utf-8',status=200,download=None):
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        if download: self.send_header('Content-Disposition',f'attachment; filename="{download}"')
        self.end_headers(); self.wfile.write(data)
    def respond(self,value,status=200): self.send_bytes(json.dumps(value,ensure_ascii=False).encode(),status=status)
    def allowed(self):
        host=self.headers.get('Host','')
        if urlsplit('http://'+host).hostname not in ('localhost','127.0.0.1','::1'): return False
        origin=self.headers.get('Origin')
        return not origin or (urlsplit(origin).scheme=='http' and urlsplit(origin).netloc==host)
    def do_GET(self):
        if not self.allowed(): return self.respond({'error':'Local access only'},403)
        path=unquote(urlsplit(self.path).path)
        try:
            if path=='/api/health': return self.respond({'ok':True,'version':(ROOT/'VERSION').read_text().strip()})
            if path=='/api/jobs':
                jobs=[json.loads(p.read_text()) for p in (DATA/'jobs').glob('*/job.json')]
                return self.respond(sorted(jobs,key=lambda x:x['created'],reverse=True))
            match=re.fullmatch(r'/api/jobs/([0-9a-f]{32})/download',path)
            if match:
                folder=job_path(match[1]);info=json.loads((folder/'job.json').read_text())
                if info['status']!='ready': return self.respond({'error':'No validated result'},409)
                data=io.BytesIO()
                with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as archive:
                    archive.write(folder/'job.json','job.json')
                    for item in (folder/'result').rglob('*'):
                        if item.is_file(): archive.write(item,item.relative_to(folder))
                return self.send_bytes(data.getvalue(),'application/zip',download='ascii-qr-'+match[1][:8]+'.zip')
            match=re.fullmatch(r'/files/([0-9a-f]{32})/(.+)',path)
            if match:
                folder=job_path(match[1]).resolve();target=(folder/match[2]).resolve()
                if not target.is_relative_to(folder): return self.respond({'error':'Not found'},404)
            elif path in STATIC:
                target=ROOT/'web'/STATIC[path]
            else: return self.respond({'error':'Not found'},404)
            if not target.is_file(): return self.respond({'error':'Not found'},404)
            kind='font/woff2' if target.suffix=='.woff2' else mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            return self.send_bytes(target.read_bytes(),kind)
        except (OSError,ValueError): return self.respond({'error':'Not found'},404)
    def do_POST(self):
        if not self.allowed(): return self.respond({'error':'Local access only'},403)
        if self.path!='/api/jobs': return self.respond({'error':'Not found'},404)
        if not self.headers.get('Content-Type','').startswith('application/json'): return self.respond({'error':'JSON required'},415)
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: return self.respond({'error':'Invalid length'},400)
        if not 0<length<=MAX_BODY: return self.respond({'error':'Upload too large'},413)
        if not BUSY.acquire(blocking=False): return self.respond({'error':'Another conversion is running'},409)
        try:
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict): raise ValueError('JSON object required')
            return self.respond(run_job(payload),201)
        except (ValueError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
            return self.respond({'error':str(exc)[:200]},400)
        except Exception:
            return self.respond({'error':'Conversion failed; check your input and try again'},500)
        finally: BUSY.release()
    def do_DELETE(self):
        if not self.allowed(): return self.respond({'error':'Local access only'},403)
        match=re.fullmatch(r'/api/jobs/([0-9a-f]{32})',self.path)
        if not match: return self.respond({'error':'Not found'},404)
        if not BUSY.acquire(blocking=False): return self.respond({'error':'Conversion in progress'},409)
        try:
            folder=job_path(match[1])
            if not folder.exists(): return self.respond({'error':'Not found'},404)
            shutil.rmtree(folder)
            return self.respond({'deleted':True})
        finally: BUSY.release()


def main():
    (DATA/'jobs').mkdir(parents=True,exist_ok=True)
    print('ASCII QR Studio listening on port 8787',flush=True)
    ThreadingHTTPServer(('0.0.0.0',8787),Handler).serve_forever()

if __name__=='__main__': main()
