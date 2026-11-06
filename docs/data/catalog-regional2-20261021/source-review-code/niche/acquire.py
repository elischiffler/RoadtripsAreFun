"""Bounded operator review: robots, prior blocks, immutable receipts, no retries."""
from pathlib import Path
import argparse,datetime,hashlib,json,signal,time,urllib.parse,urllib.robotparser
import requests
ROOT=Path(__file__).resolve().parent
UA='RoadtripsAreFun-CatalogFollowup/1.0 (bounded public research)'
MAX_TOTAL=12*1024*1024
MAX_PAGE=1024*1024
PAGES=[('Q15210824', 'https://www.clarksbears.com'), ('Q2071814', 'https://www.nps.gov/pevi/index.htm'), ('Q5411232', 'https://www.esnarailway.com/'), ('Q448450', 'https://www.alohatower.com/visit/index.html'), ('Q448450-hdot', 'https://hidot.hawaii.gov/blog/2026/10/12/aloha-tower-celebrates-centennial-with-anchored-in-aloha-community-events-oct-15-16/'), ('Q6878674', 'https://www.missionpointlighthouse.com/'), ('Q7886992', 'https://www.uniroyaltires.com/auto/community-involvement'), ('Q3308122', 'https://obcinc.org/currituck-beach-lighthouse/plan-your-visit/'), ('Q7404187', 'https://www.newsalem-nd.com/'), ('Q16983149', 'https://www.ocnrr.com'), ('Q97355534', 'https://www.millersofficefurniture.com/history'), ('Q30623769', 'https://www.visitoldmeadecounty.com/the-dalton-gang-hideout'), ('Q7371062', 'https://cityofpascagoula.com/452/Pascagoula-Museums'), ('Q7106394', 'https://transportationmuseum.org/train-rides'), ('Q5093786', 'https://www.chesterwv.org/')]
FOLLOWUP_PAGES=[('Q7404187-tourism','https://www.salemsue.com'),('Q2071814-conditions','https://www.nps.gov/pevi/planyourvisit/conditions.htm'),('Q3308122-visit','https://obcinc.org/currituck-beach-lighthouse/plan-your-visit/'),('Q5093786-teapot','https://www.chesterwv.org/world-s-largest-teapot'),('Q7106394-home','https://transportationmuseum.org/')]

def load():return json.loads((ROOT/'receipts.json').read_text()) if (ROOT/'receipts.json').exists() else []
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def host(url):return urllib.parse.urlparse(url).hostname.removeprefix('www.')
def prior_blocks():
 found=[]
 for path in [p for base in ['/workspace/catalog-pilot-600-20261021','/workspace/catalog-followup-20261021','/workspace/catalog-geodiverse-20261021'] for p in Path(base).glob('*/**/*receipts*.json')]:
  try:rows=json.loads(path.read_text())
  except (ValueError,OSError):continue
  if not isinstance(rows,list):continue
  for r in rows:
   if isinstance(r,dict) and r.get('status') in [401,403,429] and r.get('url'):
    found.append({'url':r['url'],'status':r['status'],'ledger':str(path),'checked_at':r.get('checked_at')})
 save('prior-blocks.json',found);return found
def required_wait(rows,url,now):
 """Minimum start-to-start delay from retained policy and receipts; no network."""
 recent=[r for r in rows if r.get('checked_at') and host(r['url'])==host(url)]
 if not recent:return 0.0
 intervals=[]
 for r in recent:
  if not r['id'].startswith('robots') or r.get('status')!=200 or not r.get('path'):continue
  rp=urllib.robotparser.RobotFileParser();rp.parse((ROOT/r['path']).read_text(errors='replace').splitlines())
  delay=rp.crawl_delay(UA) or rp.crawl_delay('*') or 0
  rate=rp.request_rate(UA) or rp.request_rate('*')
  if rate:delay=max(delay,rate.seconds/rate.requests)
  intervals.append(delay)
 interval=max(intervals,default=0)
 last=max(datetime.datetime.fromisoformat(r['checked_at']).timestamp() for r in recent)
 return max(0.0,last+interval-now)
