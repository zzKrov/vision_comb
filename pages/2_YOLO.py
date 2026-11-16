import io
import time

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from ui_theme import inject_theme, render_topbar, svg_idle_reticle

st.set_page_config(
    page_title="Detección · Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
render_topbar(active="yolo")


@st.cache_resource(show_spinner=False)
def load_yolo_model():
    from ultralytics import YOLO

    return YOLO("yolov5su.pt")


st.markdown(
    """
<div class="eq-header">
  <h1 class="eq-title">Detección</h1>
  <p class="eq-subtitle">Identifica y cuenta los objetos presentes en una imagen.</p>
</div>
    """,
    unsafe_allow_html=True,
)

# Parámetros inline (reemplaza el sidebar)
with st.expander("Ajustes de detección", expanded=False):
    p1, p2, p3 = st.columns(3, gap="medium")
    with p1:
        conf_threshold = st.slider("Confianza mínima", 0.05, 1.0, 0.25, 0.01)
    with p2:
        iou_threshold = st.slider("Umbral IoU", 0.05, 1.0, 0.45, 0.01)
    with p3:
        max_det = st.number_input("Máximo de objetos", 10, 1000, 100, 10)

with st.spinner("Cargando modelo..."):
    try:
        model = load_yolo_model()
    except Exception as exc:
        st.error(f"No se pudo cargar el modelo: {exc}")
        st.stop()

source = st.radio(
    "Origen",
    ["Cámara", "Archivo"],
    horizontal=True,
    label_visibility="collapsed",
)

pil_img = None
if source == "Cámara":
    picture = st.camera_input("Capturar imagen", label_visibility="collapsed")
    if picture is not None:
        pil_img = Image.open(io.BytesIO(picture.getvalue())).convert("RGB")
else:
    uploaded = st.file_uploader(
        "Subir imagen",
        type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        pil_img = Image.open(uploaded).convert("RGB")

if pil_img is None:
    st.markdown(
        f"""
<div class="eq-idle" style="margin-top:0.75rem;">
  {svg_idle_reticle()}
  <p>Toma una foto o sube una imagen para detectar objetos.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
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

    if boxes is not None and len(boxes) > 0:
        names = model.names
        counts = {}
        confs = {}
        for box in boxes:
            cls_id = int(box.cls.item())
            conf = float(box.conf.item())
            counts[cls_id] = counts.get(cls_id, 0) + 1
            confs.setdefault(cls_id, []).append(conf)

        df = pd.DataFrame(
            [
                {
                    "Objeto": names[cid],
                    "Cantidad": cnt,
                    "Confianza": f"{np.mean(confs[cid]) * 100:.1f} %",
                }
                for cid, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)
        st.bar_chart(df.set_index("Objeto")["Cantidad"])
    else:
        st.info("No se encontraron objetos con la confianza actual.")
