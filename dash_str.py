import streamlit as st
import pandas as pd
import numpy as np
import joblib
import time
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go go

# =========================================================
# 1. CONFIGURACIÓN Y MODELO (SIN FIREBASE-ADMIN)
# =========================================================
# URL de tu base de datos con ".json" al final (IMPORTANTE)
URL_BASE = "https://ras-udca-default-rtdb.firebaseio.com/.json"
URL_ACTUAL = "https://ras-udca-default-rtdb.firebaseio.com/sensores/temperatura/actual/.json"

@st.cache_resource
def cargar_modelo():
    p = joblib.load('sistema_ras_completo.pkl')
    return p['modelo_temp'], p['modelo_ph'], p['columnas']

mod_t, mod_p, cols_modelo = cargar_modelo()

# ... (Mantén tu código de login igual aquí) ...

# =========================================================
# 2. BUCLE DE MONITOREO (CONEXIÓN DIRECTA)
# =========================================================
while True:
    ahora = datetime.now()
    
    try:
        # LEEMOS DIRECTAMENTE POR URL (Sin llaves, sin errores JWT)
        respuesta = requests.get(URL_ACTUAL)
        
        if respuesta.status_code == 200:
            data = respuesta.json()
            # Si el ESP32 manda un número directo:
            t_now = float(data) if data is not None else 22.0
            st.sidebar.success(f"📡 Conectado (REST): {t_now}°C")
        else:
            t_now = 22.0
            st.sidebar.error("⚠️ Error de respuesta de Firebase")
            
    except Exception as e:
        t_now = 22.0
        st.sidebar.error(f"❌ Error de red: {e}")

    # --- C. PROYECCIÓN IA (Igual que antes) ---
    p_now = 7.4 + np.random.uniform(-0.02, 0.02)
    df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
    for c in cols_modelo:
        if c not in df_in.columns: df_in[c] = 0
    df_in = df_in[cols_modelo]

    tf = t_now + float(mod_t.predict(df_in)[0])
    pf = p_now + float(mod_p.predict(df_in)[0])

    # ... (El resto del código de métricas y gráficas es IGUAL) ...
    t_met.metric("🌡️ TEMP ACTUAL", f"{t_now:.2f}°C")
    # ...
    time.sleep(5)

# =========================================================
# 3. INTERFAZ Y LOGIN
# =========================================================
st.set_page_config(page_title="RAS Real-Time Monitor", layout="wide")

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
# 4. CONFIGURACIÓN DE UI Y ESTADO
# =========================================================
st.sidebar.title("⚙️ Configuración")
sensibilidad = st.sidebar.slider("Sensibilidad IA (Predicción)", 0.1, 2.0, 1.0, step=0.1)
refresco = st.sidebar.slider("Refresco (seg)", 2, 30, 10)

if 'hist' not in st.session_state:
    st.session_state.hist = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P"])
    st.session_state.ultimo_aviso = datetime.now() - timedelta(minutes=20)
    st.session_state.ph_sim = 7.4

# Botón de Descarga de Historial Real de la Nube
with st.sidebar.expander("📥 Datos de la Nube"):
    if st.button("Descargar CSV"):
        raw_data = rtdb.reference('/sensores/temperatura/historial').get()
        if raw_data:
            df_nube = pd.DataFrame(list(raw_data.values()))
            # Convertir timestamp a fecha legible de Bogotá
            if 'tiempo' in df_nube.columns:
                df_nube['fecha'] = pd.to_datetime(df_nube['tiempo'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('America/Bogota')
            csv = df_nube.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Archivo", csv, "historial_ras.csv", "text/csv", key="btn_descarga")

st.title("🐟 Monitoreo Realtime + Predicción XGBoost")
alerta_ui = st.empty()
m1, m2, m3, m4 = st.columns(4)
t_met, p_met = m1.empty(), m2.empty()
ti_met, pi_met = m3.empty(), m4.empty()

chart_t = st.empty()
chart_p = st.empty()

# =========================================================
# 5. BUCLE DE MONITOREO
# =========================================================
while True:
    ahora = datetime.now()
    
    try:
        # LEEMOS LA NUEVA RUTA (Como ahora es un JSON, buscamos el campo 'actual')
        # Si en tu Firebase ves: actual -> valor, la ruta es '/sensores/temperatura/actual'
        data_fb = rtdb.reference('/sensores/temperatura/actual').get()
        
        if data_fb is not None:
            # Si mandaste el dato como número directo:
            t_now = float(data_fb)
            st.sidebar.success(f"📡 Conectado: {t_now}°C")
        else:
            t_now = 22.0
            st.sidebar.warning("⚠️ No hay datos en '/actual'")
            
    except Exception as e:
        t_now = 22.0
        st.sidebar.error(f"❌ Error: {e}")

    # --- B. PH SIMULADO ---
    p_now = 7.4 + np.random.uniform(-0.02, 0.02)

    # --- C. PROYECCIÓN IA ---
    # Creamos el DataFrame de entrada EXACTAMENTE como lo espera el modelo
    df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
    for c in cols_modelo:
        if c not in df_in.columns: df_in[c] = 0
    df_in = df_in[cols_modelo]

    # Predicción (Sin multiplicadores locos para evitar que se vaya al suelo)
    pred_t = float(mod_t.predict(df_in)[0])
    pred_p = float(mod_p.predict(df_in)[0])
    
    tf = t_now + (pred_t * sensibilidad)
    pf = p_now + (pred_p * sensibilidad)

    # --- D. ALERTAS ---
    errores = []
    if tf < TEMP_MIN or tf > TEMP_MAX: errores.append(f"🌡️ Temp Crítica Proyectada: {tf:.2f}°C")
    
    mins_alerta = (ahora - st.session_state.ultimo_aviso).total_seconds() / 60
    if errores:
        alerta_ui.error("🚨 **ALERTA IA:**\n" + "\n".join(errores))
        if mins_alerta > 15:
            enviar_telegram("🚨 *AVISO RAS*\n" + "\n".join(errores))
            st.session_state.ultimo_aviso = ahora
    else:
        alerta_ui.success("✅ Sistema estable - Tanque en condiciones óptimas")

    # --- E. ACTUALIZAR DASHBOARD ---
    t_met.metric("🌡️ TEMP ACTUAL", f"{t_now:.2f}°C")
    p_met.metric("🧪 PH ACTUAL", f"{p_now:.2f}")
    ti_met.metric("🤖 IA TEMP (1h)", f"{tf:.2f}°C", delta=f"{tf-t_now:.2f}")
    pi_met.metric("🤖 IA PH (1h)", f"{pf:.2f}", delta=f"{pf-p_now:.2f}")

    # Actualizar Gráfica
    nuevo = pd.DataFrame({"Hora":[ahora.strftime("%H:%M:%S")],"T_R":[t_now],"T_P":[tf],"P_R":[p_now],"P_P":[pf]})
    st.session_state.hist = pd.concat([st.session_state.hist, nuevo]).tail(20)

    def graficar(df, r, p, color, tit):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[r], name="Real", line=dict(color='#00d4ff', width=3)))
        fig.add_trace(go.Scatter(x=df["Hora"], y=df[p], name="IA", line=dict(color=color, dash='dot')))
        fig.update_layout(template="plotly_dark", title=tit, height=350)
        return fig

    chart_t.plotly_chart(graficar(st.session_state.hist, "T_R", "T_P", "orange", "Temperatura (°C)"), use_container_width=True)
    chart_p.plotly_chart(graficar(st.session_state.hist, "P_R", "P_P", "crimson", "Nivel de pH"), use_container_width=True)

    time.sleep(refresco)
