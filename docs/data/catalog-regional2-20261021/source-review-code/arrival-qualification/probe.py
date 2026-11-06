"""Serial bounded GETs. Stops denied hosts; immutable original receipts; no retries."""
from pathlib import Path
import requests,datetime,json,hashlib,signal,time,sys,urllib.parse
ROOT=Path(__file__).resolve().parent
UA='RoadtripsAreFun-CatalogFollowup/1.0 (bounded public research)'
def get(ident,url):
 p=ROOT/'receipts.json';rows=json.loads(p.read_text()) if p.exists() else []
 assert len(rows)<12,'12GET ceiling'
 assert not any(x['url']==url for x in rows),'attempted URL; never retry'
 host=urllib.parse.urlparse(url).hostname.removeprefix('www.')
 assert not any(x.get('status') in (401,403,429) and urllib.parse.urlparse(x['url']).hostname.removeprefix('www.')==host for x in rows),'denied host'
 row={'id':ident,'url':url,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'GET','max_bytes':1048576};data=None
 def stop(*a):raise TimeoutError('35 second total ceiling')
 signal.signal(signal.SIGALRM,stop);signal.alarm(35)
 try:
  with requests.get(url,headers={'User-Agent':UA},timeout=(7,22),allow_redirects=False,stream=True) as resp:
   row.update(status=resp.status_code,final_url=resp.url,content_type=resp.headers.get('Content-Type'),location=resp.headers.get('Location'),content_length=resp.headers.get('Content-Length'),last_modified=resp.headers.get('Last-Modified'))
   if int(resp.headers.get('Content-Length') or 0)>1048576:raise ValueError('Content-Length exceeds1MiB; body not downloaded')
   parts=[];size=0
   for b in resp.iter_content(65536):
    size+=len(b)
    if size>1048576:raise ValueError('stream exceeded1MiB; stopped')
    parts.append(b)
   data=b''.join(parts);dest=ROOT/'raw'/(ident+'.body');dest.write_bytes(data);row.update(path=str(dest.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 except Exception as e:row['error']=type(e).__name__+': '+str(e)
 finally:signal.alarm(0)
 rows.append(row);p.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True);time.sleep(1.3)
if __name__=='__main__':get(sys.argv[1],sys.argv[2])
