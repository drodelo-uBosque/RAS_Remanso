import streamlit as st
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. CONFIGURACIÓN DE NIVELES Y UMBRALES
# =========================================================
# Rangos Temperatura (Tus valores exactos)
T_OPT_MIN, T_OPT_MAX = 16.0, 20.0  
T_SUB_MIN, T_SUB_MAX = 11.0, 27.0  

# Rangos pH (Estándar sugerido)
PH_OPT_MIN, PH_OPT_MAX = 6.5, 8.5
PH_SUB_MIN, PH_SUB_MAX = 5.5, 9.5

TDS_MAX = 900
VALOR_DEFECTO_T = 18.0

# =========================================================
# 2. FUNCIONES DE APOYO (DEFINICIONES)
# =========================================================
@st.cache_resource
def iniciar_servicios():
    ruta_json = "llave_firebase.json"
    ruta_pkl = "sistema_ras_completo.pkl"
    
    # 1. Verificación de archivos físicos en el servidor
    import os
    if not os.path.exists(ruta_json) or not os.path.exists(ruta_pkl):
        st.error(f"⚠️ Error: Faltan archivos en el repositorio. Asegúrate de subir {ruta_json} y {ruta_pkl}")
        st.stop()

    # 2. Inicializar Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(ruta_json)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/'
        })
    
    # 3. Carga segura del modelo
    try:
        # Cargamos el archivo completo
        data_pkl = joblib.load(ruta_pkl)
        
        # Verificamos si es un diccionario y qué contiene
        if isinstance(data_pkl, dict):
            m_temp = data_pkl.get('modelo_temp')
            m_ph = data_pkl.get('modelo_ph')
            columnas = data_pkl.get('columnas')
            
            # Si alguna llave falta, lanzamos error descriptivo
            if m_temp is None or m_ph is None or columnas is None:
                st.error(f"❌ El archivo .pkl tiene llaves incorrectas. Encontradas: {list(data_pkl.keys())}")
                st.stop()
                
            return m_temp, m_ph, columnas
        else:
            st.error("❌ El archivo .pkl no es un diccionario. Revisa cómo lo guardaste en Python.")
            st.stop()

    except Exception as e:
        st.error(f"❌ Error crítico al leer el modelo: {e}")
        st.stop()
def graficar_proyeccion(df, real_col, pred_col, min_opt, max_opt, min_sub, max_sub, titulo, color_linea):
    """Genera gráficas dinámicas con zonas de seguridad y predicción IA."""
    fig = go.Figure()
    # Zonas de fondo (Sombreado térmico/químico)
    fig.add_hrect(y0=min_opt, y1=max_opt, fillcolor="green", opacity=0.15, line_width=0, annotation_text="Óptimo")
    fig.add_hrect(y0=min_sub, y1=min_opt, fillcolor="yellow", opacity=0.08, line_width=0)
    fig.add_hrect(y0=max_opt, y1=max_sub, fillcolor="yellow", opacity=0.08, line_width=0)
    
    # Líneas de datos
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[real_col], name="Dato Real", line=dict(color=color_linea, width=4)))
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[pred_col], name="IA (XGBoost)", line=dict(color='white', dash='dot', width=2)))
    
    fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10, r=10, t=50, b=10), showlegend=True)
    return fig

# =========================================================
# 3. CONFIGURACIÓN DE PÁGINA Y LOGIN
# =========================================================
st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide", page_icon="🐟")

# Persistencia de autenticación
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Control de Acceso - Proyecto de Grado")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar al Dashboard"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 4. PROCESAMIENTO DE DATOS EN TIEMPO REAL (SIN CACHÉ)
# =========================================================
# Iniciar servicios básicos
mod_t, mod_p, cols_modelo = iniciar_servicios()

# Refresco automático cada 5 segundos
st_autorefresh(interval=5000, key="data_refresh_timer")

# Inicializar historial en sesión si no existe
if 'hist' not in st.session_state:
    st.session_state.hist = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS_R"])

# --- LECTURA DE FIREBASE ---
ahora = datetime.now()
try:
    # IMPORTANTE: La lectura .get() se hace fuera de funciones cache para que cambie el valor
    raw_data = rtdb.reference('/sensor_data').get()
    if raw_data:
        t_now = float(raw_data.get('temp', VALOR_DEFECTO_T))
        p_now = float(raw_data.get('ph', 7.0))
        tds_now = float(raw_data.get('tds', 0.0))
    else:
        t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0
