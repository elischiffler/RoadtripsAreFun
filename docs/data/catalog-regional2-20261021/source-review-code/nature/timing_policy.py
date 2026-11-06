"""Pure conservative request policy; independent of network or system clock."""
import re
from datetime import datetime
from urllib.parse import urlparse

def declared_delay(text):
    # Conservative maximum also honors orphan declarations and other UA groups.
    return max([0.7]+[float(v)for v in re.findall(r'(?im)^\s*crawl-delay\s*:\s*([0-9]+(?:\.[0-9]+)?)',text)])
def required_wait(now,last_completed,delay):
    return max(0.0,float(delay)-(float(now)-float(last_completed)))
def host(url):return(urlparse(url).hostname or'').removeprefix('www.')
def wait_for(url,attempts,body_reader,now):
    relevant=[r for r in attempts if host(r['url'])==host(url)]
    if not relevant:return 0.7
    delay=max([0.7]+[declared_delay(body_reader(r))for r in relevant if '/robots.txt'in r['url']and r.get('status')==200])
    # Old ledgers lack response completion; 35-second ceiling is conservative.
    last=max(datetime.fromisoformat(r.get('completed_at',r['checked_at'])).timestamp()+(0 if r.get('completed_at')else 35)for r in relevant)
    return required_wait(now,last,delay)
