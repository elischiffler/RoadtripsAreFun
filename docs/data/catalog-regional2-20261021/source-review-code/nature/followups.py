from acquire import get,P
import json
TARGETS=[('greensboro-hours','https://www.greensboroscience.org/hours-prices/'),('life-visit','https://www.lifeandscience.org/visit/'),('cheekwood-visit','https://cheekwood.org/visit/'),('arboretum-hours','https://ncarboretum.org/plan-a-visit/hours-directions-prices/'),('magnolia-visit','https://www.magnoliaplantation.com/visit'),('moore-tours','https://www.moorefarmsbg.org/bookings/tours')]
if __name__=='__main__':
 out=[]
 for k,u in TARGETS:
  out.append(dict(key=k,result=get('nature-'+k,u)))
  (P/'followup-results.json').write_text(json.dumps(out,indent=2)+'\n')