except Exception as e:
    t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0
    st.error(f"Error de conexión: {e}")

# --- PROYECCIÓN IA (XGBOOST) ---
sensibilidad = st.sidebar.slider("Sensibilidad de Predicción", 0.1, 2.0, 1.0)
df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
for c in cols_modelo:
    if c not in df_in.columns: df_in[c] = 0
df_in = df_in[cols_modelo]

# Predicciones
tf = t_now + (float(mod_t.predict(df_in)[0]) * sensibilidad)
pf = p_now + (float(mod_p.predict(df_in)[0]) * sensibilidad)

# --- ACTUALIZAR HISTORIAL ---
nuevo_punto = pd.DataFrame({
    "Hora": [ahora.strftime("%H:%M:%S")],
    "T_R": [t_now], "T_P": [tf], 
    "P_R": [p_now], "P_P": [pf], 
    "TDS_R": [tds_now]
})
st.session_state.hist = pd.concat([st.session_state.hist, nuevo_punto], ignore_index=True).tail(30)

# =========================================================
# 5. INTERFAZ GRÁFICA (SIDEBAR Y MAIN)
# =========================================================
# Sidebar
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)
st.sidebar.markdown("---")

# Semáforo de Riesgo (Basado en tus rangos de 16-20°C)
if T_OPT_MIN <= t_now <= T_OPT_MAX:
    color_sem, msg_sem = "#28a745", "🟢 ÓPTIMO"
elif T_SUB_MIN <= t_now <= T_SUB_MAX:
    color_sem, msg_sem = "#ffc107", "🟡 SUBÓPTIMO"
else:
    color_sem, msg_sem = "#dc3545", "🔴 CRÍTICO"

st.sidebar.markdown(f"""
    <div style="text-align: center; background: #121212; padding: 15px; border-radius: 15px; border: 2px solid {color_sem};">
        <p style="color: white; font-size: 12px; margin-bottom: 5px;">ESTADO TÉRMICO</p>
        <div style="width: 50px; height: 50px; background: {color_sem}; border-radius: 50%; margin: 0 auto; box-shadow: 0 0 15px {color_sem};"></div>
        <h4 style="color: {color_sem}; margin-top: 10px;">{msg_sem}</h4>
    </div>
""", unsafe_allow_html=True)

# Botón de Descarga
st.sidebar.markdown("---")
csv_data = st.session_state.hist.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Descargar Historial CSV", csv_data, f"ras_report_{ahora.strftime('%Y%m%d')}.csv", "text/csv")

# Main Dashboard
st.title("🌊 Monitoreo RAS Inteligente - UDCA")
st.markdown(f"**Sincronización:** {ahora.strftime('%d/%m/%Y %H:%M:%S')}")

# Métricas
col1, col2, col3 = st.columns(3)
col1.metric("🌡️ Temperatura", f"{t_now:.1f} °C", delta=f"{tf-t_now:.2f} (Pred.)")
col2.metric("🧪 pH Agua", f"{p_now:.2f}", delta=f"{pf-p_now:.2f} (Pred.)")
col3.metric("💧 TDS", f"{tds_now:.0f} ppm")

# Gráficas
fila1_c1, fila1_c2 = st.columns(2)
with fila1_c1:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "T_R", "T_P", T_OPT_MIN, T_OPT_MAX, T_SUB_MIN, T_SUB_MAX, "Análisis de Temperatura (°C)", "#00d4ff"), use_container_width=True)

with fila1_c2:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "P_R", "P_P", PH_OPT_MIN, PH_OPT_MAX, PH_SUB_MIN, PH_SUB_MAX, "Proyección de pH", "#ff00ff"), use_container_width=True)

# Gráfica TDS (Área)
st.markdown("---")
fig_tds = go.Figure(go.Scatter(x=st.session_state.hist["Hora"], y=st.session_state.hist["TDS_R"], fill='tozeroy', line=dict(color='#00ff88'), name="TDS Real"))
fig_tds.add_hline(y=TDS_MAX, line_dash="dot", line_color="red", annotation_text="Límite Salinidad")
fig_tds.update_layout(template="plotly_dark", title="Sólidos Totales Disueltos (TDS - ppm)", height=280)
st.plotly_chart(fig_tds, use_container_width=True)
