import streamlit as st
import pandas as pd
import numpy as np
import joblib
import time
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go


# =========================================================
# CONFIGURACIÓN DE ALERTAS (BOGOTÁ / UDCA)
# =========================================================
TOKEN_TELEGRAM = "TU_TOKEN_AQUI"
CHAT_ID_TELEGRAM = "TU_ID_AQUI"
TEMP_MIN, TEMP_MAX = 22.0, 30.0
PH_MIN, PH_MAX = 6.8, 8.2

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage?chat_id={CHAT_ID_TELEGRAM}&text={mensaje}&parse_mode=Markdown"
    try:
        requests.get(url)
    except:
        pass
# =========================================================
# 1. CONFIGURACIÓN Y RECURSOS
# =========================================================
# URL de tu base de datos (IMPORTANTE el .json al final para modo REST)
URL_ACTUAL = "https://ras-udca-default-rtdb.firebaseio.com/sensores/temperatura/actual/.json"
URL_HISTORIAL = "https://ras-udca-default-rtdb.firebaseio.com/sensores/temperatura/historial/.json"

@st.cache_resource
def cargar_recursos():
    # Asegúrate de que el archivo .pkl esté en la misma carpeta en GitHub
    p = joblib.load('sistema_ras_completo.pkl')
    return p['modelo_temp'], p['modelo_ph'], p['columnas']

mod_t, mod_p, cols_modelo = cargar_recursos()

# =========================================================
# 2. LOGIN DE SEGURIDAD
# =========================================================
st.set_page_config(page_title="RAS AI Monitor", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Control de Acceso RAS")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 3. DEFINICIÓN DE INTERFAZ (EVITA EL NAMEERROR)
# =========================================================
st.title("Monitoreo Realtime + Predicción XGBoost")

# Sidebar para controles y descarga
st.sidebar.title("⚙️ Configuración")
sensibilidad = st.sidebar.slider("Sensibilidad IA", 0.1, 2.0, 1.0)
refresco = st.sidebar.slider("Refresco (seg)", 2, 30, 10)

with st.sidebar.expander("📥 Datos de la Nube"):
    if st.button("Descargar Historial"):
        r_hist = requests.get(URL_HISTORIAL)
        if r_hist.status_code == 200 and r_hist.json():
            df_nube = pd.DataFrame(list(r_hist.json().values()))
            st.download_button("Bajar CSV", df_nube.to_csv().encode('utf-8'), "historial.csv")

# CREACIÓN DE CONTENEDORES (Aquí se soluciona el error)
alerta_ui = st.empty()
m1, m2, m3, m4 = st.columns(4)
t_met = m1.empty()
p_met = m2.empty()
ti_met = m3.empty()
pi_met = m4.empty()

chart_t = st.empty()
chart_p = st.empty()

if 'hist_v' not in st.session_state:
    st.session_state.hist_v = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P"])

# =========================================================
# 4. BUCLE DE MONITOREO (CONEXIÓN REST)
# =========================================================
while True:
    ahora = datetime.now()
    
    # A. Lectura de Sensor (Sin llaves JWT)
    try:
        resp = requests.get(URL_ACTUAL)
        if resp.status_code == 200:
            data_val = resp.json()
            t_now = float(data_val) if data_val is not None else 22.0
            st.sidebar.success(f"📡 Sensor OK: {t_now}°C")
        else:
            t_now = 22.0
            st.sidebar.warning("⚠️ Error en Firebase (Rules?)")
    except:
        t_now = 22.0
        st.sidebar.error("❌ Error de Red")

    # B. IA y Simulación pH
    p_now = 7.4 + np.random.uniform(-0.01, 0.01)
    df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
    for c in cols_modelo:
        if c not in df_in.columns: df_in[c] = 0
    df_in = df_in[cols_modelo]

    tf = t_now + float(mod_t.predict(df_in)[0] * sensibilidad)
    pf = p_now + float(mod_p.predict(df_in)[0] * sensibilidad)

    # --- BLOQUE DE ALERTAS REINSTALADO ---
    errores = []
    # Alerta basada en la PREDICCIÓN (IA se adelanta al problema)
    if tf < TEMP_MIN or tf > TEMP_MAX: 
        errores.append(f"🌡️ IA predice Temp Crítica: {tf:.2f}°C")
    
    if pf < PH_MIN or pf > PH_MAX: 
        errores.append(f"🧪 IA predice pH Crítico: {pf:.2f}")

    # Control de tiempo para no saturar el Telegram (cada 15 min)
    if 'ultimo_aviso' not in st.session_state:
        st.session_state.ultimo_aviso = ahora - timedelta(minutes=20)

    mins_desde_alerta = (ahora - st.session_state.ultimo_aviso).total_seconds() / 60

    if errores:
        alerta_ui.error("🚨 **ALERTA DETECTADA POR IA:**\n" + "\n".join(errores))
        if mins_desde_alerta > 15:
            mensaje_bot = "🚨 *AVISO SISTEMA RAS*\n" + "\n".join(errores)
            enviar_telegram(mensaje_bot)
            st.session_state.ultimo_aviso = ahora
    else:
        alerta_ui.success("✅ Sistema Estable: Tanque en condiciones óptimas")

    # C. Actualizar Métricas (Ya no dará NameError)
    t_met.metric("🌡️ TEMP ACTUAL", f"{t_now:.2f}°C")
    p_met.metric("🧪 PH ACTUAL", f"{p_now:.2f}")
    ti_met.metric("🤖 IA TEMP (1h)", f"{tf:.2f}°C", delta=f"{tf-t_now:.2f}")
    pi_met.metric("🤖 IA PH (1h)", f"{pf:.2f}", delta=f"{pf-p_now:.2f}")

    # D. Gráficas Plotly
    nuevo_p = pd.DataFrame({"Hora":[ahora.strftime("%H:%M:%S")],"T_R":[t_now],"T_P":[tf],"P_R":[p_now],"P_P":[pf]})
    st.session_state.hist_v = pd.concat([st.session_state.hist_v, nuevo_p]).tail(20)

    def crear_fig(df, real, pred, color, titulo):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[real], name="Real", line=dict(color='#00d4ff', width=3)))
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[pred], name="IA", line=dict(color=color, dash='dot')))
        fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10,r=10,t=40,b=10))
        return fig

    chart_t.plotly_chart(crear_fig(st.session_state.hist_v, "T_R", "T_P", "orange", "Temperatura (°C)"), use_container_width=True)
    chart_p.plotly_chart(crear_fig(st.session_state.hist_v, "P_R", "P_P", "crimson", "Nivel de pH"), use_container_width=True)

    time.sleep(refresco)
