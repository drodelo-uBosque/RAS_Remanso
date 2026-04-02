import streamlit as st
import pandas as pd
import numpy as np
import joblib
import firebase_admin
from firebase_admin import credentials, db as rtdb
from datetime import datetime, timedelta
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from sklearn.metrics import mean_absolute_error, mean_squared_error
from PIL import Image
import os
import base64

# =========================================================
# 0. FUNCIONES GLOBALES (DEFINIDAS AL INICIO)
# =========================================================
def get_base64_image(image_path):
    """Convierte imagen a Base64 para inyección HTML."""
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None
    return None

# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA Y FAVICON
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

# --- PARÁMETROS TÉCNICOS ---
TEMP_MIN, TEMP_MAX = 14.0, 22.0
PH_MIN, PH_MAX = 6.5, 8.5
TDS_LIMITE = 800

@st.cache_resource
def iniciar_servicios():
    if not firebase_admin._apps:
        try:
            info = dict(st.secrets["firebase_key"])
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred, {'databaseURL': 'https://ras-udca-default-rtdb.firebaseio.com/'})
        except Exception as e:
            st.error(f"Error Firebase: {e}"); st.stop()
    try:
        p = joblib.load('sistema_ras_completo.pkl')
        return p['modelo_temp'], p['modelo_ph'], p['columnas']
    except:
        st.error("Error al cargar modelos IA (.pkl)"); st.stop()

