# Claude Handoff: Growth Engine Reading Order

Use this file as the reading guide for Claude. Read the documents in the order below before suggesting or changing implementation.

## Read in this order

1. **[MEETING_REQUIREMENTS_ANALYSIS.md](MEETING_REQUIREMENTS_ANALYSIS.md)**
   - This is the normalized conversation analysis.
   - Treat it as the primary statement of what Kesari asked for.
   - Pay special attention to Sales Goal, Daily Rhythm, five agents, pause/resume, approvals, geography-aware scheduling, Leads, Content, and the open questions.
   - Distinguish confirmed requirements from examples and recommendations.

2. **[claudePlane.md](claudePlane.md)**
   - This is the Claude artifact build specification.
   - Review its quarterly sales-goal model, agent configuration, target accounts, plays, jobs, data model, lead rooms, approval queue, guardrails, security requirements, and ten-week build plan.
   - Use its comparison section to see where it differs from the meeting. Do not silently resolve differences.

3. **[PROJECT_STATUS.md](PROJECT_STATUS.md)**
   - This describes the existing application and the work already completed.
   - Use it to avoid proposing features that already exist or assuming integrations are connected.

4. **[README.md](README.md)**
   - This explains how the current Python application runs, its provider integrations, budgets, limitations, and deployment behavior.
   - Read the sections about scheduled discovery and drafts, monthly provider limits, approvals, and deployment.

5. **[GROWTH_ENGINE_REDESIGN_HANDOFF.md](GROWTH_ENGINE_REDESIGN_HANDOFF.md)** and **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)**
   - Read these for earlier design decisions and implementation context.
   - If they conflict with the meeting analysis or Claude specification, call out the conflict and prefer the newer confirmed requirement.

## Current implementation state

- The repository is `D:\\sale automation`.
- Latest pushed commit: `8bf7511` on `main`.
- The app supports BIM Services and Training locally; the Claude specification describes five future agents.
- BIM and Training rhythms are stored in `rhythms.json` and shown in the Daily Rhythm interface.
- Scheduled campaign discovery and approval-ready draft preparation are implemented in `automation.py`.
- The workflow uses Apollo, Brave, and Gemini when the hosted server has keys and monthly limits configured.
- Discovery can find and save screened leads. Drafts must wait for human approval. The app does not send messages automatically.
- Pause controls prevent new work. A provider request already in flight cannot be recalled.
- The hosted app has already produced BIM discovery results. A PostgreSQL wildcard-binding bug affecting scheduled draft processing was fixed in commit `8bf7511`.
- The hosted API is protected by login, so deployment verification requires an authenticated browser session.

## What Claude should do

After reading the documents, Claude should:

1. Summarize the agreed requirements separately from proposed ideas.
2. Compare the requested behavior with the current repository implementation.
3. Identify the smallest next implementation milestone.
4. Preserve human approval, provider budgets, opt-out handling, and pause controls.
5. Flag conflicts such as XAM versus XIM naming, weekday versus 24/7 behavior, and pause semantics before changing code.
6. Avoid sending messages, publishing content, changing provider settings, or deploying without explicit authorization.

## Prompt to paste into Claude

> Read `CLAUDE_READ_ORDER.md` first, then read the documents in its stated order. Treat `MEETING_REQUIREMENTS_ANALYSIS.md` as the primary conversation requirements, `claudePlane.md` as the proposed build specification, and the remaining files as current-project context. Compare the requirements against the actual repository at `D:\\sale automation`. Report: (1) confirmed requirements, (2) current implementation, (3) gaps, (4) conflicts requiring a decision, and (5) the next smallest safe implementation milestone. Do not send messages, publish content, change provider settings, or deploy anything. Preserve approval-before-send and pause controls.

## Important interpretation

The conversation says agents should be available continuously according to their rhythms and pause only when the owner pauses them. The current implementation has a background worker for scheduled discovery and draft preparation, but it is still dependent on the hosted/local server process being alive. It does not yet implement every activity in the full Daily Rhythm, automatic sending, recipient-local-time delivery, or all five agents.
