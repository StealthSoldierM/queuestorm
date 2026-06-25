---
name: verify
description: Run the grader's five sample cases from the QueueStorm brief against a live or locally running instance and assert schema, enums, safety rule, and human_review_required behavior. Use before submission, after any logic change, or when debugging a failing case.
---

# /verify

End-to-end verification of the QueueStorm classifier against the public brief.

## Inputs

- `BASE_URL` (env var, optional) — base URL of the running service. If unset, defaults to `http://localhost:8000` or asks the user.

## What it does

1. For each of the 5 sample cases in §7 of @Submission-Warmup_Mock_Preliminary.pdf, POST to `/sort-ticket` with the canonical request body.
2. For each response, assert:
   - HTTP 200.
   - `ticket_id` echoed exactly.
   - `case_type` ∈ allowed enum and matches the expected value for samples 1–5.
   - `severity` ∈ {low, medium, high, critical}.
   - `department` ∈ allowed enum.
   - `confidence` is a number in `[0, 1]`.
   - `human_review_required` is `true` when `severity == "critical"` OR `case_type == "phishing_or_social_engineering"`.
   - `agent_summary` does NOT contain any of: `pin`, `otp`, `password`, `card number`, `cvv` (case-insensitive), and does not contain "send me your", "share your", "provide your".
3. Print a pass/fail table and exit non-zero on any failure.

## Sample request bodies

```json
{"ticket_id":"T-01","channel":"app","locale":"en","message":"I sent 3000 to wrong number"}
{"ticket_id":"T-02","channel":"app","locale":"en","message":"Payment failed but balance deducted?"}
{"ticket_id":"T-03","channel":"sms","locale":"en","message":"Someone called asking my OTP, is that bKash?"}
{"ticket_id":"T-04","channel":"app","locale":"en","message":"Please refund my last transaction, I changed my mind"}
{"ticket_id":"T-05","channel":"app","locale":"en","message":"App crashed when I opened it"}
```

## Implementation notes

- If the project has no test runner yet, this skill should write a small Python script at `.puku-cli/skills/verify/run.py` that uses only `urllib` + `json` (no extra deps) and invoke it via `python3 .puku-cli/skills/verify/run.py "$BASE_URL"`.
- Time the whole run; warn if any single request exceeds 30 seconds.
- Report latency per request alongside the pass/fail table.