from pathlib import Path
import streamlit as st
from ui_theme import inject_theme, render_topbar, svg_hero_emblem, svg_step_frame, svg_step_capture

st.set_page_config(
    page_title="Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
render_topbar(active="inicio")

# Encabezado simétrico principal
h_col1, h_col2 = st.columns([0.12, 0.88], vertical_alignment="center")
with h_col1:
    st.markdown(svg_hero_emblem(), unsafe_allow_html=True)
with h_col2:
    st.markdown(
        """
<div class="eq-header" style="margin-bottom:0;">
  <h1 class="eq-title">Visión por computador</h1>
  <p class="eq-subtitle">Elige una herramienta para analizar imágenes desde tu cámara o desde un archivo.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)

# Tarjetas de acceso directo
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(
        f"""
<div class="eq-card">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  {svg_step_frame()}
  <h2 class="eq-card-title">Clasificación</h2>
  <p class="eq-card-desc">Evalúa una imagen con tu modelo entrenado en Teachable Machine y visualiza las probabilidades por clase.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    st.page_link("pages/1_Teachable_Machine.py", label="Abrir clasificación", width="stretch")

with col2:
    st.markdown(
        f"""
<div class="eq-card">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  {svg_step_capture()}
  <h2 class="eq-card-title">Detección</h2>
  <p class="eq-card-desc">Localiza múltiples objetos en escena con YOLO, ajusta los umbrales y revisa el conteo por categoría.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    st.page_link("pages/2_YOLO.py", label="Abrir detección", width="stretch")

# Estado rápido de archivos en repositorio (sin cargar modelos pesados aquí)
root = Path(__file__).resolve().parent
has_keras = (root / "keras_model.h5").exists()
has_labels = (root / "labels.txt").exists()

st.markdown('<hr class="eq-divider">', unsafe_allow_html=True)
st.markdown(
    f"""
<div style="display:flex;flex-wrap:wrap;gap:0.6rem;align-items:center;justify-content:space-between;">
  <span style="color:#8B929E;font-size:0.85rem;">Archivos del repositorio</span>
  <div>
    <span class="eq-pill">keras_model.h5 · {"listo" if has_keras else "no encontrado"}</span>
    <span class="eq-pill">labels.txt · {"listo" if has_labels else "no encontrado"}</span>
  </div>
</div>
    """,
    unsafe_allow_html=True,
)
