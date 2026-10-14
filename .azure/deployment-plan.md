# Complete-district Catastro collection - release 2026-10-14

Status: Validated - correction to the Catastro publication requested by the user
Recipe: CI/CD, existing GitHub Actions pipeline

## Scope and existing target
Remove the user-facing record quantity selector and default to every property
found in the selected district. One execution streams internal groups of 100
geometries and persists inventory, archived and remaining counts. Keep optional
bounded CLI/skill tests, administrator/CSRF access, stop and resumption.
Remove the initial 1 GB archive cap. In Azure keep the ledger and pending working
copies; after verified R2 upload remove only new working files, preserving existing
review copies. Read full indexes, original PDFs and images directly from private
R2 when no local copy exists. Missing individual galleries remain pending while
the collector continues to the other properties. Denied access and connection or
storage failures stop collection with its progress preserved.
Base main 25ed5a80659fd5397cec10ddd65bdfa6d9afff72. Same existing App Service,
subscription, region, R2 settings and directory /home/data/catastro. No new
resources, roles, dependencies, credentials or SQL Server migrations. SQLite job
progress columns are additive and preserve existing jobs and property records.

## 7. Validation Proof
azure-validate completed 2026-10-14, America/Lima:
- 17 collector tests passed, including a single 503-property run beyond the old
  500 ceiling, streamed source groups, default unlimited job, persisted stop/
  progress, R2-only retry without source redownload, unavailable galleries,
  transient upload retries and preservation of existing review files.
- 8 isolated Django view tests passed, including whole-district API default,
  administrator/CSRF protections and reading private PDF/page/index from R2
  without any Azure file copies. Wrong-property remote index rejected.
- JavaScript syntax, source whitespace checks and both templates passed.
- Production WSGI and collectstatic passed with isolated SQLite; release assets
  byte-match source. Local CSS/JS HTTP 200 and exact source byte matches.
- Local authenticated browser confirmed no quantity selector, correct full-
  district action and updated storage copy. Screenshot saved locally.
- Shared D:/PROMETEO served checkout updated only for these Catastro files;
  previous versions backed up and unrelated edits retained.
- Existing Azure target and deployment authorization established in the previous
  release. Runtime R2 settings and uploaded pilot indexes are retained.

## Execution and verification
Publish this correction through the already-authorized Catastro production
pipeline, fetching main and integrating newer revisions without force push.
No prolonged monitoring; user performs visual production verification. A bounded
public asset check must report pending rather than live until bytes match.
Rollback is a new revert commit; preserve the archive and additive job columns.

---

# Catastro archive dashboard - release 2026-10-14

Status: Validated - user explicitly requested production publication
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
Publish the Catastro dashboard, individual document viewer with original PDF lines,
field extraction, private original-file access, bounded resumable collector and
Geollaqta skill. Preserve the cadastral map in Cuadrantizacion and all other modules.
Latest main and successful production revision: af610a4561f8fbf0dc691e919b927c32285b58e4,
workflow 38590373658. Existing App Service granextractorservice / rg-elgranextractor,
Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
No new infrastructure, roles, dependencies or application database migrations.
Use existing private R2 bucket prometeo-catastro and its scoped credentials through
Azure application settings. CATASTRO_DATA_DIR=/home/data/catastro persists the SQLite
work ledger and current JSON indexes. Import the 12 reviewed pilot indexes and a
consistent SQLite backup; leave original PDFs/photos in R2 and use authenticated
GET fallback. Refuse overwriting existing cadastral data/configuration.

## 7. Validation Proof
azure-validate completed on 2026-10-14, America/Lima:
- python -m unittest catastro.test_collector -q: 12 passed (resumption, all gallery
  documents, PDF field mapping, inventory completeness, R2 retries, batch scope).
- manage.py test catastro.test_views --settings=catastro.test_settings: 6 passed
  (administrator access, CSRF, private allowlisted originals, original PDF pages).
- Production WSGI and both Catastro templates compile with isolated SQLite.
- collectstatic passed; Catastro CSS/JS byte-match source; node --check passed.
- Local authenticated dashboard, new property, pending document names and original
  rendered PDF page verified. Local CSS HTTP 200. 10 new Yanahuara properties
  archived with successful interrupted-upload recovery; totals 12 properties,
  34 PDFs, 20 images. Source errors remain explicitly pending.
