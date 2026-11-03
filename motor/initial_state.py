"""Versioned operational inputs. Unknown work is rejected, never imputed."""
from dataclasses import dataclass, field, asdict
import math

RESOURCES = ('doctors', 'nurses', 'beds', 'icu', 'ventilators')
ORIGINS = {'observed', 'estimated', 'synthetic', 'unknown'}

def number(value, name, minimum=0):
    if type(value) not in (float, int) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'{name}: finite number >= {minimum} required')
    return value

def capacities(value):
    if not isinstance(value, dict) or set(value) != set(RESOURCES):
        raise ValueError('All five resource capacities required')
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError('Capacities must be nonnegative integers')
    return dict(value)

@dataclass(frozen=True)
class Phase:
    name: str
    work: float
    resources: dict
    interruptible: bool = True

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip(): raise ValueError('Phase name required')
        number(self.work, 'phase work', 1e-12)
        if type(self.interruptible) is not bool: raise ValueError('interruptible must be boolean')
        if not isinstance(self.resources, dict) or set(self.resources)-set(RESOURCES): raise ValueError('Unknown resource')
        if any(type(n) is not int or n < 0 for n in self.resources.values()): raise ValueError('Invalid requirement')

@dataclass(frozen=True)
class InitialPatient:
    id: int
    arrival: float
    priority: int
    phases: tuple[Phase, ...]
    state: str = 'waiting'
    phase_index: int = 0
    remaining: float | None = None
    elapsed: float = 0
    first_start: float | None = None
    allocations: dict = field(default_factory=dict)
    source: str = 'synthetic-fixture'
    provenance: dict = field(default_factory=lambda: {'record': 'synthetic', 'work': 'synthetic'})

    def validate(self):
        if type(self.id) is not int or self.id < 0: raise ValueError('Invalid id')
        if type(self.priority) is not int or self.priority not in (0,1,2): raise ValueError('Invalid priority')
        if type(self.arrival) not in (float,int) or not math.isfinite(self.arrival) or self.arrival > 0: raise ValueError('Initial arrival must be <=0')
        number(self.elapsed,'elapsed')
        if self.state not in ('waiting','active'): raise ValueError('Invalid initial state')
        if not self.phases or type(self.phase_index) is not int or not 0 <= self.phase_index < len(self.phases): raise ValueError('Invalid phase index')
        for p in self.phases: p.validate()
        number(self.remaining,'remaining')
        if self.remaining > self.phases[self.phase_index].work: raise ValueError('Residual exceeds phase work')
        if not isinstance(self.source,str) or not self.source.strip(): raise ValueError('Source required')
        if not isinstance(self.provenance,dict) or not {'record','work'}<=set(self.provenance): raise ValueError('Provenance required')
        if any(v not in ORIGINS for v in self.provenance.values()): raise ValueError('Invalid provenance')
        if self.provenance['work']=='unknown': raise ValueError('Unknown work cannot be simulated')
        if self.first_start is not None and (type(self.first_start) not in (float,int) or not math.isfinite(self.first_start) or not self.arrival <= self.first_start <= 0): raise ValueError('Invalid first_start')
        if self.state=='active' and self.first_start is None: raise ValueError('Active patient requires first_start')
        if self.elapsed > -self.arrival: raise ValueError('Elapsed exceeds time since arrival')
        if self.state=='active' and self.elapsed > -self.first_start: raise ValueError('Elapsed exceeds time since start')
        if self.state=='waiting' and self.allocations: raise ValueError('Waiting patient holds resources')

@dataclass(frozen=True)
class InitialState:
    capacity: dict
    patients: tuple[InitialPatient, ...] = ()
    fatigue: float = 0
    source: str = 'synthetic-fixture'
    fatigue_origin: str = 'synthetic'
    version: int = 1

    def validate(self):
        capacities(self.capacity)
        if type(self.version) is not int or self.version!=1: raise ValueError('Initial schema version must be 1')
        number(self.fatigue,'fatigue')
        if self.fatigue>1 or self.fatigue_origin not in ORIGINS-{'unknown'}: raise ValueError('Fatigue must be known in [0,1]')
        if not isinstance(self.source,str) or not self.source.strip(): raise ValueError('State source required')
        ids=set();used={r:set() for r in RESOURCES}
        for p in self.patients:
            p.validate()
            if p.id in ids: raise ValueError('Duplicate patient')
            ids.add(p.id)
            if not isinstance(p.allocations,dict) or set(p.allocations)-set(RESOURCES): raise ValueError('Invalid allocations')
            if p.state=='active':
                req=p.phases[p.phase_index].resources
                for r in RESOURCES:
                    values=p.allocations.get(r,[])
                    if not isinstance(values,(list,tuple)) or len(values)!=req.get(r,0): raise ValueError('Allocation does not match phase')
                    for i in values:
                        if type(i) is not int or not 0<=i<self.capacity[r] or i in used[r]: raise ValueError('Duplicate or unavailable resource')
                        used[r].add(i)
        return self

    def availability(self):
        self.validate()
        return {r:self.capacity[r]-sum(len(p.allocations.get(r,())) for p in self.patients) for r in RESOURCES}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data,dict) or set(data)-{'version','capacity','patients','fatigue','source','fatigue_origin'}: raise ValueError('Unknown initial-state fields')
        rows=[]
        for row in data.get('patients',[]):
            row=dict(row); row['phases']=tuple(Phase(**p) for p in row['phases'])
            rows.append(InitialPatient(**row))
        return cls(**{**data,'patients':tuple(rows)}).validate()

def from_operational(records, capacity, work_by_id, fatigue, fatigue_origin, source):
    """Explicit enrichment: work/phases/allocations cannot be inferred from SQL status."""
    patients=[]
    for row in records:
        key=row['id']
        if key not in work_by_id: raise ValueError(f'Missing explicit work enrichment for {key}')
        extra=dict(work_by_id[key])
        patients.append(InitialPatient(id=key,arrival=row['arrival_relative_minutes'],priority=row['priority'],
            state={'waiting':'waiting','treating':'active'}[row['state']],source=source,**extra))
    return InitialState(capacity,tuple(patients),fatigue,source,fatigue_origin).validate()
