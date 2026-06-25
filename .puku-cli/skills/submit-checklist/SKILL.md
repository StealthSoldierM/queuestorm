---
name: submit-checklist
description: Pre-submission gate for the QueueStorm Google Form. Checks the deployment, secrets hygiene, README, /health latency, and end-to-end curl. Run before filling the form.
---

# /submit-checklist

Walk through every Google Form field in §8 of @Submission-Warmup_Mock_Preliminary.pdf and confirm the answer is ready.

## Checklist

1. **Team name** — confirm it matches the registered team name exactly (case-sensitive).
2. **GitHub repo URL** — public; contains `README.md` with deployment runbook and source code; no secrets committed.
3. **Live API base URL** — HTTPS; `/health` returns 200 within 10 seconds.
4. **Deployment platform** — known value (Render, Railway, Fly, Vercel, EC2, Poridhi Lab, other).
5. **LLM usage** — Yes/No/which. If Yes, name the model and provider.
6. **Known issues or blockers** — optional; list anything the grader should know.

## Automated checks the skill runs

- `git remote -v` and verify the remote URL is HTTPS and ends in `.git` on github.com (or comparable host).
- `grep -RInE "(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})" .` — must return nothing.
- `.gitignore` must include `.env`, `*.pem`, `secrets.*`, or equivalent.
- `curl -fsS "$BASE_URL/health" -o /dev/null -w '%{http_code} %{time_total}\n'` — must show `200` and time `< 10`.
- `curl -fsS -X POST "$BASE_URL/sort-ticket" -H 'content-type: application/json' -d '{"ticket_id":"smoke-1","message":"smoke test"}'` — must return 200 with a JSON body containing all required fields.
- `README.md` exists and mentions the deployment platform, environment variables, and how to run locally.

## Output

A markdown table with each Google Form field, its current value/derivation, and a green check / red X. End with "READY TO SUBMIT" or a list of blockers.