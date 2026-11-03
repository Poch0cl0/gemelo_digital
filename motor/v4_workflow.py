"""Reproducible V4 evidence workflow. Existing stage outputs are never overwritten.

Run from gemelo_digital: python -B -m motor.v4_workflow diagnose|pilot|experiment|benchmark
"""
from pathlib import Path
from dataclasses import asdict,replace
import csv,gzip,hashlib,io,json,math,os,platform,statistics,sys,time,tracemalloc,unittest
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy import stats
from scipy.stats import qmc
from .model import Config,Policy,simulate as legacy
from .model_v4 import simulate,Dynamics
from .initial_state import RESOURCES
from .scenario_graph_v4 import ScenarioRequest,configuration,direct,build_graph,source_hashes
from .calibration_v4 import calibrate,validate_holdout,synthetic_dataset

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidencia_v4'
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False)
def csvsave(path,rows):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def manifest(folder):
    target=folder/'manifest.json'
    save(target,{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file() and p!=target})
def baseline_check():
    data=load(OUT/'fase_0/baseline_manifest.json')
    # All historical source/results should remain unchanged: V4 is additive.
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in data['files'].items()}

def tests():
    class Result(unittest.TextTestResult):
        def stopTestRun(self):
            super().stopTestRun()
    modules=['motor.test_model','motor.test_cohort','motor.test_database','motor.test_ui','motor.test_agent','motor.test_exports','motor.test_v4','motor.test_scenario_v4']
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
    bad={getattr(case,'test_case',getattr(case,'_test_case',case)).id() for case,_ in result.failures+result.errors}
    (OUT/'fase_0/tests_final.log').write_text(stream.getvalue(),encoding='utf-8')
    save(OUT/'fase_0/tests_final.json',dict(modules=modules,methods=result.testsRun,successful_methods=result.testsRun-len(bad)-len(result.skipped),failed_method_ids=sorted(bad),failure_records=len(result.failures),error_records=len(result.errors),skipped=len(result.skipped),coverage_measured=False))

def diagnose():
    folder=OUT/'fase_0';folder.mkdir(exist_ok=True,parents=True)
    if (folder/'diagnostics.json').exists():raise FileExistsError('Diagnostics already exist')
    cases=[(Config(),Policy('fifo'),1000),(Config(),Policy(),1000),(Config(demand=2),Policy('tuned',2,60),1001)]
    expected=['3851b91247328a16d94fe7f902b4697607f2beeb58b4adb0a4afb78cc4a5f7ea','be80648ee588bc075ce278264201621e1f0bbe761d4b977e335b51f718402c69','d6bd70e258fb74508a30655a943b6693bc7cc28325a13f792b3728d26a5b6753']
    hashes=[]
    for i,(c,p,seed) in enumerate(cases):
        a=legacy(c,p,seed,trace=True);a['metrics'].pop('runtime_s');b=legacy(c,p,seed,trace=True);b['metrics'].pop('runtime_s')
        raw=json.dumps(a,sort_keys=True).encode()
        with gzip.open(folder/f'case_{i}_current.json.gz','wb') as f:f.write(raw)
        def ints(o):
            if isinstance(o,float) and o.is_integer():return int(o)
            if isinstance(o,list):return [ints(x) for x in o]
            if isinstance(o,dict):return {k:ints(v) for k,v in o.items()}
            return o
        representations={'default':hashlib.sha256(raw).hexdigest(),'compact':hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'integral_floats_to_ints':hashlib.sha256(json.dumps(ints(a),sort_keys=True).encode()).hexdigest()}
        hashes.append(dict(config=asdict(c),policy=asdict(p),seed=seed,expected=expected[i],representations=representations,matches_historical=expected[i] in representations.values(),current_repeat_semantically_equal=a==b,source_original_recovered=False))
    old=list(csv.DictReader((ROOT/'gemelo_digital/resultados/evaluacion.csv').open(encoding='utf-8')))
    queue=[]
    for seed in (1020,1025):
        for policy in ('priority','tuned'):
            r=legacy(Config(demand=2),Policy(policy),seed,trace=True)
            before=max(x['queue'] for x in r['trace'] if x['t']<480);final=r['trace'][-1]['queue']
            historical=int(float(next(row['max_queue'] for row in old if row['scenario']=='demanda_200' and row['policy']==policy and int(row['seed'])==seed)))
            queue.append(dict(seed=seed,policy=policy,historical=historical,max_excluding_H=before,queue_at_H=final,current=r['metrics']['max_queue'],counterfactual_exclusion_matches=before==historical,last_trace_rows=r['trace'][-3:]))
    save(folder/'diagnostics.json',dict(hashes=hashes,max_queue=queue,conclusion='All four historical maxima equal the current trace maximum with H excluded. This demonstrates the terminal-metric counterfactual for these cases, not recovery/identity of historical source. Hash cause remains open.',baseline_preserved=all(baseline_check().values())))
    f1=OUT/'fase_1';f1.mkdir(exist_ok=True)
    train=synthetic_dataset(51001);validation=synthetic_dataset(51002);fit=calibrate(train)
    save(f1/'calibration_inputs.json',dict(calibration=train,validation=validation))
    save(f1/'calibration_results.json',dict(truth=dict(beta=.25,tau=60,arrival_rates=[.8,.3,.1],service_means=[60,30,15]),fit=fit,holdout=validate_holdout(fit,validation),acceptance=dict(service_relative_error_limit=.05,beta_error_limit=1e-8,tau_error_limit=1e-8),external_validation=False))
    print('Diagnostics and synthetic calibration stored',flush=True)

