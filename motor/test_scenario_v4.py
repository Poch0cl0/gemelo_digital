import json,tempfile,unittest
from pathlib import Path
from .scenario_graph_v4 import ScenarioRequest,direct,build_graph
from .model_v4 import simulate

class ScenarioTests(unittest.TestCase):
    def test_actual_graph_equals_direct(self):
        request=dict(horizon=20,seeds=[9001],variant='full')
        graph=build_graph().invoke({'payload':request})
        self.assertEqual(graph['response'],direct(request))
        self.assertIn('record_provenance',graph['steps'])
    def test_reject_invalid_and_ambiguous(self):
        for request in ('choose the best clinical policy',{'origin':'observed'},{'work_unit':'NHAMCS_LOV'},{'horizon':True},{'seeds':[1,1]},{'parameters':{'beta':float('nan')}},{'metrics':['survival']},{'unexpected':1}):
            self.assertEqual(build_graph().invoke({'payload':request})['response']['status'],'abstained')
    def test_cache_recovery_and_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            request=dict(horizon=10)
            a=direct(request,folder);b=direct(request,folder)
            self.assertEqual(a,b)
            path=next(Path(folder).glob('*.json'));path.write_text(path.read_text().replace('completed','fabricated'))
            self.assertEqual(direct(request,folder)['status'],'abstained')
    def test_retry_real_graph_injected_tool(self):
        calls=[]
        def transient(*args,**kw):
            calls.append(1)
            if len(calls)==1:raise RuntimeError('transient fixture')
            return simulate(*args,**kw)
        result=build_graph(runner=transient).invoke({'payload':{'horizon':10}})
        self.assertEqual(result['attempts'],2);self.assertEqual(result['response']['status'],'completed')
    def test_failure_no_fabrication(self):
        def fail(*args,**kw):raise RuntimeError('fixture unavailable')
        result=build_graph(runner=fail).invoke({'payload':{'horizon':10}})
        self.assertEqual(result['response']['status'],'failed');self.assertNotIn('means',result['response'])

if __name__=='__main__':unittest.main(verbosity=2)
