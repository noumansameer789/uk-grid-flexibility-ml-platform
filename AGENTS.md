# Working on GridFlex GB

The Python service and collector live in `src/gridflex/`. Run their tests in `tests/`. The independent Cloudflare demo lives in `public-demo/`. The Azure configuration is in `infra/terraform/`. The retrospective Power BI inputs are in `powerbi/`. Start with the [README](README.md) and [verification record](docs/VERIFICATION.md).

## Checks

Follow [ci.yml](.github/workflows/ci.yml) for the pinned action revisions and complete Docker smoke requests.

| Area | Commands from the repository root unless indicated |
|---|---|
| Python 3.12 | Install `requirements-dev.lock` and the project with `pip install --no-deps -e .`. Run `ruff check src tests scripts`, `ruff format --check src tests scripts`, and `pytest --cov=gridflex --cov-report=term-missing --cov-report=xml`. |
| Dependency audits | Use `pip-audit==2.10.1` and run `pip-audit -r requirements-dev.lock --no-deps --disable-pip`. With Node 22, run `npm ci --ignore-scripts` and `npm audit --audit-level=high`. |
| FastAPI container | Run `docker build -t gridflex:test .`, start the container on port 8000, check readiness, the 48-slot replay and the default schedule. Run `npm run test:ui` against it. |
| Terraform | In `infra/terraform/`, use Terraform 1.13.3 for `terraform init -backend=false`, `terraform fmt -check` and `terraform validate`. |
| Cloudflare demo | In `public-demo/` with Node 22 and pnpm 11.25.0, run `pnpm install --frozen-lockfile`, `pnpm exec tsc --noEmit`, `node --experimental-strip-types --test tests/grid.test.ts` and `pnpm build`. |

## Evidence and release rules

- Use dated files for new observations. Preserve historical evidence, model artefacts and holdout results. Run `python scripts/audit_evidence.py` in a disposable copy when checking reproduction because the script writes outputs. [Scientific audit](docs/AUDIT.md)
- Describe charging as a simulation using average grid intensity. Treat overlapping forecast horizons as dependent. Record the promotion decision and distinguish retrospective from as-issued evidence. [Model card](docs/MODEL_CARD.md)
- Keep tests, coverage, audit checks, action pins and failure conditions intact. In a clean Python 3.12 Linux environment regenerate both locks with `scripts/lock_requirements.py` after audit-driven dependency changes. Use Ruff's 110-character line length, LF and British spelling.
- Before a commit, check the staged diff and `git status`. Keep tokens, private identifiers, `.env`, Azure inputs, state, plans and provider caches out of Git. Attribute AI-assisted work to the tool and model used. [Security](SECURITY.md)
- The live Cloudflare service and the Python deployment are separate. For authorised Azure work follow the [deployment guide](docs/DEPLOYMENT.md). Release claims require saved results from the platform in question.
