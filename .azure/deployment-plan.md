# ACM PDF PDM layout and mandatory justification - 2026-10-23

Status: Validated
Recipe: existing GitHub Actions App Service pipeline.
Authorization: the user requested moving the PDM zone to the end of the PDF, correcting table widths, and requiring a written justification before PDF emission.
Target: existing granextractorservice / rg-elgranextractor.
Public: https://acm.propifai.com/acm/analisis/

## Scope
Move valuation immediately after the property facts, keep all three market values visible before secondary sections, label the five-card section "Propiedades comparables" in PDF, Word and HTML, and place PDM as the final section after the required justification. Render PDM parameters as a compact four-column grid (two parameter/value pairs per row) instead of a half-page table.
Require a non-blank justification in the ACM before requesting a PDF. The UI opens a blocking modal when the field is empty; the server independently returns HTTP 422 if an API client bypasses the modal.
Add a signature block at the end of PDF, Word and HTML reports: signing space, horizontal line, the agent's complete name centered under the line, and "Agente Inmobiliario" below it.
Allow bounded manifest reads up to 128 MB so large but valid Geollaqta JSON files do not stop the district migration. Add an Azure-side recovery watchdog outside Gunicorn for interrupted leases and expose stale migration state in the dashboard.
Raise the bounded manifest ceiling to 256 MB for lot `04012602082010` (141 MB) and download each manifest in a batch sequentially to avoid concurrent memory spikes on the B2 App Service.
Split the plan inventory's D1 query into bounded source, version, contribution-count and active-geometry queries. The former source/version/contribution join plus JSON extraction exceeded D1 memory and returned `SQLITE_NOMEM`.
Keep global ACM history access for verified superadministrators even while they preview a lower role, and force the history capability on for that verified identity.

## Validation Proof - 2026-10-23 America/Lima
- Rendered the adjusted sample PDF and visually verified A4 portrait, one page, valuation at the top, the explicit "Propiedades comparables" section, justification after the cards, the compact PDM final section and the centered full-name signature block.
- ACM report suite passed: 54 tests, including the comparable-section label in PDF/Word/HTML, PDM order and server-side blank-justification rejection.
- Focused report regression passed after the signature adjustment: 10 tests.
- Located the stalled Yanahuara lot `04012601011003`: its R2 manifest is 66.4 MB and was rejected by the former 20 MB transport cap. The new 128 MB bounded read normalized it to a 401,777-byte D1 payload without writing to production during validation.
- Located the next stalled lot `04012602082010`: its R2 manifest is 141,242,411 bytes. The B2 instance has 3.5 GB RAM; the new bounded read allows 256 MB and uses one manifest at a time.
- Catastro migration tests passed: 13 tests covering bounded large-manifest reads, stale lease recovery, bounded retries, background runner and administrative endpoints.
- The recovery watchdog also retries the observed legacy 20 MB error, with a maximum of three attempts.
- Migration batches are capped at five lots so large Geollaqta property sets stay below D1 Free's transaction limit.
- JavaScript syntax and master migration UI regression passed; `startup.sh` passed `bash -n`.
- Reproduced the plan inventory failure against D1: the combined file query returned `HTTP 400 D1_ERROR: out of memory: SQLITE_NOMEM`; the replacement queries returned 10 sources, 29 versions and 17 contribution groups.
- End-to-end `plans_portfolio` read-only validation returned HTTP 200 with 29 files, 1 project and 1 active district.
- Catastro plan/master tests passed: 52 tests; JavaScript syntax and master UI regression passed.
- ACM identity/history suite passed: 58 tests, including global history for a superadministrator while previewing an agent role.
- JavaScript modal and PDF-download suites passed; updated assets are cache-busted.

---

# Yanahuara R2 to D1 master linkage - 2026-10-22

Status: Validated
Recipe: existing GitHub Actions App Service pipeline plus private Cloudflare D1 Worker.
Authorization: the user requested that the existing Yanahuara data be linked to Catastro Maestro and exposed through ACM and the lateral Catastro menu.
Base: origin/main 5740fed1.
Targets: granextractorservice / rg-elgranextractor; Cloudflare D1 prometeo-catastro-maestro.
Public: https://acm.propifai.com/catastro/

## Scope
Make the extraction path explicit in the Catastro dashboard: COFOPRI -> private R2 manifest and originals -> normalized lot -> Cloudflare D1 -> Catastro/ACM. Add a resumable migration control that processes pending R2 manifests in bounded batches.
Show in Catastro Maestro the stable UUID alias, COFOPRI source code, normalized attributes, GIS source values, owners, media, identifiers and provenance. Let ACM consume the same D1 lot/unit ficha first and fall back to the verified report evidence when a field is absent.
Keep raw PDFs and photographs in R2; D1 stores normalized lot/unit facts, relationships, evidence and R2 object references.

## Validation Proof - 2026-10-22 America/Lima
- Confirmed 5,240 archived Yanahuara manifests in R2 and initially 0 linked entities in D1.
- Fixed Worker commits for `current_attributes`, added its regression test, and deployed the corrected private Worker.
- Completed an audited pilot cleanup and imported one lot plus a 20-lot batch; D1 reported 21 linked lots and 5,219 pending.
- Verified a real migrated ficha returned `land_area=5997.42`, `built_area=29`, floors, report ID, PDF and facade links from D1/R2.
- Added an Azure-side resumable worker with a five-minute D1 lease; closing the browser or turning off the user's computer does not stop an active migration.
- Catastro suite: 69 focused tests passed after the background-worker change; earlier complete Catastro run passed 82 tests. ACM suite: 31 focused cadastral tests passed; broader ACM run passed 55 tests.
- JavaScript syntax and regressions passed for master entity UI, plan dashboard, ACM cadastre, Cayma linkage and Worker D1 transaction behavior.
- R2 service audit: `AREA_TER` has no positive values in the current Yanahuara source layer; `AREA_CON>0` appears in 7 lots across `PLN-00000111782` and `PLN-00000112139`. The UI labels these values as source values without assuming a validated unit.

---

# ACM default location - 2026-10-22

Status: Validated
Recipe: existing serialized GitHub Actions App Service pipeline.
Authorization: the user requested that the ACM marker default to Propify Inmobiliaria instead of the Plaza de Armas.
Base: origin/main 4b2be029.
Target: existing granextractorservice / rg-elgranextractor, Brazil South.
Public: https://acm.propifai.com/acm/analisis/

## Scope
Set the initial analysis coordinates and marker to `-16.38553594297145, -71.54766510511159`. Apply the same fallback center to the legacy ACM map, invalidate both JavaScript files, and add a regression assertion that the old Plaza de Armas defaults cannot return.
No schema, infrastructure, credentials, collector or stored-user-data changes.

## Validation Proof - 2026-10-22 America/Lima
- `acm.test_components`: 40 tests passed, including the rendered default latitude/longitude and absence of the former defaults.
- Exact ACM report/page regression suite passed: 124 tests, Django system check clean.
- `node --check` passed for `acm.js` and `components.js`; age and comparable feature JavaScript suites passed.
- Workflow YAML parsed successfully and now verifies the changed page test plus public `acm.js` exact bytes.
- Public revision, assets and protected endpoints remain mandatory after CI/CD completes.

---

# Catastro Maestro and ACM production release - 2026-10-22

Status: Validated
Recipe: existing serialized GitHub Actions App Service pipeline.
Authorization: the user explicitly requested publication of all Catastro Maestro and ACM changes and improvements.
Base: origin/main 932f1bd3.
Target: existing granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/catastro/maestro/

## Scope
Publish the eleven-stage plan dashboard with titles, dated notes, thumbnails, document lists and stage progress; Geollaqta data as a source consumed by the master; the SQL data model for joining plan codes to stable entity UUIDs; Cayma 2006 plus provisional Sector 32 with the old plan clipped where Sector 32 applies; the drone/satellite raster shared by Catastro and ACM; integer-only ACM values; PDM use-zone tables in PDF, Word and HTML reports; and the global Catastro navigation links.
No other shared-checkout work is included. The additive D1 plan annotation migration is applied before deployment. Existing App Service and Azure credentials remain unchanged.

## Validation Proof - 2026-10-22 America/Lima
- `catastro.test_master_layers`, `test_raster_overlays`, `test_master_model`, `test_master_store`, `test_master_d1`, `test_planos` and `test_views`: 78 tests passed; Django system check clean.
- `acm.test_cadastral`, `test_client_report`, `test_report_selection`, `test_reference_fallback` and `test_components.ComponentsEngineTests`: 89 tests passed; Django system check clean.
- The first CI run correctly rejected three legacy report assertions that still expected decimal amounts. Their expected PDF, Word and HTML values were updated to the new integer format; the exact 124-test workflow regression suite then passed.
- JavaScript checks passed for plan geometry, eleven stage descriptions and exclusive file stages, native Google vectors, Cayma sector adjustment, ACM cadastre loading/refresh, raster assets and the private D1 worker.
- Offline collectstatic collected 134 assets; all nine changed Catastro/ACM assets matched their source bytes.
- Python AST parse passed for 12 changed runtime modules; workflow YAML and Sector 32 GeoJSON parsed successfully.
- D1 migration `007_plan_annotations.sql` applied remotely; `plan_workspace` and `plan_notes` were verified in database `prometeo-catastro-maestro`.
- Worker `prometeo-catastro-maestro` deployed successfully as version `c250f774-17b5-4bc2-b9fd-5836252daea4`; public health reports configured.
- Azure read confirms the existing App Service is Running in Brazil South with `CATASTRO_MASTER_STORAGE=d1` and `CATASTRO_MASTER_ENABLED=1`.
- Final CI/CD, public revision and production endpoint checks remain mandatory before reporting the release live.

---

# ACM house land-only and adopted report unit - 2026-10-20

Status: Validated
Recipe: existing GitHub Actions CI/CD.
Authorization: explicit user request to publish all three completed ACM corrections.
Base: latest origin/main cf5806c2e34fc37415188dbe76ba1418e54fad59.
Target: existing granextractorservice / rg-elgranextractor and unchanged pipeline OIDC identity/subscription secret.
Public: https://acm.propifai.com/acm/analisis/
No CLI provisioning, new resources, SQL migration, role assignment or credential changes.
The local CLI default subscription differs from the historical plan ID; it is not used for this deployment. The existing authorized pipeline target and credentials remain unchanged.

## Scope
Houses aged 30 or older use land only, including exactly 30. Missing or zero built area is optional for a house at any age and uses land-only valuation; valid built area retains the younger-house model. Apartments/offices still require built area. The form keeps optional construction editable and selects the corresponding map layer. Without suitable land, no house-construction fallback is invented.
Land cards show the unit actually applied to the target instead of a different zone indicator. Adjusted values update the land equation and unit together. PDF/Word use final target total divided by the appropriate target area, whether automatic or manually adjusted, retaining client-facing titles.
Preserve all current production cadastral/map/history/scraper work and local edits outside scope.

## 7. Validation Proof - 2026-10-20T17:44:18.517874-05:00
- Verified all 12 scoped source/test files against their earliest pre-change backups and exact current production before integration; no baseline conflicts.
- python webapp/manage.py test acm.test_age_selection acm.test_zone_land acm.test_reference_fallback acm.test_report_selection acm.test_client_report acm.test_components.ComponentsEngineTests acm.test_valuation_notes acm.test_weighted_adjustments --settings=acm.access_test_settings --noinput --verbosity 0: 119 tests passed, system check clean.
- Node test_age_controls.cjs, test_valuation_controls.cjs, components-presentation.test.cjs and test_report_feedback.cjs passed. components.js syntax check passed.
- Production-configured offline WSGI import, three templates, collectstatic and exact changed JS assets passed using isolated in-memory SQLite. Workflow YAML parsed successfully; added age/engine/zone regression gates and retained existing exact public asset verification.
- Shared real localhost login/analysis HTTP 200 and components.js v79 exact byte match HTTP 200; prior manual unit fixture 650 x 1212 = 787800, adjusted 789012 / 1212 = 651 verified in PDF/Word and controls.
- No models/schema changes. Existing pipeline roles and target unchanged.

## Execution
Non-forced main push starts the existing serialized CI/CD. User handles monitoring; report dispatch separately from confirmed live success and do not repeatedly poll.
Existing workflow verifies health, login guards and exact public assets before declaring deployment successful.
Rollback: scoped revert through the same workflow; no data migration to reverse.

---

# Basic cadastral PDFs and organized map cards - 2026-10-20

Status: Validated. User explicitly requested immediate publication after implementation in this chat.
Recipe: existing serialized GitHub Actions App Service pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main bc931d8a64bf88116950be4ab3c11bbab58d5100.
Public: https://acm.propifai.com/acm/analisis/

## 1. Scope
Enable Abrir reporte PDF by default in basic cadastral information for every role. Serve the verified original of the selected lot/unit through authenticated ACM, reusing validated shared copies, preserving explicit cadastral access restrictions and keeping the current analysis-report permission independent.
Add collapse/expand next to the cadastral close button. Place the expanded comparison table at the lower left of the map, with plan-layer controls initially above it. Dock collapsed search, comparison, plan layers, PDM, cadastral and selected-property cards along the upper map margin; overflow continues below in nonoverlapping rows. Restore original DOM and positions on expansion, preserve map/data and close actions, fit expanded floating cards between occupied margins and retain keyboard access.
No schema, infrastructure, Azure RBAC, secrets, resources, collector configuration or user-data migrations. Shared D:/PROMETEO preview serves the same tested source.

