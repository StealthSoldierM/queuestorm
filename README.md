# QueueStorm

A small web service that classifies one CRM customer-support message at a time and returns a JSON verdict. Submission for the **SUST CSE Carnival 2026 — Codex Community Hackathon** mock preliminary warmup.

See [Submission-Warmup_Mock_Preliminary.pdf](./Submission-Warmup_Mock_Preliminary.pdf) for the full brief, or read [PUKU.md](./PUKU.md) for a concise summary of the rules this service enforces.

## Endpoints

| Method | Path           | Purpose                                            |
| ------ | -------------- | -------------------------------------------------- |
| GET    | `/health`      | Liveness probe. Must respond within 10 s.          |
| POST   | `/sort-ticket` | Classify one ticket. Returns JSON. ≤ 30 s budget.  |
| GET    | `/`            | A minimal web UI to test the classifier manually.  |

### Request

```json
{
  "ticket_id": "T-001",
  "channel": "app",
  "locale": "en",
  "message": "I sent 3000 taka to a wrong number, please help me get it back"
}
```

- `ticket_id` (required, echoed in the response)
- `channel` (optional: `app | sms | call_center | merchant_portal`)
- `locale` (optional: `bn | en | mixed`)
- `message` (required, free text)

### Response

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports that funds were sent to an unintended recipient. Dispute resolution has been notified and will contact the customer.",
  "human_review_required": true,
  "confidence": 0.92
}
```

Enum values and safety rules are enforced exactly per the brief. Any `agent_summary` that asks the customer for a PIN, OTP, password, or full card number is rejected with HTTP 500.

## Local development

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000/> for the UI, or hit the API directly:

```bash
curl -s -X POST http://localhost:8000/sort-ticket \
  -H 'content-type: application/json' \
  -d '{"ticket_id":"T-01","channel":"app","locale":"en","message":"I sent 3000 to wrong number"}'
```

## Deployment

The project ships with both a `Procfile` and a `render.yaml` blueprint so it can be deployed to Render with one click.

### One-click deploy to Render

1. Push this repo to GitHub (public).
2. In Render, click **New → Blueprint**, point it at the repo. Render reads `render.yaml` and provisions a single web service named `queuestorm`.
3. Wait for the first deploy. The service URL looks like `https://queuestorm-<id>.onrender.com`.
4. Confirm `/health` responds:

   ```bash
   curl -fsS https://queuestorm-<id>.onrender.com/health
   ```

5. Submit the form with the service URL as the **Live API base URL**.

### Manual Render setup (alternative)

If you do not want to use the blueprint:

1. **New → Web Service → Public Git Repo**.
2. **Runtime**: Python 3.
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. **Health Check Path**: `/health`
6. **Instance Type**: Free.

### Other platforms

The service has no platform-specific dependencies and works anywhere that can run Python 3.11:

- **Railway**: New Project → Deploy from GitHub → set start command to `uvicorn app:app --host 0.0.0.0 --port $PORT`.
- **Fly.io**: `fly launch`, `fly deploy`. Add `uvicorn app:app --host 0.0.0.0 --port 8080` to the fly.toml.
- **Vercel**: Adapt as a serverless function (entrypoint `app.py`); note that cold starts may approach the 30 s `/sort-ticket` budget on the free tier.

## Environment variables

None are required for the rules-based classifier. If you later add an LLM fallback, set the provider's API key in the Render dashboard and read it via `os.environ`. **Never commit a `.env` file.**

## Verifying against the brief

Five sample messages from §7 of the brief are baked into the web UI (click any pill under the message box). To run them via the CLI:

```bash
for m in \
  "I sent 3000 to wrong number" \
  "Payment failed but balance deducted?" \
  "Someone called asking my OTP, is that bKash?" \
  "Please refund my last transaction, I changed my mind" \
  "App crashed when I opened it"; do
  curl -s -X POST "$BASE_URL/sort-ticket" \
    -H 'content-type: application/json' \
    -d "$(jq -nc --arg m "$m" '{ticket_id:"S",channel:"app",locale:"en",message:$m}')"
  echo
done
```

Expected `case_type`s: `wrong_transfer`, `payment_failed`, `phishing_or_social_engineering` (critical), `refund_request` (low), `other`.

## Submission checklist

- [x] Public GitHub repo with this README.
- [x] Live HTTPS URL with `/health` returning `{"status":"ok"}` in under 10 s.
- [x] No secrets committed; `.env` is gitignored.
- [x] Live URL submitted via the Google Form.
