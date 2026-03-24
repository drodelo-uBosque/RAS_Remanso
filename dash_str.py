import streamlit as st
import pandas as pd
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. SERVICIOS (FIREBASE + IA)
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
        except Exception as e:
            st.error(f"Error Firebase: {e}"); st.stop()
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except:
        st.error("Error al cargar modelos IA"); st.stop()

st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide")
mod_t, mod_p, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

# =========================================================
# 2. SIDEBAR: EL SLIDER DE SENSIBILIDAD / AJUSTE
# =========================================================
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.title("⚙️ Ajuste de Predicción")

# SLIDER DE SENSIBILIDAD (Ajuste aditivo para subir/bajar la línea)
# Si la línea está muy abajo, mueve este slider hacia la derecha.
ajuste_sensibilidad = st.sidebar.slider("Ajuste de Línea IA (Sensibilidad)", -5.0, 5.0, 0.0, 0.1)
n_muestras = st.sidebar.slider("Puntos en pantalla", 10, 100, 40)

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS"])

# =========================================================
# 3. CAPTURA Y CÁLCULO IA
# =========================================================
ahora = datetime.now()
try:
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
        
        # Preparación para XGBoost
        entrada = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        entrada = entrada[cols_modelo]

        # --- APLICACIÓN DEL SLIDER ---
        # Sumamos el ajuste_sensibilidad al resultado del modelo para posicionar la línea
        tf = t_now + float(mod_t.predict(entrada)[0]) + ajuste_sensibilidad
        pf = p_now + float(mod_p.predict(entrada)[0]) + (ajuste_sensibilidad * 0.2) # pH varía menos
        
        nuevo = {"Hora": ahora.strftime("%H:%M:%S"), "T_R": t_now, "T_P": tf, "P_R": p_now, "P_P": pf, "TDS": tds_now}
        st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(n_muestras)
    else:
        t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0
except:
    t_now, p_now, tds_now, tf, pf = 18.0, 7.0, 0.0, 18.0, 7.0

# =========================================================
# 4. DASHBOARD VISUAL
# =========================================================
st.title("🌊 Dashboard Inteligente RAS - UDCA")

col1, col2, col3 = st.columns(3)
col1.metric("🌡️ Temp Actual", f"{t_now:.1f} °C", f"{tf-t_now:.2f} IA")
col2.metric("🧪 pH Actual", f"{p_now:.2f}", f"{pf-p_now:.2f} IA")
col3.metric("💧 TDS", f"{tds_now:.0f} ppm")

c_a, c_b = st.columns(2)

with c_a:
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_R"], name="Dato Real", line=dict(color="#00d4ff", width=4)))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"], name="Predicción IA", line=dict(dash='dot', color="yellow", width=2)))
    # Forzamos a que el eje Y se ajuste automáticamente para ver ambas líneas
    fig_t.update_layout(template="plotly_dark", title="Tendencia de Temperatura", height=380, yaxis=dict(autorange=True))
    st.plotly_chart(fig_t, use_container_width=True)

with c_b:
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_R"], name="Dato Real", line=dict(color="#ff00ff", width=4)))
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_P"], name="Predicción IA", line=dict(dash='dot', color="yellow", width=2)))
    fig_p.update_layout(template="plotly_dark", title="Tendencia de pH", height=380, yaxis=dict(autorange=True))
    st.plotly_chart(fig_p, use_container_width=True)

# Gráfica de Sólidos (TDS)
st.markdown("---")
fig_tds = go.Figure(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["TDS"], fill='tozeroy', line=dict(color='#00ff88')))
fig_tds.update_layout(template="plotly_dark", title="Sólidos Totales Disueltos (TDS)", height=250)
st.plotly_chart(fig_tds, use_container_width=True)

# Descarga en Sidebar
st.sidebar.markdown("---")
csv = st.session_state.historial.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Descargar Reporte CSV", csv, "reporte_ras.csv", "text/csv")
