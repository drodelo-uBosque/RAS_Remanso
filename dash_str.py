import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import io
import os
import base64

# =========================================================
# 0. CONFIGURACIÓN Y ESTILO (CLEAN WHITE)
# =========================================================
ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')

try:
    favicon = Image.open(ruta_logo)
except:
    favicon = "🐟"

st.set_page_config(
    page_title="Sistema IoT RAS - Unidad Académica El Remanso UDCA",
    layout="wide",
    page_icon=favicon
)

# Inyección de CSS para fondo blanco y métricas elegantes
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eeeeee; }
    [data-testid="stSidebar"] { background-color: #f1f3f6; }
    .stButton>button { border-radius: 20px; }
    </style>
    """, unsafe_allow_html=True)

def get_base64_image(image_path):
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except: return None

# =========================================================
# 1. MOTOR DE SIMULACIÓN Y ESTADO DE SESIÓN
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

# Simulación de Histórico inicial si no existe
if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=5*i) for i in range(50, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Fecha_Hora": [t.strftime("%Y-%m-%d %H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(17.8, 19.2, 50),
        "pH": np.random.uniform(7.1, 7.6, 50),
        "TDS": np.random.uniform(480, 520, 50)
    })

# --- LOGIN REESTRUCTURADO ---
if not st.session_state.auth:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        img_b64 = get_base64_image("logo_1.png")
        if img_b64:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{img_b64}" width="180"></div>', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Acceso al Sistema</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Entrar", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.rerun()
                else: st.error("Error de acceso")
    st.stop()

# Auto-refresco (3 seg)
st_autorefresh(interval=3000, key="datarefresh")

# Generar nuevo dato simulado
ultimo = st.session_state.db_simulada.iloc[-1]
nuevo_row = {
    "Fecha_Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "Temperatura": np.clip(ultimo["Temperatura"] + np.random.uniform(-0.15, 0.15), 14, 25),
    "pH": np.clip(ultimo["pH"] + np.random.uniform(-0.03, 0.03), 6, 9),
    "TDS": np.clip(ultimo["TDS"] + np.random.uniform(-3, 3), 100, 800)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nuevo_row])], ignore_index=True).tail(60)

# =========================================================
# 2. SIDEBAR (CONTROLES Y DESCARGA)
# =========================================================
with st.sidebar:
    st.image("logo_1.png", use_container_width=True) if os.path.exists("logo_1.png") else st.title("UDCA RAS")
    st.markdown("### Gestión de Datos")
    
    # Exportar a Excel (XLSX)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.db_simulada.to_excel(writer, index=False, sheet_name='Monitoreo_RAS')
    
    st.download_button(
        label="📥 Descargar Reporte Excel",
        data=buffer.getvalue(),
        file_name=f"Reporte_RAS_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    st.markdown("---")
    if st.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()
    
    st.caption("Estado: Simulación Activa (Real-Time)")

# =========================================================
# 3. INTERFAZ PRINCIPAL (GAUGES Y GRÁFICAS)
# =========================================================
st.title("Panel de Control Biométrico - El Remanso")
st.markdown(f"**Ubicación:** Bogotá, Colombia (2640 msnm) | **Actualización:** {nuevo_row['Fecha_Hora']}")

def render_gauge(valor, titulo, unidad, min_v, max_v, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = valor,
        title = {'text': f"<b style='color:#555'>{titulo}</b>", 'font': {'size': 18}},
        number = {'suffix': f" {unidad}", 'font': {'color': '#333'}},
        gauge = {'axis': {'range': [min_v, max_v]}, 'bar': {'color': color},
                 'bgcolor': "#f1f1f1", 'borderwidth': 0}
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)')
    return fig

# Fila de Gauges
g1, g2, g3 = st.columns(3)
with g1: st.plotly_chart(render_gauge(nuevo_row["Temperatura"], "TEMPERATURA", "°C", 10, 30, "#ef4444"), use_container_width=True)
with g2: st.plotly_chart(render_gauge(nuevo_row["pH"], "pH", "pts", 0, 14, "#10b981"), use_container_width=True)
with g3: st.plotly_chart(render_gauge(nuevo_row["TDS"], "SOLIDOS TDS", "ppm", 0, 1000, "#3b82f6"), use_container_width=True)

# Fila de Gráficas de Tendencia
st.markdown("### Tendencias Recientes")
c_a, c_b = st.columns(2)

with c_a:
    fig_t = px.line(st.session_state.db_simulada, x="Fecha_Hora", y="Temperatura", 
                    title="Historial Térmico (°C)", template="plotly_white", color_discrete_sequence=["#ef4444"])
    st.plotly_chart(fig_t, use_container_width=True)

with c_b:
    fig_p = px.area(st.session_state.db_simulada, x="Fecha_Hora", y="pH", 
                    title="Fluctuación de pH", template="plotly_white", color_discrete_sequence=["#10b981"])
    st.plotly_chart(fig_p, use_container_width=True)

# =========================================================
# 4. ANALÍTICA: HEATMAP DE CORRELACIÓN
# =========================================================
st.markdown("---")
col_heat, col_desc = st.columns([0.6, 0.4])

with col_heat:
    st.subheader("Mapa de Calor: Correlación de Variables")
    corr = st.session_state.db_simulada[["Temperatura", "pH", "TDS"]].corr()
    fig_h = px.imshow(corr, text_auto=".2f", color_continuous_scale='Blues', template="plotly_white")
    st.plotly_chart(fig_h, use_container_width=True)

with col_desc:
    st.subheader("Resumen Estadístico")
    st.dataframe(st.session_state.db_simulada[["Temperatura", "pH", "TDS"]].describe().T, use_container_width=True)
    st.success("Variables dentro de rangos operativos óptimos para Tilapia Roja.")