# =========================================================
# 2. SISTEMA DE LOGIN (LOGO INTEGRADO AL FONDO)
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    # --- ESTILO CSS (SIN BORDES NI SOMBRAS PARA INTEGRACIÓN TOTAL) ---
    st.markdown(
        """
        <style>
        .centered-logo {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 25px;
            margin-top: -20px;
            background-color: transparent;
        }
        .centered-logo img {
            width: 180px; 
            height: auto;
            border: none;
            border-radius: 0;
            box-shadow: none;
            /* mix-blend-mode: multiply; */ /* Opcional: para fundir blancos si el fondo no es exacto */
        }
        .login-header h2 {
            margin-top: 0;
            padding-top: 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    _, col_login, _ = st.columns([1, 1.5, 1])
    
    with col_login:
        img_b64 = get_base64_image(ruta_logo)
        
        if img_b64:
            st.markdown(
                f'<div class="centered-logo"><img src="data:image/png;base64,{img_b64}"></div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown("<h1 style='text-align: center;'>🐟</h1>", unsafe_allow_html=True)
            
        st.markdown("<div class='login-header'><h2 style='text-align: center;'>Inicio de Sesión</h2><p style='text-align: center; color: gray;'>Plataforma IoT - RAS El Remanso (UDCA)</p></div>", unsafe_allow_html=True)
        
        with st.container(border=True):
            u = st.text_input("USUARIO", placeholder="Ej: admin")
            p = st.text_input("CONTRASEÑA", type="password")
            
            if st.button("Ingresar a la plataforma", use_container_width=True):
                if u == "admin" and p == "ras_2026":
                    st.session_state.auth = True
                    st.success("Acceso concedido")
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
                    
    st.stop()

# =========================================================
# 3. CARGA DE DATOS Y SIDEBAR TÉCNICO
# =========================================================
mod_t, mod_p, cols_modelo = iniciar_servicios()
st_autorefresh(interval=5000, key="global_refresh")

try:
    st.sidebar.image(ruta_logo, use_container_width=True)
except:
    pass

st.sidebar.title("Configuración IA")

jornada_hrs = st.sidebar.select_slider("Horizonte de Predicción (Hrs):", options=[1, 4, 8, 12, 24], value=1)
ajuste_sensibilidad = st.sidebar.slider("Calibración IA (Offset)", -5.0, 5.0, 0.0, 0.1)

if 'historial' not in st.session_state:
    st.session_state.historial = pd.DataFrame(columns=["Hora", "T_R", "T_P", "P_R", "P_P", "TDS", "Error_Banda"])

if len(st.session_state.historial) > 5:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Rendimiento del Modelo")
    y_true = st.session_state.historial["T_R"].values.astype(float)
    y_pred = st.session_state.historial["T_P"].values.astype(float)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    st.sidebar.metric("MAE (Error Medio)", f"{mae:.3f} °C")
    st.sidebar.metric("RMSE", f"{rmse:.3f} °C")

# =========================================================
# 4. LÓGICA DE PROYECCIÓN (FIREBASE + IA)
# =========================================================
ahora = datetime.now()
try:
    ref = rtdb.reference('/sensor_data').get()
    if ref:
        t_now = float(ref.get('temp', 18.0))
        p_now = float(ref.get('ph', 7.0))
        tds_now = float(ref.get('tds', 0.0))
        
        entrada = pd.DataFrame([[t_now, p_now, float(jornada_hrs)]], columns=['temperatura', 'ph', 'horas_transcurridas'])
        for c in cols_modelo:
            if c not in entrada.columns: entrada[c] = 0
        
        tf = t_now + float(mod_t.predict(entrada[cols_modelo])[0]) + ajuste_sensibilidad
        pf = p_now + float(mod_p.predict(entrada[cols_modelo])[0]) + (ajuste_sensibilidad * 0.1)
        banda = (jornada_hrs / 24.0) * 1.2
        
        nuevo = {
            "Hora": ahora.strftime("%H:%M:%S"), 
            "T_R": t_now, "T_P": tf, 
            "P_R": p_now, "P_P": pf, 
            "TDS": tds_now,
            "Error_Banda": banda
        }
        st.session_state.historial = pd.concat([st.session_state.historial, pd.DataFrame([nuevo])], ignore_index=True).tail(50)
    else:
        t_now, p_now, tds_now, tf, pf, banda = 18.0, 7.0, 0.0, 18.0, 7.0, 0.1
except:
    t_now, p_now, tds_now, tf, pf, banda = 18.0, 7.0, 0.0, 18.0, 7.0, 0.1

# =========================================================
# 5. INTERFAZ DE USUARIO PRINCIPAL
# =========================================================
c_head1, c_head2 = st.columns([0.15, 0.85])
with c_head1:
    try:
        st.image(ruta_logo, width=80)
    except:
        pass
with c_head2:
    st.title("Sistema IoT RAS - Unidad Académica El Remanso UDCA")

hora_proyectada = (ahora + timedelta(hours=jornada_hrs)).strftime("%H:%M")
st.info(f"Proyectando comportamiento para las **{hora_proyectada}** ({jornada_hrs}h de horizonte)")

def obtener_estado_valido(valor, min_v, max_v):
    if min_v <= valor <= max_v: return "🟢 Óptimo", "complete"
    elif (min_v - 2) <= valor <= (max_v + 2): return "🟡 Alerta", "running"
    else: return "🔴 Crítico", "error"

s1, s2, s3 = st.columns(3)
txt_t, state_t = obtener_estado_valido(t_now, TEMP_MIN, TEMP_MAX)
txt_p, state_p = obtener_estado_valido(p_now, PH_MIN, PH_MAX)

with s1: st.status(f"Temp: {txt_t}", state=state_t)
with s2: st.status(f"pH: {txt_p}", state=state_p)
with s3: 
    st_tds = "complete" if tds_now < TDS_LIMITE else "error"
    st.status(f"TDS: {'🟢 Estable' if tds_now < TDS_LIMITE else '🔴 Alto'}", state=st_tds)

st.markdown("---")

m1, m2, m3 = st.columns(3)
m1.metric("Temperatura Actual", f"{t_now:.1f} °C")
m2.metric(f"Predicción (+{jornada_hrs}h)", f"{tf:.1f} °C", f"{tf-t_now:.2f} Δ")
m3.metric("pH Actual", f"{p_now:.2f}")

c_graph_a, c_graph_b = st.columns(2)

with c_graph_a:
    fig_t = go.Figure()
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"] + st.session_state.historial["Error_Banda"], mode='lines', line=dict(width=0), showlegend=False))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"] - st.session_state.historial["Error_Banda"], fill='tonexty', fillcolor='rgba(255, 255, 0, 0.1)', mode='lines', line=dict(width=0), name="Confianza IA"))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_R"], name="Real", line=dict(color="#00d4ff", width=4)))
    fig_t.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["T_P"], name="Predicción", line=dict(dash='dot', color="yellow")))
    fig_t.update_layout(template="plotly_dark", title="Tendencia Térmica Proyectada", height=400)
    st.plotly_chart(fig_t, use_container_width=True)

with c_graph_b:
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_R"], name="Real", line=dict(color="#ff00ff", width=4)))
    fig_p.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["P_P"], name="Predicción", line=dict(dash='dot', color="yellow")))
    fig_p.update_layout(template="plotly_dark", title="Tendencia pH Proyectada", height=400)
    st.plotly_chart(fig_p, use_container_width=True)

st.markdown("### TDS (Sólidos Totales Disueltos)")
fig_tds = go.Figure()
fig_tds.add_trace(go.Scatter(x=st.session_state.historial["Hora"], y=st.session_state.historial["TDS"], fill='tozeroy', name="TDS (ppm)", line=dict(color='#00ff88', width=2), fillcolor='rgba(0, 255, 136, 0.1)'))

if not st.session_state.historial.empty:
    fig_tds.add_shape(type="line", line=dict(color="red", dash="dash"), x0=st.session_state.historial["Hora"].iloc[0], y0=TDS_LIMITE, x1=st.session_state.historial["Hora"].iloc[-1], y1=TDS_LIMITE)

fig_tds.update_layout(template="plotly_dark", height=300, xaxis_title="Hora", yaxis_title="ppm")
st.plotly_chart(fig_tds, use_container_width=True)

st.sidebar.markdown("---")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

csv = st.session_state.historial.to_csv(index=False).encode('utf-8')
st.sidebar.download_button("Descargar Dataset Tesis", csv, f"ras_udca_{ahora.strftime('%H%M')}.csv", "text/csv")
