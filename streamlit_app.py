import streamlit as st
from datetime import datetime, time, timedelta
import json

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def restar_minutos(t: time, minutos: int) -> time:
    dt = datetime.combine(datetime.today(), t) - timedelta(minutes=minutos)
    return dt.time()

def fmt(t: time) -> str:
    return t.strftime("%H:%M")

# ─── CONFIG ───────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Gestión de Turnos", page_icon="⏱️", layout="centered")
st.title("⏱️ Gestión de Turnos")

with st.expander("⚙️ Configuración"):
    ajuste_min = st.number_input(
        "Ajuste de minutos (diferencia entre tiempo oficial y real)",
        min_value=0, max_value=120, value=10, step=1,
        help="Por defecto 10 min. Ajústalo según las reglas internas de tu empresa."
    )

st.divider()

# ─── INPUTS ───────────────────────────────────────────────────────────────────

col_ini, col_fin = st.columns(2)

with col_ini:
    st.subheader("🟢 Inicio de turno")
    inicio_real = st.time_input("Hora real de inicio", value=time(8, 0), key="inicio_real")

with col_fin:
    st.subheader("🔴 Fin de turno")
    fin_real = st.time_input("Hora real de fin", value=time(16, 0), key="fin_real")

# ─── CÁLCULOS ─────────────────────────────────────────────────────────────────

inicio_oficial = restar_minutos(inicio_real, ajuste_min)
fin_oficial    = restar_minutos(fin_real,    ajuste_min)

# ─── DISPLAY ──────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Comparativa")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    label="Inicio oficial",
    value=fmt(inicio_oficial),
    delta=f"-{ajuste_min} min",
    delta_color="off"
)
col2.metric(
    label="Inicio real",
    value=fmt(inicio_real)
)
col3.metric(
    label="Fin oficial",
    value=fmt(fin_oficial),
    delta=f"-{ajuste_min} min",
    delta_color="off"
)
col4.metric(
    label="Fin real",
    value=fmt(fin_real)
)

# ─── DURACIÓN ─────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Duración")

dur_oficial = datetime.combine(datetime.today(), fin_oficial) - datetime.combine(datetime.today(), inicio_oficial)
dur_real    = datetime.combine(datetime.today(), fin_real)    - datetime.combine(datetime.today(), inicio_real)

total_oficial_h = int(dur_oficial.total_seconds() // 3600)
total_oficial_m = int((dur_oficial.total_seconds() % 3600) // 60)
total_real_h    = int(dur_real.total_seconds() // 3600)
total_real_m    = int((dur_real.total_seconds() % 3600) // 60)

col5, col6 = st.columns(2)
col5.metric("Duración oficial", f"{total_oficial_h}h {total_oficial_m:02d}min")
col6.metric("Duración real",    f"{total_real_h}h {total_real_m:02d}min")

# ─── JSON ─────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Datos del turno (JSON)")

datos = {
    "inicio_oficial": fmt(inicio_oficial),
    "inicio_real":    fmt(inicio_real),
    "fin_oficial":    fmt(fin_oficial),
    "fin_real":       fmt(fin_real),
    "ajuste_minutos": ajuste_min,
    "duracion_oficial_min": int(dur_oficial.total_seconds() // 60),
    "duracion_real_min":    int(dur_real.total_seconds()    // 60),
}

st.json(datos)
