import logging
import math
import re
from functools import lru_cache
from sqlalchemy import case, select
from sqlalchemy.orm import Session
from .config import settings
from .models import Opportunity, Skill, SearchLog
from .schemas import Intent, SearchRequest, SearchResponse, OpportunityOut

log = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def embedding_key():
    if settings.embedding_provider == 'local':
        return 'local:sentence-transformers/all-MiniLM-L6-v2'
    if settings.embedding_provider == 'openai':
        # Include the endpoint because different providers may use the same model name.
        from urllib.parse import urlsplit
        url = urlsplit(settings.embedding_base_url)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Embedding base URL must be HTTPS without credentials, query, or fragment')
        return f'openai:{url.geturl().rstrip("/")}:{settings.embedding_model}:384'
    raise ValueError('Unsupported embedding provider')

def embed(text: str):
    if not settings.embeddings_enabled or not text.strip(): return None
    try:
        embedding_key()
        if settings.embedding_provider == 'local':
            raw = embedding_model().encode(text, normalize_embeddings=True).tolist()
        else:
            if not settings.embedding_api_key:
                raise ValueError('EMBEDDING_API_KEY is missing')
            import httpx
            response = httpx.post(settings.embedding_base_url.rstrip('/') + '/embeddings', headers={'Authorization': 'Bearer ' + settings.embedding_api_key}, json={'model':settings.embedding_model, 'input':text, 'dimensions':384, 'encoding_format':'float'}, timeout=30)
            response.raise_for_status()
            raw = response.json()['data'][0]['embedding']
        if len(raw) != 384 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in raw):
            raise ValueError('Embedding must contain 384 finite numbers')
        norm = math.sqrt(sum(float(x) ** 2 for x in raw))
        if not math.isfinite(norm) or norm == 0: raise ValueError('Embedding must have nonzero finite norm')
        return [float(x) / norm for x in raw]
    except Exception:
        log.warning('Embedding unavailable; using lexical ranking')
        return None

def known_skills(db: Session, text: str):
    lower = text.lower()
    return [s for s in db.scalars(select(Skill.name)).all() if re.search(r'(?<!\w)' + re.escape(s.lower()) + r'(?!\w)', lower)]

def fallback_intent(db: Session, query: str) -> Intent:
    q = query.lower()
    return Intent(skills=known_skills(db, query), interests=[], remote=True if re.search(r'\bremote\b', q) else None, kind='internship' if 'internship' in q else ('project' if 'project' in q else None))

def parse_intent(db: Session, query: str):
    fallback = fallback_intent(db, query)
    if not settings.llm_api_key or not query.strip(): return fallback, 'fallback'
    try:
        import httpx
        response = httpx.post(settings.llm_base_url.rstrip('/') + '/chat/completions', headers={'Authorization': 'Bearer ' + settings.llm_api_key}, json={'model': settings.llm_model, 'messages': [{'role': 'system', 'content': 'Extract search intent. Only infer constraints explicitly stated by the user.'}, {'role': 'user', 'content': query}], 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'intent', 'strict': True, 'schema': {'type':'object','properties':{'skills':{'type':'array','items':{'type':'string'}},'interests':{'type':'array','items':{'type':'string'}},'location':{'type':['string','null']},'remote':{'type':['boolean','null']},'kind':{'type':['string','null'],'enum':['internship','project',None]}},'required':['skills','interests','location','remote','kind'],'additionalProperties':False}}}}, timeout=15)
        response.raise_for_status()
        return Intent.model_validate_json(response.json()['choices'][0]['message']['content']), 'llm'
    except Exception:
        log.warning('Intent provider unavailable; using fallback')
        return fallback, 'fallback'

def search(db: Session, request: SearchRequest) -> SearchResponse:
    intent, intent_mode = parse_intent(db, request.query)
    if request.skills: intent.skills = list(dict.fromkeys([*intent.skills, *request.skills]))
    if request.location is not None: intent.location = request.location.strip() or None
    if request.remote is not None: intent.remote = request.remote
    if request.kind is not None: intent.kind = request.kind
    stmt = select(Opportunity)
    if intent.location: stmt = stmt.where(Opportunity.location.ilike('%' + intent.location.replace('%', r'\%').replace('_', r'\_') + '%'))
    if intent.remote is not None: stmt = stmt.where(Opportunity.remote == intent.remote)
    if intent.kind: stmt = stmt.where(Opportunity.kind == intent.kind)
    vector = embed(request.query)
    # Retrieve a bounded semantic candidate set from pgvector when embeddings exist.
    model_key = embedding_key() if vector is not None else None
    if vector is not None:
        distance = case((Opportunity.embedding_model == model_key, Opportunity.embedding.cosine_distance(vector)), else_=None)
        stmt = stmt.order_by(distance.nulls_last(), Opportunity.id).limit(500)
    else: stmt = stmt.order_by(Opportunity.id).limit(500)
    candidates = db.scalars(stmt).all()
    wanted = {s.lower().strip() for s in intent.skills if s.strip()}
    words = set(re.findall(r'[a-z0-9+#.]+', request.query.lower())) - {'the','and','for','with','a','an','in','i','want','looking','remote','internship','project'}
    results = []
    for o in candidates:
        skills = [s.name for s in o.skills]
        matched = [s for s in skills if s.lower() in wanted]
        missing = [s for s in skills if s.lower() not in wanted]
        overlap = len(matched) / max(len(wanted), 1)
        lexical = len(words & set(re.findall(r'[a-z0-9+#.]+', (o.title+' '+o.description+' '+' '.join(skills)).lower()))) / max(len(words), 1)
        similarity = 0.0
        if vector is not None and o.embedding is not None and o.embedding_model == model_key:
            similarity = max(0.0, min(1.0, sum(float(a)*float(b) for a,b in zip(vector,o.embedding))))
        score = min(1.0, 0.55*(similarity if vector is not None and o.embedding is not None and o.embedding_model == model_key else lexical) + 0.35*overlap + 0.1*(1 if intent.remote is not None or intent.location or intent.kind else 0))
        explanation = f"{o.title} at {o.organization}"
        if matched: explanation += ' uses ' + ', '.join(matched)
        explanation += f". {o.location}; {'remote' if o.remote else 'on-site or hybrid'}."
        results.append(OpportunityOut(id=o.id,title=o.title,organization=o.organization,description=o.description,kind=o.kind,location=o.location,remote=o.remote,source_type=o.source_type,source_url=o.source_url,source_date=o.source_date,skills=skills,score=round(score*100,1),matched_skills=matched,missing_skills=missing,explanation=explanation))
    results.sort(key=lambda x: (-x.score, x.id))
    db.add(SearchLog(query=request.query, result_count=len(results)))
    db.commit()
    embedded = sum(o.embedding is not None and o.embedding_model == model_key for o in candidates) if vector is not None else 0
    mode = 'lexical+hybrid' if not embedded else ('semantic+hybrid' if embedded == len(candidates) else 'mixed+hybrid')
    return SearchResponse(intent=intent, results=results[:request.limit], retrieval_mode=mode, intent_mode=intent_mode)
