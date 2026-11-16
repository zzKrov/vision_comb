import io
import time

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from ui_theme import (
    init_game_state,
    inject_theme,
    register_scan,
    render_collection_grid,
    render_hud,
    render_mission_bar,
    render_topbar,
    svg_idle_reticle,
    translate_label,
)

st.set_page_config(
    page_title="Exploración · Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
init_game_state()
render_topbar()


@st.cache_resource(show_spinner=False)
def load_yolo_model():
    from ultralytics import YOLO

    return YOLO("yolov5su.pt")


st.markdown(
    """
<div class="eq-header">
  <h1 class="eq-title">Exploración de escena</h1>
  <p class="eq-subtitle">Localiza múltiples objetos a la vez y completa los desafíos.</p>
</div>
    """,
    unsafe_allow_html=True,
)

render_hud()
render_mission_bar("yolo")
st.markdown("<div style='height:0.9rem;'></div>", unsafe_allow_html=True)

with st.expander("Ajustes de detección", expanded=False):
    p1, p2, p3 = st.columns(3, gap="medium")
    with p1:
        conf_threshold = st.slider("Confianza mínima", 0.05, 0.95, 0.25, 0.01)
    with p2:
        iou_threshold = st.slider("Umbral IoU", 0.05, 0.95, 0.45, 0.01)
    with p3:
        max_det = st.slider("Máximo de objetos", 5, 100, 30, 5)

with st.spinner("Cargando modelo..."):
    model = load_yolo_model()

source = st.radio("Origen", ["Cámara", "Archivo"], horizontal=True, label_visibility="collapsed")

raw_bytes = None
pil_img = None

if source == "Cámara":
    picture = st.camera_input("Capturar imagen", label_visibility="collapsed")
    if picture is not None:
        raw_bytes = picture.getvalue()
        pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
else:
    uploaded = st.file_uploader(
        "Subir imagen",
        type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

if pil_img is None or raw_bytes is None:
    st.markdown(
        f"""
<div class="eq-idle" style="margin-top:0.75rem;">
  {svg_idle_reticle()}
  <p>Toma una foto o sube una imagen para buscar objetos.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    render_collection_grid()
    st.stop()

np_bgr = np.array(pil_img)[..., ::-1]
t0 = time.perf_counter()
results = model(
    np_bgr,
    conf=conf_threshold,
    iou=iou_threshold,
    max_det=int(max_det),
    verbose=False,
)
elapsed_ms = (time.perf_counter() - t0) * 1000.0

result = results[0]
boxes = result.boxes
annotated_rgb = result.plot()[:, :, ::-1]

counts = {}
confs = {}
if boxes is not None and len(boxes) > 0:
    for box in boxes:
        raw_name = model.names[int(box.cls.item())]
        es_name = translate_label(raw_name)
        conf = float(box.conf.item())
        counts[es_name] = counts.get(es_name, 0) + 1
        confs.setdefault(es_name, []).append(conf)

events = register_scan(raw_bytes, list(counts.keys()))
for ev in events:
    st.markdown(f'<div class="eq-event">{ev}</div>', unsafe_allow_html=True)

col1, col2 = st.columns([1.1, 0.9], gap="large")

with col1:
    st.markdown(
        f"""
<div class="eq-frame" style="margin-bottom:0.65rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <span style="font-size:0.86rem;color:#8B929E;">Imagen analizada · {elapsed_ms:.0f} ms</span>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.image(annotated_rgb, width="stretch")

with col2:
    st.markdown(
        """
<div class="eq-frame" style="margin-bottom:0.65rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <span style="font-size:0.86rem;color:#8B929E;">Objetos encontrados</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    if counts:
        df = pd.DataFrame(
            [
                {
                    "Objeto": name,
                    "Cantidad": cnt,
                    "Confianza": f"{np.mean(confs[name]) * 100:.1f} %",
                }
                for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)
        st.bar_chart(df.set_index("Objeto")["Cantidad"])
    else:
        st.info("No se encontraron objetos con la confianza actual.")

st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
render_collection_grid()
