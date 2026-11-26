import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from PIL import Image, ImageDraw
from http.server import ThreadingHTTPServer
import server

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(server,'DATA',Path(self.tmp.name));self.patch.start()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}'
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.patch.stop();self.tmp.cleanup()
    def request(self,path,data=None,method=None,headers=None):
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers or {'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as res:return res.status,res.read()
        except urllib.error.HTTPError as e:
            with e:return e.code,e.read()
    def test_local_routes_and_input_rejection(self):
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/api/health')[0],200)
        self.assertEqual(self.request('/api/jobs')[1],b'[]')
        self.assertEqual(self.request('/api/jobs',{},headers={'Content-Type':'application/json','Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/jobs',{'url':'file:///a'})[0],400)
        self.assertEqual(self.request('/api/jobs',{'url':'https://example.com/','image':'bad'})[0],400)
        self.assertEqual(self.request('/files/'+ 'a'*32 +'/../../VERSION')[0],404)
    def test_job_roundtrip_download_reuse_delete(self):
        image=Image.new('RGB',(160,160),'white');d=ImageDraw.Draw(image);d.ellipse((20,20,140,140),fill='navy')
        data=io.BytesIO();image.save(data,format='PNG')
        payload={'url':'https://example.com/','image':base64.b64encode(data.getvalue()).decode(),'columns':32,'min_version':5}
        code,body=self.request('/api/jobs',payload);self.assertEqual(code,201,body)
        job=json.loads(body);self.assertEqual(job['status'],'ready');self.assertEqual(job['checks'],14)
        self.assertEqual(self.request('/files/'+job['id']+'/result/selected-color.png')[0],200)
        code,zipdata=self.request('/api/jobs/'+job['id']+'/download');self.assertEqual(code,200);self.assertTrue(zipdata.startswith(b'PK'))
        payload.pop('image');payload['reuse']=job['id']
        code,body=self.request('/api/jobs',payload);self.assertEqual(code,201,body)
        self.assertEqual(self.request('/api/jobs/'+job['id'],method='DELETE')[0],200)
        self.assertEqual(self.request('/files/'+job['id']+'/input.png')[0],404)
    def test_failed_validation_is_not_downloadable(self):
        identifier='a'*32;p=server.DATA/'jobs'/identifier;p.mkdir(parents=True)
        (p/'job.json').write_text(json.dumps({'status':'failed'}))
        self.assertEqual(self.request('/api/jobs/'+identifier+'/download')[0],409)

if __name__=='__main__':unittest.main()
