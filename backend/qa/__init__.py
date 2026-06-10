"""Round 10 QA driver.

End-to-end smoke + verification against a live FastAPI app, backed by a
real Postgres. Orthanc-dependent paths (WADO/thumbnail) are marked SKIP
when Orthanc isn't reachable.

Run from the backend dir:
    .venv/bin/python -m qa.run_qa --report docs/qa/round10_qa_report.md
"""
