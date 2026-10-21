"""Bounded, read-only primary-operator acquisition for the exact first25 queue IDs.
Default offline. No accounts, keys, paid services, AI, databases or host bypasses.
"""
from pathlib import Path
from urllib.parse import urlparse,urljoin
from urllib.robotparser import RobotFileParser
from datetime import datetime,UTC
import json,hashlib,time,signal,argparse,requests
ROOT=Path(__file__).resolve().parent
UA='RoadtripsAreFun-CatalogReview/1.0 (bounded public source research)'
MAX_RAW=10*1024*1024
HOST_DELAYS={}
HOST_LAST={}
REQUESTS=[('Q4769571', 'https://library.brown.edu/about/amb/'), ('Q2650982', 'https://www.newportmansions.org/mansions-and-gardens/marble-house/'), ('Q18154824', 'https://www.museepata.org/'), ('Q6974447', 'https://www.americanillustration.org/'), ('Q2166814', 'https://www.newportmansions.org/mansions-and-gardens/rosecliff/'), ('Q1786400', 'https://www.newportmansions.org/mansions-and-gardens/the-breakers/'), ('Q7974817', 'https://www.historicnewengland.org/property/watson-farm/'), ('Q119585283', 'https://www.gloucestercountynj.gov/671/Red-Bank-Battlefield'), ('Q4554796', 'https://louisianastatemuseum.org/museum/1850-house'), ('Q931081', 'https://www.themuseum.org/'), ('Q49519614', 'https://audubonnatureinstitute.org/nature-center'), ('Q4839767', 'https://www.backstreetmuseum.org/'), ('Q134581303', 'https://jamnola.com/'), ('Q3485438', 'https://www.lastateparks.com/historic-sites/longfellow-evangeline-state-historic-site'), ('Q6689220', 'https://www.louisianahistorymuseum.org/'), ('Q6689293', 'https://louisianastatemuseum.org/'), ('Q1573286', 'https://louisianastatemuseum.org/museum/madame-johns-legacy'), ('Q30591923', 'https://liberalarts.tulane.edu/mari'), ('Q6033435', 'https://www.voodoomuseum.com/'), ('Q2063082', 'https://www.noma.org/'), ('Q16974720', 'https://newcombartmuseum.tulane.edu/')]
def save(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def fetch(id,url,max_bytes=1024*1024):
 receipts=json.loads((ROOT/'receipts.json').read_text())if(ROOT/'receipts.json').exists()else[]
 old=next((x for x in receipts if x['id']==id),None)
 if old is None:old=next((x for x in receipts if x['url']==url),None)
 if old:
  if old['url']!=url:raise ValueError('Immutable receipt ID reused for newURL')
  b=(ROOT/old['path']).read_bytes()if old.get('path')else None
  if b is not None:assert hashlib.sha256(b).hexdigest()==old['sha256']
  return old,b
 if len(receipts)>=80:raise ValueError('80 total request ceiling')
 if sum(p.stat().st_size for p in(ROOT/'raw').glob('*'))>MAX_RAW-max_bytes:raise ValueError('10MiB raw acquisition ceiling')
 host=urlparse(url).hostname;delay=HOST_DELAYS.get(host,1.1)
 previous=max([datetime.fromisoformat(e['checked_at']).timestamp()for e in receipts if urlparse(e.get('url','')).hostname==host]or[0])
 wait=max(HOST_LAST.get(host,0)+delay-time.monotonic(),previous+delay-datetime.now(UTC).timestamp(),0)
 if wait:time.sleep(wait)
 d={'id':id,'url':url,'checked_at':datetime.now(UTC).isoformat(),'method':'GET','max_response_bytes':max_bytes};b=None
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in()).throw(TimeoutError('35second wallclock cap')));signal.alarm(35)
 try:
  with requests.get(url,stream=True,allow_redirects=False,timeout=(7,25),headers={'User-Agent':UA})as r:
   d.update(status=r.status_code,final_url=r.url,location=r.headers.get('Location'),content_type=r.headers.get('Content-Type'),etag=r.headers.get('ETag'),last_modified=r.headers.get('Last-Modified'));b=b''
   for chunk in r.iter_content(65536):
    if len(b)+len(chunk)>max_bytes:raise ValueError('Response byte ceiling; stopped')
    b+=chunk
   target=ROOT/'raw'/(id+'.body');target.write_bytes(b);d.update(path=str(target.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
 except Exception as e:d['error']=str(e);b=None
 finally:signal.alarm(0);HOST_LAST[host]=time.monotonic()
 receipts.append(d);save(ROOT/'receipts.json',receipts);print(id,d.get('status'),d.get('bytes'),d.get('error',''),flush=True);time.sleep(1.1);return d,b
ROBOTS={};BLOCKED={'www.siouxcityartcenter.org', 'www.emmett-till.org', 'www.wam.org', 'www.audubon.org', 'www.newhavenmuseum.org', 'discovermgp.org', 'www.thewadsworth.org', 'florencegriswoldmuseum.org', 'bentoftheriver.audubon.org', 'jamestownhistoricalsociety.org', 'www.choate.edu', 'wam.org', 'delmnh.org', 'www.usj.edu', 'www.newporthistoricalsociety.org', 'www.coggeshallfarm.org', 'www.nianticchildrensmuseum.org', 'www.discoverymuseum.org', 'www.mattatuckmuseum.org', 'grammymuseumms.org'}
def robots_for(url):
 u=urlparse(url);origin=f'{u.scheme}://{u.netloc}'
 if origin in ROBOTS:return ROBOTS[origin]
 target=origin+'/robots.txt';r=None;b=None
 for i in range(4):
  host=urlparse(target).hostname
  if host in BLOCKED:ROBOTS[origin]=(None,False,None);return ROBOTS[origin]
  ident='robots-'+hashlib.sha256(target.encode()).hexdigest()[:16];r,b=fetch(ident,target,128*1024)
  if r.get('status')in[401,403,429]:BLOCKED.add(host);break
  if r.get('status')in[301,302,303,307,308]and r.get('location'):
   target=urljoin(target,r['location']);continue
  break
 if r and r.get('status')==404:ROBOTS[origin]=(None,True,r['id'])
 elif r and r.get('status')==200 and b is not None and b.lstrip()[:30].lower().find(b'<html')<0 and b.lstrip()[:30].lower().find(b'<!doctype')<0:
  rp=RobotFileParser();rp.parse(b.decode(errors='replace').splitlines())
  delay=rp.crawl_delay(UA)or 1.1;rate=rp.request_rate(UA)
  if rate and rate.requests:delay=max(delay,rate.seconds/rate.requests)
  HOST_DELAYS[u.hostname]=max(1.1,delay);ROBOTS[origin]=(rp,True,r['id'])
 else:ROBOTS[origin]=(None,False,r['id']if r else None)
 return ROBOTS[origin]
def acquire_one(qid,url,label='operator'):
 decisions=[];current=url
 if qid=='Q5098184' and 'childrensmuseumsect.org' in url:return {'pilot_id':'culture:wd:'+qid,'native_id':qid,'requested_url':url,'decisions':[{'hold':'old_operator_domain_redirects_to_unrelated_motorcycle_and_restaurant_domains; no visitor proof'}]}
 for i in range(4):
  u=urlparse(current)
  if u.scheme not in['https','http']or not u.hostname or u.username:decisions.append({'hold':'nonpublic_or_invalid_redirect'});break
  if u.hostname in BLOCKED:decisions.append({'hold':'prior_denied_host_not_retried','url':current});break
  rp,okay,robotid=robots_for(current)
  allowed=okay and(rp is None or rp.can_fetch(UA,current))
  if not allowed:decisions.append({'hold':'robots_disallowed_or_unresolved','url':current,'robots_receipt':robotid});break
  r,b=fetch(f'{label}-{qid}-{i}',current);decisions.append({'receipt_id':r['id'],'url':current,'status':r.get('status'),'error':r.get('error')})
  if r.get('status')in[401,403,429]:BLOCKED.add(u.hostname);break
  if r.get('status')in[301,302,303,307,308]and r.get('location'):
   current=urljoin(current,r['location']);continue
  if r.get('status')==200 and b is not None:
   from lxml import html
   try:
    tree=html.fromstring(b)
    for e in tree.xpath('//script|//style|//noscript'):e.drop_tree()
    (ROOT/'text'/(r['id']+'.txt')).write_text(' '.join(tree.text_content().split())+'\n')
   except Exception:pass
  break
 return {'pilot_id':'culture:wd:'+qid,'native_id':qid,'requested_url':url,'decisions':decisions}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--acquire',action='store_true');args=parser.parse_args()
 if not args.acquire:print('Offline default. --acquire opts into exact public GET list.');raise SystemExit
 out=[]
 for q,url in REQUESTS:
  try:out.append(acquire_one(q,url))
  except Exception as e:out.append({'pilot_id':'culture:wd:'+q,'requested_url':url,'decisions':[{'hold':'bounded_acquisition_failure','error':str(e)}]})
  save(ROOT/'acquisition-decisions.json',out)
