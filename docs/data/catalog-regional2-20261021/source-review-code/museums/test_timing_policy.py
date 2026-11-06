"""No-network timing test: first content, same-host redirect and cached re-run."""
from pathlib import Path
from datetime import datetime as RealDatetime,UTC
import tempfile,socket,json
import acquire

clock=[1792600000.0];calls=[]
class FakeDatetime:
 @staticmethod
 def now(tz):return RealDatetime.fromtimestamp(clock[0],UTC)
 @staticmethod
 def fromisoformat(value):return RealDatetime.fromisoformat(value)
class Response:
 def __init__(self,url):
  self.url=url;self.headers={'Content-Type':'text/plain'}
  if url.endswith('/robots.txt'):self.status_code=200;self.body=b'User-agent: *\nCrawl-delay: 10\n'
  elif url.endswith('/visit'):self.status_code=302;self.headers['Location']='/gallery';self.body=b''
  else:self.status_code=200;self.body=b'<html>Public museum gallery</html>'
 def __enter__(self):clock[0]+=2;return self
 def __exit__(self,*_):return False
 def iter_content(self,size):yield self.body

def fake_get(url,**kwargs):calls.append({'url':url,'epoch':clock[0]});return Response(url)
def denied(*a,**k):raise AssertionError('No real network is permitted in this test')
with tempfile.TemporaryDirectory(prefix='timing-test-',dir=acquire.ROOT)as tmp:
 acquire.ROOT=Path(tmp);(acquire.ROOT/'raw').mkdir();(acquire.ROOT/'text').mkdir();acquire.ROBOTS={};acquire.HOST_DELAYS={};acquire.HOST_LAST={};acquire.BLOCKED=set()
 acquire.requests.get=fake_get;acquire.time.sleep=lambda seconds:clock.__setitem__(0,clock[0]+seconds);acquire.time.monotonic=lambda:clock[0];acquire.datetime=FakeDatetime;socket.socket=denied
 acquire.acquire_one('timing','https://timing-policy.example/visit')
 assert len(calls)==3,calls
 gaps=[calls[i]['epoch']-calls[i-1]['epoch']for i in range(1,len(calls))];assert min(gaps)>=10,gaps
 assert acquire.HOST_DELAYS['timing-policy.example']==10
 count=len(calls);acquire.acquire_one('timing','https://timing-policy.example/visit');assert len(calls)==count,'Immutable replay issued a new request'
 result={'real_network_disabled':True,'first_content_after_robots_seconds':gaps[0],'same_host_redirect_gap_seconds':gaps[1],'applicable_crawl_delay_seconds':10,'immutable_replay_no_requests':True,'passed':True}
(Path(__file__).resolve().parent/'timing-policy-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
