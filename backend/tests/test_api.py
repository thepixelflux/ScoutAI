import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from app.main import app
from app.db import SessionLocal
from app.models import Opportunity
from app.schemas import Intent, SearchRequest
from pydantic import ValidationError

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c: yield c

def test_schema_rejects_invalid_values():
    with pytest.raises(ValidationError): SearchRequest(limit=0)
    with pytest.raises(ValidationError): Intent(kind='job')

def test_search_filters_and_grounding(client):
    r=client.post('/api/search',json={'query':'Python internship','remote':True,'limit':5})
    assert r.status_code == 200
    body=r.json(); assert body['results']; assert body['intent']['remote'] is True
    for item in body['results']:
        assert item['remote'] and item['kind']=='internship'
        assert item['source_type']=='sample' and item['source_url'] is None
        assert set(item['matched_skills']).issubset(item['skills'])
        assert item['title'] in item['explanation']

def test_recommendation_and_detail(client):
    r=client.post('/api/recommendations',json={'query':'internship','resume_text':'I know Python and SQL','limit':5})
    assert r.status_code==200 and 'Python' in r.json()['intent']['skills']
    item=r.json()['results'][0]
    assert client.get('/api/opportunities/'+str(item['id'])).json()['title']==item['title']
    assert client.get('/api/opportunities/999999').status_code==404

def test_agent_tool_selection(client):
    r=client.post('/api/agent',json={'message':'details for opportunity 1'})
    assert r.status_code==200 and r.json()['tool']=='get_opportunity_details'
    assert client.post('/api/agent',json={'message':'Python internships'}).json()['tool']=='search_opportunities'

def test_pgvector_semantic_retrieval(monkeypatch):
    from app import retrieval
    vector = [1.0] + [0.0] * 383
    other = [0.0, 1.0] + [0.0] * 382
    with SessionLocal() as db:
        first, second = db.scalars(select(Opportunity).order_by(Opportunity.id).limit(2)).all()
        first.embedding, second.embedding = vector, other
        first.embedding_model = second.embedding_model = retrieval.embedding_key()
        db.flush()
        monkeypatch.setattr(retrieval, 'embed', lambda _: vector)
        monkeypatch.setattr(db, 'commit', lambda: db.flush())
        response = retrieval.search(db, SearchRequest(query='semantic probe', limit=5))
        assert response.retrieval_mode == 'mixed+hybrid'
        assert response.results[0].id == first.id
        db.rollback()

