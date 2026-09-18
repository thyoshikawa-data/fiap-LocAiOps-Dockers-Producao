# LocAiOps — Arquitetura de Produção

Challenge Locaweb · FIAP 2TSCOA · Sprint 4 (entrega final).

Este repositório implementa, de ponta a ponta, a arquitetura de produção do LocAiOps:
extração orquestrada por Airflow, armazenamento em PostgreSQL, modelos de ML e uma API
própria que serve as previsões — a mesma abordagem descrita no PPT de solução final.

É complementar ao repositório principal do projeto, [fiap-LocAiOps](https://github.com/thyoshikawa-data/fiap-LocAiOps),
que contém o dashboard público (Next.js, publicado na Vercel em
[fiap-loc-ai-ops.vercel.app](https://fiap-loc-ai-ops.vercel.app/)). Enquanto aquele repositório
roda com o pipeline simplificado (Python → JSON estático), este demonstra a stack completa
rodando localmente via Docker.

## Arquitetura

```
Dataset ITSM  ->  Airflow (extração/ETL)  ->  PostgreSQL  ->  Modelos de ML (API FastAPI)  ->  Dashboard
```

| Camada | Componente | Onde está aqui |
|---|---|---|
| 1. Fontes de dados | Dataset ITSM da Locaweb | `data/` |
| 2. Extração e orquestração | Apache Airflow | `airflow/dags/extract_load_locaweb.py` |
| 3. Armazenamento | PostgreSQL | `db/schema.sql` |
| 4. Modelos de ML | scikit-learn (RandomForest, KMeans) | `api/pipeline.py` |
| 5. Camada de serviço | API REST (FastAPI) | `api/main.py` |
| 6. Visualização | Dashboard Next.js (repositório principal, publicado na Vercel) | — |

## Dataset: real vs. amostra sintética

O `LW-DATASET.xlsx` real da Locaweb é confidencial e **não faz parte deste repositório**
(mesma política do repositório principal). Para permitir rodar e testar toda a arquitetura
sem ele, este repositório inclui uma amostra **sintética** (dados fabricados, não reais) em
`data/sample_synthetic.csv`, gerada por `data/generate_sample.py`.

Para rodar com o dataset real: coloque `LW-DATASET.xlsx` em `data/` e defina
`LW_DATASET_PATH=/opt/airflow/data/LW-DATASET.xlsx` no `docker-compose.yml` (variável do
serviço `airflow`).

## Como rodar

Pré-requisito: Docker + Docker Compose.

```bash
docker compose up -d --build
```

Serviços expostos:

| Serviço | URL | Credenciais |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| API (FastAPI) | http://localhost:8000/docs | — |
| PostgreSQL | localhost:5432 | locaiops / locaiops |

Depois de subir os containers, dispare a DAG de extração/carga (via UI do Airflow ou CLI):

```bash
docker compose exec airflow-webserver airflow dags trigger extract_load_locaweb
```

Com os dados carregados em `locaiops.incidentes_raw`, a API já pode gerar as previsões:

```bash
curl -X POST http://localhost:8000/api/refresh
curl http://localhost:8000/api/overview
curl http://localhost:8000/api/forecast
curl http://localhost:8000/api/risk
curl http://localhost:8000/api/rootcause
```

## Modelos

Mesma lógica do pipeline do repositório principal (`locaiops-mvp/pipeline/generate_dashboard_data.py`),
adaptada para ler do Postgres em vez do Excel:

- **Previsão de volume**: `RandomForestRegressor` sobre série diária (lags + médias móveis).
- **Risco de violação de SLA**: `RandomForestClassifier`, avaliado em holdout genuíno (tickets
  nunca vistos no treino do modelo que gera a probabilidade).
- **Causa raiz**: `KMeans` (k=4) sobre duração e horário de abertura.

## Equipe

Silvielen Couto (RM564378) e Thales Yoshikawa (RM562897) — FIAP 2TSCOA, Challenge Locaweb.
