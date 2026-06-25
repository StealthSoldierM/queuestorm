#!/usr/bin/env python3
"""Verify QueueStorm against §7 of the brief. No external deps."""
import json
import sys
import time
import urllib.request

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"

CASES = [
    ("T-01", "I sent 3000 to wrong number", "wrong_transfer", "high"),
    ("T-02", "Payment failed but balance deducted?", "payment_failed", "high"),
    ("T-03", "Someone called asking my OTP, is that bKash?", "phishing_or_social_engineering", "critical"),
    ("T-04", "Please refund my last transaction, I changed my mind", "refund_request", "low"),
    ("T-05", "App crashed when I opened it", "other", "low"),
]

VALID_CASE = {"wrong_transfer", "payment_failed", "refund_request", "phishing_or_social_engineering", "other"}
VALID_SEV = {"low", "medium", "high", "critical"}
VALID_DEPT = {"customer_support", "dispute_resolution", "payments_ops", "fraud_risk"}
FORBIDDEN = ("pin", "otp", "password", "card number", "cvv", "share your", "send me your", "provide your")

def post(ticket):
    body = json.dumps({"ticket_id": ticket[0], "channel": "app", "locale": "en", "message": ticket[1]}).encode()
    req = urllib.request.Request(f"{BASE_URL}/sort-ticket", data=body, headers={"content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        elapsed = time.time() - t0
        return r.status, json.loads(r.read()), elapsed

failures = 0
print(f"{'TICKET':8} {'EXPECTED':36} {'GOT':36} {'SEV':10} {'HUMAN':6} {'ms':>6}  RESULT")
print("-" * 120)
for c in CASES:
    status, data, elapsed_ms = (None, None, 0)
    try:
        status, data, elapsed = post(c)
        elapsed_ms = int(elapsed * 1000)
    except Exception as e:
        print(f"{c[0]:8} {c[2]:36} {'ERROR':36} {'-':10} {'-':6} {'-':>6}  FAIL — {e}")
        failures += 1
        continue

    errs = []
    if status != 200:
        errs.append(f"http {status}")
    if data.get("ticket_id") != c[0]:
        errs.append(f"ticket_id echo wrong: {data.get('ticket_id')}")
    if data.get("case_type") not in VALID_CASE:
        errs.append(f"bad case_type: {data.get('case_type')}")
    if data.get("case_type") != c[2]:
        errs.append(f"case_type mismatch (expected {c[2]})")
    if data.get("severity") not in VALID_SEV:
        errs.append(f"bad severity: {data.get('severity')}")
    if data.get("severity") != c[3]:
        errs.append(f"severity mismatch (expected {c[3]})")
    if data.get("department") not in VALID_DEPT:
        errs.append(f"bad department: {data.get('department')}")
    conf = data.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        errs.append(f"bad confidence: {conf}")
    summary = (data.get("agent_summary") or "").lower()
    for f in FORBIDDEN:
        if f in summary:
            errs.append(f"summary contains forbidden phrase: '{f}'")
    expected_human = (data.get("severity") == "critical") or (data.get("case_type") == "phishing_or_social_engineering")
    if data.get("human_review_required") != expected_human:
        errs.append(f"human_review_required should be {expected_human}")

    result = "PASS" if not errs else "FAIL"
    if errs:
        failures += 1
    print(f"{c[0]:8} {c[2]:36} {data.get('case_type',''):36} {data.get('severity',''):10} {str(data.get('human_review_required','')):6} {elapsed_ms:>6}  {result}")
    for e in errs:
        print(f"        • {e}")

# Latency check: each sample under 30s
# /health already checked separately if needed

print()
print(f"Failures: {failures}/{len(CASES)}")
sys.exit(0 if failures == 0 else 1)