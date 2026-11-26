# ScoutAI

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

## Deploy on Render

The included `render.yaml` configures one free Docker web service for the frontend and API, plus free PostgreSQL. **Prepared only; not deployed.**

1. In [Render](https://dashboard.render.com/), connect GitHub via **Account Settings → Git Deployment Credentials → Add credential**.
2. Select **New → Blueprint**, choose `thepixelflux/ScoutAI` and branch `work`.
3. Review `scoutai-demo` and `scoutai-db`; confirm both are on free plans and check any charges. Render supplies the database URL.
4. Enter your Groq key in the `LLM_API_KEY` secret field. Keep `EMBEDDINGS_ENABLED=false` and `CORS_ORIGINS` empty. Check Groq's model availability and usage limits.
5. When ready, click **Apply** / **Create Blueprint Instance**. Open the web-service URL and search for “Python internship”. Results should show **FICTIONAL DEMO** and **Keyword and skills ranking (fallback)**. Check `/api/health` for database connectivity.

Render's free web service sleeps after inactivity, and free PostgreSQL expires after 30 days. Check [current limits](https://render.com/docs/free) before deployment. The single-instance rate limiter is a demo safeguard, not a distributed production quota; visitors behind the same proxy can share a limit.

## Verify

```sh
docker compose exec api python -m pytest -q
cd frontend && npm ci && npm run build
```

To verify a configured Groq provider without embeddings:

```sh
docker compose exec api python -m scripts.verify_provider
```

Scores are heuristic, not calibrated probabilities. Avoid submitting sensitive information in search queries.
