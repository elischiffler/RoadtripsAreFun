# Public demonstration and MacBook rehearsal

Presentation: Tuesday, October 6, 2026. Primary target: the public
RoadtripsAreFun website from the presenter's MacBook. The `/algorithm` page is
owner-only; API routes remain `/algorithm-lab/presets` and `/algorithm-lab/run`.
The [teaching guide](cp-sat-explained.md) explains the model. This runbook does
not authorize a merge or a manual production deployment.

## Public release gap observed October 4

Read-only HTTP checks found the website, API `/health` and `/ready` responding
200. Public `/algorithms` still returned `greedy` and `ortools`, with `greedy`
default. Thus the public backend did not run the inspected CP-SAT feature.
The frontend bundle pointed to `https://api.roadtrips.elischiffler.dev/`.
The API exposed no commit-revision response header, so its exact SHA is unknown.

GitHub main was `92ac3af`; PR #26 was draft at `53fd0bf`, with successful checks.
The latest recorded successful Vercel Production deployment used that main SHA.
Those are observations, not acceptance for this new feature. Pulling the code
on a MacBook does not update either public service.

## Release sequence

1. Review the Lab changes together with the underlying CP-SAT feature. Verify
   required checks on the final shared PR head; retain draft status for material
   live acceptance blockers.
2. The user approves/merges the PR. Record the resulting main SHA and its checks.
3. Verify current Vercel production branch, build variables and Cognito pairing;
   retain the prior frontend deployment. A frontend preview does not prove the
   public backend has the Lab endpoint.
4. The repository has CI but no production backend deployment workflow. A
   separately authorized operator must deploy the reviewed merged-main SHA
   through the existing AWS/Caddy API + external Neon topology in
   `compose.neon.yaml`. Preserve target, TLS, write gate, CORS and protected
   provider configuration. Do not switch to proposed same-host PostgreSQL.
5. Retain the prior backend image/digest and verify recovery evidence. Existing
   `aws-api-readiness.md` reports active off-host backup, while
   `off-host-neon-recovery.md` still says proposed; inspect live evidence before
   treating either statement as current proof. No migration is added by the Lab.
6. Check public `/algorithms` reports only/default `cp_sat`; inspect host image
   labels for exact backend revision. Test the public owner `/algorithm` screen,
   non-owner API denial, a complete live route and itinerary, provider failure,
   reload and ordinary chat. Record the actual target and evidence.

The current owner authorization reuses verified Cognito access and ID tokens,
matching subjects and verified owner email. Use normal login on the MacBook;
do not copy browser tokens or send passwords to an agent. The navigation link
does not depend on development-tool build flags. If the link is absent, inspect
backend eligibility, token expiry/claims and frontend/backend release parity.

## MacBook local backup

Use the public website first. If a local fallback is desired, install Python
3.12 and Node 24 before rehearsal. Clone or fetch this repository and check out
the reviewed final task/feature branch until it is merged; after merge use
updated main. Do not assume an older local branch contains the feature.

```sh
git fetch origin
# Use the exact reviewed branch supplied in the final PR handoff.
git switch --track origin/codex/senior-demo-plan
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt 'ruff==0.16.7'
npm ci --prefix frontend
node scripts/dev.mjs
```

If the branch already exists locally, switch to it and pull with `--ff-only`.
If its changes have been integrated elsewhere, use that final verified ref.
Store required local configuration in ignored root `.env`, following
`.env.example` and [development setup](../.steering/development.md). Git does
not transfer ignored secrets. Use the existing protected configuration process.
For a local frontend/backend pair, set `VITE_BACKEND_SERVER` to the local API
and allow the exact local origin. Never copy server keys into `VITE_*` values.

All Lab runs need live backend providers, Cognito connectivity, account-persona
reads and experiment storage; access may be limited by IP allowlists. The Lab
runs the shared planner directly and does not silently forward to an older remote
planner. Test on the actual MacBook/network.

## Screen and presentation flow

1. Sign in with the owner account and open `/algorithm` from the header.
2. Click **Trip presets** to open the modal. Pick **Coastal nature** or one of
   the six varied benchmark trips. Selection fills every field and closes the
   modal without starting provider work.
3. Review the upcoming date, travelers, room occupants, vehicle and schedule.
   Adjust interests with the pie editor, percentage fields or keyboard controls.
4. Click **Run live route**. Inspect discovery, selection, scheduling, rerouting
   and itinerary outcomes. Open one candidate's contribution table to explain
   weights × ratings, the .60 threshold, stop cap and one-candidate-per-slot rule.
5. Choose **Same corridor, culture** or another preset and run again. Each run
   discovers fresh places; differences may reflect both weights and candidates.
6. Show map and schedule only if produced. Explain that CP-SAT selection's
   optimality does not prove a globally optimal full road trip. Provider failures
   remain visible and are never replaced with synthetic data.

The page is intentionally transient: edits invalidate output, reset cancels
display of stale requests, and reloading clears the experiment. Browser abort
does not guarantee every already-started provider request was canceled server-side.

For classroom reliability, rehearse the exact public account, browser and network
before Tuesday. Keep the teaching guide and a clearly labeled recording or
screenshots of a successful rehearsal on the MacBook if you choose to capture
them. A saved demonstration is evidence of that run, not current provider health.

## Persistent Algorithm Lab experiments

Algorithm Lab records live provider runs in a separate, owner-scoped
PostgreSQL table. Ordinary chat runs are excluded. A benchmark modal queues the
six route categories sequentially, with optional repeats and persistent input/metric
history. See [run history and migration](algorithm-run-history.md) for scoring, feasibility,
comparison rules and operational boundaries. Apply the additive table migration
to the approved target before the backend release; local validation is not evidence
of a public database migration. Historical replay records remain labeled, but new replay runs are rejected.
