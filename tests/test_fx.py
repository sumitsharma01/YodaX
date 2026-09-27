import unittest
from backend.fx import validate

class CurrencyTests(unittest.TestCase):
    def fixture(self):
        return dict(base='USD',amount=1,date='2026-01-02',rates=dict(INR=90,EUR=.9,GBP=.8,JPY=150,CAD=1.4))

    def test_base_and_complete_rates(self):
        fx=validate(self.fixture())
        self.assertEqual(fx['rates']['USD'],1)
        self.assertEqual(100*fx['rates']['INR'],9000)
        self.assertEqual(len(fx['rates']),6)

    def test_invalid_or_incomplete_rates_fail(self):
        for value in [0,-1,float('nan'),float('inf')]:
            data=self.fixture();data['rates']['INR']=value
            with self.assertRaises(ValueError): validate(data)
        data=self.fixture();del data['rates']['JPY']
        with self.assertRaises(KeyError): validate(data)
        data=self.fixture();data['base']='EUR'
        with self.assertRaises(ValueError): validate(data)
