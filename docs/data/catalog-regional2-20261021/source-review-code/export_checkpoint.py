"""Offline checkpoint packaging; never downloads or changes approvals."""
from pathlib import Path
from collections import Counter
import hashlib,json,shutil,sys

REPO=Path('/workspace/RoadtripsAreFun'); WORK=Path(__file__).parent
OUT=REPO/'docs/data/catalog-regional2-20261021'
sys.path[:0]=[str(REPO),str(REPO/'backend')]
from scripts.run_offline_tests import install
install()
from app.catalog import usfs_current
from app.catalog.pilot import distance,names,_native_aliases

def read(p):return json.loads(p.read_bytes())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

before=read(WORK/'comparison-890.json'); additions=read(OUT/'additions.preview.json');after=before+additions
assert len(before)==890 and len(additions)==27 and len(after)==917
assert len({r['source_id']for r in after})==917
source=read(WORK/'assembled/reviewed.json')
assert len(source['records'])==60
write(OUT/'prepared-queue.json',read(REPO/'docs/data/catalog-geodiverse-20261021/next-queue.json'))
write(OUT/'comparison-receipt.json',read(WORK/'comparison-890.receipt.json'))
write(OUT/'source-preflight.json',{
 'source_manifest_sha256':sha(WORK/'assembled/reviewed.json'),
 'prepared_queue':source['prepared_queue'],
 'comparison_artifacts':source['comparison_artifacts'],
 'local_comparison_rows':890,'live_parent_reconciled':False,
 'untouched_prior_source_manifests':{str(p):sha(p)for p in [Path('/workspace/catalog-geodiverse-20261021/assembled-main/reviewed.json'),Path('/workspace/catalog-geodiverse-20261021/assembled-baltimore-final/reviewed.json')]},
})

for group,files in {
 'museums':['decisions.json','report.json','validation.json','rate-policy-audit.json','timing-policy-validation.json','terms-access-review.json','receipts.json'],
 'nature':['decisions.json','validation.json','timing-audit.json','attempts.json','skipped-and-held-actions.json','persona-fact-basis.json'],
 'niche':['decisions.json','report.json','validation.json','robots-timing-audit.json','terms-ledger.json','receipts.json','discovery-leads.json'],
 'arrival-qualification':['qualification-report.json','receipts.json','evidence-receipts.json','size-receipts.json'],
}.items():
 for name in files:write(OUT/'source-review'/group/name,read(WORK/group/name))
 if (WORK/group/'README.md').exists():shutil.copyfile(WORK/group/'README.md',OUT/'source-review'/group/'README.md')
 # Keep the correction reviewable in Git. These copies are for code review;
 # original execution paths, raw bodies and working ledgers remain private.
 for path in sorted((WORK/group).glob('*.py')):
  dest=OUT/'source-review-code'/group/path.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)

routes_root=Path('/workspace/catalog-expansion-20261021/expansion-routes')
routes=usfs_current._load_routes(routes_root/'index.json',routes_root)
grid=usfs_current.corridor_grid(routes)
def corridors(rows):
 result=dict.fromkeys((ident for ident,_ in routes),0)
 result.update(Counter(ident for row in rows for ident in usfs_current.nearby_corridors(row['latitude'],row['longitude'],grid)))
 return result
coverage=read(OUT/'coverage.json')
coverage.update(
 program={'before_T2':194,'after_T2':221,'T3':0,'live_net_new':None},
 corridor_definition='Unchanged continuous five-mile buffer of16 frozen OSRM road captures; approximate city endpoints. Feature proximity only, not routable attraction counts or trip feasibility.',
 corridors_before=corridors(before),corridors_after=corridors(after),
 corridors_additions=corridors(additions),
 corridor_source_hashes={p.name:sha(p)for p in sorted(routes_root.glob('*.json'))},
)
write(OUT/'coverage.json',coverage)

# A useful bounded next queue from genuinely unreviewed native museum facts.
# No operator or permission is inferred by selection. Blocked-host audit remains
# mandatory before every future request.
available=read(WORK/'remaining-museum-candidates.json')
counts=Counter(r['region']for r in after);chosen=[];state_taken=Counter()
while available and len(chosen)<32:
 eligible=[r for r in available if state_taken[r['state']]<4]
 if not eligible:break
 row=min(eligible,key=lambda r:(state_taken[r['state']],counts[r['state']],r['state'],r['name'],r['pilot_id']))
 chosen.append(row);available.remove(row);state_taken[row['state']]+=1