def case(variant,policy,seed,horizon=120,scenario='reference',scale=1.,beta=.25):
    payload=dict(variant='single' if variant=='legacy' else variant,engine='legacy' if variant=='legacy' else 'extended',policy=policy,seeds=[seed],horizon=horizon,scenario=scenario,parameters={'service_scale':float(scale),'beta':float(beta)})
    req=ScenarioRequest.parse(payload);c,p,initial,d=configuration(req)
    return simulate(c,p,seed,mode='legacy') if variant=='legacy' else simulate(c,p,seed,initial=initial,dynamics=d)

def case_metrics(task):
    return case(*task)['metrics']

def pilot():
    folder=OUT/'fase_3';folder.mkdir(exist_ok=True)
    if (folder/'protocol.json').exists():raise FileExistsError('Protocol already fixed')
    variants=['legacy','single','occupied','phases','interruptions','shifts','full']
    runs=[];tracemalloc.start();tic=time.perf_counter()
    for variant in variants:
        start=time.perf_counter();r=case(variant,'priority',40000)
        runs.append(dict(variant=variant,seconds=time.perf_counter()-start,rows=len(r['patients'])))
    seconds=time.perf_counter()-tic;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    # Tracemalloc timing is conservative; no pilot seed is used for inference.
    main_count=7*4*20*2;uncertainty=2*3*2*10;sobol_count=4*64*4*3
    estimated=seconds/7*(main_count+uncertainty+sobol_count)
    pilot_data=dict(runs=runs,total_seconds=seconds,python_peak_allocated_bytes=peak,memory_note='tracemalloc Python allocations, not process peak RSS',estimated_runs=main_count+uncertainty+sobol_count,estimated_seconds_conservative=estimated,storage_budget_bytes=30_000_000,time_budget_seconds=max(1800,estimated*2),no_extraordinary_resources=True)
    save(folder/'pilot.json',pilot_data)
    protocol=dict(version=1,date='2026-10-31',label='new-post-V3-synthetic-exploratory',variants=variants,policies=['fifo','priority','reserve','aging'],scenarios=['reference','demand_150'],seeds=list(range(41000,41020)),horizon=120,main_runs=main_count,uncertainty=dict(load_structures=['staff','resource_peak'],service_scales=[.8,1.,1.2],initial_fatigue=[0.,.5],seeds=list(range(42000,42010)),runs=uncertainty),sobol=dict(scrambles=[53001,53002,53003,53004],nested_N=[32,64],common_seeds=[43000,43001,43002],service_scale=[.8,1.2],beta=[0.,.5],variant='full',runs=sobol_count,stability_change_limit=.03,halfwidth_limit=.05),metrics=['objective','wait_censored','coverage_p0','coverage_p1','coverage_p2','completed','waiting','in_service','abandoned','dead','transferred','util_doctors','util_nurses'],statistical_plan='Paired differences by scenario, variant and common seed; t(19) marginal CI and dz; Holm across all policy-vs-priority contrasts; no clinical/confirmatory claims. Structural and initial-state uncertainty is a factorial scenario analysis, not a calibrated posterior.',source_hashes=source_hashes(),pilot=pilot_data)
    save(folder/'protocol.json',protocol)
    print('Protocol fixed before campaign',pilot_data,flush=True)

def interval(x):
    x=np.asarray(x,float);mean=float(np.mean(x));sd=float(np.std(x,ddof=1));half=float(stats.t.ppf(.975,len(x)-1)*sd/math.sqrt(len(x))) if sd else 0
    return dict(n=len(x),mean=mean,ci95=[mean-half,mean+half],sd=sd)

