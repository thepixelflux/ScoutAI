"""Verify real structured intent and tool calling with the configured provider."""
from app.config import settings
from app.db import SessionLocal
from app.retrieval import parse_intent
from app.agent import run_agent
from app.models import Opportunity
from sqlalchemy import select

def main():
    if not settings.llm_api_key:
        raise SystemExit('LLM_API_KEY is missing; configure it securely before running this check.')
    with SessionLocal() as db:
        intent, mode = parse_intent(db, 'Find a remote Python internship')
        if mode != 'llm': raise SystemExit('Structured intent provider request failed; fallback was used. See logs for details.')
        if 'python' not in [s.lower() for s in intent.skills] or intent.remote is not True or intent.kind != 'internship':
            raise SystemExit('Provider returned a valid schema but did not extract the expected constraints.')
        opportunity_id = db.scalar(select(Opportunity.id).order_by(Opportunity.id).limit(1))
        if opportunity_id is None: raise SystemExit('No opportunity is available for the details tool check.')
        result = run_agent(db, f'Get details for opportunity {opportunity_id}')
        if result['mode'] != 'llm' or result['tool'] != 'get_opportunity_details' or result['data'].get('id') != opportunity_id:
            raise SystemExit('Provider did not select and execute the expected details tool.')
        print('Provider structured intent and tool call verified.')
if __name__ == '__main__': main()
