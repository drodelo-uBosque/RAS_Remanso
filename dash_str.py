import streamlit as st
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. CONFIGURACIÓN DE NIVELES Y UMBRALES
# =========================================================
# Rangos Temperatura (Tus valores exactos)
T_OPT_MIN, T_OPT_MAX = 16.0, 20.0  
T_SUB_MIN, T_SUB_MAX = 11.0, 27.0  

# Rangos pH (Estándar sugerido)
PH_OPT_MIN, PH_OPT_MAX = 6.5, 8.5
PH_SUB_MIN, PH_SUB_MAX = 5.5, 9.5

TDS_MAX = 900
VALOR_DEFECTO_T = 18.0

# =========================================================
# 2. FUNCIONES DE APOYO (DEFINICIONES)
# =========================================================
@st.cache_resource
def iniciar_servicios():
    if not firebase_admin._apps:
        cred = credentials.Certificate("llave_firebase.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/'
        })
    p = joblib.load('sistema_ras_completo.pkl')
    return p['modelo_temp'], p['modelo_ph'], p['columnas']

def graficar_proyeccion(df, real_col, pred_col, min_opt, max_opt, min_sub, max_sub, titulo, color_linea):
    fig = go.Figure()
    # Zonas de fondo
    fig.add_hrect(y0=min_opt, y1=max_opt, fillcolor="green", opacity=0.15, line_width=0)
    fig.add_hrect(y0=min_sub, y1=min_opt, fillcolor="yellow", opacity=0.08, line_width=0)
    fig.add_hrect(y0=max_opt, y1=max_sub, fillcolor="yellow", opacity=0.08, line_width=0)
    # Líneas de datos
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[real_col], name="Real", line=dict(color=color_linea, width=4)))
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[pred_col], name="IA (XGBoost)", line=dict(color='white', dash='dot', width=2)))
    fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10, r=10, t=50, b=10))
    return fig

# =========================================================
# 3. INICIO DE SERVICIOS Y LOGIN
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()

st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide", page_icon="🐟")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Control de Acceso - Proyecto de Grado")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 4. SIDEBAR - CONTROL Y ESTADO
# =========================================================
st.sidebar.image("logo_1.png", width=300)
st.sidebar.title("⚙️ Panel de Control")

refresco_seg = st.sidebar.slider("Refresco (seg)", 2, 30, 5)
st_autorefresh(interval=refresco_seg * 1000, key="datarefresh")

sensibilidad = st.sidebar.slider("Sensibilidad IA", 0.1, 2.0, 1.0)

if 'hist' not in st.session_state:
    st.session_state.hist = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS_R"])

# --- OBTENCIÓN DE DATOS ---
ahora = datetime.now()
try:
    data = rtdb.reference('/sensor_data').get()
    if data:
        t_now = float(data.get('temp', VALOR_DEFECTO_T))
        p_now = float(data.get('ph', 7.0))
        tds_now = float(data.get('tds', 0.0))
        st.sidebar.success(f"📡 Conectado: {ahora.strftime('%H:%M:%S')}")
    else:
        t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0
except:
    t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0

# --- PREDICCIÓN IA ---
df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
for c in cols_modelo:
    if c not in df_in.columns: df_in[c] = 0
df_in = df_in[cols_modelo]

tf = t_now + (float(mod_t.predict(df_in)[0]) * sensibilidad)
pf = p_now + (float(mod_p.predict(df_in)[0]) * sensibilidad)

# --- HISTORIAL ---
nuevo = pd.DataFrame({"Hora": [ahora.strftime("%H:%M:%S")], "T_R": [t_now], "T_P": [tf], "P_R": [p_now], "P_P": [pf], "TDS_R": [tds_now]})
st.session_state.hist = pd.concat([st.session_state.hist, nuevo]).tail(30)

# =========================================================
# 5. RENDERIZADO DEL DASHBOARD
# =========================================================
st.title("🌊 Monitoreo Inteligente RAS - UDCA")

# Métricas
m1, m2, m3 = st.columns(3)
m1.metric("🌡️ TEMPERATURA", f"{t_now:.1f} °C", delta=f"{tf-t_now:.2f} (IA)")
m2.metric("🧪 pH AGUA", f"{p_now:.2f}", delta=f"{pf-p_now:.2f} (IA)")
m3.metric("💧 TDS", f"{tds_now:.0f} ppm")

# Semáforo de Estado Térmico
color_sem = "#28a745" if T_OPT_MIN <= t_now <= T_OPT_MAX else "#ffc107" if T_SUB_MIN <= t_now <= T_SUB_MAX else "#dc3545"
st.sidebar.markdown(f"""
    <div style="text-align: center; background: #121212; padding: 15px; border-radius: 15px; border: 2px solid {color_sem};">
        <p style="color: white; font-size: 13px;">ESTADO TÉRMICO</p>
        <div style="width: 55px; height: 55px; background: {color_sem}; border-radius: 50%; margin: 0 auto; box-shadow: 0 0 15px {color_sem};"></div>
    </div>
""", unsafe_allow_html=True)

# Descarga
st.sidebar.markdown("---")
csv = st.session_state.hist.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Descargar Datos", csv, f"ras_{ahora.strftime('%Y%m%d')}.csv", "text/csv", key="dl_btn")

# --- GRÁFICAS ---
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "T_R", "T_P", T_OPT_MIN, T_OPT_MAX, T_SUB_MIN, T_SUB_MAX, "Proyección Térmica (°C)", "#00d4ff"), use_container_width=True)
with c2:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "P_R", "P_P", PH_OPT_MIN, PH_OPT_MAX, PH_SUB_MIN, PH_SUB_MAX, "Proyección de pH", "#ff00ff"), use_container_width=True)

# Gráfica de TDS (Fondo)
fig_tds = go.Figure(go.Scatter(x=st.session_state.hist["Hora"], y=st.session_state.hist["TDS_R"], fill='tozeroy', line=dict(color='#00ff88'), name="TDS"))
fig_tds.update_layout(template="plotly_dark", title="Sólidos Totales Disueltos (ppm)", height=280)
st.plotly_chart(fig_tds, use_container_width=True)