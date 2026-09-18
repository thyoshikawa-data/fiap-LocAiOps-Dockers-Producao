-- LocAiOps — schema da camada de armazenamento (PostgreSQL)
-- Executado automaticamente pelo Postgres na primeira inicialização do container
-- (montado em /docker-entrypoint-initdb.d).

CREATE SCHEMA IF NOT EXISTS locaiops;

CREATE TABLE IF NOT EXISTS locaiops.incidentes_raw (
    numero               TEXT PRIMARY KEY,
    aberto               TIMESTAMP,
    resolvido            TIMESTAMP,
    encerrado            TIMESTAMP,
    prioridade           TEXT,
    categoria            TEXT,
    subcategoria         TEXT,
    produto              TEXT,
    item_configuracao    TEXT,
    grupo_designado      TEXT,
    aberto_por           TEXT,
    entrou_kpi           TEXT,
    kpi_violado          TEXT,
    codigo_fechamento    TEXT,
    solucao              TEXT,
    duracao_segundos     DOUBLE PRECISION,
    carga_em             TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidentes_aberto ON locaiops.incidentes_raw (aberto);
CREATE INDEX IF NOT EXISTS idx_incidentes_produto ON locaiops.incidentes_raw (produto);
CREATE INDEX IF NOT EXISTS idx_incidentes_prioridade ON locaiops.incidentes_raw (prioridade);

COMMENT ON TABLE locaiops.incidentes_raw IS
    'Incidentes ITSM carregados pela DAG extract_load_locaweb. Em produção real, aponta '
    'para o dataset oficial da Locaweb; no ambiente de demonstração, é carregada com uma '
    'amostra sintética (data/sample_synthetic.csv), sem nenhum dado real de cliente.';
