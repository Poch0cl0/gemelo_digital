"""Reanalysis of synthetic data; no clinical validation. Run from gemelo_digital."""
from pathlib import Path
from dataclasses import replace
import csv,json,hashlib,sys,time
import numpy as np
import scipy
from scipy import stats
from scipy.stats import qmc
from .model import Config,Policy,simulate

OUT=Path(__file__).resolve().parents[1]/'resultados'/'revision_manuscrito'
OUT.mkdir(exist_ok=True)
DATA=OUT.parent/'evaluacion.csv'
rng=np.random.default_rng(20261024)
rows=list(csv.DictReader(DATA.open(encoding='utf-8')))
formal=[]
for name in dict.fromkeys(r['scenario'] for r in rows):
 a={int(r['seed']):float(r['objective']) for r in rows if r['scenario']==name and r['policy']=='tuned'}
 b={int(r['seed']):float(r['objective']) for r in rows if r['scenario']==name and r['policy']=='fifo'}
 assert a.keys()==b.keys() and len(a)==30
 d=np.array([a[k]-b[k] for k in sorted(a)])
 sh=stats.shapiro(d);t=stats.ttest_1samp(d,0)
 boot=d[rng.integers(0,len(d),(20000,len(d)))]
 dz=boot.mean(axis=1)/boot.std(axis=1,ddof=1)
 ci=stats.t.interval(.95,29,loc=d.mean(),scale=stats.sem(d))
 formal.append(dict(scenario=name,n=30,shapiro_p=float(sh.pvalue),test='paired t, two-sided',t=float(t.statistic),df=29,p=float(t.pvalue),mean=float(d.mean()),ci=list(ci),dz=float(d.mean()/d.std(ddof=1)),dz_ci=np.quantile(dz,[.025,.975]).tolist(),bootstrap_mean_ci=np.quantile(boot.mean(axis=1),[.025,.975]).tolist(),wilcoxon_p=float(stats.wilcoxon(d,method='auto').pvalue)))
order=np.argsort([x['p'] for x in formal]);prev=0
for rank,index in enumerate(order):
 prev=max(prev,(len(formal)-rank)*formal[index]['p']);formal[index]['holm_p']=min(1,prev)
print('Formal analysis complete',flush=True)
interaction=[]
for scale in [.8,1.,1.2]:
 for beta in [0.,.25,.5]:
  vals=[]
  for seed in range(1000,1030):
   j=simulate(replace(Config(),service_scale=scale,beta=beta),Policy('priority'),seed)['metrics']['objective']
   interaction.append(dict(service_scale=scale,beta=beta,seed=seed,J=j));vals.append(j)
  print('Interaction',scale,beta,round(np.mean(vals),3),flush=True)
def ci(vals):
 a=np.asarray(vals);z=stats.t.interval(.95,len(a)-1,loc=a.mean(),scale=stats.sem(a));return dict(mean=float(a.mean()),ci=list(z))
cells=[dict(service_scale=s,beta=b,**ci([r['J'] for r in interaction if r['service_scale']==s and r['beta']==b])) for s in [.8,1.,1.2] for b in [0.,.25,.5]]
lookup={(r['service_scale'],r['beta'],r['seed']):r['J'] for r in interaction}
contrasts=[lookup[(1.2,.5,k)]-lookup[(1.2,0.,k)]-lookup[(.8,.5,k)]+lookup[(.8,0.,k)] for k in range(1000,1030)]
inter_contrast=ci(contrasts)
with (OUT/'interacciones.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=interaction[0]);w.writeheader();w.writerows(interaction)
# Exploratory Sobol analysis of mean J across five fixed common seeds.
# Independent uniform service_scale [0.8,1.2], beta [0,0.5].
# N=64, two inputs => N*(D+2)*5 = 1280 simulations.
u=qmc.Sobol(d=4,scramble=True,seed=20261024).random_base2(6)
A=u[:,:2];B=u[:,2:];raw=[]
def evaluate(points,label):
 values=[]
 for i,point in enumerate(points):
  scale=.8+.4*point[0];beta=.5*point[1];vals=[]
  for seed in range(2000,2005):
   j=simulate(replace(Config(),service_scale=float(scale),beta=float(beta)),Policy('priority'),seed)['metrics']['objective']
   vals.append(j);raw.append(dict(matrix=label,index=i,service_scale=float(scale),beta=float(beta),seed=seed,J=j))
  values.append(np.mean(vals))
 print('Sobol matrix',label,'complete',flush=True)
 return np.array(values)
fa=evaluate(A,'A');fb=evaluate(B,'B');fab=[]
for k in range(2):
 ab=A.copy();ab[:,k]=B[:,k];fab.append(evaluate(ab,'AB'+str(k)))
def indices(a,b,ab):
 center=np.mean(np.r_[a,b]);a=a-center;b=b-center;ab=ab-center
 v=np.var(np.r_[a,b],ddof=0)
 return float(np.mean(b*(ab-a))/v),float(.5*np.mean((a-ab)**2)/v)
sobol=[]
for k,name in enumerate(['service_scale','beta']):
 s,st=indices(fa,fb,fab[k]);boots=[]
 for _ in range(2000):
  ix=rng.integers(0,64,64);boots.append(indices(fa[ix],fb[ix],fab[k][ix]))
 bounds=np.quantile(boots,[.025,.975],axis=0)
 sobol.append(dict(parameter=name,S1=s,ST=st,S1_ci=bounds[:,0].tolist(),ST_ci=bounds[:,1].tolist(),half_sample=indices(fa[:32],fb[:32],fab[k][:32])))
with (OUT/'sobol_ejecuciones.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=raw[0]);w.writeheader();w.writerows(raw)
result=dict(formal=formal,interaction_cells=cells,interaction_contrast=inter_contrast,sobol=sobol,additional_runs=1550,interaction_runs=270,sobol_runs=1280,bootstrap_seed=20261024,bootstrap_replicates=20000,sobol_bootstrap_replicates=2000,python=sys.version,numpy=np.__version__,scipy=scipy.__version__,evaluation_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),model_sha256=hashlib.sha256((Path(__file__).parent/'model.py').read_bytes()).hexdigest())
(OUT/'analisis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('ALL DONE',flush=True)
