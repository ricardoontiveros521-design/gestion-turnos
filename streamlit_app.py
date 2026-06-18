import streamlit as st
from datetime import datetime, time, timezone, timedelta
import pandas as pd

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

INDICADORES = [
    ("85%",  0.85),
    ("90%",  0.90),
    ("100%", 1.00),
    ("101%", 1.01),
]

TURNOS = {
    "Turno A":      {"inicio": time(6,  0),  "fin": time(15, 30)},
    "Turno B":      {"inicio": time(15, 30), "fin": time(0,  0)},
    "Turno C":      {"inicio": time(0,  0),  "fin": time(6,  0)},
    "Tiempo Extra": {"inicio": time(6,  0),  "fin": time(14, 0)},
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
    return fin_m + 1440 if fin_m <= inicio_m else fin_m

def hora_en_turno(hora_m: int, inicio_m: int) -> int:
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

def get_filas_turno(turno_sel: str, es_sabado: bool):
    """Devuelve lista de (etiqueta_rango, minutos_base) por fila de la tabla."""
    filas = []
    if turno_sel == "Turno A":
        # 9 horas completas + media hora al final
        for i in range(9):
            ini = 360 + i * 60
            filas.append((f"{m2str(ini)}–{m2str(ini + 60)}", 60))
        filas.append((f"{m2str(900)}–{m2str(930)}", 30))
    elif turno_sel == "Turno B":
        # media hora al inicio + 8 horas completas
        filas.append((f"{m2str(930)}–{m2str(960)}", 30))
        for i in range(8):
            ini = 960 + i * 60
            filas.append((f"{m2str(ini)}–{m2str(ini + 60)}", 60))
    elif turno_sel == "Turno C":
        n = 12 if es_sabado else 6
        for i in range(n):
            ini = i * 60
            filas.append((f"{m2str(ini)}–{m2str(ini + 60)}", 60))
    elif turno_sel == "Tiempo Extra":
        for i in range(8):
            ini = 360 + i * 60
            filas.append((f"{m2str(ini)}–{m2str(ini + 60)}", 60))
    return filas

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
es_sabado = _ahora.weekday() == 5

st.sidebar.caption(f"Hora local detectada: **{_ahora.strftime('%H:%M')}**")

# ── Selector de turno ────────────────────────────────────────────────────────
turno_sel  = st.selectbox("Turno", list(TURNOS.keys()))
turno_cfg  = TURNOS[turno_sel]
inicio_m   = t2m(turno_cfg["inicio"])
fin_m_raw  = t2m(turno_cfg["fin"])

# Turno C sábado dura 12 horas (12:00am–12:00pm)
if turno_sel == "Turno C" and es_sabado:
    fin_m_raw = t2m(time(12, 0))

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

    # ── Alerta de ritmo crítico ───────────────────────────────────────────────
    faltan_85 = faltan[0]
    if faltan_85 > 0 and min_restantes > 0:
        ritmo_min_85 = (faltan_85 / min_restantes) * 60
        if max_real_pzh < ritmo_min_85:
            st.error(
                f"🚨 **El 85% ya no es recuperable** · "
                f"incluso al máximo ({int(max_real_pzh)} pz/h) "
                f"solo alcanzarías {round(piezas + (max_real_pzh/60)*min_restantes):,} pz"
            )
        elif ritmo_real < ritmo_min_85:
            st.warning(
                f"⚠️ **Ritmo insuficiente para el 85%** · "
                f"llevas {ritmo_real:.0f} pz/h, necesitas al menos "
                f"**{ritmo_min_85:.0f} pz/h** · faltan {faltan_85:,} pz en {min_restantes} min"
            )

    st.subheader("Indicadores")
    for (lbl, meta_v), estado, f, eta_r, eta_t, r_nec in zip(
            metas_pz, estados, faltan, eta_real_list, eta_turbo_list, ritmos_nec):

        if f <= 0:
            detalle = "alcanzado"
        elif estado == "✅":
            eta_s = f" · terminas ~{m2str(eta_r)}" if eta_r else ""
            nec_s = f" · necesitas {r_nec} pz/h" if r_nec else ""
            detalle = f"faltan {f:,} pz{eta_s}{nec_s}"
        elif estado == "⚡":
            eta_s = f" · con turbo ~{m2str(eta_t)}" if eta_t else ""
            nec_s = f" · necesitas {r_nec} pz/h" if r_nec else ""
            detalle = f"faltan {f:,} pz{eta_s}{nec_s}"
        else:
            nec_s = f" · necesitarías {r_nec} pz/h" if r_nec else ""
            detalle = f"faltan {f:,} pz · imposible{nec_s}"

        st.markdown(f"**{estado} {lbl}** → `{meta_v:,} pz`&nbsp;&nbsp;&nbsp;{detalle}")

    situacion = texto_situacion(estados, max_real_pzh)
    if "muy bien" in situacion:
        st.success(situacion)
    elif "no tiene recuperación" in situacion:
        st.error(situacion)
    else:
        st.warning(situacion)

# ─── TABLA DE PLANEACIÓN ──────────────────────────────────────────────────────

st.divider()
st.subheader("📋 Tabla de planeación")

filas = get_filas_turno(turno_sel, es_sabado)

# ── Selectores de hora para comida y breaks ───────────────────────────────────
if turno_sel == "Turno C" and es_sabado:
    # Comida: primeras 6 horas (12am–6am); breaks: últimas 6 horas (6am–12pm)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        hora_comida_idx = st.selectbox(
            "¿En qué hora comes?",
            options=list(range(6)),
            format_func=lambda i: filas[i][0],
            key="hora_comida_tabla",
        )
    with col_t2:
        hora_break1_idx = st.selectbox(
            "¿En qué hora es el break 1?",
            options=list(range(6, 12)),
            format_func=lambda i: filas[i][0],
            key="hora_break1_tabla",
        )
    hora_break2_idx = st.selectbox(
        "¿En qué hora es el break 2?",
        options=list(range(6, 12)),
        format_func=lambda i: filas[i][0],
        key="hora_break2_tabla",
    )
    break_idxs = [hora_break1_idx, hora_break2_idx]

