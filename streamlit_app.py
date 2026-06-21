import streamlit as st
from datetime import datetime, time, timezone, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import io

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

def tabla_a_png(df: "pd.DataFrame", titulo: str) -> io.BytesIO:
    n = len(df)
    fig, ax = plt.subplots(figsize=(9, max(2.5, n * 0.38 + 1.2)))
    ax.axis("off")
    tbl = ax.table(
        cellText=df.values,
        colLabels=df.columns.tolist(),
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    for j in range(len(df.columns)):
        tbl[(0, j)].set_facecolor("#2c3e50")
        tbl[(0, j)].set_text_props(color="white", fontweight="bold")
        tbl[(n, j)].set_facecolor("#dfe6e9")
        tbl[(n, j)].set_text_props(fontweight="bold")
    ax.set_title(titulo, fontsize=11, fontweight="bold", pad=14)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return buf

def get_filas_turno(turno_sel: str, es_sabado: bool, te_inicio_m: int = 360, te_fin_m: int = 840):
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
        curr = te_inicio_m
        while curr < te_fin_m:
            slot_end = min(curr + 60, te_fin_m)
            filas.append((f"{m2str(curr)}–{m2str(slot_end)}", slot_end - curr))
            curr = slot_end
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
turno_sel = st.selectbox("Turno", list(TURNOS.keys()))

if turno_sel == "Tiempo Extra":
    col_te1, col_te2 = st.columns(2)
    with col_te1:
        te_inicio = st.time_input("Hora de entrada", value=time(6, 0), key="te_inicio")
    with col_te2:
        te_fin = st.time_input("Hora de salida", value=time(14, 0), key="te_fin")
    inicio_m  = t2m(te_inicio)
    fin_m_raw = t2m(te_fin)
    if fin_m_raw <= inicio_m:
        st.error("La hora de salida debe ser después de la hora de entrada.")
        st.stop()
else:
    turno_cfg = TURNOS[turno_sel]
    inicio_m  = t2m(turno_cfg["inicio"])
    fin_m_raw = t2m(turno_cfg["fin"])

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

    eficiencia = (piezas / esperadas * 100) if esperadas > 0 else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Llevan",      f"{piezas:,} pz")
    c2.metric("Esperadas",   f"{esperadas:,} pz")
    c3.metric("Diferencia",
              f"{'+' if diferencia >= 0 else ''}{diferencia:,} pz",
              delta=diferencia, delta_color="normal")
    c4.metric("Eficiencia",  f"{eficiencia:.1f}%",
              f"{eficiencia - 100:+.1f}%", delta_color="normal")

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

    # ETA del indicador más alto alcanzable al ritmo actual o turbo
    eta_mejor = None
    for i in range(len(INDICADORES) - 1, -1, -1):
        if estados[i] == "✅" and faltan[i] > 0 and eta_real_list[i]:
            eta_mejor = (INDICADORES[i][0], eta_real_list[i])
            break
        if estados[i] == "⚡" and faltan[i] > 0 and eta_turbo_list[i]:
            eta_mejor = (INDICADORES[i][0], eta_turbo_list[i])
            break

    sufijo_eta = f" · Terminas el {eta_mejor[0]} ~{m2str(eta_mejor[1])}" if eta_mejor else ""

    if "muy bien" in situacion:
        st.success(situacion + sufijo_eta)
    elif "no tiene recuperación" in situacion:
        st.error(situacion)
    else:
        st.warning(situacion + sufijo_eta)

    # ── Recomendación de cobertura de descansos ──────────────────────────────
    breaks_restantes = max_breaks - breaks
    hay_comida = not comio
    hay_break  = breaks_restantes > 0

    if proy_real < metas_pz[-1][1] and (hay_comida or hay_break) and min_restantes > 0 and ritmo_real > 0:
        min_break_disp = breaks_restantes * 15
        extra_comida = round((ritmo_real / 60) * COMIDA_MIN) if hay_comida else 0
        extra_break  = round((ritmo_real / 60) * min_break_disp) if hay_break else 0

        proy_comida = proy_real + extra_comida
        proy_break  = proy_real + extra_break

        st.divider()
        st.subheader("💡 ¿Cubrir los descansos?")

        ncols = (1 if hay_comida else 0) + (1 if hay_break else 0)
        cols  = st.columns(ncols)
        ci = 0
        if hay_comida:
            cols[ci].metric(
                f"Cubriendo comida ({COMIDA_MIN} min)",
                f"{proy_comida:,} pz",
                f"+{extra_comida:,} pz",
                delta_color="off",
            )
            ci += 1
        if hay_break:
            cols[ci].metric(
                f"Cubriendo break ({min_break_disp} min)",
                f"{proy_break:,} pz",
                f"+{extra_break:,} pz",
                delta_color="off",
            )

        for (lbl, meta_v) in metas_pz:
            if hay_comida and proy_comida >= meta_v:
                marca = "✅ cubriendo la comida"
            elif hay_break and proy_break >= meta_v:
                marca = "⚡ cubriendo el break"
            else:
                marca = "❌ no alcanza"
            st.markdown(f"**{lbl}** → {marca}")

        mejor_comida = next(
            (lbl for lbl, mv in reversed(metas_pz) if hay_comida and proy_comida >= mv), None
        )
        mejor_break = next(
            (lbl for lbl, mv in reversed(metas_pz) if hay_break and proy_break >= mv), None
        )

        if mejor_comida:
            st.success(f"⭐ Cubre la comida → proyectas **{mejor_comida}** ({proy_comida:,} pz)")
        elif mejor_break:
            st.warning(
                f"La comida completa no alcanza al 85%. "
                f"Al menos cubre el break → proyectas **{mejor_break}** ({proy_break:,} pz)"
            )
        else:
            st.info("Aunque cubras los descansos el turno ya no tiene recuperación. Cada pieza suma.")

# ─── TABLA DE PLANEACIÓN ──────────────────────────────────────────────────────

st.divider()
st.subheader("📋 Tabla de planeación")

filas = get_filas_turno(turno_sel, es_sabado, inicio_m, fin_m)

objetivo_total = st.number_input(
    "🎯 Objetivo total del turno — 100% (deja en 0 para usar meta pz/h automática)",
    min_value=0, value=0, step=10,
    help="Útil cuando las decimales no cuadran. Este número se convierte en el 100% y la tabla distribuye de ahí.",
)

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
n = len(filas)

# Pre-pase: calcular minutos efectivos por fila con todas las deducciones
pre_minutos = []
for idx, (_, base_min) in enumerate(filas):
    comida_ded = COMIDA_MIN if idx == hora_comida_idx else 0
    break_ded  = break_idxs.count(idx) * 15
    if idx == 0:
        m = base_min - 10 - comida_ded - break_ded
    elif idx == n - 1:
        m = base_min - comida_ded - break_ded - 10
    else:
        m = base_min - comida_ded - break_ded
    pre_minutos.append(max(m, 0))

# Rate correcto: si hay objetivo, dividir entre los minutos reales de la tabla
# (+10 porque redist redistribuye los 10 min de arranque a las otras filas)
if objetivo_total > 0:
    rate_tabla = objetivo_total / (sum(pre_minutos) + 10)
else:
    rate_tabla = meta_pzh / 60

redist = (rate_tabla * 10) / (n - 1) if n > 1 else 0

tabla_rows = []
for idx, (label, base_min) in enumerate(filas):
    is_first   = idx == 0
    is_last    = idx == n - 1
    comida_ded = COMIDA_MIN if idx == hora_comida_idx else 0
    break_ded  = break_idxs.count(idx) * 15

    minutos      = pre_minutos[idx]
    minutos_acum = max(base_min - comida_ded - break_ded, 0) if is_last else minutos
    pz_acum      = rate_tabla * minutos_acum
    base_pz      = rate_tabla * minutos + (0 if is_last else redist)

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

titulo_img = (
    f"Tabla de planeación — {turno_sel} · {objetivo_total:,} pz (100%)"
    if objetivo_total > 0
    else f"Tabla de planeación — {turno_sel} · {meta_pzh:.0f} pz/h"
)
img_buf = tabla_a_png(df_plan, titulo_img)
st.download_button(
    "📥 Descargar tabla como imagen",
    data=img_buf,
    file_name="tabla_planeacion.png",
    mime="image/png",
    use_container_width=True,
)

# ─── GRÁFICA DE PRODUCCIÓN ────────────────────────────────────────────────────

import numpy as np

st.divider()
st.subheader("📈 Gráfica de producción")

hora_actual_local = hora_en_turno(_ahora.hour * 60 + _ahora.minute, inicio_m)

# Rangos de cada slot: inicio acumulado por fila
slot_starts = []
t_acc = inicio_m
for _, base_min in filas:
    slot_starts.append(t_acc)
    t_acc += base_min

# Slots que ya comenzaron
active_slots = [
    (i, filas[i][0], slot_starts[i], slot_starts[i] + filas[i][1])
    for i in range(len(filas))
    if hora_actual_local > slot_starts[i]
]

if not active_slots:
    st.info("El turno aún no ha iniciado — la gráfica aparecerá cuando empiece.")
else:
    st.markdown("**Piezas producidas por hora:**")
    ncols = min(4, len(active_slots))
    grid_cols = st.columns(ncols)
    piezas_hora = {}
    for j, (i, label, s_start, s_end) in enumerate(active_slots):
        es_parcial = hora_actual_local < s_end
        with grid_cols[j % ncols]:
            val = st.number_input(
                label + (" *(en curso)*" if es_parcial else ""),
                min_value=0, value=0, step=1, key=f"ph_{i}",
            )
        mins_slot = max(min(hora_actual_local, s_end) - s_start, 1)
        piezas_hora[i] = (val, es_parcial, mins_slot)

    hay_datos = any(v > 0 for v, _, _ in piezas_hora.values())

    if not hay_datos:
        st.caption("Ingresa las piezas de cada hora para ver la gráfica.")
    else:
        # ── Metas de referencia ──────────────────────────────────────────────
        meta_100_v = objetivo_total if objetivo_total > 0 else round((meta_pzh / 60) * min_oficiales)
        metas_ref = [
            ("85%",  round(meta_100_v * 0.85), "#666677"),
            ("90%",  round(meta_100_v * 0.90), "#8888aa"),
            ("100%", meta_100_v,                "#4488ff"),
            ("101%", round(meta_100_v * 1.01),  "#ffaa00"),
        ]
        meta_101_v = metas_ref[3][1]

        # ── Línea ideal (columna 100% de la tabla, acumulada) ────────────────
        ideal_x, ideal_y = [inicio_m], [0]
        t_run, run_100 = inicio_m, 0
        for row, (_, base_min) in zip(tabla_rows[:-1], filas):
            t_run  += base_min
            run_100 += row[2]
            ideal_x.append(t_run)
            ideal_y.append(run_100)

        # ── Línea turbo (ritmo máximo real, acumulada) ───────────────────────
        turbo_x, turbo_y = [inicio_m], [0]
        t_run, run_turbo = inicio_m, 0
        for idx_r, (_, base_min) in enumerate(filas):
            t_run    += base_min
            run_turbo += round((max_real_pzh / 60) * pre_minutos[idx_r])
            turbo_x.append(t_run)
            turbo_y.append(run_turbo)

        # ── Línea real (acumulado hora a hora) ───────────────────────────────
        real_x, real_y = [inicio_m], [0]
        run_real = 0
        for i, _, s_start, s_end in active_slots:
            val, es_parcial, _ = piezas_hora[i]
            run_real += val
            real_x.append(min(hora_actual_local, s_end))
            real_y.append(run_real)
        last_x, last_y = real_x[-1], real_y[-1]

        # ── Rate de proyección: parcial > prom últimas 2 > última completada ─
        completados = [(i, v, pre_minutos[i]) for i, (v, par, _) in piezas_hora.items()
                       if not par and v > 0]
        parciales   = [(i, v, m)              for i, (v, par, m) in piezas_hora.items()
                       if par and v > 0]

        rate_proj = None
        if parciales:
            _, v_p, m_p = parciales[-1]
            rate_proj = (v_p / m_p) * 60 if m_p > 0 else None
        if rate_proj is None and len(completados) >= 2:
            last2 = completados[-2:]
            pz2   = sum(v for _, v, _ in last2)
            min2  = sum(m for _, _, m in last2)
            rate_proj = (pz2 / min2) * 60 if min2 > 0 else None
        if rate_proj is None and completados:
            _, v_c, m_c = completados[-1]
            rate_proj = (v_c / m_c) * 60 if m_c > 0 else None
        if rate_proj is None:
            rate_proj = meta_pzh

        rate_proj_pm  = rate_proj / 60      # pz/min
        rate_turbo_pm = max_real_pzh / 60   # pz/min

        # ── Proyecciones hasta 101% o fin de turno ───────────────────────────
        def proj_line(from_x, from_y, rate_pm, cap_y, end_x):
            if rate_pm <= 0 or from_y >= cap_y:
                return [from_x, end_x], [from_y, from_y]
            mins = (cap_y - from_y) / rate_pm
            x1   = min(from_x + mins, end_x)
            y1   = min(from_y + (x1 - from_x) * rate_pm, cap_y)
            return [from_x, x1], [from_y, y1]

        px_real,  py_real  = proj_line(last_x, last_y, rate_proj_pm,  meta_101_v, fin_m)
        px_turbo, py_turbo = proj_line(last_x, last_y, rate_turbo_pm, meta_101_v, fin_m)

        # ── ETAs por nivel (dentro del turno) ────────────────────────────────
        etas_real, etas_turbo = [], []
        for pct, meta_v, _ in metas_ref:
            if meta_v > last_y:
                if rate_proj_pm > 0:
                    eta = last_x + (meta_v - last_y) / rate_proj_pm
                    if eta <= fin_m:
                        etas_real.append((pct, int(eta), meta_v))
                if rate_turbo_pm > 0:
                    eta_t = last_x + (meta_v - last_y) / rate_turbo_pm
                    if eta_t <= fin_m:
                        etas_turbo.append((pct, int(eta_t), meta_v))

        # ── Gráfica ──────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(11, 5))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#131722")

        # Zonas de descanso
        ax.axvspan(slot_starts[hora_comida_idx],
                   slot_starts[hora_comida_idx] + COMIDA_MIN,
                   color="#1a2a44", alpha=0.7, zorder=0, label="Comida")
        seen_b = {}
        for bi in break_idxs:
            seen_b[bi] = seen_b.get(bi, 0) + 1
        for bi, cnt in seen_b.items():
            ax.axvspan(slot_starts[bi], slot_starts[bi] + 15 * cnt,
                       color="#2a2a10", alpha=0.7, zorder=0, label="Break")

        # Líneas horizontales de referencia
        for pct, meta_v, color in metas_ref:
            ax.axhline(meta_v, color=color, linewidth=0.8, linestyle=":", alpha=0.6)
            ax.text(fin_m + (fin_m - inicio_m) * 0.01, meta_v,
                    pct, color=color, fontsize=7, va="center", ha="left")

        # Turbo (fondo)
        ax.plot(turbo_x, turbo_y, color="#ffaa00", linewidth=1.0,
                alpha=0.4, label=f"Turbo ({int(max_real_pzh)} pz/h)")

        # Ideal
        ax.plot(ideal_x, ideal_y, color="#4488ff", linewidth=1.5,
                alpha=0.85, label="Ideal 100%")

        # Área sombreada entre real e ideal
        rx  = np.array(real_x)
        ry  = np.array(real_y)
        iy  = np.interp(rx, ideal_x, ideal_y)
        ax.fill_between(rx, ry, iy, where=(ry >= iy),
                        color="#00cc44", alpha=0.18, interpolate=True)
        ax.fill_between(rx, ry, iy, where=(ry < iy),
                        color="#ff4444", alpha=0.18, interpolate=True)

        # Real
        ax.plot(real_x, real_y, color="#ff4444", linewidth=2.5, label="Real")
        ax.plot(last_x, last_y, "o", color="#ff4444", markersize=7, zorder=5)

        # Proyecciones punteadas
        ax.plot(px_real,  py_real,  color="#ff7777", linewidth=1.5,
                linestyle="--", alpha=0.9, label="Proyección actual")
        ax.plot(px_turbo, py_turbo, color="#ffcc55", linewidth=1.5,
                linestyle="--", alpha=0.9, label="Proyección turbo")

        # Puntos de ETA en la gráfica (más alto alcanzable de cada proyección)
        if etas_real:
            pct, eta_m, meta_v = etas_real[-1]
            ax.plot(eta_m, meta_v, "o", color="#ff7777", markersize=5, zorder=6)
            ax.annotate(f"{pct} {m2str(eta_m)}", xy=(eta_m, meta_v),
                        xytext=(eta_m - (fin_m - inicio_m) * 0.05, meta_v * 1.025),
                        color="#ff9999", fontsize=6.5, zorder=7,
                        arrowprops=dict(arrowstyle="-", color="#ff777755", lw=0.8))
        if etas_turbo:
            pct, eta_m, meta_v = etas_turbo[-1]
            ax.plot(eta_m, meta_v, "o", color="#ffcc55", markersize=5, zorder=6)
            ax.annotate(f"{pct} {m2str(eta_m)}", xy=(eta_m, meta_v),
                        xytext=(eta_m + (fin_m - inicio_m) * 0.01, meta_v * 0.975),
                        color="#ffdd88", fontsize=6.5, zorder=7,
                        arrowprops=dict(arrowstyle="-", color="#ffaa0055", lw=0.8))

        # Ejes
        tick_step = max(1, len(slot_starts) // 6)
        ticks_x   = slot_starts[::tick_step]
        if fin_m not in ticks_x:
            ticks_x = list(ticks_x) + [fin_m]
        ax.set_xticks(ticks_x)
        ax.set_xticklabels([m2str(x) for x in ticks_x],
                           color="#aaaaaa", fontsize=7, rotation=30, ha="right")
        ax.set_xlim(inicio_m - 3, fin_m + (fin_m - inicio_m) * 0.08)
        ax.set_ylim(0, meta_101_v * 1.08)
        ax.set_yticks([m[1] for m in metas_ref])
        ax.set_yticklabels([f"{m[1]:,}" for m in metas_ref],
                           color="#aaaaaa", fontsize=7)
        ax.tick_params(colors="#333344", length=3)
        for sp in ax.spines.values():
            sp.set_edgecolor("#222233")

        ax.legend(loc="upper left", fontsize=7, facecolor="#1a1a2e",
                  labelcolor="white", framealpha=0.75, edgecolor="#333344",
                  ncol=2)
        ax.set_title("Producción acumulada en el turno", color="white",
                     fontsize=10, pad=8)

        plt.tight_layout()
        st.pyplot(fig)

        buf_graf = io.BytesIO()
        fig.savefig(buf_graf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf_graf.seek(0)
        plt.close(fig)

        st.download_button(
            "📥 Descargar gráfica como imagen",
            data=buf_graf,
            file_name="grafica_produccion.png",
            mime="image/png",
            use_container_width=True,
        )

        # ── Resumen de ETAs ──────────────────────────────────────────────────
        if etas_real or etas_turbo:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                if etas_real:
                    st.markdown(f"**🔴 Al ritmo actual ({rate_proj:.0f} pz/h):**")
                    for pct, eta_m, _ in etas_real:
                        st.markdown(f"- {pct} → ~{m2str(eta_m)}")
            with col_e2:
                if etas_turbo:
                    st.markdown(f"**🟡 Al turbo ({int(max_real_pzh)} pz/h):**")
                    for pct, eta_m, _ in etas_turbo:
                        st.markdown(f"- {pct} → ~{m2str(eta_m)}")
