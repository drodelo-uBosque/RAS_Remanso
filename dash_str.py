import streamlit as st
import pandas as pd
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import os

# =========================================================
# 1. CONFIGURACIÓN Y SERVICIOS
# =========================================================
@st.cache_resource
def iniciar_servicios():
    if not firebase_admin._apps:
        try:
            info = dict(st.secrets["firebase_key"])
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/' 
            })
        except Exception as e:
            st.error(f"Error Firebase: {e}")
            st.stop()
    
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except:
        st.error("Error al cargar modelos IA (.pkl)")
        st.stop()

st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide", page_icon="🐟")
mod_t, mod_p, cols_modelo = iniciar_servicios()

# =========================================================
# 2. SIDEBAR: CONTROLES TÉCNICOS
# =========================================================
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.title("⚙️ Panel de Control")

# Control de muestras (Historial)
n_muestras = st.sidebar.slider("Puntos en pantalla", 10, 200, 50)

# Sensibilidad Numérica (Para ajuste de algoritmos de detección)
sensibilidad = st.sidebar.number_input("Umbral de Sensibilidad (0.0 - 1.0)", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

st.sidebar.markdown("---")

# =========================================================
# 3. MOTOR DE DATOS (FIREBASE + HISTORIAL)
# =========================================================
st_autorefresh(interval=5000, key="global_refresh")

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS"])

ahora = datetime.now()

try:
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
        
        # Predicción IA (XGBoost)
        entrada = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        entrada = entrada[cols_modelo]

        tf = t_now + float(mod_t.predict(entrada)[0])
        pf = p_now + float(mod_p.predict(entrada)[0])
        
        # Guardar en historial dinámico
        nuevo = {"Hora": ahora.strftime("%H:%M:%S"), "T_R": t_now, "T_P": tf, "P_R": p_now, "P_P": pf, "TDS": tds_now}
        st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(n_muestras)
    else:
        t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0
except:
    t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0

# =========================================================
# 4. INTERFAZ PRINCIPAL (DASHBOARD)
# =========================================================
st.title("🌊 Dashboard Inteligente RAS - UDCA")
st.caption(f"Sincronizado con Bogotá | Hora: {ahora.strftime('%H:%M:%S')}")

# Métricas en tiempo real
m1, m2, m3 = st.columns(3)
m1.metric("🌡️ Temperatura", f"{t_now:.1f} °C", f"{tf-t_now:.2f} (IA)")
m2.metric("🧪 pH del Agua", f"{p_now:.2f}", f"{pf-p_now:.2f} (IA)")
m3.metric("💧 TDS (Sólidos)", f"{tds_now:.0f} ppm")

# Gráficas de Tendencia
col_a, col_b = st.columns(2)

with col_a:
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_R"], name="Real", line=dict(color="#00d4ff", width=3)))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"], name="Predicción", line=dict(dash='dot', color="white", width=2)))
    fig_t.update_layout(template="plotly_dark", title="Dinámica Térmica (°C)", height=350, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_t, use_container_width=True)

with col_b:
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_R"], name="Real", line=dict(color="#ff00ff", width=3)))
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_P"], name="Predicción", line=dict(dash='dot', color="white", width=2)))
    fig_p.update_layout(template="plotly_dark", title="Evolución de pH", height=350, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_p, use_container_width=True)

# 📊 GRÁFICA DE TDS (Sólidos Totales Disueltos)
st.markdown("---")
fig_tds = go.Figure(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["TDS"], fill='tozeroy', line=dict(color='#00ff88'), name="TDS"))
fig_tds.add_hline(y=900, line_dash="dot", line_color="red", annotation_text="Límite Salinidad")
fig_tds.update_layout(template="plotly_dark", title="Análisis de Sólidos Totales Disueltos (ppm)", height=300, margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig_tds, use_container_width=True)

# Descarga de datos
st.sidebar.subheader("📥 Exportación")
csv = st.session_state.historial.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("Descargar Reporte CSV", csv, f"ensayo_ras_{ahora.strftime('%H%M')}.csv", "text/csv")
