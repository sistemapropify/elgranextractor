# ACM nearest comparables - release 2026-10-12

Status: Validated - deployment dispatch authorized

## Authorized scope
The user explicitly requested production deployment on 2026-10-12.
Apartments, offices and land now use the nearest eligible properties by default:
all for 1-3 candidates, 3 for 4-15, 4 for 16-30, and 5 for more than 30.
Radius, quality and exclusion filters apply before selection. Recalculation
selects the next nearest eligible records. The table and valuation use only
selected comparables; the remaining properties belong to the reference layer.

## Existing deployment recipe
Push to main triggers .github/workflows/main_granextractorservice.yml.
App Service: granextractorservice; resource group: rg-elgranextractor;
region: Brazil South; subscription: 0219eecc-9920-4789-9929-3091a2f09daf.
Public endpoint: https://acm.propifai.com/acm/analisis/
No infrastructure, dependencies, permissions or database schema changes.

## Integration and validation
Base/latest origin/main and served shared checkout:
f6a3d086d8a9699d43f26e234cb2bc62ad19ad36.
All six application/test files match D:/PROMETEO byte for byte.
Preserve unrelated Cuadrantizacion changes and untracked files.
- 56 relevant Django tests passed (components, report selection, references).
- Node presentation tests, JavaScript syntax and git diff checks passed.
- Served local page and both JavaScript assets return HTTP 200.
- Local page loads components.js v53 and presentation.js v11.
- Real local browser: 91 apartments found, 5 selected, 86 references at 500 m.
  Both map layers enabled; comparable table retains only the five selected rows.

## Deployment handoff
Fetch latest main before the non-forced push. The user explicitly asked to
handle monitoring and production verification themselves. Do not poll the
workflow or claim confirmed live status after dispatch. CI includes deployment
and public health/static checks. Report the workflow link and pending status.

---

# Publication capture — release 2026-10-11

Status: Validated — deployment pending

## 1. Authorized scope
The user explicitly authorized production publication on 2026-10-11 and asked
not to monitor: the user will follow the pipeline and verify production.
Publish full-page capture for Properati, Remax, Urbania, Adondevivir and
Facebook Marketplace, opening inline maps when necessary, private Blob archive,
capture URL/date in each record and the table/viewer, preservation of earlier
captures, and the scraper table's Estreno label for age zero.
Captures apply to new jobs; preview and listing-only do not archive a detail.

## 2. Deployment recipe and existing target
Existing CI/CD: .github/workflows/main_granextractorservice.yml, push to main.
App Service granextractorservice, rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Endpoint: https://acm.propifai.com/ingestas/scraping/dashboard/
No new infrastructure, dependencies, roles or database schema. Capture metadata
uses existing datos_crudos; files use propiedadesimagenes/capturas/.

## 3. Integration and preview
Base/latest origin/main/shared HEAD: 9528326376442f81187abde0ba7aa4778fd54125.
All 18 release application/test files match the served D:/PROMETEO checkout.
Preserve unrelated Cuadrantizacion changes and untracked files.
Non-forced push only; fetch immediately before dispatch.

## 4. Validation
- [x] 98 isolated Django tests passed: capture across all five adapters, map
  click order, auth, SAS expiry, persistence, cancellation, gallery and recovery.
- [x] Two capture-view tests passed after final URL validation tightening.
- [x] Python AST and embedded browser JavaScript syntax checks passed.
- [x] makemigrations ingestas --check --dry-run: no schema changes.
- [x] Rendered table has 36 columns, capture link/date, and Estreno for zero.
- [x] Capture viewer escapes titles; unavailable map/scroll status is visible.
- [x] Local HTTP page and static assets 200; served JavaScript matches source.
- [x] Native browser: capture checkbox checked, Capture column, authenticated
  capture view, existing-record empty state verified.
Infrastructure provisioning, what-if and role changes are not applicable to this
code-only update using the existing storage configuration and deployment identity.

## 5. Execution and verification handoff
Commit only the 18 release files and this record, then push main to trigger the
existing pipeline. At the user's explicit request, do not monitor its progress
or report the new functionality live without verification. Supply the Actions
workflow link; user will monitor and verify the public page/assets. The pipeline
itself builds, collects static files and checks production startup and health.
Rollback is a revert through the same pipeline.

