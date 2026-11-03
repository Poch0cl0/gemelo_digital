"""Executable local LangGraph for structured scenarios, separate from ML chat.

No LLM/provider required. Natural-language interpretation is deliberately absent:
ambiguous prose is refused. Does not claim clinical validity or agent advantage.
"""
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import TypedDict
import hashlib,json,time
from .model import Config,Policy,Patient
from .initial_state import InitialState,InitialPatient,Phase,RESOURCES
from .model_v4 import simulate,Dynamics

METRICS={'objective','wait_censored','started','completed','waiting','in_service','coverage_p0','coverage_p1','coverage_p2','abandoned','dead','transferred','max_queue'}
SCENARIOS={'reference':{},'demand_150':{'demand':1.5},'demand_200':{'demand':2},'staff_reduced':{'doctors':6,'nurses':9},'critical_reduced':{'icu':2,'ventilators':1}}
VARIANTS=('single','occupied','phases','interruptions','shifts','full')

@dataclass(frozen=True)
class ScenarioRequest:
    scenario:str='reference'
    policy:str='priority'
    horizon:int=120
    seeds:tuple=(4100,)
    engine:str='extended'
    variant:str='single'
    parameters:dict=None
    metrics:tuple=('objective','coverage_p0','coverage_p1','coverage_p2')
    work_unit:str='basal_minutes'
    origin:str='synthetic'

    @classmethod
    def parse(cls,payload):
        if isinstance(payload,str):
            try:payload=json.loads(payload)
            except (ValueError,TypeError):raise ValueError('Ambiguous request: provide a structured JSON scenario')
        if not isinstance(payload,dict):raise ValueError('A JSON object is required')
        if set(payload)-set(cls.__dataclass_fields__):raise ValueError('Unknown request field')
        if 'seeds' in payload and not isinstance(payload['seeds'],(list,tuple)):raise ValueError('Seeds must be a list')
        if 'metrics' in payload and not isinstance(payload['metrics'],(list,tuple)):raise ValueError('Metrics must be a list')
        obj=cls(**{**payload,'seeds':tuple(payload.get('seeds',(4100,))),'metrics':tuple(payload.get('metrics',cls.metrics))})
        if obj.scenario not in SCENARIOS or obj.policy not in ('fifo','priority','reserve','aging'):raise ValueError('Unknown scenario/policy')
        if type(obj.horizon) is not int or not 10<=obj.horizon<=480:raise ValueError('Horizon must be 10..480 integer minutes')
        if not 1<=len(obj.seeds)<=5 or any(type(x) is not int or not 0<=x<=2**31-1 for x in obj.seeds) or len(set(obj.seeds))!=len(obj.seeds):raise ValueError('One to five unique integer seeds required')
        if not obj.metrics or any(not isinstance(x,str) or x not in METRICS for x in obj.metrics):raise ValueError('Unknown or clinical metric; only simulation metrics supported')
        if obj.origin!='synthetic':raise ValueError('Observed evidence unavailable: refusing observed-data claim')
        if obj.work_unit!='basal_minutes':raise ValueError('Length of stay/NHAMCS cannot substitute basal work')
        if obj.engine not in ('legacy','extended') or obj.variant not in VARIANTS:raise ValueError('Unknown engine/variant')
        if obj.engine=='legacy' and obj.variant!='single':raise ValueError('Legacy cannot use expanded dynamics')
        params=obj.parameters or {}
        if not isinstance(params,dict) or set(params)-{'beta','service_scale','demand'}:raise ValueError('Unknown parameters')
        c=replace(Config(),horizon=obj.horizon,**SCENARIOS[obj.scenario],**{k:v for k,v in params.items() if k not in SCENARIOS[obj.scenario]})
        # Explicit overrides take precedence over scenario defaults.
        c=replace(c,**params);c.validate()
        if c.service_scale>3 or c.demand>3:raise ValueError('Request exceeds bounded computational domain')
        return obj

def configuration(request):
    c=replace(Config(),**SCENARIOS[request.scenario]);c=replace(c,horizon=request.horizon,**(request.parameters or {}))
    policy={'fifo':Policy('fifo'),'priority':Policy(),'reserve':Policy('tuned',1,60),'aging':Policy('aging',aging_interval=60)}[request.policy]
    variant=request.variant
    cap={r:getattr(c,r) for r in RESOURCES}
    initial=None
    if variant in ('occupied','full'):
        initial=InitialState(cap,(InitialPatient(100000,-20,2,(Phase('residual',30,{'doctors':1,'nurses':1,'beds':1}),),state='active',remaining=20,elapsed=10,first_start=-10,allocations={'doctors':[0],'nurses':[0],'beds':[0]}),),.35)
    calendar=() if variant not in ('shifts','full') else ((c.horizon/3,{**cap,'doctors':max(1,c.doctors-2)}),(2*c.horizon/3,cap))
    dynamics=Dynamics(phase_fractions=(.3,.7) if variant in ('phases','full') else (1.,),preemption='immediate' if variant in ('interruptions','full') else 'none',calendar=calendar,deterioration=.001 if variant=='full' else 0,abandonment=.001 if variant=='full' else 0,death=.0002 if variant=='full' else 0,transfer=.0005 if variant=='full' else 0)
    return c,policy,initial,dynamics

