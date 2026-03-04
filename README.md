# 🚚 Dashboard de Expedição Logística

Dashboard interativo com histórico, login por região e gráficos comparativos.

---

## 📁 Estrutura de arquivos

```
dashboard_expedicao/
├── app.py              ← App principal (Streamlit)
├── processing.py       ← Lógica de processamento
├── charts.py           ← Gráficos Plotly
├── database.py         ← Integração Supabase
├── style.css           ← Visual dark
├── config.yaml         ← Usuários e senhas (não subir no Git)
├── gerar_senha.py      ← Helper para gerar hashes de senha
├── requirements.txt    ← Dependências
├── .gitignore
└── .streamlit/
    └── secrets.toml    ← Credenciais Supabase (não subir no Git)
```

---

## 🚀 Deploy passo a passo

### 1. Criar banco no Supabase (gratuito)

1. Acesse https://supabase.com → **New Project**
2. No menu esquerdo → **SQL Editor** → cole e execute:

```sql
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
    id               BIGSERIAL PRIMARY KEY,
    data_ref         DATE  NOT NULL,
    scan_station     TEXT  NOT NULL,
    destination_city TEXT  NOT NULL,
    recebido         INTEGER DEFAULT 0,
    expedido         INTEGER DEFAULT 0,
    entregas         INTEGER DEFAULT 0,
    taxa_exp         FLOAT   DEFAULT 0,
    taxa_ent         FLOAT   DEFAULT 0,
    UNIQUE (data_ref, scan_station, destination_city)
);
```

3. Vá em **Settings → API** e copie:
   - **Project URL** → `https://XXXXX.supabase.co`
   - **anon public** key

4. Cole em `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://XXXXX.supabase.co"
SUPABASE_KEY = "eyJhbGci..."
```

---

### 2. Configurar usuários e senhas

1. Rode o gerador de senhas:
```bash
pip install bcrypt
python gerar_senha.py
```

2. Copie os hashes gerados para `config.yaml`

3. Edite `app.py` se quiser mudar quais regiões cada usuário vê:
```python
REGIOES_USUARIO = {
    "admin":       None,                # vê tudo
    "sup_capital": ["capital"],
    ...
}
```

---

### 3. Publicar no Streamlit Cloud (gratuito)

1. Suba a pasta para um repositório GitHub (**privado** recomendado)
   - Confirme que `.gitignore` está excluindo `secrets.toml` e `config.yaml`

2. Acesse https://share.streamlit.io → **New app**
   - Repository: seu repositório
   - Branch: `main`
   - Main file path: `app.py`

3. Em **Advanced settings → Secrets**, cole o conteúdo do `secrets.toml`

4. Clique **Deploy** — em ~2 minutos o link estará disponível

---

### 4. Testar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 👥 Usuários padrão

| Usuário       | Vê                              |
|---------------|----------------------------------|
| `admin`       | Tudo                             |
| `sup_capital` | Somente Capital                  |
| `sup_metro`   | Somente Metropolitan             |
| `sup_country` | Somente Countryside              |
| `sup_geral`   | Capital + Metropolitan + Countryside |

---

## 📊 Funcionalidades

- ✅ Login com separação por região
- ✅ Upload de arquivos e processamento por data
- ✅ Histórico salvo no Supabase
- ✅ Gráficos interativos (Plotly):
  - Volume por DS
  - Taxa de expedição por DS (horizontal)
  - Mapa de calor DS × Cidade
  - Evolução diária
  - Comparativo diário / semanal / mensal
- ✅ Comparativo ontem vs hoje nos KPIs
- ✅ Tabelas detalhadas por DS e cidade
