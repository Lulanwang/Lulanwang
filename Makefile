.PHONY: up down restart logs seed seed-models test fmt clean

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart backend frontend

logs:
	docker compose logs -f --tail=200

seed:
	docker compose exec backend python -m seed.load_pydicom_samples

seed-models:
	docker compose exec backend python -m seed.download_monai_bundles

# Dump synthetic DICOMs to /data/artifacts/synthetic in the backend container
# so you can download + open them in any DICOM viewer.
generate-synthetic:
	docker compose exec backend python -m seed.dump_synthetic /data/artifacts/synthetic

# Run the bundled + public pydicom-data DICOMs through the pipeline and
# emit a Markdown + JSON analysis report.
analyze-external:
	docker compose exec backend python -m seed.analyze_external_data --out /data/artifacts/analysis

test:
	docker compose exec backend pytest -q

fmt:
	docker compose exec backend ruff format app tests seed
	docker compose exec backend ruff check --fix app tests seed

clean:
	docker compose down -v
	rm -rf data/artifacts data/monai-bundles