elif max_breaks == 1:
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        hora_comida_idx = st.selectbox(
            "¿En qué hora comes?",
            options=list(range(len(filas))),
            format_func=lambda i: filas[i][0],
            key="hora_comida_tabla",
        )
    with col_t2:
        hora_break_idx = st.selectbox(
            "¿En qué hora es el break?",
            options=list(range(len(filas))),
            format_func=lambda i: filas[i][0],
            key="hora_break_tabla",
        )
    break_idxs = [hora_break_idx]

else:
    # Turno C entre semana: solo comida, sin breaks
    hora_comida_idx = st.selectbox(
        "¿En qué hora comes?",
        options=list(range(len(filas))),
        format_func=lambda i: filas[i][0],
        key="hora_comida_tabla",
    )
    break_idxs = []

# ── Construir y mostrar tabla ─────────────────────────────────────────────────
n      = len(filas)
redist = (meta_pzh / 60 * 10) / (n - 1) if n > 1 else 0

tabla_rows = []
for idx, (label, base_min) in enumerate(filas):
    is_first   = idx == 0
    is_last    = idx == n - 1
    comida_ded = COMIDA_MIN if idx == hora_comida_idx else 0
    break_ded  = break_idxs.count(idx) * 15

    if is_first:
        minutos = base_min - 10 - comida_ded - break_ded
    elif is_last:
        minutos = base_min - comida_ded - break_ded - 10
    else:
        minutos = base_min - comida_ded - break_ded

    minutos = max(minutos, 0)
    # Para el acumulado la última hora usa 60 min (sin el -10 de parada anticipada)
    minutos_acum = max(base_min - comida_ded - break_ded, 0) if is_last else minutos
    pz_acum = (meta_pzh / 60) * minutos_acum
    base_pz = (meta_pzh / 60) * minutos + (0 if is_last else redist)

    tabla_rows.append([
        label,
        round(base_pz * 1.01),
        round(base_pz * 1.00),
        round(base_pz * 0.90),
        round(base_pz * 0.85),
        round(pz_acum),   # temporal para acumulado
    ])

# Columna de acumulado (running total de 100% sin redistribución)
running = 0
for row in tabla_rows:
    running += row[5]   # índice 5 = pz_puro
    row[5] = running    # reemplazar temporal por acumulado

# Fila de totales
totales = ["Total",
           sum(r[1] for r in tabla_rows),
           sum(r[2] for r in tabla_rows),
           sum(r[3] for r in tabla_rows),
           sum(r[4] for r in tabla_rows),
           running]
tabla_rows.append(totales)

df_plan = pd.DataFrame(tabla_rows, columns=["Hora", "101%", "100%", "90%", "85%", "Acumulado"])

st.dataframe(df_plan, use_container_width=True, hide_index=True)
