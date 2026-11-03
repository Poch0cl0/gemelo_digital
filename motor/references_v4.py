"""Bounded external metadata checks. Never edits manuscript or assumes DOI validity."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.parse import quote
import json,re,time

ROOT=Path(__file__).resolve().parents[2]
def verify(entry):
    ident,text=entry
    match=re.search(r'https://doi.org/([^\s]+)',text)
    if not match:return dict(id=ident,original=text,status='NO_VERIFICABLE',reason='No DOI in entry; documentation/book needs separate source review')
    doi=match.group(1).rstrip('.');url='https://api.crossref.org/works/'+quote(doi,safe='/')
    try:
        req=Request(url,headers={'User-Agent':'ScientificReproducibilityAudit/1.0','Accept':'application/json'})
        with urlopen(req,timeout=8) as response:data=json.load(response)['message']
        titles=data.get('title',[]);title=titles[0] if titles else ''
        year=(data.get('published',{}).get('date-parts') or [[None]])[0][0]
        def norm(x):return re.sub(r'[^a-z0-9]','',x.lower())
        title_match=bool(title and norm(title) in norm(text))
        return dict(id=ident,doi=doi,source=url,original=text,status='METADATA_RETRIEVED' if title_match else 'REVIEW_REQUIRED',title=title,authors=data.get('author',[]),year=year,title_matches=title_match,year_in_entry=str(year) in text,full_text_verified=False)
    except Exception as exc:return dict(id=ident,doi=doi,source=url,original=text,status='NO_VERIFICABLE',reason=str(exc),full_text_verified=False)

if __name__=='__main__':
    text=(ROOT/'correcciones_articulo/Articulo_v3_con_evidencia_suplementaria_auditoria_extraido.txt').read_text(encoding='utf-8')
    entries=[(int(m.group(1)),m.group(2)) for m in re.finditer(r'^\[(\d+)\]\t(.+)$',text,re.M)]
    out=ROOT/'evidencia_v4/fase_5/references_external.json'
    if out.exists():raise FileExistsError('Do not overwrite external checks')
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(verify,entries))
    out.write_text(json.dumps(dict(date='2026-10-31',seconds=time.perf_counter()-start,entries=results,clinical_validation=False,note='Metadata retrieval is not full-text validation or proof of novelty; HTTP failures remain unverified'),ensure_ascii=False,indent=2),encoding='utf-8')
    print('References checked',len(results),{s:sum(r['status']==s for r in results) for s in {r['status'] for r in results}})
