"""Require a real embedding and verify pgvector and the search retrieval path."""
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import Opportunity
from app.retrieval import embed, embedding_key, search
from app.schemas import SearchRequest

def main():
    if not settings.embeddings_enabled: raise SystemExit('Set EMBEDDINGS_ENABLED=true first')
    key = embedding_key()
    with SessionLocal() as db:
        row = db.scalars(select(Opportunity).where(Opportunity.embedding.is_not(None), Opportunity.embedding_model == key).order_by(Opportunity.id).limit(1)).first()
        if not row: raise SystemExit('No matching stored vectors. Run python -m scripts.embed_existing first.')
        text = row.title + ' ' + row.description
        vector = embed(text)
        if vector is None: raise SystemExit('Embedding generation failed; fallback is not a successful verification.')
        distance = db.scalar(select(Opportunity.embedding.cosine_distance(vector)).where(Opportunity.id == row.id))
        if distance is None or not -0.0001 <= float(distance) < 0.05:
            raise SystemExit(f'Vector does not match the stored text (cosine distance {distance}). Re-embed if source text or model changed.')
        nearest = db.scalar(select(Opportunity.id).where(Opportunity.embedding_model == key, Opportunity.embedding.is_not(None)).order_by(Opportunity.embedding.cosine_distance(vector)).limit(1))
        if nearest is None: raise SystemExit('pgvector similarity search returned no results')
        result = search(db, SearchRequest(query=text[:2000], limit=5))
        if result.retrieval_mode not in ('semantic+hybrid', 'mixed+hybrid') or not result.results:
            raise SystemExit('Search did not use semantic retrieval.')
        print(f'Real embedding and pgvector search verified; model={key}, dimension=384, cosine distance={float(distance):.6f}, nearest id={nearest}, retrieval={result.retrieval_mode}.')
if __name__ == '__main__': main()
