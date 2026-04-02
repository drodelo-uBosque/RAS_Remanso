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
# 0. CONFIGURACIÓN TÉCNICA Y LOGOS
# =========================================================
TEMP_MIN, TEMP_MAX = 14.0, 22.0
PH_MIN, PH_MAX = 6.5, 8.5
TDS_LIMITE = 800

ruta_logo = os.path.join(os.path.dirname(__file__), 'logo_1.png')
try:
    favicon = Image.open(ruta_logo)
except:
    favicon = "🐟"

st.set_page_config(page_title="Sistema RAS - UDCA", layout="wide", page_icon=favicon)

# Estilo para fondo blanco
st.markdown("<style>.main { background-color: #ffffff; } [data-testid='stSidebar'] { background-color: #f1f3f6; }</style>", unsafe_allow_html=True)

# =========================================================
# 1. GESTIÓN DE SESIÓN Y DATOS
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
            if st.button("Entrar", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.rerun()
                else: st.error("Credenciales incorrectas")
    st.stop()

st_autorefresh(interval=3000, key="datarefresh")

if 'db_simulada' not in st.session_state:
    ahora = datetime.now()
    tiempos = [ahora - timedelta(minutes=2*i) for i in range(40, 0, -1)]
    st.session_state.db_simulada = pd.DataFrame({
        "Hora": [t.strftime("%H:%M:%S") for t in tiempos],
        "Temperatura": np.random.uniform(18.5, 19.5, 40),
        "pH": np.random.uniform(7.3, 7.5, 40),
        "TDS": np.random.uniform(480, 520, 40)
    })

# Simulación con ruido visual (puntos que se mueven)
ultimo = st.session_state.db_simulada.iloc[-1]
nuevo_row = {
    "Hora": datetime.now().strftime("%H:%M:%S"),
    "Temperatura": ultimo["Temperatura"] + np.random.uniform(-0.15, 0.15),
    "pH": ultimo["pH"] + np.random.uniform(-0.02, 0.02),
    "TDS": ultimo["TDS"] + np.random.uniform(-4, 4)
}
st.session_state.db_simulada = pd.concat([st.session_state.db_simulada, pd.DataFrame([nuevo_row])], ignore_index=True).tail(40)

# =========================================================
# 2. SIDEBAR (DESCARGAS)
# =========================================================
with st.sidebar:
    if os.path.exists(ruta_logo): st.image(ruta_logo, use_container_width=True)
    st.markdown("### Exportar Datos")
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.db_simulada.to_excel(writer, index=False, sheet_name='RAS_Data')
        st.download_button("📥 Descargar Excel", buffer.getvalue(), f"RAS_{datetime.now().strftime('%H%M')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except:
        st.download_button("📝 Descargar CSV", st.session_state.db_simulada.to_csv(index=False).encode('utf-8'), "datos.csv", "text/csv", use_container_width=True)
    
    if st.button("🔴 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# =========================================================
# 3. GAUGES CON ZONAS OPERATIVAS
# =========================================================
st.title("Panel de Control RAS - UDCA")

def render_gauge(valor, titulo, unidad, min_v, max_v, opt_min, opt_max):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = valor,
        title = {'text': f"<b>{titulo}</b>", 'font': {'size': 18}},
        number = {'suffix': f" {unidad}", 'font': {'color': '#333'}},
        gauge = {
            'axis': {'range': [min_v, max_v]},
            'bar': {'color': "#333"},
            'steps': [
                {'range': [min_v, opt_min], 'color': "#fee2e2"}, # Rojo suave (Bajo)
                {'range': [opt_min, opt_max], 'color': "#dcfce7"}, # Verde (Óptimo)
                {'range': [opt_max, max_v], 'color': "#fee2e2"}  # Rojo suave (Alto)
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75, 'value': valor
            }
        }
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
    return fig

g1, g2, g3 = st.columns(3)
with g1: st.plotly_chart(render_gauge(nuevo_row["Temperatura"], "TEMP", "°C", 10, 30, TEMP_MIN, TEMP_MAX), use_container_width=True)
with g2: st.plotly_chart(render_gauge(nuevo_row["pH"], "pH", "pts", 0, 14, PH_MIN, PH_MAX), use_container_width=True)
with g3: st.plotly_chart(render_gauge(nuevo_row["TDS"], "TDS", "ppm", 0, 1000, 0, TDS_LIMITE), use_container_width=True)

# =========================================================
# 4. GRÁFICAS (LÍNEAS + PUNTOS)
# =========================================================
st.markdown("### 📈 Monitoreo en Tiempo Real")
c1, c2 = st.columns(2)

with c1:
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=st.session_state.db_simulada["Hora"], y=st.session_state.db_simulada["Temperatura"],
                               mode='lines+markers', line=dict(color='#ef4444', width=2), marker=dict(size=6), name="Temp"))
    fig_t.update_layout(title="Variación Térmica (°C)", template="plotly_white", yaxis=dict(autorange=True))
    st.plotly_chart(fig_t, use_container_width=True)

with c2:
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=st.session_state.db_simulada["Hora"], y=st.session_state.db_simulada["pH"],
                               mode='lines+markers', line=dict(color='#10b981', width=2), marker=dict(size=6), name="pH"))
    fig_p.update_layout(title="Fluctuación de pH", template="plotly_white", yaxis=dict(autorange=True))
    st.plotly_chart(fig_p, use_container_width=True)

# TDS de ancho completo abajo
fig_tds = go.Figure()
fig_tds.add_trace(go.Scatter(x=st.session_state.db_simulada["Hora"], y=st.session_state.db_simulada["TDS"],
                             fill='tozeroy', mode='lines+markers', line=dict(color='#3b82f6'), name="TDS"))
fig_tds.update_layout(title="Historial de Sólidos Disueltos (TDS ppm)", template="plotly_white", height=300)
st.plotly_chart(fig_tds, use_container_width=True)

# =========================================================
# 5. HEATMAP DEL DATASET DE ENTRENAMIENTO
# =========================================================
st.markdown("---")
st.subheader("🔥 Análisis Científico: Dataset de Entrenamiento")

# Simulación de dataset histórico para el heatmap
np.random.seed(42)
df_train = pd.DataFrame({
    'Temp': np.random.normal(18.5, 2, 800),
    'pH': np.random.normal(7.4, 0.5, 800)
})

fig_h = px.density_heatmap(df_train, x="Temp", y="pH", nbinsx=30, nbinsy=30, 
                           color_continuous_scale="Viridis", title="Mapa de Densidad: Relación Temp vs pH Histórica",
                           labels={'Temp':'Temperatura (°C)', 'pH':'Nivel pH'}, template="plotly_white")
st.plotly_chart(fig_h, use_container_width=True)
