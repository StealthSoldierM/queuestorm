# PUKU.md

This file provides guidance to puku-cli when working with code in this repository.

## What this repo is

QueueStorm warmup submission for SUST CSE Carnival 2026 (Codex Community Hackathon, mock preliminary). Build a small web service that classifies one CRM customer-support message and returns a JSON verdict. Full brief: @Submission-Warmup_Mock_Preliminary.pdf

## Required endpoints

- `GET /health` — simple liveness response.
- `POST /sort-ticket` — accepts one ticket, returns classification JSON.

Request body fields: `ticket_id` (required, echoed), `channel` (optional: `app|sms|call_center|merchant_portal`), `locale` (optional: `bn|en|mixed`), `message` (required, free text).

## Response enums (must match exactly)

- `case_type`: `wrong_transfer | payment_failed | refund_request | phishing_or_social_engineering | other`
- `severity`: `low | medium | high | critical`
- `department`: `customer_support | dispute_resolution | payments_ops | fraud_risk`
- `human_review_required`: boolean — `true` for `critical` severity or `phishing_or_social_engineering` case_type.
- `confidence`: float in `[0, 1]`.
- `agent_summary`: one or two neutral sentences.

## Safety rule (auto-fail if violated)

`agent_summary` must NEVER ask the customer for PIN, OTP, password, or full card number. The grader checks this on every response.

## Runtime requirements

- Public HTTPS endpoint (Render / Railway / Fly / Vercel / EC2 / Poridhi Lab / etc.).
- `/health` response time ≤ 10 seconds.
- `/sort-ticket` response time ≤ 30 seconds.
- GPU dependency is not allowed.
- No secrets in the repository — use environment variables.
- LLM usage is allowed but not required; rules-based classifiers are accepted.
- Submit via the Google Form with: team name, GitHub repo URL, live API base URL, deployment platform, LLM usage (Yes/No/which), known issues.

## Sample cases (from §7 of the brief)

| # | Message | Expected case_type | Severity |
|---|---|---|---|
| 1 | I sent 3000 to wrong number | wrong_transfer | high |
| 2 | Payment failed but balance deducted? | payment_failed | high |
| 3 | Someone called asking my OTP, is that bKash? | phishing_or_social_engineering | critical |
| 4 | Please refund my last transaction, I changed my mind | refund_request | low |
| 5 | App crashed when I opened it | other | low |

## Working agreements

- Keep the agent_summary to one or two neutral sentences describing the ticket; do not include advice or follow-up questions to the customer (avoid risk of violating the safety rule).
- Echo `ticket_id` exactly in the response.
- Don't add endpoints beyond `/health` and `/sort-ticket` unless the brief changes — keep the surface area minimal for grading.
