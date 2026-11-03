"""Explicit parameter estimation; synthetic recovery is not hospital calibration."""
import math
from dataclasses import replace
import numpy as np
from scipy import stats
from .initial_state import capacities, number
from .model import Patient

def calibrate(data):
    required={'kind','source','record_ids','arrival_counts','exposures','service','load_observations','capacity_observations'}
    if not isinstance(data,dict) or set(data)!=required: raise ValueError('Calibration schema mismatch')
    if data['kind'] not in ('synthetic','observed') or not isinstance(data['source'],str) or not data['source']: raise ValueError('Data origin/source required')
    ids=data['record_ids']
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids): raise ValueError('Unique record IDs required')
    counts=data['arrival_counts'];exposures=data['exposures']
    if not counts or len(counts)!=len(exposures): raise ValueError('Counts/exposures mismatch')
    rates=[]
    for count,exposure in zip(counts,exposures):
        if type(count) is not int or count<0: raise ValueError('Counts must be nonnegative integers')
        number(exposure,'exposure',1e-12)
        rates.append(dict(rate=count/exposure,ci95=[float(stats.chi2.ppf(.025,2*count)/2/exposure) if count else 0,float(stats.chi2.ppf(.975,2*(count+1))/2/exposure)]))
    services={}
    for label,values in data['service'].items():
        if label not in ('0','1','2') or len(values)<2: raise ValueError('At least two service observations per class')
        for x in values:number(x,'service',1e-12)
        mean=float(np.mean(values));var=float(np.var(values,ddof=1))
        services[label]=dict(distribution='gamma_moments' if var else 'constant',mean=mean,variance=var,shape=mean*mean/var if var else None,scale=var/mean if var else None,n=len(values))
    if set(services)!={'0','1','2'}: raise ValueError('All priority groups required')
    rows=data['load_observations']
    if len(rows)<3: raise ValueError('Load observations required')
    xs=[];ys=[];fatigue=[];speed=[]
    for row in rows:
        if set(row)!={'F','next_F','utilization','dt','speed'}: raise ValueError('Invalid load observation')
        for k,x in row.items():number(x,k)
        if max(row['F'],row['next_F'],row['utilization'],row['speed'])>1 or row['dt']<=0: raise ValueError('Load observation outside domain')
        xs.append(row['dt']*(row['utilization']-row['F']));ys.append(row['next_F']-row['F']);fatigue.append(row['F']);speed.append(row['speed'])
    x=np.array(xs);y=np.array(ys);f=np.array(fatigue);speed=np.array(speed)
    if x@x<1e-12 or f@f<1e-12: raise ValueError('Load parameters not identifiable')
    inverse_tau=float(x@y/(x@x));beta=float(f@(1-speed)/(f@f))
    if inverse_tau<=0 or not 0<=beta<1: raise ValueError('Estimated load parameters outside model domain')
    caps=[capacities(c) for c in data['capacity_observations']]
    if not caps: raise ValueError('Capacity observations required')
    return dict(kind=data['kind'],source=data['source'],record_ids=ids,arrival_rates=rates,service=services,beta=beta,tau=1/inverse_tau,capacities_max={r:max(c[r] for c in caps) for r in caps[0]},load_rmse=float(np.sqrt(np.mean((y-x*inverse_tau)**2))),speed_rmse=float(np.sqrt(np.mean((speed-(1-beta*f))**2))),clinical_validation=False,note='Max observed availability is descriptive, not an optimized staffing recommendation; gamma fit does not automatically replace V3 triangular inputs')

def validate_holdout(fit,data):
    if set(fit['record_ids']) & set(data['record_ids']): raise ValueError('Calibration/validation leakage')
    validation=calibrate(data)
    return dict(kind=data['kind'],source=data['source'],service_mean_errors={k:validation['service'][k]['mean']-fit['service'][k]['mean'] for k in fit['service']},arrival_rate_errors=[b['rate']-a['rate'] for a,b in zip(fit['arrival_rates'],validation['arrival_rates'])],beta_error=validation['beta']-fit['beta'],tau_error=validation['tau']-fit['tau'],clinical_validation=False)

def synthetic_dataset(seed,n=4000):
    rng=np.random.default_rng(seed);fatigue=.1;rows=[]
    for i in range(240):
        u=float(.5+.4*math.sin(i/20));nxt=fatigue+(u-fatigue)/60
        rows.append(dict(F=fatigue,next_F=nxt,utilization=u,dt=1,speed=1-.25*fatigue));fatigue=nxt
    return dict(kind='synthetic',source=f'generated-recovery-{seed}',record_ids=[f'{seed}:{i}' for i in range(n)],arrival_counts=[int(rng.poisson(rate*10000)) for rate in (.8,.3,.1)],exposures=[10000]*3,service={str(k):rng.gamma(4,mean/4,n).tolist() for k,mean in enumerate((60,30,15))},load_observations=rows,capacity_observations=[dict(doctors=8,nurses=12,beds=12,icu=4,ventilators=3)])

def calibrated_inputs(fit,config,seed,*,accept_synthetic=False):
    """Explicitly opt into fitted rates, gamma work, capacities and load parameters.

    Priority proportions/ventilation are still declared synthetic assumptions;
    fitting service/arrivals does not make the whole simulation observed.
    """
    if fit['kind']=='synthetic' and not accept_synthetic: raise ValueError('Explicit synthetic-fit acceptance required')
    if len(fit['arrival_rates'])!=3: raise ValueError('Three arrival windows required')
    c=replace(config,beta=fit['beta'],tau=fit['tau'],**fit['capacities_max']);c.validate()
    rng=np.random.default_rng(seed);patients=[]
    for (lo,hi),rate in zip(((0,120),(120,240),(240,c.horizon)),fit['arrival_rates']):
        hi=min(hi,c.horizon);t=float(lo)
        if hi<=lo or rate['rate']==0: continue
        while True:
            t+=float(rng.exponential(1/rate['rate']))
            if t>=hi:break
            priority=int(rng.choice(3,p=[.2,.35,.45]));service=fit['service'][str(priority)]
            work=float(rng.gamma(service['shape'],service['scale'])) if service['shape'] else service['mean']
            patients.append(Patient(len(patients),t,priority,work,bool(priority==0 and rng.random()<.5),work))
    return c,patients,dict(fit_kind=fit['kind'],fit_source=fit['source'],remaining_synthetic_assumptions=['priority_proportions','ventilation_probability'],clinical_validation=False)