## 3. Validation steps
- Test exact-release PDF defaults, login/role denials, original bytes, selection changes, shared snapshot integrity, cadastral reading and existing histories/role guards in isolated SQLite.
- Run real cadastral controls and existing valuation/report/map/role JavaScript regressions; syntax-check new layout modules.
- Exercise actual templates/scripts in browser fixtures at wide and narrow map widths, including collapse, overflow, expansion and closing.
- Validate production-configured WSGI import, templates, collectstatic, exact assets and final workflow YAML; confirm existing Azure target.
- Publish without force after latest-main check, require successful CI/CD and verify exact public revision, changed assets, health, login redirects and PDF access protection.

## 5. Execution and rollback
Use existing main workflow; add cadastral PDF/card regression gate and new dock asset comparisons. Revert only this scoped commit through the same pipeline if necessary. Existing ACM global history and prior valuations remain in the release baseline.

## 7. Validation Proof
Validated with azure-validate on 2026-10-20, America/Lima:
- Exact-release python -B webapp/manage.py test acm.test_cadastral_pdf acm.test_cadastral_facade_template acm.test_cadastral acm.test_access acm.test_superadmin_access acm.test_history_visibility catastro.test_map_report catastro.test_report_snapshot --settings=acm.access_test_settings --noinput --verbosity=0: all 121 tests passed, no system-check issues.
- Original PDF tests verify inline response, role/default policies, session denial, R2 hashes, lot/report identity and shared original reuse without source contact or local cache creation. No live cadastral originals were downloaded for validation.
- Node suites test_cadastral.cjs, test_valuation_controls.cjs, test_report_feedback.cjs, test_numbered_markers.cjs and test_role_analysis.cjs passed. Both docking/floating modules passed node --check.
- Actual browser fixture checked six collapsed cards with zero pairwise rectangle intersections at map widths 1100 and 340 pixels; overflow correctly occupied the lower rail. Expanded comparison started 8 pixels from left and 32 pixels above bottom. Cadastral expansion stayed between occupied rails, and close/expand restored original parents and controls.
- Production-configured offline WSGI import and three actual templates passed. collectstatic completed on C: and all six changed JS/CSS assets exactly matched source. Initial D: static build ran out of space; the rejected temporary-folder cleanup was left unexecuted. No production resource/storage settings changed.
- Five shared localhost assets returned HTTP 200 with exact source bytes; unauthenticated cadastral PDF route returned HTTP 401. Local explicit role policies contain no cadastral_pdf override.
- Existing explicitly targeted App Service is Running in Brazil South. No infrastructure/RBAC changes require provisioning or assignments.
- Final workflow parsed and includes PDF/card tests plus public exact dock assets. Latest-main integration and scoped whitespace check passed.
- Public exact release marker, all changed assets, health and access guards remain required after the deployment succeeds.

---

# Global ACM history and creator column - 2026-10-20

Status: Validated. User explicitly requested production publication in this chat.
Recipe: existing serialized GitHub Actions App Service pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main e0f22cc39526c38a14bee79109c4550481ce5974.
Public: https://acm.propifai.com/acm/historial/

## 1. Scope
Allow the real Gerente General role and verified Propify superusers (including adminpropify) to list, replicate and download all agents' saved ACMs. Show creator username and full name in a Usuario column, preserve original creator/date in reports and save author identity for new snapshots without changing deduplication. Resolve legacy authors with one bounded directory query per page.
Keep other agents restricted to their own histories, including direct URLs. Role preview cannot elevate an unprivileged account; previewing an agent stays personal. Retain explicit history/report restrictions and owner-only deletion.
Shared local preview contains the tested change. Preserve unrelated local edits, including the separate cadastral PDF permission. No schema, infrastructure, RBAC, secrets, resource or collector changes.

## 3. Validation steps
- Run exact-release history/identity/role/report regressions with isolated SQLite.
- Validate production-configured WSGI startup, actual templates, collected CSS and pipeline YAML.
- Confirm the existing Azure target and latest origin/main, then publish without force.
- Require successful CI/CD, exact public revision marker and CSS bytes, healthy application and anonymous access guards.

## 5. Execution and rollback
Use the existing main deployment workflow and its public verification gate; add the history regression suite and exact CSS check. Roll back through a scoped revert commit if required. No new environment or subscription is selected.

## 7. Validation Proof
Validated with azure-validate on 2026-10-20, America/Lima:
- Exact-release command: python -B webapp/manage.py test acm.test_history_visibility acm.test_access acm.test_superadmin_access acm.test_role_analysis acm.test_valuation_notes acm.test_client_report --settings=acm.access_test_settings --noinput --verbosity=0. All 83 tests passed, with no system check issues.
- Tested global/personal scope, role preview, explicit denial, direct downloads, owner-only deletion, batch legacy attribution, original report author/date, escaping, pagination and stable saved-snapshot deduplication.
- Offline production-configured WSGI import passed; three actual portal templates compiled, collectstatic completed and collected history.css exactly matched source. Database aliases isolated in-memory and skill bookkeeping disabled only for offline validation.
- Workflow YAML parsed and includes the same 83-test gate plus public history.css byte comparison.
- Shared localhost CSS returned HTTP 200 with exact source bytes; protected history retained its login redirect. Actual-template browser fixture displayed the Usuario column and all synthetic agent rows; personal fixture exposed only its owner.
- Explicitly targeted App Service read confirmed Running in Brazil South. No infrastructure or Azure RBAC changes require provisioning or assignment updates.
- Latest origin/main was fetched. Release scope excludes unrelated shared edits; git diff --check passed after preserving original workflow line endings.
- Public revision, assets, health and guards remain required after deployment before reporting success.

---

# Live unit price and report-download feedback - 2026-10-20

Status: Validated. User explicitly requested publication in this chat.
Recipe: existing serialized GitHub Actions App Service pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main 6d939fd1a206c8b82d581083700b9a5e2f10e871.
Public: https://acm.propifai.com/acm/analisis/

## 1. Scope
Show the final property value per square meter immediately below its total, updating with dial, wheel, keyboard, typed amounts, rounding, restored values and changed surfaces. Use built area for ordinary houses, apartments and offices; land area for land and houses valued as land only. Keep the independent neighborhood soil indicator unchanged.
Make report generation/download feedback visible beside its button, preserve current value and notes on failure, and identify authenticated expired snapshots correctly while rejecting tampered tokens. Verify that PDFs and saved report snapshots include the adjusted total and justification.
No schema, infrastructure, dependencies, roles, credentials or collector changes. Shared local preview serves the current tested files.

## 3. Validation steps
- Run exact-release regression tests for roles, report values, notes, snapshot expiration, references and land indicators.
- Run actual JavaScript controls and download behavior tests; compile templates and collect static assets.
- Verify existing Azure target health; stage only scoped code/tests and this record.
- Publish without force after confirming main has not advanced, wait for the workflow and compare public committed assets.

## 5. Execution and rollback
Use the existing main deployment workflow. Preserve other local work and all currently published features. Roll back with a new revert commit if required.

## 7. Validation Proof
Validated with azure-validate on 2026-10-20, America/Lima:
- Exact release on current origin/main passed 165 Django tests: snapshot expiry, valuation notes, neighborhood soil, reference fallback, components, age selection, weighted adjustments, role access, role analysis and report selection; --settings=acm.access_test_settings --noinput.
- Real PDF endpoint test confirms USD 487,038.39 and the submitted justification in both generated PDF and saved history.
- Node suites passed for actual download payload/error feedback, valuation unit updates and component presentation. Components.js syntax passed.
- Actual components template compiled; collectstatic completed and all three changed JS/CSS artifacts match the release source.
- Shared localhost assets matched current source. Browser fixture confirmed live unit updates and preserved values/notes on failure.
- Existing explicitly targeted App Service is Running in Brazil South. No infrastructure, schema, role or credential changes.
- Git whitespace check passed; scope is nine ACM code/test files plus this record. Previous production revision is 6d939fd1.
- Public release marker, exact changed assets, health and anonymous access restrictions will be checked after CI/CD succeeds.

---

# Basic ACM neighborhood soil price - 2026-10-20

Status: Validated. User explicitly requested publication in the current chat.
Recipe: existing serialized GitHub Actions App Service pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/acm/analisis/
Base: origin/main 5c3135dc5f9f868d30da544cb951231ea5c4f909.

## 1. Scope
Show neighborhood land offer price per square meter above the property valuation in the basic view for Casa, Departamento, Oficina and Terreno, even without a subject lot area. Use the median of valid vacant-land sale offers within 500 m, expanding only if necessary up to the existing configured limit. Preserve existing property-model totals, quality exclusions and anonymized role access. Keep valid soil evidence when house valuation falls back to references. Restore the available house land/construction breakdown in the map valuation footer.
No infrastructure, schema, dependencies, credentials, access policies or collector changes.
Shared local preview at D:/PROMETEO already serves the tested source files.

## 3. Validation steps
- Test the exact release against current origin/main: engine, references, age, adjustment, report-selection, role and basic-access regressions.
- Run JavaScript controls/presentation/feature regressions and syntax checks.
- Render the real template, collect static assets and check exact source bytes.
- Confirm the existing Azure target is Running and the preceding release succeeded.
- Review exact Git scope, then publish without force through the existing pipeline.

## 5. Execution and rollback
Push only this release to main after final validation; if main advances, integrate first. Wait for CI/CD completion and verify the public release marker, changed assets, login and API access guards. Roll back by a new revert commit through the same pipeline if required.

## 7. Validation Proof
Validated with azure-validate on 2026-10-20, America/Lima:
- Exact release at current origin/main passed 154 isolated tests: acm.test_zone_land, acm.test_reference_fallback, acm.test_components, acm.test_age_selection, acm.test_weighted_adjustments, acm.test_access, acm.test_role_analysis, acm.test_report_selection; --settings=acm.access_test_settings --noinput.
- Node valuation controls, component presentation, feature columns and marker numbering suites passed; components.js syntax passed.
- Real components template compiled. Django collectstatic completed; all four modified JS/CSS outputs match the release source exactly.
- Shared local HTTP assets matched current source; the basic view was inspected with synthetic house, apartment, office and land examples.
- Explicit Azure subscription query confirmed the existing granextractorservice is Running in Brazil South. No resource, identity or role-assignment changes.
- Previous main release 5c3135dc was successfully deployed by workflow run 39471939847.
- Git whitespace check passed; release scope is ten ACM source/test files plus this deployment record. Public version/assets and preserved anonymous access guards remain mandatory after CI/CD completion.

---

# Preserve ACM photo dimensions and open carousel from existing image — 2026-10-20

Status: Validated.
User authorization: correct production after the photo release. User explicitly requires the existing "Sin foto" space to show the property photo with unchanged form/card dimensions, and clicking that same image to open a modal carousel with all property photos.
Mode: MODIFY existing App Service through the existing GitHub Actions workflow.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/acm/analisis/

Scope: restore the original direct image element. Add only click/keyboard gallery attributes to it; no wrapper or extra card-footer button. Remove all gallery stylesheet rules that set photo/card/form dimensions; carousel geometry is scoped to its own modal. Original components.css stays byte-identical to pre-gallery revision 57520179. Guard basic hidden marker controls without select.options so basic cards can initialize. Preserve enabled basic photo access and prefer an already stored property image over a legacy cover. No analysis/form/card sizing, infrastructure, credentials, migrations or collector changes.

Validation: 57 access/gallery/feature tests and listing-card Node regression passed; carousel JS syntax passed. Shared served checkout integrated with existing local edits preserved. Local authenticated HTML and original CSS/JS returned 200. Complete local page, using 25 real comparables and the user session in its basic Gerente General perspective: form 280 x 184.4 px, selected card 273.6 x 682.85 px, direct image 248 x 139.5 px; each dimension exactly equals the same page without the carousel stylesheet. The photo loaded, its original parent remains cmp-card-top, clicking it opened a ten-photo modal, and next navigation advanced to photo 2/10. Screenshots saved. Node regression covers the basic hidden marker control and full selector for house/apartment/land. CI must verify exact public release assets.

Deployment: integrate latest origin/main, use existing production workflow, verify marker, original layout assets and authenticated image protection. Preserve current COFOPRI queue.

---

# ACM basic property photos and complete gallery — 2026-10-20

Status: Validated.
User authorization: requested photos in the basic ACM and all property photos in a gallery; explicitly said "publicalo".
Mode: MODIFY existing Django App Service using existing GitHub Actions pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/acm/analisis/

Scope: basic roles see property photos by default, independently of portal name/link permissions. Scoped encrypted gallery tickets read all previously captured photos on demand, using authenticated same-origin image delivery. Cards and detail open a responsive gallery with all thumbnails, navigation and unavailable-image states. Explicit role disable/review restrictions remain configurable. One audited data migration upgrades the previously forced basic-role review flag, preserving disabled photos and other permissions. No new infrastructure, secrets or collector changes.

