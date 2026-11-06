from pathlib import Path
import json,requests,datetime,signal
p=Path(__file__).resolve().parent;out=[]
urls=[('tybee-brochure','https://www.tybeelighthouse.org/_files/ugd/f985d7_15fcfed44194459c99d3a373e4ec0be3.pdf'),('gratiot-directions','https://www.stclaircounty.org/Uploads/ParksAndRecreation/forms/FGLS%20map%20inset.pdf'),('gratiot-brochure','https://www.stclaircounty.org/Uploads/ParksAndRecreation/forms/Brochures/FGLS%20Brochure%202025%20NEW%20WEB.pdf')]
for ident,url in urls:
 x={'id':ident+'-size','url':url,'method':'HEAD','checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()};signal.signal(signal.SIGALRM,lambda *_:(_ for _ in()).throw(TimeoutError('35s total ceiling')));signal.alarm(35)
 try:
  r=requests.head(url,headers={'User-Agent':'RoadtripsAreFun-CatalogFollowup/1.0 (bounded public research)'},timeout=(7,22),allow_redirects=False);x.update(status=r.status_code,content_length=r.headers.get('Content-Length'),content_type=r.headers.get('Content-Type'),last_modified=r.headers.get('Last-Modified'),location=r.headers.get('Location'))
 except Exception as e:x['error']=type(e).__name__+': '+str(e)
 finally:signal.alarm(0)
 out.append(x);(p/'size-receipts.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(x),flush=True)
 if x.get('status') in (401,403,429):break
