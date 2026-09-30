#!/usr/bin/env python3
import json,re,time,urllib.parse,urllib.request
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,timedelta,timezone
from etf_collect import collect_etfs,snapshots,sort_otc,publish
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
 # The source provides a publication date and NAV date, but not an explicit
 # premium trading date. Keep that date unknown rather than inventing T-1.
 published=re.search(r'场内ETF概览.*?byline[^>]*>.*?(\d{4}-\d{2}-\d{2})',h,re.S)
 for row in re.findall(r'<tr\b[^>]*>.*?</tr>',h,re.S):
  code=re.search(r'class="c-code">(\d{6})<',row)
  if code and code[1] in etfs:
   nav=re.search(r'净值(\d{4}-\d{2}-\d{2})',row)
   etfs[code[1]].update(premium_effective_date=None,premium_nav_date=nav[1] if nav else None,
                       premium_published_date=published[1] if published else None,
                       premium_date_note='来源标记T-1，未披露对应交易日',metadata_status='live')
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
def fetch_otc(qmap):
 rows=[];errors=[]
 try:funds=discover()
 except Exception as exc:
  funds=list(qmap.values());errors.append({'source':'fund catalog','error':str(exc)})
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
def fetch_etf_metadata(history):
 try:
  qmap,master=qdiilimit_tables()
  if not qmap or not master:raise ValueError('empty qdiilimit tables')
  return qmap,master,[]
 except Exception as exc:
  if not history:raise
  old=history[0]
  qmap={x['code']:{**x,'quota_status':'fallback'} for x in old.get('otc',[])}
  fields=('index','fund_company','code','name','size_yi','previous_amount_yi','premium_pct',
          'fee_annual','premium_source','premium_effective_date','premium_nav_date',
          'premium_published_date','premium_date_note')
  master={x['code']:{**{k:x.get(k) for k in fields},'metadata_status':'fallback'} for x in old['etf']}
  return qmap,master,[{'source':'qdiilimit','error':str(exc)}]

def etf_quotes(master,history,deadline):
 return collect_etfs(master,get,TableParser,history,deadline)

def fetch_indices(history):
 out={};errs=[]
 for key,symbol,label in [('nasdaq100','%5ENDX','纳斯达克100'),('sp500','%5EGSPC','标普500')]:
  try:
   raw=json.loads(get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d',timeout=8))
   r=raw['chart']['result'][0];meta=r.get('meta') or {};ts=r.get('timestamp') or [];cl=(r.get('indicators',{}).get('quote') or [{}])[0].get('close') or []
   pts=[[int(t),round(float(v),2)] for t,v in zip(ts,cl) if v is not None]
   price=meta.get('regularMarketPrice');prev=meta.get('chartPreviousClose') or meta.get('previousClose')
   if price is None and pts:price=pts[-1][1]
   if prev is None and len(pts)>1:prev=pts[-2][1]
   change=(float(price)-float(prev)) if price is not None and prev is not None else None
   out[key]={'name':label,'symbol':'^NDX' if key=='nasdaq100' else '^GSPC','price':round(float(price),2) if price is not None else None,'change':round(change,2) if change is not None else None,'change_pct':round(change/float(prev)*100,2) if change is not None and prev else None,'history_1y':pts,'source':'Yahoo Finance chart','status':'live','updated_at':now.isoformat(timespec='seconds')}
  except Exception as exc:
   old=next((h.get('indices',{}).get(key) for h in history if h.get('indices',{}).get(key,{}).get('price') is not None),None)
   if old:out[key]={**old,'status':'fallback','error':str(exc)}
   else:out[key]={'name':label,'price':None,'change':None,'change_pct':None,'history_1y':[],'status':'unavailable','error':str(exc)}
   errs.append({'source':'market index '+key,'error':str(exc)})
 return out,errs

def previous_day():
 fs=sorted(p for p in HIST.glob('*.json') if p.stem<today)
 if not fs:return {}
 try:return {x['code']:x for x in json.loads(fs[-1].read_text('utf-8')).get('otc',[])}
 except:return {}
def comparable(v):
 return float(v) if isinstance(v,(int,float)) else v
def main():
 started=time.perf_counter();deadline=time.monotonic()+50;old=previous_day();history=snapshots(DATA)
 qmap,master,metadata_errors=fetch_etf_metadata(history)
 indices,index_errors=fetch_indices(history)
 metadata_errors.extend(index_errors)
 with ThreadPoolExecutor(max_workers=2) as pool:
  otc_job=pool.submit(fetch_otc,qmap)
  etf_job=pool.submit(etf_quotes,master,history,deadline)
  otc,errs=otc_job.result();etf=etf_job.result()
 errs.extend(metadata_errors)
 otc=sort_otc(otc)
 for row in etf:
  for error in row.get('collection_errors',[]):errs.append({'code':row['code'],**error})
 for x in otc:
  p=old.get(x['code'])
  if not p:x['change']='new'
  else:
   a,b=comparable(x.get('agency_limit')),comparable(p.get('agency_limit'))
   x['change']='same' if a==b else ('changed')
 payload={'date':today,'updated_at':now.isoformat(timespec='seconds'),'duration_seconds':round(time.perf_counter()-started,2),'otc':otc,'etf':etf,'indices':indices,'errors':errs,'sources':['天天基金/东方财富公开基金销售页','qdiilimit公开汇总（场外额度/费率及场内基础信息）','东方财富/腾讯公开场内行情','天天基金pingzhongdata syl_1n（近一年）'],'validation_note':'场内价格、涨跌、成交额来自东方财富/腾讯公开行情，失败保留历史快照并标记fallback；场内溢价率为qdiilimit最近已发布的T-1数据。场外代销额度由天天基金销售页交叉核对，直销/费率来自公开汇总。'}
 publish(payload,DATA,history)
 print(json.dumps({'ok':True,'duration_seconds':payload['duration_seconds'],'otc':len(otc),'etf':len(etf),'errors':len(errs)},ensure_ascii=False))
if __name__=='__main__':main()