## 6. Runtime configuration
Preserve all existing settings and secrets. Viewer generates 30-minute SAS
access on demand; responses are private/no-store. No signed URLs are stored.

## 7. Validation proof
Azure Validate applied actual checks on 2026-10-11:
manage.py test ingestas.tests.test_publication_capture ingestas.tests.test_photo_gallery
 ingestas.tests.test_scraping_integrity ingestas.tests.test_scraping_job_reporting
 ingestas.tests.test_scraping_recovery ingestas.tests.test_facebook_marketplace_scraper
 scrapi.test_properati_age --settings=ingestas.scraping_test_settings --noinput:
98 tests passed; system checks clean. Final CaptureViewTests: 2 passed.
makemigrations --check --dry-run: no changes. AST and node script checks passed.
Local HTTP 200 and authenticated browser checks passed; screenshot
scraper-captura-opcion-local.jpg. Real Properati map opened and full-page image
verified; other adapter flows tested with mocked pages and Blob uploads.
No new bulk live scrape or production data backfill was started.

---

# Previous release record (preserved)

# Scraper galleries and Properati construction age — release 2026-10-11

Status: Validated — deployment pending

## 1. Authorized scope
The user explicitly requested production deployment on 2026-10-11.
Publish the local all/cover/none photo modes, Azure Blob photo archive,
authenticated on-demand gallery in the scraper and ACM detail, preservation of
previously archived photos, and Properati construction-year conversion to age.
For extraction in 2026, 2006 becomes 20 years and 2010 becomes 16 years.
Existing records require re-extraction to fill previously missing photos or age.
No bulk scraping or data backfill is included in this deployment.

## 2. Deployment recipe and target
CI/CD: .github/workflows/main_granextractorservice.yml, non-forced push to main.
Existing App Service granextractorservice, resource group rg-elgranextractor,
subscription 0219eecc-9920-4789-9929-3091a2f09daf, Brazil South.
Public endpoints: https://acm.propifai.com/acm/analisis/ and
https://acm.propifai.com/ingestas/scraping/dashboard/ (authenticated).
Use existing private Blob container and configured storage helper.
No infrastructure, role, dependency, schema or runtime-setting changes.
Existing CI/CD federated identity and previously authorized target remain valid.

## 3. Integration and local preview
Base / origin/main / shared HEAD: 85fcd53de2c3972c3347826f84c2bbeae3a0b2d5.
Base Actions run 38082400130 succeeded. All 24 application and test files match
D:/PROMETEO byte-for-byte. Preserve unrelated shared Cuadrantizacion edits and
untracked files; fetch again before push and never force-push.

## 4. Validation steps
- [x] Fetch and compare production base and successful pipeline.
- [x] 97 isolated Django tests: gallery, persistence, access, job recovery,
  dashboard, Facebook, Properati age and location, existing detail age.
- [x] Parse changed Python files; node --check components.js; diff --check.
- [x] Isolated collectstatic; changed JavaScript matches collected output.
- [x] Local HTTP ACM and versioned JavaScript 200 and source match.
- [x] Existing Azure target Running in the intended subscription / region.
Infrastructure, template what-if, new-role and provisioning checks are not
applicable to this code-only CI/CD release. Storage uses the existing helper.

## 5. Execution and rollback
Commit the 24 release files and this record. Push main; monitor build/deploy to
completion. Verify public HTML, versioned assets, authenticated gallery route,
health and deployed Properati/gallery source before reporting success.
Rollback is a revert commit through the same pipeline.

## 6. Runtime configuration
Preserve all existing application settings and secrets. Gallery SAS URLs are
created on demand with 30-minute expiry and are not saved in records.

## 7. Validation proof
Azure Validate performed actual checks on 2026-10-11:
manage.py test ingestas.tests.test_photo_gallery ingestas.tests.test_scraping_integrity
 ingestas.tests.test_facebook_marketplace_scraper ingestas.tests.test_scraping_recovery
 ingestas.tests.test_scraping_dashboard_state scrapi.test_properati_age
 scrapi.test_detail_age scrapi.test_properati_location
 --settings=ingestas.scraping_test_settings --noinput: 97 passed; system check clean.
