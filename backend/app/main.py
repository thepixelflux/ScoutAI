import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import Opportunity
from .retrieval import known_skills, search
from .schemas import AgentRequest, RecommendationRequest, SearchRequest, SearchResponse

logging.basicConfig(level=logging.INFO)
app = FastAPI(title='ScoutAI API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(',') if x.strip()], allow_methods=['GET','POST'], allow_headers=['Content-Type'])

@app.get('/api/health')
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {'status': 'ok'}

@app.post('/api/search', response_model=SearchResponse)
def search_endpoint(request: SearchRequest, db: Session = Depends(get_db)):
    return search(db, request)

@app.post('/api/recommendations', response_model=SearchResponse)
def recommendations(request: RecommendationRequest, db: Session = Depends(get_db)):
    data = request.model_dump(exclude={'resume_text'})
    data['skills'] = list(dict.fromkeys([*request.skills, *known_skills(db, request.resume_text)]))
    return search(db, SearchRequest(**data))

@app.get('/api/opportunities/{opportunity_id}')
def details(opportunity_id: int, db: Session = Depends(get_db)):
    o = db.get(Opportunity, opportunity_id)
    if not o: raise HTTPException(status_code=404, detail='Opportunity not found')
    return {'id':o.id,'title':o.title,'organization':o.organization,'description':o.description,'kind':o.kind,'location':o.location,'remote':o.remote,'source_type':o.source_type,'source_url':o.source_url,'source_date':o.source_date,'skills':[s.name for s in o.skills]}

@app.post('/api/agent')
def agent(request: AgentRequest, db: Session = Depends(get_db)):
    from .agent import run_agent
    return run_agent(db, request.message)

@app.post('/api/resume/extract')
async def extract_resume_endpoint(file: UploadFile = File(...), db: Session = Depends(get_db)):
    from .resume import MAX_BYTES, extract_resume
    try:
        content = await file.read(MAX_BYTES + 1)
        text = extract_resume(file.filename or '', content)
        return {'skills': known_skills(db, text), 'characters': len(text)}
    finally:
        await file.close()
