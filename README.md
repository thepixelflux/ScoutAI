# ScoutAI

ScoutAI is a demo internship and project discovery app. Its 150 generated listings are **fictional samples**, not real vacancies. Imported listings are labeled verified only because the importer is intended for sources verified by the operator; ScoutAI does not independently verify them.

## Quick start

Requirements: Docker and Docker Compose. Copy `.env.example` to `.env`, then run:

```sh
docker compose up --build
```

Open http://localhost:5173; the API documentation is at http://localhost:8000/docs. Compose waits for PostgreSQL, applies Alembic migrations, and seeds the database only when it contains no opportunities. The database is persisted in the `postgres_data` volume. The default database password is for local development only; change it for any non-local use and update both `POSTGRES_PASSWORD` and `DATABASE_URL` consistently.

By default searches use deterministic lexical/skill ranking and rule-based intent parsing, so credentials and model downloads are not needed. To use semantic retrieval, set `EMBEDDINGS_ENABLED=true` in `.env`, ensure the model `sentence-transformers/all-MiniLM-L6-v2` can be downloaded from Hugging Face or is cached, and restart the API. Existing records without embeddings can be populated with:

```sh
docker compose exec api python -m scripts.embed_existing
```

To use an OpenAI-compatible provider, set `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in `.env` and restart the API. The provider must support chat completions, JSON schema response format, and tool calling. If calls fail, the API falls back to deterministic behavior. Never commit `.env` or keys.

## Architecture

React/Vite/Tailwind calls FastAPI through Nginx in Compose (or the Vite proxy during local development). Pydantic validates input and output; SQLAlchemy and Alembic manage PostgreSQL with pgvector. Search extracts intent, applies SQL filters, selects up to 500 candidates ordered by cosine distance when embeddings are available, then ranks with semantic similarity (or lexical overlap), skill overlap, and filter preferences. Scores are heuristic, not calibrated probabilities. The response identifies retrieval and intent modes. The agent selects one of `search_opportunities` or `get_opportunity_details` through a provider tool call or a deterministic fallback; its output is retrieved data rather than free-form generated claims. Explanations are templates using listing fields only.

The dashboard accepts PDF, DOCX, or UTF-8 text resumes up to 2 MB, with at most 20 PDF pages and 30,000 extracted characters. DOCX expansion is capped at 10 MB. It extracts known skills in memory and does not retain the file or text; scanned image-only PDFs, encrypted files, user-profile management, and authentication are not supported. Profile tables are reserved for future use. Search queries are stored in `search_logs`; avoid including sensitive information. This is an MVP, not a hardened public deployment: add authentication, rate limits, secret management, retention policies, and appropriate database credentials before production use.

## API examples

```sh
curl -s http://localhost:8000/api/search -H 'Content-Type: application/json' -d '{"query":"remote Python internship","limit":5}'
curl -s http://localhost:8000/api/opportunities/1
curl -s http://localhost:8000/api/recommendations -H 'Content-Type: application/json' -d '{"query":"data science","resume_text":"Python and SQL"}'
curl -s http://localhost:8000/api/agent -H 'Content-Type: application/json' -d '{"message":"details for opportunity 1"}'
```

Explicit `location`, `kind`, `remote`, and `skills` fields can refine searches. The rule-based fallback recognizes known skills, remote and kind; location and interests require explicit filters or a working provider. A blank search browses the first candidates. Scores indicate relative heuristic fit and may be zero for broad searches.

## Import

Verify listings and source permission independently before importing. CSV requires headers `title,organization,description,kind,location,remote,source_url,source_date,skills`. Use `internship` or `project` for kind, `true` or `false` for remote, ISO `YYYY-MM-DD` dates, and semicolon-separated skills. Source URLs must be HTTP(S). Run `docker compose exec api python -m scripts.import_csv /path/in/container.csv`; mount or copy the CSV into the container first. Imports are transactional but are not deduplicated.

## Tests and evaluation

With the stack running, `docker compose exec api python -m pytest -q` runs integration checks against the configured database. `docker compose exec api python -m scripts.evaluate` runs the versioned cases in `backend/evaluation/cases.json` and reports top-five skill hits, schema validity, tool selection, observed modes, and request latency. This is a tiny synthetic check, not a benchmark or production relevance metric. `cd frontend && npm ci && npm run build` validates the frontend build. The recorded run in `backend/evaluation/latest-results.json` used 150 synthetic samples, lexical and rule-based fallbacks, no LLM, and no embeddings. It found a relevant skill in the top five for 8/8 cases, validated 8/8 responses, and selected the expected fallback tool in 4/4 cases; median search latency was 7.17 ms on this machine. This tiny, hand-written dataset is not independent of the sample catalog, and timing is not a deployment benchmark.

## Provider configuration and verification

`LLM_API_KEY` is the API key for an OpenAI-compatible Chat Completions provider. Set it in the ignored `.env` file (or inject it using your deployment secret manager); never paste it into chat or commit it. The supplied `.env.example` selects Groq with `LLM_BASE_URL=https://api.groq.com/openai/v1` and `LLM_MODEL=openai/gpt-oss-20b`. The application defaults remain OpenAI when these values are omitted. For another provider, set both to its compatible API base URL and model. The endpoint must support strict `json_schema` response formats and function tool calls. The API sends the search query to the provider, but not the uploaded resume text: only locally extracted skills are sent as explicit filters.

