"""
processing.py — Toda a lógica de processamento dos arquivos
"""
import re
import unicodedata
import numpy as np
import pandas as pd

try:
    import python_calamine
    _ENGINE = "calamine"
except ImportError:
    _ENGINE = "openpyxl"

# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ══════════════════════════════════════════════════════════════
def _remover_acentos(t: str) -> str:
    return unicodedata.normalize("NFD", t).encode("ascii","ignore").decode().lower().strip()

def normalizar_colunas(df: pd.DataFrame, mapeamento: dict) -> pd.DataFrame:
    norm = {_remover_acentos(c): c for c in df.columns}
    ren  = {}
    for k in mapeamento:
        nk = _remover_acentos(k)
        if nk in norm and norm[nk] != k:
            ren[norm[nk]] = k
    return df.rename(columns=ren) if ren else df

def _limpar_col(serie: pd.Series) -> pd.Series:
    return (serie.astype(str)
                 .str.encode("utf-8", errors="ignore").str.decode("utf-8")
                 .str.replace(r"[\xa0\t\r\n\u200b\u200c\u200d\ufeff]"," ",regex=True)
                 .str.replace(r"\s+"," ",regex=True)
                 .str.strip().str.upper())

def _wb_to_str(serie: pd.Series) -> pd.Series:
    try:
        return serie.astype(float).astype("int64").astype(str).str.strip()
    except Exception:
        return serie.astype(str).str.strip()

def _ler_uploads(arquivos, cols: dict) -> pd.DataFrame:
    if not arquivos:
        return pd.DataFrame()
    col_names = list(cols.keys())
    frames = []
    for arq in arquivos:
        try:
            df = pd.read_excel(arq, engine=_ENGINE, usecols=lambda c: c in col_names)
        except Exception:
            df = pd.read_excel(arq, engine=_ENGINE)
        df = normalizar_colunas(df, cols)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# ══════════════════════════════════════════════════════════════
#  DETECÇÃO DE COLUNA DE DATA
# ══════════════════════════════════════════════════════════════
DATE_CANDIDATES = [
    "scan time","data","date","scan date","data escaneamento",
    "data de escaneamento","created time","creation time",
    "scan_time","data_hora","datetime","timestamp","inbound time"
]

def detectar_coluna_data(arquivo) -> str | None:
    """Lê as primeiras linhas e retorna o nome da coluna de data."""
    try:
        df = pd.read_excel(arquivo, engine=_ENGINE, nrows=10)
        arquivo.seek(0)
        for col in df.columns:
            if _remover_acentos(col) in DATE_CANDIDATES:
                return col
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
        for col in df.columns:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() >= 5:
                    return col
            except Exception:
                pass
    except Exception:
        pass
    return None

def ler_datas_recebimento(arquivos, col_data: str):
    """Lê só a coluna de data de todos os arquivos e retorna lista de datas únicas."""
    frames = []
    for arq in arquivos:
        try:
            df = pd.read_excel(arq, engine=_ENGINE, usecols=[col_data])
            arq.seek(0)
            frames.append(df)
        except Exception:
            pass
    if not frames:
        return []
    df_all = pd.concat(frames, ignore_index=True)
    df_all[col_data] = pd.to_datetime(df_all[col_data], errors="coerce")
    return sorted(df_all[col_data].dt.date.dropna().unique())

# ══════════════════════════════════════════════════════════════
#  MAPA DE SIGLAS
# ══════════════════════════════════════════════════════════════
def construir_mapa_sigla(df_sup: pd.DataFrame) -> dict:
    df = df_sup.copy()
    df["SIGLA"] = _limpar_col(df["SIGLA"])
    mapa = {}
    for _, row in df.iterrows():
        sigla  = row["SIGLA"]
        region = row["REGION"]
        mapa[sigla] = (sigla, region)
        codigo = re.sub(r'^(RDC|DC|DS)[\s\-]+', '', sigla).strip()
        if codigo not in mapa:
            mapa[codigo] = (sigla, region)
    return mapa

def padronizar_scan_station(df: pd.DataFrame, mapa: dict, col="Scan Station") -> pd.DataFrame:
    df = df.copy()
    df[col] = _limpar_col(df[col])
    mapa_sigla = {k: v[0] for k, v in mapa.items()}
    mapeado = df[col].map(mapa_sigla)
    sem = mapeado.isna()
    if sem.any():
        codigos = df.loc[sem, col].str.replace(r'^(RDC|DC|DS)[\s\-]+','',regex=True).str.strip()
        mapeado[sem] = codigos.map(mapa_sigla)
    df[col] = mapeado.fillna(df[col])
    return df

