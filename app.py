"""
app.py — Dashboard de Expedição Logística
Streamlit Cloud + Supabase + Login por região
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

from processing import (
    normalizar_colunas, construir_mapa_sigla, padronizar_scan_station,
    filtrar_dados, fazer_merge, criar_pivot, criar_pivot_cidades,
    calcular_metricas, separar_por_regiao,
    detectar_coluna_data, ler_datas_recebimento, _ler_uploads, _wb_to_str
)
from database import (
    salvar_processamento, ler_dia, ler_periodo,
    ler_cidades_dia, ler_datas_disponiveis
)
from charts import (
    chart_volume_ds, chart_taxa_ds, chart_evolucao_diaria,
    chart_heatmap_cidades, chart_comparativo, chart_donut
)

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Expedição Logística",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────
import os
_css = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
if os.path.exists(_css):
    with open(_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  MAPA DE REGIÕES POR USUÁRIO
#  Edite aqui para adicionar/remover usuários
# ══════════════════════════════════════════════════════════════
REGIOES_USUARIO = {
    "admin":        None,                              # vê tudo
    "sup_capital":  ["capital"],
    "sup_metro":    ["metropolitan"],
    "sup_country":  ["countryside"],
    "sup_geral":    ["capital","metropolitan","countryside"],
}

# ══════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def _carregar_auth():
    with open("config.yaml") as f:
        cfg = yaml.load(f, Loader=SafeLoader)
    auth = stauth.Authenticate(
        cfg["credentials"],
        cfg["cookie"]["name"],
        cfg["cookie"]["key"],
        cfg["cookie"]["expiry_days"],
    )
    return auth, cfg

auth, cfg = _carregar_auth()
nome, autenticado, usuario = auth.login(location="main")

if not autenticado:
    if autenticado is False:
        st.error("Usuário ou senha incorretos.")
    st.stop()

# ── Regiões permitidas para este usuário ─────────────────────
regioes_user = REGIOES_USUARIO.get(usuario)   # None = admin = tudo
is_admin     = regioes_user is None

# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style='padding:16px 0 8px'>
      <div style='font-size:22px'>🚚</div>
      <div style='font-size:15px;font-weight:700;color:#fff'>Expedição Logística</div>
      <div style='font-size:12px;color:#4a6a90;margin-top:4px'>Olá, <b>{nome}</b></div>
      {'<div style="font-size:10px;background:#1a3060;color:#4f8ef7;padding:2px 8px;border-radius:20px;display:inline-block;margin-top:4px">ADMIN</div>' if is_admin else ''}
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    pagina = st.radio(
        "Navegação",
        ["📊 Dashboard", "📤 Upload / Processar", "📅 Histórico", "📈 Comparativos"],
        label_visibility="collapsed"
    )
    st.divider()
    auth.logout("Sair", location="sidebar")

# ══════════════════════════════════════════════════════════════
#  PÁGINA: DASHBOARD
# ══════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":
    st.markdown("""
    <div class="app-header">
      <div class="app-header-icon">📊</div>
      <div><h1>Dashboard</h1>
      <p>Visão consolidada por dia</p></div>
    </div>""", unsafe_allow_html=True)

    # Seletor de data
    datas = ler_datas_disponiveis(regioes_user)
    if not datas:
        st.info("Nenhum dado no histórico ainda. Vá para **Upload / Processar** para gerar o primeiro.")
        st.stop()

    col_dt, col_reg, _ = st.columns([2, 2, 4])
    with col_dt:
        data_sel = st.selectbox(
            "Data",
            options=datas,
            format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
            index=0
        )
    with col_reg:
        if is_admin:
            reg_filtro = st.multiselect(
                "Região", ["capital","metropolitan","countryside"],
                default=["capital","metropolitan","countryside"])
        else:
            reg_filtro = regioes_user
            st.markdown(f"**Região:** {', '.join(regioes_user)}")

    # Carrega dados
    df_dia    = ler_dia(data_sel, reg_filtro if not is_admin else None)
    df_cid    = ler_cidades_dia(data_sel, reg_filtro if not is_admin else None)

    if len(df_dia) == 0:
        st.warning(f"Sem dados para {pd.to_datetime(data_sel).strftime('%d/%m/%Y')}.")
        st.stop()

    # ── KPIs ──────────────────────────────────────────────────
    rec  = int(df_dia["recebido"].sum())
    exp  = int(df_dia["expedido"].sum())
    ent  = int(df_dia["entregas"].sum())
    tx   = exp / rec if rec else 0
    txe  = ent / rec if rec else 0
    nds  = len(df_dia)
    nok  = int(df_dia["atingiu_meta"].sum())

    st.markdown(f"""
    <div class="kpi-grid">
      <div class="kpi-card c1">
        <div class="kpi-lbl">Recebido</div>
        <div class="kpi-val">{rec:,}</div>
        <div class="kpi-sub">waybills no dia</div>
      </div>
      <div class="kpi-card c2">
        <div class="kpi-lbl">Em Rota</div>
        <div class="kpi-val">{exp:,}</div>
        <div class="kpi-sub">taxa {tx:.1%}</div>
      </div>
      <div class="kpi-card c3">
        <div class="kpi-lbl">Entregas</div>
        <div class="kpi-val">{ent:,}</div>
        <div class="kpi-sub">{'taxa ' + f'{txe:.1%}' if ent else 'sem dados'}</div>
      </div>
      <div class="kpi-card c4">
        <div class="kpi-lbl">DS na Meta</div>
        <div class="kpi-val">{nok}</div>
        <div class="kpi-sub">de {nds} bases</div>
      </div>
      <div class="kpi-card c5">
        <div class="kpi-lbl">DS Abaixo</div>
        <div class="kpi-val">{nds - nok}</div>
        <div class="kpi-sub">precisam atenção</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Comparativo ontem ─────────────────────────────────────
    ontem = pd.to_datetime(data_sel).date() - timedelta(days=1)
    df_ont = ler_dia(str(ontem), reg_filtro if not is_admin else None)
    if len(df_ont):
        rec_ont = int(df_ont["recebido"].sum())
        exp_ont = int(df_ont["expedido"].sum())
        tx_ont  = exp_ont / rec_ont if rec_ont else 0
        d_rec   = rec - rec_ont
        d_exp   = exp - exp_ont
        d_tx    = tx  - tx_ont
        def _delta(v, fmt=","):
            sinal = "+" if v >= 0 else ""
            cor   = "#22c55e" if v >= 0 else "#ef4444"
            txt   = f"{sinal}{v:{fmt}}" if fmt == "," else f"{sinal}{v:.1%}"
            return f"<span style='color:{cor};font-size:12px'>{txt} vs ontem</span>"
        st.markdown(f"""
        <div style='display:flex;gap:32px;margin:-8px 0 20px;flex-wrap:wrap'>
          <div>{_delta(d_rec)} Recebido</div>
          <div>{_delta(d_exp)} Expedido</div>
          <div>{_delta(d_tx, fmt='%')} Taxa</div>
        </div>""", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────
    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        st.plotly_chart(chart_volume_ds(df_dia), use_container_width=True)
    with col_b:
        st.plotly_chart(chart_donut(rec, exp, tx), use_container_width=True)

    st.plotly_chart(chart_taxa_ds(df_dia), use_container_width=True)

    if len(df_cid):
        col_c, col_d = st.columns(2)
        with col_c:
            st.plotly_chart(chart_heatmap_cidades(df_cid, "taxa_exp"), use_container_width=True)
        with col_d:
            st.plotly_chart(chart_heatmap_cidades(df_cid, "taxa_ent"), use_container_width=True)

    # ── Tabela detalhada ──────────────────────────────────────
    st.markdown('<div class="section-label">Detalhe por DS</div>', unsafe_allow_html=True)
    df_show = df_dia[["scan_station","region","recebido","expedido","entregas",
                       "taxa_exp","taxa_ent","meta","atingiu_meta"]].copy()
    df_show.columns = ["DS","Região","Recebido","Expedido","Entregas",
                       "Taxa Exp.","Taxa Ent.","Meta","Na Meta"]
    df_show["Taxa Exp."] = df_show["Taxa Exp."].map("{:.1%}".format)
    df_show["Taxa Ent."] = df_show["Taxa Ent."].map("{:.1%}".format)
    df_show["Meta"]      = df_show["Meta"].map("{:.0%}".format)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════
#  PÁGINA: UPLOAD / PROCESSAR
# ══════════════════════════════════════════════════════════════
elif pagina == "📤 Upload / Processar":
    st.markdown("""
    <div class="app-header">
      <div class="app-header-icon">📤</div>
      <div><h1>Upload e Processamento</h1>
      <p>Carregue os arquivos do dia · Processe · Salva automaticamente no histórico</p></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Arquivos de entrada</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<div class="upload-label">Supervisores <span class="badge-r">OBRIGATÓRIO</span></div>'
                    '<div class="upload-hint">arquivo único — colunas: SIGLA, REGION</div>',
                    unsafe_allow_html=True)
        f_sup = st.file_uploader("sup", type=["xlsx","xls"], key="sup", label_visibility="collapsed")
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        st.markdown('<div class="upload-label">Recebimento <span class="badge-r">OBRIGATÓRIO</span></div>'
                    '<div class="upload-hint">todos os arquivos da pasta — precisa ter coluna de data</div>',
                    unsafe_allow_html=True)
        f_rec = st.file_uploader("rec", type=["xlsx","xls"], key="rec",
                                  accept_multiple_files=True, label_visibility="collapsed")
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        st.markdown('<div class="upload-label">Out of Delivery <span class="badge-r">OBRIGATÓRIO</span></div>'
                    '<div class="upload-hint">todos os arquivos da pasta</div>',
                    unsafe_allow_html=True)
        f_out = st.file_uploader("out", type=["xlsx","xls"], key="out",
                                  accept_multiple_files=True, label_visibility="collapsed")

    with col2:
        st.markdown('<div class="upload-label">Entregas <span class="badge-o">OPCIONAL</span></div>'
                    '<div class="upload-hint">todos os arquivos da pasta</div>',
                    unsafe_allow_html=True)
        f_ent = st.file_uploader("ent", type=["xlsx","xls"], key="ent",
                                  accept_multiple_files=True, label_visibility="collapsed")
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        st.markdown('<div class="upload-label">Metas por Base <span class="badge-o">OPCIONAL</span></div>'
                    '<div class="upload-hint">arquivo único — colunas: DS, Meta</div>',
                    unsafe_allow_html=True)
        f_meta = st.file_uploader("meta", type=["xlsx","xls"], key="meta", label_visibility="collapsed")

    # ── Detecção de data ──────────────────────────────────────
    data_selecionada = None
    col_data_nome    = None

    if f_rec:
        st.markdown('<div class="section-label">Selecione a data</div>', unsafe_allow_html=True)
        with st.spinner("Detectando datas..."):
            col_data_nome = detectar_coluna_data(f_rec[0])
            datas_disp    = ler_datas_recebimento(f_rec, col_data_nome) if col_data_nome else []

        if col_data_nome and datas_disp:
            st.success(f"Coluna de data: **{col_data_nome}** — {len(datas_disp)} dia(s) disponível(is)")
            data_selecionada = st.selectbox(
                "Dia para processar:",
                options=datas_disp,
                format_func=lambda d: d.strftime("%d/%m/%Y (%A)"),
                index=len(datas_disp)-1
            )
        else:
            st.warning("Coluna de data não encontrada. Todos os registros serão usados.")

    # ── Botão processar ───────────────────────────────────────
    st.markdown('<div class="section-label">Processar</div>', unsafe_allow_html=True)
    pronto    = bool(f_sup and f_rec and f_out)
    data_lbl  = data_selecionada.strftime("%d/%m/%Y") if data_selecionada else "todos os dias"
    if not pronto:
        st.info("Faça o upload dos 3 arquivos obrigatórios.")

    if st.button(f"▶  PROCESSAR E SALVAR — {data_lbl}", disabled=not pronto, use_container_width=True):
        prog = st.progress(0, text="Iniciando...")
        try:
            prog.progress(8,  "Carregando arquivos...")
            cols_sup = {"SIGLA":"SIGLA","REGION":"REGION"}
            cols_rec = {"Scan Station":"Scan Station","Waybill Number":"Waybill Number",
                        "Destination City":"Destination City"}
            if col_data_nome:
                cols_rec[col_data_nome] = col_data_nome
            cols_out = {"Waybill No.":"Waybill No.","Scan time":"Scan time"}

            df_sup = normalizar_colunas(pd.read_excel(f_sup), cols_sup)
            df_rec = _ler_uploads(f_rec, cols_rec)
            df_out = _ler_uploads(f_out, cols_out)

            # Filtro por data
            prog.progress(18, "Filtrando por data...")
            if data_selecionada and col_data_nome and col_data_nome in df_rec.columns:
                df_rec[col_data_nome] = pd.to_datetime(df_rec[col_data_nome], errors="coerce")
                df_rec = df_rec[df_rec[col_data_nome].dt.date == data_selecionada].copy()
                if len(df_rec) == 0:
                    st.error("Nenhum registro para a data selecionada.")
                    st.stop()

            if "Scan Station" not in df_out.columns:
                wb_to_ss = (df_rec[["Waybill Number","Scan Station"]]
                            .dropna(subset=["Waybill Number","Scan Station"])
                            .drop_duplicates("Waybill Number")
                            .rename(columns={"Waybill Number":"Waybill No."}))
                df_out = df_out.merge(wb_to_ss, on="Waybill No.", how="left")

            df_ent  = _ler_uploads(f_ent,  {"Scan Station":"Scan Station","Waybill No.":"Waybill No."}) if f_ent  else None
            df_meta = None
            if f_meta:
                df_meta = normalizar_colunas(pd.read_excel(f_meta), {"DS":"DS","Meta":"Meta"})
                df_meta["DS"]   = df_meta["DS"].astype(str).str.strip()
                df_meta["Meta"] = (pd.to_numeric(
                    df_meta["Meta"].astype(str).str.replace("%","",regex=False)
                        .str.replace(",",".",regex=False).str.strip(),
                    errors="coerce") / 100).fillna(0.5)

            prog.progress(32, "Padronizando Scan Stations...")
            mapa    = construir_mapa_sigla(df_sup)
            df_rec  = filtrar_dados(df_sup, df_rec, mapa)
            df_out  = padronizar_scan_station(df_out, mapa)
            if df_ent is not None:
                df_ent = padronizar_scan_station(df_ent, mapa)

            prog.progress(48, "Calculando volumes por Waybill...")
            df_merge      = fazer_merge(df_sup, df_rec)
            pivot         = criar_pivot(df_merge, df_out, df_ent)
            pivot_cidades = criar_pivot_cidades(df_merge, df_out, df_ent)

            prog.progress(65, "Calculando métricas...")
            pivot_m = calcular_metricas(pivot, df_meta)

            prog.progress(80, "Salvando no histórico (Supabase)...")
            salvar_processamento(
                pivot_metricas=pivot_m,
                pivot_cidades=pivot_cidades,
                data_ref=data_selecionada or date.today(),
                usuario=usuario
            )

            prog.progress(100, "Concluído!")

            # ── Resumo ────────────────────────────────────────
            rec_t = int(pivot_m["recebido no DS"].sum())
            exp_t = int(pivot_m["em rota de entrega"].sum())
            ent_t = int(pivot_m["Entregas"].sum())
            tx_t  = exp_t / rec_t if rec_t else 0
            n_ds  = len(pivot_m)
            n_ok  = int(pivot_m["Atingiu Meta"].sum())

            st.success(f"✅ Processamento salvo para **{data_lbl}**")
            st.markdown(f"""
            <div class="kpi-grid">
              <div class="kpi-card c1"><div class="kpi-lbl">Recebido</div>
                <div class="kpi-val">{rec_t:,}</div></div>
              <div class="kpi-card c2"><div class="kpi-lbl">Expedido</div>
                <div class="kpi-val">{exp_t:,}</div>
                <div class="kpi-sub">taxa {tx_t:.1%}</div></div>
              <div class="kpi-card c3"><div class="kpi-lbl">Entregas</div>
                <div class="kpi-val">{ent_t:,}</div></div>
              <div class="kpi-card c4"><div class="kpi-lbl">DS na Meta</div>
                <div class="kpi-val">{n_ok}/{n_ds}</div></div>
              <div class="kpi-card c5"><div class="kpi-lbl">DS Abaixo</div>
                <div class="kpi-val">{n_ds-n_ok}</div></div>
            </div>""", unsafe_allow_html=True)
            st.info("Vá para **📊 Dashboard** para ver os gráficos completos.")

        except Exception as e:
            import traceback
            prog.progress(0, "Erro")
            st.error(f"Erro: {e}")
            with st.expander("Detalhes"):
                st.code(traceback.format_exc())

# ══════════════════════════════════════════════════════════════
#  PÁGINA: HISTÓRICO
# ══════════════════════════════════════════════════════════════
elif pagina == "📅 Histórico":
    st.markdown("""
    <div class="app-header">
      <div class="app-header-icon">📅</div>
      <div><h1>Histórico</h1>
      <p>Todos os dias processados</p></div>
    </div>""", unsafe_allow_html=True)

    col_i, col_f, _ = st.columns([2, 2, 4])
    with col_i:
        d_ini = st.date_input("De", value=date.today() - timedelta(days=30))
    with col_f:
        d_fim = st.date_input("Até", value=date.today())

    df_hist = ler_periodo(d_ini, d_fim, regioes_user if not is_admin else None)

    if len(df_hist) == 0:
        st.info("Nenhum dado no período selecionado.")
        st.stop()

    # ── Resumo do período ─────────────────────────────────────
    agg = (df_hist.groupby("data_ref", as_index=False)
                  .agg(recebido=("recebido","sum"),
                       expedido=("expedido","sum"),
                       entregas=("entregas","sum")))
    agg["taxa_exp"] = agg["expedido"] / agg["recebido"].replace(0, np.nan)

    rec_per = int(agg["recebido"].sum())
    exp_per = int(agg["expedido"].sum())
    tx_per  = exp_per / rec_per if rec_per else 0
    dias    = len(agg)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Recebido",  f"{rec_per:,}")
    c2.metric("Total Expedido",  f"{exp_per:,}")
    c3.metric("Taxa Média",      f"{tx_per:.1%}")
    c4.metric("Dias no período", dias)

    st.plotly_chart(chart_evolucao_diaria(df_hist), use_container_width=True)

    # ── Tabela por dia ────────────────────────────────────────
    st.markdown('<div class="section-label">Resumo por dia</div>', unsafe_allow_html=True)
    agg["Taxa"]     = agg["taxa_exp"].map("{:.1%}".format)
    agg["data_ref"] = pd.to_datetime(agg["data_ref"]).dt.strftime("%d/%m/%Y")
    agg.columns     = ["Data","Recebido","Expedido","Entregas","taxa_exp","Taxa Exp."]
    st.dataframe(agg[["Data","Recebido","Expedido","Entregas","Taxa Exp."]],
                 use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════
#  PÁGINA: COMPARATIVOS
# ══════════════════════════════════════════════════════════════
elif pagina == "📈 Comparativos":
    st.markdown("""
    <div class="app-header">
      <div class="app-header-icon">📈</div>
      <div><h1>Comparativos</h1>
      <p>Evolução por dia, semana e mês</p></div>
    </div>""", unsafe_allow_html=True)

    col_i, col_f, _ = st.columns([2, 2, 4])
    with col_i:
        d_ini = st.date_input("De", value=date.today() - timedelta(days=90), key="ci")
    with col_f:
        d_fim = st.date_input("Até", value=date.today(), key="cf")

    df_hist = ler_periodo(d_ini, d_fim, regioes_user if not is_admin else None)
    if len(df_hist) == 0:
        st.info("Nenhum dado no período.")
        st.stop()

    # Filtro de DS (opcional)
    ds_lista = sorted(df_hist["scan_station"].unique().tolist())
    ds_sel   = st.multiselect("Filtrar por DS (deixe vazio = todos)", ds_lista)
    if ds_sel:
        df_hist = df_hist[df_hist["scan_station"].isin(ds_sel)]

    # Tabs por período
    tab_d, tab_s, tab_m = st.tabs(["📅 Diário", "📆 Semanal", "🗓️ Mensal"])
    with tab_d:
        st.plotly_chart(chart_comparativo(df_hist, "dia"),    use_container_width=True)
    with tab_s:
        st.plotly_chart(chart_comparativo(df_hist, "semana"), use_container_width=True)
    with tab_m:
        st.plotly_chart(chart_comparativo(df_hist, "mes"),    use_container_width=True)

    st.divider()

    # Taxa por DS ao longo do tempo
    st.markdown('<div class="section-label">Evolução por DS</div>', unsafe_allow_html=True)
    ds_top = (df_hist.groupby("scan_station")["recebido"].sum()
              .nlargest(10).index.tolist())
    df_top = df_hist[df_hist["scan_station"].isin(ds_top)].copy()
    df_top["data_ref"] = pd.to_datetime(df_top["data_ref"])

    import plotly.express as px
    fig = px.line(
        df_top.sort_values("data_ref"),
        x="data_ref", y="taxa_exp", color="scan_station",
        labels={"data_ref":"Data","taxa_exp":"Taxa Exp.","scan_station":"DS"},
        color_discrete_sequence=px.colors.qualitative.Bold)
    fig.update_layout(
        paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
        font=dict(color="#e2e8f0"), height=420,
        yaxis=dict(tickformat=".0%", gridcolor="#334155"),
        xaxis=dict(gridcolor="#334155"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"))
    fig.add_hline(y=0.5, line_dash="dash", line_color="#64748b",
                  annotation_text="Meta 50%")
    st.plotly_chart(fig, use_container_width=True)
