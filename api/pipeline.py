"""
Camadas 3 e 4 da arquitetura — modelos de ML e lógica de previsão/risco/causa raiz.

Adaptado de `locaiops-mvp/pipeline/generate_dashboard_data.py`: mesma abordagem
de modelagem (RandomForestRegressor para volume, RandomForestClassifier para
risco de SLA com holdout genuíno, KMeans para causa raiz), só que lendo de
`locaiops.incidentes_raw` (Postgres) em vez do Excel diretamente.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42


def load_dataframe(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM locaiops.incidentes_raw", engine)
    for col in ["aberto", "resolvido", "encerrado"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["entrou_kpi_bool"] = df["entrou_kpi"].astype(str).str.strip().str.upper().eq("SIM")
    df["kpi_violado_bool"] = df["kpi_violado"].astype(str).str.strip().str.upper().eq("SIM")
    df["hora_abertura"] = df["aberto"].dt.hour
    df["dia_semana"] = df["aberto"].dt.dayofweek
    return df


def build_daily_series(df: pd.DataFrame) -> pd.DataFrame:
    full = df.groupby(df["aberto"].dt.date).size().rename("volume").reset_index()
    full = full.rename(columns={"aberto": "data"})
    full["data"] = pd.to_datetime(full["data"])
    idx = pd.date_range(full["data"].min(), full["data"].max(), freq="D")
    full = full.set_index("data").reindex(idx, fill_value=0).rename_axis("data").reset_index()
    return full


def make_features(series_df: pd.DataFrame) -> pd.DataFrame:
    s = series_df.copy()
    s["dow"] = s["data"].dt.dayofweek
    s["is_weekend"] = s["dow"].isin([5, 6]).astype(int)
    for lag in (1, 2, 7):
        s[f"lag_{lag}"] = s["volume"].shift(lag)
    s["roll_mean_7"] = s["volume"].shift(1).rolling(7).mean()
    s["roll_mean_14"] = s["volume"].shift(1).rolling(14).mean()
    s["trend"] = np.arange(len(s))
    return s


FEATURES = ["dow", "is_weekend", "lag_1", "lag_2", "lag_7", "roll_mean_7", "roll_mean_14", "trend"]


def forecast_volume(df: pd.DataFrame) -> dict:
    daily = build_daily_series(df)
    feat = make_features(daily).dropna().reset_index(drop=True)

    test_size = min(14, max(1, len(feat) // 5))
    train, test = feat.iloc[:-test_size], feat.iloc[-test_size:]

    model = RandomForestRegressor(n_estimators=300, random_state=RANDOM_STATE, min_samples_leaf=2)
    model.fit(train[FEATURES], train["volume"])
    pred_test = model.predict(test[FEATURES])

    mae = float(mean_absolute_error(test["volume"], pred_test))
    denom = test["volume"].replace(0, np.nan)
    mape_series = (np.abs(test["volume"] - pred_test) / denom).dropna()
    mape = float(mape_series.mean() * 100) if len(mape_series) else None

    model_full = RandomForestRegressor(n_estimators=300, random_state=RANDOM_STATE, min_samples_leaf=2)
    model_full.fit(feat[FEATURES], feat["volume"])

    history = daily.copy()
    forecasts = []
    last_date = history["data"].max()
    for step in range(1, 8):
        feat_hist = make_features(history)
        row = feat_hist.iloc[[-1]]
        next_date = last_date + pd.Timedelta(days=step)
        next_row = pd.DataFrame(
            {
                "data": [next_date],
                "dow": [next_date.dayofweek],
                "is_weekend": [1 if next_date.dayofweek in (5, 6) else 0],
                "lag_1": [history["volume"].iloc[-1]],
                "lag_2": [history["volume"].iloc[-2]],
                "lag_7": [history["volume"].iloc[-7]],
                "roll_mean_7": [history["volume"].tail(7).mean()],
                "roll_mean_14": [history["volume"].tail(14).mean()],
                "trend": [row["trend"].values[0] + 1],
            }
        )
        pred = max(float(model_full.predict(next_row[FEATURES])[0]), 0.0)
        forecasts.append({"data": next_date.date().isoformat(), "previsto": round(pred, 1)})
        history = pd.concat(
            [history, pd.DataFrame({"data": [next_date], "volume": [pred]})], ignore_index=True
        )

    return {
        "metricas": {
            "mae_backtest": round(mae, 2),
            "mape_backtest_pct": round(mape, 2) if mape is not None else None,
            "janela_backtest_dias": test_size,
            "amostras_treino": int(len(train)),
        },
        "previsao_7d": forecasts,
        "d1": forecasts[0]["previsto"],
        "d7_total": round(sum(f["previsto"] for f in forecasts), 1),
    }


def risk_model(df: pd.DataFrame) -> dict:
    kpi_df = df[df["entrou_kpi_bool"]].copy()
    kpi_df["produto_null"] = kpi_df["produto"].isna().astype(int)
    kpi_df["item_cfg_null"] = kpi_df["item_configuracao"].isna().astype(int)

    cat_cols = ["prioridade", "grupo_designado", "aberto_por"]
    X = pd.get_dummies(kpi_df[cat_cols].astype(str), dummy_na=True)
    X["hora_abertura"] = kpi_df["hora_abertura"]
    X["dia_semana"] = kpi_df["dia_semana"]
    X["produto_null"] = kpi_df["produto_null"]
    X["item_cfg_null"] = kpi_df["item_cfg_null"]
    y = kpi_df["kpi_violado_bool"].astype(int)

    rng = np.random.RandomState(RANDOM_STATE)
    idx = rng.permutation(len(X))
    split = int(len(idx) * 0.75)
    train_idx, test_idx = idx[:split], idx[split:]

    clf = RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=RANDOM_STATE, min_samples_leaf=30
    )
    clf.fit(X.iloc[train_idx], y.iloc[train_idx])
    proba_test = clf.predict_proba(X.iloc[test_idx])[:, 1]

    try:
        auc = float(roc_auc_score(y.iloc[test_idx], proba_test))
    except ValueError:
        auc = None

    kpi_df_reset = kpi_df.reset_index(drop=True)
    holdout_mask = np.zeros(len(kpi_df_reset), dtype=bool)
    holdout_mask[test_idx] = True
    holdout_df = kpi_df_reset[holdout_mask].copy()
    holdout_df["prob_violacao"] = proba_test

    top_risco = holdout_df.sort_values("prob_violacao", ascending=False).head(8)

    alertas = [
        {
            "ticket": row["numero"],
            "prioridade": row["prioridade"],
            "produto": row["produto"] if pd.notna(row["produto"]) else "não categorizado",
            "probabilidade": round(float(row["prob_violacao"]) * 100, 1),
            "violou_sla_real": bool(row["kpi_violado_bool"]),
        }
        for _, row in top_risco.iterrows()
    ]

    return {
        "metricas": {
            "auc_holdout": round(auc, 3) if auc is not None else None,
            "taxa_violacao_base_pct": round(float(y.mean()) * 100, 2),
            "amostras_treino": int(len(train_idx)),
            "amostras_teste": int(len(test_idx)),
        },
        "alertas": alertas,
    }


def root_cause(df: pd.DataFrame) -> dict:
    kpi_df = df[df["entrou_kpi_bool"]].copy()

    top_produtos = (
        df["produto"].value_counts(dropna=True).head(6).rename_axis("produto").reset_index(name="volume")
    ).to_dict("records")

    por_abertura = (
        kpi_df.groupby("aberto_por")["kpi_violado_bool"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "taxa_violacao", "count": "amostras"})
        .reset_index()
    )
    por_abertura["taxa_violacao"] = (por_abertura["taxa_violacao"] * 100).round(2)

    cluster_df = df.dropna(subset=["duracao_segundos"]).copy()
    cluster_df = cluster_df[cluster_df["duracao_segundos"] >= 0]
    feats = cluster_df[["duracao_segundos", "hora_abertura", "dia_semana"]].astype(float)
    scaler = StandardScaler()
    X = scaler.fit_transform(feats)
    k = 4
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    cluster_df["cluster"] = km.fit_predict(X)

    resumo_clusters = []
    for c in range(k):
        sub = cluster_df[cluster_df["cluster"] == c]
        resumo_clusters.append(
            {
                "cluster": int(c),
                "tamanho": int(len(sub)),
                "duracao_media_min": round(float(sub["duracao_segundos"].mean() / 60), 1),
                "pct_manual": round(float((sub["aberto_por"] == "Manual").mean() * 100), 1),
            }
        )

    return {
        "top_produtos": top_produtos,
        "violacao_por_origem": por_abertura.to_dict("records"),
        "clusters_operacionais": resumo_clusters,
    }


def overview(df: pd.DataFrame, forecast: dict, risk: dict) -> dict:
    kpi_df = df[df["entrou_kpi_bool"]]
    return {
        "periodo_dataset": {
            "inicio": df["aberto"].min().date().isoformat(),
            "fim": df["aberto"].max().date().isoformat(),
            "total_registros": int(len(df)),
        },
        "kpis": {
            "previsao_d1": forecast["d1"],
            "previsao_d7_total": forecast["d7_total"],
            "taxa_violacao_sla_pct": round(float(kpi_df["kpi_violado_bool"].mean()) * 100, 2),
            "auc_modelo_risco": risk["metricas"]["auc_holdout"],
        },
    }


def run_pipeline(engine) -> dict:
    df = load_dataframe(engine)
    forecast = forecast_volume(df)
    risk = risk_model(df)
    causes = root_cause(df)
    ov = overview(df, forecast, risk)
    return {"overview": ov, "forecast": forecast, "risk": risk, "rootcause": causes}