Validation proof: real shared-local HTTP page and three gallery/card assets returned 200. Real search returned 25 comparables, a 17-photo gallery and two real JPEG HTTP 200 responses. 46 existing access/feature tests and 10 gallery tests passed, including ordering/deduplication, legacy covers, owner/role/revision isolation, denial, review-only policy, parameterized Propify queries and idempotent audited migration. Listing-card Node regression and JS syntax check passed. Repeat relevant tests in release; CI compares the new public assets exactly.

Deployment: latest origin/main integrated; existing production workflow retained. Verify exact release marker, gallery JS/CSS, protected endpoints and App Service health. No local sessions copied to production.


Post-deployment verification — 2026-10-20:
- GitHub Actions run 39464172044 succeeded in all jobs. Release: 4f123f1e9bacce03ae92950b200f0315186d36dd.
- Public gallery marker returned that exact revision. components.js, property-gallery.js, property-gallery.css and portal-access.js returned HTTP 200 and matched committed release bytes.
- Public login returned 200. Anonymous gallery/photo endpoints returned 401.
- Read-only production SQL confirmed migration 0006_basic_property_photos applied, with photos and unreviewed_photos enabled for the existing basic roles 3, 20 and 8.
- Local browser verified 17-photo gallery, thumbnails and next-photo navigation using real captured images; temporary loopback QA proxy stopped after verification.
- Authenticated production UI was not inspected in the agent browser, which has no user login session. No local sessions copied to production.
Publication: live at https://acm.propifai.com/acm/analisis/ .

---

# Cayma: shared corrections consumed by production ACM — 2026-10-20

Status: Validated.
User authorization: asked for every saved plan/block correction to appear in production ACM, then said "hazlo".
Mode: MODIFY existing Django application. Recipe: existing GitHub Actions App Service pipeline.
Target: granextractorservice / rg-elgranextractor, Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/acm/analisis/

## 1. Scope and execution
Preserve and migrate the latest local Cayma placement (920 adjusted blocks at revision 87 at intake).
Store each canonical correction revision in existing private R2 with conditional writes and conflict checks.
Editor and master/ACM read the same authoritative correction. Retain source geometry, null official codes, ACL and CSRF.
Refresh open ACM geometry on revision change and window focus; never reuse stale corrected footprints.
Publish the approved Cayma source/editor/ACM integration with the current production baseline, preserving other work.
No new infrastructure, no database migration, no collector restart/configuration changes.

## 2. Resources and security
Reuse existing App Service and R2 credentials; no new RBAC, secrets or public bucket access.
Keep credentials server-side; no local cadastral downloads or caches. Source layers remain application source.
Shared D:/PROMETEO local preview must run and serve the tested files before deployment.

## 3. Validation plan
- Cross-instance shared placement read/write, CAS conflicts, failed writes and preserved imported revisions.
- Same transformed block and lot geometry reaches both master and ACM; original source bytes preserved.
- Open ACM refreshes only on actual revision changes; request/access failures keep ACL restrictions.
- Existing cadastral, radius and source-edit test suites; deployment build and template/static checks.
- Verify exact public revision/static bytes and authenticated geometry/configuration where available.
- Confirm collector advances after publication; no change to its queue.

## 7. Validation Proof
Validated by azure-validate on 2026-10-20, America/Lima:
- 60 isolated cadastral tests passed, including shared CAS, migration, cross-instance reads, preservation, conflicts, failures, lost acknowledgements, existing collector and parallel-worker regressions.
- 31 ACM tests passed (30 combined before the extra revision-permission case, followed by all four Cayma cases passing).
- Four Node suites passed: actual edit controls, master geometry, ACM radius regression and actual ACM auto-refresh on changed/shared revision, focus and visibility.
- Production WSGI import, five affected templates, collectstatic and final workflow YAML passed. External skill-version database bookkeeping disabled only for offline local build validation; no application behavior changed.
- Real authenticated local ACM HTML, configuration, revision and radius endpoints returned HTTP 200; both changed JS assets matched shared source bytes. Config/radius agreed on revision 97.
- Real migration imported revision 96 with 967 edited blocks into private R2 and verified exact readback, preserving the local original and complete prior history. Subsequent real editor save produced revision 97 / 972 edited blocks, read successfully by ACM.
- Azure read confirmed existing Running App Service in Brazil South, expected subscription. No new resources, infrastructure/RBAC or credentials were introduced.
- Canonical private runtime placement/history excluded from Git/artifacts. CI/CD will validate and compare public exact release assets. Public geometry and ongoing collector state remain mandatory post-deployment checks.



Post-deployment verification completed 2026-10-20, America/Lima:
- GitHub Actions run 39451625782 completed successfully (cad-reader, build, deploy).
- Public marker returned exact release 575201799a4d1b56f3b9242d503f23106160d17a.
- All six Cayma/master/ACM JS/CSS assets returned HTTP 200 and matched their committed release bytes.
- Public ACM login returned HTTP 200; anonymous revision/geometry requests returned HTTP 401; master/analysis routes retained their existing login redirects.
- Azure's existing private R2 credentials read the same canonical revision 97 / 972 adjusted blocks successfully. Local authenticated ACM configuration and radius responses also consumed revision 97.
- Authenticated production UI was not inspected in the agent browser, which has no user login session; no authentication guards were relaxed.
- Existing collector continued reporting fresh progress after the release; no collector job or configuration changes were required.
Publication: live at https://acm.propifai.com/acm/analisis/ .

---

# Properati human response timing - 2026-10-19

Status: Validated. Existing production scraper correction authorized by user.
Recipe: existing serialized GitHub Actions CI/CD, same subscription and app below.
Base: origin/main 6d5004e987579b29e25c940b9d74462b630dc580.
Scope: only manual verification timing and honest input status. Observe portal enabled state for up to five seconds; never force it. Each of three attempts receives up to 300 seconds, entire session capped at 900. No database, infrastructure, RBAC, or collector changes.

## 7. Validation Proof
2026-10-19 America/Lima: 12 unittest scrapi.test_manual_verification tests passed in shared D preview and isolated latest-main release. Regressions prove delayed native enablement succeeds, permanently disabled controls never click, and each retry gets 300 seconds. Local dashboard HTTP 200. Existing public App Service Running verified with explicit original subscription. No new resource or role assignments; existing deployment identity retained. CI performs backend tests and exact public release/static verification. Actual portal acceptance still requires a human answer and is not proven by unit tests. Rollback is a scoped revert; saved properties and pending queue preserved.

---

# Properati disabled human-submit control - 2026-10-19

Status: Validated. User requested correction of the production scraper.
Recipe: existing serialized GitHub Actions CI/CD for granextractorservice.
Target: rg-elgranextractor / granextractorservice, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main de2051079265bfeeee02db02f715aafeb9050e50.
Public: https://acm.propifai.com/ingestas/scraping/dashboard/

## 1. Scope
Only correct Properati manual verification reporting. If the portal keeps its
submit button disabled after human input and blur, do not try Enter or claim
submission; reopen the existing human-response mailbox with a current image.
Human solves verification; do not enable portal controls or solve automatically.
Saved properties, candidate queue, checkpoint and portal/browser scope remain.
No database migrations, settings, infrastructure, RBAC or collector changes.
Local collector downloads were separately stopped, removed at the user's
request and disabled. Those local-only controls are not in this release.

## 7. Validation Proof
azure-validate completed 2026-10-19 America/Lima:
- 10 manual verification async tests passed in the shared preview checkout and
  again on the isolated latest-main release. New regression confirms a disabled
  button never clicks, presses Enter or marks the human action executed/submitted.
- Existing success, trusted keyboard fallback, stopped job, timeout, origin
  restriction, feedback and content confirmation regressions pass.
- Production source diff limited to the handler, regression test and this proof.
- Existing Python/Django runtime and serialized CI, already validated for this
  deployment target. No resource or role modifications apply. Existing pipeline
  includes the complete manual verification regression suite before deployment.
- Shared local source contains the same correction, preserving other work.
  The local preview remains running. No real CAPTCHA is solved during testing.
- Normal push, no forced history changes. Existing CI checks exact public
  revision and assets before reporting a live release. User handles monitoring.
- Rollback: scoped revert; original saved properties and queues stay intact.

---

# Saved block alignment, satellite and parcel labels - 2026-10-19

Status: Validated. User explicitly requested this production deployment.
Recipe: existing serialized main_granextractorservice.yml CI/CD.
Target: granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main 5562e6713925b99520e526a9b514f210b3dcadf5.
Public: https://acm.propifai.com/catastro/visor-planos/

## 1. Scope
Move an entire manzana with its contained lots and labels, or move its corners.
No rotation control. Piecewise affine mesh keeps shared lot edges connected;
reject crossed boundaries and inverted mesh triangles. Versioned visual edits
are independent of original DWG/geometry, keyed by plan ID and source CRS.
Staff authorization, CSRF, per-member containment and stale-save conflict checks.
Save timestamp and automatic reload allow continuation through the same URL.
Satellite toggle is visible in the header; later CRS changes preserve the camera
and basemap. Include previously prepared adaptive lot-label sizing (10-16 px).
Shared D:/PROMETEO contains this same implementation and working local preview.
Existing Azure CATASTRO_DATA_DIR=/home/data/catastro is persistent; adjustment
JSON/history live beside the existing plan under that root. No SQL migrations,
infrastructure, app settings, roles, collector ledger or scraper changes.

## 7. Validation Proof
azure-validate completed 2026-10-19, America/Lima:
- 14 Django tests passed on the isolated production branch: plan_adjustments,
  plan viewer, staff/anonymous authorization, CSRF, version conflicts, restore,
  original-file byte preservation, invalid meshes and out-of-block membership.
- Five Node suites passed: plan_fit, plan_labels, vector_map_ui,
  plan_edit_geometry and plan_editor. Covers complete layers, map camera and
  satellite retention, linked translations, shared-edge deformation, labels,
  undo, save failure retention, reload and restore. No rotation UI.
- Browser fixture with a real Cayma block (28328, 29 entities): full current
  viewer template and local HTTP-served assets, move, move corner, actual save
  into a temporary independent plan, reload restored it; source SQLite hash
  unchanged and no JavaScript errors. Google API is a controlled test adapter,
  not a claim of an authenticated production editing session.
- WSGI under PRODUCTION=true, two templates, route reverse, collectstatic
  (527 files) and workflow YAML passed using isolated SQLite databases.
- Local HTTP page and adjustments API require login; all five served viewer JS
  assets match the shared source byte for byte. Fixture/admin tests are separate
  from the real server. Production browser sessions were not extracted.
- Existing subscription and Running/Brazil South App Service confirmed. Existing
  persistent archive setting read only; no RBAC/IaC modifications apply.
- CI adds these regression checks and compares all new public JS assets to the
  exact deployed revision, in addition to existing public page/health checks.
- Normal push only. Rollback is a scoped revert; original source and saved
  visual adjustment JSON/history remain on persistent storage.
- User handles ongoing monitoring. Dispatch is not proof of a live release.

---

# Shared verified cadastral reports - 2026-10-19

Status: Validated. User explicitly requested publication of the report correction.
Recipe: existing serialized main_granextractorservice.yml CI/CD.
Target: granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main 2496b0b6e0bd34aa86df23114b26a6654419b4af.
Public: https://acm.propifai.com/acm/analisis/

## 1. Scope
Only publish shared report copies, independent archive reading and regression
tests. Read validated public report PDFs from private R2 when COFOPRI is offline
from Azure. Original PDFs have immutable SHA256 names; publish their catalogue
after acknowledging PDF and metadata. Preserve per-unit selection, permissions,
private responses and unknown fields. Collector progress and datos.json remain.
No new infrastructure, migrations, settings, roles or extraction jobs.
Pending local lot-label sizing and separated local ledger remain unpublished;
the release cherry-picks only the report correction onto latest origin/main.
Shared D:/PROMETEO has the same report implementation and its working preview.

## 7. Validation Proof
azure-validate completed 2026-10-19, America/Lima:
- 92 Django tests passed on the isolated production branch: map_report,
  report_snapshot, collector, ACM cadastral endpoint and geollaqta.
- PRODUCTION=true WSGI import, six templates, collectstatic (521 files),
  and workflow YAML parsing passed via the existing build_check.py.
- Real lot 04011703036035 returned 325 / 141.3 m2 and 13 / 25 / 25 / 13 m
  from R2 in a process without local files and without a COFOPRI connection.
  Azure's read-only diagnostic retrieved that PDF and verified its SHA256.
- Latest shared HTTP preview: analysis/login 200, exact static source bytes,
  unauthenticated private report endpoint 401. No browser session extraction.
- Azure account matches the existing subscription; App Service Running,
  Brazil South. No RBAC/IaC changes apply to this application-only release.
- Latest main fetched; only scoped report changes are included. Use normal push.
- Existing CI verifies public exact-revision marker and page/static health.
  Dispatch alone is not a live-release claim. User handles ongoing monitoring.
- Rollback is a scoped revert through CI; private PDF evidence is retained.

---

# Close selected ACM property card - 2026-10-19

