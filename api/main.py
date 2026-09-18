"""
Camada de serviço (camada 5 da arquitetura) — API REST em FastAPI.

Expõe as previsões e recomendações geradas a partir dos dados em
`locaiops.incidentes_raw` (Postgres). Pensada para futuramente substituir a
leitura direta de JSON estático no dashboard Next.js.
"""

import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine

from pipeline import run_pipeline

DB_URI = os.environ.get(
    "LOCAIOPS_DB_URI", "postgresql+psycopg2://locaiops:locaiops@postgres:5432/airflow"
)

app = FastAPI(title="LocAiOps API", version="1.0.0")
engine = create_engine(DB_URI)

_cache: dict = {}


def _ensure_cache():
    if not _cache:
        refresh()
    return _cache


def refresh():
    _cache.clear()
    _cache.update(run_pipeline(engine))
    return _cache


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/refresh")
def api_refresh():
    try:
        refresh()
    except Exception as exc:  # dataset ainda não carregado pela DAG, p.ex.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "refreshed"}


@app.get("/api/overview")
def api_overview():
    return _ensure_cache()["overview"]


@app.get("/api/forecast")
def api_forecast():
    return _ensure_cache()["forecast"]


@app.get("/api/risk")
def api_risk():
    return _ensure_cache()["risk"]


@app.get("/api/rootcause")
def api_rootcause():
    return _ensure_cache()["rootcause"]