- Sample R2 GET originals and current JSON SHA256 match the local archive.
- origin/main fetched; current branch starts at latest production af610a45.
  Only three tracked integration files changed; all other shared local edits retained.
- Azure account and existing Running App Service confirmed; Kudu active deployment
  status 4. R2 settings are not yet configured on production. Authenticated Entra
  SCM access confirmed; Basic authentication remains unchanged.
- Resource template, what-if and new role checks do not apply to this existing
  app-only release. Existing federation and production pipeline remain unchanged.

## Execution and rollback
Runtime setup completed: 12 pilot indexes and consistent SQLite ledger imported into
/home/data/catastro; every remote index and ledger SHA256 verified. Private R2
application settings confirmed without printing credentials; other settings retained.

Configure only the required private R2 settings while preserving all existing app
settings. Import the ledger/indexes into a new persistent directory and verify
SHA256 before publishing. Push scoped source changes to main without force;
re-fetch and integrate newer main if needed. The user requested no prolonged
monitoring and will perform visual production verification personally. Do a
bounded public route/static check and report pending if the release is not yet
served. A rollback uses a new revert commit; retain archived data and R2 originals.

---

# Catastro in Cuadrantizacion only - release 2026-10-14

Status: Validated - production publication explicitly authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
Publish the reusable Arequipa cadastral module and district selector in Cuadrantizacion. Remove the Catastros card, initialization and cadastral assets from ACM. Preserve the ACM nearest places feature from main and all unrelated shared-checkout edits. Source release commits: 24a9ae0f and 59302185, on main 0f9f961d. Last successful production revision: 6294e1c9 (workflow 38320568638). The prior 0f9f961d workflow 38578210956 built successfully but deployment failed with 409 conflicts.
Existing target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf. No new resources, roles, secrets, dependencies or database migrations. Serialize production pipelines and cap the ML worker log at four files of 5 MiB to prevent the diagnosed disk exhaustion.

## 7. Validation Proof
azure-validate completed on 2026-10-14, America/Lima:
- 29 isolated Django cadastral and ACM replication tests passed.
- Four Node suites passed: provider for ten districts, district switching, cache, pan/zoom, geometry and facade gallery including skipped suffixes.
- Production WSGI and all three page/panel templates compile with isolated SQLite.
- collectstatic passed; six cadastral and ACM JavaScript/CSS release assets byte-match source.
- Local ACM HTTP 200 confirms Catastros card and its asset references removed; nearest places card retained. Updated ACM JavaScript assets return HTTP 200 and match source.
- Live COFOPRI geometry queries verified real sample lots for all ten published districts; report galleries checked without exposing personal data.
- Shared D:/PROMETEO changes integrated surgically, retaining unrelated ACM edits. Source whitespace checks passed.
- Worker stream rotation: two tests passed for bounded output without newlines and intact multibyte text. Workflow serialization YAML parsed successfully.
- origin/main fetched; no newer revision beyond 0f9f961d. Azure existing subscription and Running App Service confirmed.

## Execution and recovery
Publishing authorized by the user's current instruction. Push to main without force after integrating any newly advanced revision. The prior pipeline's 409 failures require resolving the existing App Service deployment issue before retrying. A read-only SCM diagnostic found /home at 100 percent of its 10 GB capacity. The 5,512,251,623-byte ML worker log was backed up locally with verified SHA256 c9dfab7965977745a90c3e33bd87cd77f8faf804d70683d9c1f75b35fc1ae7c6. Archive its remote copy outside the full persistent volume; preserve application data. Recovery confirmed: the historical log was moved out of /home, the service restarted to release open handles, and /home now has 5.2 GB available (49 percent used). The archive in SCM temporary storage was cleared by the restart; the verified durable local backup remains in D:/PROMETEO/outputs/azure-deployment-recovery-20261014. Bash startup syntax, worker log rotation tests and workflow YAML validation passed. No blanket recursive deletion. User preference remains no prolonged deployment monitoring and personal visual verification. Confirm actual publication through a bounded public page/static check; do not call dispatch itself a successful publication.

---

# ACM nearest places - release 2026-10-14

