"""Offline timestamp audit; no fetches. Robots policies are applied when observed."""
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
import json
ROOT=Path(__file__).resolve().parent
UA='RoadtripsAreFun-CatalogReview/1.0 (bounded public source research)'
receipts=json.loads((ROOT/'receipts.json').read_text());policies={};last={};checks=[];grants=[];inspections=[]
for e in receipts:
 host=urlparse(e['url']).hostname;stamp=datetime.fromisoformat(e['checked_at']).timestamp();p=policies.get(host)
 if p and host in last:
  gap=stamp-last[host]['epoch'];checks.append({'receipt_id':e['id'],'url':e['url'],'previous_receipt_id':last[host]['receipt_id'],'previous_url':last[host]['url'],'actual_start_gap_seconds':round(gap,6),'required_crawl_delay_seconds':p['delay'],'policy_receipt_id':p['receipt_id'],'policy_url':p['url'],'compliant':gap>=p['delay']})
 last[host]={'epoch':stamp,'receipt_id':e['id'],'url':e['url']}
 if e['id'].startswith('robots')and e.get('status')==200 and e.get('path'):
  body=(ROOT/e['path']).read_text(errors='replace');rp=RobotFileParser();rp.parse(body.splitlines());delay=rp.crawl_delay(UA);rate=rp.request_rate(UA)
  if rate and rate.requests:delay=max(delay or 0,rate.seconds/rate.requests)
  inspections.append({'host':host,'receipt_id':e['id'],'url':e['url'],'applicable_crawl_delay_seconds':delay,'user_agent':UA})
  if delay is not None:
   policies[host]={'delay':delay,'receipt_id':e['id'],'url':e['url']};grants.append({'host':host,'delay_seconds':delay,'receipt_id':e['id'],'url':e['url']})
violations=[c for c in checks if not c['compliant']]
out={'method':'Chronological request-start timestamps, by exact host, including robots-to-first-content and redirect hops; applicable user-agent robots policies become known only after their retained response. Request completion timestamps were not recorded, so start gaps cannot certify completion-to-start intervals.','request_receipts_audited':len(receipts),'robots_policy_inspections':inspections,'applicable_policies':grants,'checks':checks,'violations':violations,'affected_pilot_ids':['culture:wd:Q119585283','culture:wd:Q49519614'],'affected_positive_evidence':['operator-Q49519614-0'],'disposition':'All affected destinations held. No further acquisition or timing-remedy requests. Reusable fetcher corrected offline; future review requires a separately authorized compliant acquisition.'}
(ROOT/'rate-policy-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'checks':len(checks),'violations':violations},indent=2))