Python ast.parse for every changed Python file and node --check: passed.
Isolated django collectstatic: passed; components.js byte match.
Local /acm/analisis/ and /static/acm/js/components.js?v=52: HTTP 200.
Azure webapp show: Running, Brazil South, intended target.
Earlier native local gallery verification loaded all 7 archived images and
verified next/thumbnail navigation; screenshot scraper-galeria-local.jpg.
Photo uploads tested with real PNG bytes and mocked SDK; no bulk live scrape.

---

# Previous release record (preserved)

# ACM move pin and new analysis — release 2026-10-10

Status: Validated — deployment pending

## 1. Authorized scope
The user explicitly authorized production deployment of the locally tested
Mover pin y recalcular and Nuevo ACM buttons on 2026-10-10.
The buttons are stacked beneath the collapsed search card. Reopening preserves
all entered parameters and unlocks the target pin; Nuevo ACM clears parameters,
analysis, selections and map state by restoring defaults and reloading.

## 2. Deployment recipe and existing target
CI/CD: .github/workflows/main_granextractorservice.yml, non-forced push to main.
Existing Azure App Service granextractorservice, resource group
rg-elgranextractor, subscription 0219eecc-9920-4789-9929-3091a2f09daf,
Brazil South. Endpoint: https://acm.propifai.com/acm/analisis/
No infrastructure, dependencies, roles, schema or runtime settings changes.

## 3. Integration and local preview
Base, origin/main and shared local HEAD: 61710d8765b97b01bb712162164c86f712272baa.
Base deployment run 38068208504 completed successfully.
The three UI files match D:/PROMETEO byte-for-byte. Preserve unrelated shared
Cuadrantizacion edits and all untracked files. Fetch immediately before push,
integrate any newer revision, and never force-push.

## 4. Validation
Azure Validate applied to the current release:
- Eight isolated ComponentsEndpointTests passed; system check clean.
- node --check components.js and Git whitespace checks passed.
- Isolated collectstatic produced matching CSS and JavaScript.
- Local HTTP page and versioned assets returned 200 and matched source.
- Existing Azure target verified Running under the intended subscription.
- Native local browser verified collapse, both stacked buttons, reopening with
  preserved values, target-pin movement, another search/collapse, and Nuevo ACM
  returning blank fields, default Casa/500 m, no result and no selected cards.
Infrastructure, what-if and RBAC change checks do not apply to this UI-only update.

## 5. Execution and rollback
Commit only components.html, components.css, components.js and this record.
Push main, monitor CI/CD to completion, verify public HTML, exact updated static
content and health, then report live. Rollback is a revert through the pipeline.

## 6. Runtime configuration
Preserve all existing Azure application settings and secrets.

## 7. Validation proof
All checks above passed on 2026-10-10. New assets: components.css?v=32 and
components.js?v=51. Browser screenshot: acm-mover-pin-nuevo-acm.jpg.

---

# Previous release record (preserved)

# ACM comparables and reports — release 2026-10-10

Status: Validated — deployment pending

## 1. Authorized scope
The user explicitly requested deployment on 2026-10-10.
Publish the locally reviewed comparable-card filtering, selected-radius map pins
and visible circle, PDF/Word/HTML report dropdown, HTML export, target-pin lock
and collapsible search form, and removal of portal codes from property cards.
Automatic selection of the nearest 3–5 properties was proposed but is not
implemented in this release. Preserve the existing calculation engine.

## 2. Deployment recipe and existing target
Recipe: CI/CD via `.github/workflows/main_granextractorservice.yml` and a
non-forced push to main. Existing Azure subscription
0219eecc-9920-4789-9929-3091a2f09daf; App Service granextractorservice;
resource group rg-elgranextractor; Brazil South.
Public endpoint: https://acm.propifai.com/acm/analisis/
No infrastructure, role assignments, dependencies, or database schema changes.
Existing runtime secrets and independently prepared worker infrastructure remain
outside the release scope.

## 3. Integration and local preview
Production revision, origin/main, worktree base, and shared local HEAD:
1c282e076f358a31cc8e06c26e11252831e8655c.
Base production Actions run 38004027726 completed successfully.
All 11 requested application files are identical in this worktree and
D:/PROMETEO. Preserve the shared checkout's unrelated Cuadrantizacion edits
and untracked files. Fetch again immediately before publication; integrate any
new upstream revision before pushing. Never force-push.

