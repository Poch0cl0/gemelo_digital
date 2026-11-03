import copy, json, unittest
from dataclasses import replace, asdict
from .model import Config,Policy,Patient,simulate as old
from .model_v4 import simulate,Dynamics
from .initial_state import InitialState,InitialPatient,Phase,from_operational
from .calibration_v4 import calibrate,synthetic_dataset,validate_holdout,calibrated_inputs

class V4Tests(unittest.TestCase):
    def config(self,**kw):return replace(Config(horizon=30,beta=0,doctors=1,nurses=1),**kw)
    def initial(self,c,state='active',remaining=4,**kw):
        p=InitialPatient(999,-5,2,(Phase('care',10,{'doctors':1,'nurses':1,'beds':1}),),state,remaining=remaining,elapsed=2 if state=='active' else 0,first_start=-2 if state=='active' else None,allocations={'doctors':[0],'nurses':[0],'beds':[0]} if state=='active' else {},**kw)
        return InitialState({k:getattr(c,k) for k in ('doctors','nurses','beds','icu','ventilators')},(p,),.3)
    def test_legacy_identity(self):
        for p in (Policy('fifo'),Policy(),Policy('tuned',2,60),Policy('aging')):
            a=old(self.config(),p,44,trace=True);b=simulate(self.config(),p,44,trace=True,mode='legacy')
            for r in (a,b):r['metrics'].pop('runtime_s')
            self.assertEqual(a,b)
    def test_one_phase_matches_metrics(self):
        for seed in (1000,1001):
            c=Config();a=old(c,seed=seed)['metrics'];b=simulate(c,seed=seed)['metrics']
            for key in ('objective','completed','started','max_queue','wait_censored'):
                self.assertAlmostEqual(a[key],b[key])
    def test_empty(self):
        self.assertEqual(simulate(self.config(),patients=[])['metrics']['arrivals'],0)
    def test_occupied_residual(self):
        c=self.config();r=simulate(c,patients=[],initial=self.initial(c))
        self.assertEqual(r['patients'][0]['finish'],4)
        self.assertEqual(r['metrics']['completed'],1)
    def test_full_capacity_wait(self):
        c=self.config();r=simulate(c,patients=[Patient(1,0,2,2,False)],initial=self.initial(c))
        self.assertEqual(r['patients'][1]['first_start'],4)
    def test_initial_roundtrip(self):
        c=self.config();init=self.initial(c)
        self.assertEqual(InitialState.from_dict(json.loads(json.dumps(asdict(init)))).availability()['doctors'],0)
    def test_initial_invalid(self):
        c=self.config();p=self.initial(c).patients[0]
        for bad in (replace(p,remaining=-1),replace(p,remaining=None),replace(p,provenance={'record':'observed','work':'unknown'}),replace(p,allocations={'doctors':[2]}),replace(p,first_start=1)):
            with self.subTest(patient=bad),self.assertRaises(ValueError):replace(self.initial(c),patients=(bad,)).validate()
        with self.assertRaises(ValueError):replace(self.initial(c),patients=(p,p)).validate()
    def test_operational_missing_work(self):
        with self.assertRaises(ValueError):from_operational([dict(id=1)],self.initial(self.config()).capacity,{},0,'observed','fixture')
    def test_resource_shortage(self):
        c=self.config(doctors=0);r=simulate(c,patients=[Patient(0,0,2,2,False)])
        self.assertEqual(r['metrics']['started'],0)
    def test_checkpoint_exact(self):
        c=Config(horizon=60);d=Dynamics(phase_fractions=(.3,.7),death=.001)
        full=simulate(c,seed=11,dynamics=d,trace=True)
        part=simulate(c,seed=11,dynamics=d,trace=True,stop_at=20)
        resumed=simulate(c,seed=11,dynamics=d,trace=True,checkpoint=json.loads(json.dumps(part['checkpoint'])))
        self.assertEqual(full,resumed)
    def test_checkpoint_mismatch(self):
        cp=simulate(self.config(),patients=[],stop_at=5)['checkpoint']
        with self.assertRaises(ValueError):simulate(self.config(),seed=2,checkpoint=cp)
    def test_immediate_preemption(self):
        c=self.config();ps=[Patient(0,0,2,10,False),Patient(1,2,0,2,False)]
        r=simulate(c,patients=ps,dynamics=Dynamics(preemption='immediate'))
        self.assertEqual(r['patients'][1]['first_start'],2)
        self.assertEqual(r['patients'][0]['finish'],12)
        self.assertTrue(any(e['type']=='preempted' for e in r['events']))
    def test_boundary_no_midphase_preemption(self):
        r=simulate(self.config(),patients=[Patient(0,0,2,10,False),Patient(1,2,0,2,False)],dynamics=Dynamics(preemption='boundary'))
        self.assertEqual(r['patients'][1]['first_start'],10)
    def test_noninterruptible(self):
        c=self.config();init=self.initial(c);p=init.patients[0]
        init=replace(init,patients=(replace(p,phases=(replace(p.phases[0],interruptible=False),)),))
        r=simulate(c,patients=[Patient(1,0,0,1,False)],initial=init,dynamics=Dynamics(preemption='immediate'))
        self.assertEqual(r['patients'][1]['first_start'],4)
    def test_phases_release_resources(self):
        r=simulate(self.config(),patients=[Patient(1,0,2,10,False)],dynamics=Dynamics(phase_fractions=(.5,.5)),trace=True)
        row=next(x for x in r['trace'] if x['t']==5)
        self.assertEqual(row['nurses'],0);self.assertEqual(r['patients'][0]['finish'],10)
    def test_capacity_drop_and_return(self):
        c=self.config();cap=self.initial(c).capacity;off={**cap,'doctors':0}
        r=simulate(c,patients=[Patient(0,0,2,10,False)],dynamics=Dynamics(calendar=((2,off),(5,cap))),trace=True)
        self.assertEqual(r['patients'][0]['finish'],13)
        self.assertTrue(any(e['type']=='capacity_pause' for e in r['events']))
    def test_fractional_calendar(self):
        c=self.config();cap=self.initial(c).capacity
        r=simulate(c,patients=[Patient(0,0,2,4,False)],dynamics=Dynamics(calendar=((.5,{**cap,'doctors':0}),(1.,cap))))
        self.assertEqual(r['patients'][0]['finish'],5)
    def test_outcomes_conservation_determinism(self):
        c=Config(horizon=60);d=Dynamics(death=.01,transfer=.01,abandonment=.02,deterioration=.03)
        a=simulate(c,seed=10,dynamics=d);b=simulate(c,seed=10,dynamics=d)
        self.assertEqual(a,b);m=a['metrics']
        self.assertEqual(m['arrivals'],sum(m[k] for k in ('completed','waiting','in_service','abandoned','dead','transferred')))
        self.assertGreater(sum(m[k] for k in ('abandoned','dead','transferred')),0)
    def test_disable_mechanisms(self):
        r=simulate(self.config(),seed=12)
        self.assertFalse(any(e['type'] in ('dead','transferred','abandoned','deteriorated') for e in r['events']))
    def test_invalid_dynamics(self):
        for d in (Dynamics(phase_fractions=(.5,)),Dynamics(death=-1),Dynamics(load='typo'),Dynamics(preemption='bad')):
            with self.assertRaises(ValueError):simulate(self.config(),dynamics=d)
    def test_synthetic_recovery_and_holdout(self):
        fit=calibrate(synthetic_dataset(99));valid=validate_holdout(fit,synthetic_dataset(100))
        self.assertAlmostEqual(fit['beta'],.25);self.assertAlmostEqual(fit['tau'],60)
        self.assertLess(abs(fit['service']['0']['mean']/60-1),.05)
        self.assertFalse(valid['clinical_validation'])
    def test_calibration_leakage_and_identifiability(self):
        data=synthetic_dataset(99);fit=calibrate(data)
        with self.assertRaises(ValueError):validate_holdout(fit,data)
        for row in data['load_observations']:row.update(F=0,next_F=0,utilization=0)
        with self.assertRaises(ValueError):calibrate(data)
    def test_calibrated_inputs_executable(self):
        fit=calibrate(synthetic_dataset(99))
        with self.assertRaises(ValueError):calibrated_inputs(fit,self.config(),1)
        c,patients,meta=calibrated_inputs(fit,self.config(),1,accept_synthetic=True)
        result=simulate(c,patients=patients)
        self.assertGreater(result['metrics']['arrivals'],0)
        self.assertFalse(meta['clinical_validation'])
    def test_terminal_max_queue_definition(self):
        c=self.config(horizon=1)
        r=simulate(c,patients=[Patient(0,.5,2,1,False)],trace=True)
        self.assertEqual(r['metrics']['max_queue'],1)
        self.assertEqual(max(row['waiting'] for row in r['trace'] if row['t']<1),0)
    def test_operational_enrichment_success(self):
        c=self.config();cap=self.initial(c).capacity
        initial=from_operational([dict(id=1,arrival_relative_minutes=-2,priority=2,state='waiting')],cap,{1:dict(phases=(Phase('care',3,{'doctors':1}),),remaining=3,provenance={'record':'observed','work':'estimated'})},.2,'estimated','local-fixture')
        self.assertEqual(simulate(c,patients=[],initial=initial)['metrics']['completed'],1)

if __name__=='__main__':unittest.main(verbosity=2)
