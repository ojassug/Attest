# P6-S4 — putting the console somewhere judges can reach it

The rules require a working project **testable by judges for free until judging ends**
(`Attest-PRODUCT.md` §1.4), and a live demo link explicitly strengthens the Technical
Implementation score (§1.5). This is that link.

Everything code-side is done. What remains needs a browser and an account, so it could not be
finished from a terminal session.

---

## Why this deploys cleanly

- **No API key is needed at runtime.** Every model call replays from committed `cassettes/`, so the
  hosted app produces identical results with no credentials configured. Nothing secret is deployed,
  which also means nothing secret can leak from it.
- **`requirements.txt` is one line: `.`** — it installs this package from `pyproject.toml` and pulls
  the declared dependencies with it. The deployed environment cannot drift from the developer one,
  and there is no pinned list to forget to update.
- **The writable paths are redirectable.** `$ATTEST_STORE_DIR` and `$ATTEST_OUT_DIR` move the case
  store and emitted artifacts off the default relative paths. Streamlit Community Cloud gives the
  app a writable working directory, so the defaults work — but on any host that does not, set both
  to somewhere under `/tmp`.

## Steps

1. Push `main` to GitHub. The repository must be public — §1.4 requires it anyway.
2. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns
   the repo.
3. **Create app** → point it at this repository, branch `main`, main file `app.py`.
4. Deploy. First build installs the dependency tree and takes a few minutes.
5. Leave **Secrets** empty. If the app asks for a key, something has regressed to a live model call
   — find that rather than adding a key, because it breaks the offline claim everywhere else too.

## Then close the step

```bash
curl -sf -L -c /tmp/jar -b /tmp/jar https://attest.streamlit.app -o /dev/null && echo ok
```

**The cookie jar is not optional, and omitting it produces a convincing false alarm.** Streamlit
Cloud bootstraps an anonymous session by redirecting to `/-/auth/app`, which sets a session cookie
and redirects back. A browser stores it and completes the loop instantly. A cookie-less `curl -L`
arrives back without it, gets redirected again, and loops until curl aborts with **exit 47** —
which reads exactly like a login wall on a private app. It cost this project two rounds of
"your deploy is broken" against an app that was public and working the whole time.

Also run it from a machine with no local state — a phone on cellular is the closest thing to a
judge's first visit, and unlike curl it exercises the JavaScript the page actually needs.

**A 200 is necessary and nowhere near sufficient.** It proves Streamlit's shell booted. A Python
traceback renders *inside* a page the server returns 200 for, so the app can be completely broken
and still pass this check — which is exactly what happened on the first deploy: `FileNotFoundError`
on the corpus, behind a healthy 200. **Open the page and click through a case.** The step is not
done until someone has actually used the deployed app.

- [ ] Record the URL in `README.md` and in `STATUS.md`'s **Public demo URL** row.
- [ ] Walk `docs/ui-checklist.md` **against the deployed app**, not the local one. First-run
      behaviour on a cold container is what a judge sees.
- [ ] `./scripts/verify.sh P6` exits zero.

## Known limits of the hosted demo

- **The case store is ephemeral.** Community Cloud restarts the container when the app sleeps, and
  stored cases go with it. Precedent reuse therefore demonstrates within a session, not across
  days. This is a hosting property, not a product one — the store is durable, and
  `test_case_survives_process_restart` proves it across real processes. Say so plainly if asked
  rather than implying the demo persists.
- **The app sleeps when idle.** First load after a quiet period takes a while to wake. Load it once
  before recording anything or presenting it.