Status: Validated - publication explicitly authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
Publish only the ACM nearest places card: police, healthcare, shopping mall and
school, walking/driving route distances and minutes, configurable radius,
blue/yellow/red distance ranges and optional route drawing. Use the existing
Maps key and the Places (New) and Routes APIs enabled with the user's consent.
Base main and latest successful production workflow: 6294e1c9 / 38320568638.
Target remains granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf. No infrastructure, roles,
secrets, dependencies or migrations change. Preserve unrelated shared ACM work.

## 7. Validation Proof
azure-validate completed on 2026-10-14, America/Lima:
- Node nearby-place suite passed: thresholds, four categories, nearest route,
  walking/driving, traffic, cache, denied API, login and stale-pin cancellation.
- Syntax checks passed for components.js and floating-comparison.js.
- Production WSGI and both ACM templates compile using isolated SQLite.
- collectstatic succeeds; all four release assets byte-match their sources.
- Shared local ACM and four assets return HTTP 200; new card is included.
- Google APIs report ENABLED; real Places and Routes requests with the existing
  browser key returned 200, including a 291 m walking route from a public point.
- Azure subscription and existing Running App Service verified; existing
  federation, resource location and startup settings preserved.
- Main fetched and scoped changes reviewed; no upstream revision advanced.

## Execution and handoff
Commit scoped files and push to main without force. The existing pipeline
performs build, deployment and health verification. The user explicitly requested
no deployment monitoring: dispatch the release and proceed with the next task.
Do not poll CI, create an automation or declare the change live before public
assets confirm it. A single later HTTP check may establish the release status.
Rollback is a revert through the same pipeline. Further cadastral district
changes are local-only until separately authorized for publication.

---

# Catastros gallery facade correction - release 2026-10-12

Status: Validated - correction of production explicitly requested
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
The gallery previously embedded and linked the COFOPRI report, displaying its
cadastral record table before the photo. Show verified facade images directly;
photo clicks open the image URL. Put report and individual-record links in a
separate Ficha catastral section. Preserve vector navigation and ACM defaults.
Base: published main b56173a3; successful workflow 38317158997. Preserve all
other local ACM work in D:/PROMETEO. Existing granextractorservice target and
federation retained; no database, dependency, role or infrastructure changes.
Existing WEBSITES_CONTAINER_START_TIME_LIMIT=900 verified and preserved.

## 7. Validation Proof
azure-validate completed on 2026-10-12, America/Lima:
- node --check webapp/static/js/geollaqta-map.js passed.
- test_geollaqta_geometry.cjs: 12 geometry/transport checks passed.
- test_geollaqta_loading.cjs: 10 navigation/failure checks passed.
- test_geollaqta_gallery.cjs: 8 gallery regression cases passed, including
  image-only gallery links, separated records, missing images, multiple photos
  and late events from a previously selected lot.
- Production WSGI and both page templates compile with isolated SQLite;
  collectstatic succeeds and both changed assets byte-match their sources.
- Shared local HTTP serves JS v5 / CSS v4; unrelated local changes preserved.
- Browser transport shows the real sample 04012607042018 facade (448 pixels
  wide); gallery href is its JPG and the report resides in Ficha catastral.
- COFOPRI reports verified for 04012607042018, 04012607042017 (two photos),
  and the user's open report 04012607041008. Primary and numbered image paths
  match the published report URLs. Photos are displayed only after successful
  image loading; extra discovery stops at the first missing suffix, maximum 12.
- Azure subscription and existing Running App Service verified. No new RBAC
  assignments or provisioning; existing startup timeout remains 900 seconds.

## Execution and verification
Commit the seven scoped files and push to main without force, after rechecking
main. Monitor CI and verify public JS v5, CSS v4 and their release hashes,
page markup, application health, and real facade links if the browser's public
session is available. Never create production users or sessions for testing.
Rollback via a revert through the same pipeline. Keep other shared local work
unpublished. Verification evidence lives in outputs/geollaqta-release-validation.

---

# Catastros COFOPRI Yanahuara - release 2026-10-12

