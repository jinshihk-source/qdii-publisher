#!/usr/bin/env python3
import json,re,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';HIST=DATA/'history';HIST.mkdir(parents=True,exist_ok=True)
TZ=timezone(timedelta(hours=8));now=datetime.now(TZ);today=now.date().isoformat()
UA='Mozilla/5.0 AppleWebKit/537.36 Chrome/154 Safari/537.36'
CATALOG='https://fund.eastmoney.com/js/fundcode_search.js'
def get(url,timeout=10):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':'https://fund.eastmoney.com/'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode('utf-8','ignore')
def text(h):return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',h))
def classify(name):
 n=name.upper()
 if '纳斯达克100' in name or 'NASDAQ100' in n or 'NASDAQ 100' in n:return 'nasdaq100'
 if '标普500' in name or 'S&P500' in n or 'S&P 500' in n:return 'sp500'
 return None
def share_class(name):
 s=re.sub(r'\([^)]*\)','',name);m=re.search(r'(?:人民币|美元现汇|美元现钞)?([A-Z])(?:人民币|类|$)',s,re.I);return m.group(1).upper() if m else None
def discover():
 raw=get(CATALOG);m=re.search(r'(\[\[.*\]\])',raw,re.S)
 if not m:raise RuntimeError('基金目录格式无法识别')
 rows=json.loads(m.group(1));out=[]
 for r in rows:
  if len(r)<4:continue
  code,name=str(r[0]),str(r[2]);idx=classify(name)
  if not idx or not re.fullmatch(r'\d{6}',code):continue
  # 场外人民币份额；排除 ETF 本体、美元份额
  u=name.upper()
  if 'ETF' in u and '联接' not in name:continue
  if '美元' in name:continue
  out.append({'code':code,'name':name,'index':idx,'share_class':share_class(name)})
 return out
def parse_one(f):
 t=time.perf_counter();h=get('https://fund.eastmoney.com/'+f['code']+'.html');s=text(h)
 status='unknown';seg=s[s.find('交易状态'):s.find('交易状态')+500] if '交易状态' in s else s[:1200]
 if re.search(r'暂停申购|暂停购买',seg):status='suspended'
 elif re.search(r'暂不开放购买|不可购买|不支持购买',seg):status='unavailable'
 elif re.search(r'限大额|限购|限制申购|购买上限',seg):status='limited'
 elif re.search(r'开放申购|开放购买',seg):status='open'
 m=re.search(r'(?:单日累计(?:购买|申购)上限|购买上限|申购上限|限额|限制金额)[^0-9]{0,30}([0-9,.]+)\s*(万|元)',seg)
 amt=None
 if m:
  amt=float(m.group(1).replace(',',''))*(10000 if m.group(2)=='万' else 1)
 if status=='suspended':agency='暂停'
 elif status=='unavailable':agency='不可申购'
 elif status=='open':agency='开放'
 else:agency=amt
 m=re.search(r'近1年[：:]?\s*([-+0-9.]+)%',s);r1=float(m.group(1)) if m else None
 # 管理人字段；若页面形态变化则保留空值，不猜
 company=None
 for pat in [r'基金管理人[：:]?\s*([^|]{2,24}?基金)',r'管 理 人[：:]?\s*([^|]{2,24}?基金)']:
  mm=re.search(pat,s)
  if mm:company=mm.group(1).strip().lstrip('：: ').strip();break
 return {**f,'agency_limit':agency,'agency_status':status,'direct_limit':None,'direct_status':'unverified','fund_company':company,'fee_annual':None,'return_1y':r1,'source_url':'https://fund.eastmoney.com/'+f['code']+'.html','fetch_seconds':round(time.perf_counter()-t,3)}
def fetch_otc():
 funds=discover();rows=[];errors=[]
 with ThreadPoolExecutor(max_workers=12) as ex:
  jobs={ex.submit(parse_one,f):f for f in funds}
  for job in as_completed(jobs):
   try:rows.append(job.result())
   except Exception as e:errors.append({'code':jobs[job]['code'],'error':str(e)})
 return rows,errors
ETF_MASTER=[('513100','NDX100',1),('513110','NDX100',1),('159941','NDX100',0),('159501','NDX100',0),('159513','NDX100',0),('159632','NDX100',0),('513500','SP500',1),('159612','SP500',0),('513650','SP500',1)]
def etf_one(e):
 code,idx,market=e;d=json.loads(get(f'https://push2.eastmoney.com/api/qt/stock/get?secid={market}.{code}&fields=f43,f48,f57,f58,f152,f170')).get('data') or {};dp=int(d.get('f152') or 3);div=10**dp
 def n(k,dv=1):
  try:return float(d.get(k))/dv
  except:return None
 return {'code':code,'index':idx,'market':market,'name':d.get('f58') or code,'price':n('f43',div),'change_pct':n('f170',100),'amount':n('f48'),'premium_pct':None,'premium_source':'待接入可靠IOPV/官方折溢价源','updated_at':now.isoformat(timespec='seconds')}
def etf_quotes():
 with ThreadPoolExecutor(max_workers=9) as ex:return list(ex.map(etf_one,ETF_MASTER))
def previous_day():
 fs=sorted(p for p in HIST.glob('*.json') if p.stem<today)
 if not fs:return {}
 try:return {x['code']:x for x in json.loads(fs[-1].read_text('utf-8')).get('otc',[])}
 except:return {}
def comparable(v):
 return float(v) if isinstance(v,(int,float)) else v
def main():
 started=time.perf_counter();old=previous_day();otc,errs=fetch_otc()
 for x in otc:
  p=old.get(x['code'])
  if not p:x['change']='new'
  else:
   a,b=comparable(x.get('agency_limit')),comparable(p.get('agency_limit'))
   x['change']='same' if a==b else ('changed')
 # 直销额度不再伪造：轻量主链路暂标 unverified，后续接第二可靠源
 etf=etf_quotes();payload={'date':today,'updated_at':now.isoformat(timespec='seconds'),'duration_seconds':round(time.perf_counter()-started,2),'otc':otc,'etf':etf,'errors':errs,'sources':['天天基金/东方财富公开基金销售页','东方财富公开场内行情'],'validation_note':'直销额度尚未接入第二可靠源，当前不展示为已验证数据'}
 tmp=DATA/'latest.tmp.json';tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8');tmp.replace(DATA/'latest.json');(HIST/f'{today}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps({'ok':True,'duration_seconds':payload['duration_seconds'],'otc':len(otc),'etf':len(etf),'errors':len(errs)},ensure_ascii=False))
if __name__=='__main__':main()
