# Public GridFlex service

Public URL: https://nouman-gridflex-gb.nimblepeony1.chatgpt.site

The dashboard and API run on Cloudflare Workers through Sites. They use a lightweight TypeScript implementation of the seven-day mean baseline and constrained charging allocation. This is an operational public research demo, not an Azure deployment or a hosted Python FastAPI process.

## API

- `GET /api/health`: process health, version and hosting/model identifiers. This does not promise data readiness.
- `GET /api/forecast`: 48 baseline predictions starting at the next half hour, source URL, fetch time, origin and observation cutoff. A 503 means data is unavailable or incomplete. No historical replay is substituted.
- `POST /api/schedule`: JSON fields `battery_kwh`, `power_kw`, `efficiency`, `available_hours`, `carbon_weight`, `tariff` (`flat` or `illustrative`) and `flat_pence`. Returns a plan plus an immediate-charging comparator. Invalid/infeasible requests return 422.

Example request: `{"battery_kwh":14.4,"power_kw":7.2,"efficiency":0.9,"available_hours":24,"carbon_weight":1,"tariff":"flat","flat_pence":25}`.

The baseline uses seven eligible observations at the same **UTC** half-hour on previous days. An actual's interval end must precede the origin by at least two hours. Display times and illustrative tariff hours use Europe/London. NESO responses are validated; server data is cached for at most five minutes per origin.

## Decision scope

The charging algorithm allocates energy to the lowest weighted carbon/price slots, respecting available time, grid power and charging efficiency. It is a charge-only linear allocation; there is no discharge, battery degradation cost, export revenue or device control. Carbon totals are average-intensity proxies, not causal avoided emissions. Prices are supplied assumptions, never live tariffs.

The original backtest favoured seven-day mean. The later holdout favoured persistence among baselines. The public demo retains its transparent initial baseline and exposes the newer result; no reliable superiority claim is made. Poor interval coverage is disclosed and no misleading nominal interval is displayed.

## Source and verification

`public-demo/` contains the published application source and tests. Its hosting manifest omits the private deployment identity so another checkout does not target the owner's Site. Use Node 22.13+ and pnpm 11.25.0; run `pnpm install --frozen-lockfile`, `pnpm dev` for local development, and `node --experimental-strip-types --test tests/grid.test.ts` for domain checks. Publishing requires your own hosting configuration. The existing Python/Docker/Azure workflow remains at repository root.

Checked before publication: TypeScript compilation, production build, and five behavioural tests covering observation eligibility, data failure, feasibility, energy/power conservation and cost/carbon objectives. Browser visual QA was unavailable in the build environment. Publication and public HTTP verification are recorded separately in `reports/public-deployment.json`.

A GitHub Actions probe captures future issued predictions every six hours for audit. These artifacts start a prospective record; they do not establish performance before actual future outcomes arrive. The original maintenance workflow separately captures and scores Python-model predictions.