Status: Validated - production publication explicitly authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and existing target
Publish the reviewed Catastros card in Cuadrantizacion and the optional,
default-off floating card in ACM. Include roads, lots, blocks, commerce and
construction floors 01-06, plus the original COFOPRI report/gallery links.
Scope all layers to Yanahuara UBIGEO 040126. Preserve other local ACM work.
Use existing granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf. No new resources, roles,
dependencies, configuration secrets or database migrations.

## Integration and validation steps
Latest production and origin/main: c31f75bf7699ee45f4f927366713b7790ea405a5,
successful workflow 38302615909. Publish only this task's changes on that base.
Other shared-checkout ACM edits are unpublished and must remain local.
- [x] Confirm Azure subscription, Running target and latest successful pipeline.
- [x] Compare release scope with main and preserve shared checkout changes.
- [x] Run isolated backend, geometry and ACM replication regression tests.
- [x] Compile production WSGI with isolated build databases and collect assets.
- [x] Verify the production browser transport in the served local preview.
- [x] Final whitespace, scoped source, static asset and JavaScript checks.

## Runtime integration
Azure's outbound IP times out connecting to both COFOPRI hosts, while an
independent GitHub control request succeeds. COFOPRI reflects the public
application Origin in its CORS response and its report allows framing.
Production therefore authorizes configuration through PROMETEO, reads public
geometry from the user's browser, and embeds the original report/gallery in
the selected lot card. The existing server transport remains available locally.
Both transports retain district filtering, viewport limits, 500-record batches,
1,000 features per layer, partial-load and missing-geometry messages.

## 7. Validation Proof
Validation completed under azure-validate on 2026-10-12:
- 24 isolated backend/ACM replication tests passed (acm.history_test_settings).
- 12 geometry/transport cases and 10 pan/zoom/failure regression checks passed
  in the Node test runner. Existing vectors remain during reloads and at zoom
  below 17. Buffered viewport cache avoids repeated small-pan/zoom-in queries.
- JavaScript syntax checks passed for all four changed modules.
- Production WSGI imports and collectstatic passed with isolated SQLite build
  databases; five release assets byte-match their collected versions.
- Served browser transport displays 519 real lots; panning and zooming in
  retains the loaded vectors. The sample original report and photo load in the
  iframe (image naturalWidth 448). ACM starts with its checkbox disabled.
- The user will verify the authenticated public map personally after release;
  verify public HTTP, assets and default-off ACM card without creating sessions.
- Azure reports the authorized App Service Running. No RBAC or infrastructure
  templates change; the existing workflow federation and settings are preserved.

## Execution and rollback
After validation, commit the scoped release and push to main without force.
If main advances, integrate and revalidate first. Monitor the workflow and verify
the public ACM page, protected-route authentication and static hashes before
declaring the change live. The real lot/gallery are verified locally using the
production browser transport; the user will check the public map in their session. Rollback is a revert through the
same existing pipeline. No production SQL fixtures or sessions are created.

---

# ACM history replication - release 2026-10-12

Status: Validated - publication explicitly authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
Publish the locally reviewed Replicar ACM history action. Restore saved target
GPS coordinates, property type, areas, radius, sources and optional features;
load an editable form and search current comparables only after user submission.
Keep the original history unchanged and reject records without valid inputs.
Owner-scoped authenticated access protects saved coordinates. Nuevo ACM returns
to a clean form. No database migrations, dependencies or infrastructure changes.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription
0219eecc-9920-4789-9929-3091a2f09daf. Preserve existing federation and app settings.
Public history: https://acm.propifai.com/acm/historial/

## Integration and validation checks
Latest origin/main e1f53af1 has no changes beyond the base of application commit
d37ad4bf. The nine application files match the served D:/PROMETEO preview.
Preserve unrelated Cuadrantizacion edits and untracked files in that checkout.
- [x] Fetch and compare main; review exact release scope.
- [x] Run isolated history, valuation, component and report tests.
- [x] Check JavaScript syntax and collect the updated static asset.
- [x] Verify local history-to-form navigation and Nuevo ACM reset.
- [x] Confirm the existing Azure target and deployment pipeline.

## 7. Validation Proof
Azure Validate applied on 2026-10-12 at 15:10 America/Lima:
- 64 isolated tests passed with acm.history_test_settings.
- node --check webapp/acm/static/acm/js/components.js passed.
- Production settings static collection passed; collected components.js
  byte-matches source. WSGI imports with an isolated in-memory build database.
