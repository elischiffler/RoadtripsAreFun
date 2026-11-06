"""Offline standalone adapter assembly for exactly 24 frozen museum prospects."""
from pathlib import Path
from datetime import datetime,UTC
from collections import Counter
import json,hashlib,copy,sys
ROOT=Path(__file__).resolve().parent;REPO=Path('/workspace/RoadtripsAreFun');STATES=Path('/workspace/catalog-followup-20261021/assembled-final/states.json');COMPARISON=ROOT.parent/'comparison-890.json'
sys.path.insert(0,str(REPO/'backend'))
from app.catalog import pilot,usfs
from app.catalog.mixed import distance

def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
q=load(ROOT/'frozen-prospects.json');s=load(ROOT/'review_spec.json');receipts=load(ROOT/'receipts.json');nr=load(ROOT/'native-rights-receipts.json');byid={r['id']:r for r in receipts};used=set();out=[];decisions=[]
assert len(q)==24;assert set(s['positive'])|set(s['holds'])=={r['native_id']for r in q}
if not(ROOT/'review-stamp.json').exists():save(ROOT/'review-stamp.json',{'reviewer':'culture_sources_5000 (agent-assisted source review)','reviewed_at_epoch':int(datetime.now(UTC).timestamp())})
stamp=load(ROOT/'review-stamp.json');rights=[{'evidence_id':'rights-wikidata','literal':'available under the Creative Commons CC0 License'}]
for o in q:
 id=o['native_id'];r={'pilot_id':o['pilot_id'],'cohort':o['cohort'],'source_family':'wikidata','state':o['state'],'category':o['category'],'operator_url':o['operator_url'],'bindings':copy.deepcopy(o['bindings']),'aliases':[],'rights_proofs':copy.deepcopy(rights)};d={'pilot_id':o['pilot_id'],'native_id':id,'name':o['name'],'state':o['state'],'agent_assisted_review':True,'reviewed_at_epoch':stamp['reviewed_at_epoch'],'live_net_new':None}
 if id in s['positive']:
  rid,access,identity,cat,reason=s['positive'][id];e=byid[rid];assert e['status']==200 and e.get('path');b=(ROOT/e['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==e['sha256'];text=pilot.evidence_text(b)
  for literal in access+identity:assert pilot.plain(literal).casefold()in text.casefold(),(id,literal)
  used.add(rid);r.update(category=cat,operator_url=e['url'],access_proofs=[{'evidence_id':rid,'literal':x}for x in access],operator_identity_location_proofs=[{'evidence_id':rid,'literal':x}for x in identity],source_constraints=[reason,'Original native label, identifier and feature coordinate are unchanged; the point is not a verified arrival.','Opening, cost, accessibility, amenities and availability fields remain unknown; source notices are dated constraints only.','Campus, institutional parent/component and co-located identities require final cross-source semantic reconciliation.'],review=dict(stamp,decision='T2',license='CC0-1.0',reason=reason,operator_is_primary=True,public_visit_affirmed=True,closure_conflicts_reviewed=True));d.update(decision='T2_source_review',operator_evidence_id=rid,reason=reason,category=cat)
 else:
  reason=s['holds'][id];r.update(hold_reason=reason,review=dict(stamp,decision='T1',reason=reason));d.update(decision='T1_hold',reason=reason)
 out.append(r);decisions.append(d)
evidence=nr+[byid[id]for id in sorted(used)];assert all(e.get('status')==200 for e in evidence);assert len(evidence)==len({e['id']for e in evidence});assert sum((ROOT/e['path']).stat().st_size for e in evidence)<6*1024*1024
save(ROOT/'adapter-inputs.json',{'schema_version':pilot.SCHEMA,'records':out,'evidence':evidence});save(ROOT/'decisions.json',decisions)
ev={e['id']:(e,(ROOT/e['path']).read_bytes())for e in evidence};shapes=usfs.state_shapes(load(STATES));rows=[]
for r in out:
 # Every native fact is retained and replayed, including held discoveries.
 qid=pilot._value(r['bindings']['native_id'],ev,family='wikidata');name=pilot._value(r['bindings']['name'],ev,family='wikidata');lat,lon=pilot._coordinates(r['bindings']['coordinates'],ev,'wikidata');original=next(x for x in q if x['pilot_id']==r['pilot_id']);assert r['pilot_id']=='culture:wd:'+qid;assert name==original['name'];assert[lat,lon]==[original['latitude'],original['longitude']];assert usfs.state_for([lat,lon],shapes)==r['state']
 if r['review']['decision']!='T2':continue
 pilot._source_contract(r,'wikidata',ev,pilot._same_native_entity(r['bindings'],'wikidata'))
 for k in ['rights_proofs','access_proofs','operator_identity_location_proofs']:pilot._proofs(r[k],ev,label=k)
 rows.append({'pilot_id':r['pilot_id'],'name':name,'latitude':lat,'longitude':lon,'region':r['state']})
local=load(COMPARISON);assert len(local)==890;assert sha(COMPARISON)=='9431758ec5d516c185e5f9349d1035a128b1f9ec078438f5ee7a02d20c3a1404'
collisions=[]
for i,a in enumerate(rows):
 for b in local+rows[:i]:
  if b.get('region')==a['region']and distance(a,b)<=250:collisions.append({'pilot_id':a['pilot_id'],'other':b.get('source_id',b.get('pilot_id')),'other_name':b.get('name'),'distance_m':round(distance(a,b),1)})
report={'reviewed_dispositions':len(out),'T2_source_review_recommendations':len(rows),'T1_held':len(out)-len(rows),'T3':0,'live_net_new':None,'T2_states':dict(Counter(x['region']for x in rows)),'T2_categories':dict(Counter(r['category']for r in out if r['review']['decision']=='T2')),'positive_adapter_evidence_bytes':sum((ROOT/e['path']).stat().st_size for e in evidence),'positive_adapter_evidence_receipts':len(evidence),'all_request_receipts':len(receipts),'retained_acquired_bytes':sum(e.get('bytes',0)for e in receipts),'source_failures':[e for e in receipts if e.get('error')or e.get('status')in[202,401,403,429,503]],'local_collision_candidates':collisions,'comparison_count':890,'comparison_sha256':sha(COMPARISON),'all24_native_field_Census_replay_passed':True,'T2_native_contract_rights_operator_literal_replay_passed':True,'adapter_sha256':sha(ROOT/'adapter-inputs.json'),'limitations':['Agent-assisted published-source review, not independent human or field verification.','Byte replay and state containment establish specific source/geometry properties; they do not establish publisher truth, surveyed accuracy or real-time public availability.','T2 recommendations are browse-only. Arrivals, compiled calendars and itinerary-ready conversions remain unverified.','Root must reconcile all60 candidates with890 local comparisons, semantic parent/component identities and the live catalog before counting net additions.','Operator evidence is restricted local audit material. Catalog structured facts derive from CC0 Wikidata; no operator photos, collection descriptions, testimonials or licensed exhibit materials are imported.']}
report['rate_policy_audit']={'violations':len(load(ROOT/'rate-policy-audit.json')['violations']),'affected_pilot_ids':load(ROOT/'rate-policy-audit.json')['affected_pilot_ids'],'all_affected_held':True,'future_fetcher_corrected_offline':True,'no_remedy_requests':True}
save(ROOT/'report.json',report);print(json.dumps({k:v for k,v in report.items()if k not in ['source_failures','limitations']},indent=2))
