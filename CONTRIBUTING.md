# Contributing — ZeniTrade AI

Terima kasih atas minat Anda untuk berkontribusi! Dokumen ini menjelaskan cara setup development, code style, dan proses pull request.

---

## Development Setup

### Prasyarat
- Python 3.13+
- Node.js 22+ + bun
- Git
- VS Code (recommended)

### Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/frxtee.git
cd frxtee
git remote add upstream https://github.com/teekar2312/frxtee.git
```

### Backend Development

```powershell
cd python-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
copy config.example.env .env
# Edit .env — at minimum set MT5 credentials + one AI API key
```

### Frontend Development

```bash
bun install
bun run dev
```

Dashboard tersedia di http://localhost:3000

---

## Code Style

### Python
- **Type hints** pada semua public functions
- **Docstrings** pada semua modules dan public functions
- **Pydantic models** untuk semua request/response bodies
- **`asyncio.to_thread()`** untuk semua MT5/sync calls di async routes
- **`noqa: BLE001`** untuk broad exception catches (trading systems must not crash)
- Gunakan `log.info()` untuk trade events, `log.warning()` untuk recoverable errors

Contoh:
```python
async def api_order(body: OrderReq, request: Request, _auth=Depends(require_token)):
    """Place a market order with full safety enforcement."""
    async with _order_lock:
        equity = _get_equity()
        ok, msg = guard.can_open(equity)
        if not ok:
            return {"ok": False, "error": msg}
        # ...
```

### TypeScript / React
- **`"use client"`** di atas setiap component file
- **shadcn/ui components** — jangan rebuild yang sudah ada
- **TanStack Query** untuk semua server state (bukan useEffect + fetch)
- **Zustand** untuk client state (dengan `persist` untuk config)
- **`next/dynamic`** untuk code splitting views berat
- **`React.memo`** untuk components yang re-render sering (e.g. ticker cells)
- **`AbortSignal`** pada fetch yang bisa dibatalkan (e.g. multi-analysis)
- **`placeholderData: (prev) => prev`** untuk smooth transitions

Contoh:
```typescript
export function useMultiAnalysis(symbols: string[], provider: string) {
  return useQuery({
    queryKey: ["multi-analysis", symbols.join(","), provider],
    queryFn: async ({ signal }) => {
      const r = await j(`/api/trading/analysis/batch?symbols=${symbols.join(",")}`, signal);
      return { results: r.results ?? {} };
    },
    placeholderData: (prev) => prev,
  });
}
```

### CSS
- **Tailwind CSS 4** — gunakan utility classes, bukan custom CSS
- **CSS variables** (`var(--success)`, `var(--danger)`) untuk theme-aware colors
- **`tnum`** class untuk tabular numbers (trading figures)
- **`scroll-thin`** class untuk compact scrollbars

---

## Project Structure

```
src/
├── app/
│   ├── api/trading/     # Next.js API routes (proxy to backend)
│   ├── page.tsx         # Main dashboard (nav + view switcher)
│   └── layout.tsx       # Root layout (theme + query provider)
├── components/trading/  # View components (1 file per view)
├── lib/                 # Hooks, stores, utils, proxy
└── hooks/               # shadcn hooks (use-toast, use-mobile)

python-backend/
├── main.py              # FastAPI app + all routes
├── mt5_service.py       # MT5 integration
├── ai_service.py        # AI providers
├── ml_model.py          # ML model
├── risk_manager.py      # Risk management
├── indicators.py        # 30 technical indicators
├── news_service.py      # News + sentiment
├── trading_analytics.py # Strength, correlation, sweep, flow
├── db.py                # SQLite persistence
├── notifier.py          # Notifications
├── config.py            # Pydantic settings
└── backtest.py          # Backtesting engine
```

---

## Pull Request Process

1. **Branch** — buat branch dari `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Commit** — gunakan conventional commits:
   ```bash
   git commit -m "feat: add currency strength heatmap"
   git commit -m "fix: trailing stop not advancing on SELL positions"
   git commit -m "docs: update API.md with /strength endpoint"
   ```

3. **Lint** — pastikan lolos:
   ```bash
   bun run lint          # Frontend (0 errors required)
   # Python: pastikan `python -c "import ast; ..."` pass untuk semua file
   ```

4. **Test** — verifikasi dashboard render:
   - Buka http://localhost:3000
   - Navigate ke view yang Anda ubah
   - Pastikan tidak ada console error

5. **PR** — buka Pull Request ke `main`:
   - Jelaskan apa yang diubah dan mengapa
   - Sertakan screenshot jika UI berubah
   - Reference issue jika ada

---

## Commit Message Convention

```
<type>: <description>

<optional body>
<optional footer>
```

**Types:**
- `feat:` — fitur baru
- `fix:` — bug fix
- `docs:` — dokumentasi
- `refactor:` — refactoring tanpa perubahan fungsi
- `perf:` — performance improvement
- `chore:` — maintenance (deps, config)

**Contoh:**
```
feat: add ATR-based dynamic trailing stop

Trailing distance now adapts to volatility via ATR(14) * multiplier.
Configurable via trailing_use_atr + trailing_atr_multiplier.
```

---

## Testing

Saat ini tidak ada automated tests (trading system memerlukan MT5 untuk test penuh). Verifikasi manual:

1. **Backend** — `python -c "import ast; ast.parse(open('file.py').read())"` untuk semua file
2. **Frontend** — `bun run lint` (0 errors)
3. **Dashboard** — buka di browser, navigate semua views, verify no console errors
4. **Order flow** — place order via Trading view, verify toast + position appears
5. **Close flow** — click Close, verify AlertDialog + toast + position removed

---

## Areas That Need Help

- [ ] Automated tests (pytest for backend, vitest for frontend)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] WebSocket integration testing
- [ ] Multi-symbol ML model (one model per pair)
- [ ] Strategy builder backtest execution
- [ ] Mobile responsive testing
- [ ] Internationalization (i18n)

---

## Questions?

Buka [GitHub Issue](https://github.com/teekar2312/frxtee/issues) dengan label `question`.