def filtrar_dados(df_sup, df_rec, mapa=None):
    if mapa is None:
        mapa = construir_mapa_sigla(df_sup)
    df_rec = df_rec.copy()
    df_rec["Scan Station"] = _limpar_col(df_rec["Scan Station"])
    ms = {k: v[0] for k, v in mapa.items()}
    mr = {k: v[1] for k, v in mapa.items()}
    ss = df_rec["Scan Station"]
    m  = ss.map(ms)
    sem = m.isna()
    if sem.any():
        cod = ss[sem].str.replace(r'^(RDC|DC|DS)[\s\-]+','',regex=True).str.strip()
        m[sem] = cod.map(ms)
    df_rec["Scan Station"] = m.fillna(ss)
    df_rec["REGION"] = df_rec["Scan Station"].map(mr).fillna("Sem Classificacao")
    return df_rec

def fazer_merge(df_sup, df_filt):
    df_sup = df_sup.copy()
    df_sup["SIGLA"] = _limpar_col(df_sup["SIGLA"])
    df = df_filt.copy()
    sg = set(df_sup["SIGLA"])
    sc = set(df["Scan Station"].dropna().unique())
    ss = sg - sc
    if ss:
        extras = (df_sup[df_sup["SIGLA"].isin(ss)][["SIGLA","REGION"]].copy()
                  .rename(columns={"SIGLA":"Scan Station"}))
        df = pd.concat([df, extras], ignore_index=True)
    df["REGION"] = df["REGION"].fillna("Sem Classificacao")
    return df

# ══════════════════════════════════════════════════════════════
#  PIVOT — LÓGICA POR WAYBILL
# ══════════════════════════════════════════════════════════════
def criar_pivot(df_merge, df_out, df_ent=None):
    col_wb = "Waybill Number"
    ds_base = (df_merge[["Scan Station","REGION"]]
               .drop_duplicates("Scan Station").dropna(subset=["Scan Station"]))

    # Recebido
    if col_wb in df_merge.columns:
        df_wb = df_merge.dropna(subset=[col_wb]).copy()
        df_wb[col_wb] = _wb_to_str(df_wb[col_wb])
        df_wb = df_wb.drop_duplicates(subset=[col_wb])
        rec = df_wb.groupby("Scan Station").size().reset_index(name="Recebido")
        wb_set = set(df_wb[col_wb].unique())
    else:
        rec = (df_merge.dropna(subset=["Scan Station"])["Scan Station"]
               .value_counts().reset_index(name="Recebido"))
        wb_set = set()

    # Expedido
    df_out2 = df_out.copy()
    df_out2["Scan Station"] = _limpar_col(df_out2["Scan Station"])
    if "Waybill No." in df_out2.columns and wb_set:
        df_out2["Waybill No."] = _wb_to_str(df_out2["Waybill No."])
        df_out2 = df_out2[df_out2["Waybill No."].isin(wb_set)]
        exp = (df_out2.drop_duplicates("Waybill No.")
                      .groupby("Scan Station").size()
                      .reset_index(name="Expedido"))
    else:
        exp = df_out2["Scan Station"].value_counts().reset_index(name="Expedido")

    ds_out_extra = exp[~exp["Scan Station"].isin(ds_base["Scan Station"])][["Scan Station"]].copy()
    ds_out_extra["REGION"] = "Sem Classificacao"
    ds_todas = pd.concat([ds_base, ds_out_extra], ignore_index=True).drop_duplicates("Scan Station")
    p = ds_todas.merge(rec, on="Scan Station", how="left")
    p = p.merge(exp, on="Scan Station", how="left")
    p["Recebido"] = p["Recebido"].fillna(0).astype(int)
    p["Expedido"] = p["Expedido"].fillna(0).astype(int)

    # Entregas
    if df_ent is not None and len(df_ent) > 0 and wb_set:
        df_ent2 = df_ent.copy()
        df_ent2["Scan Station"] = _limpar_col(df_ent2["Scan Station"])
        if "Waybill No." in df_ent2.columns:
            df_ent2["Waybill No."] = _wb_to_str(df_ent2["Waybill No."])
            df_ent2 = df_ent2[df_ent2["Waybill No."].isin(wb_set)]
            ent = (df_ent2.drop_duplicates("Waybill No.")
                          .groupby("Scan Station").size()
                          .reset_index(name="Entregas"))
        else:
            ent = df_ent2["Scan Station"].value_counts().reset_index(name="Entregas")
        ds_ent_extra = ent[~ent["Scan Station"].isin(p["Scan Station"])][["Scan Station"]].copy()
        ds_ent_extra["REGION"] = "Sem Classificacao"
        if len(ds_ent_extra):
            p = pd.concat([p, ds_ent_extra], ignore_index=True).reset_index(drop=True)
        p["Entregas"] = p["Scan Station"].map(ent.set_index("Scan Station")["Entregas"]).fillna(0).astype(int)
    else:
        p["Entregas"] = 0

    p["recebido no DS"]     = p["Recebido"]
    p["em rota de entrega"] = p["Expedido"]
    p["Total Geral"]        = p["Recebido"]
    return p

