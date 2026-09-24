# Security — ZeniTrade AI

> ⚠️ **This system trades real money. Read this document fully before deploying.**

---

## Authentication

### API Token Auth
All mutating endpoints (POST/DELETE) require the `X-API-Token` header:

```http
X-API-Token: your-secret-token
```

- Set `ZENITRADE_API_TOKEN` in `python-backend/.env`
- Set the same token in dashboard `.env.local` as `ZENITRADE_API_TOKEN`
- The Next.js proxy (`backend-proxy.ts`) forwards this header automatically
- When empty (dev mode), all requests are allowed (NEVER deploy empty to production)

### Binding
- Default `HOST=127.0.0.1` — only accessible from localhost
- NEVER use `HOST=0.0.0.0` without a reverse proxy (nginx/Caddy) with TLS

---

## Rate Limiting

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /order` | 10/min | Prevent runaway order spam |
| `DELETE /positions/{ticket}` | 10/min | Prevent rapid close/reopen |
| `POST /positions/{ticket}/modify` | 20/min | Trailing needs frequent updates |
| `POST /positions/{ticket}/partial` | 10/min | Scale-out limit |
| `POST /email/test` | 3/min | Prevent SMTP abuse |
| `POST /ml/train` | 1/hour | CPU-intensive training |
| `POST /accounts/switch` | 5/min | Account switching |
| `POST /connect` | — | No limit (startup operation) |

Rate limiting uses `slowapi` library. On limit breach: HTTP 429 with JSON body `{"ok": false, "error": "Rate limit exceeded: ..."}`.

---

## Input Validation

All mutating endpoints use Pydantic models:

```python
class OrderReq(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=12)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    volume: float | None = None
    slPips: int = Field(default=10, ge=1, le=200)
    comment: str = Field(default="AI:auto", max_length=31)
```

- Invalid input → HTTP 422 (not 500)
- `slPips` clamped to [1, 200] — prevents ZeroDivisionError
- `side` pattern-validated — only "BUY" or "SELL"
- Volume clamped to FINEX range [0.01, 50.0] in code

---

## Secrets Management

### What's Stored
| Secret | Location | Purpose |
|--------|----------|---------|
| MT5 password | `.env` | Broker login |
| API keys (Finnhub, MARKETAUX, Z.AI, Groq, Google) | `.env` | External API auth |
| SMTP password | `.env` | Email notifications |
| Telegram bot token | `.env` | Push notifications |
| `ZENITRADE_API_TOKEN` | `.env` | API auth |

### What's NOT Stored
- Secrets are NEVER logged (verified: `grep -r "log.*settings" python-backend/` returns no matches)
- Secrets are NEVER returned by any GET endpoint (verified: no endpoint returns `settings.*` values)
- `.env` is gitignored (verified: `git check-ignore python-backend/.env` matches)
- Only `config.example.env` (with placeholders) is committed

### Secrets in Memory
- Pydantic Settings loads keys into a singleton at startup
- Keys stored as plain `str` (not `SecretStr` — acceptable for single-user system, upgrade if multi-tenant)

---

## Terminal Path Security

The API **refuses** client-supplied terminal paths to prevent arbitrary executable launch (RCE):

```python
class ConnectReq(BaseModel):
    login: int | None = None
    server: str | None = None
    password: str | None = None
    autoLaunch: bool | None = None
    # NOTE: `terminal` field intentionally NOT accepted from client
```

Terminal path is locked to `.env` (`MT5_TERMINAL_PATH`). The path is validated:
- Must exist (`os.path.exists`)
- Must be a file (`os.path.isfile`)
- Must end with `.exe`

---

## Multi-Worker Safety

The system uses in-process state (`_order_lock`, `guard.daily_loss`, `guard.open_count`). Running multiple uvicorn workers would create per-worker copies of this state, silently breaking risk limits.

**Guard:** On startup, if `UVICORN_WORKERS > 1` and `MULTI_WORKER_SAFE != "1"`, the system refuses to start:

```python
if workers > 1 and os.environ.get("MULTI_WORKER_SAFE") != "1":
    raise RuntimeError("Refusing to start with multiple workers — ...")