def fetch(ident,url,limit=MAX_PAGE):
 rows=load();old=next((r for r in rows if r['id']==ident or r['url']==url),None)
 if old:
  assert old['url']==url
  data=(ROOT/old['path']).read_bytes() if old.get('path') else None
  if data is not None:assert hashlib.sha256(data).hexdigest()==old['sha256']
  return old,data
 if len(rows)>=60:raise ValueError('60 attempt ceiling')
 if sum(r.get('bytes',0) for r in rows)+limit>MAX_TOTAL:raise ValueError('aggregate8MiB evidence ceiling')
 wait=required_wait(rows,url,datetime.datetime.now(datetime.timezone.utc).timestamp())
 if wait>60:raise ValueError('Required source wait exceeds bounded 60-second policy; held')
 if wait:time.sleep(wait)
 r={'id':ident,'url':url,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'GET','max_bytes':limit};data=None
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('35second total request ceiling')));signal.alarm(35)
 try:
  with requests.get(url,headers={'User-Agent':UA},timeout=(7,22),stream=True,allow_redirects=False) as resp:
   r.update(status=resp.status_code,final_url=resp.url,content_type=resp.headers.get('Content-Type'),location=resp.headers.get('Location'),etag=resp.headers.get('ETag'),last_modified=resp.headers.get('Last-Modified'))
   parts=[];length=0
   for part in resp.iter_content(65536):
    length+=len(part)
    if length>limit:raise ValueError('body ceiling exceeded; response stopped')
    parts.append(part)
   data=b''.join(parts);path='raw/'+ident+'.body';(ROOT/path).write_bytes(data)
   r.update(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 except Exception as exc:r.update(error=type(exc).__name__+': '+str(exc));data=None
 finally:signal.alarm(0)
 rows.append(r);save('receipts.json',rows);print(ident,r.get('status'),r.get('bytes'),r.get('error',''),flush=True);time.sleep(1.3)
 return r,data
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--acquire',action='store_true');args=parser.parse_args()
 if not args.acquire:print('Offline default; no source requests.');return
 blocks=prior_blocks();stopped={host(r['url']) for r in blocks};robots={};decisions=[]
 def allow(url):
  origin=urllib.parse.urlparse(url).scheme+'://'+urllib.parse.urlparse(url).netloc
  if host(url) in stopped:return False,'Prior/current access-blocked host; not retried.'
  if origin not in robots:
   rid='robots-'+urllib.parse.urlparse(url).netloc.replace('.','-');r,b=fetch(rid,origin+'/robots.txt',128*1024)
   if r.get('status') in [301,302,303,307,308] and r.get('location'):
    target=urllib.parse.urljoin(origin+'/robots.txt',r['location'])
    if urllib.parse.urlparse(target).scheme=='https' and host(target)==host(url):
     r,b=fetch(rid+'-canonical',target,128*1024)
   if r.get('status') in [401,403,429]:stopped.add(host(url));robots[origin]=(None,False);return False,'Robots endpoint blocked; no operator request.'
   if r.get('status')==404:robots[origin]=(None,True)
   elif r.get('status')==200 and b is not None:
    rp=urllib.robotparser.RobotFileParser();rp.parse(b.decode('utf-8',errors='replace').splitlines());robots[origin]=(rp,True)
   else:robots[origin]=(None,False)
  rp,default=robots[origin]
  if rp:
   delay=rp.crawl_delay(UA) or rp.crawl_delay('*') or 0
   if delay>60:return False,'Robots crawl delay exceeds this bounded probe policy; held.'
   return rp.can_fetch(UA,url),'Robots rules evaluated.'
  return default,'No robots resource404.' if default else 'Robots unresolved; no operator request.'
 for qid,url in PAGES+FOLLOWUP_PAGES:
  decision={'qid':qid,'requested_url':url};current=url
  for hop in range(3):
   allowed,reason=allow(current);decision.setdefault('robots_checks',[]).append({'url':current,'allowed':allowed,'reason':reason})
   if not allowed:decision.update(outcome='held',reason=reason);break
   r,b=fetch('operator-'+qid+(('-redirect'+str(hop)) if hop else ''),current)
   if r.get('status') in [401,403,429]:stopped.add(host(current));decision.update(outcome='held',reason='Operator access/rate response; stopped without retry.',status=r.get('status'));break
   if r.get('status') in [301,302,303,307,308] and r.get('location'):
    current=urllib.parse.urljoin(current,r['location']);decision.setdefault('redirects',[]).append(current)
    if urllib.parse.urlparse(current).scheme!='https':decision.update(outcome='held',reason='Redirect is not HTTPS; no follow.');break
    continue
   decision.update(status=r.get('status'),receipt_id=r['id'],final_url=current,outcome='body_acquired_for_review' if r.get('status')==200 and b is not None else 'held',reason=r.get('error') or ('Page requires actual entity/access review.' if r.get('status')==200 else 'Unsuccessful operator response.'));break
  else:decision.update(outcome='held',reason='Redirect ceiling reached; no further requests.')
  decisions.append(decision);save('replay-operator-decisions.json' if (ROOT/'adapter-inputs.json').exists() else 'operator-decisions.json',decisions)
if __name__=='__main__':main()
