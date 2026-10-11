import csv
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import SOURCE, SNAPSHOT, connect, create_server, initialize, quality, safe_csv


class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.db=Path(cls.temp.name)/'test.sqlite3'
        cls.server=create_server(cls.db)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def raw(self,path,method='GET'):
        try:
            with urlopen(Request(self.base+path,method=method),timeout=3) as response:
                return response.status,response.read(),response.headers
        except HTTPError as err:
            return err.code,err.read(),err.headers

    def data(self,path):
        status,body,_=self.raw(path)
        self.assertEqual(status,200)
        return json.loads(body)

    def test_health(self):self.assertEqual(self.data('/api/health')['mode'],'synthetic')
    def test_summary(self):
        d=self.data('/api/summary');self.assertEqual((d['total'],d['records']),(6,30));self.assertEqual(d['quality_counts'],{'valid':4,'stale':1,'missing':1,'invalid':0})
    def test_provenance(self):self.assertEqual(self.data('/api/assets')['source'],SOURCE)
    def test_group_filter(self):self.assertEqual(len(self.data('/api/assets?group=%E5%90%8A%E7%9B%98')['items']),3)
    def test_search(self):self.assertEqual(self.data('/api/assets?q=d-01')['items'][0]['id'],'D-01')
    def test_empty_search(self):self.assertEqual(self.data('/api/assets?q=missing')['items'],[])
    def test_missing_asset(self):self.assertEqual(self.raw('/api/assets/X-99')[0],404)
    def test_zero_is_valid(self):
        a=self.data('/api/assets/D-02')['asset'];self.assertEqual(a['value'],0);self.assertEqual(a['quality'],'valid')
    def test_missing_is_null(self):
        a=self.data('/api/assets/D-03')['asset'];self.assertIsNone(a['value']);self.assertEqual(a['quality'],'missing')
    def test_stale(self):self.assertEqual(self.data('/api/assets/P-03')['asset']['quality'],'stale')
    def test_future_is_invalid(self):
        a={'value':1,'observed_at':(datetime.fromisoformat(SNAPSHOT)+timedelta(seconds=1)).isoformat()};self.assertEqual(quality(a,SNAPSHOT),'invalid')
    def test_series_gaps(self):
        d=self.data('/api/assets/D-01/series');self.assertEqual(len(d['items']),24);self.assertIsNone(d['items'][7]['value']);self.assertEqual(d['items'][-1]['value'],32.4)
    def test_missing_series(self):self.assertTrue(all(x['value'] is None for x in self.data('/api/assets/D-03/series')['items']))
    def test_filtered_records(self):
        d=self.data('/api/records?asset_id=P-02&stage=%E6%A3%80%E6%9F%A5');self.assertEqual(d['total'],2);self.assertTrue(all(r['asset_id']=='P-02' and r['stage']=='检查' for r in d['items']))
    def test_record_pagination(self):
        d=self.data('/api/records?limit=2&offset=2');self.assertEqual(len(d['items']),2);self.assertEqual(d['total'],30)
    def test_empty_stage(self):self.assertEqual(self.data('/api/records?stage=%E6%8B%86%E9%99%A4')['items'],[])
    def test_bad_queries(self):
        for path in ['/api/assets?group=no','/api/records?stage=no','/api/records?limit=0','/api/records?limit=201','/api/records?limit=x','/api/records?offset=-1','/api/records?asset_id=X-99','/api/assets?q=a&q=b']:
            with self.subTest(path=path):self.assertEqual(self.raw(path)[0],400)
    def test_csv_filter_and_bom(self):
        status,body,headers=self.raw('/api/records.csv?asset_id=D-01');self.assertEqual(status,200);self.assertTrue(body.startswith(b'\xef\xbb\xbf'));rows=list(csv.reader(io.StringIO(body.decode('utf-8-sig'))));self.assertEqual(len(rows),6);self.assertTrue(all(r[1]=='D-01' and r[-1]==SOURCE for r in rows[1:]));self.assertIn('attachment',headers['Content-Disposition'])
    def test_csv_complete_filtered_export(self):
        _,body,_=self.raw('/api/records.csv?asset_id=D-01&limit=1&offset=2');self.assertEqual(len(list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))),6)
    def test_csv_formula_escape(self):
        for value in ['=1+1',' +SUM(A1)','-5','@cmd']:
            self.assertTrue(safe_csv(value).startswith("'"))
    def test_sql_injection_rejected(self):self.assertEqual(self.raw('/api/records?asset_id=%27%20OR%201%3D1--')[0],400)
    def test_no_static_traversal(self):
        for path in ['/../app.py','/%2e%2e/app.py','/runtime/demo.sqlite3','/.git/config']:
            self.assertEqual(self.raw(path)[0],404)
    def test_writes_disabled(self):
        for method in ['POST','PUT','DELETE','PATCH']:self.assertEqual(self.raw('/api/assets',method)[0],405)
    def test_static_and_security_headers(self):
        for path in ['/','/app.js','/styles.css']:
            status,body,headers=self.raw(path);self.assertEqual(status,200);self.assertGreater(len(body),100);self.assertEqual(headers['X-Content-Type-Options'],'nosniff');self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
    def test_seed_idempotency(self):
        initialize(self.db)
        with connect(self.db) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],30)


if __name__=='__main__':unittest.main()

