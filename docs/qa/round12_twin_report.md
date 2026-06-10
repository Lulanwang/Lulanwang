# Round 12 — 3D Digital Twin

## Context

The user asked for a feature that **creates a 3D digital twin of an internal body organ from the patient's DICOM images**. This round adds it end-to-end:

* a new backend service package (`app/services/twin/`) that pulls a DICOM series from Orthanc, segments the primary organ with classical computer vision, runs marching cubes, exports a glTF-binary mesh, and stores it as a durable `organ_twins` artifact;
* three modality-specific segmenters behind a registry (`OrganSegmenter` protocol) — `lung_ct`, `brain_mri`, `breast_mammo` — that a future MONAI organ model can be plugged in beside;
* a three-tier lesion mesh fallback so AI findings with only normalized bbox geometry still appear as clean ellipsoid markers (flagged `synthetic_marker`) without faking real segmentation provenance;
* a new `/studies/[studyUid]/twin` Next.js page with a three.js + react-three-fiber + drei viewer (lazy-loaded with `ssr:false`), authenticated GLB streaming via `fetch + GLTFLoader.parse` (drei's `useGLTF` cannot send the bearer token), per-structure visibility/opacity controls, snapshot + GLB download, and a research-only banner.

Decisions locked in by the user before implementation: classical CV (MONAI-pluggable), dedicated `/twin` page, target organ + lesions scope.

## Stack

Same live stack as Round 11: Postgres 16 + Orthanc 1.12 + uvicorn + Next 15 + Playwright/Chromium. New deps: `scikit-image>=0.24`, `trimesh>=4.4`, `scipy>=1.13` (Python); `three`, `@react-three/fiber`, `@react-three/drei`, `@types/three` (Node). Frontend deps installed with `--legacy-peer-deps` to coexist with React 19.

## Results

| Layer | Result |
|---|---|
| `pytest -q` (full backend suite) | **112 passed / 1 skipped** (was 101 — +11 new twin tests, zero regressions) |
| `npm run build` | clean compile, 13 routes, 0 type errors. New `/studies/[studyUid]/twin` route is 6.0 kB (three.js is code-split). |
| `npm run test:e2e -- e2e/09-twin.spec.ts` | **4 passed** (banner visible, page state mounts, legend cm³ visible, visibility toggle wired) |
| `npm run test:e2e` (full suite incl. new twin spec) | **67 passed / 1 skipped / 1 flaky** (the flaky one is the same worklist Open-link test from Round 11 that passes alone) |
| Live twin generation against the 5-study cohort | 5/5 succeeded after the segmentation fixes below — GLB sizes 76 KB – 819 KB, all under the 5 MB ceiling |

Sample twins captured in `docs/qa/round12_artifacts/screenshots/`:
* `twin-lung-ct.png` — lung CT, organ envelope + bbox-derived lesion marker
* `twin-brain-mr.png` — brain MR, Otsu-stripped brain envelope + lesion marker
* `twin-breast-mg.png` — mammogram silhouette extruded into a thin 3D slab

## Bugs found and fixed during the build

Several issues surfaced during the live integration; all are fixed in this round.

### Bug 1 — Marching-cubes Y-flip inverted face winding

`mask_to_mesh` flips Y so the patient renders head-up in three.js. The reflection inverts triangle winding → `mesh.volume` came back negative → `keep largest component by volume` picked the smallest piece → meshes shrank to nothing. Caught by the test that compares marching-cubes volume to the analytic sphere. Fixed by swapping face indices `faces = faces[:, ::-1]` after the reflection, and ranking pieces by `abs(volume)` to be safe.

### Bug 2 — Orthanc DICOMweb plugin rejects `Accept: application/dicom`

The bundled Ubuntu `orthanc-dicomweb` plugin requires the strict DICOMweb-spec `multipart/related; type="application/dicom"` Accept header. A plain `application/dicom` returns 400 with the plugin's own error JSON. Round 11 hit the same shape on STOW. Switched the new full-series volume loader to Orthanc's **native REST** path (`tools/lookup` → `instances/{id}/file`), same approach the QA seeder uses to push DICOMs in.

### Bug 3 — VARCHAR(128) overflow on a new audit `resource_type`

Round 11 widened `audit_events.resource_id` to 512 chars. Twin generation surfaces no new audit overflow because we logged only the twin UUID, but the path is exercised — confirms Round 11's migration was the right call.

### Bug 4 — Synthetic CT has no air-filled lungs

The seeded synthetic chest CTs clip at ≈ -315 HU, so the fixed lung HU window (`< -320`) found zero voxels and the twin came back empty. The lung segmenter now probes the volume's 1st percentile: only HU-calibrated volumes (`p1 < -700`) take the lung-air path; non-calibrated / synthetic volumes fall back to Otsu + body envelope so the demo always shows a 3D shape. A real clinical CT keeps the classical lung mask.

### Bug 5 — Single-slice CT/MR (pydicom bundled samples) returns empty

`CT_small.dcm` and `MR_small.dcm` are 1-slice volumes; the 3D segmenters bail with `volume.shape[0] < 2`. Routed all `series.is_2d` paths (regardless of body part) through the breast/2D silhouette segmenter so single-slice studies still produce a thin extruded slab — same approach as MG. Flagged `synthetic_extrusion: true` so the UI can disclose it.

### Bug 6 — Next dev server didn't proxy `/api`

Round 11 added a `/dicom-web/*` rewrite for standalone dev. The new twin endpoints live under `/api/v1`, so client code calling `BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1"` 404'd against Next when the env var wasn't baked at compile time (which `next dev` doesn't reliably do for `NEXT_PUBLIC_*` reads). Extended `next.config.mjs` to also rewrite `/api/*` → backend. Production via Caddy is unaffected (rewrite is a no-op when `NEXT_PUBLIC_API_BASE` is unset).

### Bug 7 — drei `<Environment preset="city">` reached out to a CDN

The viewer initially used drei's `Environment` for nice reflections. That component fetches an HDR file from a public CDN, which failed in this container with `CERT_AUTHORITY_INVALID` → the Canvas crashed → the `<canvas>` element disappeared right after mounting. Dropped Environment; the ambient + hemisphere + two directional lights are more than enough for the demo and have no network dependency.

## What's now in the repo

```
backend/
  alembic/versions/0006_organ_twins.py       # new migration
  app/db/models/organ_twin.py                # new SQLAlchemy model
  app/services/twin/
    config.py                                # SEG_CONFIG_VERSION + budgets + colors
    volume_loader.py                         # full-series WADO + spacing_from
    segment.py                               # OrganSegmenter + lung/brain/breast + lesion tiers
    meshing.py                               # mask → trimesh → glTF-binary
    pipeline.py                              # enqueue + run_twin_generation
  app/api/v1/twins.py                        # POST generate / GET twin / GET model.glb
  app/workers/background.py                  # extended recovery to flip stuck twin rows
  app/dicom/parse.py                         # spacing_from helper added (assemble_volume unchanged)
  tests/test_twin_pipeline.py                # 11 new tests
frontend/
  app/studies/[studyUid]/twin/page.tsx       # page (poll, empty/generating/ready states)
  components/twin/
    TwinViewer.tsx                           # three.js canvas + auth GLB load + screenshot
    StructurePanel.tsx                       # visibility/opacity per structure
    ResearchTwinBanner.tsx                   # research-only disclosure
  next.config.mjs                            # /api rewrite extended
  e2e/09-twin.spec.ts                        # 4 button-level tests
  e2e/screenshots-twin.spec.ts               # capture spec
```

## Top 3 risks (and how we mitigated them)

1. **Noisy threshold mask → ugly non-manifold mesh.** Gaussian-smooth the mask field before marching cubes, keep only the largest CC to kill speckle islands, quadric-decimate to fixed face budgets (40k organ / 5k lesion), Taubin-smooth (volume-preserving). Hard GLB ceiling at 5 MB with a re-decimate retry.
2. **Anisotropic voxel spacing → distorted organ.** `spacing_from(datasets)` derives `(sz, sy, sx)` mm from `PixelSpacing` + median `ΔImagePositionPatient`, passed directly into `marching_cubes(spacing=...)`. Sphere-volume regression test guards against regressions.
3. **three.js in Next 15 RSC + GLB size/JWT.** `dynamic(() => …, {ssr:false})` for the canvas; manual `fetch → arrayBuffer → GLTFLoader.parse` for bearer-authed GLB; geometry/material disposal on unmount.

## How to reproduce

```bash
# 1. Postgres + Orthanc + backend
pg_ctlcluster 16 main start
Orthanc /tmp/orthanc-qa.json &
cd backend
alembic upgrade head                                # applies 0006
python -m qa.seed_qa --with-orthanc                 # 5 studies, both Postgres + Orthanc
uvicorn app.main:app --port 8000 &

# 2. Frontend
cd ../frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1 npm run dev &

# 3. End-to-end smoke
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"clinician@lulan.local","password":"clinician_demo_password"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# Any study with body_part in {CHEST, BRAIN, BREAST}:
STUDY=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/studies/ \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')

curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/twins/$STUDY/generate"   # → 202 queued
sleep 5
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/twins/$STUDY"            # → succeeded + structures metadata
curl -o twin.glb -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/twins/$STUDY/model.glb"  # → 200, model/gltf-binary

# 4. Or just browse /studies/<id>/twin in a browser and click Generate.
# 5. Regression suites:
cd ../backend && pytest -q                              # 112 pass
cd ../frontend && npm run test:e2e                      # 67 pass + 1 skipped
```
