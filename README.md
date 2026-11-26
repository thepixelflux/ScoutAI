# ScoutAI

[Live demo](https://scoutai-demo.onrender.com/)

ScoutAI is a demo for finding internships and projects by skills, interests, and location. **All 150 seeded opportunities are fictional; they are not open positions.**

- **Stack:** React, Vite, FastAPI, PostgreSQL, Docker.
- **Search:** keyword and skill-based fallback ranking; embeddings are disabled.
- **AI:** Groq extracts search intent when configured; rule-based parsing takes over if unavailable. Search results show the active modes.
- **Privacy:** search queries are stored and may be sent to Groq. Uploaded resumes are processed in memory to extract skills.

Scores are heuristic, not calibrated probabilities. Avoid submitting sensitive information in search queries.
