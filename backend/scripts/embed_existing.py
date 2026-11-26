import argparse
from sqlalchemy import or_, select
from app.db import SessionLocal
from app.models import Opportunity
from app.retrieval import embed, embedding_key
from app.config import settings

def main():
    parser = argparse.ArgumentParser(description='Generate missing embeddings. --replace switches existing embeddings to the configured model.')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    if not settings.embeddings_enabled: raise SystemExit('Set EMBEDDINGS_ENABLED=true first')
    key = embedding_key()
    with SessionLocal() as db:
        stmt = select(Opportunity)
        if not args.replace: stmt = stmt.where(Opportunity.embedding.is_(None))
        else: stmt = stmt.where(or_(Opportunity.embedding.is_(None), Opportunity.embedding_model.is_distinct_from(key)))
        rows = db.scalars(stmt).all()
        for row in rows:
            vector = embed(row.title + ' ' + row.description)
            if vector is None: raise SystemExit('Embedding generation failed; no database changes committed')
            row.embedding, row.embedding_model = vector, key
        db.commit()
        print(f'Embedded {len(rows)} opportunities with {key}.')
if __name__ == '__main__': main()
