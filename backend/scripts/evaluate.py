"""Run a small, versioned synthetic smoke evaluation; prints measured JSON."""
import json
import statistics
import time
from pathlib import Path
from app.db import SessionLocal
from app.retrieval import search
from app.schemas import SearchRequest, SearchResponse
from app.agent import run_agent

DATASET = Path(__file__).resolve().parents[1] / 'evaluation' / 'cases.json'

def main():
    cases = json.loads(DATASET.read_text())
    searches, tools = [], []
    with SessionLocal() as db:
        for case in cases['search']:
            start = time.perf_counter()
            result = search(db, SearchRequest(query=case['query'], limit=5))
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            schema_valid = bool(SearchResponse.model_validate(result.model_dump()))
            relevant = lambda row: case['expected_skill'] in row.skills and ('kind' not in case or row.kind == case['kind']) and ('remote' not in case or row.remote == case['remote'])
            searches.append({'query':case['query'], 'hit_at_5':any(relevant(row) for row in result.results), 'schema_valid':schema_valid, 'latency_ms':elapsed, 'intent_mode':result.intent_mode, 'retrieval_mode':result.retrieval_mode})
        for case in cases['tools']:
            result = run_agent(db, case['message'])
            tools.append({'message':case['message'], 'expected':case['expected'], 'actual':result['tool'], 'mode':result['mode']})
    print(json.dumps({'dataset':'evaluation/cases.json', 'search_cases':len(searches), 'hit_at_5':sum(x['hit_at_5'] for x in searches), 'schema_valid':sum(x['schema_valid'] for x in searches), 'median_latency_ms':round(statistics.median(x['latency_ms'] for x in searches), 2), 'tool_cases':len(tools), 'tools_correct':sum(x['expected']==x['actual'] for x in tools), 'searches':searches, 'tools':tools}, indent=2))
if __name__ == '__main__': main()