Status: Validated. User explicitly authorized publication.
Recipe: existing serialized main_granextractorservice.yml CI/CD.
Target: granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main bf170c2629fea285b165e72f7a7830fe337fa2fc.
Public: https://acm.propifai.com/acm/analisis/

## 1. Scope and execution
Add a separate accessible X button to the selected property's sidebar header.
Use the existing clearSelectedRecord handler to hide the full sidebar/resizer,
clear the highlighted comparable row and allow another marker to reopen it.
Preserve the existing content-collapse button. Bump JS/CSS cache versions.
Shared D:/PROMETEO preview contains these changes, preserving other local edits.
No database migrations, resources, settings, permissions or scraper job changes.
Normal push after latest-main check; existing pipeline verifies public revision
and matching JS/CSS. Rollback is a scoped revert through that same pipeline.
User handles ongoing monitoring; dispatch does not mean the revision is live.

## 7. Validation Proof
azure-validate completed 2026-10-19, America/Lima:
- Actual selected-card template and HTTP-served JS/CSS tested using installed
  Camoufox on a fixture at desktop and mobile widths: close expanded card,
  reopen another selected property, close collapsed card with keyboard,
  clear row highlight and hide resizer; no JavaScript errors.
- Local analysis/login endpoint and both changed static files returned 200;
  static bytes match shared source. Authenticated SQL is not asserted tested.
  Proof: D:/PROMETEO/outputs/acm-close-selected-property-20261019/validation.json.
- node webapp/acm/test_numbered_markers.cjs passed.
- node webapp/acm/test_comparable_features.cjs passed.
- PRODUCTION=true WSGI import, six templates including acm/components.html,
  collectstatic (521 files) and workflow YAML parse passed.
  Proof: D:/PROMETEO/outputs/acm-close-selected-property-20261019/build.log.
- Existing App Service read confirms Running in Brazil South. No new RBAC
  or infrastructure validation applies to this three-file UI correction.
- origin/main fetched, no intervening revisions; scoped whitespace check passed.
- Public exact-revision/static verification is required before claiming success.

---

# Complete property review and compact ACM feature columns - 2026-10-19

Status: Validated. User explicitly authorized production publication.
Recipe: existing serialized main_granextractorservice.yml CI/CD.
Target: granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: origin/main e932410a3ce9dac929a07d34d75003a5fb2dc9b2.
Public: https://acm.propifai.com/acm/analisis/
Review: https://acm.propifai.com/ingestas/scraping/calidad/?estado=acm

## 1. Scope and execution
Expose parking, parking types, elevator and apartment floor in the existing
audited property editor, retaining all original source/model evidence.
Protect corrected values from later scraping; preserve legacy clients,
permissions, CSRF and optimistic concurrency. Add independent persistent
manual-review filters and review dates.
Display compact separate car/presence, Type and apartment-floor columns in
the existing ACM comparable table. Houses show parking; land layout is unchanged.
Unknown values remain unknown. These fields do not change valuation.
Shared D:/PROMETEO preview contains these scoped changes and preserves other edits.
No migrations, resources, settings, credentials, firewall or RBAC changes.
No scraper recovery or resume-job tag. Normal push only after latest-main check.
Existing pipeline verifies exact public revision and static assets; rollback
uses a scoped revert through the same pipeline, preserving stored corrections.

## 7. Validation Proof
azure-validate completed 2026-10-19, America/Lima:
- 59 isolated SQLite Django tests passed: ACM catalogue, quality/editor,
  complete fields, correction protection, manual review, reference fallback
  and comparable feature projection.
- Three Node suites passed: actual comparable renderer, presentation and
  numbered markers; separate apartment/house/land layouts, explicit no versus
  unknown, multi-level floors, escaping and stable comparable IDs.
- PRODUCTION=true WSGI import, six template compilations and collectstatic
  passed (521 files); workflow YAML parses with required review test gate.
  Build log: D:/PROMETEO/outputs/acm-review-icon-release-20261019/build.log.
- Offline Camoufox checked actual template/renderer with installed CSS;
  final icon-column preview approved by user publication request.
- Shared local HTTP assets returned 200 and matched all three source files
  byte for byte; analysis redirects correctly to authenticated login.
  Local authenticated SQL remains blocked by firewall 40615; no bypass used.
- Azure read confirms expected subscription, Running App Service, Brazil South.
- Latest origin/main fetched; scoped release has no unrelated shared edits.
- Public exact-revision/static verification stays required for success.
  User handles ongoing monitoring; dispatch is not reported as a live release.

---

# Review properties admitted by the ACM in the existing quality template - 2026-10-18

Status: Validated. User explicitly requested production publication.
Recipe: existing serialized GitHub Actions main_granextractorservice.yml (CI/CD).
Target: existing granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Base: latest production origin/main 654d52b7d33b3a6eb0b4512418a346b9f64c79a5.
Public: https://acm.propifai.com/ingestas/scraping/calidad/?estado=acm

## 1. Scope and execution
Keep the existing quality table, filters and audited/protected property editor.
Default to the ACM-admitted catalogue, using the engine's primary rules and
shared alternative-reference eligibility. Distinguish principal/alternative
calculations and do not claim all candidates were selected by a specific ACM.
Add archived capture alongside editable fields, gallery/live-publication links,
clear automatic/manual review labels and an explicit all-scraped-records view.
Preserve authenticated access, CSRF, optimistic conflict checks and audit history.
Propify uses the existing bounded loader; source failure explicitly flags partial data.
Scoped changes are integrated into D:/PROMETEO, preserving other local edits.
No database migrations, new resources, app settings, credentials, firewall or RBAC changes.
No extraction/recovery is requested by this release; do not use a resume-job tag.
Push without force only after latest-main and whitespace checks. Existing pipeline
publishes and verifies the exact public revision and static assets. Rollback is a
scoped revert through that same pipeline, retaining stored records and corrections.

## 7. Validation Proof
azure-validate completed 2026-10-18, America/Lima:
- 44 isolated SQLite Django tests passed in release checkout: ACM eligibility,
  default-only admitted records, principal/alternative routes, filters, manual
  flags, pagination/export, source failure, permissions, editing protection/audit,
  stale-write rejection, embedded private capture and existing fallback regressions.
- Installed Camoufox tested the actual editor template on an offline fixture:
  capture/form side by side, per-record evidence changes, read-only/edit transitions,
  mobile close access, no JavaScript errors. Does not assert live portal content.
- PRODUCTION=true WSGI import passed with isolated SQLite databases; five affected
  templates compiled and collectstatic produced 521 files. Workflow YAML parsed
  and includes the same 44-test review gate on Linux Python 3.12 before publication.
- Azure account and existing App Service read: expected subscription, Running,
  Brazil South. No infrastructure provisioning/static role changes apply.
- Shared localhost source and assets are integrated; the authenticated SQL-backed
  preview is blocked by Azure SQL firewall 40615. No firewall/authentication bypass.
- Previously successful deployment 39168010118 matches base 654d52b7. Later failed
  run 39168529043 belongs to the separate procesar-control workflow, not deployment.
- Exact-SHA public marker and existing health/static gates remain mandatory.
- No long-running scraper monitoring or background automation is introduced.

---

# Properati native human input and post-submit feedback - 2026-10-18

Status: Validated. Continuing the authorized production verification repair.
Recipe: existing serialized main_granextractorservice.yml CI/CD.
Base: 715a90dd08303545d3603024a5a0b7ab8bbfdd93, successful production run 39157368709.
Target: existing granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/ingestas/scraping/dashboard/

## 1. Evidence and scope
The human's 14:33 response reached the browser; the native click timed out,
synthetic DOM click returned, and Properati did not serve requested content.
A later challenge expired. Older 12:32 errors belong to the prior execution.
Disable generated cursor trajectories only for Properati manual-answer launches,
focus the existing page, and fall back to native Enter rather than synthetic
DOM click. No CAPTCHA solver, answer inspection/export, cookie transfer,
origin, isolation or authorization relaxation. Other portals retain their options.
Publish bounded post-submit captures to the same private mailbox, preserving
its execution/state fencing. Report safe boolean input/button diagnostics and
actual remaining seconds, and distinguish server receipt from portal acceptance.
Screenshots/answers never enter logs. A capture failing during navigation does
not itself reject a successful submit. Job 229 and its preserved queue remain.
No migrations, new resources, app settings, credentials, firewall or RBAC changes.
Shared checkout edits were backed up and scoped changes integrated locally;
the local server was restarted from its existing preview helper.

## 7. Validation Proof
azure-validate completed 2026-10-18, America/Lima:
- 74 isolated release Django tests passed: mailbox, manual/browser verification,
  recovery and manual-answer launcher isolation; Node real-template tests passed.
- 82 related tests also passed in the shared preview checkout.
- Linux Python 3.11.2 ran 10 focused native-input/launcher tests successfully,
  including expiry, interruption, native Enter and post-submit screen feedback.
- Real installed Camoufox on an offline fixture emitted trusted keyboard events
  and trusted form submission with the new options; no synthetic fallback used.
  This proves input dispatch, NOT acceptance by the live Properati service.
- Production WSGI import, changed dashboard compilation and isolated collectstatic
  passed (520 files); workflow YAML including the added launcher test parsed.
- Actual restarted localhost dashboard/login redirect and shared JS/CSS return 200.
  Authenticated SQL-backed live extraction is not claimed as locally validated.
- Latest SQL read shows job 229 error with 133 stored properties after expiration.
  The preserved run/checkpoint/candidates are not reset by this application change.
- Existing exact-revision public gate and once-only tagged recovery remain in CI.
- Scope, whitespace and latest-main checks gate push. User handles ongoing
  deployment/extraction monitoring. Human live verification is still required;
  no successful Properati acceptance or completed extraction is claimed.

---

# Exact release verification during Azure startup - 2026-10-18

Status: Validated. Continuation of the user-authorized deployment and job recovery.
Recipe: existing serialized CI/CD main_granextractorservice.yml; existing Azure
App Service granextractorservice / rg-elgranextractor, Brazil South, subscription
0219eecc-9920-4789-9929-3091a2f09daf. No provisioning or identity/role changes.
Base: c41b21de60b5c44156d17f3c3f9946fe6b19e049.
Public: https://acm.propifai.com/ingestas/scraping/dashboard/

## 1. Root cause and scope
Run 39155245422 passed build/tests, Azure publication and public health/static
checks, then failed only in the authorized recovery step. The normal health gate
could accept the previous healthy version because unchanged static assets match.
The recovery helper correctly rejected the missing new marker after about one
minute; Azure finished starting the new version later. No recovery SQL ran.
Add the generated exact-SHA marker as the first required release asset inside
existing 45-attempt stabilization checks. Cache-bust release asset GETs with the
current GITHUB_SHA. The helper keeps its independent same-revision safety check.
No application code, migrations, data schema, resources or credentials changed.
Shared workflow edits were preserved and only these two lines integrated locally.

## 7. Validation Proof
azure-validate completed 2026-10-18, America/Lima:
- Retrieved GitHub failed step and actual traceback: wait_for_release exhausted;
  build and publication succeeded. Current public JSON proves c41b21de is live.
- Public health and ACM login returned 200. Actual ACM components JS, cadastral
  viewer JS and CSS match current release Git blob bytes exactly.
- Parsed actual before/after YAML verification run steps and ran their Bash in
  an isolated Linux HTTP simulation. Old gate falsely passed the previous
  healthy release; new gate rejected the first old marker and passed only after
  the second request served the current marker. All requests cache-busted.
- A server permanently serving the old marker exhausted simulated retries and
  failed, preserving the requirement for the requested exact release.
- SQL recovery --dry-run still reports job 229 error, 133 saved, 18 pending,
  page 4/run 119; no competing extraction was detected and no job was changed.
- Actual shared local HTTP page/login redirect and JS/CSS remain accessible.
- Application source, 72-test verification gate, six recovery tests and validated
  build are unchanged from the previous successful build in run 39155245422.
- Scope/whitespace/latest-main checks gate the non-forced retry push. Existing CI
  checks the public new version before the once-only recovery continuation.
- User handles ongoing monitoring; report live application separately from the
  pending CI adjustment. No full extraction-completion claim is made.

---

# Properati deployment gate repair - 2026-10-18

Status: Validated. User reported the failed authorized deployment; retry is in scope.
Recipe: existing CI/CD main_granextractorservice.yml. Same Azure target/subscription.
Base: ef5cc17c42d1a5a4877475490a4226930a3b077e.

## 1. Scope and cause
Run 39152715465 failed in the manual-verification test gate before deployment.
The expiry test patched time.monotonic on the shared standard-library module,
which also changed asyncio's scheduling clock. Python 3.12/Linux exhausted the
mock's two values and aborted with StopIteration. Local Python 3.14 had passed.
Replace only manual_verification's clock namespace and assert that the event
loop's own clock continues running normally. No application/workflow changes,
SQL migrations, resource, identity, credential or firewall changes in this retry.
The same reviewed release and once-only recovery of Properati job 229 remain.
Shared local test edits were compared and preserved before integration.

