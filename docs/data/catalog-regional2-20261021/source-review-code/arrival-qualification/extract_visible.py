from html.parser import HTMLParser
from pathlib import Path
import sys,re,json
class P(HTMLParser):
 def __init__(self):super().__init__();self.s=0;self.text=[];self.links=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t in ['script','style']:self.s+=1
  if t in ['a','iframe','img'] and a.get('href',a.get('src')):self.links.append(a.get('href',a.get('src')))
 def handle_endtag(self,t):
  if t in ['script','style']:self.s=max(0,self.s-1)
 def handle_data(self,s):
  if not self.s:self.text.append(s)
for filename in sys.argv[1:]:
 p=Path(filename);h=P();h.feed(p.read_text());s=' '.join(' '.join(h.text).split());p.with_suffix('.txt').write_text(s);print(p.name+'\n'+s+'\nLINKS\n'+'\n'.join(sorted(set(x for x in h.links if any(w in x.lower() for w in ['map','direction','park','pdf','calendar','hour','policy','terms','sitemap'])))))
