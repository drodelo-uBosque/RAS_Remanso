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

# Rangos para Gauges (Zonas Operativas Técnicas)
RANGOS_TEMP = [10.0, 14.0, 17.0, 21.0, 24.0, 30.0]
RANGOS_PH = [4.0, 6.0, 6.8, 8.2, 9.0, 11.0]
TDS_ESCALA_GAUGE = [0, 100, 180, 182, 250, 300] 

ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = None

st.set_page_config(page_title="Sistema RAS - UDCA", layout="wide", page_icon=favicon)

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 1. SISTEMA DE AUTENTICACIÓN
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
                else: st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 2. MOTOR DE SIMULACIÓN ORGÁNICA (VIBRACIÓN NATURAL)
# =========================================================
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(50, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(20.4, 20.7, 50),
        "pH": np.random.uniform(7.2, 7.4, 50),
        "TDS": np.random.uniform(180.5, 181.5, 50)
    })

def generar_vibracion(actual, variacion, min_v, max_v):
    # Reducimos la inercia a 0.7 para que la gráfica tenga "movimiento"
    cambio = np.random.uniform(-variacion, variacion)
    nuevo = (actual * 0.7) + ((actual + cambio) * 0.3)
    # Rebotar si toca los bordes para mantener la gráfica centrada
    if nuevo >= max_v: nuevo = max_v - 0.05
    if nuevo <= min_v: nuevo = min_v + 0.05
    return nuevo

ult = st.session_state.db_simulada.iloc[-1]
nueva_medicion = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": generar_vibracion(ult["Temperatura"], 0.2, TEMP_MIN_SIM, TEMP_MAX_SIM),
    "pH": generar_vibracion(ult["pH"], 0.06, PH_MIN_SIM, PH_MAX_SIM),
    "TDS": generar_vibracion(ult["TDS"], 0.4, TDS_MIN_SIM, TDS_MAX_SIM)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nueva_medicion])], ignore_index=True).tail(50)

# =========================================================
# 3. SIDEBAR
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo, use_container_width=True)
    st.markdown("### Gestión de Datos")
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            st.session_state.db_simulada.to_excel(w, index=False, sheet_name='Monitoreo_RAS')
        st.download_button("Descargar Reporte Excel", buf.getvalue(), "Reporte_RAS.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except:
        st.download_button("Descargar CSV", st.session_state.db_simulada.to_csv(index=False).encode('utf-8'), "Reporte.csv", "text/csv", use_container_width=True)
    
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# =========================================================
# 4. INTERFAZ DE PESTAÑAS (TABS)
# =========================================================
st.title("Plataforma de Monitoreo RAS - El Remanso")
tab1, tab2 = st.tabs(["Monitor en Tiempo Real", "Análisis de Entrenamiento"])

with tab1:
    # Gauges
    def render_gauge(val, titulo, unidad, lims, custom_range=None):
        axis_range = custom_range if custom_range else [lims[0], lims[5]]
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=val,
            title={'text': f"<b>{titulo}</b>"}, number={'suffix': f" {unidad}"},
            gauge={
                'axis': {'range': axis_range},
                'bar': {'color': "#2d3436"},
                'steps': [
                    {'range': [lims[0], lims[1]], 'color': "#ff7675"},
                    {'range': [lims[1], lims[2]], 'color': "#ffeaa7"},
                    {'range': [lims[2], lims[3]], 'color': "#55efc4"},
                    {'range': [lims[3], lims[4]], 'color': "#ffeaa7"},
                    {'range': [lims[4], lims[5]], 'color': "#ff7675"}
                ]
            }
        ))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
        return fig

    g1, g2, g3 = st.columns(3)
    with g1: st.plotly_chart(render_gauge(nueva_medicion["Temperatura"], "TEMPERATURA", "°C", RANGOS_TEMP), use_container_width=True)
    with g2: st.plotly_chart(render_gauge(nueva_medicion["pH"], "pH", "pts", RANGOS_PH), use_container_width=True)
    with g3: st.plotly_chart(render_gauge(nueva_medicion["TDS"], "SÓLIDOS TDS", "ppm", TDS_ESCALA_GAUGE, custom_range=[0, 300]), use_container_width=True)

    # Gráficas
    st.markdown("### Análisis de Tendencias")
    c1, c2 = st.columns(2)
    with c1:
        f_temp = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", markers=True, 
                         title="Monitoreo de Temperatura", color_discrete_sequence=["#d63031"], template="plotly_white")
        f_temp.update_yaxes(range=[TEMP_MIN_SIM - 0.1, TEMP_MAX_SIM + 0.1])
        st.plotly_chart(f_temp, use_container_width=True)
    with c2:
        f_ph = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="pH", markers=True, 
                       title="Monitoreo de pH", color_discrete_sequence=["#00b894"], template="plotly_white")
        f_ph.update_yaxes(range=[PH_MIN_SIM - 0.1, PH_MAX_SIM + 0.1])
        st.plotly_chart(f_ph, use_container_width=True)
    
    f_tds_area = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="TDS", markers=True,
                         title="Sólidos Disueltos Totales", color_discrete_sequence=["#0984e3"], template="plotly_white")
    f_tds_area.update_yaxes(range=[TDS_MIN_SIM - 0.5, TDS_MAX_SIM + 0.5])
    st.plotly_chart(f_tds_area, use_container_width=True)

with tab2:
    st.subheader("Dataset de Entrenamiento")
    np.random.seed(42)
    df_train = pd.DataFrame({
        'Temperatura': np.random.normal(20.5, 1.2, 1000),
        'pH': np.random.normal(7.3, 0.4, 1000),
        'TDS': np.random.normal(250, 50, 1000)
    })
    col_h, col_s = st.columns([0.65, 0.35])
    with col_h:
        f_heat = px.density_heatmap(df_train, x="Temperatura", y="pH", z="TDS", histfunc="avg", 
                                    color_continuous_scale="Viridis", template="plotly_white",
                                    title="Relación Temperatura vs pH (Histórico)")
        st.plotly_chart(f_heat, use_container_width=True)
    with col_s:
        st.markdown("**Resumen Estadístico**")
        st.dataframe(df_train.describe().T, use_container_width=True)