After setting these values, recreate the API (`docker compose up -d --force-recreate api`) and run `docker compose exec api python -m scripts.verify_provider`. This fails if the request silently falls back or does not extract the expected intent and tool. No live provider was available for the recorded run. If the provider hostname is blocked, permit its HTTPS destination in your environment's network settings.

To enable local embeddings, set `EMBEDDINGS_ENABLED=true` and `EMBEDDING_PROVIDER=local`, permit HTTPS access to `huggingface.co` and the model's redirected artifact hosts, recreate the API, and run `docker compose exec api python -m scripts.embed_existing`. The model must be available in the local cache or reachable on Hugging Face. A hosted alternative is described below. In the recorded environment the proxy returned HTTP 403 for `huggingface.co`; real model generation therefore remains unverified. Search responses and the UI explicitly identify semantic, mixed, or keyword fallback retrieval and LLM or rule-based intent.

## Deployment notes

Compose builds a static frontend served by Nginx, proxies `/api` to the API, and runs migrations before startup. `WEB_PORT`, `API_PORT`, `API_UPSTREAM`, `DATABASE_URL`, and `CORS_ORIGINS` are configurable; `DATABASE_URL` must be a PostgreSQL URL usable from the API container. The sample database volume and password are for local development. Set strong credentials, a secret manager, TLS termination, authentication, rate limits, network restrictions, and backups before exposing the service. The included Compose file is a deployment starting point, not a claim of a public deployment.

If your build network uses a trusted intercepting proxy, provide its CA bundle to Docker BuildKit as the optional `build_ca` secret (for example `docker build --secret id=build_ca,src=/path/to/trusted-ca-bundle -t scoutai-api backend` and the equivalent command for `frontend`); this keeps TLS verification enabled and the CA out of the resulting images. Then start with `docker compose up -d --no-build`. Do not commit certificates or private configuration.

## Enable real AI

The simplest LLM option is the Groq API. Create an API key in the [Groq console](https://console.groq.com/keys), and place it in `LLM_API_KEY` in your ignored `.env` file or supply it as a runtime secret; do not put the key in chat. The supplied example selects `LLM_BASE_URL=https://api.groq.com/openai/v1` and `LLM_MODEL=openai/gpt-oss-20b`. Groq offers a free tier subject to its current account and model limits; check its current pricing and availability. Groq's [SDK](https://github.com/groq/groq-python/blob/main/src/groq/types/chat/completion_create_params.py) documents both `json_schema` and tool calling, with schema support restricted to [supported models](https://console.groq.com/docs/structured-outputs#supported-models). The selected model and this exact integration have not been verified with a live key. The application makes separate calls for structured intent and tool selection, and validates the JSON with Pydantic.

For a model-download-free embedding path, set `EMBEDDINGS_ENABLED=true`, `EMBEDDING_PROVIDER=openai`, `EMBEDDING_BASE_URL=https://api.openai.com/v1`, and `EMBEDDING_MODEL=text-embedding-3-small`, and securely provide a separate `EMBEDDING_API_KEY` from an OpenAI account. The provider must support the OpenAI embeddings endpoint and `dimensions=384`. OpenAI embeddings may incur charges and are not assumed to have a free tier; the Groq key is not an OpenAI embedding key. Opportunity text and search queries are sent to the embedding provider. Alternatively, keep `EMBEDDING_PROVIDER=local` and use the existing MiniLM model from a trusted cache.

In this cloud environment, the enforced network policy denied `api.groq.com`, `api.openai.com`, and `huggingface.co`. Add `api.groq.com` and, for hosted OpenAI embeddings, `api.openai.com` to the environment's allowed destinations in its settings. If using local MiniLM, allow the model host and any artifact redirect hosts instead. After changing access, recreate the API container. If the environment uses a TLS-intercepting proxy, containers must trust its CA. For this cloud session, create a temporary override outside the repository with `services.api.volumes` mapping `/etc/ssl/certs/ca-certificates.crt` to `/run/scout/ca-bundle.crt:ro`, and `services.api.environment.SSL_CERT_FILE` set to `/run/scout/ca-bundle.crt`. Use `docker compose -f compose.yaml -f /tmp/scout-ca.yaml up -d --force-recreate api` to apply it. Keep certificate verification enabled.

After configuring credentials and access, run:

```sh
docker compose up -d --force-recreate api
docker compose exec api python -m scripts.embed_existing
docker compose exec api python -m scripts.verify_ai
```

The final command performs real structured intent and tool-selection calls, generates a real embedding, checks its stored match with pgvector cosine distance, and requires semantic search. It exits nonzero on fallback. To check one side independently use `python -m scripts.verify_ai --llm-only` or `--embedding-only` inside the API container. The embed command fills missing vectors only. When switching models, use `python -m scripts.embed_existing --replace` to replace vectors from other models; it makes one request per listing and may incur charges. The database labels each vector with its model and endpoint and does not compare incompatible spaces. If generation fails, the backfill transaction is rolled back and search remains usable with lexical fallback. Re-embed after changing listing text.
