# ScoutAI

[Live demo](https://scoutai-demo.onrender.com/)

ScoutAI is a demo for finding internships and projects by skills, interests, and location. **All 150 seeded opportunities are fictional; they are not open positions.**

- **Stack:** React, Vite, FastAPI, PostgreSQL, Docker.
- **Search:** keyword and skill-based fallback ranking; embeddings are disabled.
- **AI:** Groq extracts search intent when configured; rule-based parsing takes over if unavailable. Search results show the active modes.
- **Privacy:** search queries are stored and may be sent to Groq. Uploaded resumes are processed in memory to extract skills.

## Run locally

Requires Docker and Docker Compose.

1. Copy `.env.example` to `.env`.
2. Set the same database password in `POSTGRES_PASSWORD` and `DATABASE_URL`. Optionally set `LLM_API_KEY` for Groq; leave it empty for rule-based intent. Never commit `.env` or API keys.
3. Start the app:

```sh
docker compose up --build
```

Open [localhost:5173](http://localhost:5173). API docs: [localhost:8000/docs](http://localhost:8000/docs). Migrations and demo data are applied automatically to an empty database.

Scores are heuristic, not calibrated probabilities. Avoid submitting sensitive information in search queries.
