import streamlit as st
import pandas as pd
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime, timedelta
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. PARÁMETROS Y SERVICIOS
# =========================================================
TEMP_MIN, TEMP_MAX = 14.0, 22.0
PH_MIN, PH_MAX = 6.5, 8.5
TDS_LIMITE = 800

@st.cache_resource
def iniciar_servicios():
    if not firebase_admin._apps:
        try:
            info = dict(st.secrets["firebase_key"])
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred, {'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/'})
        except Exception as e:
            st.error(f"Error Firebase: {e}"); st.stop()
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except:
        st.error("Error al cargar modelos IA"); st.stop()

st.set_page_config(page_title="RAS UDCA - Planeación IA", layout="wide")

# --- LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 Acceso Restringido - Tesis UDCA")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
        else: st.error("Error")
    st.stop()

# =========================================================
# 2. CONFIGURACIÓN DE JORNADA (HORIZONTE LEJANO)
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.title("📅 Planeación por Jornadas")

# Selector de Jornada (Predictor a largo plazo)
jornada_hrs = st.sidebar.select_slider(
    "Seleccionar Horizonte (Horas):",
    options=[4, 8, 12, 24],
    value=12
)

offset_manual = st.sidebar.slider("Calibración IA (Offset)", -3.0, 3.0, 0.0, 0.1)

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora_Real", "T_Real", "Hora_Futuro", "T_Pred", "Incertidumbre"])

# =========================================================
# 3. LÓGICA DE PROYECCIÓN TEMPORAL
# =========================================================
ahora = datetime.now()
try:
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
        
        # Entrada IA: Usamos 'jornada_hrs' como variable de tiempo
        entrada = pd.DataFrame([[t_now, p_now, float(jornada_hrs)]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        
        # Predicción Desplazada
        # Calculamos la hora exacta en que ocurrirá esta predicción
        hora_futuro = (ahora + timedelta(hours=jornada_hrs)).strftime("%H:%M:%S")
        
        # El modelo predice el cambio; sumamos offset y aplicamos una banda de error (ej. 5% por cada 4 horas)
        pred_base = float(mod_t.predict(entrada[cols_modelo])[0])
        tf = t_now + pred_base + offset_manual
        error_banda = (jornada_hrs / 24.0) * 1.5 # Entre más lejos, más duda (hasta 1.5°C)
        
        nuevo = {
            "Hora_Real": ahora.strftime("%H:%M:%S"),
            "T_Real": t_now,
            "Hora_Futuro": hora_futuro,
            "T_Pred": tf,
            "Incertidumbre": error_banda
        }
        st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(30)
    else: t_now, tf, hora_futuro, error_banda
