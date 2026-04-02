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
# 0. FUNCIONES DE APOYO (RECURSOS Y LOGOS)
# =========================================================
def get_base64_image(image_path):
    """Convierte imagen a Base64 para inyectar en HTML/CSS."""
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except: return None
    return None

# Definición de ruta global del logo
ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')

# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA (FAVICON Y PESTAÑA)
# =========================================================
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = "🐟"

st.set_page_config(
    page_title="Sistema RAS - El Remanso UDCA",
    layout="wide",
    page_icon=favicon, # <--- AQUÍ SE INTEGRA EL LOGO EN LA PESTAÑA
    initial_sidebar_state="expanded"
)

# Inyección de Estilo Visual (Clean White Design)
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eeeeee; }
    [data-testid="stSidebar"] { background-color: #f1f3f6; }
    .centered-logo { display: flex; justify-content: center; align-items: center; margin-bottom: 20px; }
    .centered-logo img { width: 180px; height: auto; border: none; box-shadow: none; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 2. SISTEMA DE AUTENTICACIÓN (LOGIN)
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        img_b64 = get_base64_image(ruta_logo)
        if img_b64:
            st.markdown(f'<div class="centered-logo"><img src="data:image/png;base64,{img_b64}"></div>', unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🐟</h1>", unsafe_allow_html=True)
            
        st.markdown("<h2 style='text-align: center; color: #333;'>Control de Acceso</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Plataforma IoT - Nodo El Remanso</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Ingresar al Dashboard", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 3. GENERACIÓN DE DATOS (SIMULACIÓN REAL-TIME)
# =========================================================
st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    # Histórico base de 60 puntos
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(60, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(18.0, 19.5, 60),
        "pH": np.random.uniform(7.2, 7.6, 60),
        "TDS": np.random.uniform(490, 510, 60)
    })

# Añadir nuevo punto simulado con variación suave
ultimo = st.session_state.db_simulada.iloc[-1]
nuevo_row = {
    "Fecha_Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": np.clip(ultimo["Temperatura"] + np.random.uniform(-0.1, 0.1), 14, 25),
    "pH": np.clip(ultimo["pH"] + np.random.uniform(-0.02, 0.02), 6, 9),
    "TDS": np.clip(ultimo["TDS"] + np.random.uniform(-2, 2), 0, 800)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nuevo_row])], ignore_index=True).tail(60)

# =========================================================
# 4. SIDEBAR (GESTIÓN Y DESCARGAS)
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo):
        st.image(ruta_logo, use_container_width=True)
    
    st.markdown("### Exportación de Datos")
    
    # Intento de exportación a Excel
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.db_simulada.to_excel(writer, index=False, sheet_name='Datos_RAS')
        
        st.download_button(
            label="📊 Descargar Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"Reporte_UDCA_{datetime.now().strftime('%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    except Exception:
        # Respaldo en CSV si falla openpyxl
        csv_data = st.session_state.db_simulada.to_csv(index=False).encode('utf-8')
        st.download_button("📝 Descargar CSV (Respaldo)", csv_data, "reporte_ras.csv", "text/csv", use_container_width=True)

    st.markdown("---")
    if st.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()
    st.caption("Estado: Conectado | Nodo: Bogotá")

# =========================================================
# 5. DASHBOARD PRINCIPAL (GAUGES Y GRÁFICAS)
# =========================================================
st.title("Monitoreo de Calidad de Agua - RAS El Remanso")
st.write(f"Registro Actual: {nuevo_row['Fecha_Hora']} | **Proyecto de Grado UDCA**")

# Funciones de visualización
def render_gauge(valor, titulo, unidad, min_v, max_v, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = valor,
        title = {'text': f"<span style='color:gray; font-size:16px'>{titulo}</span>"},
        number = {'suffix': f" {unidad}", 'font': {'color': '#333'}},
        gauge = {'axis': {'range': [min_v, max_v]}, 'bar': {'color': color}, 'bgcolor': "#f1f1f1"}
    ))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# Fila 1: Gauges de Variables Críticas
g1, g2, g3 = st.columns(3)
with g1: st.plotly_chart(render_gauge(nuevo_row["Temperatura"], "TEMPERATURA", "°C", 10, 30, "#ef4444"), use_container_width=True)
with g2: st.plotly_chart(render_gauge(nuevo_row["pH"], "pH", "pts", 0, 14, "#10b981"), use_container_width=True)
with g3: st.plotly_chart(render_gauge(nuevo_row["TDS"], "SÓLIDOS TDS", "ppm", 0, 1000, "#3b82f6"), use_container_width=True)

# Fila 2: Tendencias Dinámicas
st.markdown("### Comportamiento Histórico (Última Hora)")
c_a, c_b = st.columns(2)
with c_a:
    fig_t = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", 
                    template="plotly_white", color_discrete_sequence=["#ef4444"])
    fig_t.update_layout(title="Dinámica Térmica")
    st.plotly_chart(fig_t, use_container_width=True)
with c_b:
    fig_p = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="pH", 
                    template="plotly_white", color_discrete_sequence=["#10b981"])
    fig_p.update_layout(title="Variación de pH")
    st.plotly_chart(fig_p, use_container_width=True)

# Fila 3: Analítica Avanzada
st.markdown("---")
st.subheader("Análisis de Interdependencia")
col_h, col_s = st.columns([0.6, 0.4])

with col_h:
    corr = st.session_state.db_simulada[["Temperatura", "pH", "TDS"]].corr()
    fig_h = px.imshow(corr, text_auto=".2f", color_continuous_scale='Blues', template="plotly_white")
    st.plotly_chart(fig_h, use_container_width=True)

with col_s:
    st.markdown("**Resumen Estadístico Operativo**")
    st.dataframe(st.session_state.db_simulada[["Temperatura", "pH", "TDS"]].describe().T, use_container_width=True)
    st.info("El sistema valida la estabilidad de las variables cada 3 segundos mediante simulación estocástica.")
