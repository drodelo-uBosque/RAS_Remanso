import streamlit as st
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime, timedelta
import plotly.graph_objects as go
from sklearn.metrics import mean_absolute_error, mean_squared_error
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. SERVICIOS Y CONFIGURACIÓN
# =========================================================
@st.cache_resource
def iniciar_servicios():
    if not firebase_admin._apps:
        try:
            info = dict(st.secrets["firebase_key"])
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred, {'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/'})
        except: st.error("Error Firebase"); st.stop()
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['columnas']
    except: return None, None

st.set_page_config(page_title="Validación IA - UDCA", layout="wide")
mod_t, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

# --- LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔒 Validación Técnica RAS")
    u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
    st.stop()

# =========================================================
# 2. SIDEBAR: CONTROL Y MÉTRICAS EN VIVO
# =========================================================
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.header("📊 Validación de Rendimiento")

jornada_hrs = st.sidebar.select_slider("Horizonte (Hrs):", options=[4, 8, 12, 24], value=12)

# Historial de datos
if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "Real", "Pred"])

# --- CÁLCULO DE MÉTRICAS (Si hay datos suficientes) ---
if len(st.session_state.historial) > 5:
    y_true = st.session_state.historial["Real"].values
    y_pred = st.session_state.historial["Pred"].values
    
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    st.sidebar.metric("MAE (Error Medio)", f"{mae:.3f} °C")
    st.sidebar.metric("RMSE (Estabilidad)", f"{rmse:.3f} °C")
    
    # Interpretación para la tesis
    if mae < 0.5: st.sidebar.success("✅ Precisión Alta")
    elif mae < 1.0: st.sidebar.warning("⚠️ Precisión Moderada")
    else: st.sidebar.error("❌ Revisar Calibración")

# =========================================================
# 3. PROCESAMIENTO Y PREDICCIÓN
# =========================================================
try:
    ref = rtdb.reference('/sensor_data').get()
    t_now = float(ref.get('temp', 18.0)) if ref else 18.0
    p_now = float(ref.get('ph', 7.0)) if ref else 7.0
    
    # Predicción XGBoost
    if mod_t:
        entrada = pd.DataFrame([[t_now, p_now, float(jornada_hrs)]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        tf = t_now + float(mod_t.predict(entrada[cols_modelo])[0])
    else: tf = t_now

    # Guardar para métricas
    nuevo = {"Hora": datetime.now().strftime("%H:%M:%S"), "Real": t_now, "Pred": tf}
    st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(50)
except: pass

# =========================================================
# 4. VISUALIZACIÓN
# =========================================================
st.title("🔬 Laboratorio de Validación IA - RAS")
st.markdown(f"Evaluando el comportamiento térmico en **Bogotá** con horizonte de **{jornada_hrs} horas**.")

# Gráfica de Dispersión (Real vs Predicho) - CLAVE PARA TESIS
fig_eval = go.Figure()
fig_eval.add_trace(go.Scatter(x=st.session_state.historial["Real"], y=st.session_state.historial["Pred"],
                             mode='markers', name="Puntos de Datos", marker=dict(color='yellow', size=10)))
# Línea de 45 grados (Ideal)
limit_min = min(st.session_state.historial["Real"].min(), st.session_state.historial["Pred"].min())
limit_max = max(st.session_state.historial["Real"].max(), st.session_state.historial["Pred"].max())
fig_eval.add_trace(go.Scatter(x=[limit_min, limit_max], y=[limit_min, limit_max], 
                             mode='lines', name="Predicción Perfecta", line=dict(color='white', dash='dash')))

fig_eval.update_layout(template="plotly_dark", title="Gráfica de Ajuste (Real vs IA)",
                       xaxis_title="Temperatura Real (°C)", yaxis_title="Temperatura Predicha (°C)", height=500)
st.plotly_chart(fig_eval, use_container_width=True)

with st.expander("📚 ¿Cómo leer estas métricas en mi sustentación?"):
    st.write("""
    - **MAE:** Es qué tan lejos está la IA del termómetro en promedio. Para peces, un MAE menor a 0.8°C es ideal.
    - **RMSE:** Si este valor es mucho más alto que el MAE, significa que tu modelo tiene 'outliers' o errores grandes puntuales.
    - **Gráfica de Ajuste:** Entre más cerca estén los puntos amarillos de la línea blanca diagonal, más 'perfecto' es tu modelo XGBoost.
    """)