def criar_pivot_cidades(df_merge, df_out=None, df_ent=None):
    col_wb = "Waybill Number"
    df = df_merge.copy()
    if col_wb not in df.columns:
        return pd.DataFrame()
    df = df.dropna(subset=[col_wb]).copy()
    df[col_wb] = _wb_to_str(df[col_wb])
    df = df.drop_duplicates(subset=[col_wb]).dropna(subset=["Scan Station"])
    if "Destination City" in df.columns:
        df["Destination City"] = (df["Destination City"].fillna("Sem Cidade")
                                   .replace("","Sem Cidade").astype(str).str.strip())
    else:
        df["Destination City"] = "Sem Cidade"

    rec_city = (df.groupby(["Scan Station","Destination City"], observed=True)
                  .size().reset_index(name="Recebido"))
    wb_set = set(df[col_wb].unique())
    idx = df[[col_wb,"Scan Station","Destination City"]].set_index(col_wb)

    def _join_wb(df_src, col_wb_src, wb_set, idx):
        df_src = df_src[[col_wb_src]].copy()
        df_src[col_wb_src] = _wb_to_str(df_src[col_wb_src])
        df_src = df_src[df_src[col_wb_src].isin(wb_set)].drop_duplicates()
        df_src["Scan Station"]    = df_src[col_wb_src].map(idx["Scan Station"])
        df_src["Destination City"] = df_src[col_wb_src].map(idx["Destination City"])
        return (df_src.dropna(subset=["Scan Station","Destination City"])
                      .groupby(["Scan Station","Destination City"], observed=True)
                      .size().reset_index(name="cnt"))

    if df_out is not None and len(df_out) > 0 and "Waybill No." in df_out.columns:
        exp_city = _join_wb(df_out, "Waybill No.", wb_set, idx).rename(columns={"cnt":"Expedido"})
        rec_city = rec_city.merge(exp_city, on=["Scan Station","Destination City"], how="left")
    else:
        rec_city["Expedido"] = 0

    if df_ent is not None and len(df_ent) > 0 and "Waybill No." in df_ent.columns:
        ent_city = _join_wb(df_ent, "Waybill No.", wb_set, idx).rename(columns={"cnt":"Entregas"})
        rec_city = rec_city.merge(ent_city, on=["Scan Station","Destination City"], how="left")
    else:
        rec_city["Entregas"] = 0

    rec_city["Expedido"] = rec_city["Expedido"].fillna(0).astype(int)
    rec_city["Entregas"] = rec_city["Entregas"].fillna(0).astype(int)
    rec_city["recebido no DS"]     = rec_city["Recebido"]
    rec_city["em rota de entrega"] = rec_city["Expedido"]
    rec_city["Total Geral"]        = rec_city["Recebido"]
    rec_city["Taxa de Expedicao"]  = np.where(rec_city["Recebido"]>0,
        rec_city["Expedido"]/rec_city["Recebido"], 0.0)
    rec_city["Taxa de Entrega"]    = np.where(rec_city["Recebido"]>0,
        (rec_city["Entregas"]/rec_city["Recebido"]).clip(upper=1.0), 0.0)
    return rec_city

def calcular_metricas(pivot, df_meta=None):
    p = pivot.copy()
    p["Taxa de Expedicao"] = np.where(p["Recebido"]>0, p["Expedido"]/p["Recebido"], 0.0)
    p["Taxa de Entrega"]   = np.where(p["Recebido"]>0,
        (p["Entregas"]/p["Recebido"]).clip(upper=1.0), 0.0)
    if df_meta is not None and len(df_meta)>0:
        p["Meta"] = p["Scan Station"].map(df_meta.set_index("DS")["Meta"].to_dict()).fillna(0.5)
    else:
        p["Meta"] = 0.5
    p["Atingiu Meta"] = p["Taxa de Expedicao"] >= p["Meta"]
    return p

def separar_por_regiao(df_merge, pivot):
    pf = pivot.copy()
    if "REGION" not in pf.columns:
        rmap = (df_merge[["Scan Station","REGION"]]
                .drop_duplicates("Scan Station").dropna(subset=["Scan Station"])
                .set_index("Scan Station")["REGION"])
        pf["REGION"] = pf["Scan Station"].map(rmap)
    def _f(r):
        return pf[pf["REGION"].astype(str).str.strip().str.lower()==r.lower()].reset_index(drop=True)
    return pf, _f("capital"), _f("metropolitan"), _f("countryside")
