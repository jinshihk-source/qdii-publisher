#!/usr/bin/env python3
import json,re,subprocess,tempfile,urllib.parse,urllib.request
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';HIST=DATA/'history';HIST.mkdir(parents=True,exist_ok=True)
TZ=timezone(timedelta(hours=8));now=datetime.now(TZ);today=now.date().isoformat()
UA='Mozilla/5.0 AppleWebKit/537.36 Chrome/154 Safari/537.36'
def get(url,headers=None,timeout=25):
 h={'User-Agent':UA,'Accept':'*/*'};h.update(headers or {})
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=timeout) as r:return r.read().decode('utf-8','ignore')
def run_limit_engine():
 with tempfile.TemporaryDirectory() as td:
  repo=Path(td)/'engine';subprocess.run(['git','clone','--depth','1','https://github.com/aiten2/qdii-purchase-limits.git',str(repo)],check=True)
  subprocess.run(['npm','ci','--omit=optional','--ignore-scripts'],cwd=repo,check=True)
  p=subprocess.run(['node','scripts/query-purchase-limits.js','--json'],cwd=repo,text=True,capture_output=True,check=True)
  s=p.stdout.strip();a=s.find('{');b=s.rfind('}')
  if a<0 or b<a:raise RuntimeError('额度引擎未返回 JSON')
  return json.loads(s[a:b+1])
def flatten_limits(raw):
 out=[]
 def walk(x,ctx=''):
  if isinstance(x,dict):
   code=str(x.get('code') or x.get('fund_code') or x.get('fundCode') or '');name=x.get('name') or x.get('fund_name') or x.get('fundName')
   if re.fullmatch(r'\d{6}',code) and name:
    out.append({'code':code,'name':str(name),'limit':x.get('max_buy',x.get('limit',x.get('maxPurchase'))),'status':x.get('status'),'channel':str(x.get('channel') or ctx).lower(),'fee_annual':x.get('fee_annual'),'index':x.get('index'),'share_class':x.get('share_class')})
   for k,v in x.items():walk(v,str(k))
  elif isinstance(x,list):
   for v in x:walk(v,ctx)
 walk(raw);merged={}
 for r in out:
  k=r['code'];m=merged.setdefault(k,{'code':k,'name':r['name'],'agency_limit':None,'direct_limit':None,'status':r['status'],'fee_annual':r['fee_annual'],'index':r['index'],'share_class':r['share_class']})
  if any(w in r['channel'] for w in ['direct','official','直销']):m['direct_limit']=r['limit']
  else:m['agency_limit']=r['limit']
  for f in ['fee_annual','index','share_class','status']:
   if m.get(f) is None and r.get(f) is not None:m[f]=r[f]
 return list(merged.values())
def returns_1y():
 end=now.date();start=end-timedelta(days=370);q={'op':'ph','dt':'kf','ft':'qdii','rs':'','gs':'0','sc':'1nzf','st':'desc','sd':start.isoformat(),'ed':end.isoformat(),'qdii':'','tabSubtype':',,,,,','pi':'1','pn':'1000','dx':'1','v':'0.77'}
 txt=get('https://fund.eastmoney.com/data/rankhandler.aspx?'+urllib.parse.urlencode(q),{'Referer':'https://fund.eastmoney.com/data/fundranking.html'})
 m=re.search(r'datas\s*:\s*(\[.*?\])\s*,\s*allRecords',txt,re.S) or re.search(r'datas\s*:\s*(\[.*?\])\s*[,}]',txt,re.S)
 if not m:return {}
 rows=json.loads(m.group(1));result={}
 for row in rows:
  parts=row.split(',') if isinstance(row,str) else row
  if len(parts)<12:continue
  code=str(parts[0]).strip('"')
  if re.fullmatch(r'\d{6}',code):
   try:result[code]=float(str(parts[11]).replace('%',''))
   except:result[code]=None
 return result
ETF_MASTER=[{'code':'513100','index':'NDX100','market':1},{'code':'513110','index':'NDX100','market':1},{'code':'159941','index':'NDX100','market':0},{'code':'159501','index':'NDX100','market':0},{'code':'159513','index':'NDX100','market':0},{'code':'159632','index':'NDX100','market':0},{'code':'513500','index':'SP500','market':1},{'code':'159612','index':'SP500','market':0},{'code':'513650','index':'SP500','market':1}]
def etf_quotes():
 out=[]
 for e in ETF_MASTER:
  try:
   u=f"https://push2.eastmoney.com/api/qt/stock/get?secid={e['market']}.{e['code']}&fields=f43,f48,f57,f58,f60,f152,f169,f170";d=json.loads(get(u)).get('data') or {};dp=int(d.get('f152') or 3);div=10**dp
   def n(k,dv=1):
    try:return float(d.get(k))/dv
    except:return None
   out.append({**e,'name':d.get('f58') or e['code'],'price':n('f43',div),'change_pct':n('f170',100),'amount':n('f48'),'premium_pct':None,'premium_source':'待接入可靠IOPV/折溢价源','updated_at':now.isoformat(timespec='seconds')})
  except Exception as ex:out.append({**e,'name':e['code'],'error':str(ex),'premium_pct':None})
 return out
def previous():
 fs=sorted(HIST.glob('*.json'))
 if not fs:return {}
 try:return {x['code']:x for x in json.loads(fs[-1].read_text('utf-8')).get('otc',[])}
 except:return {}
def limit_num(v):
 if v is None:return None
 if isinstance(v,(int,float)):return float(v)
 s=str(v).replace(',','')
 m=re.search(r'\d+(?:\.\d+)?',s)
 return float(m.group()) if m else None
def main():
 old=previous();errors=[]
 try:otc=flatten_limits(run_limit_engine())
 except Exception as e:
  errors.append('场外额度更新失败: '+str(e));otc=json.loads((DATA/'latest.json').read_text('utf-8')).get('otc',[]) if (DATA/'latest.json').exists() else []
 try:r1=returns_1y()
 except Exception as e:errors.append('近1年收益更新失败: '+str(e));r1={}
 for x in otc:
  x['return_1y']=r1.get(x['code'],x.get('return_1y'));p=old.get(x['code'])
  if not p:x['change']='new'
  else:
   a,b=limit_num(x.get('agency_limit')),limit_num(p.get('agency_limit'))
   x['change']='same' if a==b else ('up' if a is not None and (b is None or a>b) else 'down')
 etf=etf_quotes();payload={'date':today,'updated_at':now.isoformat(timespec='seconds'),'otc':otc,'etf':etf,'errors':errors,'sources':['aiten2/qdii-purchase-limits','天天基金/东方财富公开数据','东方财富公开场内行情']}
 tmp=DATA/'latest.tmp.json';tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8');tmp.replace(DATA/'latest.json');(HIST/f'{today}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8');print(json.dumps({'ok':True,'otc':len(otc),'etf':len(etf),'errors':errors},ensure_ascii=False))
if __name__=='__main__':main()