def experiment():
    import math
    folder=OUT/'fase_3';protocol=load(folder/'protocol.json')
    if (folder/'runs.csv').exists():raise FileExistsError('Never overwrite results')
    assert protocol['source_hashes']==source_hashes(),'Source changed after protocol; require explicit new protocol'
    tic=time.perf_counter();rows=[]
    tasks=[(variant,policy,seed,120,scenario,1.,.25) for scenario in protocol['scenarios'] for variant in protocol['variants'] for policy in protocol['policies'] for seed in protocol['seeds']]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for task,m in zip(tasks,pool.map(case_metrics,tasks,chunksize=8)):
            variant,policy,seed,_,scenario,_,_=task
            rows.append(dict(scenario=scenario,variant=variant,policy=policy,seed=seed,**{k:m.get(k,0 if k in ('abandoned','dead','transferred') else None) for k in protocol['metrics']}))
            if len(rows)%160==0:print('Main runs',len(rows),'/',len(tasks),flush=True)
    csvsave(folder/'runs.csv',rows)
    contrasts=[];summaries=[]
    for scenario in protocol['scenarios']:
        for variant in protocol['variants']:
            base={r['seed']:r for r in rows if r['scenario']==scenario and r['variant']==variant and r['policy']=='priority'}
            for policy in protocol['policies']:
                sub=[r for r in rows if r['scenario']==scenario and r['variant']==variant and r['policy']==policy]
                summaries.append(dict(scenario=scenario,variant=variant,policy=policy,metrics={k:interval([r[k] for r in sub if r[k] is not None]) for k in protocol['metrics'] if all(r[k] is not None for r in sub)}))
                if policy!='priority':
                    delta=np.array([r['objective']-base[r['seed']]['objective'] for r in sub]);sd=float(delta.std(ddof=1))
                    contrasts.append(dict(scenario=scenario,variant=variant,policy=policy,reference='priority',**interval(delta),dz=float(delta.mean()/sd) if sd else None,p=float(stats.ttest_1samp(delta,0).pvalue) if sd else 1.))
    previous=0
    for rank,r in enumerate(sorted(contrasts,key=lambda x:x['p'])):previous=max(previous,(len(contrasts)-rank)*r['p']);r['holm_p']=min(1.,previous)
    # Controlled engine ablations, same policy/scenario/seed; do not attribute full bundle to one component.
    ablations=[]
    for scenario in protocol['scenarios']:
        for variant in protocol['variants'][1:]:
            lookup={(r['variant'],r['seed']):r for r in rows if r['scenario']==scenario and r['policy']=='priority'}
            diff=[lookup[(variant,seed)]['objective']-lookup[('single',seed)]['objective'] for seed in protocol['seeds']]
            ablations.append(dict(scenario=scenario,variant=variant,reference='single',**interval(diff)))
    uncertainty=[]
    for structure in ('staff','resource_peak'):
        for scale in (.8,1.,1.2):
            for fatigue in (0.,.5):
                for seed in range(42000,42010):
                    req=ScenarioRequest.parse(dict(variant='full',parameters={'service_scale':scale},horizon=120))
                    c,p,initial,d=configuration(req);initial=replace(initial,fatigue=fatigue);d=replace(d,load=structure)
                    r=simulate(c,p,seed,initial=initial,dynamics=d)
                    uncertainty.append(dict(structure=structure,scale=scale,initial_fatigue=fatigue,seed=seed,objective=r['metrics']['objective']))
    csvsave(folder/'uncertainty.csv',uncertainty)
    raw=[];indices=[]
    for scramble in protocol['sobol']['scrambles']:
        u=qmc.Sobol(d=4,scramble=True,seed=scramble).random_base2(6);a=u[:,:2];b=u[:,2:]
        arrays={}
        for label,points in [('A',a),('B',b),('AB0',np.column_stack([b[:,0],a[:,1]])),('AB1',np.column_stack([a[:,0],b[:,1]]))]:
            means=[]
            tasks=[('full','priority',seed,120,'reference',float(.8+.4*point[0]),float(.5*point[1])) for point in points for seed in protocol['sobol']['common_seeds']]
            with ProcessPoolExecutor(max_workers=6) as pool:values=list(pool.map(case_metrics,tasks,chunksize=8))
            for i,point in enumerate(points):
                group=values[i*3:(i+1)*3]
                for seed,m in zip(protocol['sobol']['common_seeds'],group):raw.append(dict(scramble=scramble,matrix=label,index=i,scale=.8+.4*point[0],beta=.5*point[1],seed=seed,J=m['objective']))
                means.append(np.mean([m['objective'] for m in group]))
            arrays[label]=np.array(means)
        for n in (32,64):
            fa=arrays['A'][:n];fb=arrays['B'][:n];center=np.r_[fa,fb].mean();variance=np.var(np.r_[fa,fb])
            for k,name in enumerate(('service_scale','beta')):
                ab=arrays['AB'+str(k)][:n]
                indices.append(dict(scramble=scramble,N=n,parameter=name,S1=float(np.mean((fb-center)*(ab-fa))/variance),ST=float(.5*np.mean((fa-ab)**2)/variance)))
        print('Sobol scramble',scramble,'complete',flush=True)
    csvsave(folder/'sobol_runs.csv',raw);csvsave(folder/'sobol_indices.csv',indices)
    stability=[]
    for name in ('service_scale','beta'):
        for metric in ('S1','ST'):
            by={n:interval([r[metric] for r in indices if r['parameter']==name and r['N']==n]) for n in (32,64)}
            change=abs(by[64]['mean']-by[32]['mean']);half=(by[64]['ci95'][1]-by[64]['ci95'][0])/2
            stability.append(dict(parameter=name,index=metric,by_N=by,change=change,halfwidth=half,criterion_met=change<=.03 and half<=.05))
    save(folder/'results.json',dict(counts=dict(main=len(rows),uncertainty=len(uncertainty),sobol=len(raw)),summaries=summaries,paired_policy_contrasts=contrasts,engine_ablations=ablations,sobol_stability=stability,runtime_seconds=time.perf_counter()-tic,clinical_validation=False,protocol_sha256=hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest()))
    figures(folder,rows,stability)
    print('Experiments complete',len(rows)+len(uncertainty)+len(raw),flush=True)

