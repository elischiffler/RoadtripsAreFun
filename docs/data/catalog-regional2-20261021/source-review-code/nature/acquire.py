"""Bounded public, robots-aware operator review. No credentials, DB, AI or writes outside this directory."""
from pathlib import Path
from datetime import datetime,UTC
import urllib.request,urllib.error,urllib.parse,urllib.robotparser,json,hashlib,time
from timing_policy import wait_for
P=Path(__file__).parent;MAX_ATTEMPTS=65;MAX_BODY=1024*1024;UA='RoadtripsCatalogResearch/1.0';BLOCKED={'dothanbotanicalgardens.com','twpark.com','ncaquariums.com'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
OPENER=urllib.request.build_opener(NoRedirect)
def ledger():return json.loads((P/'attempts.json').read_text())if(P/'attempts.json').exists()else[]
def host(url):return urllib.parse.urlparse(url).netloc.lower().removeprefix('www.')
def raw_get(label,url,ceiling=MAX_BODY):
 old=ledger();hit=next((x for x in old if x['id']==label),None)
 if hit:return hit
 if len(old)>=MAX_ATTEMPTS:raise ValueError('65-attempt ceiling')
 if host(url)in BLOCKED or any(host(x['url'])==host(url)and x.get('status')in[401,403,429]for x in old):
  return dict(id=label,url=url,error='previous_denial_host_not_requested',not_requested=True)
 wait=wait_for(url,old,lambda r:(P/r['path']).read_text(errors='replace'),time.time())
 if wait>60: return dict(id=label,url=url,error='timing_wait_exceeds_turn_budget',not_requested=True)
 time.sleep(wait);r=dict(id=label,url=url,checked_at=datetime.now(UTC).isoformat());b=b''
 try:
  with OPENER.open(urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/plain;q=0.9,*/*;q=0.5'}),timeout=35)as z:
   b=z.read(ceiling+1);r.update(status=z.status,final_url=z.url,content_type=z.headers.get('Content-Type'))
   if len(b)>ceiling:b=b[:ceiling];r['error']='body_ceiling_incomplete'
 except urllib.error.HTTPError as e:
  b=e.read(min(4096,ceiling));r.update(status=e.code,error='HTTPError')
  if e.headers.get('Location'):r['location']=urllib.parse.urljoin(url,e.headers['Location'])
 except Exception as e:r.update(error=type(e).__name__,message=str(e))
 r['completed_at']=datetime.now(UTC).isoformat()
 path=P/'sources'/(label+'.body');path.parent.mkdir(exist_ok=True);path.write_bytes(b);r.update(path=str(path.relative_to(P)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest());(P/'attempts.json').write_text(json.dumps(old+[r],indent=2)+'\n');print(label,r.get('status'),len(b),r.get('error'),flush=True);return r

def get(label,url):
 if host(url)in BLOCKED:return dict(id=label,url=url,error='old_denial_or_robots_block_no_retry',not_requested=True)
 origin=urllib.parse.urlunparse(urllib.parse.urlparse(url)._replace(path='',params='',query='',fragment=''));key=hashlib.sha256(origin.encode()).hexdigest()[:12]
 rr=raw_get('robots-'+key,origin+'/robots.txt',30000)
 for hop in range(4):
  if rr.get('status')not in[301,302,303,307,308]:break
  if not rr.get('location'):return dict(id=label,url=url,error='robots_redirect_missing_location',not_requested=True)
  rr=raw_get('robots-'+key+'-hop'+str(hop),rr['location'],30000)
 else:return dict(id=label,url=url,error='robots_redirect_limit',not_requested=True)
 if rr.get('status') not in [200,301,302,303,307,308,404,410] or rr.get('error')in['URLError','TimeoutError','body_ceiling_incomplete']:return dict(id=label,url=url,error='robots_unavailable_or_denied',not_requested=True)
 if rr.get('status')==200:
  parser=urllib.robotparser.RobotFileParser();parser.parse((P/rr['path']).read_text(errors='replace').splitlines())
  if not parser.can_fetch(UA,url):return dict(id=label,url=url,error='robots_disallow',not_requested=True)
 rec=raw_get(label,url)
 if rec.get('status')in[301,302,303,307,308]and rec.get('location'):
  return get(label+'-redirect',rec['location'])
 return rec

TARGETS=[
('blue-spring','https://www.bluespringheritage.com/'),
('belle-conservatory','https://www.michigan.gov/recsearch/parks/belleisle'),
('chippewa','https://www.chippewanaturecenter.org/'),
('dow','https://dowgardens.org/'),
('formar','https://geneseecountyparks.org/for-mar-nature-preserve-arboretum-2/'),
('hector','https://www.lincolnparkpublicschools.com/web/index.php?page=home&iduser=326'),
('mcmath','https://www.mcmathhulbert.org/'),
('greensboro','https://www.greensboroscience.org/visit/'),
('life-science','https://www.lifeandscience.org/plan-your-visit/'),
('arboretum','https://www.ncarboretum.org/plan-a-visit/'),
('cypress','https://cypressgardens.berkeleycountysc.gov/'),
('magnolia','https://www.magnoliaplantation.com/'),
('moore','https://moorefarmsbg.org/'),
('cheekwood','https://cheekwood.org/plan-your-visit/'),
('miller','https://www.millergarden.org/'),
('longhorn','https://tpwd.texas.gov/state-parks/longhorn-cavern'),
]
if __name__=='__main__':
 result=[]
 for label,url in TARGETS:
  result.append(dict(key=label,result=get('nature-'+label,url)))
  (P/'probe-results.json').write_text(json.dumps(result,indent=2)+'\n')
