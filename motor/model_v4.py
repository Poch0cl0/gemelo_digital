"""Opt-in synthetic phase engine. Legacy mode delegates to the unchanged V3 source.

Capacity drops forcibly pause nonfitting episodes, even noninterruptible phases;
this is a declared structural scenario, not a clinically validated rule.
"""
from dataclasses import dataclass, asdict
import copy, hashlib, json, math, random
from .model import Config, Policy, generate, simulate as legacy_simulate
from .initial_state import InitialState, Phase, RESOURCES, capacities, number

@dataclass(frozen=True)
class Dynamics:
    phase_fractions: tuple = (1.0,)
    preemption: str = 'none'  # none, immediate, boundary
    calendar: tuple = ()  # (time, full capacities)
    deterioration: float = 0
    abandonment: float = 0
    death: float = 0
    transfer: float = 0
    load: str = 'staff'  # staff or resource_peak structural alternative
    parameter_origin: str = 'synthetic'

    def validate(self,c):
        if not self.phase_fractions or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in self.phase_fractions) or abs(sum(self.phase_fractions)-1)>1e-9: raise ValueError('Phase fractions must sum to one')
        if self.preemption not in ('none','immediate','boundary'): raise ValueError('Invalid preemption')
        if self.load not in ('staff','resource_peak'): raise ValueError('Unknown load structure')
        if self.parameter_origin not in ('synthetic','estimated','observed'): raise ValueError('Parameter provenance required')
        for key in ('deterioration','abandonment','death','transfer'): number(getattr(self,key),key)
        previous=-1
        for t,cap in self.calendar:
            number(t,'calendar time'); capacities(cap)
            if t<=previous or t>c.horizon: raise ValueError('Calendar must be strictly increasing within horizon')
            previous=t

def phase_plan(p,fractions):
    resources={'doctors':1,'nurses':1,'icu' if p.priority==0 else 'beds':1}
    if p.ventilation: resources['ventilators']=1
    # Abstract final phase releases the nurse when multiple phases are enabled.
    return tuple(Phase(f'phase_{i}',p.service*f,{k:v for k,v in resources.items() if not (len(fractions)>1 and i==len(fractions)-1 and k=='nurses')}) for i,f in enumerate(fractions))

