"""
charts.py — Gráficos Plotly interativos
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Paleta
AZ="#4f8ef7"; LR="#f97316"; VD="#22c55e"; VM="#ef4444"
RX="#a855f7"; CZ="#64748b"; BG="#0f172a"; BP="#1e293b"; GD="#334155"; TX="#e2e8f0"

def _layout(fig, h=420, title=""):
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BP,
        font=dict(color=TX, family="DM Sans, Segoe UI, Arial"),
        legend=dict(bgcolor=BP, bordercolor=GD, borderwidth=1),
        margin=dict(t=50, b=40, l=50, r=30), height=h,
        title=dict(text=title, font=dict(size=14, color=TX)),
        hoverlabel=dict(bgcolor=BP, bordercolor=GD, font=dict(color=TX)))
    fig.update_xaxes(gridcolor=GD, zerolinecolor=GD)
    fig.update_yaxes(gridcolor=GD, zerolinecolor=GD)
    return fig

def _cor_taxa(taxa, meta=0.5):
    return VD if taxa >= meta else VM

# ══════════════════════════════════════════════════════════════
#  1. VOLUME POR DS (barras empilhadas)
# ══════════════════════════════════════════════════════════════
def chart_volume_ds(df: pd.DataFrame, top_n=20) -> go.Figure:
    df = df.copy().sort_values("expedido", ascending=False).head(top_n)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Recebido", x=df["scan_station"], y=df["recebido"],
        marker_color=AZ,
        text=df["recebido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white", size=9)))
    fig.add_trace(go.Bar(
        name="Expedido", x=df["scan_station"], y=df["expedido"],
        marker_color=LR,
        text=df["expedido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white", size=9)))
    if "entregas" in df.columns and df["entregas"].sum() > 0:
        fig.add_trace(go.Scatter(
            name="Entregas", x=df["scan_station"], y=df["entregas"],
            mode="markers", marker=dict(color=RX, size=9, symbol="diamond")))
    fig.update_layout(barmode="group", xaxis=dict(tickangle=-35))
    return _layout(fig, h=430, title=f"Volume por DS — Top {top_n}")

# ══════════════════════════════════════════════════════════════
#  2. TAXA DE EXPEDIÇÃO POR DS (barras horizontais)
# ══════════════════════════════════════════════════════════════
def chart_taxa_ds(df: pd.DataFrame, meta_col="meta") -> go.Figure:
    df = df.copy().sort_values("taxa_exp", ascending=True)
    cores = [_cor_taxa(r["taxa_exp"], r.get(meta_col, 0.5)) for _, r in df.iterrows()]
    metas = df[meta_col].values if meta_col in df.columns else [0.5]*len(df)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        orientation="h",
        x=df["taxa_exp"] * 100,
        y=df["scan_station"],
        marker=dict(color=cores),
        text=[f"{t:.1%}" for t in df["taxa_exp"]],
        textposition="outside",
        textfont=dict(size=10, color=TX),
        customdata=np.column_stack([df.get("recebido", 0), df.get("expedido", 0),
                                     metas * 100]),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Taxa: %{x:.1f}%<br>"
            "Recebido: %{customdata[0]:,}<br>"
            "Expedido: %{customdata[1]:,}<br>"
            "Meta: %{customdata[2]:.1f}%<extra></extra>")))
    fig.add_vline(x=50, line_dash="dash", line_color=TX,
                  annotation_text="Meta 50%", annotation_font_color=TX)
    fig.update_layout(
        xaxis=dict(ticksuffix="%", range=[0, 120]),
        height=max(400, len(df) * 26))
    return _layout(fig, title="Taxa de Expedição por DS")

# ══════════════════════════════════════════════════════════════
#  3. EVOLUÇÃO DIÁRIA (linha do tempo)
# ══════════════════════════════════════════════════════════════
def chart_evolucao_diaria(df_hist: pd.DataFrame) -> go.Figure:
    """df_hist deve ter: data_ref, recebido, expedido, entregas, taxa_exp"""
    df = (df_hist.groupby("data_ref", as_index=False)
                 .agg(recebido=("recebido","sum"),
                      expedido=("expedido","sum"),
                      entregas=("entregas","sum"))
                 .sort_values("data_ref"))
    df["taxa_exp"] = df["expedido"] / df["recebido"].replace(0, np.nan)
    df["taxa_ent"] = df["entregas"] / df["recebido"].replace(0, np.nan)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Recebido", x=df["data_ref"], y=df["recebido"],
        marker_color=AZ, opacity=0.7,
        text=df["recebido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white", size=9)))
    fig.add_trace(go.Bar(
        name="Expedido", x=df["data_ref"], y=df["expedido"],
        marker_color=LR, opacity=0.7,
        text=df["expedido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white", size=9)))
    fig.add_trace(go.Scatter(
        name="Taxa Exp. %", x=df["data_ref"], y=df["taxa_exp"]*100,
        mode="lines+markers+text", yaxis="y2",
        line=dict(color=VD, width=3), marker=dict(size=8),
        text=[f"{t:.0%}" for t in df["taxa_exp"].fillna(0)],
        textposition="top center", textfont=dict(color=VD, size=11)))
    if df["entregas"].sum() > 0:
        fig.add_trace(go.Scatter(
            name="Taxa Ent. %", x=df["data_ref"], y=df["taxa_ent"]*100,
            mode="lines+markers", yaxis="y2",
            line=dict(color=RX, width=2, dash="dot"), marker=dict(size=7)))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Quantidade"),
        yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 120]))
    return _layout(fig, h=420, title="Evolução Diária — Volume e Taxa")

# ══════════════════════════════════════════════════════════════
#  4. MAPA DE CALOR DS × CIDADE
# ══════════════════════════════════════════════════════════════
def chart_heatmap_cidades(df_cidades: pd.DataFrame, metrica="taxa_exp") -> go.Figure:
    if len(df_cidades) == 0:
        return go.Figure()
    pivot = (df_cidades.pivot_table(
                index="destination_city", columns="scan_station",
                values=metrica, aggfunc="mean")
             .fillna(0))
    # Limitar a top 20 cidades e top 15 DS por volume
    top_ds = (df_cidades.groupby("scan_station")["recebido"].sum()
              .nlargest(15).index.tolist())
    top_city = (df_cidades.groupby("destination_city")["recebido"].sum()
                .nlargest(20).index.tolist())
    pivot = pivot.loc[
        [c for c in top_city if c in pivot.index],
        [c for c in top_ds   if c in pivot.columns]]

    fig = go.Figure(go.Heatmap(
        z=pivot.values * 100,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0,"#7f1d1d"],[0.5,"#1e3a5f"],[1,"#14532d"]],
        zmin=0, zmax=100,
        text=[[f"{v:.0f}%" for v in row] for row in pivot.values * 100],
        texttemplate="%{text}",
        textfont=dict(size=9, color="white"),
        hovertemplate="DS: %{x}<br>Cidade: %{y}<br>Taxa: %{z:.1f}%<extra></extra>",
        colorbar=dict(ticksuffix="%", title="Taxa Exp.")))
    fig.update_layout(xaxis=dict(tickangle=-35))
    return _layout(fig, h=max(420, len(pivot)*22 + 80),
                   title="Mapa de Calor — Taxa de Expedição por DS × Cidade")

# ══════════════════════════════════════════════════════════════
#  5. COMPARATIVO DIA / SEMANA / MÊS
# ══════════════════════════════════════════════════════════════
def chart_comparativo(df_hist: pd.DataFrame, periodo="semana") -> go.Figure:
    """Agrupa por dia, semana ou mês e compara taxa."""
    df = df_hist.copy()
    df["data_ref"] = pd.to_datetime(df["data_ref"])

    if periodo == "dia":
        df["grupo"] = df["data_ref"].dt.strftime("%d/%m")
    elif periodo == "semana":
        df["grupo"] = df["data_ref"].dt.to_period("W").apply(
            lambda p: f"Sem {p.start_time.strftime('%d/%m')}")
    else:  # mes
        df["grupo"] = df["data_ref"].dt.strftime("%b/%Y")

    agg = (df.groupby("grupo", as_index=False)
             .agg(recebido=("recebido","sum"),
                  expedido=("expedido","sum"),
                  entregas=("entregas","sum")))
    agg["taxa_exp"] = agg["expedido"] / agg["recebido"].replace(0, np.nan).fillna(1)
    agg["taxa_ent"] = agg["entregas"] / agg["recebido"].replace(0, np.nan).fillna(1)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Recebido", x=agg["grupo"], y=agg["recebido"],
        marker_color=AZ, text=agg["recebido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white")))
    fig.add_trace(go.Bar(
        name="Expedido", x=agg["grupo"], y=agg["expedido"],
        marker_color=LR, text=agg["expedido"].apply(lambda v: f"{v:,}"),
        textposition="inside", textfont=dict(color="white")))
    fig.add_trace(go.Scatter(
        name="Taxa Exp. %", x=agg["grupo"], y=agg["taxa_exp"]*100,
        mode="lines+markers+text", yaxis="y2",
        line=dict(color=VD, width=3), marker=dict(size=10),
        text=[f"{t:.0%}" for t in agg["taxa_exp"]],
        textposition="top center", textfont=dict(color=VD, size=12)))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Quantidade"),
        yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 120]))
    labels = {"dia":"Diário","semana":"Semanal","mes":"Mensal"}
    return _layout(fig, h=400, title=f"Comparativo {labels.get(periodo,'')}")

# ══════════════════════════════════════════════════════════════
#  6. DONUT GERAL
# ══════════════════════════════════════════════════════════════
def chart_donut(total_rec, total_exp, taxa) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=["Recebido no DS", "Em Rota de Entrega"],
        values=[total_rec, total_exp],
        hole=0.62,
        marker=dict(colors=[AZ, LR], line=dict(color=BG, width=3)),
        textinfo="label+percent",
        textfont=dict(size=12, color=TX),
        hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>"))
    fig.update_layout(
        annotations=[dict(text=f"<b>{taxa:.1%}</b><br>Em Rota",
                          x=0.5, y=0.5, showarrow=False,
                          font=dict(size=16, color=TX))],
        legend=dict(bgcolor=BP))
    return _layout(fig, h=360, title="Distribuição Geral")