- Local HTTP page and components.js?v=55 returned 200; native browser confirmed
  restored areas/radius, map center matching saved GPS and clean Nuevo ACM reset.
- Azure CLI confirms the authorized subscription and Running App Service.
- Existing workflow collects static files, validates startup and deploys to the
  Production slot. No new roles or infrastructure templates are introduced.

## Execution and handoff
Push non-forced to main to dispatch main_granextractorservice.yml. The user
handles monitoring: do not poll CI or claim the new button is live before it
finishes. Provide the workflow link and public history URL. Rollback uses a
revert commit through the same pipeline.

---

# Private ML dataset Blob archives - release 2026-10-12

Status: Validated - execution and publication authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## Authorized scope and target
The user explicitly requested execution of the locally reviewed archive in
production. Keep the five latest cuts and every training-linked cut in SQL.
Copy older entries to private Azure Blob, download and verify SHA-256,
complete decompression and row count before atomic SQL pruning plus manifest.
No business conversations, lead/agent/bot records, source observations,
properties or ACM histories are pruned. No SQL SKU or quota changes.
Use existing granextractorservice / rg-elgranextractor, subscription
0219eecc-9920-4789-9929-3091a2f09daf. Storage uses existing app credentials and
private ml-dataset-archives container. No new schema or production dependency.

## Integration
Base origin/main 66ef58a01cea355b8869728b716f569176b738fc.
Application commit 2e501703 is reviewed and integrated byte-for-byte in the
shared D:/PROMETEO preview. Preserve unrelated Cuadrantizacion edits.

## 7. Validation Proof
Validated at 2026-10-12T19:07:45.561485+00:00 under azure-validate for existing CI/CD recipe.
- 24 targeted isolated Django archive tests pass in the shared checkout.
- SQL rollback, corrupt or missing Blob, retention, restore, immutable upload,
  private container, historical CSV equality and training reader are covered.
- 3 older unrelated spatial/candidate test failures reproduce on the base.
- Current Python AST and git whitespace checks pass.
- Bounded 200-row keyset reads, separate observation/spatial lookups and
  minimal observation evidence avoid whole-cut SQL joins and repeated source
  descriptions. The original observations remain intact in SQL.
- Regression verifies complete archiving/restoration across the 200-row boundary.
- SQL pruning also uses 200-row statements within the same atomic transaction;
  verified count and rollback guarantees are unchanged. 24 tests pass.
- Production synchronous auto-statistics caused timeouts; SQL now updates
  statistics asynchronously at low priority (no price or capacity changes).
- First six cuts verified and archived: 31,590 SQL rows relocated; a current
  FILEPROPERTY reading confirms 59.562 MB reusable within the 2 GB data file.
- Local authenticated /acm/modelos/ displays 111 eligible cuts, archive disabled.
- Local /acm/analisis/ and its CSS static assets return HTTP 200.
- Azure account matches the existing subscription; App Service is Running.
- One-off Azure maintenance uses production credentials in memory, TLS,
  release codec and private Blob implementation, SQL dataset-worker locking,
  retention recheck, full read-back verification and per-cut transaction.

## 8. Execution and handoff
Execute initial backlog in bounded batches from Azure; record actual SQL page
usage before/after. Enable ML_DATASET_ARCHIVE_ENABLED=True for ongoing upkeep.
Non-forced push to main dispatches existing workflow. User handles deployment
monitoring; do not poll CI after dispatch or claim verified live code.

---

# Remax complete gallery extraction - release 2026-10-12

Status: Validated - production dispatch authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## 1. Authorized scope
The user explicitly requested production publication of the Remax photo fix.
Read every Slider Pro property image, including lazy image URLs, in gallery
order. Prefer full-sized photos; exclude placeholders, thumbnails, agents,
related properties and duplicate URLs for the same source image path.
Existing cover/none modes, Blob persistence and publication captures remain.
Existing fichas with only two photos require reprocessing after publication.

## 2. Existing target and recipe
Non-forced push to main triggers .github/workflows/main_granextractorservice.yml.
App Service granextractorservice; rg-elgranextractor; Brazil South;
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public dashboard: https://acm.propifai.com/ingestas/scraping/dashboard/
Existing deployment federation and configuration. No infrastructure, roles,
database schema, dependencies or static asset changes.

