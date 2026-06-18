import streamlit as st
from datetime import datetime, time, timedelta

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

INDICADORES = [
    ("85%",  0.85),
    ("90%",  0.90),
    ("100%", 1.00),
    ("101%", 1.01),
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def t2m(t: time) -> int:
    return t.hour * 60 + t.minute

def m2str(m: int) -> str:
    m = int(m) % (24 * 60)
    h = (m // 60) % 24
    mins = m % 60
    suf = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{mins:02d}{suf}"

def get_estado(piezas, proy_real, proy_turbo, meta):
    if piezas >= meta or proy_real >= meta:
        return "✅"
    if proy_turbo >= meta:
        return "⚡"
    return "❌"

def texto_situacion(estados, max_real):
    etiquetas = ["85%", "90%", "100%", "101%"]
    verdes = [e for e, s in zip(etiquetas, estados) if s == "✅"]
    rayos  = [e for e, s in zip(etiquetas, estados) if s == "⚡"]
    rojos  = [e for e, s in zip(etiquetas, estados) if s == "❌"]
    if not rojos and not rayos:
        return "Vas muy bien — todos los indicadores están asegurados a tu ritmo actual."
    if not verdes and not rayos:
        return "Este turno ya no tiene recuperación en números. Concéntrate en hacer las cosas bien, no rápido."
    if not verdes and not rojos:
        return (f"A tu ritmo actual no alcanzas ningún indicador. "
                f"Acelerando al máximo ({int(max_real)} pz/h) puedes alcanzar todos — hasta el 101%.")
    partes = []
    if verdes:
        partes.append(f"El {verdes[-1]} ya está asegurado a tu ritmo actual.")
    if rayos:
        partes.append(f"Con turbo ({int(max_real)} pz/h) alcanzas hasta el {rayos[-1]}.")
    if rojos:
        partes.append(f"El {rojos[0]} ya no es posible en este turno.")
    return " ".join(partes)

# ─── UI ───────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Monitor de Turno", page_icon="🏭", layout="centered")
st.title("🏭 Monitor de Turno")

# ── Configuración del turno ──────────────────────────────────────────────────
with st.expander("⚙️ Configuración del turno", expanded=True):
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        inicio_turno = st.time_input("Inicio del turno", value=time(0, 0))
    with col_t2:
        fin_turno = st.time_input("Fin del turno", value=time(6, 0))

    col_t3, col_t4 = st.columns(2)
    with col_t3:
        ajuste_min = st.number_input(
            "Minutos de ajuste (arranque / parada anticipada)",
            min_value=0, max_value=60, value=10, step=1
        )
    with col_t4:
        comida_min = st.number_input(
            "Duración de comida (min)",
            min_value=0, max_value=60, value=30, step=5
        )

# Derivados del turno
inicio_turno_m = t2m(inicio_turno)
fin_turno_m    = t2m(fin_turno)
fin_real_m     = fin_turno_m - ajuste_min

duracion_total = fin_turno_m - inicio_turno_m
min_oficiales  = duracion_total - ajuste_min - comida_min
min_reales     = min_oficiales - ajuste_min

st.caption(
    f"Línea activa: **{m2str(inicio_turno_m + ajuste_min)}** → **{m2str(fin_real_m)}** "
    f"· Minutos oficiales: {min_oficiales} · Minutos reales: {min_reales}"
)

st.divider()

# ── Datos de producción ──────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    meta_pzh = st.number_input("Meta pz/h", min_value=1.0, value=500.0, step=10.0)
with col2:
    max_real_pzh = st.number_input("Máximo real pz/h", min_value=1.0, value=560.0, step=10.0)

if max_real_pzh < meta_pzh:
    st.warning(f"El máximo real ({max_real_pzh:.0f}) es menor a la meta ({meta_pzh:.0f}). Verifica los datos.")

hora_actual = st.time_input("Hora actual", value=time(0, 0))

col3, col4 = st.columns(2)
with col3:
    comio = st.checkbox("¿Ya comieron?")
with col4:
    breaks = st.selectbox("Breaks tomados", [0, 1, 2])

piezas = int(st.number_input("Piezas que llevan", min_value=0, value=0, step=1))

# ── Calcular ─────────────────────────────────────────────────────────────────
if st.button("Calcular", type="primary", use_container_width=True):

    hora_actual_m = t2m(hora_actual)

    min_productivos = hora_actual_m - inicio_turno_m - ajuste_min
    if comio:
        min_productivos -= comida_min
    min_productivos -= breaks * 15
    min_productivos  = max(min_productivos, 1)

    esperadas  = round((meta_pzh / 60) * min_productivos)
    diferencia = piezas - esperadas

    min_restantes = max(min_reales - min_productivos, 0)
    ritmo_real    = (piezas / min_productivos) * 60
    proy_real     = round(piezas + (ritmo_real   / 60) * min_restantes)
    proy_meta     = round(piezas + (meta_pzh     / 60) * min_restantes)
    proy_turbo    = round(piezas + (max_real_pzh / 60) * min_restantes)

    metas_pz   = [(lbl, round((meta_pzh / 60) * min_oficiales * pct)) for lbl, pct in INDICADORES]
    estados    = [get_estado(piezas, proy_real, proy_turbo, m) for _, m in metas_pz]
    faltan     = [max(m - piezas, 0) for _, m in metas_pz]
    ritmos_nec = [
        round((f / min_restantes) * 60) if f > 0 and min_restantes > 0 else None
        for f in faltan
    ]

    clock_bf = (comida_min if not comio else 0) + max(2 - breaks, 0) * 15

    eta_real_list, eta_turbo_list = [], []
    for f in faltan:
        if f <= 0:
            eta_real_list.append(None)
            eta_turbo_list.append(None)
        else:
            r = hora_actual_m + (f * 60 / ritmo_real)   + clock_bf if ritmo_real > 0 else None
            t = hora_actual_m + (f * 60 / max_real_pzh) + clock_bf
            eta_real_list.append(round(r) if r and r <= fin_real_m else None)
            eta_turbo_list.append(round(t) if t <= fin_real_m else None)

    # ── Output ───────────────────────────────────────────────────────────────

    st.divider()
    st.subheader(f"{m2str(inicio_turno_m)} – {m2str(fin_turno_m)}  ·  Hora: {m2str(hora_actual_m)}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Llevan",    f"{piezas:,} pz")
    c2.metric("Esperadas", f"{esperadas:,} pz")
    c3.metric("Diferencia",
              f"{'+' if diferencia >= 0 else ''}{diferencia:,} pz",
              delta=diferencia, delta_color="normal")

    st.subheader("Proyecciones")
    c4, c5, c6 = st.columns(3)
    c4.metric("📊 Real",  f"{proy_real:,} pz",  f"{ritmo_real:.1f} pz/h",    delta_color="off")
    c5.metric("📈 Ideal", f"{proy_meta:,} pz",  f"{int(meta_pzh)} pz/h",     delta_color="off")
    c6.metric("⚡ Turbo", f"{proy_turbo:,} pz", f"{int(max_real_pzh)} pz/h", delta_color="off")

    st.subheader("Indicadores")
    for (lbl, meta_v), estado, f, eta_r, eta_t, r_nec in zip(
            metas_pz, estados, faltan, eta_real_list, eta_turbo_list, ritmos_nec):

        if f <= 0:
            detalle = "alcanzado"
        elif estado == "✅":
            eta_s = f" · ~{m2str(eta_r)}" if eta_r else ""
            detalle = f"faltan {f:,} pz{eta_s}"
        elif estado == "⚡":
            eta_s = f" · con turbo ~{m2str(eta_t)}" if eta_t else ""
            nec_s = f" · necesitas {r_nec} pz/h" if r_nec else ""
            detalle = f"faltan {f:,} pz{eta_s}{nec_s}"
        else:
            nec_s = f" (necesitarías {r_nec} pz/h)" if r_nec else ""
            detalle = f"faltan {f:,} pz · imposible{nec_s}"

        st.markdown(f"**{estado} {lbl}** → `{meta_v:,} pz`&nbsp;&nbsp;&nbsp;{detalle}")

    situacion = texto_situacion(estados, max_real_pzh)
    if "muy bien" in situacion:
        st.success(situacion)
    elif "no tiene recuperación" in situacion:
        st.error(situacion)
    else:
        st.warning(situacion)
