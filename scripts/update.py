#!/usr/bin/env python3
import json,re,time,urllib.parse,urllib.request
from html.parser import HTMLParser
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

class TableParser(HTMLParser):
 def __init__(self):
  super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='table':self.table=[]
  elif tag=='tr' and self.table is not None:self.row=[]
  elif tag in ('td','th') and self.row is not None:self.cell=[]
 def handle_data(self,data):
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag in ('td','th') and self.cell is not None:self.row.append(''.join(self.cell).strip());self.cell=None
  elif tag=='tr' and self.row is not None:
   if any(self.row):self.table.append(self.row)
   self.row=None
  elif tag=='table' and self.table is not None:
   if self.table:self.tables.append(self.table)
   self.table=None
def qvalue(v):
 v=str(v).strip()
 if v in ('暂停','无代销','无直销','不适用','—','-'):return v
 m=re.search(r'[0-9,.]+',v);return float(m.group().replace(',','')) if m else v
def pct(v):
 m=re.search(r'[-+]?\d+(?:\.\d+)?',str(v));return float(m.group()) if m else None
def qdiilimit_tables():
 h=get('https://qdiilimit.com/',timeout=12);p=TableParser();p.feed(h);otc={};etfs={}
 for t in p.tables:
  if not t:continue
  head=t[0]
  if '代销限额(元/日)' in head and '直销限额(元/日)' in head:
   for r in t[1:]:
    if len(r)<7 or not re.fullmatch(r'\d{6}',r[2].strip()):continue
    code=r[2].strip();otc[code]={'index':'sp500' if '标普' in r[0] else 'nasdaq100','fund_company':r[1].strip(),'code':code,'name':r[3].strip(),'agency_limit':qvalue(r[4]),'direct_limit':qvalue(r[5]),'fee_annual':pct(r[6]),'tracking_error':pct(r[7]) if len(r)>7 else None,'quota_note':r[8].strip() if len(r)>8 else '','share_class':share_class(r[3])}
  elif 'T-1日溢价率' in head and '前一日成交额(亿)' in head:
   for r in t[1:]:
    if len(r)<9 or not re.fullmatch(r'\d{6}',r[2].strip()):continue
    code=r[2].strip();etfs[code]={'index':'SP500' if '标普' in r[0] else 'NDX100','fund_company':r[1].strip(),'code':code,'name':r[3].strip(),'size_yi':pct(r[5]),'previous_amount_yi':pct(r[6]),'premium_pct':pct(r[7]),'fee_annual':pct(r[8]),'premium_source':'qdiilimit公开汇总（T-1）'}
 return otc,etfs

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
 qmap,_=qdiilimit_tables();funds=discover();rows=[];errors=[]
 with ThreadPoolExecutor(max_workers=12) as ex:
  jobs={ex.submit(parse_one,f):f for f in funds}
  for job in as_completed(jobs):
   try:rows.append(job.result())
   except Exception as e:errors.append({'code':jobs[job]['code'],'error':str(e)})
 live={x['code']:x for x in rows};merged=[]
 for code,q in qmap.items():
  x=live.get(code,{})
  q['return_1y']=x.get('return_1y');q['agency_live']=x.get('agency_limit');q['agency_status']=x.get('agency_status');q['direct_status']='published-summary';q['source_url']=x.get('source_url');q['fetch_seconds']=x.get('fetch_seconds')
  q['verification']='matched' if x and str(x.get('agency_limit'))==str(q.get('agency_limit')) else ('agency-source-diff' if x else 'summary-only')
  merged.append(q)
 return merged,errors
def etf_quotes():
 _,master=qdiilimit_tables();out=[]
 def one(e):
  code=e['code'];market=1 if code.startswith(('5','6')) else 0
  try:
   d=json.loads(get(f"https://push2.eastmoney.com/api/qt/stock/get?secid={market}.{code}&fields=f43,f48,f57,f58,f170")).get('data') or {};div=1000
   def num(k,dv=1):
    try:return float(d.get(k))/dv
    except:return None
   return {**e,'market':market,'price':num('f43',div),'change_pct':num('f170',100),'amount':num('f48'),'premium_source':'qdiilimit公开汇总（T-1）','updated_at':now.isoformat(timespec='seconds')}
  except Exception as ex:return {**e,'market':market,'price':None,'change_pct':None,'amount':None,'premium_source':'qdiilimit公开汇总（T-1）','error':str(ex)}
 with ThreadPoolExecutor(max_workers=12) as ex:
  for x in ex.map(one,master.values()):out.append(x)
 return out
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
 etf=etf_quotes();payload={'date':today,'updated_at':now.isoformat(timespec='seconds'),'duration_seconds':round(time.perf_counter()-started,2),'otc':otc,'etf':etf,'errors':errs,'sources':['天天基金/东方财富公开基金销售页','qdiilimit公开汇总（场外额度/费率及场内基础信息）','东方财富公开场内行情'],'validation_note':'场内价格、涨跌、成交额来自东方财富公开行情；场内溢价率为qdiilimit最近已发布的T-1数据。场外代销额度由天天基金销售页交叉核对，直销/费率来自公开汇总。'}
 tmp=DATA/'latest.tmp.json';tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8');tmp.replace(DATA/'latest.json');(HIST/f'{today}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
 print(json.dumps({'ok':True,'duration_seconds':payload['duration_seconds'],'otc':len(otc),'etf':len(etf),'errors':len(errs)},ensure_ascii=False))
if __name__=='__main__':main()
