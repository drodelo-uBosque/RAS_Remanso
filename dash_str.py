import streamlit as st
import pandas as pd
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime, timedelta
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. SERVICIOS Y CONFIGURACIÓN
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
        st.warning("Usando modo de simulación (No se encontró .pkl)"); return None, None, None

st.set_page_config(page_title="RAS UDCA - Planeación IA", layout="wide", page_icon="🐟")

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
        else: st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 2. CONFIGURACIÓN DE JORNADA
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.title("📅 Planeación por Jornadas")

jornada_hrs = st.sidebar.select_slider("Seleccionar Horizonte (Horas):", options=[4, 8, 12, 24], value=12)
offset_manual = st.sidebar.slider("Calibración IA (Offset)", -3.0, 3.0, 0.0, 0.1)

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora_Real", "T_Real", "Hora_Futuro", "T_Pred", "Incertidumbre"])

# =========================================================
# 3. PROCESAMIENTO DE DATOS (REPARADO)
# =========================================================
ahora = datetime.now()
t_now, p_now, tds_now = 18.0, 7.0, 0.0 # Valores base por si falla Firebase

try:
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
except Exception as e:
    st.sidebar.warning("Error de conexión a Firebase")

# Lógica de Predicción
hora_futuro = (ahora + timedelta(hours=jornada_hrs)).strftime("%H:%M:%S")
tf = t_now # Valor default

if mod_t and cols_modelo:
    entrada = pd.DataFrame([[t_now, p_now, float(jornada_hrs)]], columns=['temperatura', 'ph', 'horas_transcurridas'])
    for c in cols_modelo:
        if c not in entrada.columns: entrada[c] = 0
    pred_base = float(mod_t.predict(entrada[cols_modelo])[0])
    tf = t_now + pred_base + offset_manual
else:
    tf = t_now + (0.1 * jornada_hrs) # Simulación si no hay modelo

error_banda = (jornada_hrs / 24.0) * 1.2 # Margen de error lógico para la tesis

# Guardar en historial
nuevo = {
    "Hora_Real": ahora.strftime("%H:%M:%S"),
    "T_Real": t_now,
    "Hora_Futuro": hora_futuro,
    "T_Pred": tf,
    "Incertidumbre": error_banda
}
st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(30)

# =========================================================
# 4. INTERFAZ GRÁFICA
# =========================================================
st.title("🌊 Dashboard de Planeación Predictiva RAS")
st.info(f"Visualizando proyección para las **{hora_futuro}** (Horizonte de {jornada_hrs}h)")

# Semáforo de Riesgo
riesgo_futuro = "🔴 ALTO" if tf > 24 or tf < 15 else "🟢 BAJO"
m1, m2, m3 = st.columns(3)
m1.metric("Temperatura Actual", f"{t_now:.1f} °C")
m2.metric(f"Predicción (+{jornada_hrs}h)", f"{tf:.1f} °C", f"{tf-t_now:.2f} Δ")
m3.metric("Riesgo Proyectado", riesgo_futuro)

# GRÁFICA PROYECTADA
fig = go.Figure()

# 1. Sombreado de Incertidumbre
fig.add_trace(go.Scatter(
    x=st.session_state.historial["Hora_Real"], 
    y=st.session_state.historial["T_Pred"] + st.session_state.historial["Incertidumbre"],
    mode='lines', line=dict(width=0), showlegend=False))

fig.add_trace(go.Scatter(
    x=st.session_state.historial["Hora_Real"], 
    y=st.session_state.historial["T_Pred"] - st.session_state.historial["Incertidumbre"],
    fill='tonexty', fillcolor='rgba(255, 255, 0, 0.1)', mode='lines', line=dict(width=0),
    name="Margen de Error (IA)"))

# 2. Líneas Principales
fig.add_trace(go.Scatter(x=st.session_state.historial["Hora_Real"], y=st.session_state.historial["T_Real"], 
                         name="Dato Real (Presente)", line=dict(color="#00d4ff", width=4)))

fig.add_trace(go.Scatter(x=st.session_state.historial["Hora_Real"], y=st.session_state.historial["T_Pred"], 
                         name=f"Tendencia a futuro ({jornada_hrs}h)", line=dict(dash='dot', color="yellow", width=2)))

fig.update_layout(template="plotly_dark", title="Análisis de Inercia Térmica Proyectada", height=500)
st.plotly_chart(fig, use_container_width=True)

# Sección Inferior
st.markdown("---")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

st.sidebar.write(f"Sólidos TDS: {tds_now:.0f} ppm")
