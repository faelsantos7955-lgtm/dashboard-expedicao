"""
database.py — Integração com Supabase
Tabelas necessárias (criar no Supabase SQL Editor):

CREATE TABLE expedicao_diaria (
    id            BIGSERIAL PRIMARY KEY,
    data_ref      DATE        NOT NULL,
    scan_station  TEXT        NOT NULL,
    region        TEXT,
    recebido      INTEGER     DEFAULT 0,
    expedido      INTEGER     DEFAULT 0,
    entregas      INTEGER     DEFAULT 0,
    taxa_exp      FLOAT       DEFAULT 0,
    taxa_ent      FLOAT       DEFAULT 0,
    meta          FLOAT       DEFAULT 0.5,
    atingiu_meta  BOOLEAN     DEFAULT FALSE,
    processado_em TIMESTAMPTZ DEFAULT NOW(),
    processado_por TEXT,
    UNIQUE (data_ref, scan_station)
);

CREATE TABLE expedicao_cidades (
    id              BIGSERIAL PRIMARY KEY,
    data_ref        DATE  NOT NULL,
    scan_station    TEXT  NOT NULL,
    destination_city TEXT NOT NULL,
    recebido        INTEGER DEFAULT 0,
    expedido        INTEGER DEFAULT 0,
    entregas        INTEGER DEFAULT 0,
    taxa_exp        FLOAT   DEFAULT 0,
    taxa_ent        FLOAT   DEFAULT 0,
    UNIQUE (data_ref, scan_station, destination_city)
);

-- Habilitar RLS (Row Level Security) para separar por usuário/região
ALTER TABLE expedicao_diaria  ENABLE ROW LEVEL SECURITY;
ALTER TABLE expedicao_cidades ENABLE ROW LEVEL SECURITY;
"""

import os
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date, timedelta

# ── Conexão ───────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ══════════════════════════════════════════════════════════════
#  SALVAR
# ══════════════════════════════════════════════════════════════
def salvar_processamento(pivot_metricas: pd.DataFrame,
                          pivot_cidades: pd.DataFrame,
                          data_ref: date,
                          usuario: str):
    """Upsert dos resultados do dia no Supabase."""
    sb = get_supabase()

    # ── Tabela diária ─────────────────────────────────────────
    rows_diario = []
    for _, r in pivot_metricas.iterrows():
        rows_diario.append({
            "data_ref":      str(data_ref),
            "scan_station":  r["Scan Station"],
            "region":        r.get("REGION", ""),
            "recebido":      int(r.get("recebido no DS", 0)),
            "expedido":      int(r.get("em rota de entrega", 0)),
            "entregas":      int(r.get("Entregas", 0)),
            "taxa_exp":      float(r.get("Taxa de Expedicao", 0)),
            "taxa_ent":      float(r.get("Taxa de Entrega", 0)),
            "meta":          float(r.get("Meta", 0.5)),
            "atingiu_meta":  bool(r.get("Atingiu Meta", False)),
            "processado_por": usuario,
        })
    if rows_diario:
        sb.table("expedicao_diaria").upsert(
            rows_diario,
            on_conflict="data_ref,scan_station"
        ).execute()

    # ── Tabela cidades ────────────────────────────────────────
    rows_cidades = []
    for _, r in pivot_cidades.iterrows():
        rows_cidades.append({
            "data_ref":         str(data_ref),
            "scan_station":     r["Scan Station"],
            "destination_city": r["Destination City"],
            "recebido":         int(r.get("recebido no DS", 0)),
            "expedido":         int(r.get("em rota de entrega", 0)),
            "entregas":         int(r.get("Entregas", 0)),
            "taxa_exp":         float(r.get("Taxa de Expedicao", 0)),
            "taxa_ent":         float(r.get("Taxa de Entrega", 0)),
        })
    if rows_cidades:
        sb.table("expedicao_cidades").upsert(
            rows_cidades,
            on_conflict="data_ref,scan_station,destination_city"
        ).execute()

# ══════════════════════════════════════════════════════════════
#  LER
# ══════════════════════════════════════════════════════════════
def _filtrar_regioes(regioes_permitidas: list) -> list:
    """Retorna filtro de regiões para a query."""
    return regioes_permitidas  # lista de strings, ex: ["capital","metropolitan"]

def ler_dia(data_ref: date, regioes: list = None) -> pd.DataFrame:
    sb = get_supabase()
    q = sb.table("expedicao_diaria").select("*").eq("data_ref", str(data_ref))
    if regioes:
        q = q.in_("region", regioes)
    res = q.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def ler_periodo(data_ini: date, data_fim: date, regioes: list = None) -> pd.DataFrame:
    sb = get_supabase()
    q = (sb.table("expedicao_diaria").select("*")
           .gte("data_ref", str(data_ini))
           .lte("data_ref", str(data_fim)))
    if regioes:
        q = q.in_("region", regioes)
    res = q.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def ler_cidades_dia(data_ref: date, regioes: list = None) -> pd.DataFrame:
    sb = get_supabase()
    # Join via scan_station para filtrar região
    q = sb.table("expedicao_cidades").select("*").eq("data_ref", str(data_ref))
    res = q.execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if regioes and len(df) > 0:
        # Filtra pegando as DS da tabela diária
        df_ds = ler_dia(data_ref, regioes)
        if len(df_ds) > 0:
            ds_permitidas = set(df_ds["scan_station"].unique())
            df = df[df["scan_station"].isin(ds_permitidas)]
    return df

def ler_datas_disponiveis(regioes: list = None) -> list:
    sb = get_supabase()
    q = sb.table("expedicao_diaria").select("data_ref")
    if regioes:
        q = q.in_("region", regioes)
    res = q.execute()
    if not res.data:
        return []
    datas = sorted(set(r["data_ref"] for r in res.data), reverse=True)
    return datas
