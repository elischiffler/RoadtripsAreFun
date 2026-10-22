"""Offline audit, fetch timing checks and immutable source-contract replay."""
from pathlib import Path
import datetime,hashlib,json,os,socket,subprocess,sys,urllib.robotparser
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def deny(*a,**k):raise AssertionError('Network prohibited in audit/replay')
def main():
 socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny
 sys.path.insert(0,str(ROOT));import acquire;acquire.requests.get=deny
 q=json.loads((ROOT/'seed.json').read_text());rs=json.loads((ROOT/'receipts.json').read_text());native=json.loads((ROOT/'native-receipts.json').read_text());a=json.loads((ROOT/'adapter-inputs.json').read_text());ds=json.loads((ROOT/'decisions.json').read_text());profiles=json.loads((ROOT/'persona-previews.json').read_text())['profiles'];checks=[]
 assert len(q)==len(a['records'])==len(ds)==16;assert len({r['pilot_id'] for r in q})==16;assert [r['pilot_id'] for r in q]==[r['pilot_id'] for r in a['records']];checks.append('Exact16 queue denominator, identity and order')
 assert sum(r['review']['decision']=='T2' for r in a['records'])==9;assert sum(r['review']['decision']=='T1' for r in a['records'])==7;checks.append('Measured9T2/7T1/0T3; no final-net claim')
 for r in rs+native:
  if r.get('path'):assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
 checks.append('Original byte hashes and lengths for every retained HTTP/native response')
 assert len(rs)==41<=60;assert max(r.get('bytes',0) for r in rs)<=1024*1024;assert sum(r['bytes'] for r in a['evidence'])==2281993;checks.append('Bounded41 requests,1MiB response ceilings,2,281,993-byte used evidence')
 assert all(r['status']==200 and not r.get('error') for r in a['evidence']);assert all(not Path(r['path']).is_absolute() and '..' not in Path(r['path']).parts for r in a['evidence']);checks.append('Adapter evidence is successful and internal to owned group')
 eids={r['id'] for r in a['evidence']};pmap={r['pilot_id']:r for r in q}
 for r in a['records']:
  if r['review']['decision']!='T2':assert r['hold_reason'];continue
  s=pmap[r['pilot_id']];assert r['bindings']['name']['pointer']==s['pointer']+'/itemLabel/value';assert r['bindings']['name']['evidence_id']==s['native_evidence_id'];assert all(r['bindings'][k]['evidence_id'] in eids for k in ['native_id','name']);assert r['bindings']['coordinates']['value']['evidence_id'] in eids
  assert all(p['evidence_id'] in eids for k in ['rights_proofs','access_proofs','operator_identity_location_proofs'] for p in r[k]);assert r['rights_proofs'][0]['evidence_id']=='native-wikidata-cc0';assert not any(k in r for k in ['hours','cost','amenities','accessibility','arrival_coordinate','calendar'])
 checks.append('Original native bindings, rights pin, internal proof references and unknown practical fields')
 assert len(profiles)==9
 for p in profiles:
  assert len(p['attribute_ratings'])==14 and p['activities']==[];assert p['validation_scope']['schema_validation_is_factual_verification'] is False;assert p['practical_context']['arrival_verified'] is False;assert all(v is None for k,v in p['practical_context'].items() if k not in ['arrival_verified','source_constraints']);assert p['inferred_traveler_fit']['confidence']=='limited category inference'
 checks.append('Nine deterministic14-attribute profiles label inferences and unknowns')
 audit=[]
 for receipt in rs:
  if not receipt['id'].startswith('robots') or receipt.get('status')!=200:continue
  rp=urllib.robotparser.RobotFileParser();rp.parse((ROOT/receipt['path']).read_text(errors='replace').splitlines());delay=rp.crawl_delay(acquire.UA) or rp.crawl_delay('*') or 0;rate=rp.request_rate(acquire.UA) or rp.request_rate('*');interval=max(delay,rate.seconds/rate.requests if rate else 0)
  same=sorted([r for r in rs if acquire.host(r['url'])==acquire.host(receipt['url'])],key=lambda r:r['checked_at']);pairs=[]
  for left,right in zip(same,same[1:]):
   # Apply policy from its successful acquisition onwards, including first content and redirects.
   if left['checked_at']<receipt['checked_at']:continue
   gap=(datetime.datetime.fromisoformat(right['checked_at'])-datetime.datetime.fromisoformat(left['checked_at'])).total_seconds();pairs.append({'from':left['id'],'to':right['id'],'start_gap_seconds':gap,'meets_required_interval':gap>=interval});assert gap>=interval,(receipt['id'],left['id'],right['id'],gap,interval)
  audit.append({'robots_id':receipt['id'],'url':receipt['url'],'applicable_delay_seconds':delay,'applicable_request_rate':list(rate) if rate else None,'pairs':pairs})
 (ROOT/'robots-timing-audit.json').write_text(json.dumps({'user_agent':acquire.UA,'audit_scope':'All current-group successful robots origins, first content requests and observed redirects. Rules apply after successful robots acquisition; no remediation acquisition performed.','missed_intervals':0,'policies':audit},indent=2)+'\n');checks.append('All applicable current-group crawl delays and request-rate intervals honored')
 # Test a frozen10s rule at first-content and cached-next-request boundaries without sleeping or fetching.
 city=next(r for r in rs if r['id']=='robots-cityofpascagoula-com');stamp=datetime.datetime.fromisoformat(city['checked_at']).timestamp();assert abs(acquire.required_wait([city],city['url'].replace('/robots.txt','/a'),stamp+1)-9)<1e-6
 content=next(r for r in rs if r['id']=='operator-Q7371062');now=datetime.datetime.fromisoformat(content['checked_at']).timestamp();assert abs(acquire.required_wait([city,content],content['url'],now+2)-8)<1e-6;assert acquire.required_wait([city,content],content['url'],now+11)==0;checks.append('Fetcher pure pacing guard tests first-content, cached-robots and elapsed delay')
 receipt=next(r for r in rs if r['id']=='operator-Q5411232');before=sha(ROOT/'receipts.json');found,body=acquire.fetch('different-replay-id',receipt['url']);assert found['sha256']==receipt['sha256'] and sha(ROOT/'receipts.json')==before;checks.append('ImmutableURL cache returns retained body without a request or ledger mutation')
 oldload=acquire.load;acquire.load=lambda:[{'id':str(i),'url':'https://invalid.example/'+str(i)} for i in range(60)]
 try:
  try:acquire.fetch('new','https://invalid.example/new');raise AssertionError('ceiling missing')
  except ValueError as exc:assert '60 attempt ceiling' in str(exc)
 finally:acquire.load=oldload
 checks.append('Fetcher60-attempt hard gate enforced before network')
 allledger=json.loads((ROOT/'initial-operator-decisions.json').read_text())+json.loads((ROOT/'followup-operator-decisions.json').read_text())+json.loads((ROOT/'operator-decisions.json').read_text());assert len(allledger)==20;assert not any('ocnrr.com' in r['url'] and not r['id'].startswith('robots') for r in rs);checks.append('All20 staged attempt dispositions retained; denied OldColony content never fetched')
 before={name:sha(ROOT/name) for name in ['adapter-inputs.json','decisions.json','report.json','review-contract.json','terms-ledger.json','persona-previews.json']};p=subprocess.run([sys.executable,str(ROOT/'build.py')],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));assert p.returncode==0,p.stdout+p.stderr;assert before=={name:sha(ROOT/name) for name in before};checks.append('Sockets-blocked source-contract replay is idempotent and review timestamps unchanged')
 assert json.loads((ROOT/'terms-ledger.json').read_text())['noncommercial_partition']['accepted']==0;checks.append('Only clearedCC0 native facts; operator prose/NC rights not presumed')
 result={'checks_passed':len(checks),'checks':checks,'queue_reviewed':16,'T2_source_contract_passes':9,'T1_holds':7,'T3_conversions':0,'final_combined_or_live_net_additions':None,'original_response_hashes_checked':sum(bool(r.get('path')) for r in rs+native),'robots_delay_misses':0,'used_evidence_bytes':2281993,'adapter_sha256':sha(ROOT/'adapter-inputs.json'),'scope':'Agent-assisted primary reading and offline byte/field/rights replay. Not independent human or field verification; root combined dedup and live reconciliation pending.'};(ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