## 7. Validation Proof
azure-validate completed 2026-10-18, America/Lima:
- Read actual GitHub job/step failure and traceback; deploy job was skipped.
- Azure App Service remained Running in Brazil South.
- Linux Python 3.11.2 isolated reproduction: original test suite exits 1 with
  StopIteration; corrected suite runs all 8 tests successfully, exit 0.
  Test-only temporary files removed automatically; no database/browser accessed.
- Same 72-test Django gate now passes locally with the corrected test.
- Previous production WSGI/template/static and recovery-helper validation remain
  applicable because their source and deployment configuration are unchanged.
- Exact commit scope, whitespace, latest-main and local HTTP checks gate push.
- New tagged push retries the authorized release. Existing CI verifies public
  pages, assets and exact release marker before requesting job recovery.
- User handles ongoing deployment/extraction monitoring; dispatch is not live proof.

---

# Properati human verification and preserved-job recovery - 2026-10-18

Status: Validated. User explicitly approved publication and recovery of job 229.
Recipe: CI/CD, existing serialized main_granextractorservice.yml.
Target: existing granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf (Azure subscription 1).
Public: https://acm.propifai.com/ingestas/scraping/dashboard/

## 1. Scope and integration
Base d3aee8c272838d2d836ec18920656646cfc89e16, latest production/main.
Forward only the human's bounded answer using keyboard events, expose receipt,
browser consumption and browser execution separately, reconcile pending UI and
prevent duplicate submissions. Only actual portal content confirms resolution.
No CAPTCHA answer is generated, read or logged by the assistant.
Scoped application changes are already integrated in shared D:/PROMETEO;
other local edits are preserved and are not included in this release.
No migrations, infrastructure, resource, RBAC, firewall or credential changes.

## 3. Execution and recovery
Push without force to existing main workflow. New isolated verification tests
gate the build. Generate a static release SHA marker before collectstatic.
After normal public-page/static checks, refresh existing OIDC authentication.
Only this commit's [resume-properati-229] tag enables one authorized recovery.
The helper verifies that the public marker serves this exact revision before
queuing the preserved job, using TLS-verified SQL from the existing SCM host.
Keep run 119, page 4, 133 saved properties, 18 pending candidates and parameters.
Reject another active extraction, foreign portal or a changed job; a stored
release marker makes reruns idempotent. Never retry recovery after a later
failure of this same release. Properati may still request human verification.
The user monitors deployment/extraction; report dispatch separately from live
completion. Rollback is a scoped revert through the same serialized workflow;
already stored properties, photos, runs and candidates are retained.

## 7. Validation Proof
azure-validate completed 2026-10-18, America/Lima:
- 106 isolated Django tests passed for verification, browser verification,
  recovery, parking/elevators, exports and apartment floor handling.
- Node real-dashboard verification tests passed: pending states, duplicate
  submit prevention, stale responses, expiry and Adondevivir regression.
- Six isolated recovery tests passed: exact public revision, no-write dry run,
  preserved checkpoint, idempotence, concurrency/portal guards and row conflict.
- Actual production-side --dry-run returned error-state job 229, saved=133,
  pending=18, run=119, checkpoint=4 without changing the job.
- PRODUCTION=true WSGI import and changed dashboard template compilation passed
  using isolated SQLite databases; collectstatic produced 520 static files.
- Workflow YAML parsed, including build gates and conditional recovery steps.
- Actual local dashboard redirects correctly to authentication and shared JS/CSS
  return HTTP 200. No claim of authenticated live portal acceptance is made.
- Existing Azure subscription identity and App Service Running/Brazil South
  were verified using az account show and az webapp show.
- Infrastructure provisioning and new-role checks are inapplicable to this
  application-only CI/CD release. Scope/whitespace and latest-main checks gate push.

---

# Scraper parking and elevator fields - release 2026-10-17

Status: Validated - user explicitly requested deployment of the reviewed local implementation.
Recipe: CI/CD, existing main_granextractorservice.yml. No provisioning.

## 1. Scope
Publish only shared extraction, persistence in existing datos_crudos, table,
gallery, Excel, historical reprocessing command and regression tests for parking
and elevators. Four physical parking types, explicit zero vs unknown, mixed
parking, optional spaces, conflicts and protected manual fields are preserved.
No SQL migrations, new resources, settings, credentials or roles. Production
historical records are not batch-rewritten as part of publication.

## 2. Existing target and integration
App Service granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf (Azure subscription 1).
Public https://acm.propifai.com/ingestas/scraping/dashboard/ .
Base da18851b, current origin/main and successful production Actions 39081575010.
Scoped patch applied over the production base; shared D:/PROMETEO edits retained.
The local COFOPRI index recovery is operational data repair, not shipped data.

## 3. Execution and rollback
Push this scoped commit to main without force; existing OIDC/serialized workflow
builds and deploys. Added isolated scraper tests as a required build step.
Existing workflow verifies public health, protected pages and exact static assets.
The user's standing request is to monitor personally: report dispatch separately
from confirmed live completion and do not repeatedly poll the pipeline.
Rollback uses a scoped revert through the same workflow, preserving stored data.

## 7. Validation Proof
azure-validate completed 2026-10-17, America/Lima:
- 108 isolated SQLite tests passed in the release checkout: all five portal
  normalization paths, persistence/reload, tri-state fields, mixed/optional
  parking, conflicts, protection, HTML, Excel and historical resume/idempotence.
- Production WSGI import passed with PRODUCTION=true and isolated databases;
  the three changed templates compiled; collectstatic produced 521 files.
- Workflow YAML parsed and includes the required isolated scraper test gate.
- Local authenticated table and gallery show separate parking/elevator values;
  existing local CSS, JS and logo returned HTTP 200. Real archived evidence was
  checked read-only; no claim of live extraction validation for all five portals.
- az account show verified the existing subscription; az webapp show confirmed
  the expected App Service Running in Brazil South. No resource or RBAC changes;
  infrastructure-specific provisioning checks are inapplicable.
- GitHub confirmed the base production workflow completed successfully.
- Scope and whitespace checks are required immediately before commit/push.

---

# Complete cadastral plan and text overlay — 2026-10-17

Status: Validated — user explicitly authorized publication.
Recipe: CI/CD, existing main_granextractorservice.yml.
Target: existing granextractorservice / rg-elgranextractor, Brazil South,
subscription 0219eecc-9920-4789-9929-3091a2f09daf.
Public: https://acm.propifai.com/catastro/visor-planos/?plano=cdbae0cfc1c64f2f9b450432c789df42

## Scope
Load every page of active layers, instead of stopping at 2,000 entities.
Preserve all 28,300 lots, 2,067 blocks and all numbers and place names in the
user's Cayma drawing. Render outlines without polygon fill. Render the full
geometry and text datasets in one viewport canvas, with legible labels at
appropriate zooms and no circle pins. Retain every feature and cancel stale CRS requests.
Source DWG, geometry coordinates, accounts, other modules, infrastructure,
roles, app settings, database schema and runtime dependencies are unchanged.
Integrate on current main 3dfe82da166aac2baa0ee608fafb92d674061fa9.
The user's standing instruction is to handle deployment monitoring personally.
Dispatch the existing pipeline and report its run link without claiming that
an unfinished run is already live.

## Validation steps
- [x] Exact release scope and latest main comparison.
- [x] Node syntax, UI and complete-pagination/text-overlay regressions.
- [x] Isolated Django template/static build with exact asset hashes.
- [x] Real local HTTP and browser validation with the full Cayma drawing.
- [x] Git whitespace and source/static integrity.
- [x] Existing target/pipeline identity and public health.
No provisioning or role changes: new environment, regional quota and role
assignment creation gates do not apply to this existing CI/CD code release.

## 7. Validation Proof
Validated 2026-10-17, America/Lima. Node syntax and three regression suites
pass, including full pagination, 28,300 retained contours and 30,000 retained
labels in the renderer test. Isolated Django template compilation and
collectstatic pass; source and collected asset bytes match. Real local browser
loaded all 62,224 entities: 30,367 contours and 31,857 labels, across all eight
non-empty layers. Checked parcel numbers, red block numbers, teal urban names
and unfilled contours at zoom 17. Full dataset remains loaded while panning.
Browser screenshot and HTTP/build hashes are saved under
D:/PROMETEO/outputs/visor-vector-lines-20261017/.
Existing public login and baseline main asset return HTTP 200. The new overlay
asset returns 404 before this release, as expected. Existing CI/CD credentials
and target are reused; local ARM inspection was unavailable with connection
resets. No infrastructure, setting or role changes are included.
Other shared work, including the separate local COFOPRI recovery, is excluded.


---

# Apartment floor scraper release - 2026-10-17

Status: Validated
Recipe: existing GitHub Actions CI/CD main_granextractorservice.yml.
Authorization: user explicitly requested publication of the apartment-floor feature.
Base: f4a4a5d9bb7662979c558c0998573ade7554780b, equal to origin/main before integration.
Target: existing subscription 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South.

## Scope
Expose Piso del departamento after Operacion in the scraper table and Excel.
Extract explicit apartment floors from saved description/title and structured fields
through the shared validator used by all five portals. Keep building total floors
and ambiguous descriptions separate. Store the value and evidence in existing
datos_crudos JSON; old records have a read-only fallback. No SQL schema changes,
new resources, RBAC changes, external APIs or additional extraction requests.
Preserve unrelated local edits and all latest production changes.

## 7. Validation Proof - 2026-10-17T17:32:02.832852-05:00
- Integrated eight manifest-scoped files after verifying before/after SHA-256 and current production contents.
- python manage.py test ingestas.tests.test_apartment_floor ingestas.tests.test_scraping_export ingestas.tests.test_scraping_integrity scrapi.test_properati_areas scrapi.test_properati_age scrapi.test_properati_location --settings=ingestas.scraping_test_settings --noinput --verbosity 0: 63 tests passed, system check clean, exit 0.
- python manage.py makemigrations ingestas --check --dry-run --settings=ingestas.scraping_test_settings --verbosity 0: exit 0, no schema drift.
- Shared local preview previously verified authenticated HTTP 200 dashboard and rows, actual apartment floors 7, 2 and 3, and 37 aligned columns; no static asset changes.
- Existing CI test command now includes floor, export and integrity suites. Existing deployment public page and exact asset checks retained.
- Scoped git diff --check passed. Existing deployment identity, infrastructure and approved target remain unchanged.

## Publication
Non-forced push to main starts the existing deployment. User handles monitoring;
report dispatch separately from confirmed live status. No background deployment polling.
Rollback: scoped revert through the same pipeline; no data migration to reverse.

---

# Consolidated release — 2026-10-17

Status: Validated
Recipe: CI/CD — existing main_granextractorservice.yml.
Authorization: user explicitly requested publishing all pending changes.
Target remains Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South. No provisioning or RBAC changes.

## Scope
- Client PDF and Word: one page, five comparable columns, logged-in author, existing price labels.
- Shared Street View facade below cadastral facade in both maps; basic ACM role inclusion.
- Catastro: bounded 1–10 concurrent lot downloads with durable pause/resume and checkpoints.
- Portal scraper: visible operation before prices; Properati primary detail area instead of a storage-room area.
- Adondevivir retains explicit native-PC routing and PC default; PC status is shown only in PC mode.
- Preserve the existing direct-report ACM handler and all latest production work.
- Exclude experimental relays, browser profiles, credentials, downloaded documents and diagnostics.

## Validation proof — 2026-10-17T16:22:23-05:00
- Integrated 49 scoped files onto latest origin/main 069713a8; one script include conflict resolved by preserving current report handler version and adding the shared viewer.
- 91 ACM/report/facade tests passed with acm.access_test_settings.
- 66 collector/control/document tests passed with catastro.test_settings.
- 44 portal scraper/routing/Properati tests passed with ingestas.scraping_test_settings.
- Eight Node regression suites passed, including shared facade, maps, concurrent dashboard and scraper executor selection.
- WSGI import, collectstatic, changed Python syntax and workflow YAML passed with isolated build settings; no production SQL was used by these checks.
- Earlier real local preview verified sale and rental operation before prices; four rendered operation cases preserve all 36 columns.
- Actual Properati detail block verifies 220 m²; the 10 m² description is a storage room. Regression covers detail override, accessory exclusion, conflicting and recommended properties, and legacy mÂ² decoding.
- Report previews already rendered and visually reviewed: Word and PDF each one page for 1/5 comparables and long notes.
- No Django model migration changes. Catastro ledger adds its existing SQLite column idempotently; older jobs preserve their worker setting.
- Azure CLI confirms the existing authorized subscription. Existing OIDC deployment and exact public asset/page checks are retained and extended for new assets.

## Execution and verification
Non-forced push to origin/main starts the existing pipeline. Its validation gates run before deployment, then public health/pages and exact static assets are checked.
The user handles deployment monitoring; report dispatch separately from confirmed live deployment and do not poll repeatedly.
Rollback: scoped revert through the same workflow. Runtime ledgers and source checkpoints are outside the release.

---

# ACM direct cadastral report release - 2026-10-17

Status: Validated - scoped code release requested by the user.
Recipe: existing GitHub Actions CI/CD main_granextractorservice.yml.
Approved target: subscription 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South.
Base: latest origin/main 29bdc04b6480fa58b8860f7cad8f5bf5c04269e8.