def source_hashes():
    folder=Path(__file__).parent
    return {name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('model.py','model_v4.py','initial_state.py','scenario_graph_v4.py')}

def execute(request,cache=None,runner=simulate):
    provenance=json.loads(json.dumps(dict(request=asdict(request),sources=source_hashes(),clinical_validation=False)))
    ident=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    path=Path(cache)/(ident+'.json') if cache else None
    if path and path.exists():
        payload=json.loads(path.read_text(encoding='utf-8'));saved_hash=payload.pop('content_sha256')
        if hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()!=saved_hash:raise ValueError('Corrupt evidence cache')
        if payload['provenance']!=json.loads(json.dumps(provenance)):raise ValueError('Cached provenance mismatch')
        return payload
    c,p,initial,d=configuration(request);runs=[]
    for seed in request.seeds:
        result=runner(c,p,seed,mode='legacy') if request.engine=='legacy' else runner(c,p,seed,initial=initial,dynamics=d)
        runs.append(dict(seed=seed,metrics={k:result['metrics'][k] for k in request.metrics}))
    means={k:sum(row['metrics'][k] for row in runs)/len(runs) if all(row['metrics'][k] is not None for row in runs) else None for k in request.metrics}
    payload=dict(status='completed',evidence_id=ident,provenance=provenance,runs=runs,means=means,explanation='Synthetic simulation results; coverage is initiation, not survival. Numeric claims are exactly the means linked to the evidence ID.')
    if path:
        path.parent.mkdir(parents=True,exist_ok=True)
        stored={**payload,'content_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}
        path.write_text(json.dumps(stored,indent=2),encoding='utf-8')
    return payload

def direct(payload,cache=None,runner=simulate):
    try:return execute(ScenarioRequest.parse(payload),cache,runner)
    except (ValueError,TypeError,KeyError,RuntimeError) as exc:return dict(status='abstained',error=str(exc),clinical_validation=False)

class GraphState(TypedDict,total=False):
    payload:dict
    request:ScenarioRequest
    response:dict
    steps:list
    attempts:int

def build_graph(cache=None,runner=simulate):
    from langgraph.graph import StateGraph,START,END
    def normalize(state):
        try:return dict(request=ScenarioRequest.parse(state['payload']),steps=['normalize','validate','select_scenario','select_policy'])
        except (ValueError,TypeError,KeyError) as exc:return dict(response=dict(status='abstained',error=str(exc),clinical_validation=False),steps=['normalize','reject'])
    def run(state):
        # Bounded single retry on a declared transient tool error, no invented fallback.
        attempts=0
        while attempts<2:
            attempts+=1
            try:return dict(response=execute(state['request'],cache,runner),attempts=attempts,steps=state['steps']+['execute_or_retrieve','deterministic_metrics'])
            except RuntimeError as exc:
                if attempts==2:return dict(response=dict(status='failed',error=str(exc),clinical_validation=False),attempts=attempts,steps=state['steps']+['tool_failed'])
            except (ValueError,TypeError,KeyError) as exc:return dict(response=dict(status='failed',error=str(exc),clinical_validation=False),attempts=attempts,steps=state['steps']+['tool_failed'])
    def evidence(state):return dict(steps=state['steps']+['prepare_evidence','explain','record_provenance'])
    graph=StateGraph(GraphState);graph.add_node('normalize_validate',normalize);graph.add_node('run',run);graph.add_node('evidence',evidence)
    graph.add_edge(START,'normalize_validate');graph.add_conditional_edges('normalize_validate',lambda state:'stop' if 'response' in state else 'run',{'stop':END,'run':'run'})
    graph.add_edge('run','evidence');graph.add_edge('evidence',END)
    return graph.compile()

def answer_scenario(payload,cache=None):
    """Public integration point; existing agent.answer for ML remains unchanged."""
    return build_graph(cache).invoke({'payload':payload})

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('request',help='Structured JSON object');parser.add_argument('--cache')
    args=parser.parse_args();print(json.dumps(answer_scenario(args.request,args.cache),default=lambda o:asdict(o),indent=2))
