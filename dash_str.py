import streamlit as st
import pandas as pd
import numpy as np
import joblib
import time
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go

# =========================================================
# 1. CONFIGURACIÓN Y RECURSOS (MÉTODO REST)
# =========================================================
# REEMPLAZA CON TUS DATOS DE TELEGRAM
TOKEN_TELEGRAM = "TU_TOKEN_BOT_AQUI"
CHAT_ID_TELEGRAM = "TU_ID_CHAT_AQUI"

# URLs de Firebase (Importante el .json al final)
URL_BASE = "https://ras-udca-default-rtdb.firebaseio.com/"
URL_ACTUAL = f"{URL_BASE}sensores/temperatura/actual/.json"
URL_HISTORIAL = f"{URL_BASE}sensores/temperatura/historial/.json"

@st.cache_resource
def cargar_recursos():
    # El archivo .pkl debe estar en la misma carpeta del repo
    p = joblib.load('sistema_ras_completo.pkl')
    return p['modelo_temp'], p['modelo_ph'], p['columnas']

mod_t, mod_p, cols_modelo = cargar_recursos()

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage?chat_id={CHAT_ID_TELEGRAM}&text={mensaje}&parse_mode=Markdown"
    try: requests.get(url, timeout=5)
    except: pass

# =========================================================
# 2. LOGIN Y CONFIGURACIÓN DE PÁGINA
# =========================================================
st.set_page_config(page_title="RAS AI Monitor - UDCA", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Acceso Sistema RAS - Remanso")
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
# 3. INTERFAZ Y CONTENEDORES (EVITA NAMEERROR)
# =========================================================
st.title("🐟 Monitoreo Inteligente RAS con XGBoost")

# Sidebar
st.sidebar.title("⚙️ Panel de Control")
sensibilidad = st.sidebar.slider("Sensibilidad IA", 0.5, 1.5, 1.0)
horas_pred = st.sidebar.slider("Horizonte de Predicción (Horas)", 0.5, 12.0, 1.0, step=0.5)
refresco = st.sidebar.slider("Refresco (seg)", 5, 60, 10)

with st.sidebar.expander("📥 Exportar Datos"):
    if st.button("Descargar Historial CSV"):
        r_hist = requests.get(URL_HISTORIAL)
        if r_hist.status_code == 200 and r_hist.json():
            df_nube = pd.DataFrame(list(r_hist.json().values()))
            st.download_button("Descargar Archivo", df_nube.to_csv().encode('utf-8'), "datos_ras.csv")

# Layout de métricas
alerta_ui = st.empty()
m1, m2, m3, m4 = st.columns(4)
t_met, p_met = m1.empty(), m2.empty()
ti_met, pi_met = m3.empty(), m4.empty()

chart_t = st.empty()
chart_p = st.empty()

if 'hist_v' not in st.session_state:
    st.session_state.hist_v = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P"])
if 'ultimo_aviso' not in st.session_state:
    st.session_state.ultimo_aviso = datetime.now() - timedelta(minutes=20)

# =========================================================
# 4. BUCLE DE EJECUCIÓN
# =========================================================
while True:
    ahora = datetime.now()
    
    # A. Lectura de Firebase
    try:
        resp = requests.get(URL_ACTUAL, timeout=5)
        t_now = float(resp.json()) if resp.status_code == 200 and resp.json() else 22.0
        st.sidebar.success(f"📡 Sensor Online: {t_now}°C")
    except:
        t_now = 22.0
        st.sidebar.error("❌ Error de Conexión")

    # B. Procesamiento IA
    p_now = 7.4 + np.random.uniform(-0.01, 0.01) # Simulación estable de pH
    df_in = pd.DataFrame([[t_now, p_now, horas_pred]], columns=['temperatura', 'ph', 'horas_transcurridas'])
    for c in cols_modelo:
        if c not in df_in.columns: df_in[c] = 0
    df_in = df_in[cols_modelo]

    # Predicción escalada
    tf = t_now + float(mod_t.predict(df_in)[0] * sensibilidad)
    pf = p_now + float(mod_p.predict(df_in)[0] * (sensibilidad * 0.5))

    # C. Lógica de Alertas
    errores = []
    if tf < 23.0 or tf > 29.0: errores.append(f"🌡️ Temp Crítica prevista: {tf:.2f}°C")
    if pf < 6.8 or pf > 8.5: errores.append(f"🧪 pH Crítico previsto: {pf:.2f}")

    if errores:
        alerta_ui.error("⚠️ **ALERTA PREVENTIVA IA:**\n" + "\n".join(errores))
        mins_pasados = (ahora - st.session_state.ultimo_aviso).total_seconds() / 60
        if mins_pasados > 15:
            enviar_telegram(f"🚨 *AVISO RAS*\nHorizonte: {horas_pred}h\n" + "\n".join(errores))
            st.session_state.ultimo_aviso = ahora
    else:
        alerta_ui.success("✅ Condiciones óptimas proyectadas en el tanque.")

    # D. Actualizar Visualización
    t_met.metric("🌡️ TEMP ACTUAL", f"{t_now:.2f}°C")
    p_met.metric("🧪 PH ACTUAL", f"{p_now:.2f}")
    ti_met.metric(f"🤖 IA TEMP ({horas_pred}h)", f"{tf:.2f}°C", delta=f"{tf-t_now:.2f}")
    pi_met.metric(f"🤖 IA PH ({horas_pred}h)", f"{pf:.2f}", delta=f"{pf-p_now:.2f}")

    # E. Gráficas
    nueva_fila = pd.DataFrame({"Hora":[ahora.strftime("%H:%M:%S")],"T_R":[t_now],"T_P":[tf],"P_R":[p_now],"P_P":[pf]})
    st.session_state.hist_v = pd.concat([st.session_state.hist_v, nueva_fila]).tail(20)

    def crear_grafica(df, col_r, col_p, color, titulo):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[col_r], name="Real", line=dict(color='#00d4ff', width=3)))
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[col_p], name="IA", line=dict(color=color, dash='dot')))
        fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10,r=10,t=40,b=10))
        return fig

    chart_t.plotly_chart(crear_grafica(st.session_state.hist_v, "T_R", "T_P", "orange", "Temperatura (°C)"), use_container_width=True)
    chart_p.plotly_chart(crear_grafica(st.session_state.hist_v, "P_R", "P_P", "crimson", "Nivel de pH"), use_container_width=True)

    time.sleep(refresco)
