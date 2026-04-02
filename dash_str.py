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
# 0. CONFIGURACIÓN Y LOGOS
# =========================================================
ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = "🐟"

st.set_page_config(page_title="Plataforma IoT RAS - Unidad Académica El Remanso UDCA", layout="wide", page_icon=favicon)

# Estilos para fondo blanco
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eeeeee; }
    [data-testid="stSidebar"] { background-color: #f1f3f6; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 1. GESTIÓN DE SESIÓN Y SIMULACIÓN
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    # --- LOGIN REESTRUCTURADO ---
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        if os.path.exists(ruta_logo):
            st.image(ruta_logo, width=180)
        st.markdown("<h2 style='text-align: center;'>Acceso al Sistema</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Entrar", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.rerun()
                else: st.error("Credenciales incorrectas")
    st.stop()

# Auto-refresco cada 3 segundos
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(60, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(18.2, 19.8, 60),
        "pH": np.random.uniform(7.25, 7.55, 60),
        "TDS": np.random.uniform(495, 515, 60)
    })

# Generar nuevo punto
ultimo = st.session_state.db_simulada.iloc[-1]
nuevo_row = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": ultimo["Temperatura"] + np.random.uniform(-0.1, 0.1),
    "pH": ultimo["pH"] + np.random.uniform(-0.01, 0.01),
    "TDS": ultimo["TDS"] + np.random.uniform(-2, 2)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nuevo_row])], ignore_index=True).tail(60)

# =========================================================
# 2. SIDEBAR: LOGOS, DESCARGAS Y CIERRE
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo):
        st.image(ruta_logo, use_container_width=True)
    
    st.markdown("### Exportar Resultados")
    
    # Lógica de descarga Excel / CSV
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.db_simulada.to_excel(writer, index=False, sheet_name='Datos_RAS')
        
        st.download_button(
            label="Descargar Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"Reporte_RAS_{datetime.now().strftime('%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    except:
        csv_data = st.session_state.db_simulada.to_csv(index=False).encode('utf-8')
        st.download_button("📝 Descargar CSV", csv_data, "reporte_ras.csv", "text/csv", use_container_width=True)

    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# =========================================================
# 3. INTERFAZ PRINCIPAL: INDICADORES (GAUGES)
# =========================================================
st.title("Panel Biométrico RAS - El Remanso")
st.write(f"Registro Actual: **{nuevo_row['Fecha_Hora']}**")

def render_gauge(valor, titulo, unidad, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = valor,
        title = {'text': f"<b style='color:#555'>{titulo}</b>"},
        number = {'suffix': f" {unidad}"},
        gauge = {'bar': {'color': color}, 'bgcolor': "#f1f1f1"}
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
    return fig

g1, g2, g3 = st.columns(3)
with g1: st.plotly_chart(render_gauge(nuevo_row["Temperatura"], "TEMP", "°C", "#ef4444"), use_container_width=True)
with g2: st.plotly_chart(render_gauge(nuevo_row["pH"], "pH", "pts", "#10b981"), use_container_width=True)
with g3: st.plotly_chart(render_gauge(nuevo_row["TDS"], "TDS", "ppm", "#3b82f6"), use_container_width=True)

# =========================================================
# 4. GRÁFICAS DE TENDENCIA (LAYOUT SOLICITADO)
# =========================================================
st.markdown("###Tendencias de Calidad de Agua")

# Fila 1: Temperatura y pH (Lado a lado)
col_a, col_b = st.columns(2)
with col_a:
    fig_t = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", 
                    title="Historial de Temperatura", color_discrete_sequence=["#ef4444"], template="plotly_white")
    st.plotly_chart(fig_t, use_container_width=True)
with col_b:
    fig_p = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="pH", 
                    title="Historial de pH (Escala Adaptativa)", color_discrete_sequence=["#10b981"], template="plotly_white")
    fig_p.update_yaxes(autorange=True)
    st.plotly_chart(fig_p, use_container_width=True)

# Fila 2: TDS (Debajo, ancho completo)
fig_tds = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="TDS", 
                  title="Sólidos Totales Disueltos (Historial TDS)", color_discrete_sequence=["#3b82f6"], template="plotly_white")
st.plotly_chart(fig_tds, use_container_width=True)

# =========================================================
# 5. HEATMAP DEL DATASET DE ENTRENAMIENTO
# =========================================================
st.markdown("---")
st.subheader("Análisis Estadístico: Dataset de Entrenamiento")

# Simulamos el dataset de entrenamiento cargado (aquí podrías cargar tu .csv real)
# Si tienes el archivo, usa: df_entrenamiento = pd.read_csv('tu_archivo.csv')
np.random.seed(42)
df_train = pd.DataFrame({
    'Temperatura': np.random.normal(19, 1.5, 500),
    'pH': np.random.normal(7.4, 0.4, 500),
    'TDS': np.random.normal(500, 50, 500)
})

col_h1, col_h2 = st.columns([0.6, 0.4])
with col_h1:
    # Heatmap de Densidad del histórico de entrenamiento
    fig_heat_train = px.density_heatmap(
        df_train, x="Temperatura", y="pH", z="TDS",
        title="Relación Temperatura vs pH (Dataset de Entrenamiento)",
        color_continuous_scale="Viridis", template="plotly_white",
        labels={'x':'Temperatura (°C)', 'y':'pH'}
    )
    st.plotly_chart(fig_heat_train, use_container_width=True)

with col_h2:
    st.info("**Análisis del Dataset:**")
    st.markdown("""
    Este mapa de calor representa la distribución de los datos utilizados para entrenar el modelo de IA. 
    
    * **Zonas Amarillas:** Indican la mayor concentración de muestras.
    * **Rango Crítico:** El modelo se especializa en el comportamiento del RAS entre 17°C y 21°C.
    """)
    st.dataframe(df_train.describe().T, use_container_width=True)
