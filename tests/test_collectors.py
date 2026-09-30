import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import etf_collect as c
import update

class CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads((update.DATA/'latest.json').read_text('utf-8'))

    def test_quote_timeout_preserves_each_field_and_date(self):
        old={'code':'513100','price':2.1,'change_pct':0,'amount':None,'quote_effective_date':'2026-09-28'}
        earlier={'code':'513100','price':2,'change_pct':1,'amount':100,'quote_effective_date':'2026-09-27'}
        result=c.merge_etf_data({'code':'513100','premium_pct':9,'fee_annual':.8},None,{'return_1y':12},
                                [{'etf':[old]},{'etf':[earlier]}],[])
        self.assertEqual([result[k] for k in c.QUOTE_KEYS],[2.1,0,100])
        self.assertEqual(result['quote_status'],'fallback')
        self.assertIsNone(result['quote_effective_date'])
        self.assertEqual(result['quote_field_dates']['amount'],'2026-09-27')
        self.assertEqual(result['return_1y'],12)
        self.assertEqual(result['premium_pct'],9)

    def test_return_failure_preserves_quote_and_stale_date(self):
        row=self.payload['etf'][0]
        result=c.merge_etf_data(row,{'price':3,'change_pct':1,'amount':4},None,[self.payload],[])
        self.assertEqual(result['price'],3)
        self.assertEqual(result['return_1y'],row['return_1y'])
        self.assertEqual(result['return_1y_date'],row['return_1y_date'])
        self.assertTrue(result['return_1y_stale'])

    def test_retry_is_bounded(self):
        calls=[]
        def fail(timeout):calls.append(timeout);raise TimeoutError('simulated timeout')
        with patch.object(c.time,'sleep') as sleep:
            with self.assertRaises(RuntimeError):c.request_retry(fail,time.monotonic()+20)
        self.assertEqual(len(calls),3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list],[.2,.4])
        self.assertTrue(all(t<=2.5 for t in calls))

    def test_year_not_month_and_code_identity(self):
        raw='var fS_code="513100";var syl_1n="-3.21";var syl_1y="99";var Data_netWorthTrend=[{"x":1790611200000}];'
        self.assertEqual(c.parse_pingzhong(raw,'513100'),(-3.21,'2026-09-29'))
        with self.assertRaises(ValueError):c.parse_pingzhong(raw,'159941')

    def test_reject_bad_data_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'history').mkdir();(data/'latest.json').write_text('previous good snapshot')
            bad=copy.deepcopy(self.payload)
            for r in bad['etf']:r['return_1y']=None
            with self.assertRaises(ValueError):c.publish(bad,data,[self.payload])
            self.assertEqual((data/'latest.json').read_text(),'previous good snapshot')
            self.assertEqual(list((data/'history').iterdir()),[])
            bad=copy.deepcopy(self.payload);bad['etf'].pop()
            with self.assertRaises(ValueError):c.validate(bad,[self.payload])
            bad=copy.deepcopy(self.payload)
            for r in bad['etf']:r['price']=None
            with self.assertRaises(ValueError):c.validate(bad,[self.payload])

    def test_company_groups_and_share_order(self):
        rows=[{'index':'nasdaq100','code':str(i),'fund_company':company,'share_class':share,
               'agency_limit':quota,'direct_limit':None} for i,(company,share,quota) in enumerate([
                   ('甲','C',10),('乙','A',15),('甲','A',10),('甲','I','开放'),('丙','A','暂停')])]
        result=c.sort_otc(rows)
        self.assertEqual([r['fund_company'] for r in result],['甲','甲','甲','乙','丙'])
        self.assertEqual([r['share_class'] for r in result[:3]],['A','C','I'])
        self.assertEqual(result[0]['company_total_quota'],20)

    def test_metadata_failure_uses_snapshot(self):
        with patch.object(update,'qdiilimit_tables',side_effect=TimeoutError('simulated')):
            otc,master,errors=update.fetch_etf_metadata([self.payload])
        self.assertEqual(len(master),18)
        self.assertEqual(master['513100']['metadata_status'],'fallback')
        self.assertTrue(errors)
        self.assertEqual(len(otc),55)

    def test_independent_requests_failure_does_not_drop_products(self):
        master={r['code']:r for r in self.payload['etf'][:2]}
        def quote(code,*args):
            if code=='513100':raise TimeoutError('simulated')
            return {'price':3,'change_pct':0,'amount':5,'quote_status':'live'}
        with patch.object(c,'fetch_etf_quote',side_effect=quote),patch.object(c,'fetch_etf_return',return_value={'return_1y':1}):
            result=c.collect_etfs(master,None,None,[self.payload],time.monotonic()+2)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['quote_status'],'fallback')
        self.assertEqual(result[1]['quote_status'],'live')
        self.assertTrue(all(r['return_1y']==1 for r in result))

if __name__=='__main__':unittest.main()