def simulate(c=Config(),policy=Policy(),seed=0,patients=None,trace=False,*,initial=None,dynamics=None,mode='extended',checkpoint=None,stop_at=None):
    if mode=='legacy':
        if initial is not None or dynamics is not None or checkpoint is not None or stop_at is not None: raise ValueError('Legacy mode does not accept extensions')
        return legacy_simulate(c,policy,seed,patients,trace)
    if mode!='extended': raise ValueError('Unknown engine mode')
    c.validate();policy.validate();d=dynamics or Dynamics();d.validate(c)
    if type(seed) is not int: raise ValueError('Integer seed required')
    signature=hashlib.sha256(json.dumps(dict(config=asdict(c),policy=asdict(policy),dynamics=asdict(d),seed=seed),sort_keys=True).encode()).hexdigest()
    if checkpoint is not None:
        if initial is not None or patients is not None: raise ValueError('Checkpoint cannot be mixed with fresh inputs')
        if checkpoint.get('signature')!=signature: raise ValueError('Checkpoint configuration mismatch')
        state=copy.deepcopy(checkpoint['state'])
    else:
        cap={r:getattr(c,r) for r in RESOURCES}
        init=initial or InitialState(cap)
        if isinstance(init,dict):init=InitialState.from_dict(init)
        init.validate()
        if init.capacity!=cap: raise ValueError('Config and initial capacities disagree')
        source=generate(c,seed) if patients is None else patients
        # Use the legacy input validator without running the legacy simulation.
        seen={p.id for p in init.patients};ps=[]
        for p in init.patients:
            ps.append(dict(id=p.id,arrival=p.arrival,priority=p.priority,original_priority=p.priority,phases=[asdict(x) for x in p.phases],phase=p.phase_index,remaining=p.remaining,state=p.state,first_start=p.first_start,finish=None,allocations=copy.deepcopy(p.allocations),elapsed=p.elapsed,wait_queue=max(0,(p.first_start if p.first_start is not None else 0)-p.arrival),source=p.source,provenance=p.provenance))
        for p in source:
            if type(p.id) is not int or p.id<0 or p.id in seen: raise ValueError('Invalid or duplicate future id')
            seen.add(p.id)
            if type(p.priority) is not int or p.priority not in (0,1,2) or type(p.ventilation) is not bool or (p.ventilation and p.priority!=0): raise ValueError('Invalid future patient')
            number(p.arrival,'arrival');number(p.service,'service',1e-12)
            if p.arrival>=c.horizon: raise ValueError('Arrival outside horizon')
            phases=phase_plan(p,d.phase_fractions)
            ps.append(dict(id=p.id,arrival=p.arrival,priority=p.priority,original_priority=p.priority,phases=[asdict(x) for x in phases],phase=0,remaining=phases[0].work,state='future',first_start=None,finish=None,allocations={},elapsed=0,wait_queue=0,source='synthetic-generator' if patients is None else 'explicit-cohort',provenance={'record':'synthetic','work':'synthetic'}))
        state=dict(t=0.,fatigue=init.fatigue,patients=ps,events=[],trace=[],areas={r:0. for r in RESOURCES},capacity_areas={r:0. for r in RESOURCES},fatigue_area=0.,max_queue=0,calendar_index=0)
    if stop_at is not None:
        number(stop_at,'stop_at')
        if not state['t']<=stop_at<=c.horizon or abs(stop_at/c.dt-round(stop_at/c.dt))>1e-9: raise ValueError('stop_at must be a future grid time')
    ps=state['patients']
    def event(p,kind,t,**extra):state['events'].append(dict(t=t,id=p['id'],type=kind,**extra))
    def release(p):p['allocations']={}
    def req(p):return p['phases'][p['phase']]['resources']
    def key(p,t):
        rank=p['priority']
        if policy.name=='aging':rank=max(0,rank-math.floor((t-p['arrival'])/policy.aging_interval))
        return (p['arrival'],p['id']) if policy.name=='fifo' else (rank,p['arrival'],p['id'])
    def uniform(p,t,label):
        # Counter-derived streams: event draws do not depend on policy iteration order.
        raw=hashlib.sha256(f'{seed}:{p["id"]}:{t:.12g}:{label}'.encode()).digest()
        return (int.from_bytes(raw[:8],'big')+.5)/2**64
    def cap_at(t):
        cap={r:getattr(c,r) for r in RESOURCES}
        for at,values in d.calendar:
            if at<=t:cap=dict(values)
        return cap
    while state['t']<=c.horizon:
        t=state['t']
        # Checkpoints are before processing t: resume processes that instant exactly once.
        if stop_at is not None and t>=stop_at and t<c.horizon:break
        cap=cap_at(t)
        for p in ps:
            if p['state']=='active' and p['remaining']<=1e-9:
                release(p);event(p,'phase_completed',t,phase=p['phase'])
                p['phase']+=1
                if p['phase']==len(p['phases']):p.update(state='completed',finish=t);event(p,'completed',t)
                else:p.update(state='waiting',remaining=p['phases'][p['phase']]['work'])
            if p['state']=='future' and p['arrival']<=t:p['state']='waiting';event(p,'arrived',t)
        # Retain higher-ranked active episodes if a shift removes assigned identities.
        used={r:set() for r in RESOURCES}
        for p in sorted((p for p in ps if p['state']=='active'),key=lambda p:key(p,t)):
            if any(any(i>=cap[r] or i in used[r] for i in p['allocations'].get(r,[])) for r in RESOURCES):
                p['state']='waiting';release(p);event(p,'capacity_pause',t)
            else:
                for r in RESOURCES:used[r].update(p['allocations'].get(r,[]))
        def free():return {r:sorted(set(range(cap[r]))-set(i for p in ps if p['state']=='active' for i in p['allocations'].get(r,[]))) for r in RESOURCES}
        def feasible(p,f):
            if any(len(f[r])<n for r,n in req(p).items()):return False
            if policy.name=='tuned' and t<policy.release and p['priority']>0 and len(f['icu'])>0:
                return min(len(f['doctors'])-req(p).get('doctors',0),len(f['nurses'])-req(p).get('nurses',0))>=policy.reserve
            return True
        if t<c.horizon:
            for p in sorted((p for p in ps if p['state']=='waiting'),key=lambda p:key(p,t)):
                f=free()
                if not feasible(p,f) and d.preemption=='immediate':
                    victims=sorted((v for v in ps if v['state']=='active' and key(p,t)<key(v,t) and v['phases'][v['phase']]['interruptible']),key=lambda v:key(v,t),reverse=True)
                    # Only commit interruptions if the complete candidate can be admitted.
                    chosen=[];potential=copy.deepcopy(f)
                    for v in victims:
                        chosen.append(v)
                        for r,ids in v['allocations'].items():potential[r]=sorted(potential[r]+ids)
                        if feasible(p,potential):break
                    if feasible(p,potential):
                        for v in chosen:v['state']='waiting';release(v);event(v,'preempted',t,by=p['id'])
                        f=free()
                if feasible(p,f):
                    p['allocations']={r:f[r][:n] for r,n in req(p).items() if n}
                    p['state']='active'
                    if p['first_start'] is None:p['first_start']=t
                    event(p,'started_or_resumed',t,phase=p['phase'])
        counts={name:sum(p['state']==name for p in ps) for name in ('future','waiting','active','completed','abandoned','dead','transferred')}
        assert sum(counts.values())==len(ps)
        usage={r:sum(len(p['allocations'].get(r,[])) for p in ps) for r in RESOURCES}
        for r in RESOURCES:
            ids=[i for p in ps for i in p['allocations'].get(r,[])]
            assert len(ids)==len(set(ids)) and usage[r]<=cap[r]
        assert all(p['remaining']>=-1e-9 for p in ps) and 0<=state['fatigue']<=1
        state['max_queue']=max(state['max_queue'],counts['waiting'])
        if trace:state['trace'].append(dict(t=t,fatigue=state['fatigue'],**counts,**usage))
        if t>=c.horizon:break
        next_grid=min(c.horizon,(math.floor((t+1e-10)/c.dt)+1)*c.dt)
        changes=[at for at,_ in d.calendar if at>t]
        nxt=min([next_grid]+changes);h=nxt-t
        load=max(usage['doctors']/cap['doctors'] if cap['doctors'] else 0,usage['nurses']/cap['nurses'] if cap['nurses'] else 0)
        if d.load=='resource_peak':load=max([load]+[usage[r]/cap[r] if cap[r] else 0 for r in RESOURCES])
        # Same Euler relaxation/speed as V3, phase-specific actual staff utilization.
        speed=1-c.beta*state['fatigue']
        for p in ps:
            if p['state']=='active':p['remaining']=max(0.,p['remaining']-speed*h);p['elapsed']+=h
            elif p['state']=='waiting':p['wait_queue']+=h
        state['fatigue_area']+=state['fatigue']*h
        state['fatigue']+=h*(load-state['fatigue'])/c.tau
        for r in RESOURCES:state['areas'][r]+=usage[r]*h;state['capacity_areas'][r]+=cap[r]*h
        for p in ps:
            if p['state'] not in ('waiting','active'):continue
            risks=[('abandoned',d.abandonment if p['state']=='waiting' else 0),('dead',d.death),('transferred',d.transfer)]
            total=sum(rate for _,rate in risks)
            if total and uniform(p,t,'exit')< -math.expm1(-total*h):
                choice=uniform(p,t,'cause')*total
                for outcome,rate in risks:
                    choice-=rate
                    if choice<0:p.update(state=outcome,finish=nxt);release(p);event(p,outcome,nxt);break
            elif p['priority']>0 and d.deterioration and uniform(p,t,'deterioration')< -math.expm1(-d.deterioration*h):
                p['priority']-=1;event(p,'deteriorated',nxt)
        state['t']=nxt
    end=state['t'];arrived=[p for p in ps if p['state']!='future']
    def wait(p):return (p['first_start'] if p['first_start'] is not None else min(end,p['finish'] if p['finish'] is not None else end))-p['arrival']
    weights=sum(c.priority_weights[p['original_priority']] for p in arrived)
    metrics=dict(arrivals=len(arrived),started=sum(p['first_start'] is not None for p in arrived),completed=sum(p['state']=='completed' for p in arrived),waiting=sum(p['state']=='waiting' for p in arrived),in_service=sum(p['state']=='active' for p in arrived),max_queue=state['max_queue'],fatigue_mean=state['fatigue_area']/end if end else 0,wait_censored=sum(wait(p) for p in arrived)/len(arrived) if arrived else None,objective=sum(c.priority_weights[p['original_priority']]*(wait(p)+c.unfinished_penalty*(p['state']!='completed')) for p in arrived)/weights if weights else 0)
    for terminal in ('abandoned','dead','transferred'):metrics[terminal]=sum(p['state']==terminal for p in arrived)
    for k in range(3):
        group=[p for p in arrived if p['original_priority']==k]
        metrics[f'coverage_p{k}']=sum(p['first_start'] is not None for p in group)/len(group) if group else None
        metrics[f'wait_p{k}']=sum(wait(p) for p in group)/len(group) if group else None
    for r in RESOURCES:metrics['util_'+r]=state['areas'][r]/state['capacity_areas'][r] if state['capacity_areas'][r] else None
    return dict(metrics=metrics,patients=copy.deepcopy(ps),trace=copy.deepcopy(state['trace']),events=copy.deepcopy(state['events']),checkpoint=dict(version=1,signature=signature,state=copy.deepcopy(state)),metadata=dict(engine='v4-phases-1',origin=d.parameter_origin,clinical_validation=False,preemption=d.preemption,capacity_drop='pause_and_release',load=d.load,metric_note='J penalizes every non-completed outcome; wait stops at exit for unstarted patients'))
