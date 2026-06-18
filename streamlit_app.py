import streamlit as st
from datetime import datetime, time, timezone, timedelta

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

INDICADORES = [
    ("85%",  0.85),
    ("90%",  0.90),
    ("100%", 1.00),
    ("101%", 1.01),
]

TURNOS = {
    "Turno A": {"inicio": time(6,  0),  "fin": time(15, 30)},
    "Turno B": {"inicio": time(15, 30), "fin": time(0,  0)},
    "Turno C": {"inicio": time(0,  0),  "fin": time(6,  0)},
}

AJUSTE_MIN = 10
COMIDA_MIN = 30

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def t2m(t: time) -> int:
    return t.hour * 60 + t.minute

def m2str(m: int) -> str:
    m = int(m) % 1440
    h = (m // 60) % 24
    mn = m % 60
    suf = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{mn:02d}{suf}"

def fin_ajustado(inicio_m: int, fin_m: int) -> int:
    """Para turnos que cruzan medianoche, ajusta fin > inicio."""
    return fin_m + 1440 if fin_m <= inicio_m else fin_m

def hora_en_turno(hora_m: int, inicio_m: int) -> int:
    """Ajusta la hora actual si el turno empezó ayer (cruza medianoche)."""
    if inicio_m > 720 and hora_m < 720:
        return hora_m + 1440
    return hora_m

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

# ── Zona horaria ─────────────────────────────────────────────────────────────
utc_offset = st.sidebar.number_input(
    "Zona horaria (UTC offset)", min_value=-12, max_value=14, value=-6, step=1,
    help="México Centro = -6 · México Noroeste = -7"
)
_tz    = timezone(timedelta(hours=utc_offset))
_ahora = datetime.now(_tz)

st.sidebar.caption(f"Hora local detectada: **{_ahora.strftime('%H:%M')}**")

# ── Selector de turno ────────────────────────────────────────────────────────
turno_sel  = st.selectbox("Turno", list(TURNOS.keys()))
turno_cfg  = TURNOS[turno_sel]
inicio_m   = t2m(turno_cfg["inicio"])
fin_m_raw  = t2m(turno_cfg["fin"])
fin_m      = fin_ajustado(inicio_m, fin_m_raw)
fin_real_m = fin_m - AJUSTE_MIN

duracion_total = fin_m - inicio_m
min_oficiales  = duracion_total - AJUSTE_MIN - COMIDA_MIN
min_reales     = min_oficiales  - AJUSTE_MIN

st.caption(
    f"Línea activa: **{m2str(inicio_m + AJUSTE_MIN)}** → **{m2str(fin_real_m)}** "
    f"· Min. oficiales: {min_oficiales} · Min. reales: {min_reales}"
)

st.divider()

# ── Producción ───────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    meta_pzh = st.number_input("Meta pz/h", min_value=1.0, value=500.0, step=10.0)
with col2:
    max_real_pzh = st.number_input("Máximo real pz/h", min_value=1.0, value=560.0, step=10.0)

if max_real_pzh < meta_pzh:
    st.warning(f"El máximo real ({max_real_pzh:.0f}) es menor a la meta ({meta_pzh:.0f}). Verifica los datos.")

# ── Descansos ────────────────────────────────────────────────────────────────
es_sabado = _ahora.weekday() == 5

if turno_sel == "Turno C":
    max_breaks = 2 if es_sabado else 0
else:
    max_breaks = 1

col3, col4 = st.columns(2)
with col3:
    comio = st.checkbox("¿Ya comiste?")
with col4:
    if max_breaks == 0:
        st.caption("Sin breaks en este turno")
        breaks = 0
    else:
        breaks = st.selectbox("¿Cuántos breaks tomaste?", list(range(max_breaks + 1)))

piezas = int(st.number_input("Piezas que llevan", min_value=0, value=0, step=1))

# ── Calcular ─────────────────────────────────────────────────────────────────
if st.button("Calcular", type="primary", use_container_width=True):

    ahora         = _ahora
    hora_actual_m = hora_en_turno(ahora.hour * 60 + ahora.minute, inicio_m)

    min_productivos = hora_actual_m - inicio_m - AJUSTE_MIN
    if comio:
        min_productivos -= COMIDA_MIN
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

    # Breaks de reloj que aún faltan (para ETA precisa)
    clock_bf = (COMIDA_MIN if not comio else 0) + (max_breaks - breaks) * 15

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

    hora_str = m2str(ahora.hour * 60 + ahora.minute)

    st.divider()
    st.subheader(
        f"{turno_sel} · {m2str(inicio_m)} – {m2str(fin_m_raw)}  ·  Hora: {hora_str}"
    )

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