records=[{'pilot_id':r['pilot_id'],'name':r['name'],'state':r['state'],'category':r['category'],'source_family':r['source_family'],'operator_url':r.get('operator_url'),'native_sha256':r['source_receipt']['sha256']}for r in chosen]
write(OUT/'next-queue.json',{
 'schema_version':'roadtrips-pilot-followup-queue/1','release':'catalog-next-museums',
 'records':records,'unreviewed_operator_review':[r['pilot_id']for r in records],
 'frozen_native_sha256':{r['pilot_id']:r['native_sha256']for r in records},
 'states':dict(state_taken),'local_comparison_count':917,
 'scope':'32 unreviewed museum-query entities across9 states. Native points have no immediate local name/identity/250m conflict; semantic review and all other gates remain. No current public access, operator rights or T2 admission inferred.',
 'preparation':'Standalone bounded artifact compared with all917 local rows. Carry blocked/closed and timing-quarantine ledgers forward. No blanket approval or repeated denied probes.',
})
assert len(records)==32 and len(state_taken)==9

# Separate varied industrial/ship/heritage discovery leads. Source permission
# and listed status do not establish public entry, safe arrival or current use.
all_culture=read(Path('/workspace/catalog-pilot-600-20261021/culture/prospects.json'))
old=read(Path('/workspace/catalog-geodiverse-20261021/assembled-main/reviewed.json'))
unreviewed={r['pilot_id']for r in old['records']if 'unreviewed_current_operator'in r.get('hold_reason','')}
keywords=('Kregel','Roundhouse','CAPTAIN MERIWETHER','Parker Carousel','WILLIAM M. BLACK','SERGEANT FLOYD','USS HAZARD','Mr. Charlie','Shreveport Water Works','Speedwell','Spencer Park','Burlington County Prison','Old Barracks','Norris,','Cather House','Coffin,','Debs,','Welty,','Rosalie','Old State Capitol','Murrell Home','Arbor Lodge','Dodge,','Knapp-Wilson','Hollenberg','Constitution Hall','Creek National Capitol')
leads=[]
for r in all_culture:
 if r['source_family']!='nps-nhl'or r['pilot_id']not in unreviewed or not any(k in r['name']for k in keywords):continue
 row={'source_id':'catalog-pilot:nps-nhl:'+r['native_id'],'provenance':[],'region':r['state'],'name':r['name'],'latitude':r['latitude'],'longitude':r['longitude']}
 if any(_native_aliases(row)&_native_aliases(o)or(row['region']==o['region']and names(row)&names(o))or distance(row,o)<250 for o in after):continue
 leads.append({'pilot_id':r['pilot_id'],'name':r['name'],'state':r['state'],'source_family':'nps-nhl','native_id':r['native_id'],'native_sha256':r['source_receipt']['sha256'],'raw_record_pointer':r['raw_record_pointer'],'operator_url':r.get('operator_url'),'tier':'T1','browse_eligible':False,'routing_eligible':False})
write(OUT/'next-heritage-leads.json',{
 'scope':'Discovery-only supplement from retained NPS native listed features; not admissions and not added to the32-place executable queue.',
 'records':leads,'count':len(leads),
 'next_steps':['Extend prepared-queue namespace/native checks explicitly for culture:nris before assembly; existing source-family/backend grant checks must remain.', 'Find permitted current public operators; distinguish relocated vessels, private homes, functioning workplaces and public visitor sites.','Preserve source identifiers/feature points and compare against917 local rows plus the live parent before release.'],
})

write(OUT/'validation.json',{
 'backend':{'passed':2124,'skipped':138,'coverage_percent':80.73,'minimum_unchanged':63,'log':'/workspace/catalog-regional2-20261021/backend-final-tests.log'},
 'postgres':{'passed':71,'split_suites':[63,8],'external_network':'blocked; fixed disposable loopback catalog_test only'},
 'focused_source_assembly_tests':30,'byte_identical_socket_disabled_replay_files':4,
 'database_proof':{'actual_repository_queries':27,'staged_twice':True,'rollback':True,'parent':'one synthetic row, not the live parent','calendars':0},
 'frontend':'No frontend changes; previous checkpoint278 tests/format/lint/build retained, not rerun in this checkpoint.',
 'acquisition_audit':{'confirmed_below_delay_intervals':8,'museum':3,'nature':5,'niche':0,'all_affected_positive_bodies_excluded_or_separately_compliant_positive_selected':True,'no_remedy_requests':True,'corrected_fetcher_tests':'offline, per-group artifacts'},
 'no_new_NC_admissions':True,'prior_NC_partition_sha256':sha(REPO/'docs/data/catalog-geodiverse-20261021/rights-research/partitions-final.json'),
 'production_writes':False,'external_AI_requests':0,'live_parent_reconciled':False,
})
write(OUT/'checksums.json',{str(p.relative_to(OUT)):sha(p)for p in sorted(OUT.rglob('*'))if p.is_file()and p.name!='checksums.json'})
print(json.dumps({'new_browse':27,'held':33,'program_browse':221,'local_total':917,'next_queue':len(records),'heritage_leads':len(leads),'corridor_additions':coverage['corridors_additions'],'audit_bytes':sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())},indent=2))
