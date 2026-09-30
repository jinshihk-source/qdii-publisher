#!/usr/bin/env python3
import json,re,time,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
UA="Mozilla/5.0"; ROOT=Path(__file__).resolve().parents[1]
TESTS={"539001":"建信纳斯达克100 A","019441":"万家纳斯达克100 A","017641":"摩根标普500 A"}
def fetch(url,timeout=12):
 t=time.perf_counter(); req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":"https://fund.eastmoney.com/"})
 with urllib.request.urlopen(req,timeout=timeout) as r: body=r.read().decode("utf-8","ignore")
 return body,round(time.perf_counter()-t,3)
def clean(h): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",h))
out={"tested_at":datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),"rows":[]}
for code,label in TESTS.items():
 row={"code":code,"label":label}
 try:
  h,sec=fetch("https://fund.eastmoney.com/"+code+".html"); txt=clean(h); row["seconds"]=sec
  m=re.search(r"(?:单日累计购买上限|购买上限)[^0-9]{0,20}([0-9,.]+)元",txt); row["agency_limit"]=float(m.group(1).replace(",","")) if m else None
  m=re.search(r"近1年[：:]?\s*([-+0-9.]+)%",txt); row["return_1y"]=float(m.group(1)) if m else None
  row["ok"]=True
 except Exception as e: row.update(ok=False,error=str(e))
 out["rows"].append(row)
(ROOT/"data"/"smoke.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
print(json.dumps(out,ensure_ascii=False))
