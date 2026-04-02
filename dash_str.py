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
# 0. CONFIGURACIÓN TÉCNICA (LÍMITES UDCA)
# =========================================================
# Rangos: [Min_Critico, Min_Suboptimo, Optimo_Min, Optimo_Max, Max_Suboptimo, Max_Critico]
RANGOS_TEMP = [10.0, 14.0, 17.0, 21.0, 24.0, 30.0]
RANGOS_PH = [4.0, 6.0, 6.8, 8.2, 9.0, 11.0]
TDS_UMBRAL_ALERTA = 600
TDS_MAX = 800

ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = None

st.set_page_config(page_title="Plataforma IoT RAS Unidad Académica El Remanso - UDCA", layout="wide", page_icon=favicon)

# CSS para Interfaz Limpia y Profesional
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

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
                else: st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 2. MOTOR DE SIMULACIÓN ESTABILIZADO (MEDIA MÓVIL)
# =========================================================
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(50, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(18.5, 19.5, 50),
        "pH": np.random.uniform(7.3, 7.5, 50),
        "TDS": np.random.uniform(490, 510, 50)
    })

# Generación estabilizada: El nuevo valor es un promedio ponderado del anterior
def generar_valor_estable(actual, variacion, min_val, max_val):
    ruido = np.random.uniform(-variacion, variacion)
    nuevo = (actual * 0.8) + ((actual + ruido) * 0.2) # Filtro de suavizado
    return np.clip(nuevo, min_val, max_val)

ult = st.session_state.db_simulada.iloc[-1]
nueva_fila = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": generar_valor_estable(ult["Temperatura"], 0.3, 10, 30),
    "pH": generar_valor_estable(ult["pH"], 0.05, 0, 14),
    "TDS": generar_valor_estable(ult["TDS"], 5.0, 0, 1000)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nueva_fila])], ignore_index=True).tail(50)

# =========================================================
# 3. SIDEBAR Y EXPORTACIÓN
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo, use_container_width=True)
    st.markdown("### Exportar Datos Historicos")
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            st.session_state.db_simulada.to_excel(w, index=False, sheet_name='Data_RAS')
        st.download_button("Descargar Reporte Excel", buf.getvalue(), "Reporte_RAS.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except:
        st.download_button("Descargar Reporte CSV", st.session_state.db_simulada.to_csv(index=False).encode('utf-8'), "Reporte_RAS.csv", "text/csv", use_container_width=True)
    
    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# =========================================================
# 4. GAUGES CON ZONAS SUBÓPTIMAS
# =========================================================
st.title("Monitoreo en tiempo real - Unidad El Remanso")

def render_gauge_tri(valor, titulo, unidad, limites):
    # limites: [Crit_Min, Sub_Min, Opt_Min, Opt_Max, Sub_Max, Crit_Max]
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = valor,
        title = {'text': f"<b>{titulo}</b>", 'font': {'size': 18}},
        number = {'suffix': f" {unidad}"},
        gauge = {
            'axis': {'range': [limites[0], limites[5]]},
            'bar': {'color': "#2d3436"},
            'steps': [
                {'range': [limites[0], limites[1]], 'color': "#ff6b6b"}, # Crítico Bajo
                {'range': [limites[1], limites[2]], 'color': "#feca57"}, # Subóptimo Bajo
                {'range': [limites[2], limites[3]], 'color': "#1dd1a1"}, # Óptimo
                {'range': [limites[3], limites[4]], 'color': "#feca57"}, # Subóptimo Alto
                {'range': [limites[4], limites[5]], 'color': "#ff6b6b"}  # Crítico Alto
            ]
        }
    ))
    fig.update_layout(height=220, margin=dict(l=25, r=25, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
    return fig

g1, g2, g3 = st.columns(3)
with g1: st.plotly_chart(render_gauge_tri(nueva_fila["Temperatura"], "TEMPERATURA", "°C", RANGOS_TEMP), use_container_width=True)
with g2: st.plotly_chart(render_gauge_tri(nueva_fila["pH"], "NIVEL pH", "pts", RANGOS_PH), use_container_width=True)
with g3: 
    # Gauge TDS (Binario: Estable / Crítico)
    fig_tds_g = go.Figure(go.Indicator(
        mode = "gauge+number", value = nueva_fila["TDS"],
        title = {'text': "<b>SÓLIDOS TDS</b>"},
        gauge = {
            'axis': {'range': [0, 1000]},
            'steps': [
                {'range': [0, TDS_UMBRAL_ALERTA], 'color': "#1dd1a1"},
                {'range': [TDS_UMBRAL_ALERTA, TDS_MAX], 'color': "#feca57"},
                {'range': [TDS_MAX, 1000], 'color': "#ff6b6b"}
            ]
        }
    ))
    fig_tds_g.update_layout(height=220, margin=dict(l=25, r=25, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_tds_g, use_container_width=True)

# =========================================================
# 5. GRÁFICAS DE TENDENCIA (LÍNEAS + MARCADORES)
# =========================================================
st.markdown("### Historial de Variables en Tiempo Real")
c_a, c_b = st.columns(2)

with c_a:
    f_temp = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", 
                     markers=True, title="Tendencia Térmica", color_discrete_sequence=["#ff6b6b"], template="plotly_white")
    f_temp.update_yaxes(autorange=True)
    st.plotly_chart(f_temp, use_container_width=True)

with c_b:
    f_ph = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="pH", 
                   markers=True, title="Tendencia pH", color_discrete_sequence=["#1dd1a1"], template="plotly_white")
    f_ph.update_yaxes(autorange=True)
    st.plotly_chart(f_ph, use_container_width=True)

# TDS Ancho Completo
f_tds = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="TDS", 
                markers=True, title="Historial de Sólidos (TDS ppm)", color_discrete_sequence=["#48dbfb"], template="plotly_white")
st.plotly_chart(f_tds, use_container_width=True)

# =========================================================
# 6. HEATMAP DATASET ENTRENAMIENTO
# =========================================================
st.markdown("---")
st.subheader("Análisis Científico: Distribución del Dataset de Entrenamiento")

# Simulación de carga de dataset maestro
df_train = pd.DataFrame({
    'Temperatura': np.random.normal(RANGOS_TEMP[2]+1, 2, 1000),
    'pH': np.random.normal(RANGOS_PH[2]+0.5, 0.6, 1000)
})

f_heat = px.density_heatmap(df_train, x="Temperatura", y="pH", 
                            color_continuous_scale="Viridis", template="plotly_white",
                            labels={'Temperatura':'Temperatura (°C)', 'pH':'pH'},
                            title="Mapa de Calor: Concentración de Datos Históricos")
st.plotly_chart(f_heat, use_container_width=True)
