"""Additional exploratory input-distribution experiment, separately preregistered.

It extends the initial V4 protocol without relabeling existing results.
"""
from dataclasses import replace
from pathlib import Path
import json,hashlib,time
import numpy as np
from .model import generate
from .model_v4 import simulate
from .scenario_graph_v4 import ScenarioRequest,configuration,source_hashes
from .v4_workflow import OUT,save,csvsave,interval

if __name__=='__main__':
    folder=OUT/'fase_3'
    protocol=dict(label='additional-exploratory-input-shape',date='2026-10-31',note='Protocol fixed before these additional runs; main V4 campaign already started. No confirmatory selection.',distributions=['triangular','gamma_matched_moments'],seeds=list(range(45000,45020)),runs=40,horizon=120,variant='full',policy='priority',shared_arrivals=True,gamma_moments=dict(means=[60,30,15],variances=[150,37.5,100/6]),clinical_validation=False,source_hashes=source_hashes())
    save(folder/'distribution_protocol.json',protocol)
    rows=[];tic=time.perf_counter()
    for seed in protocol['seeds']:
        c,p,initial,d=configuration(ScenarioRequest.parse(dict(horizon=120,variant='full')))
        cohort=generate(c,seed);rng=np.random.default_rng(seed+100000)
        gamma=[]
        for patient in cohort:
            mean=[60,30,15][patient.priority];var=[150,37.5,100/6][patient.priority]
            work=float(rng.gamma(mean*mean/var,var/mean))
            gamma.append(replace(patient,service=work,remaining=work))
        for name,patients in [('triangular',cohort),('gamma_matched_moments',gamma)]:
            r=simulate(c,p,seed,patients=patients,initial=initial,dynamics=d)
            rows.append(dict(distribution=name,seed=seed,objective=r['metrics']['objective'],completed=r['metrics']['completed']))
    csvsave(folder/'distribution_runs.csv',rows)
    lookup={(r['distribution'],r['seed']):r['objective'] for r in rows}
    save(folder/'distribution_results.json',dict(runs=len(rows),paired_gamma_minus_triangular=interval([lookup[('gamma_matched_moments',seed)]-lookup[('triangular',seed)] for seed in protocol['seeds']]),seconds=time.perf_counter()-tic,clinical_validation=False))
    print('Additional input-distribution experiment complete',len(rows))
