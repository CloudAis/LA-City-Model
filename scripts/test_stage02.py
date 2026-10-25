"""Local artificial transport fixtures, separate from actual Census data acceptance."""
import http.server
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage02_io import Client, arcgis_fetch, write_json
from stage02_clean import length_m


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.calls=[];owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                owner.calls.append((self.path,self.headers.get('Range')))
                if self.path=='/retry' and sum(x[0]=='/retry' for x in owner.calls)==1:
                    self.send_response(503);self.end_headers();return
                data=b'0123456789'
                offset=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0])
                self.send_response(206 if offset else 200);self.send_header('ETag','"fixture-v1"')
                self.send_header('Content-Length',str(len(data)-offset))
                if offset:self.send_header('Content-Range',f'bytes {offset}-9/10')
                self.end_headers();self.wfile.write(data[offset:])
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.client=Client(self.root,{'request':{'retries':2,'retry_statuses':[503],
            'timeout_seconds':5,'max_json_mib':1,'disk_headroom_gib':0}})
    def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def test_cache_and_hash(self):
        p=self.client.get(self.url+'/file','a.bin');n=len(self.calls)
        self.client.get(self.url+'/file','a.bin');self.assertEqual(len(self.calls),n)
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.client.get(self.url+'/file','a.bin')
    def test_resume_range(self):
        (self.root/'a.bin.part').write_bytes(b'01234')
        write_json(self.root/'a.bin.part.json',{'url':self.url+'/file','validator':'"fixture-v1"'})
        p=self.client.get(self.url+'/file','a.bin')
        self.assertEqual(p.read_bytes(),b'0123456789');self.assertEqual(self.calls[0][1],'bytes=5-')
    def test_size_limit(self):
        with self.assertRaises(ValueError):self.client.get(self.url+'/file','a.bin',limit=5)
    def test_retry_transient(self):
        self.client.get(self.url+'/retry','a.bin');self.assertEqual(len(self.calls),2)
    def test_height_units_and_ambiguity(self):
        self.assertEqual(length_m('12'),None);self.assertEqual(length_m('12',numeric_unit='m'),12)
        self.assertAlmostEqual(length_m('10 ft'),3.048);self.assertAlmostEqual(length_m("5'6\""),1.6764)
        self.assertEqual(length_m('12;14'),None);self.assertAlmostEqual(length_m('10 us-ft'),12000/3937)
    def test_arcgis_id_paging_and_recursive_limits(self):
        class Fake:
            root=self.root
            def json(self,url,path,params):
                if not url.endswith('/query'):return {'objectIdField':'OID','maxRecordCount':3}
                if params.get('returnCountOnly'):return {'count':5}
                if params.get('returnIdsOnly'):return {'objectIds':[5,1,3,2,4]}
                ids=list(map(int,params['objectIds'].split(',')))
                return {'exceededTransferLimit':len(ids)>1,'features':[{'attributes':{'OID':i}} for i in ids]}
        _,values,e=arcgis_fetch(Fake(),'http://fixture/layer','pages',page_size=3)
        self.assertEqual(len(values),5);self.assertTrue(e['id_set_equal'])
    def test_arcgis_missing_ids_fails(self):
        class Fake:
            root=self.root
            def json(self,url,path,params):
                if not url.endswith('/query'):return {'objectIdField':'OID','maxRecordCount':3}
                if params.get('returnCountOnly'):return {'count':2}
                return {'objectIds':[1]}
        with self.assertRaises(ValueError):arcgis_fetch(Fake(),'http://fixture/layer','pages')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    for n in ['PROJECT_SPEC.md','STATUS.md']:(root/n).read_text()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    write_json(root/'work/reports/stage02/transport_tests.json',{'fixture_type':'artificial_local_http_not_city_observations',
        'executed':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'status':'passed' if result.wasSuccessful() else 'failed'})
    raise SystemExit(0 if result.wasSuccessful() else 1)