## Scope
The ACM reads only cadastral report PDFs, with independent temporary cache,
without attempting individual fichas. Discover the actual report through the
lot gallery; prior collection is unnecessary. Re-read existing archived PDF
originals only with matching SHA-256, bounded interactive source timeouts,
clear retry errors, and the card script cache version. Preserve role gates,
report identity, separate units and document-only measurements. The collector
retains its default connection timeout; no concurrency or IP changes.
Other pending local report design and shared Street View changes are excluded.
No migrations, new Azure resources, SKU, settings, RBAC or billing changes.

## Validation steps
- [x] Integrated report, collector, access and map Django tests.
- [x] ACM card and Cuadrantizacion measurement Node regressions.
- [x] collectstatic, exact script bytes, template and WSGI build.
- [x] CI YAML, scoped diff and whitespace checks.
- [x] Shared local HTTP login/static and production preflight health/login.

## 7. Validation Proof
Validated at 2026-10-17T14:29:25.301953-05:00 in the integrated release checkout.
- manage.py test catastro.test_map_report catastro.test_collector
  acm.test_cadastral cuadrantizacion.test_geollaqta
  --settings=acm.access_test_settings --noinput: 82 passed, 24.817 seconds.
- Node acm/test_cadastral.cjs and cuadrantizacion/test_geollaqta_measures.cjs pass.
- Django collectstatic completed to an isolated output, exact cadastral script
  bytes matched source, components template compiled with v7 and WSGI loaded.
- CI YAML parsed and includes the same direct-report/collector test gate.
- Shared local login and exact cadastral script return HTTP 200. Existing public
  health and login return HTTP 200. git diff --check passes.
- Earlier live checks without an archive: three districts returned report areas
  and all four boundaries in 5-6 seconds, with no individual ficha requests.
  These local source checks do not establish Azure-to-COFOPRI connectivity.
- Existing subscription confirmed. ARM plan/cost lookup was unavailable; this
  code deployment uses existing OIDC and makes no resource/billing changes.
Static role verification: no identities, infrastructure or role assignments
change; existing application access tests pass.

Execution: scoped commit and non-forced push to main triggers existing CI/CD.
The user handles monitoring. Report dispatch separately from completed/live
success; existing CI checks public health, protected pages and exact assets.
Rollback: scoped revert through the same workflow.

---

# Pending ACM references and facade release - 2026-10-16

Status: Validated - all release checks passed; user requests all pending implementations.
Recipe: existing GitHub Actions CI/CD main_granextractorservice.yml.
Existing approved target: Azure subscription 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South.
Base: origin/main 1115db47; its deployment 38966994894 completed successfully.

## Scope
Publish both pending implementations from the shared local preview:
- Automatic fallback to at most five nearest same-type references within the
  selected radius, reversible selection and server-side recalculation.
- Preserve the valuation knob, empty exact-value input and justification.
- Correct reference labels and consistent PDF/Word/HTML values and role-safe IDs.
- Compact Street View below the cadastral facade, camera bearing toward the real
  pin, acquisition date when available, bounded lookup, stale-request protection,
  retry, and effective role permissions.
Include the existing local tests and docs. All earliest baseline files match the
latest production revision. No other shared-checkout edits are being replaced.
No migrations, new resources, infrastructure, RBAC, credentials, API activation,
capacity or billing-plan changes.

## Validation steps
- [x] Isolated release calculation, role, report and history regression tests.
- [x] Node reference controls, facade and cadastral regressions.
- [x] Static collection, template compilation and isolated WSGI build.
- [x] CI YAML parse, exact asset gates, scoped diff and whitespace.
- [x] Existing Azure subscription and public health/login verification.

## 7. Validation Proof
Validated at 2026-10-16T16:55:23-05:00 (America/Lima) in the integrated release checkout.
- Python: manage.py test acm.test_components acm.test_age_selection
  acm.test_report_selection acm.test_listing_operation acm.test_reference_fallback
  acm.test_access acm.test_role_analysis acm.test_valuation_notes
  acm.test_cadastral cuadrantizacion.test_geollaqta
  --settings=acm.access_test_settings --noinput: 197 passed, 12.442 seconds.
- Node: presentation, valuation controls, facade, ACM cadastral, district loader,
  map loading, data transport, gallery, measurements and labels: 10 suites passed.
- collectstatic completed in temporary output; six emitted ACM assets matched
  release source bytes. WSGI startup and ACM/Quad templates compiled. Conditional
  facade markup respects the active role.
- CI YAML parsed; deployment workflow adds the new regression gate and exact
  public checks for facade, presentation and valuation assets.
- git diff --check passed. All earliest local baseline files match origin/main;
  only the 23 manifest files plus release plan/workflow are included.
- Existing Azure account is the approved subscription. Previous release
  38966994894 succeeded. Public health and ACM login return HTTP 200.
- Six shared-local HTTP assets match the integrated release byte for byte.
- Earlier browser checks verified real Google facade rendering and a synthetic
  eight-record search yielding exactly five rows/pins; deselecting and reselecting
  retained the manual value and justification. Production authenticated UI is
  user-verified, not claimed from these fixture tests.

Static role verification: no infrastructure, identities, role assignments or
credentials are changed. Existing OIDC deployment and application role gates are
preserved. No new Azure provisioning or Google API activation is performed.

Execution after validation: explicit scoped commit and non-forced push to main.
Use the existing Azure OIDC workflow. User handles deployment monitoring; report
dispatch separately from a completed/live deployment. CI verifies public health,
protected pages and exact bytes of the reference/facade scripts.
Rollback: scoped revert through the same existing workflow.

---

# Full-district Geollaqta layers in Cuadrantización — 2026-10-16

Status: Validated — user explicitly requested publication after local preview.
Recipe: existing CI/CD main_granextractorservice.yml.
Target: existing subscription 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South.
Base: latest origin/main e3abe84b; previous deployment 38964665668 succeeded.

## Scope
Publish complete selected-district layers in bounded 500-feature batches,
maximum two source requests at once, progressive counts, resumable failures,
session reuse, district framing and stale-response protection. Preserve ACM
radius behavior and all role/document access. Integrate only scoped template
script changes; pre-existing local portal checkbox edits are not published.
Add a Node regression gate and exact public checks for the new district loader.
No database, capacity, resource, identity, secret, RBAC or billing changes.

All validation checks:
- [x] Seven Node map/data/gallery/labels/ACM regression suites passed.
- [x] 48 isolated Django cadastral/access tests passed.
- [x] Real source Yanahuara: 5240 / 5240 polygons, zero skipped.
- [x] Authenticated shared-local browser: Cerro Colorado 15636 / 15636.
- [x] Local HTTP 200 and exact source bytes for all four map scripts.
- [x] Latest upstream integration, CI YAML and git whitespace checks passed.
- [x] Release static collection, WSGI and Cuadrantización template build.

## 7. Validation Proof
Previous shared-preview verification loaded Yanahuara completely and retained
its 5240 / 5240 count after zooming out, then rendered Cerro Colorado with
15636 / 15636. Loader regressions cover more than 1000 features, progressive
rendering, two-request concurrency, incomplete batches, missing geometry,
foreign districts, cancellation, cache and resuming only missing blocks.
48 Django tests and seven Node suites pass in this release worktree. CI YAML
parses, scoped diff excludes unrelated local checkbox edits and whitespace passes.
Azure CLI account confirms the approved subscription. Resource-show ARM request
reset, but the existing deployment completed successfully and both production
health and ACM login currently return HTTP 200. No ARM mutation is required.
Release collectstatic succeeded, all four emitted script files exactly match
release sources, WSGI startup succeeded with isolated databases, and the map
template compiled with the district-loader dependency present.

Execution: scoped non-forced push to main triggers the existing Azure OIDC
pipeline. User handles monitoring; report dispatch separately from live success.
CI must verify public health, protected pages and exact release static assets.
Rollback: scoped revert through the same workflow.

---

# Identical cadastral HTTP responses in ACM and Cuadrantización — 2026-10-16

Status: Validated — continuing the requested production correction.
Recipe: existing CI/CD main_granextractorservice.yml; application code only.
Existing target: subscription 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South. Base origin/main 95dcf6d9,
whose prior deployment completed successfully. No new server or network provider.

## Scope and validation
Both authenticated entry points delegate to the same report_response handler.
Keep the ACM role gate, independent login, document-only fields, separate units,
individual-form priority, report fallback and the current radius/labels/card UI.

- [x] 111 isolated Django tests pass, including identical HTTP JSON and failures.
- [x] ACM radius/photo/card, Cuadrantización gallery and measurement Node suites pass.
- [x] Scoped source review and git diff --check pass.
- [x] Actual deployed Azure reader verified recovered R2 lot in 0.951 seconds.
- [x] Final release build, template/static/WSGI and shared-preview HTTP checks.

## 7. Validation Proof
Commands: manage.py test acm.test_cadastral catastro.test_map_report
cuadrantizacion.test_geollaqta acm.test_access acm.test_role_analysis
acm.test_superadmin_access --settings=acm.access_test_settings --noinput: 111 pass.
Three Node cadastral suites pass. Same-handler tests preserve role denial and
prove a failed read does not prevent retry. Existing Azure source connection
failure was reproduced inside the app container, not inferred from SCM.
Only the explicitly reported lot was archived; its two PDF reports and facade
were hash-verified in existing R2. Missing individual forms remain pending.
The Cloudflare trial was restored to its original configuration and not enabled
in the application. No SQL migrations, resource/RBAC/settings/price changes.
Release collectstatic, exact static output bytes, isolated WSGI startup and ACM
template compilation passed. Restarted the shared D:/PROMETEO preview. Its login
returns 200, ACM document API rejects anonymous access with 401, the legacy
Cuadrantización route redirects anonymous visitors to login, and the
card JavaScript returns 200 with exact served-source bytes. Whitespace passed.

Execution: non-forced scoped push to main through the existing Azure OIDC workflow.
CI checks public page/assets. Do not claim the new backend is live before a
successful deployment. The user handles monitoring after dispatch.
Rollback: scoped revert through the same workflow.

---

# ACM cadastral document lookup correction — 2026-10-16

Status: Validated — continuation of the requested production correction.
Recipe: existing CI/CD main_granextractorservice.yml, application code only.
Target: Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf,
rg-elgranextractor / granextractorservice, Brazil South.
Base: origin/main 855dd38c, previous radius deployment completed successfully.

## Scope and validation
Unify verified report reading/cache across ACM and Cuadrantización; retain
individual-form priority, private role checks, separate units and exact document
values. Probe the same facade suffixes as Cuadrantización. Preserve radius-based
geometry caching, floating card size, labels and unrelated modules. No SQL,
resource, identity, settings, capacity or billing changes.

All validation checks must pass:
- [x] Isolated Django report, access and cadastral regressions (106 tests).
- [x] Node ACM radius/card/photo, gallery, measures and labels regressions.
- [x] Live source example returns exact measurements and shares its result.
- [x] Shared local HTTP login/assets/auth gates, assets byte-matched.
- [x] Existing Azure subscription/app Running; previous publication successful.
- [x] Release build/static collection, WSGI import, scoped diff and whitespace.

## 7. Validation Proof
106 Django tests passed with acm.access_test_settings. Four Node suites passed.
Local source lot 04010222013014 verified land 369.71, construction 469.52 and
boundaries 11.73 / 38.44 / 38.81 / 12.27, approximately four seconds. Cross-map
cache tests prove reuse during source outages and separate per-unit selection.
No owner identifiers enter map responses. Local static URLs return 200 and
match the served source bytes; ACM login 200 and anonymous cadastral APIs 401.
Azure account and app read-only checks confirm existing approved target Running.
Previous radius run 38952032795 completed success. Release-worktree collectstatic, exact output asset comparison, isolated WSGI
startup, template compilation, JavaScript syntax and git diff --check passed.
The final release-worktree run passed all 106 Django tests and four Node suites.
No infrastructure or RBAC files were changed; no provisioning is required.

Execution: scoped non-forced push to main through the existing OIDC pipeline.
Its public page/static verification remains required before live-success claims.
The user handles monitoring; report dispatch separately from live completion.
Rollback: scoped revert through the same pipeline. No infrastructure changes.

---

# ACM radius-scoped cadastral loading - 2026-10-16

Status: Validated - release checks passed under azure-validate.
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
Replace ACM district-wide lot downloads with a spatial circle matching the
selected 100-2000 metre radius. Retain its footprint during pin movement; only
leaving the loaded footprint or changing the radius starts a new inventory.
Reuse overlapping geometries and three previous/empty footprints, resumable
500-lot batches with two workers, no pan/zoom reload. Preserve floating card,
facades, numbered lots, basic role access and verified document measurements.

## 2. Existing target
Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/acm/analisis/
Existing OIDC deployment; no new resources, settings, schema, RBAC or billing.

## 3. Integration
Base: 5c050e3e, latest origin/main. Shared preview changes preserved.
Seven scoped application/test files, documentation and this plan only.
Private originals, local sessions, real-source fixtures and credentials excluded.

