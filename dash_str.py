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
# 0. PARÁMETROS TÉCNICOS Y RANGOS UDCA
# =========================================================
# Límites estrictos solicitados para simulación
TEMP_MIN_SIM, TEMP_MAX_SIM = 20.1, 21.0
PH_MIN_SIM, PH_MAX_SIM = 7.0, 7.6

# Rangos para Gauges (Zonas Operativas)
RANGOS_TEMP = [10.0, 14.0, 17.0, 21.0, 24.0, 30.0]
RANGOS_PH = [4.0, 6.0, 6.8, 8.2, 9.0, 11.0]
TDS_ALERTA, TDS_CRITICO = 600, 800

ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = None

st.set_page_config(page_title="Sistema RAS - UDCA", layout="wide", page_icon=favicon)

# CSS para fondo blanco y diseño profesional
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; border: 1px solid #eeeeee; }
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
# 2. MOTOR DE SIMULACIÓN ULTRA-ESTABLE
# =========================================================
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(50, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(20.3, 20.8, 50),
        "pH": np.random.uniform(7.2, 7.4, 50),
        "TDS": np.random.uniform(490, 510, 50)
    })

def suavizar_valor(actual, variacion, min_v, max_v):
    # Algoritmo de inercia: 95% valor anterior, 5% nueva tendencia
    ruido = np.random.uniform(-variacion, variacion)
    nuevo = (actual * 0.95) + ((actual + ruido) * 0.05)
    return np.clip(nuevo, min_v, max_v)

ult = st.session_state.db_simulada.iloc[-1]
nueva_medicion = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": suavizar_valor(ult["Temperatura"], 0.1, TEMP_MIN_SIM, TEMP_MAX_SIM),
    "pH": suavizar_valor(ult["pH"], 0.03, PH_MIN_SIM, PH_MAX_SIM),
    "TDS": suavizar_valor(ult["TDS"], 3.0, 400, 600)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nueva_medicion])], ignore_index=True).tail(50)

# =========================================================
# 3. SIDEBAR (LOGOS Y DESCARGAS)
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo, use_container_width=True)
    st.markdown("### Gestión de Datos")
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            st.session_state.db_simulada.to_excel(w, index=False, sheet_name='Monitoreo_RAS')
        st.download_button("Descargar Excel (.xlsx)", buf.getvalue(), "Reporte_RAS_UDCA.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
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

# --- PESTAÑA 1: MONITOREO ---
with tab1:
    # Fila de Gauges con Zonas Operativas
    def render_gauge(val, titulo, unidad, lims):
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=val,
            title={'text': f"<b>{titulo}</b>"}, number={'suffix': f" {unidad}"},
            gauge={
                'axis': {'range': [lims[0], lims[5]]},
                'bar': {'color': "#2d3436"},
                'steps': [
                    {'range': [lims[0], lims[1]], 'color': "#ff7675"}, # Crítico
                    {'range': [lims[1], lims[2]], 'color': "#ffeaa7"}, # Subóptimo
                    {'range': [lims[2], lims[3]], 'color': "#55efc4"}, # Óptimo
                    {'range': [lims[3], lims[4]], 'color': "#ffeaa7"}, # Subóptimo
                    {'range': [lims[4], lims[5]], 'color': "#ff7675"}  # Crítico
                ]
            }
        ))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
        return fig

    g1, g2, g3 = st.columns(3)
    with g1: st.plotly_chart(render_gauge(nueva_medicion["Temperatura"], "TEMP", "°C", RANGOS_TEMP), use_container_width=True)
    with g2: st.plotly_chart(render_gauge(nueva_medicion["pH"], "pH", "pts", RANGOS_PH), use_container_width=True)
    with g3: 
        fig_tds = go.Figure(go.Indicator(mode="gauge+number", value=nueva_medicion["TDS"], title={'text': "<b>TDS</b>"},
            gauge={'axis': {'range': [0, 1000]}, 'steps': [
                {'range': [0, TDS_ALERTA], 'color': "#55efc4"},
                {'range': [TDS_ALERTA, TDS_CRITICO], 'color': "#ffeaa7"},
                {'range': [TDS_CRITICO, 1000], 'color': "#ff7675"}]}))
        fig_tds.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_tds, use_container_width=True)

    # Gráficas de Tendencia
    st.markdown("### Tendencias Dinámicas")
    c1, c2 = st.columns(2)
    with c1:
        f_temp = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", markers=True, 
                         title="Temperatura Estable (20.1 - 21.0 °C)", color_discrete_sequence=["#d63031"], template="plotly_white")
        f_temp.update_yaxes(autorange=True)
        st.plotly_chart(f_temp, use_container_width=True)
    with c2:
        f_ph = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="pH", markers=True, 
                       title="Nivel de pH Estable (7.0 - 7.6)", color_discrete_sequence=["#00b894"], template="plotly_white")
        f_ph.update_yaxes(autorange=True)
        st.plotly_chart(f_ph, use_container_width=True)
    
    f_tds_area = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="TDS", markers=True,
                         title="Historial de Sólidos Disueltos (ppm)", color_discrete_sequence=["#0984e3"], template="plotly_white")
    st.plotly_chart(f_tds_area, use_container_width=True)

# --- PESTAÑA 2: ANÁLISIS CIENTÍFICO ---
with tab2:
    st.subheader("Distribución del Dataset Maestro")
    
    # Generación de Dataset Maestro Estático (Simulación de entrenamiento)
    np.random.seed(42)
    df_train = pd.DataFrame({
        'Temperatura': np.random.normal(20.5, 1.2, 1000),
        'pH': np.random.normal(7.3, 0.4, 1000),
        'TDS': np.random.normal(500, 30, 1000)
    })

    col_h, col_s = st.columns([0.65, 0.35])
    with col_h:
        f_heat = px.density_heatmap(df_train, x="Temperatura", y="pH", z="TDS", 
                                    histfunc="avg", nbinsx=30, nbinsy=30,
                                    color_continuous_scale="Viridis", template="plotly_white",
                                    title="Mapa de Densidad: Relación Temperatura vs pH (Histórico)")
        st.plotly_chart(f_heat, use_container_width=True)
    
    with col_s:
        st.markdown("**Resumen Estadístico del Dataset**")
        st.dataframe(df_train.describe().T, use_container_width=True)
        st.info("Este análisis demuestra la consistencia de los datos con los que el modelo fue calibrado originalmente.")
