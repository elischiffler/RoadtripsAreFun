"""Offline replay with all network sockets disabled before app import."""
from pathlib import Path
import json,hashlib,socket,sys,subprocess,urllib.parse
P=Path(__file__).parent
socket.socket=lambda*a,**k:(_ for _ in ()).throw(RuntimeError('offline validation network forbidden'))
socket.create_connection=socket.socket
sys.path.insert(0,'/workspace/RoadtripsAreFun/backend')
from app.catalog import pilot,usfs
from app.catalog.mixed import distance,names
x=json.loads((P/'adapter-inputs.json').read_text());q=json.loads((P/'queue.json').read_text());dec=json.loads((P/'decisions.json').read_text());original={r['pilot_id']:r for r in json.load(open('/workspace/catalog-pilot-600-20261021/diversity/prospects.json'))};comparison=Path('/workspace/catalog-regional2-20261021/comparison-890.json');assert hashlib.sha256(comparison.read_bytes()).hexdigest()=='9431758ec5d516c185e5f9349d1035a128b1f9ec078438f5ee7a02d20c3a1404';baseline=json.loads(comparison.read_text());assert len(baseline)==890
states=Path('/workspace/catalog-expansion-20261021/usfs-national/sources/states.json');assert hashlib.sha256(states.read_bytes()).hexdigest()=='46404936ed8ca141ffd24779235c3250e047869655ec99bdc2211ba38a36dbd1';shapes=usfs.state_shapes(json.loads(states.read_text()));e={}
for rec in x['evidence']:
 b=(P/rec['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==rec['sha256'];assert rec['status']==200;e[rec['id']]=(rec,b)
assert len(x['records'])==20 and {r['pilot_id']for r in x['records']}=={r['pilot_id']for r in q}
conflicts=[];added=[];allrows={}
for r in x['records']:
 anchor=pilot._same_native_entity(r['bindings'],'wikidata');name=pilot._value(r['bindings']['name'],e,family='wikidata');qid=pilot._value(r['bindings']['native_id'],e,family='wikidata');loc=pilot._coordinates(r['bindings']['coordinates'],e,'wikidata');old=original[r['pilot_id']]
 assert name==old['name'] and qid==old['canonical_destination_id'].split(':')[-1] and loc==(old['latitude'],old['longitude'])
 assert usfs.state_for(loc,shapes)==r['state']
 row=dict(source_id='catalog-pilot:wikidata:'+qid,name=name,latitude=loc[0],longitude=loc[1],region=r['state'],provenance=[]);allrows[qid]=row
 if r['review']['decision']!='T2':continue
 pilot._source_contract(r,'wikidata',e,anchor)
 for field in ['access_proofs','operator_identity_location_proofs','rights_proofs']:pilot._proofs(r[field],e,label=field)
 host=lambda u:(urllib.parse.urlparse(u).hostname or'').removeprefix('www.')
 for field in ['access_proofs','operator_identity_location_proofs']:
  assert all(host(e[a['evidence_id']][0]['url'])==host(r['operator_url'])for a in r[field])
 matches=[dict(name=o['name'],source_id=o['source_id'],distance_m=round(distance(row,o),2))for o in baseline+added if distance(row,o)<250 or row['region']==o.get('region') and names(row)&names(o)]
 if matches:conflicts.append(dict(pilot_id=r['pilot_id'],matches=matches))
 added.append(row)
assert not conflicts,conflicts
attempts=json.loads((P/'attempts.json').read_text());assert len(attempts)<=65
for a in attempts:
 b=(P/a['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==a['sha256']and len(b)==a['bytes']and len(b)<=1048576
h=hashlib.sha256((P/'adapter-inputs.json').read_bytes()).hexdigest();subprocess.run([sys.executable,str(P/'build.py')],check=True,capture_output=True);assert h==hashlib.sha256((P/'adapter-inputs.json').read_bytes()).hexdigest()
report=dict(result='passed',reviewed=20,T2_source_reviewed=8,T1_held=12,T3_itinerary_ready=0,baseline_local_rows=890,live_catalog_reconciled=False,conflicts=conflicts,native_id_name_coordinate_immutability=20,Census_state_matches=20,proof_receipts=len(e),selected_positive_bytes=sum(len(v[1])for v in e.values()),actual_GET_attempts=len(attempts),replay_idempotent=True,network_disabled_in_validation=True,adapter_sha256=h,campus_relationship=dict(parent='wikidata:Q458588',component='wikidata:Q4883646',feature_distance_m=round(distance(allrows['Q458588'],allrows['Q4883646']),2),parent_disposition='T1 semantic counting hold; no category substitution',component_disposition='T2 conservatory only'),limitations=['Agent-assisted retained-source review; no independent human or field inspection.','No T3 arrival/calendar or road approach verified.','Local comparison excludes no unseen live production changes; final snapshot gate remains.','Schema/hash/literal checks do not prove all source assertions true.'])
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