## 4. Validation steps
- [x] Isolated ACM role/access/document suites.
- [x] Radius geometry, cache, moving pin, overlap, cancellation and retry tests.
- [x] Existing label behavior and JavaScript/Python syntax.
- [x] Template/configuration, static collection, WSGI and local HTTP exact bytes.
- [x] Azure target, latest production base, scoped diff and public CI asset gates.

## 5. Execution
Non-forced push through the existing production pipeline. User handles extended
monitoring; report dispatch separately from confirmed live publication. Existing
CI checks protected endpoints and exact public assets. Rollback: scoped revert
through the same pipeline. No production authentication bypass for verification.

## 6. Infrastructure and limits
Application-only update; existing subscription/location authorization applies.
No database migration or Azure/Cloudflare configuration change. Live document
access limitations remain independent; no bulk document collection is started.

## 7. Validation Proof
2026-10-16, America/Lima:
- Latest origin/main 5c050e3e confirmed. Its production run 38949369979
  completed successfully; existing upstream changes preserved.
- 72 isolated Django tests passed: acm.test_cadastral, acm.test_access,
  acm.test_role_analysis, acm.test_superadmin_access with access_test_settings.
- node acm/test_cadastral.cjs passed circular inventories, adjacent districts,
  active-download movement, street gaps, boundary lots, overlap reuse, prior and
  empty footprints, radius change, retry, cancellation/return and facade/card.
- node cuadrantizacion/test_geollaqta_labels.cjs passed existing label defaults
  and ACM all-zoom numbering. Both changed JS syntax checks passed.
- collectstatic and isolated WSGI succeeded in release checkout; both changed JS
  assets match source, collected bytes and local HTTP 200 versioned responses.
- Rendered basic ACM includes provider v3 and widget v4; provider configuration
  reports revision 3, scope radius. Changed Python AST parsed successfully.
- Local real-source validation: a 500 m circle around lot 04010483021014
  returned 1532 geometries, 669984 bytes, five requests in 2.01 seconds. Actual
  provider converted all lots and selected the correct parcel; moving inside
  added zero GIS requests. Private fixtures excluded from Git/artifact.
- Read-only Azure account/webapp checks confirm the existing authorized
  subscription, granextractorservice Running and Brazil South location.
- No settings, credentials, migrations, RBAC or infrastructure changed. Existing
  CI gates exact public static bytes and protected map/cadastral endpoints.
- Scoped nine-file diff and git diff --check passed. Preserve private originals,
  sessions, local edits and collector state. User handles extended monitoring;
  dispatch must not be described as confirmed live deployment.

---

# ACM compact floating cadastre and lot numbering - 2026-10-16

Status: Validated - scoped correction passed azure-validate checks.
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
Compact 260px floating card inside the map: facade and cadastral data, close and
drag without hiding lots, no dropdown/full-width panel, counters or source links.
Direct facade fallback and shared Canvas lot/block numbers without a minimum
zoom in ACM. Preserve Cuadrantizacion label defaults and cached district vectors.
Distinguish document connection failures from actual empty document fields.
This release does not claim to repair Azure-to-COFOPRI network connectivity.

## 2. Existing target
Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/acm/analisis/
Existing OIDC pipeline; no Azure resources, billing, schema or RBAC changes.

## 3. Integration
Base 7519d401, production Actions run 38940429869 succeeded.
Nine scoped application/test files plus documentation and this plan.
Preserve shared preview edits and latest main. No original document, harvested
fixture, local session, credential or experimental relay code enters Git.

## 4. Validation steps
- [x] Isolated ACM permission, role and verified document tests.
- [x] Widget, facade fallback, retry and shared label regression/syntax.
- [x] Rendered floating card, compact size, static collection, WSGI/local HTTP.
- [x] Real selected-lot report/facade archived and readable from Azure R2.
- [x] Azure target, latest main, scoped diff and public CI asset gates.

## 5. Execution
Non-forced push through the existing pipeline. User handles extended monitoring.
Report dispatch separately from verified live publication. CI checks exact public
static bytes and protected APIs. Rollback: scoped revert through the same pipeline.

## 6. Infrastructure and limits
No Azure setting/credential changes. Existing private R2 storage only: one user-
reported lot archived, originals/version snapshots retained, no bulk extraction.
A protected Cloudflare Worker was tested but upstream timed out; it is idle and
not configured in Azure or used by the application. General live documents remain
unavailable from the current Azure network; only archived records are confirmed.

## 7. Validation Proof
2026-10-16, America/Lima:
- Latest origin/main 7519d401 confirmed; prior production pipeline succeeded.
- 72 isolated Django tests passed: cadastral measurements/availability, basic
  policies, role preview, access and superadmin configuration.
- Node widget regression passed: progressive 1201 lots, cache, street pins,
  district replacement, facade fallback without archive, card close retaining
  polygons, all-zoom label configuration, document error display and retry.
- Shared number-label tests passed: real codes, grouping, safe placement, prior
  Cuadrantizacion defaults and ACM labels below the former zoom threshold.
- Both JS syntax checks and changed Python AST passed. Isolated collectstatic,
  WSGI import and three source/collected/local-HTTP byte comparisons passed.
- Rendered basic ACM has a floating section within map-container, no dropdown
  or layer checkbox. Visual harness measured card width 260px, height 438px.
  This is layout verification, not an authenticated Google Maps session test.
- Exact reported lot 04010483021014: real report parsing returned land 201.49,
  built 248.98, sides 10.00/19.78/19.67/10.00. One original report and facade
  archived with hash-verified R2 uploads; read from Azure confirmed revision 2.
  Its individual form remains pending. No bulk collection was initiated.
- Azure TCP to the COFOPRI host times out; the isolated Cloudflare trial also
  timed out. Failed relay code/settings are excluded, no Azure secret modified.
  Release does not assert general live document connectivity has been fixed.
- Read-only Azure checks confirm authorized subscription and Running Brazil
  South target. Existing OIDC, static/public gates, schema and RBAC preserved.
- Scoped eleven-file diff and git diff --check passed. Private data and local
  experimental files excluded. User handles extended deployment monitoring.

---

# Basic ACM district-wide cadastre correction - 2026-10-16

Status: Validated - azure-validate release checks passed.
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
Enable cadastral information by default in basic ACM, respecting explicit role
disables. Locate the cadastral district on pin placement and load all available
lot geometry, in progressive batches of 500 with two concurrent requests.
Retain district polygons during same-district pin movement and resume missing
batches after failure. Preserve facade and verified document measurements.

## 2. Existing target
Authorized Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/acm/analisis/
Existing OIDC pipeline. No resources, billing, settings, schema or RBAC changes.

## 3. Integration
Base: f32f1c09 (latest origin/main). Preserve upstream and shared preview edits.
Only eight scoped ACM/provider/test files, documentation and this plan.
No originals, harvested fixtures, sessions, credentials or extraction ledgers.

## 4. Validation steps
- [x] Isolated ACM permissions, role preview and cadastral suites.
- [x] District batching, cache, pin movement and recovery Node regression.
- [x] JavaScript syntax, static collection, WSGI and local HTTP exact bytes.
- [x] Existing Azure target/authentication and pipeline public verification.
- [x] Scoped diff, whitespace and latest origin/main integration.

## 5. Execution
Non-forced push through existing production pipeline. User handles extended
monitoring. Dispatch is reported separately from confirmed live publication.
CI requires public login/protected APIs and exact release static bytes.
Rollback: scoped revert through the same pipeline.

## 6. Infrastructure verification
Application-only update; no IaC, capacity, database migration or RBAC changes.
Use the subscription/location and deployment authorization already granted.

## 7. Validation Proof
2026-10-16, America/Lima:
- Latest origin/main f32f1c09 confirmed. Its production Actions run 38932414071
  completed successfully; all existing upstream work remains intact.
- 71 isolated Django tests passed: acm.test_cadastral, acm.test_access,
  acm.test_role_analysis, acm.test_superadmin_access (access_test_settings).
- node webapp/acm/test_cadastral.cjs passed: basic access, 1201 lots, two bounded
  workers, progressive drawing, street pin, same-district movement/cache,
  district replacement, retry pending batches and boundary UBIGEO handling.
- node --check passed for both changed JavaScript assets; changed Python AST
  parsed. collectstatic and isolated WSGI import passed in release checkout.
- Both collected JS assets exactly match source and local HTTP 200 v2 bytes.
- Local real-source validation received all 5240 Yanahuara geometries, eleven
  batches in 5.26 seconds. Provider identified lot 04012607038027. Private
  geometry fixture is excluded from Git and deployment.
- Azure read-only checks confirm subscription 0219eecc-9920-4789-9929-3091a2f09daf,
  granextractorservice Running in Brazil South. Existing OIDC remains unchanged.
- No infrastructure, new identity, RBAC, database migration or settings change.
  CI already enforces protected cadastral API and exact public release assets.
- Ten-file release scope and git diff --check passed. No private data staged.
  Extended monitoring is left to the user; dispatch does not establish live success.

---

# Pending ACM, cadastre and viewer improvements — 2026-10-16

Status: Validated — release checks passed under azure-validate (2026-10-16).
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
- ACM role-gated, collapsible cadastral card and selected block's lot contours.
- Facade and verified ficha/report measurements; no layer-based area fallback.
- Cuadrantizacion lot/block number labels reusing loaded vectors; Street View.
- DWG automatic state recovery, completed bootstrap and coordinate-view feedback.
- Windows atomic status-write retry; original files and extraction ledgers retained.
No DWG source is activated in the master without confirmed CRS/layer approval.

## 2. Existing target
Authorized Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/acm/analisis/
https://acm.propifai.com/cuadrantizacion/mapa/
https://acm.propifai.com/catastro/visor-planos/
Existing OIDC and infrastructure. No resources, capacity, RBAC or billing changes.

## 3. Integration
Latest main and confirmed successful production base: 8053415f.
Shared D:/PROMETEO edits preserved; unrelated portal default checkboxes excluded.
No private originals, local sessions, manifests, ledgers or credentials deployed.
No model migration: the new permission defaults off except Administrator.
Role policies are configured through the existing administrator UI.

## 4. Validation steps
- [x] Isolated ACM permissions, identity, reports and cadastral measurements.
- [x] Isolated Catastro reader/storage/report/viewer tests.
- [x] Browser transport, labels, Street View, DWG recovery and JS syntax.
- [x] Static collection, WSGI import, exact local HTTP bytes and release diff.
- [x] Existing Azure target/auth and CI public asset/API verification.

## 5. Execution
Non-forced push through existing pipeline. User handles extended deployment
monitoring; report dispatch separately from verified live publication.
CI validates public login, protected map/viewer, role API and exact release assets.
Rollback: scoped revert through same pipeline. Preserve existing secrets/settings.

## 6. Infrastructure verification
Application-only update. No Bicep/Terraform, Container App, identity or RBAC change.
Use the same subscription, region and deployment credentials already authorized.

## 7. Validation Proof
Validated 2026-10-16, America/Lima:
- origin/main 8053415f confirmed; prior production run 38924645440 succeeded.
- 126 isolated ACM tests passed: permissions, role preview, identity/session,
  verified document measurements, history privacy, comparable/report behavior.
- 39 isolated Catastro tests passed (one optional native fixture skipped).
  Repeated reader suite with the official LibreDWG 0.14 Polygon.dwg fixture:
  all 11 passed, including native background conversion and layer HTTP endpoint.
  An earlier generic fixture had invalid handles; the real user DWG and official
  valid fixture both complete. No unsupported-input success is claimed.
- Nine Node suites passed: transport, geometry, gallery, measurements, numbering,
  cache/pan/zoom, Street View, cadastral card and actual deadline/recovery.
- New/changed JS syntax and Python AST passed. Isolated WSGI import and
  collectstatic succeeded; ten release static assets match local HTTP 200 bytes.
- Real local browser reopened the completed DWG and rendered 2000 lot polygons;
  Google overlay tested provisionally. No datum assigned to the stored source.
- Azure account and webapp read-only checks: expected authorized subscription,
  existing Brazil South target Running. No resources/RBAC/schema/settings change.
- CI YAML parsing and bash syntax passed. Existing OIDC and startup preserved.
  Public checks now require new static bytes, protected map/viewer and API 401.
- Scoped release diff preserves upstream work and pre-existing local portal
  defaults. Private data, sessions, originals and extraction ledgers excluded.
- Git whitespace and staged scope checks required immediately before push.
  Native Linux conversion/startup/public checks remain enforced CI gates.
- User retains extended monitoring; report dispatch separately from live proof.

---

# DWG viewer visibility and feedback — release 2026-10-16

Status: Validated — viewer checks passed under azure-validate (2026-10-16).
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
Only the DWG viewer template, stylesheet, script and regression checks.
Fix SVG hidden attribute handling, prioritize LOTES geometry on opening,
show upload/reading/drawing/completion status and elapsed time, and allow
status retries without uploading the file again. Unknown CRS remains CAD;
no coordinate system or datum is guessed. No ACM/cadastral labels release.

## 2. Existing target
Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/catastro/visor-planos/
Existing OIDC pipeline and resources; no new billing, schema or RBAC changes.

## 3. Integration
Latest origin/main 9b36df17. Preserve shared D:/PROMETEO local changes and
all upstream work. No private DWG, session, secret or local data deployed.