def test_resume_upload_docx_and_invalid_files(client):
    from io import BytesIO
    from docx import Document
    document = Document(); document.add_paragraph('Python and SQL')
    buf = BytesIO(); document.save(buf)
    result = client.post('/api/resume/extract', files={'file': ('resume.docx', buf.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert result.status_code == 200
    assert {'Python', 'SQL'} <= set(result.json()['skills'])
    assert client.post('/api/resume/extract', files={'file': ('bad.pdf', b'not a pdf', 'application/pdf')}).status_code == 422
    assert client.post('/api/resume/extract', files={'file': ('bad.exe', b'test', 'application/octet-stream')}).status_code == 415
    assert client.post('/api/resume/extract', files={'file': ('large.txt', b'x' * (2 * 1024 * 1024 + 1), 'text/plain')}).status_code == 413

def test_resume_pdf_and_no_text(client):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter(); page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 20 200 Td (Python and SQL) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    buf = BytesIO(); writer.write(buf)
    result = client.post('/api/resume/extract', files={'file': ('resume.pdf', buf.getvalue(), 'application/pdf')})
    assert result.status_code == 200 and {'Python', 'SQL'} <= set(result.json()['skills'])
    assert client.post('/api/resume/extract', files={'file': ('resume.txt', b'  ', 'text/plain')}).status_code == 422

def test_structured_intent_and_tool_provider_contract(monkeypatch):
    import httpx
    from app import retrieval, agent
    from app.config import settings
    monkeypatch.setattr(settings, 'llm_api_key', 'test-key')
    def fake_post(url, **kwargs):
        payload = kwargs['json']
        if 'response_format' in payload:
            assert payload['response_format']['type'] == 'json_schema'
            content = '{"skills":["Python"],"interests":[],"location":null,"remote":true,"kind":"internship"}'
            data = {'choices':[{'message':{'content':content}}]}
        else:
            assert payload['tool_choice'] == 'required'
            data = {'choices':[{'message':{'tool_calls':[{'function':{'name':'get_opportunity_details','arguments':'{"opportunity_id":1}'}}]}}]}
        return httpx.Response(200, json=data, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx, 'post', fake_post)
    with SessionLocal() as db:
        intent, mode = retrieval.parse_intent(db, 'remote Python internship')
        assert mode == 'llm' and intent.remote and intent.skills == ['Python']
        result = agent.run_agent(db, 'details for opportunity 1')
        assert result['mode'] == 'llm' and result['tool'] == 'get_opportunity_details' and result['data']['id'] == 1

def test_invalid_provider_output_falls_back(monkeypatch):
    import httpx
    from app import retrieval
    from app.config import settings
    monkeypatch.setattr(settings, 'llm_api_key', 'test-key')
    monkeypatch.setattr(httpx, 'post', lambda url, **kw: httpx.Response(200, json={'choices':[{'message':{'content':'{"kind":"job"}'}}]}, request=httpx.Request('POST', url)))
    with SessionLocal() as db:
        intent, mode = retrieval.parse_intent(db, 'Python internship')
        assert mode == 'fallback' and intent.kind == 'internship' and 'Python' in intent.skills

def test_hosted_embeddings_and_invalid_response_fallback(monkeypatch):
    import math, httpx
    from app import retrieval
    from app.config import settings
    monkeypatch.setattr(settings, 'embeddings_enabled', True)
    monkeypatch.setattr(settings, 'embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'embedding_api_key', 'test-key')
    def fake_post(url, **kwargs):
        assert url.endswith('/embeddings')
        assert kwargs['json']['dimensions'] == 384
        return httpx.Response(200, json={'data':[{'embedding':[2.0]+[0.0]*383}]}, request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx, 'post', fake_post)
    vector = retrieval.embed('Python project')
    assert len(vector) == 384 and math.isclose(vector[0], 1.0)
    monkeypatch.setattr(httpx, 'post', lambda url, **kwargs: httpx.Response(200, json={'data':[{'embedding':[1.0]}]}, request=httpx.Request('POST',url)))
    assert retrieval.embed('Python project') is None

def test_incompatible_model_vectors_are_not_used(monkeypatch):
    from app import retrieval
    vector = [1.0] + [0.0] * 383
    with SessionLocal() as db:
        first = db.scalars(select(Opportunity).order_by(Opportunity.id).limit(1)).one()
        first.embedding, first.embedding_model = vector, 'different-model'
        db.flush()
        monkeypatch.setattr(retrieval, 'embed', lambda _: vector)
        monkeypatch.setattr(db, 'commit', lambda: db.flush())
        result = retrieval.search(db, SearchRequest(query='semantic probe', limit=5))
        assert result.retrieval_mode == 'lexical+hybrid'
        db.rollback()

def test_fallback_and_demo_catalog(client, monkeypatch):
    from app.config import settings
    from sqlalchemy import func
    monkeypatch.setattr(settings, 'embeddings_enabled', False)
    monkeypatch.setattr(settings, 'llm_api_key', '')
    result = client.post('/api/search', json={'query': 'Python', 'limit': 100})
    assert result.status_code == 200
    assert result.json()['retrieval_mode'] == 'lexical+hybrid'
    assert result.json()['intent_mode'] == 'fallback'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Opportunity)) == 150
        assert db.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.source_type != 'sample')) == 0

def test_security_limits_and_cors():
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from app.security import ApiProtection
    from app.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Settings(cors_origins='*')
    with pytest.raises(ValidationError): SearchRequest(skills=['x' * 101])
    test_app = FastAPI()
    test_app.add_middleware(ApiProtection, limit=2)
    test_app.add_middleware(CORSMiddleware, allow_origins=['https://example.com'], allow_methods=['POST'], allow_headers=['Content-Type'])
    @test_app.post('/api/test')
    async def endpoint(request: Request):
        return {'size': len(await request.body())}
    with TestClient(test_app) as c:
        assert c.post('/api/test', content=b'a', headers={'Origin':'https://example.com'}).headers['access-control-allow-origin'] == 'https://example.com'
        assert 'access-control-allow-origin' not in c.post('/api/test', content=b'a', headers={'Origin':'https://evil.example'}).headers
        assert c.post('/api/test').status_code == 429
    test_app2 = FastAPI()
    test_app2.add_middleware(ApiProtection)
    @test_app2.post('/api/test')
    async def endpoint2(request: Request):
        return {'size': len(await request.body())}
    with TestClient(test_app2) as c:
        assert c.post('/api/test', content=b'x' * (3 * 1024 * 1024 + 1)).status_code == 413