## 4. Validation steps
- [x] Compare latest main and successful production revision.
- [x] Run 45 isolated Django regression tests.
- [x] JavaScript syntax and comparable/radius presentation tests.
- [x] Isolated collectstatic; byte-match all three changed assets.
- [x] Confirm Azure authentication and existing App Service Running.
- [x] Final local HTTP page and static byte checks.
- [x] Final staged scope and whitespace checks.
Resource-template, what-if, policy and RBAC-change validation do not apply to
this application-only release through the configured pipeline.

## 5. Execution and rollback
Commit only the 11 requested ACM files and this release record. Push to main,
monitor the existing build/deploy pipeline, then verify the public page, updated
static content, and health endpoint before reporting the release live.
Rollback, if needed, is a new revert commit through the same pipeline.

## 6. Runtime configuration
Preserve the existing Maps Static API key and all runtime app settings.
No secret values are included in the release artifact or validation output.

## 7. Validation proof
Azure Validate applied on 2026-10-10:
- manage.py test acm.test_components.ComponentsEngineTests
  acm.test_components.ComponentsEndpointTests acm.test_report_selection
  acm.test_primary_reference --settings=acm.components_test_settings --noinput:
  45 passed; system checks passed. Expected mocked PDF 403 cases passed.
- node --check components.js and components-presentation.js: passed.
- components-presentation.test.cjs: passed, including comparable-only cards
  and target/reference/house-soil radius rules.
- Isolated Django collectstatic: components.css, components.js and
  components-presentation.js collected and byte-matched to source.
- Azure read-only target query: Running, correct subscription and region.
- git diff --check and git diff --cached --check: passed; only the 11 ACM
  files and this release record are staged.
- Final local page and all three versioned assets: HTTP 200 and byte matches.
- Prior local native browser checks passed: dropdown PDF/Word/HTML,
  actual HTML download, visible circle, form collapse and pin lock/unlock.

---

# Previous release record (preserved)

# ACM valuation controls — release 2026-10-09

Status: Validated — restore button follow-up release; deployment pending

## 1. Authorized scope
The user approved publishing the locally reviewed ACM changes on 2026-10-09.
Release the comparison table selection, distance and publication columns, manual
valuation dial, rounding switch, and selected-only property reports without codes.
Preserve the existing dark table styling and inline similarity percentages.
The user also approved deploying the follow-up Restablecer button on 2026-10-09.
It restores the exact computed total, clears manual report overrides and rounding,
and preserves property selection. Publish the four reviewed UI files for this update.

## 2. Deployment recipe and existing target
Recipe: CI/CD, existing `.github/workflows/main_granextractorservice.yml`.
Push the reviewed release commit to `main` to use the existing federated Azure login,
build, collectstatic, App Service deployment and verification pipeline.
Target: `granextractorservice`, resource group `rg-elgranextractor`, Brazil South.
Public page: https://acm.propifai.com/acm/analisis/
This code release changes no infrastructure, dependencies or database schema.
The PDF server map key was separately configured through runtime settings, not Git.
The scraping-worker preparation below is independent and retains its original gates.

## 3. Integration and local preview
Origin main and shared local HEAD are both `fb8720dd7405f174bbe0915c6f31da66d5cf661d`.
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

## 6. PDF maps runtime configuration
Maps Static API is now enabled and a working server key is configured through
`GOOGLE_MAPS_STATIC_API_KEY` locally and in Azure. The secret is excluded from Git.
Real Google requests returned HTTP 200 from local and Azure execution environments.
The generated PDF was rendered and inspected: all four requested map images appeared.
This existing runtime configuration must be preserved by the code deployment.

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

Follow-up release validation (2026-10-09):
- Base deployment `37970833325` completed successfully on `fb8720dd`.
- Native browser fixture for Restablecer passed: footer/sidebar original totals,
  no manual override in the report, rounding cleared, selection preserved,
  placement beside the switch, white text and inline percentages preserved.
- Local application, map layers endpoint and updated script: HTTP 200.
- Repeated JavaScript syntax, Git whitespace and native browser checks passed.
- Updated static assets collected successfully; all four UI files match the shared
  local checkout. Commit scope is those four files and this release record.

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