```

**Solution:** Always run with `--workers 1` (default). For scaling, use horizontal scaling with a shared Redis/Postgres backend instead.

---

## CORS

```python
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

- Only the dashboard origin is allowed
- `allow_methods=["GET", "POST", "DELETE"]` (not `["*"]`)
- `allow_credentials` not set (no cookies needed)

---

## Risk Protections

### Pre-Trade Checks (in order)
1. **Daily risk limit** — `daily_loss >= 3%` → halt
2. **Max open positions** — `open_count >= 3` → halt
3. **Margin level** — `< 60%` (FINEX MC at 50%) → halt
4. **Drawdown** — `> 10%` from day open → halt
5. **Weekend gap** — Fri 21:00 UTC – Sunday → halt
6. **News blackout** — high-impact event ±15 min → halt
7. **Spread filter** — spread > 5 pips → reject (news spike protection)
8. **Confidence threshold** — AI signal < 60% → reject (frontend)
9. **Signal cooldown** — 60s per symbol (auto-trade loop)

### Post-Trade Management
- **Break-even** — SL moved to entry+2pips at +1R
- **Trailing stop** — SL advanced behind price (fixed or ATR-based)
- **Partial close** — 50% closed at +1.5R (if enabled)
- **Position reconciliation** — 10s loop syncs with broker (handles SL/TP hits)

### Daily Risk Persistence
- `daily_loss` + `open_count` persisted to SQLite (`risk_state` table)
- Restored on backend restart (prevents reset-to-zero exploit)
- Resets at UTC date rollover

---

## Logging

### What's Logged
- **INFO+ from `zenitrade` logger** — full order lifecycle (signal → risk → send → fill → SL/TP → close) persisted to DB
- **WARNING+ from other loggers** — MT5, news, AI errors persisted to DB
- **Structured JSON** — `LOG_FORMAT=json` for ELK/Loki/CloudWatch

### What's NOT Logged
- API keys, passwords, tokens (verified: grep-clean)
- Full request bodies (only structured fields: symbol, side, volume, sl)
- PII (no user data — single-user system)

### Log Retention
- Max 5000 log entries (hourly cleanup)
- Max 10000 trade records
- Max 500 alerts
- Max 20 inactive ML model records

---

## Known Limitations

1. **Single-user system** — no multi-tenant isolation. All endpoints share one MT5 account.
2. **No TLS termination** — use a reverse proxy (nginx/Caddy) for HTTPS
3. **No CSRF protection** — not needed (API uses token auth, not cookies)
4. **No SQL injection risk** — uses parameterized queries via sqlite3
5. **No SSRF** — news service URLs are hardcoded (not user-controllable)

---

## Security Checklist Before Live Trading

- [ ] `ZENITRADE_API_TOKEN` set to 32+ char random string
- [ ] `HOST=127.0.0.1` (not `0.0.0.0`)
- [ ] `.env` file permissions: `chmod 600`
- [ ] Firewall: port 8000 blocked externally
- [ ] Dashboard `.env.local` token matches backend
- [ ] MT5 terminal: algo trading enabled
- [ ] Test on DEMO account first (`MT5_SERVER=FINEX-Demo`)
- [ ] `RISK_PER_TRADE_PCT` ≤ 1.0
- [ ] `DAILY_RISK_LIMIT_PCT` ≤ 3.0
- [ ] `AVOID_HIGH_IMPACT_NEWS=true`
- [ ] SMTP/Telegram configured + tested
- [ ] `/health` returns `ok: true`
- [ ] `LOG_FORMAT=json` for production

---

## Reporting Vulnerabilities

If you discover a security vulnerability:
1. Do NOT open a public GitHub issue
2. Email: security@zenitrade.ai (if configured) or contact the maintainer directly
3. Include: description, steps to reproduce, potential impact
4. You will receive a response within 48 hours
