#!/usr/bin/env python3
"""Offline viewer server: built UI, local GLBs/decoders/textures, bounded gzip cache."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlsplit
import argparse,collections,gzip,hashlib,json,mimetypes,threading,time

ROOT=Path(__file__).resolve().parents[1]
CACHE=collections.OrderedDict();LOCK=threading.Lock();CACHE_LIMIT=16*1024**2
class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def do_GET(self):
        route=unquote(urlsplit(self.path).path)
        if route=='/health':
            body=json.dumps({'status':'running','stage':9,'local_resources':True}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if route.startswith('/resources/'):
            base=ROOT/'outputs/stage09/resources';path=base/route[len('/resources/'):]
        else:
            base=ROOT/'viewer/dist';path=base/(route.lstrip('/') or 'index.html')
        path=path.resolve();base=base.resolve()
        if not path.is_relative_to(base) or not path.is_file():self.send_error(404,'Local resource not found');return
        content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        is_gzip=path.suffix=='.gz'
        if is_gzip:content_type='application/json'
        key=(str(path),path.stat().st_mtime_ns)
        use_gzip=not is_gzip and 'gzip' in self.headers.get('Accept-Encoding','') and path.suffix in ('.glb','.json','.js','.css','.html') and path.stat().st_size>1024
        with LOCK:body=CACHE.get(key) if use_gzip else None
        if body is None:
            body=path.read_bytes()
            if use_gzip:
                body=gzip.compress(body,compresslevel=4,mtime=0)
                if len(body)<CACHE_LIMIT//4:
                    with LOCK:
                        CACHE[key]=body;CACHE.move_to_end(key)
                        while sum(map(len,CACHE.values()))>CACHE_LIMIT:CACHE.popitem(last=False)
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        immutable=path.suffix=='.png' and ('textures' in path.parts or 'textures-low' in path.parts)
        self.send_header('Cache-Control','public, max-age=31536000, immutable' if immutable else 'no-cache');self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        if is_gzip or use_gzip:self.send_header('Content-Encoding','gzip');self.send_header('Vary','Accept-Encoding')
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def log_message(self,format,*args):
        if args and str(args[1] if len(args)>1 else '') not in ('200','304'):super().log_message(format,*args)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8090);args=parser.parse_args()
    if not (ROOT/'viewer/dist/index.html').is_file() or not (ROOT/'outputs/stage09/resources/manifest.json').is_file():raise SystemExit('Missing actual viewer build or exported project resources')
    server=ThreadingHTTPServer((args.host,args.port),Handler);server.daemon_threads=True
    print(f'LA_LOCAL_VIEWER http://{args.host}:{args.port}  (Ctrl+C to stop)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
