"""Import verified listings from a CSV; verification must happen before import."""
import argparse, csv
from datetime import date
from urllib.parse import urlparse
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Opportunity, Skill
from app.retrieval import embed, embedding_key

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path')
    args = p.parse_args()
    with open(args.path, newline='', encoding='utf-8-sig') as f: rows = list(csv.DictReader(f))
    with SessionLocal() as db:
        for row in rows:
            url = row['source_url'].strip()
            if urlparse(url).scheme not in ('http','https') or not urlparse(url).netloc: raise ValueError('A valid HTTP(S) source_url is required')
            source_date = date.fromisoformat(row['source_date'])
            kind = row['kind'].strip().lower()
            if kind not in ('internship','project'): raise ValueError('kind must be internship or project')
            remote = row['remote'].strip().lower()
            if remote not in ('true','false'): raise ValueError('remote must be true or false')
            names = list(dict.fromkeys(n.strip() for n in row['skills'].split(';') if n.strip()))
            skills = []
            for name in names:
                skill = db.scalar(select(Skill).where(Skill.name == name))
                if not skill:
                    skill = Skill(name=name); db.add(skill); db.flush()
                skills.append(skill)
            title, description = row['title'].strip(), row['description'].strip()
            if not title or not description or not row['organization'].strip() or not row['location'].strip(): raise ValueError('Required field is empty')
            vector = embed(title+' '+description)
            db.add(Opportunity(title=title, organization=row['organization'].strip(), description=description, kind=kind, location=row['location'].strip(), remote=remote=='true', source_type='verified', source_url=url, source_date=source_date, skills=skills, embedding=vector, embedding_model=embedding_key() if vector is not None else None))
        db.commit()
        print(f'Imported {len(rows)} opportunities.')
if __name__ == '__main__': main()
