import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from PIL import Image
import io
import os

# =========================================================
# 0. PARÁMETROS TÉCNICOS (LÍMITES ESTRICTOS)
# =========================================================
TEMP_MIN_SIM, TEMP_MAX_SIM = 20.1, 21.0
PH_MIN_SIM, PH_MAX_SIM = 7.0, 7.6
TDS_MIN_SIM, TDS_MAX_SIM = 180.0, 182.0

RANGOS_TEMP = [10.0, 14.0, 17.0, 21.0, 24.0, 30.0]
RANGOS_PH = [4.0, 6.0, 6.8, 8.2, 9.0, 11.0]
TDS_ESCALA_GAUGE = [0, 100, 180, 182, 250, 300] 

ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = None

st.set_page_config(page_title="Sistema RAS - UDCA", layout="wide", page_icon=favicon)

# =========================================================
# 1. AUTENTICACIÓN
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        if os.path.exists(ruta_logo): st.image(ruta_logo, width=180)
        st.markdown("<h2 style='text-align: center;'>Acceso al Sistema</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Ingresar", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.rerun()
                else: st.error("Acceso incorrecto")
    st.stop()

# =========================================================
# 2. MOTOR DE SIMULACIÓN ELEGANTE (CAMINATA ALEATORIA)
# =========================================================
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(50, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.linspace(20.4, 20.6, 50) + np.random.normal(0, 0.02, 50),
        "pH": np.linspace(7.2, 7.3, 50) + np.random.normal(0, 0.01, 50),
        "TDS": np.linspace(180.5, 181.5, 50)
    })

def generar_flujo_suave(actual, min_v, max_v, escala):
    # Inercia alta (0.85) para evitar saltos bruscos
    centro = (max_v + min_v) / 2
    # El valor tiende ligeramente al centro para no pegarse a los bordes
    tendencia = (centro - actual) * 0.1
    ruido = np.random.normal(tendencia, escala)
    nuevo = actual + ruido
    return np.clip(nuevo, min_v + 0.01, max_v - 0.01)

ult = st.session_state.db_simulada.iloc[-1]
nueva_medicion = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": generar_flujo_suave(ult["Temperatura"], TEMP_MIN_SIM, TEMP_MAX_SIM, 0.04),
    "pH": generar_flujo_suave(ult["pH"], PH_MIN_SIM, PH_MAX_SIM, 0.02),
    "TDS": generar_flujo_suave(ult["TDS"], TDS_MIN_SIM, TDS_MAX_SIM, 0.1)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nueva_medicion])], ignore_index=True).tail(50)

# =========================================================
# 3. INTERFAZ Y GRÁFICAS
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo, use_container_width=True)
    st.markdown("### Reportes")
    st.download_button("Descargar Excel", st.session_state.db_simulada.to_csv(index=False).encode('utf-8'), "Reporte_RAS.csv", use_container_width=True)
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

tab1, tab2 = st.tabs(["Monitor Tiempo Real", "Dataset Histórico"])

with tab1:
    # Gauges
    g1, g2, g3 = st.columns(3)
    def quick_gauge(val, tit, uni, lims, r_max=None):
        fig = go.Figure(go.Indicator(mode="gauge+number", value=val, title={'text': f"<b>{tit}</b>"}, number={'suffix': f" {uni}"},
            gauge={'axis': {'range': [0, r_max] if r_max else [lims[0], lims[5]]}, 'bar': {'color': "#2d3436"},
            'steps': [{'range': [lims[0], lims[1]], 'color': "#ff7675"}, {'range': [lims[1], lims[2]], 'color': "#ffeaa7"},
                      {'range': [lims[2], lims[3]], 'color': "#55efc4"}, {'range': [lims[3], lims[4]], 'color': "#ffeaa7"},
                      {'range': [lims[4], lims[5]], 'color': "#ff7675"}]}))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
        return fig

    g1.plotly_chart(quick_gauge(nueva_medicion["Temperatura"], "TEMPERATURA", "°C", RANGOS_TEMP), use_container_width=True)
    g2.plotly_chart(quick_gauge(nueva_medicion["pH"], "pH", "pts", RANGOS_PH), use_container_width=True)
    g3.plotly_chart(quick_gauge(nueva_medicion["TDS"], "SÓLIDOS TDS", "ppm", TDS_ESCALA_GAUGE, r_max=300), use_container_width=True)

    # Gráficas de Tendencia
    st.markdown("### Análisis de Tendencias")
    c1, c2 = st.columns(2)
    with c1:
        f1 = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", markers=True, 
                     title="Monitoreo de Temperatura", color_discrete_sequence=["#d63031"], template="plotly_white")
        f1.update_yaxes(range=[20.0, 21.1])
        st.plotly_chart(f1, use_container_width=True)
    with c2:
        f2 = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="pH", markers=True, 
                     title="Monitoreo de pH", color_discrete_sequence=["#00b894"], template="plotly_white")
        f2.update_yaxes(range=[6.9, 7.7])
        st.plotly_chart(f2, use_container_width=True)
    
    f3 = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="TDS", markers=True,
                 title="Sólidos Disueltos Totales", color_discrete_sequence=["#0984e3"], template="plotly_white")
    f3.update_yaxes(range=[179.5, 182.5])
    st.plotly_chart(f3, use_container_width=True)

with tab2:
    st.subheader("Análisis de Entrenamiento")
    df_h = pd.DataFrame({'Temp': np.random.normal(20.5, 0.8, 500), 'pH': np.random.normal(7.3, 0.3, 500)})
    st.plotly_chart(px.density_heatmap(df_h, x="Temp", y="pH", color_continuous_scale="Viridis", template="plotly_white"), use_container_width=True)
