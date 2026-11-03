"""Independent read-only checks of V4 CSVs and statistics. Writes a new check file."""
from pathlib import Path
import csv,json,hashlib
from collections import Counter
import numpy as np
from scipy import stats

ROOT=Path(__file__).resolve().parents[2]
def read(name):
    with (ROOT/'evidencia_v4/fase_3'/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))

def verify():
    folder=ROOT/'evidencia_v4/fase_3';result=json.loads((folder/'results.json').read_text());protocol=json.loads((folder/'protocol.json').read_text())
    runs=read('runs.csv');uncertainty=read('uncertainty.csv');sobol=read('sobol_runs.csv');distribution=read('distribution_runs.csv')
    assert [len(runs),len(uncertainty),len(sobol),len(distribution)]==[1120,120,3072,40]
    assert len({(r['scenario'],r['variant'],r['policy'],r['seed']) for r in runs})==1120
    assert len({(r['scramble'],r['matrix'],r['index'],r['seed']) for r in sobol})==3072
    assert len({(r['structure'],r['scale'],r['initial_fatigue'],r['seed']) for r in uncertainty})==120
    assert len({(r['distribution'],r['seed']) for r in distribution})==40
    assert {int(r['seed']) for r in runs}==set(range(41000,41020))
    lookup={(r['scenario'],r['variant'],r['policy'],r['seed']):r for r in runs}
    compatibility=[]
    for scenario in protocol['scenarios']:
        for policy in protocol['policies']:
            for seed in protocol['seeds']:
                a=lookup[(scenario,'legacy',policy,str(seed))];b=lookup[(scenario,'single',policy,str(seed))]
                compatibility.append(abs(float(a['objective'])-float(b['objective'])))
    assert max(compatibility)<1e-8
    max_mean_error=0.
    for summary in result['summaries']:
        group=[r for r in runs if all(r[k]==summary[k] for k in ('scenario','variant','policy'))]
        assert len(group)==20
        for metric,statistic in summary['metrics'].items():
            vals=np.array([float(r[metric]) for r in group]);max_mean_error=max(max_mean_error,abs(float(vals.mean())-statistic['mean']))
            half=float(stats.t.ppf(.975,19)*stats.sem(vals)) if vals.std(ddof=1) else 0
            assert abs(statistic['ci95'][0]-(vals.mean()-half))<1e-8
    assert max_mean_error<1e-8
    estimates=read('sobol_indices.csv');max_index_error=0.
    for scramble in protocol['sobol']['scrambles']:
        arrays={label:np.array([np.mean([float(r['J']) for r in sobol if int(r['scramble'])==scramble and r['matrix']==label and int(r['index'])==i]) for i in range(64)]) for label in ('A','B','AB0','AB1')}
        for n in (32,64):
            a=arrays['A'][:n];b=arrays['B'][:n];center=np.r_[a,b].mean();var=np.var(np.r_[a,b])
            for k,name in enumerate(('service_scale','beta')):
                ab=arrays['AB'+str(k)][:n]
                expected=next(r for r in estimates if int(r['scramble'])==scramble and int(r['N'])==n and r['parameter']==name)
                for index,value in [('S1',np.mean((b-center)*(ab-a))/var),('ST',.5*np.mean((a-ab)**2)/var)]:max_index_error=max(max_index_error,abs(float(value)-float(expected[index])))
    assert max_index_error<1e-8
    baseline=json.loads((ROOT/'evidencia_v4/fase_0/baseline_manifest.json').read_text(encoding='utf-8'))
    preserved={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in baseline['files'].items()}
    assert all(preserved.values())
    output=dict(counts=[len(runs),len(uncertainty),len(sobol),len(distribution)],unique_keys=True,max_legacy_vs_single_J_error=max(compatibility),max_summary_error=max_mean_error,max_sobol_index_error=max_index_error,all_baseline_preserved=True,checked_baseline_files=len(preserved),new_sobol_criteria_passed=sum(r['criterion_met'] for r in result['sobol_stability']),note='Independent recomputation; no simulations. Checks do not certify external hospital validity or universal Sobol convergence.')
    with (folder/'independent_verification.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2)
    print(output)

if __name__=='__main__':verify()
