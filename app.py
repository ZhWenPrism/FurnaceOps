"""Local, read-only asset-viewer prototype. Python 3.10+, no third-party packages."""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
SNAPSHOT = '2026-10-11T10:00:00+08:00'
SOURCE = '合成样例，非企业现场数据'
STAGES = ('组装', '就位', '使用', '检查', '拆除')
STATIC = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/styles.css': ('styles.css', 'text/css')}


@contextmanager
def connect(path):
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    """Build a deterministic synthetic dataset; never overwrite an existing dataset."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, group_name TEXT NOT NULL,
                region TEXT NOT NULL, source_status TEXT NOT NULL, x INTEGER, y INTEGER,
                observed_at TEXT, value REAL, unit TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS measurements (
                asset_id TEXT NOT NULL REFERENCES assets(id), timestamp TEXT NOT NULL,
                value REAL, PRIMARY KEY(asset_id,timestamp));
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                timestamp TEXT NOT NULL, stage TEXT NOT NULL, title TEXT NOT NULL,
                result TEXT NOT NULL, note TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS record_lookup ON records(asset_id,stage,timestamp);
        ''')
        if db.execute('SELECT 1 FROM metadata WHERE key=?', ('seed_version',)).fetchone():
            return
        now = datetime.fromisoformat(SNAPSHOT)
        items = [
            ('P-01', '保护棚模块 01', '保护棚', '上层 A 区', '使用中', 120, 80, 2, 34.2),
            ('P-02', '保护棚模块 02', '保护棚', '上层 B 区', '待复核', 340, 80, 3, 35.1),
            ('P-03', '保护棚模块 03', '保护棚', '上层 C 区', '已就位', 560, 80, 35, 33.8),
            ('D-01', '吊盘模块 01', '吊盘', '下层 A 区', '使用中', 120, 250, 1, 32.4),
            ('D-02', '吊盘模块 02', '吊盘', '下层 B 区', '已就位', 340, 250, 2, 0.0),
            ('D-03', '吊盘模块 03', '吊盘', '下层 C 区', '未填报', 560, 250, None, None),
        ]
        for index, (aid, name, group, region, status, x, y, age, value) in enumerate(items):
            observed = (now - timedelta(minutes=age)).isoformat() if age is not None else None
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (aid, name, group, region, status, x, y, observed, value, '°C'))
            # P-03 ends at its old observation; missing samples are explicit SQL NULLs.
            end = datetime.fromisoformat(observed) if observed else now
            for j in range(24):
                ts = end - timedelta(minutes=5*(23-j))
                val = None if value is None or j in (7,8) else round(value+(j%5-2)*0.15, 2)
                if j == 23:
                    val = value
                db.execute('INSERT INTO measurements VALUES (?,?,?)', (aid, ts.isoformat(), val))
            for j, (stage, title, result) in enumerate([
                ('组装', '模块信息登记', '已记录'), ('检查', '连接部位检查记录', '已记录'),
                ('就位', '区域与构件对应确认', '已记录'), ('使用', '作业阶段信息更新', '已记录'),
                ('检查', '阶段复核记录', '待复核' if aid == 'P-02' else '已记录'),
            ]):
                ts = now - timedelta(minutes=120-j*20-index)
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?)',
                           (f'R-{aid}-{j+1:02d}', aid, ts.isoformat(), stage, title, result,
                            '用于验证构件关联与记录检索；不代表现场检查结论。'))
        db.executemany('INSERT INTO metadata VALUES (?,?)',
                       [('seed_version','1'), ('snapshot',SNAPSHOT), ('source',SOURCE)])


def quality(asset, as_of):
    if asset['value'] is None or asset['observed_at'] is None:
        return 'missing'
    age = (datetime.fromisoformat(as_of)-datetime.fromisoformat(asset['observed_at'])).total_seconds()
    if age < 0:
        return 'invalid'
    return 'stale' if age > 600 else 'valid'


def safe_csv(value):
    text = str(value) if value is not None else ''
    return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text


class BadRequest(Exception):
    pass


class Handler(BaseHTTPRequestHandler):
    server_version = 'AssetViewer/0.1'

    def __init__(self, *args, database, **kwargs):
        self.database = database
        super().__init__(*args, **kwargs)

    def log_message(self, *_):
        pass

    def send(self, data, status=200, content_type='application/json', extra=None):
        if isinstance(data, (dict,list)):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        elif isinstance(data,str):
            data = data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type+'; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        for k,v in (extra or {}).items():
            self.send_header(k,v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def error(self, message, status=400):
        self.send({'error':message}, status)

    def do_POST(self):
        self.error('Read-only prototype: write operations are disabled.',405)

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST

    def do_GET(self):
        try:
            parts = urlsplit(self.path)
            if len(parts.query)>2048:
                raise BadRequest('Query too long')
            q = parse_qs(parts.query, keep_blank_values=True, max_num_fields=10)
            for k,v in q.items():
                if len(v)!=1 or len(v[0])>128:
                    raise BadRequest('Invalid query parameter')
            q = {k:v[0] for k,v in q.items()}
            if parts.path in STATIC:
                name, mime = STATIC[parts.path]
                self.send((ROOT/'static'/name).read_bytes(),content_type=mime)
                return
            with connect(self.database) as db:
                meta = dict(db.execute('SELECT key,value FROM metadata').fetchall())
                assets = []
                for row in db.execute('SELECT * FROM assets ORDER BY id'):
                    a = dict(row)
                    a['quality'] = quality(a, meta['snapshot'])
                    a['metric'] = '示例温度'
                    assets.append(a)
                if parts.path == '/api/health':
                    self.send({'status':'ok','mode':'synthetic','version':'0.1.0'})
                elif parts.path == '/api/summary':
                    counts = {s:sum(a['quality']==s for a in assets) for s in ('valid','stale','missing','invalid')}
                    self.send({'mode':'synthetic','source':meta['source'],'snapshot':meta['snapshot'],
                               'total':len(assets),'quality_counts':counts,
                               'records':db.execute('SELECT COUNT(*) FROM records').fetchone()[0]})
                elif parts.path == '/api/assets':
                    group = q.get('group','')
                    if group not in ('','吊盘','保护棚'):
                        raise BadRequest('Unknown group')
                    term = q.get('q','').casefold()
                    found = [a for a in assets if (not group or a['group_name']==group)
                             and (not term or term in (a['id']+' '+a['name']).casefold())]
                    self.send({'items':found,'source':meta['source'],'snapshot':meta['snapshot']})
                elif re.fullmatch(r'/api/assets/[A-Z]-\d{2}(/series)?',parts.path):
                    aid = parts.path.split('/')[3]
                    a = next((x for x in assets if x['id']==aid),None)
                    if not a:
                        self.error('Asset not found',404)
                    elif parts.path.endswith('/series'):
                        rows = [dict(r) for r in db.execute('SELECT timestamp,value FROM measurements WHERE asset_id=? ORDER BY timestamp',(aid,))]
                        self.send({'asset_id':aid,'unit':a['unit'],'metric':a['metric'],'items':rows,'source':meta['source']})
                    else:
                        self.send({'asset':a,'source':meta['source'],'snapshot':meta['snapshot']})
                elif parts.path in ('/api/records','/api/records.csv'):
                    aid, stage = q.get('asset_id',''),q.get('stage','')
                    if aid and not any(x['id']==aid for x in assets):
                        raise BadRequest('Unknown asset_id')
                    if stage and stage not in STAGES:
                        raise BadRequest('Unknown stage')
                    conditions, params = [],[]
                    for key,val in [('asset_id',aid),('stage',stage)]:
                        if val:
                            conditions.append(key+'=?')
                            params.append(val)
                    where = ' WHERE '+' AND '.join(conditions) if conditions else ''
                    total = db.execute('SELECT COUNT(*) FROM records'+where,params).fetchone()[0]
                    limit,offset = int(q.get('limit',100)),int(q.get('offset',0))
                    if not 1<=limit<=200 or not 0<=offset<=100000:
                        raise BadRequest('Invalid pagination')
                    sql = 'SELECT * FROM records'+where+' ORDER BY timestamp DESC,id'
                    if parts.path.endswith('.csv'):
                        # Export the complete filtered result, independent of UI pagination.
                        rows = [dict(r) for r in db.execute(sql,params)]
                        out = io.StringIO(newline='')
                        writer = csv.writer(out)
                        writer.writerow(['记录编号','构件编号','时间','阶段','事项','来源结果','备注','数据来源'])
                        for row in rows:
                            writer.writerow([safe_csv(row[k]) for k in ('id','asset_id','timestamp','stage','title','result','note')]+[meta['source']])
                        self.send('\ufeff'+out.getvalue(),content_type='text/csv',extra={'Content-Disposition':'attachment; filename="asset-records-demo.csv"'})
                    else:
                        rows = [dict(r) for r in db.execute(sql+' LIMIT ? OFFSET ?',params+[limit,offset])]
                        self.send({'items':rows,'total':total,'limit':limit,'offset':offset,'source':meta['source']})
                else:
                    self.error('Not found',404)
        except (BadRequest,ValueError) as exc:
            self.error(str(exc))
        except Exception:
            # Do not expose database paths or stack traces in HTTP responses.
            self.error('Internal server error',500)


def create_server(path,port=0):
    initialize(path)
    return ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,database=Path(path)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--db',type=Path,default=ROOT/'runtime'/'demo.sqlite3')
    args = parser.parse_args()
    server = create_server(args.db,args.port)
    print(f'Asset viewer: http://127.0.0.1:{server.server_port}',flush=True)
    print('Synthetic data only. Read-only local prototype; not a production server.',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

