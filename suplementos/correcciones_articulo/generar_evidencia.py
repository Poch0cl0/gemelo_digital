"""Run from any directory. Writes only evidencia_adicional, never historical outputs.
Frozen protocol: 4 independent scrambles, nested N=64/128/256, five common seeds.
No clinical data or external validation. Run with Python 3.11 + NumPy/SciPy.
"""
from pathlib import Path
import sys, json, csv, hashlib, platform, time
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import scipy
from scipy import stats
from scipy.stats import qmc

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'gemelo_digital'))
from motor.model import Config, Policy, simulate
from motor.experiment import SCENARIOS
OUT=Path(__file__).resolve().parent/'evidencia_adicional'

def writecsv(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def worker(task):
    kind,payload=task
    if kind=='sobol':
        scramble,matrix,index,scale,beta=payload
        return [dict(scramble=scramble,matrix=matrix,index=index,scale=scale,beta=beta,
                     seed=seed,J=simulate(replace(Config(),service_scale=scale,beta=beta),Policy('priority'),seed)['metrics']['objective'])
                for seed in range(2000,2005)]
    if kind=='policy':
        scene,label,seed=payload
        pol=Policy('aging',aging_interval=float(label.split('_')[1])) if label.startswith('aging_') else Policy(label)
        m=simulate(SCENARIOS[scene],pol,seed)['metrics'];m.pop('runtime_s')
        return [dict(scenario=scene,policy=label,seed=seed,**m)]
    scene,label,seed,old=payload
    m=simulate(SCENARIOS[scene],Policy(label),seed)['metrics'];m.pop('runtime_s')
    differences={k:abs(float(v)-float(old[k])) for k,v in m.items() if v is not None and old.get(k) not in (None,'','None')}
    return [dict(scenario=scene,policy=label,seed=seed,objective=m['objective'],objective_error=differences['objective'],max_metric_error=max(differences.values()))]

def summary(vals):
    x=np.asarray(vals,float);half=float(stats.t.ppf(.975,len(x)-1)*stats.sem(x))
    return dict(n=len(x),mean=float(x.mean()),ci95=[float(x.mean()-half),float(x.mean()+half)])

def indices(a,b,ab):
    center=np.r_[a,b].mean();a=a-center;b=b-center;ab=ab-center
    var=np.var(np.r_[a,b])
    return float(np.mean(b*(ab-a))/var),float(.5*np.mean((a-ab)**2)/var)

def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(date='2026-10-31',registered_before_this_run=True,clinical_validation=False,
        note='Protocol fixed before this supplementary run, after observing original article; not original study preregistration.',
        scrambles=[2026103101,2026103102,2026103103,2026103104],nested_N=[64,128,256],common_seeds=list(range(2000,2005)),
        stability_absolute_tolerance=.03,ci_halfwidth_tolerance=.05,
        criterion='For all four indices: absolute change of across-scramble mean N128 to N256 <=0.03 AND t CI halfwidth across four independent scrambles at N256 <=0.05. Numerical diagnostic only, not mathematical proof.',
        policy_seeds=list(range(3000,3030)),policies=['fifo','priority','aging_30','aging_60','aging_120'],
        policy_analysis='Exploratory fixed-policy comparison; no winner selected as confirmatory. Marginal paired t intervals across 30 common seeds; no claims of clinical fairness thresholds.',
        original_reproduction='450 historical rows, all numerical metrics excluding runtime_s, absolute tolerance 1e-8',
        python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
        model_sha256=hashlib.sha256((ROOT/'gemelo_digital/motor/model.py').read_bytes()).hexdigest())
    (OUT/'protocolo_previo.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    tasks=[]
    old=list(csv.DictReader((ROOT/'gemelo_digital/resultados/evaluacion.csv').open(encoding='utf-8')))
    tasks += [('reproduce',(r['scenario'],r['policy'],int(r['seed']),r)) for r in old]
    tasks += [('policy',(scene,label,seed)) for scene in SCENARIOS for label in protocol['policies'] for seed in protocol['policy_seeds']]
    for scramble in protocol['scrambles']:
        u=qmc.Sobol(d=4,scramble=True,seed=scramble).random_base2(8);a=u[:,:2];b=u[:,2:]
        for label,points in [('A',a),('B',b),('AB0',np.column_stack([b[:,0],a[:,1]])),('AB1',np.column_stack([a[:,0],b[:,1]]))]:
            tasks += [('sobol',(scramble,label,i,float(.8+.4*p[0]),float(.5*p[1]))) for i,p in enumerate(points)]
    groups={k:[] for k in ['sobol','policy','reproduce']};tic=time.perf_counter()
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i,(task,result) in enumerate(zip(tasks,pool.map(worker,tasks,chunksize=8))):
            groups[task[0]].extend(result)
            if (i+1)%256==0: print('Completed',i+1,'/',len(tasks),'tasks; seconds',round(time.perf_counter()-tic),flush=True)
    for k,v in groups.items():writecsv(k+'_ejecuciones.csv',v)
    sob=[]
    for scramble in protocol['scrambles']:
        arrays={label:np.array([np.mean([r['J'] for r in groups['sobol'] if r['scramble']==scramble and r['matrix']==label and r['index']==i]) for i in range(256)]) for label in ['A','B','AB0','AB1']}
        for n in protocol['nested_N']:
            for k,name in enumerate(['service_scale','beta']):
                s,st=indices(arrays['A'][:n],arrays['B'][:n],arrays['AB'+str(k)][:n])
                sob.append(dict(scramble=scramble,N=n,parameter=name,S1=s,ST=st))
    writecsv('sobol_indices_por_scramble.csv',sob)
    stability=[]
    for name in ['service_scale','beta']:
        for metric in ['S1','ST']:
            by={n:summary([r[metric] for r in sob if r['parameter']==name and r['N']==n]) for n in protocol['nested_N']}
            change=abs(by[256]['mean']-by[128]['mean']);half=(by[256]['ci95'][1]-by[256]['ci95'][0])/2
            stability.append(dict(parameter=name,index=metric,by_N=by,change128_256=change,halfwidth256=half,criterion_met=change<=.03 and half<=.05))
    policy=[];contrasts=[]
    for scene in SCENARIOS:
        sub=[r for r in groups['policy'] if r['scenario']==scene]
        for label in protocol['policies']:
            rr=[r for r in sub if r['policy']==label]
            policy.append(dict(scenario=scene,policy=label,metrics={k:summary([r[k] for r in rr]) for k in ['objective','completed','wait_censored','coverage_p0','coverage_p1','coverage_p2','wait_p2']}))
            if label!='priority':
                ref={r['seed']:r for r in sub if r['policy']=='priority'}
                contrasts.append(dict(scenario=scene,policy=label,reference='priority',metrics={k:summary([r[k]-ref[r['seed']][k] for r in rr]) for k in ['objective','completed','coverage_p0','coverage_p1','coverage_p2']}))
    result=dict(protocol=protocol,simulation_counts=dict(sobol=len(groups['sobol']),new_policy=len(groups['policy']),reproduction=len(groups['reproduce'])),
        sobol_stability=stability,all_stability_criteria_met=all(r['criterion_met'] for r in stability),
        policy_summary=policy,paired_policy_contrasts=contrasts,
        reproduction=dict(rows=len(old),max_objective_error=max(r['objective_error'] for r in groups['reproduce']),max_metric_error=max(r['max_metric_error'] for r in groups['reproduce']),tolerance=1e-8),runtime_seconds=time.perf_counter()-tic)
    (OUT/'resultados.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('DONE',result['simulation_counts'],'stability',result['all_stability_criteria_met'],flush=True)

if __name__=='__main__':main()