## 3. Integration
Latest main/worktree/shared checkout base:
595daf1b366158d208f99a18d26f56d633c05300.
Both application/test files match D:/PROMETEO byte for byte.
Preserve unrelated Cuadrantizacion edits and untracked/private files.

## 7. Validation Proof
Validated at 2026-10-12T16:58:15.753958+00:00 under azure-validate.
- 47 Django tests passed in the preceding implementation turn using
  ingestas.scraping_test_settings: gallery, Remax data/areas and captures.
- Regression coverage verifies lazy/full-size URLs, order, duplicate removal,
  cover fallback and that all five photos reach the mocked Blob uploader.
- Two current publications from job 221 (1200778, 1200727) each expose five
  slider photos; the corrected extractor retrieved five of five in each.
- Python AST, shared-checkout byte comparison and git whitespace checks pass.
- Local ACM page, gallery route and static JavaScript return HTTP 200.
- Current patch reviewed: only Remax gallery parsing and its tests changed.
- Existing pipeline performs build, static collection, startup validation,
  deployment and public health/static checks.

## 8. Dispatch and handoff
Fetch latest main immediately before the non-forced push. The user handles
monitoring under their standing instruction. Stop after dispatch, provide the
workflow link and do not claim confirmed live status without verification.

---

# ACM agent adjustment KPIs and gallery access - release 2026-10-12

Status: Validated - production dispatch authorized
Recipe: CI/CD, existing GitHub Actions pipeline

## 1. Authorized scope
The user explicitly requested production publication of the locally tested ACM
changes on 2026-10-12. Publish original calculated value, agent-adjusted value,
signed percentage variation and adjustment KPIs in the agent's own history;
live original value/variation beside the adjustment knob; and gallery access
on comparable cards. Preserve original calculations and existing reports.
These measure adjustments relative to the ACM, not observed sale-price errors.

## 2. Existing target and recipe
Non-forced push to main triggers .github/workflows/main_granextractorservice.yml.
App Service granextractorservice; resource group rg-elgranextractor;
Brazil South; subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public pages: https://acm.propifai.com/acm/analisis/ and
https://acm.propifai.com/acm/historial/.
Existing OIDC federation, deployment credentials and startup configuration.
No new infrastructure, dependencies, roles or database schema changes.
Metrics use existing immutable result/parameter JSON. Earlier history with
both values derives metrics without rewriting records. Untouched analyses
are excluded from adjustment averages.

## 3. Integration
Latest main/worktree/served checkout base:
887445f8c83c7cc8849fc2a31982c9bf9939764a.
Ten application/test files match the served D:/PROMETEO checkout byte for byte.
Keep unrelated Cuadrantizacion edits and untracked/private files intact.

## 7. Validation Proof
Validated at 2026-10-12T16:31:39.361125+00:00 under azure-validate for the existing CI/CD recipe.
- 61 Django tests passed using acm.history_test_settings: valuation metrics,
  signed component calculations, report selection and primary references.
- Five metrics/history tests passed after final history formatting changes.
- Tests use an isolated SQLite database, with no production fixture writes.
- Python AST, node --check (components.js, comparison-valuation.js), existing
  Node presentation suite and git diff whitespace checks passed.
- Isolated collectstatic passed; JS components/valuation and valuation CSS
  output byte-match the release sources.
- Azure account show confirms the configured subscription above.
- Local ACM page and valuation JS/CSS assets return HTTP 200 and versions
  components.js v54, comparison-valuation.js/css v3; served assets match source.
- Browser history displays actual saved original/agent values and percentages;
  4 comparisons among 10 component ACMs, mean absolute variation 12.65%.
- Browser knob: USD 144,000 original -> USD 144,100 adjusted (+0.07%);
  original stays unchanged; Restore clears the manual adjustment.
- Gallery link from a real local ACM card opened its matching property viewer.

## 8. Dispatch and verification handoff
Fetch main immediately before the non-forced push. CI performs build,
collectstatic, startup validation, deployment and public endpoint/static checks.
The user's standing instruction is to handle monitoring themselves: stop after
dispatch, provide the workflow link, and do not claim confirmed live status.

---

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