## 4. Validation steps
- [x] Viewer UI regression and JavaScript syntax.
- [x] Isolated Catastro/DWG suites and template rendering.
- [x] Static collection, exact bytes and local HTTP.
- [x] Existing Azure subscription/target and CI credential configuration.
- [x] Exact release diff/whitespace; CI native build/startup/public checks.

## 5. Execution
Non-forced push starts the existing production pipeline. User handles long
monitoring; report dispatch accurately. Pipeline checks public login, viewer
protection and exact static bytes before marking deployment successful.
Rollback is a scoped revert through the same pipeline.

## 6. Infrastructure verification
Application assets only; no Bicep/Terraform/Container Apps or new identities.
Existing subscription/location are already authorized in this session.

## 7. Validation Proof
2026-10-16, America/Lima:
- node catastro/test_dwg_ui.cjs passed native upload, each progress phase,
  failure/retry, LOTES priority and removal of the actual SVG hidden attribute.
- node --check visor-planos.js passed.
- Isolated Django viewer/CAD suite: 13 tests, 12 passed, one optional native
  fixture skipped locally. Existing CI gates real Linux DWG conversion.
- collectstatic succeeded in isolated settings; both release JS/CSS match
  collected bytes and local HTTP 200 responses. Protected viewer leads to login.
- az account show and az webapp show confirm the authorized existing
  subscription, Brazil South target and Running state. No resource/RBAC changes.
- Existing CI OIDC credentials/configuration preserved, no new permissions.
- Latest origin/main 9b36df17 confirmed; exact six-file scope and git diff
  --check passed. No SQL migration, collector, ACM or private file changes.
- Public page/static verification remains an enforced CI step. Per user request,
  long deployment monitoring is left to the user; dispatch is not live proof.

---

# ACM access and native DWG viewer â€” release 2026-10-16

Status: Approved â€” explicit publication requested by the user.
Recipe: CI/CD, existing main_granextractorservice.yml.

## 1. Scope
Publish all locally reviewed ACM role access, independent Propify login,
role preview, own histories, comparable labels, calibration controls, notes,
PDM permissions and native DWG viewer improvements. Preserve the current
production collector and other upstream changes. No local ledgers, sessions,
credentials or originals enter the deployment artifact.

## 2. Existing target
Azure subscription 1 / 0219eecc-9920-4789-9929-3091a2f09daf.
App Service granextractorservice, rg-elgranextractor, Brazil South.
https://acm.propifai.com/acm/ and /catastro/visor-planos/.
Existing OIDC pipeline, no new resources or RBAC assignments.

## 3. Integration
Base: a2dfce95 (latest origin/main). Shared preview D:/PROMETEO preserved.
Native GNU LibreDWG 0.14 reader built on Linux and bundled with release.
ACM policies/history require migration 0005; verify SQL capacity and migrate
before considering production ready. Existing sessions/data remain private.

## 4. Validation steps
- Isolated ACM and CAD regression suites, Node checks, real native fixtures.
- Production Python dependency compatibility and Linux native build/smoke.
- Static collection and WSGI import under isolated build settings.
- Azure target, SQL capacity/migrations, release scope and whitespace.
- Public page/static verification in deployment pipeline.

## 5. Execution
Non-forced push to main starts existing production pipeline. The user's
standing instruction is to handle deployment monitoring personally: do not
keep polling. Report dispatch separately from confirmed live deployment.
Rollback: scoped revert through the same pipeline.

## 6. Runtime
Preserve all existing secrets/settings, use persistent /home for private files.
No subscription/location or infrastructure changes.

## Capacity prerequisite — independently validated and authorized
Status: Validated (2026-10-16).
User explicitly approved Standard S0 after reviewing its cost (USD 0.5855/day).
Read-only az account show confirms the existing subscription. az sql server list
and az sql db show confirm rg-elgranextractor/granextractor-sql-prod/
propiextractor, Online, Basic, maxSizeBytes 2147483648. SQL reports quota 40544
for migration 0005 and verified archival cleanup; no tables were published.
Microsoft resource limits confirm S0 includes up to 250 GB. Existing target,
credentials, firewall and data retained; only edition/SLO/max-size change.
Execute through azure-deploy: az sql db update --edition Standard
--service-objective S0 --max-size 250GB. No app deployment until schema succeeds.

## 7. Validation Proof
Validated under azure-validate on 2026-10-16 (America/Lima):
- Latest origin/main a2dfce95 is also the successful production revision,
  Actions run 38651317156. Integration preserves its collector/startup work.
- 157 isolated Django ACM tests passed with acm.access_test_settings:
  identity/privacy, permissions, own histories, perspective, sessions,
  area/age selection, listing operation, reports, calibration and notes.
- 21 isolated Catastro tests passed with catastro.test_settings, including
  real native conversion of an official DWG fixture. No tests used Azure SQL.
- Nine Node regression suites passed; changed JS files pass node --check.
- Production WSGI import passed against isolated build databases.
  collectstatic passed; ACM and viewer output bytes match release sources.
- Local HTTP: /acm/login/ 200; protected viewer 302; components.js v66 and
  visor-planos.js v3 return 200 and byte-match the served D:/PROMETEO files.
- Azure account/target confirmed Running and correct existing subscription.
- Authorized SQL S0/250 GB capacity change completed. Migration acm.0005
  applied successfully; all four new tables respond to count queries.
- Three user-reviewed local role policies imported only when absent, with
  an audit entry; no local sessions, histories or collector ledgers copied.
- Native Linux compilation is a required CI build gate before app deployment,
  pinned to the verified official 0.14 source SHA256. CI converts both 2000
  and 2018 DWG fixtures. The Windows native pipeline already passed locally.
- Workflow dependency gates, YAML parsing, staged scope and whitespace passed.
- No new resource, role assignment, firewall, identity credential or subscription
  change. Only the explicitly approved SQL capacity increased billing.
- Existing CI verifies public health, ACM login, protected viewer and exact
  ACM/viewer static bytes. User handles monitoring after dispatch.

---

# Permanent Azure cadastral collector - release 2026-10-14

Status: Validated - user requires Azure only and operation with the PC powered off
Recipe: existing serialized CI/CD workflow and existing App Service startup

## Authorized scope and target
Start and supervise the cadastral collector in startup.sh, following the existing
scraping watchdog pattern. Use the same App Service granextractorservice,
rg-elgranextractor, Brazil South and existing subscription. Activate only
CATASTRO_AZURE_WORKER_ENABLED=1 after publishing this startup correction; preserve
the configured external mode, scoped token, Always On and other app settings.
The worker has a separate durable ledger /home/data/catastro-worker and a bounded
rotating log. No local PC process, Hostinger changes, new Azure resources or new
compute charges. Previous Hostinger access was read-only and is explicitly out
of scope. The manual local worker request is superseded by the user's Azure-only
requirement. Base main a4947029; its serialized publication is still in progress.

## 7. Validation Proof
azure-validate completed 2026-10-14, America/Lima:
- 38 isolated Django/collector tests passed, including unavailable-source wait
  without claiming/failing the queued job, automatic continuation on recovery,
  idle operation without COFOPRI requests, authentication, leases and resumption.
- bash -n startup.sh and JavaScript syntax passed. Runtime/dependencies are the
  existing production Python and installed PDF libraries; no infrastructure or
  RBAC changes. Shared preview integrated surgically with backups.
- Earlier real local one-property R2 trial verified original PDF areas 200/20.5.
- Two distinct Azure App Service egress networks timed out on TCP/443 to both
  COFOPRI hosts. Source reachability is unresolved; do not report real production
  extraction successful merely because the worker is running.

## Execution and verification
Push scoped files without force, preserving newer main. Let serialized CI finish.
Enable the Azure worker flag preserving all other settings. Verify the deployed
asset, private API, Azure process, heartbeat, queued-job wait and bounded log.
If COFOPRI still refuses connections, explicitly report the source connectivity
blocker and that queued work will retry automatically. Do not use the PC or
Hostinger as a fallback. No extended monitoring after verification.

---

# External cadastral collector - release 2026-10-14

Status: Validated - user explicitly requests production publication and correction
Recipe: CI/CD through existing .github/workflows/main_granextractorservice.yml

## Scope and existing target
Deploy the reviewed external collector control and dashboard. Azure keeps its
private archive ledger and administrative dashboard; a collector in a network
with normal COFOPRI access fetches originals and uploads directly to private R2.
Activate CATASTRO_EXECUTION_MODE=external and the scoped CATASTRO_WORKER_TOKEN
from the existing local private token file, without disclosing it or modifying
other settings. Start the collector against https://acm.propifai.com and verify
an actual Alto Selva Alegre archive and dashboard progress before reporting fixed.
Base main and last successful production: 441329ecc88323f2f7a91e156a138bd0917425a4,
workflow 38644680628. Existing target granextractorservice / rg-elgranextractor,
Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf. No new cloud
resources, role assignments, package dependencies or SQL Server migrations.
SQLite additions preserve existing jobs, lots and uploads. Keep R2 credentials
and originals, existing runtime configuration and unrelated local changes.

## 7. Validation Proof
azure-validate completed 2026-10-14, America/Lima:
- 36 isolated Django/collector tests passed: scoped Bearer and lease validation,
  administrative CSRF, precise middleware exception, stop/resume, lost progress
  acknowledgement, paginated seeds and fresh-machine retry without redownload.
- Real local dashboard-to-worker-to-R2 trial archived 04010206058015, reflected
  its summary and one pending individual form. PDF measurements were 200/20.5.
- Local anonymous collector endpoint returned HTTP 403. Dashboard and current
  JavaScript served over HTTP; asset bytes exactly match the shared source.
- Production WSGI and dashboard template compiled with isolated SQLite;
  collectstatic passed and the release JavaScript exactly matches its source.
- JavaScript syntax and Git whitespace checks passed. Latest origin/main fetched;
  previous production workflow confirmed successful. Shared D:/PROMETEO contains
  the 13 scoped files; unrelated work is retained. Secrets remain outside Git.
- Existing Azure subscription and target are unchanged; resource/role template
  checks are inapplicable to this application-only release.

## Execution and verification
Push scoped source and this record to main without force. Configure only the two
collector settings while preserving every other app setting. User now explicitly
requests publication after learning the permanent collector was not active.
The prior local background start was rejected by automatic approval review; do
not bypass a renewed rejection. Production needs an active authorized collector;
code dispatch alone is not a working fix. Confirm current public asset bytes,
private API authentication, an archived test lot and full-district inventory/progress.
Do not remain monitoring after that verification. Rollback preserves R2 and the
ledger; stop the worker before changing execution mode or reverting the code.

---

# ACM calculation and cadastral measurements - release 2026-10-14

Status: Validated - user explicitly requested publication of reviewed local changes
Recipe: CI/CD, existing .github/workflows/main_granextractorservice.yml

## Scope and existing target
Publish only the reviewed ACM and cadastral corrections. Nearby places query only
after successful Buscar y calcular, with a collapsed card in normal flow below
the map. The client PDF retains its existing headings; its unit price and chart
average use the selected total divided by the applicable target area. Cadastral
areas and four boundaries come from the selected original report, with separate
unit reports and no fallback to unverified vector areas. Preserve facade images.
Base main and last successful production revision: 58b2310218aef07230a4eff2959e9bb3d9876d34,
workflow 38632845572. Existing App Service granextractorservice / rg-elgranextractor,
Brazil South, subscription 0219eecc-9920-4789-9929-3091a2f09daf.
No resources, roles, secrets, dependencies or database migrations change. Retain
R2 runtime configuration, archive contents and unrelated shared-checkout edits.

## 7. Validation Proof
azure-validate completed 2026-10-14, America/Lima:
- 4 report-measurement, 22 isolated cadastral Django and 12 ACM report tests passed.
- Node suites passed for report measurements, facade galleries, ten-district
  provider, pan/zoom persistence and nearby places. Twenty pin moves produced
  zero places/routes calls; explicit calculation alone initiates discovery.
- Real local selected lot 04010206058015 displays report values 200 / 20.5 m2
  and front/right/left/rear 10 / 20 / 20 / 10 m. Original facade is retained.
- Local ACM DOM confirms initially hidden/collapsed, static-position card in
  map-main outside the map container. Seven static assets HTTP 200 and exact bytes.
- Sample PDF rendered and inspected: original PRECIO PROMEDIO DE VENTA POR M2
  heading retained, 110000 / 90 = 1222.22 and matching chart line, no new labels.
- Production WSGI, three templates and isolated collectstatic passed; seven
  collected static assets exactly match their sources.
- Latest origin/main fetched and prior production workflow confirmed successful.
  Azure existing App Service confirmed Running in the expected subscription/region.
- Shared D:/PROMETEO preview contains the changes, with unrelated edits preserved.
  Git whitespace checks passed. Resource/role template checks are inapplicable to
  this app-only release; the existing federated pipeline is unchanged.

## Execution and verification
Push only scoped application files, tests and this record to main without force,
integrating newer main if it advances. Use existing serialized production pipeline.
Perform a bounded public page/static check; report pending unless matching release
bytes are actually served. User performs visual production verification; do not
remain monitoring. Rollback uses a new revert commit and preserves archived data.

---

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
