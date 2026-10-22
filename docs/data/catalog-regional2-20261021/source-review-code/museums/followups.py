"""Offline by default; replay only the exact retained visitor/terms followup jobs."""
import argparse
import acquire
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--acquire',action='store_true');a=p.parse_args()
 if not a.acquire:print('Offline default. --acquire uses only retained exact followup jobs and cached immutable responses.');raise SystemExit
 for source,label,target in [('followup-jobs.json','followup','followup-decisions.json'),('final-followup-jobs.json','final','final-followup-decisions.json')]:
  jobs=acquire.json.loads((acquire.ROOT/source).read_text());out=[]
  for i,(q,u)in enumerate(jobs):
   try:out.append(acquire.acquire_one(q,u,label+str(i)))
   except Exception as e:out.append({'native_id':q,'hold':str(e)})
   acquire.save(acquire.ROOT/target,out)
