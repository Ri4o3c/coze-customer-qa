import runpy
import unittest
from pathlib import Path

score=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/score_actual.py'))['score']

class ScoringTests(unittest.TestCase):
    def expected(self):
        return [{'ticket_id':'A','category':'物流配送','needs_review':False,
                 'checks':{'R01':'pass','R02':'pass','R03':'pass'}},
                {'ticket_id':'B','category':None,'needs_review':True,
                 'checks':{'R01':'unknown','R02':'unknown','R03':'unknown'}}]

    def actual(self):
        return {'ticket_id':'A','category':'物流配送','category_valid':True,'needs_review':False,
                'checks':[{'rule_id':rid,'status':'pass'} for rid in ('R01','R02','R03')]}

    def test_missing_case_stays_in_denominator(self):
        s=score([self.actual()],self.expected())
        self.assertEqual(s['expected_total'],2); self.assertEqual(s['matched_cases'],1)
        self.assertEqual(s['missing_ids'],['B'])

    def test_duplicate_result_is_not_correct_answer(self):
        s=score([self.actual(),self.actual()],self.expected())
        self.assertEqual(s['matched_cases'],0); self.assertEqual(s['duplicate_ids'],['A'])

    def test_wrong_rule_label_is_reported(self):
        a=self.actual(); a['checks'][1]['status']='fail'
        s=score([a],self.expected())
        self.assertIn('R02',s['cases'][0]['differences'])

if __name__=='__main__':
    unittest.main()