def figures(folder,rows,stability):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['single','occupied','phases','interruptions','shifts','full']
    values=[np.mean([r['objective'] for r in rows if r['variant']==v and r['policy']=='priority' and r['scenario']=='reference']) for v in labels]
    fig,ax=plt.subplots(figsize=(8,4));ax.bar(labels,values);ax.set_ylabel('Mean synthetic J (minutes equivalent)');ax.tick_params(axis='x',rotation=25);fig.tight_layout();fig.savefig(folder/'engine_comparison.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    for r in stability:ax.errorbar([32,64],[r['by_N'][n]['mean'] for n in (32,64)],yerr=[(r['by_N'][n]['ci95'][1]-r['by_N'][n]['ci95'][0])/2 for n in (32,64)],label=r['parameter']+' '+r['index'],marker='o')
    ax.set_xlabel('Nested base N');ax.set_ylabel('Sobol index, t(3) CI');ax.legend();fig.tight_layout();fig.savefig(folder/'sobol_stability.png',dpi=180);plt.close(fig)

def benchmark():
    folder=OUT/'fase_4';folder.mkdir(exist_ok=True)
    valid=[dict(scenario=scenario,policy=policy,horizon=30,seeds=[44000],variant='full') for scenario in ('reference','demand_150') for policy in ('fifo','priority','reserve','aging')]
    invalid=[{'horizon':-1},{'origin':'observed'},{'work_unit':'NHAMCS_LOV'},{'metrics':['survival']},{'policy':'best'},'optimize the hospital',{'parameters':{'beta':2}},{'seeds':[1,1]}, {'parameters':{'service_scale':float('inf')}},{'horizon':True},{'scenario':'missing'},{'extra':'invented'}]
    tasks=[dict(id=i,payload=p,expected='completed' if i<len(valid) else 'abstained') for i,p in enumerate(valid+invalid)]
    # JSON-compliant invalid-domain value; no NaN/Infinity in the protocol artifact.
    tasks[16]['payload']={'parameters':{'service_scale':100}}
    save(folder/'benchmark_protocol.json',dict(tasks=tasks,acceptance='All numeric outputs and evidence IDs equal direct deterministic baseline; all invalid requests abstain; no advantage presumed',real_llm=False,mocks_in_benchmark=False,cost='No paid model calls',retries='Covered separately by injected transient-error tests'))
    graph=build_graph();results=[]
    for task in tasks:
        start=time.perf_counter();a=direct(task['payload']);direct_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter();state=graph.invoke({'payload':task['payload']});graph_ms=(time.perf_counter()-start)*1000;b=state['response']
        equal=(a==b);results.append(dict(id=task['id'],expected=task['expected'],direct_status=a['status'],graph_status=b['status'],exact_numeric_and_evidence_equal=equal,correct_status=b['status']==task['expected'],direct_ms=direct_ms,graph_ms=graph_ms,response=b,steps=state['steps']))
    save(folder/'benchmark_results.json',dict(n=len(results),correct_status=sum(r['correct_status'] for r in results),exact_equal=sum(r['exact_numeric_and_evidence_equal'] for r in results),direct_p50_ms=float(np.median([r['direct_ms'] for r in results])),graph_p50_ms=float(np.median([r['graph_ms'] for r in results])),graph_p95_ms=float(np.quantile([r['graph_ms'] for r in results],.95)),records=results,real_langgraph=True,real_llm=False,clinical_validation=False,cost_usd=0.))
    print('Real local LangGraph benchmark complete',flush=True)

if __name__=='__main__':
    import math,argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['diagnose','pilot','experiment','benchmark','tests'])
    args=parser.parse_args();globals()[args.stage]()
