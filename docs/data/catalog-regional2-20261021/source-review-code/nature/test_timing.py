from timing_policy import declared_delay,required_wait,wait_for
assert declared_delay('user-agent:*\ncrawl-delay:60')==60
assert declared_delay('Crawl-delay:10\nUser-agent: *\nDisallow:')==10
assert required_wait(1.2,0,10)==8.8
assert required_wait(61,1,60)==0
for delay in [5,10,60]:
 a=[dict(url='https://x.test/robots.txt',status=200,checked_at='2026-10-21T00:00:00+00:00',completed_at='2026-10-21T00:00:02+00:00')]
 from datetime import datetime
 now=datetime.fromisoformat('2026-10-21T00:00:03+00:00').timestamp()
 assert wait_for('https://x.test/page',a,lambda r:f'User-agent: *\nCrawl-delay: {delay}',now)==delay-1
 a.append(dict(url='https://x.test/page',status=301,checked_at='2026-10-21T00:00:03+00:00',completed_at='2026-10-21T00:00:04+00:00'))
 assert wait_for('https://x.test/redirect',a,lambda r:f'Crawl-delay: {delay}',now)==delay+1
print('Pure timing policy tests passed; no network.')
