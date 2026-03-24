import streamlit as st
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import os

# =========================================================
# 1. CONFIGURACIÓN DE PARÁMETROS (TESIS UDCA)
# =========================================================
T_OPT_MIN, T_OPT_MAX = 16.0, 20.0  
T_SUB_MIN, T_SUB_MAX = 11.0, 27.0  

PH_OPT_MIN, PH_OPT_MAX = 6.5, 8.5
PH_SUB_MIN, PH_SUB_MAX = 5.5, 9.5

TDS_MAX = 900
VALOR_DEFECTO_T = 18.0

# =========================================================
# 2. FUNCIONES DE SERVICIO (INICIALIZACIÓN)
# =========================================================
@st.cache_resource
def iniciar_servicios():
    # --- CONEXIÓN A FIREBASE (CON LIMPIEZA DE LLAVE) ---
    if not firebase_admin._apps:
        try:
            info = dict(st.secrets["firebase_key"])
            # Limpieza profunda para evitar errores JWT
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
            
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/' 
            })
        except Exception as e:
            st.error(f"❌ Error en Configuración de Firebase: {e}")
            st.stop()
    
    # --- CARGA DEL MODELO IA ---
    try:
        ruta_pkl = 'sistema_ras_completo.pkl'
        if not os.path.exists(ruta_pkl):
            st.error(f"❌ Archivo {ruta_pkl} no encontrado.")
            st.stop()
        p = joblib.load(ruta_pkl)
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except Exception as e:
        st.error(f"❌ Error al cargar modelo .pkl: {e}")
        st.stop()

def graficar_proyeccion(df, real_col, pred_col, min_opt, max_opt, min_sub, max_sub, titulo, color_linea):
    fig = go.Figure()
    # Zonas de confort térmico/químico
    fig.add_hrect(y0=min_opt, y1=max_opt, fillcolor="green", opacity=0.15, line_width=0)
    fig.add_hrect(y0=min_sub, y1=min_opt, fillcolor="yellow", opacity=0.08, line_width=0)
    fig.add_hrect(y0=max_opt, y1=max_sub, fillcolor="yellow", opacity=0.08, line_width=0)
    
    # Datos
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[real_col], name="Dato Real", line=dict(color=color_linea, width=4)))
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[pred_col], name="Predicción IA", line=dict(color='white', dash='dot', width=2)))
    
    fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10, r=10, t=50, b=10))
    return fig

# =========================================================
# 3. SEGURIDAD Y ESTADO DE SESIÓN
# =========================================================
st.set_page_config(page_title="RAS UDCA - Monitor IA", layout="wide", page_icon="🐟")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Control de Acceso - Tesis RAS")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "ras2026":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# =========================================================
# 4. PROCESAMIENTO DE DATOS EN TIEMPO REAL
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()

# Inicialización de variables para evitar NameError
t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0
tf, pf = VALOR_DEFECTO_T, 7.0 

st_autorefresh(interval=5000, key="global_refresh")

if 'hist' not in st.session_state:
    st.session_state.hist = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS_R"])

ahora = datetime.now()

# --- LECTURA DE FIREBASE ---
try:
    # Leemos la raíz para el diagnóstico en el sidebar
    data_total = rtdb.reference('/').get()
    
    # Diagnóstico en Sidebar
    st.sidebar.write("### 🔍 Datos en la Nube")
    st.sidebar.json(data_total) 

    # Buscar carpeta de sensores (ajusta 'sensor_data' si tu ESP32 usa otro nombre)
    data_firebase = data_total.get('sensor_data') if data_total else None

    if data_firebase:
        t_now = float(data_firebase.get('temp', VALOR_DEFECTO_T))
        p_now = float(data_firebase.get('ph', 7.0))
        tds_now = float(data_firebase.get('tds', 0.0))
        
        # --- CÁLCULO IA (XGBOOST) ---
        df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in df_in.columns: df_in[c] = 0
        df_in = df_in[cols_modelo]

        tf = t_now + float(mod_t.predict(df_in)[0])
        pf = p_now + float(mod_p.predict(df_in)[0])
        st.sidebar.success("✅ Conexión Activa")
    else:
        st.sidebar.warning("⚠️ Sin datos en '/sensor_data'")

except Exception as e:
    st.sidebar.error(f"❌ Error de lectura: {e}")

# --- ACTUALIZAR HISTORIAL ---
nuevo_pnt = pd.DataFrame({
    "Hora": [ahora.strftime("%H:%M:%S")], 
    "T_R": [t_now], "T_P": [tf], 
    "P_R": [p_now], "P_P": [pf], 
    "TDS_R": [tds_now]
})
st.session_state.hist = pd.concat([st.session_state.hist, nuevo_pnt], ignore_index=True).tail(30)

# =========================================================
# 5. INTERFAZ DE USUARIO (DASHBOARD)
# =========================================================
st.title("🌊 Sistema de Monitoreo Inteligente RAS")
st.markdown(f"**Ubicación:** Bogotá, Colombia (2640 msnm) | **Hora:** {ahora.strftime('%H:%M:%S')}")

# Métricas Principales
col1, col2, col3 = st.columns(3)
col1.metric("🌡️ Temperatura", f"{t_now:.1f} °C", delta=f"{tf-t_now:.2f} (IA)")
col2.metric("🧪 pH del Agua", f"{p_now:.2f}", delta=f"{pf-p_now:.2f} (IA)")
col3.metric("💧 TDS", f"{tds_now:.0f} ppm")

# Gráficas de Análisis
f1, f2 = st.columns(2)
with f1:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "T_R", "T_P", T_OPT_MIN, T_OPT_MAX, T_SUB_MIN, T_SUB_MAX, "Dinámica Térmica (°C)", "#00d4ff"), use_container_width=True)
with f2:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "P_R", "P_P", PH_OPT_MIN, PH_OPT_MAX, PH_SUB_MIN, PH_SUB_MAX, "Evolución de pH", "#ff00ff"), use_container_width=True)

# Gráfica de Sólidos (TDS)
fig_tds = go.Figure(go.Scatter(x=st.session_state.hist["Hora"], y=st.session_state.hist["TDS_R"], fill='tozeroy', line=dict(color='#00ff88'), name="TDS"))
fig_tds.add_hline(y=TDS_MAX, line_dash="dot", line_color="red", annotation_text="Límite Salinidad")
fig_tds.update_layout(template="plotly_dark", title="Sólidos Totales Disueltos (ppm)", height=300)
st.plotly_chart(fig_tds, use_container_width=True)

# Sidebar - Acciones Finales
st.sidebar.markdown("---")
csv_data = st.session_state.hist.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Descargar Datos de Ensayo", csv_data, f"reporte_ras_{ahora.strftime('%Y%m%d')}.csv", "text/csv")
