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
# 1. CONFIGURACIÓN DE NIVELES Y UMBRALES (PROYECTO UDCA)
# =========================================================
T_OPT_MIN, T_OPT_MAX = 16.0, 20.0  
T_SUB_MIN, T_SUB_MAX = 11.0, 27.0  

PH_OPT_MIN, PH_OPT_MAX = 6.5, 8.5
PH_SUB_MIN, PH_SUB_MAX = 5.5, 9.5

TDS_MAX = 900
VALOR_DEFECTO_T = 18.0

# =========================================================
# 2. FUNCIONES DE APOYO (DEFINICIONES)
# =========================================================
@st.cache_resource
def iniciar_servicios():
    # --- CONEXIÓN A FIREBASE VÍA SECRETS ---
    if not firebase_admin._apps:
        try:
            # Extrae la configuración desde Streamlit Secrets
            firebase_creds = dict(st.secrets["firebase_key"]) 
            cred = credentials.Certificate(firebase_creds)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/' 
            })
        except Exception as e:
            st.error(f"❌ Error en Secrets de Firebase: {e}")
            st.stop()
    
    # --- CARGA DEL MODELO IA (.PKL) ---
    try:
        ruta_pkl = 'sistema_ras_completo.pkl'
        if not os.path.exists(ruta_pkl):
            st.error(f"❌ No se encontró el archivo {ruta_pkl} en el repositorio.")
            st.stop()
            
        p = joblib.load(ruta_pkl)
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except Exception as e:
        st.error(f"❌ Error al cargar el modelo IA: {e}")
        st.stop()

def graficar_proyeccion(df, real_col, pred_col, min_opt, max_opt, min_sub, max_sub, titulo, color_linea):
    fig = go.Figure()
    # Zonas de seguridad (Sombreado)
    fig.add_hrect(y0=min_opt, y1=max_opt, fillcolor="green", opacity=0.15, line_width=0)
    fig.add_hrect(y0=min_sub, y1=min_opt, fillcolor="yellow", opacity=0.08, line_width=0)
    fig.add_hrect(y0=max_opt, y1=max_sub, fillcolor="yellow", opacity=0.08, line_width=0)
    
    # Datos Reales e IA
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[real_col], name="Real", line=dict(color=color_linea, width=4)))
    fig.add_trace(go.Scatter(x=df["Hora"], y=df[pred_col], name="IA (XGBoost)", line=dict(color='white', dash='dot', width=2)))
    
    fig.update_layout(template="plotly_dark", title=titulo, height=350, margin=dict(l=10, r=10, t=50, b=10))
    return fig

# =========================================================
# 3. LOGIC DE ACCESO Y CONFIGURACIÓN
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
            st.error("Acceso denegado")
    st.stop()

# =========================================================
# 4. MOTOR DE DATOS EN TIEMPO REAL
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()

# Refresco cada 5 segundos
st_autorefresh(interval=5000, key="global_refresh")

if 'hist' not in st.session_state:
    st.session_state.hist = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS_R"])

# --- LECTURA DE FIREBASE (SIN CACHÉ) ---
ahora = datetime.now()
try:
    data_firebase = rtdb.reference('/sensor_data').get()

    # =========================================================
    # 🔍 PEGA EL BLOQUE DE DIAGNÓSTICO AQUÍ:
    # =========================================================
    st.sidebar.write("---")
    st.sidebar.subheader("DEBUG de Datos")
    st.sidebar.json(data_firebase) 
    # =========================================================
    
    if data_firebase:
        t_now = float(data_firebase.get('temp', VALOR_DEFECTO_T))
        p_now = float(data_firebase.get('ph', 7.0))
        tds_now = float(data_firebase.get('tds', 0.0))
    else:
        t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0
except:
    t_now, p_now, tds_now = VALOR_DEFECTO_T, 7.0, 0.0

# --- CÁLCULO IA ---
df_in = pd.DataFrame([[t_now, p_now, 1.0]], columns=['temperatura', 'ph', 'horas_transcurridas'])
for c in cols_modelo:
    if c not in df_in.columns: df_in[c] = 0
df_in = df_in[cols_modelo]

tf = t_now + float(mod_t.predict(df_in)[0])
pf = p_now + float(mod_p.predict(df_in)[0])

# --- ACTUALIZAR HISTORIAL ---
nuevo = pd.DataFrame({"Hora": [ahora.strftime("%H:%M:%S")], "T_R": [t_now], "T_P": [tf], "P_R": [p_now], "P_P": [pf], "TDS_R": [tds_now]})
st.session_state.hist = pd.concat([st.session_state.hist, nuevo], ignore_index=True).tail(30)

# =========================================================
# 5. RENDERIZADO VISUAL
# =========================================================
st.sidebar.image("https://www.udca.edu.co/wp-content/uploads/2021/05/logo-udca.png", use_container_width=True)

# Semáforo Sidebar
color_semaforo = "#28a745" if T_OPT_MIN <= t_now <= T_OPT_MAX else "#ffc107" if T_SUB_MIN <= t_now <= T_SUB_MAX else "#dc3545"
st.sidebar.markdown(f"""
    <div style="text-align: center; background: #1a1a1a; padding: 20px; border-radius: 15px; border: 2px solid {color_semaforo};">
        <p style="color: white; font-size: 14px;">ESTADO DEL AGUA</p>
        <div style="width: 60px; height: 60px; background: {color_semaforo}; border-radius: 50%; margin: 0 auto; box-shadow: 0 0 20px {color_semaforo};"></div>
    </div>
""", unsafe_allow_html=True)

st.title("🌊 Dashboard Inteligente RAS - UDCA")
st.write(f"Sincronizado con Firebase: **{ahora.strftime('%H:%M:%S')}**")

# Métricas
m1, m2, m3 = st.columns(3)
m1.metric("🌡️ TEMP", f"{t_now:.1f} °C", delta=f"{tf-t_now:.2f} (IA)")
m2.metric("🧪 pH", f"{p_now:.2f}", delta=f"{pf-p_now:.2f} (IA)")
m3.metric("💧 TDS", f"{tds_now:.0f} ppm")

# Gráficas Principales
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "T_R", "T_P", T_OPT_MIN, T_OPT_MAX, T_SUB_MIN, T_SUB_MAX, "Proyección Térmica", "#00d4ff"), use_container_width=True)
with col_b:
    st.plotly_chart(graficar_proyeccion(st.session_state.hist, "P_R", "P_P", PH_OPT_MIN, PH_OPT_MAX, PH_SUB_MIN, PH_SUB_MAX, "Proyección de pH", "#ff00ff"), use_container_width=True)

# Gráfica TDS
fig_tds = go.Figure(go.Scatter(x=st.session_state.hist["Hora"], y=st.session_state.hist["TDS_R"], fill='tozeroy', line=dict(color='#00ff88')))
fig_tds.add_hline(y=TDS_MAX, line_dash="dot", line_color="red", annotation_text="Límite")
fig_tds.update_layout(template="plotly_dark", title="Sólidos Totales Disueltos (TDS)", height=280)
st.plotly_chart(fig_tds, use_container_width=True)

# Botón descarga
csv = st.session_state.hist.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("📥 Descargar Reporte CSV", csv, "reporte_ras.csv", "text/csv")
