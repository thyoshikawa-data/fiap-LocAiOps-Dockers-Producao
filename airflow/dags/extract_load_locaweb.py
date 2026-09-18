"""
DAG de extração e carga (camada 2 da arquitetura) — LocAiOps.

Lê o dataset de incidentes ITSM (Excel real da Locaweb em produção; amostra
sintética `data/sample_synthetic.csv` neste ambiente de demonstração) e carrega
em `locaiops.incidentes_raw`, no Postgres. Os modelos de ML (camada 3, servidos
pela API em `api/`) leem diretamente dessa tabela — não do arquivo de origem.

O dataset é histórico (não muda todo dia), então a carga é full-refresh
(TRUNCATE + INSERT). Roda diariamente para refletir eventuais atualizações do
extrato de origem.
"""

import os
from datetime import datetime

import pandas as pd
from airflow.decorators import dag, task
from sqlalchemy import create_engine

DATASET_PATH = os.environ.get("LW_DATASET_PATH", "/opt/airflow/data/sample_synthetic.csv")
DB_URI = os.environ.get(
    "LOCAIOPS_DB_URI", "postgresql+psycopg2://locaiops:locaiops@postgres:5432/airflow"
)

COLUMN_MAP = {
    "Número": "numero",
    "Aberto": "aberto",
    "Resolvido": "resolvido",
    "Encerrado": "encerrado",
    "Prioridade": "prioridade",
    "Categoria": "categoria",
    "Subcategoria": "subcategoria",
    "Produto": "produto",
    "Item de configuração": "item_configuracao",
    "Grupo designado": "grupo_designado",
    "Aberto por": "aberto_por",
    "Entrou para KPI?": "entrou_kpi",
    "KPI Violado?": "kpi_violado",
    "Código de fechamento": "codigo_fechamento",
    "Solução": "solucao",
    "Duração": "duracao_segundos",
}


@dag(
    dag_id="extract_load_locaweb",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["locaiops", "extracao"],
)
def extract_load_locaweb():
    @task
    def extract() -> str:
        if not os.path.exists(DATASET_PATH):
            raise FileNotFoundError(
                f"Dataset não encontrado em {DATASET_PATH}. Em produção, monte o "
                "LW-DATASET.xlsx real da Locaweb; no ambiente de demo, gere a amostra "
                "sintética com data/generate_sample.py."
            )
        if DATASET_PATH.endswith(".xlsx"):
            df = pd.read_excel(DATASET_PATH, sheet_name="Dataset Geral")
        else:
            df = pd.read_csv(DATASET_PATH)
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns=COLUMN_MAP)
        tmp_path = "/tmp/incidentes_extraidos.parquet"
        df.to_parquet(tmp_path)
        print(f"Extraídos {len(df):,} registros de {DATASET_PATH}")
        return tmp_path

    @task
    def load(parquet_path: str) -> None:
        df = pd.read_parquet(parquet_path)
        for col in ["aberto", "resolvido", "encerrado"]:
            df[col] = pd.to_datetime(df[col], errors="coerce")

        engine = create_engine(DB_URI)
        with engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE TABLE locaiops.incidentes_raw")
            df.to_sql(
                "incidentes_raw",
                conn,
                schema="locaiops",
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000,
            )
        print(f"Carregados {len(df):,} registros em locaiops.incidentes_raw")

    load(extract())


extract_load_locaweb()
