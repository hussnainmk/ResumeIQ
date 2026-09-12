# ResumeIQ Product Record

## Original problem statement
Build ResumeIQ, a full-stack AI-driven ATS Resume Analyzer & Optimizer using React, Tailwind/shadcn/ui, FastAPI, and MongoDB. Accept PDF, DOCX, and text resumes; parse structured sections; compare resumes against job descriptions using weighted ATS scoring; generate grounded AI insights and a complete optimized resume; export DOCX/PDF; persist browser-session history; provide trend analytics; use a light responsive design; seed sample analyses.

## Architecture decisions
- React single-workspace experience with Analyze, History, and Analytics views; browser session ID in localStorage, no authentication.
- FastAPI routes handle file parsing, deterministic scoring, Emergent LLM insights/optimization, MongoDB persistence, and DOCX/PDF exports.
- MongoDB responses exclude `_id`; stored timestamps are ISO strings; existing protected environment URLs remain unchanged.
- AI uses `emergentintegrations` with OpenAI `gpt-5.4-mini` and the built-in universal key. Prompts enforce factual grounding for names, titles, dates, degrees, certifications, and metrics.

## User personas
- Job seeker tailoring an existing resume for a specific role.
- Career coach reviewing match quality and improvement history.

## Core requirements (static)
- Upload or paste PDF, DOCX, TXT resume content.
- Contact, summary, skills, experience, and education section extraction.
- Keyword Match 45%, ATS Parseability 25%, Content Quality 30% overall score.
- Matched/missing keyword tags, score ring, AI overview, strengths, gaps, bullet rewrites, tailored summary.
- Full grounded optimizer with “what changed” list and DOCX/PDF downloads.
- Browser-session MongoDB history, seeded examples, score trend and missing-keyword analytics.

## Implemented

### 2026-09-08
- Replaced starter backend with parsing, scoring, AI, history, analytics, and export APIs.
- Added PDF/DOCX/TXT parsing plus DOCX/PDF export dependencies.
- Added grounded GPT 5.4 Mini optimizer and deterministic fallback for transient AI failures.
- Added responsive ResumeIQ UI with upload/paste workspace, report, optimizer, history, analytics, and seeded sample analyses.
- Verified API root, Python compile, frontend production build, live analysis report, score ring, mobile no-overflow, history, analytics, PDF download, and DOCX download.

## Prioritized backlog
- P0: Improve parser coverage for unusual PDF layouts and multi-column resumes.
- P1: Add side-by-side resume version comparison.
- P1: Add richer scoring breakdown details for each ATS check.
- P2: Add export styling controls and configurable filename.

## Remaining next tasks
- P0: Add automated regression coverage for grounded optimizer output invariants.
- P1: Add compare-two-versions view.
- P1: Add explainable keyword weighting and skill-gap clusters.
- P2: Add optional user accounts only if multi-device history becomes necessary.