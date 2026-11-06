from html.parser import HTMLParser
from pathlib import Path
import re
class MainText(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.allparts=[];self.depth=0;self.capture=False;self.skip=0;self.title=False;self.title_parts=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='title':self.title=True
  if not self.capture and (tag=='main' or a.get('role')=='main'):self.capture=True;self.depth=1
  elif self.capture:self.depth+=tag not in ['br','hr','img','meta','input','link','source','wbr','area','embed','param','track','col','base']
  if tag in ['script','style','nav','footer']:self.skip+=1
 def handle_endtag(self,tag):
  if tag=='title':self.title=False
  if tag in ['script','style','nav','footer']and self.skip:self.skip-=1
  if self.capture:
   self.depth-=1
   if self.depth<=0:self.capture=False;self.depth=0
 def handle_data(self,d):
  d=re.sub(r'\s+',' ',d).strip()
  if self.title and d:self.title_parts.append(d)
  if not self.skip and d:self.allparts.append(d)
  if self.capture and not self.skip and d:self.parts.append(d)
 def result(self):return '\n'.join(self.parts)
def extract(path):
 p=MainText();p.feed(Path(path).read_text(errors='replace'));return p.result() or '\n'.join(p.allparts),' '.join(p.title_parts)
if __name__=='__main__':
 root=Path(__file__).parent;out=root/'operator-main-text';out.mkdir(exist_ok=True)
 for p in (root/'sources').glob('operator-*.body'):
  txt,title=extract(p);(out/(p.stem+'.txt')).write_text(title+'\n'+txt+'\n')
 print('texts',len(list(out.glob('*.txt'))))
