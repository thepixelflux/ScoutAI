"""Create a stable set of clearly synthetic opportunities, once."""
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Opportunity, Skill
from app.retrieval import embed, embedding_key

TRACKS = [
 ('Data Science',['Python','SQL','Machine Learning']), ('Frontend',['JavaScript','React','CSS']),
 ('Backend',['Python','FastAPI','PostgreSQL']), ('Cloud',['Docker','AWS','Linux']),
 ('Design',['Figma','UX Research','Prototyping']), ('Mobile',['Kotlin','Android','Git']),
 ('Analytics',['SQL','Tableau','Python']), ('Security',['Linux','Networking','Python']),
 ('AI Research',['Python','Machine Learning','PyTorch']), ('Product',['Product Management','Analytics','Communication']),
]
LOCATIONS = ['Remote', 'New York', 'London', 'Bengaluru', 'San Francisco']
def main():
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Opportunity)):
            print('Existing opportunities found; seed skipped.')
            return
        skills = {}
        for _, names in TRACKS:
            for name in names:
                if name not in skills:
                    skills[name] = Skill(name=name)
                    db.add(skills[name])
        db.flush()
        for i in range(150):
            track, names = TRACKS[i % len(TRACKS)]
            location = LOCATIONS[(i // 10) % len(LOCATIONS)]
            kind = 'internship' if (i // 50) % 2 == 0 else 'project'
            title = f'{track} {kind.title()} {i+1:03}'
            description = f'Synthetic sample: explore {track.lower()} through a guided {kind} using {", ".join(names)}. This is fictional demo content, not an open position.'
            vector = embed(title+' '+description)
            db.add(Opportunity(title=title, organization=f'Sample Organization {i%15+1:02}', description=description, kind=kind, location=location, remote=location=='Remote', source_type='sample', skills=[skills[n] for n in names], embedding=vector, embedding_model=embedding_key() if vector is not None else None))
        db.commit()
        print('Created 150 synthetic sample opportunities.')
if __name__ == '__main__': main()
