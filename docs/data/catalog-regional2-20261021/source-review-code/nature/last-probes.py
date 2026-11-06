from acquire import get,P
import json
a=[]
for k,u in [('magnolia-plan','https://www.magnoliaplantation.com/plan-your-visit'),('magnolia-policy','https://www.magnoliaplantation.com/policies'),('mystic','https://mysticcaverns.com/')]:
 a.append(dict(key=k,result=get('nature-'+k,u)))
 (P/'last-probe-results.json').write_text(json.dumps(a,indent=2)+'\n')
