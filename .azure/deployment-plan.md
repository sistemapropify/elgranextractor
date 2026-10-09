# ACM valuation controls — release 2026-10-09

Status: Validated — ACM code release only; deployment pending

## 1. Authorized scope
The user approved publishing the locally reviewed ACM changes on 2026-10-09.
Release the comparison table selection, distance and publication columns, manual
valuation dial, rounding switch, and selected-only property reports without codes.
Preserve the existing dark table styling and inline similarity percentages.

## 2. Deployment recipe and existing target
Recipe: CI/CD, existing `.github/workflows/main_granextractorservice.yml`.
Push the reviewed release commit to `main` to use the existing federated Azure login,
build, collectstatic, App Service deployment and verification pipeline.
Target: `granextractorservice`, resource group `rg-elgranextractor`, Brazil South.
Public page: https://acm.propifai.com/acm/analisis/
No infrastructure, runtime credentials, dependency or database schema changes.
The scraping-worker preparation below is independent and retains its original gates.

## 3. Integration and local preview
Origin main and shared local HEAD are both `5b0f2aa1626e995b2769f5b9c9d809a241702113`.
The previous production workflow for that revision completed successfully.
The requested application files are already identical in this worktree and
`D:/PROMETEO`, which serves the local preview. Preserve unrelated local edits.

## 4. Validation steps
- [x] Fetch and compare the latest production revision.
- [x] Run selected report and manual valuation regression tests.
- [x] Validate both changed JavaScript modules.
- [x] Collect and inspect the new static assets.
- [x] Run final Git whitespace and staged scope checks.
- [x] Read the existing deployment workflow and verify Azure target availability.
Infrastructure and role-assignment template checks do not apply: this release
uses the existing pipeline and changes no resources or roles.

## 5. Execution and rollback
Commit only the ACM release files and this release record. Push without force.
If `main` advances first, integrate that revision before publishing.
After a successful push, provide the Actions run link. The user requested to
monitor deployment personally; do not wait or report it as live before completion.
Rollback, if needed, is a new revert commit through the same pipeline.

## 6. Known limitation
The current server map key returns HTTP 403 because Maps Static API is disabled.
This release supports a separate `GOOGLE_MAPS_STATIC_API_KEY` and corrects PDF
image sizing and selected-property maps, but does not claim to enable Google APIs.
Google key configuration remains pending and is outside this code publication.

## 7. Validation proof
2026-10-09:
- `manage.py test acm.test_report_selection --settings=acm.components_test_settings
  --noinput`: 6 tests passed, including seven selected property pages and map requests.
- `node --check` for `components.js` and `comparison-valuation.js`: passed.
- Local page and new CSS/JavaScript HTTP checks: 200.
- Native browser fixture: selection/pins/report IDs, manual total, wheel and rounding,
  white text and inline percentages passed. PDF layout rendering inspected.
- Azure read-only target query: existing App Service is Running.
- GitHub run `37953595379` for the base revision: completed successfully.
- Isolated Django `collectstatic`: all three release CSS/JavaScript files collected.
- `git diff --check` and `git diff --cached --check`: passed; staged scope contains
  only ten ACM files and this release record. Unrelated shared edits are preserved.

---

# Scraping worker — preparation (independent scope; original record preserved)

Status: Ready for Validation — local preparation complete; not production validated

## Scope and authorization
The user approved implementation of the integral scraper plan on 2026-09-07.
Prepare a reproducible dedicated worker image and validation workflow. Preserve
the current App Service until the image and database migration are validated.
No production migration, deployment, new billable resource, or historical data
rewrite has been performed by this implementation task.

The user is simultaneously modifying other modules. Keep this work in its
isolated worktree. Before any release, integrate against the latest shared
revision and review the exact artifact; never deploy this older full checkout
over newer module work. Coordinate web restart and additive migration separately
from a worker image release.

## Existing environment
- Application: Django/Python, Azure App Service `granextractorservice`.
- Resource group: `rg-elgranextractor`; region observed: Brazil South.
- Existing durable SQL queue and `scraping_watchdog` command.
- Existing source profiles and secrets are supplied at runtime, never copied into an image.

## Architecture
- Django remains configuration/control/reporting.
- Worker consumes the existing SQL queue in an independently deployed container.
- Versioned source URL snapshots, durable candidates and scoped observations.
- Image build installs native libraries, Python requirements and an exact browser release.
- Startup validates availability; it does not install browser dependencies.

## Deliverables and validation
- [x] Worker Dockerfile, pinned browser manifest, entrypoint and smoke check.
- [x] CI workflow for Linux browser launch and isolated SQL Server tests (prepared, not executed).
- [x] Successful CI build and real Linux browser launch, including network-disabled runtime.
- [x] Isolated SQLite and SQL Server database tests; additive migrations 0016–0019.
- [x] Worker/web coordination and rollback instructions in deploy/scraping/README.md.
- [ ] Azure validation before production release.

## Deployment gate
The local host has no Docker/WSL runtime. Linux image build, network-disabled
browser launch and isolated SQL Server tests passed in GitHub Actions run
34240278527 on commit 8122c8cc. Require successful checks on the final release commit.
Deployment target sizing and identity configuration must use the existing Azure
context; do not create a parallel environment implicitly.

## Validation proof

- 105 local tests passed with `manage.py test ingestas.tests scrapi.test_camoufox_launcher
  --settings=ingestas.scraping_test_settings --noinput` in the isolated local runtime.
- `manage.py makemigrations --check --dry-run --settings=ingestas.scraping_test_settings`:
  no model/migration drift. SQLite test databases apply migrations; production untouched.
- Python compilation, dashboard JavaScript syntax, workflow YAML parsing and Git
  whitespace checks passed.
- `python -m scrapi.worker_smoke`: real local Windows browser launch/close and
  pagination DOM checks passed. Python 3.12.14, Camoufox package 0.5.4,
  browser 152.0.4-beta.29, Playwright 1.52.0. This does not certify Linux.
- Live read-only listing probes: Urbania pages 5–6; Remax 32–34;
  Properati beyond page 30 and disabled Next on 33; Adondevivir first page;
  Marketplace scroll reached 144 distinct IDs with a 120-row sample cap.
- Browser archive, Python base image, Microsoft repository bootstrap and SQL test
  image hashes verified from public official registries/releases. Python Linux
  wheels downloaded and recorded with SHA256. Docker build passed in CI.
- Integration branch `codex/scraping-integral-20260908` starts at shared revision
  f4ead8d4. Other modules and the mobile startup migration were preserved.
- Historical repair application and guarded rollback use an atomic SQL journal;
  tests cover dry run, conflicting updates, tampering and rollback after new data.
- Dashboard browser fixture passed locally; final CI also exercises this fixture.
- Worker health is scoped by hostname; metrics export and graceful shutdown implemented.

Production gates remain open: successful final-commit CI, real SQL migration review,
deployment topology/resources and pilot extraction. Initial Linux/SQL validation
and integration against the observed shared revision are complete.
No Azure resource writes, production database migrations or historical repairs
were performed.
