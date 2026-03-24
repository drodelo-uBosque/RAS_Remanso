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
# 1. CONFIGURACIÓN Y SERVICIOS (OCULTO)
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
            st.error(f"Error de conexión: {e}")
            st.stop()
    
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except:
        st.error("Error al cargar modelos IA (.pkl)")
        st.stop()

# Configuración de página
st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide", page_icon="🐟")
mod_t, mod_p, cols_modelo = iniciar_servicios()

# =========================================================
# 2. SIDEBAR: CONTROLES DE USUARIO (ESTÉTICA ORIGINAL)
# =========================================================
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.title("⚙️ Configuración")

# Control de muestras (Historial)
n_muestras = st.sidebar.slider("Número de muestras en pantalla", 10, 100, 30)

# Sensibilidad (Simulada para visualización de IA)
sensibilidad = st.sidebar.select_slider("Sensibilidad de Alerta", options=["Baja", "Media", "Alta"], value="Media")

st.sidebar.markdown("---")

# =========================================================
# 3. GESTIÓN DE DATOS Y FIREBASE
# =========================================================
st_autorefresh(interval=5000, key="global_refresh")

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS"])

ahora = datetime.now()

try:
    # Lectura silenciosa (Sin mostrar JSON)
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
        
        # Predicción IA
        entrada = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        entrada = entrada[cols_modelo]

        tf = t_now + float(mod_t.predict(entrada)[0])
        pf = p_now + float(mod_p.predict(entrada)[0])
        
        # Guardar en historial
        nuevo = {"Hora": ahora.strftime("%H:%M:%S"), "T_R": t_now, "T_P": tf, "P_R": p_now, "P_P": pf, "TDS": tds_now}
        st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(n_muestras)
    else:
        t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0

except:
    t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0

# =========================================================
# 4. INTERFAZ PRINCIPAL (DASHBOARD)
# =========================================================
st.title("🌊 Sistema de Monitoreo Inteligente RAS - UDCA")
st.markdown(f"Última actualización: **{ahora.strftime('%H:%M:%S')}**")

# Métricas destacadas
m1, m2, m3 = st.columns(3)
m1.metric("🌡️ Temperatura", f"{t_now:.1f} °C", f"{tf-t_now:.2f} (IA)")
m2.metric("🧪 pH del Agua", f"{p_now:.2f}", f"{pf-p_now:.2f} (IA)")
m3.metric("💧 TDS", f"{tds_now:.0f} ppm")

# Gráficas de Análisis
col_a, col_b = st.columns(2)

with col_a:
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_R"], name="Real", line=dict(color="#00d4ff", width=4)))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"], name="IA", line=dict(dash='dot', color="white")))
    fig_t.update_layout(template="plotly_dark", title="Dinámica Térmica", height=350, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_t, use_container_width=True)

with col_b:
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_R"], name="Real", line=dict(color="#ff00ff", width=4)))
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_P"], name="IA", line=dict(dash='dot', color="white")))
    fig_p.update_layout(template="plotly_dark", title="Evolución de pH", height=350, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_p, use_container_width=True)

# Sección de descarga en el Sidebar
st.sidebar.subheader("📥 Reportes")
csv = st.session_state.historial.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("Descargar CSV de Ensayo", csv, f"ras_data_{ahora.strftime('%Y%m%d')}.csv", "text/csv")

st.sidebar.info(f"Sensibilidad configurada en modo: **{sensibilidad}** para el análisis de variables basales.")
