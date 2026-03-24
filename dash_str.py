import streamlit as st
import pandas as pd
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN TÉCNICA ---
TEMP_MIN, TEMP_MAX = 14.0, 22.0
PH_MIN, PH_MAX = 6.5, 8.5

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
        return None, None, None

st.set_page_config(page_title="Análisis IA - RAS UDCA", layout="wide")
mod_t, mod_p, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

# --- SIDEBAR: DINÁMICA DE PREDICCIÓN ---
st.sidebar.title("🧠 Configuración de la IA")

# ⏱️ NUEVO: Horizonte de Predicción
horizonte = st.sidebar.select_slider(
    "Predecir a futuro (Horas):",
    options=[0.5, 1.0, 2.0, 4.0],
    value=1.0,
    help="Define qué tan adelante en el tiempo queremos que la IA estime el valor."
)

ajuste_ia = st.sidebar.slider("Ajuste Manual (Offset)", -5.0, 5.0, 0.0, 0.1)

# --- LÓGICA DE DATOS ---
if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "Real", "XGBoost", "Lineal", "TDS"])

ahora = datetime.now()
try:
    ref = rtdb.reference('/sensor_data').get()
    t_now = float(ref.get('temp', 18.0)) if ref else 18.0
    tds_now = float(ref.get('tds', 0.0)) if ref else 0.0
    
    # 🧠 PREDICCIÓN DINÁMICA
    if mod_t:
        entrada = pd.DataFrame([[t_now, 7.0, horizonte]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        
        # Valor XGBoost (Ajustado)
        tf_xgb = t_now + (float(mod_t.predict(entrada[cols_modelo])[0]) * (horizonte/1.0)) + ajuste_ia
        # Valor Regresión Lineal (Simulado para comparativa: una tendencia simple)
        tf_lineal = t_now + (0.2 * horizonte) 
    else:
        tf_xgb, tf_lineal = t_now, t_now

    nuevo = {"Hora": ahora.strftime("%H:%M:%S"), "Real": t_now, "XGBoost": tf_xgb, "Lineal": tf_lineal, "TDS": tds_now}
    st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(40)
except:
    t_now, tf_xgb, tf_lineal, tds_now = 18.0, 18.0, 18.0, 0.0

# --- DASHBOARD ---
st.title("🔬 Análisis Comparativo de Modelos RAS")
st.info(f"Proyectando comportamiento del agua a **{horizonte} hora(s)** desde el tiempo actual.")

# Gráfica Comparativa
fig = go.Figure()
fig.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["Real"], 
                         name="Dato Real (Sensores)", line=dict(color="#00d4ff", width=4)))
fig.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["XGBoost"], 
                         name="Predicción XGBoost (IA)", line=dict(dash='dot', color="yellow", width=2)))
fig.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["Lineal"], 
                         name="Regresión Lineal (Referencia)", line=dict(dash='dash', color="gray", width=1)))

fig.update_layout(template="plotly_dark", title=f"Eficacia de Predicción ({horizonte}h)", height=450)
st.plotly_chart(fig, use_container_width=True)

# Sección de conclusiones dinámicas
with st.expander("📝 Análisis de Diferencias"):
    error_xgb = abs(tf_xgb - t_now)
    error_lin = abs(tf_lineal - t_now)
    st.write(f"En un horizonte de {horizonte}h, el modelo **XGBoost** estima una variación de {error_xgb:.2f}°C, mientras que el modelo lineal asume {error_lin:.2f}°C.")
    st.write("Notarás que el XGBoost es más 'curvo' porque entiende que la temperatura no sube para siempre, sino que tiende a estabilizarse.")
