import streamlit as st
from ui_theme import (
    inject_theme,
    init_game_state,
    render_collection_grid,
    render_hud,
    render_mission_bar,
    render_topbar,
    reset_game_state,
    svg_hero_emblem,
    svg_step_capture,
    svg_step_frame,
)

st.set_page_config(
    page_title="Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
init_game_state()
render_topbar()

h1, h2 = st.columns([0.1, 0.9], vertical_alignment="center")
with h1:
    st.markdown(svg_hero_emblem(), unsafe_allow_html=True)
with h2:
    st.markdown(
        """
<div class="eq-header" style="margin-bottom:0;">
  <h1 class="eq-title">Visión por computador</h1>
  <p class="eq-subtitle">Captura objetos reales, completa misiones y desbloquea toda la colección.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)
render_hud()
render_mission_bar("home")
st.markdown("<div style='height:1.1rem;'></div>", unsafe_allow_html=True)

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(
        f"""
<div class="eq-card">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  {svg_step_frame()}
  <h2 class="eq-card-title">Clasificación y objetos</h2>
  <p class="eq-card-desc">Evalúa tu modelo entrenado junto con detección de 80 objetos y el circuito en Wokwi.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.55rem;'></div>", unsafe_allow_html=True)
    st.page_link("pages/1_Teachable_Machine.py", label="Abrir clasificación", width="stretch")

with col2:
    st.markdown(
        f"""
<div class="eq-card">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  {svg_step_capture()}
  <h2 class="eq-card-title">Exploración de escena</h2>
  <p class="eq-card-desc">Busca múltiples objetos a la vez, ajusta umbrales y suma puntos por cada hallazgo.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.55rem;'></div>", unsafe_allow_html=True)
    st.page_link("pages/2_YOLO.py", label="Abrir exploración", width="stretch")

st.markdown("<div style='height:1.4rem;'></div>", unsafe_allow_html=True)
render_collection_grid()

st.markdown("<div style='height:0.9rem;'></div>", unsafe_allow_html=True)
_, r_col = st.columns([4, 1])
with r_col:
    if st.button("Reiniciar puntos", width="stretch"):
        reset_game_state()
        st.rerun()
