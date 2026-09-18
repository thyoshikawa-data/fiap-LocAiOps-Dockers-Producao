"""Gera uma amostra SINTÉTICA (dados fabricados, não reais) de incidentes ITSM,
só para permitir subir e testar toda a arquitetura (Airflow -> Postgres -> API ->
Grafana) sem depender do dataset confidencial real da Locaweb.

Uso: python generate_sample.py  ->  gera sample_synthetic.csv nesta mesma pasta.
"""

import numpy as np
import pandas as pd

RANDOM_STATE = 7
N = 4000

rng = np.random.RandomState(RANDOM_STATE)

produtos = ["lsin", "lhco", "lcem", "lhvp", "lrev"]
produto_pesos = [0.35, 0.28, 0.15, 0.12, 0.10]
prioridades = ["2 - Alta", "3 - Média", "4 - Baixa"]
prioridade_pesos = [0.25, 0.45, 0.30]
abertos_por = ["Manual", "Monitoramento"]
grupos = ["NOC N1", "NOC N2", "SRE", "Suporte N3"]
categorias = ["Infraestrutura", "Aplicação", "Rede", "Banco de Dados"]
codigos_fechamento = ["Falha de Aplicação", "Falha de Rede", "Erro de Configuração", "Manutenção Programada"]

start = pd.Timestamp("2025-01-01")
end = pd.Timestamp("2025-12-31")
aberto = start + pd.to_timedelta(rng.randint(0, (end - start).days * 24 * 60, size=N), unit="m")
aberto = pd.Series(aberto).sort_values().reset_index(drop=True)

duracao_min = rng.gamma(shape=2.0, scale=45, size=N)  # minutos
resolvido = aberto + pd.to_timedelta(duracao_min, unit="m")
encerrado = resolvido + pd.to_timedelta(rng.randint(0, 240, size=N), unit="m")

aberto_por = rng.choice(abertos_por, size=N, p=[0.15, 0.85])
prioridade = rng.choice(prioridades, size=N, p=prioridade_pesos)

# violação de SLA: rara (~1%), um pouco mais comum em aberturas manuais
base_rate = 0.006
manual_bonus = 0.02
prob_violacao = np.where(aberto_por == "Manual", base_rate + manual_bonus, base_rate)
kpi_violado = rng.binomial(1, prob_violacao)

df = pd.DataFrame(
    {
        "Número": [f"INC{100000 + i}" for i in range(N)],
        "Aberto": aberto,
        "Resolvido": resolvido,
        "Encerrado": encerrado,
        "Prioridade": prioridade,
        "Categoria": rng.choice(categorias, size=N),
        "Subcategoria": rng.choice(["Sub A", "Sub B", "Sub C"], size=N),
        "Produto": rng.choice(produtos, size=N, p=produto_pesos),
        "Item de configuração": [f"CI-{rng.randint(1, 400)}" for _ in range(N)],
        "Grupo designado": rng.choice(grupos, size=N),
        "Aberto por": aberto_por,
        "Entrou para KPI?": np.where(np.isin(prioridade, ["2 - Alta", "3 - Média"]), "SIM", "NAO"),
        "KPI Violado?": np.where(kpi_violado == 1, "SIM", "NAO"),
        "Código de fechamento": rng.choice(codigos_fechamento, size=N),
        "Solução": rng.choice(["Reinício de serviço", "Ajuste de configuração", "Patch aplicado"], size=N),
        "Duração": duracao_min * 60,  # segundos
    }
)

out_path = "sample_synthetic.csv"
df.to_csv(out_path, index=False)
print(f"Gerado {out_path} com {len(df)} incidentes sintéticos (dados fabricados, não reais).")
