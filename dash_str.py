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
import base64

# =========================================================
# 0. CONFIGURACIÓN INICIAL
# =========================================================
ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')

try:
    favicon = Image.open(ruta_logo)
except:
    favicon = "🐟"

st.set_page_config(
    page_title="Sistema RAS - UDCA",
    layout="wide",
    page_icon=favicon
)

# Estilos CSS para fondo blanco y limpieza visual
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eeeeee; }
    [data-testid="stSidebar"] { background-color: #f1f3f6; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 1. AUTENTICACIÓN Y DATOS
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    # (Bloque de Login omitido por brevedad, usa el anterior que ya funcionaba)
    st.session_state.auth = True # Bypass temporal para prueba
    st.rerun()

st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(60, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(18.2, 19.8, 60),
        "pH": np.random.uniform(7.25, 7.55, 60),
        "TDS": np.random.uniform(495, 515, 60)
    })

# Simulación con "ruido" natural
ultimo = st.session_state.db_simulada.iloc[-1]
nuevo_row = {
    "Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": ultimo["Temperatura"] + np.random.uniform(-0.12, 0.12),
    "pH": ultimo["pH"] + np.random.uniform(-0.015, 0.015),
    "TDS": ultimo["TDS"] + np.random.uniform(-1.5, 1.5)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nuevo_row])], ignore_index=True).tail(60)

# =========================================================
# 2. DASHBOARD PRINCIPAL
# =========================================================
st.title("Panel Biométrico de Alta Precisión - El Remanso")
st.write(f"Registro en tiempo real: **{nuevo_row['Hora']}**")

# --- GAUGES ---
g1, g2, g3 = st.columns(3)
with g1: 
    fig = go.Figure(go.Indicator(mode="gauge+number", value=nuevo_row["Temperatura"], title={'text': "TEMP °C"}, gauge={'bar':{'color':"#ef4444"}}))
    fig.update_layout(height=200, margin=dict(t=30, b=0), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
with g2:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=nuevo_row["pH"], title={'text': "pH"}, gauge={'bar':{'color':"#10b981"}}))
    fig.update_layout(height=200, margin=dict(t=30, b=0), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
with g3:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=nuevo_row["TDS"], title={'text': "TDS ppm"}, gauge={'bar':{'color':"#3b82f6"}}))
    fig.update_layout(height=200, margin=dict(t=30, b=0), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# --- TENDENCIAS (AJUSTE DE pH Y TDS) ---
st.markdown("### Análisis de Tendencias Temporales")
c_a, c_b, c_c = st.columns(3)

with c_a:
    fig_t = px.line(st.session_state.db_simulada, x="Hora", y="Temperatura", title="Variación Térmica", color_discrete_sequence=["#ef4444"], template="plotly_white")
    st.plotly_chart(fig_t, use_container_width=True)

with c_b:
    # Solución al pH: Quitamos el rango fijo de 0-14 para ver la fluctuación real
    fig_p = px.line(st.session_state.db_simulada, x="Hora", y="pH", title="Fluctuación de pH (Escala Dinámica)", color_discrete_sequence=["#10b981"], template="plotly_white")
    fig_p.update_yaxes(autorange=True) # <--- Zoom automático
    st.plotly_chart(fig_p, use_container_width=True)

with c_c:
    # Solución a TDS: Gráfica de área para Sólidos
    fig_tds = px.area(st.session_state.db_simulada, x="Hora", y="TDS", title="Sólidos Disueltos (TDS)", color_discrete_sequence=["#3b82f6"], template="plotly_white")
    st.plotly_chart(fig_tds, use_container_width=True)

# --- HEATMAP EVOLUTIVO (NO MATRIZ) ---
st.markdown("---")
st.subheader("Mapa de Densidad de Datos (Heatmap Temporal)")
col_h, col_d = st.columns([0.7, 0.3])

with col_h:
    # Creamos un Heatmap de densidad: Tiempo vs Temperatura con intensidad de pH
    # Esto muestra "zonas calientes" de estabilidad en el sistema
    fig_heat = px.density_heatmap(
        st.session_state.db_simulada, 
        x="Hora", 
        y="Temperatura", 
        z="pH", 
        histfunc="avg",
        nbinsx=20,
        color_continuous_scale="Viridis",
        template="plotly_white",
        title="Distribución Térmica vs Intensidad de pH"
    )
    st.plotly_chart(fig_heat, use_container_width=True)

with col_d:
    st.info("**Nota Técnica:**")
    st.write("A diferencia de una matriz, este heatmap muestra la **concentración de valores**. Las zonas amarillas indican periodos donde el pH y la Temperatura se mantuvieron en equilibrio constante.")
    st.dataframe(st.session_state.db_simulada.describe().T, use_container_width=True)

# --- SIDEBAR (LOGOS Y CIERRE) ---
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo)
    if st.button("🔴 Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()
