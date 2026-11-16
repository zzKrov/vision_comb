import io
from pathlib import Path
import time

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

from ui_theme import (
    WOKWI_PROJECT_ID,
    init_game_state,
    inject_theme,
    register_scan,
    render_collection_grid,
    render_hud,
    render_mission_bar,
    render_topbar,
    svg_idle_reticle,
    svg_step_capture,
    svg_step_frame,
    svg_step_result,
    translate_label,
)

st.set_page_config(
    page_title="Clasificación · Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
init_game_state()
render_topbar()

ROOT = Path(__file__).resolve().parent.parent


@st.cache_resource(show_spinner=False)
def load_keras_model(model_path: str):
    import json
    import h5py
    import tensorflow as tf

    try:
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception:
        pass

    class CompatDepthwiseConv2D(tf.keras.layers.DepthwiseConv2D):
        def __init__(self, **kwargs):
            kwargs.pop("groups", None)
            super().__init__(**kwargs)

    try:
        return tf.keras.models.load_model(
            model_path,
            compile=False,
            custom_objects={"DepthwiseConv2D": CompatDepthwiseConv2D},
        )
    except Exception:
        pass

    from keras.src.legacy.saving import saving_options, saving_utils

    def _strip_groups(obj):
        if isinstance(obj, dict):
            if obj.get("class_name") == "DepthwiseConv2D" and isinstance(obj.get("config"), dict):
                obj["config"].pop("groups", None)
            return {k: _strip_groups(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_strip_groups(v) for v in obj]
        return obj

    def _find_input_shape(cfg_dict):
        bshape = cfg_dict.get("config", {}).get("build_input_shape")
        if isinstance(bshape, (list, tuple)) and len(bshape) > 1:
            return tuple(bshape[1:])
        for lyr in cfg_dict.get("config", {}).get("layers", []):
            lcfg = lyr.get("config", {})
            for key in ("batch_input_shape", "batch_shape", "build_input_shape"):
                val = lcfg.get(key)
                if isinstance(val, (list, tuple)) and len(val) > 1:
                    return tuple(val[1:])
        return (224, 224, 3)

    def _iter_leaf_layers(layer):
        if hasattr(layer, "layers") and layer.layers:
            for sub in layer.layers:
                yield from _iter_leaf_layers(sub)
        else:
            yield layer

    def _assign_group_weights(group, target_layers):
        weight_names = [
            n.decode("utf-8") if isinstance(n, bytes) else n
            for n in group.attrs.get("weight_names", [])
        ]
        if not weight_names:
            return

        by_key = {}
        all_leaves = []
        for lyr in target_layers:
            for leaf in _iter_leaf_layers(lyr):
                all_leaves.append(leaf)
                for var in leaf.weights:
                    vname = var.name.split(":")[0].split("/")[-1]
                    by_key.setdefault((leaf.name, vname), []).append(var)

        assigned = set()
        unmatched = []

        for wn in weight_names:
            val = np.asarray(group[wn])
            clean = wn.split(":")[0]
            parts = clean.split("/")
            lname = parts[-2] if len(parts) >= 2 else group.name.rsplit("/", 1)[-1]
            vname = parts[-1]

            matched_var = None
            for var in by_key.get((lname, vname), []):
                if id(var) not in assigned and tuple(var.shape) == val.shape:
                    matched_var = var
                    break

            if matched_var is not None:
                matched_var.assign(val)
                assigned.add(id(matched_var))
            else:
                unmatched.append((wn, val))

        if unmatched:
            trainable_vars = []
            non_trainable_vars = []
            for leaf in all_leaves:
                for var in leaf.trainable_weights:
                    if id(var) not in assigned:
                        trainable_vars.append(var)
                for var in leaf.non_trainable_weights:
                    if id(var) not in assigned:
                        non_trainable_vars.append(var)
            rem_vars = trainable_vars + non_trainable_vars
            for (_, val), var in zip(unmatched, rem_vars):
                var.assign(val)

    def _apply_step(x, layer):
        y = layer(x)
        return y[0] if isinstance(y, (list, tuple)) else y

    with h5py.File(model_path, "r") as f:
        raw_cfg = f.attrs["model_config"]
        if isinstance(raw_cfg, bytes):
            raw_cfg = raw_cfg.decode("utf-8")
        cfg = _strip_groups(json.loads(raw_cfg))
        weights_group = f["model_weights"]

        inp = tf.keras.Input(shape=_find_input_shape(cfg))
        x = inp
        pending_weights = []

        with saving_options.keras_option_scope(use_legacy_config=True):
            for sub_cfg in cfg.get("config", {}).get("layers", []):
                if sub_cfg.get("class_name") == "InputLayer":
                    continue
                sub_name = sub_cfg.get("config", {}).get("name")
                loaded_sub = None
                try:
                    cand = saving_utils.model_from_config(sub_cfg)
                    x = _apply_step(x, cand)
                    loaded_sub = [cand]
                except Exception:
                    if sub_cfg.get("class_name") == "Sequential":
                        inner_list = []
                        for inner_cfg in sub_cfg.get("config", {}).get("layers", []):
                            if inner_cfg.get("class_name") == "InputLayer":
                                continue
                            inner_obj = saving_utils.model_from_config(inner_cfg)
                            x = _apply_step(x, inner_obj)
                            inner_list.append(inner_obj)
                        loaded_sub = inner_list
                    else:
                        raise
                if sub_name and sub_name in weights_group and loaded_sub:
                    pending_weights.append((weights_group[sub_name], loaded_sub))

        model = tf.keras.Model(inputs=inp, outputs=x)
        for grp, targets in pending_weights:
            _assign_group_weights(grp, targets)
        return model


@st.cache_resource(show_spinner=False)
def load_object_detector():
    from ultralytics import YOLO

    return YOLO("yolov5su.pt")


@st.cache_data(show_spinner=False)
def load_labels(labels_path: str) -> list[str]:
    p = Path(labels_path)
    if not p.exists():
        return ["Alguien", "Nadie"]
    labels = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        labels.append(parts[1].strip() if len(parts) == 2 else parts[0])
    return labels or ["Alguien", "Nadie"]


def predict_tm(model, pil_img: Image.Image) -> tuple[np.ndarray, float]:
    t0 = time.perf_counter()
    rgb = ImageOps.fit(pil_img.convert("RGB"), (224, 224), Image.Resampling.LANCZOS)
    arr = np.asarray(rgb, dtype=np.float32)
    normalized = (arr / 127.5) - 1.0
    batch = np.expand_dims(normalized, axis=0)
    preds = np.asarray(model(batch, training=False))[0]
    return preds, (time.perf_counter() - t0) * 1000.0


def detect_scene_objects(detector, pil_img: Image.Image, conf: float):
    np_bgr = np.array(pil_img.convert("RGB"))[..., ::-1]
    res = detector(np_bgr, conf=conf, iou=0.45, max_det=50, verbose=False)[0]
    counts = {}
    if res.boxes is not None:
        for box in res.boxes:
            raw_name = detector.names[int(box.cls.item())]
            es_name = translate_label(raw_name)
            counts[es_name] = counts.get(es_name, 0) + 1
    annotated_rgb = res.plot()[:, :, ::-1]
    return annotated_rgb, counts


def read_wokwi_file(filename: str, fallback: str) -> str:
    p = ROOT / "wokwi" / filename
    return p.read_text(encoding="utf-8") if p.exists() else fallback


st.markdown(
    """
<div class="eq-header">
  <h1 class="eq-title">Clasificación y objetos</h1>
  <p class="eq-subtitle">Detecta presencia con tu modelo y objetos del entorno en una misma captura.</p>
</div>
    """,
    unsafe_allow_html=True,
)

render_hud()
render_mission_bar("tm")
st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

s1, s2, s3 = st.columns(3, gap="medium")
with s1:
    st.markdown(
        f"""
<div class="eq-step">
  {svg_step_frame()}
  <div>
    <span class="eq-step-num">01</span>
    <p class="eq-step-title">Encuadra</p>
    <p class="eq-step-text">Incluye el objeto de la misión en la escena.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
with s2:
    st.markdown(
        f"""
<div class="eq-step">
  {svg_step_capture()}
  <div>
    <span class="eq-step-num">02</span>
    <p class="eq-step-title">Captura</p>
    <p class="eq-step-text">Se evalúan presencia y objetos al instante.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
with s3:
    st.markdown(
        f"""
<div class="eq-step">
  {svg_step_result()}
  <div>
    <span class="eq-step-num">03</span>
    <p class="eq-step-title">Progreso</p>
    <p class="eq-step-text">Completa misiones y desbloquea la colección.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)

model_file = ROOT / "keras_model.h5"
labels_file = ROOT / "labels.txt"
if not model_file.exists():
    st.error("No se encontró `keras_model.h5` en la raíz del repositorio.")
    st.stop()

with st.spinner("Cargando modelos..."):
    tm_model = load_keras_model(str(model_file))
    detector = load_object_detector()
labels = load_labels(str(labels_file))

col_in, col_out = st.columns([1.05, 0.95], gap="large")

raw_bytes = None
pil_input = None

with col_in:
    st.markdown(
        """
<div class="eq-frame" style="margin-bottom:0.7rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <span style="font-size:0.86rem;color:#8B929E;">Entrada de imagen</span>
</div>
        """,
        unsafe_allow_html=True,
    )
    source = st.radio("Origen", ["Cámara", "Archivo"], horizontal=True, label_visibility="collapsed")
    conf_slider = st.slider("Sensibilidad de objetos", 0.10, 0.90, 0.28, 0.02)

    if source == "Cámara":
        cam_img = st.camera_input("Toma una foto", label_visibility="collapsed")
        if cam_img is not None:
            raw_bytes = cam_img.getvalue()
            pil_input = Image.open(io.BytesIO(raw_bytes))
    else:
        up_img = st.file_uploader(
            "Sube una imagen",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )
        if up_img is not None:
            raw_bytes = up_img.getvalue()
            pil_input = Image.open(io.BytesIO(raw_bytes))

with col_out:
    if pil_input is None or raw_bytes is None:
        pills = "".join(f'<span class="eq-pill">{i} · {lbl}</span>' for i, lbl in enumerate(labels))
        st.markdown(
            f"""
<div class="eq-idle">
  {svg_idle_reticle()}
  <p>Esperando una imagen para analizar.</p>
  <div style="margin-top:0.85rem;">{pills}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        preds, elapsed_ms = predict_tm(tm_model, pil_input)
        annotated_rgb, obj_counts = detect_scene_objects(detector, pil_input, conf_slider)

        n_classes = min(len(labels), len(preds))
        scores = [(i, labels[i], float(preds[i])) for i in range(n_classes)]
        top_idx, top_label, top_conf = max(scores, key=lambda x: x[2])

        st.session_state["tm_last_idx"] = top_idx
        st.session_state["tm_last_label"] = top_label

        events = register_scan(
            raw_bytes,
            list(obj_counts.keys()),
            tm_idx=top_idx,
            tm_label=top_label,
        )
        for ev in events:
            st.markdown(f'<div class="eq-event">{ev}</div>', unsafe_allow_html=True)

        st.markdown(
            f"""
<div class="eq-result-box">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <p style="font-size:0.76rem;color:#8B929E;margin:0 0 0.25rem 0;text-transform:uppercase;letter-spacing:0.08em;">Estado detectado</p>
  <p class="eq-result-label">{top_label}</p>
  <p class="eq-result-meta">{top_conf * 100:.1f} % · {elapsed_ms:.0f} ms</p>
</div>
            """,
            unsafe_allow_html=True,
        )

        bars_html = ['<div class="eq-frame" style="margin-bottom:0.9rem;">']
        for idx, name, prob in sorted(scores, key=lambda x: x[2], reverse=True):
            pct = max(0.0, min(100.0, prob * 100.0))
            cls = "is-top" if idx == top_idx else ""
            bars_html.append(
                f"""
<div class="eq-bar-row">
  <div class="eq-bar-head">
    <span class="eq-bar-name">{name}</span>
    <span class="eq-bar-pct">{pct:.1f} %</span>
  </div>
  <div class="eq-bar-track">
    <div class="eq-bar-fill {cls}" style="width:{pct:.1f}%;"></div>
  </div>
</div>
                """
            )
        bars_html.append("</div>")
        st.markdown("".join(bars_html), unsafe_allow_html=True)

        st.image(annotated_rgb, width="stretch")

        if obj_counts:
            obj_pills = "".join(
                f'<span class="eq-pill">{name} × {cnt}</span>'
                for name, cnt in sorted(obj_counts.items(), key=lambda x: x[1], reverse=True)
            )
            st.markdown(
                f"""
<div class="eq-frame" style="margin-top:0.75rem;">
  <p style="margin:0 0 0.4rem 0;font-size:0.84rem;color:#8B929E;">Objetos detectados en escena</p>
  <div>{obj_pills}</div>
</div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No se detectaron objetos adicionales. Reduce la sensibilidad si deseas ampliar la búsqueda.")

st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
render_collection_grid()

# ---------------------------------------------------------------------------
# Simulación en Wokwi (proyecto fijo 480802023080679425)
# ---------------------------------------------------------------------------
st.markdown('<hr class="eq-divider">', unsafe_allow_html=True)
st.markdown(
    f"""
<div class="eq-header" style="margin-bottom:0.9rem;">
  <h2 style="font-size:1.35rem;font-weight:600;margin:0 0 0.25rem 0;">Circuito en Wokwi</h2>
  <p class="eq-subtitle">Simulador integrado ({WOKWI_PROJECT_ID}) y código actualizado para Alguien / Nadie.</p>
</div>
    """,
    unsafe_allow_html=True,
)

DEFAULT_INO = """#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

const int LED_ALGUIEN = 8;
const int LED_NADIE   = 9;
const int BTN_ALGUIEN = 2;
const int BTN_NADIE   = 3;

int estado = -1;

void aplicarEstado(int nuevo) {
  if (nuevo == estado) return;
  estado = nuevo;
  lcd.clear();
  lcd.setCursor(0, 0);
  if (estado == 0) {
    digitalWrite(LED_ALGUIEN, HIGH);
    digitalWrite(LED_NADIE, LOW);
    lcd.print("Estado: 0");
    lcd.setCursor(0, 1);
    lcd.print("Alguien");
    Serial.println("Estado 0: Alguien");
  } else {
    digitalWrite(LED_ALGUIEN, LOW);
    digitalWrite(LED_NADIE, HIGH);
    lcd.print("Estado: 1");
    lcd.setCursor(0, 1);
    lcd.print("Nadie");
    Serial.println("Estado 1: Nadie");
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_ALGUIEN, OUTPUT);
  pinMode(LED_NADIE, OUTPUT);
  pinMode(BTN_ALGUIEN, INPUT_PULLUP);
  pinMode(BTN_NADIE, INPUT_PULLUP);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Listo");
  lcd.setCursor(0, 1);
  lcd.print("Envia 0 o 1");
}

void loop() {
  if (digitalRead(BTN_ALGUIEN) == LOW) {
    aplicarEstado(0);
    delay(200);
  }
  if (digitalRead(BTN_NADIE) == LOW) {
    aplicarEstado(1);
    delay(200);
  }
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '0') aplicarEstado(0);
    if (c == '1') aplicarEstado(1);
  }
}
"""

DEFAULT_DIAGRAM = """{
  "version": 1,
  "author": "Vision",
  "editor": "wokwi",
  "parts": [
    { "type": "wokwi-arduino-uno", "id": "uno", "top": 0, "left": 0, "attrs": {} },
    { "type": "wokwi-lcd1602", "id": "lcd1", "top": -150, "left": 290, "attrs": { "pins": "i2c" } },
    { "type": "wokwi-led", "id": "led0", "top": 60, "left": 330, "attrs": { "color": "cyan", "label": "Alguien" } },
    { "type": "wokwi-led", "id": "led1", "top": 60, "left": 390, "attrs": { "color": "red", "label": "Nadie" } },
    { "type": "wokwi-resistor", "id": "r0", "top": 140, "left": 325, "rotate": 90, "attrs": { "value": "220" } },
    { "type": "wokwi-resistor", "id": "r1", "top": 140, "left": 385, "rotate": 90, "attrs": { "value": "220" } },
    { "type": "wokwi-pushbutton", "id": "btn0", "top": 220, "left": 320, "attrs": { "color": "blue", "label": "0" } },
    { "type": "wokwi-pushbutton", "id": "btn1", "top": 220, "left": 400, "attrs": { "color": "red", "label": "1" } }
  ],
  "connections": [
    [ "uno:5V", "lcd1:VCC", "red", [ "v0" ] ],
    [ "uno:GND.2", "lcd1:GND", "black", [ "v0" ] ],
    [ "uno:A4", "lcd1:SDA", "green", [ "v0" ] ],
    [ "uno:A5", "lcd1:SCL", "yellow", [ "v0" ] ],
    [ "uno:8", "r0:1", "cyan", [ "v0" ] ],
    [ "r0:2", "led0:A", "cyan", [ "v0" ] ],
    [ "led0:C", "uno:GND.1", "black", [ "v0" ] ],
    [ "uno:9", "r1:1", "red", [ "v0" ] ],
    [ "r1:2", "led1:A", "red", [ "v0" ] ],
    [ "led1:C", "uno:GND.1", "black", [ "v0" ] ],
    [ "uno:2", "btn0:1.l", "blue", [ "v0" ] ],
    [ "btn0:2.l", "uno:GND.2", "black", [ "v0" ] ],
    [ "uno:3", "btn1:1.l", "orange", [ "v0" ] ],
    [ "btn1:2.l", "uno:GND.2", "black", [ "v0" ] ]
  ],
  "dependencies": {}
}
"""

sketch_code = read_wokwi_file("sketch.ino", DEFAULT_INO)
diagram_code = read_wokwi_file("diagram.json", DEFAULT_DIAGRAM)
libs_code = read_wokwi_file("libraries.txt", "LiquidCrystal I2C\n")

tab_sim, tab_ino, tab_diag, tab_libs = st.tabs(
    ["Simulador", "sketch.ino", "diagram.json", "libraries.txt"]
)

with tab_sim:
    last_idx = st.session_state.get("tm_last_idx")
    last_lbl = st.session_state.get("tm_last_label")
    signal_txt = f"{last_idx} · {last_lbl}" if last_idx is not None else "—"
    embed_url = f"https://wokwi.com/projects/{WOKWI_PROJECT_ID}?embed=1"

    st.markdown(
        f"""
<div class="eq-frame" style="padding:0.75rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:0.82rem;color:#8B929E;">Wokwi · #{WOKWI_PROJECT_ID}</span>
    <span class="eq-pill">Última lectura: {signal_txt}</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    components.html(
        f'<iframe src="{embed_url}" style="width:100%;height:540px;border:1px solid rgba(226,232,240,0.16);background:#090A0C;" allowfullscreen></iframe>',
        height=555,
    )

with tab_ino:
    st.code(sketch_code, language="cpp")
    st.download_button("Descargar sketch.ino", sketch_code, file_name="sketch.ino", mime="text/plain")

with tab_diag:
    st.code(diagram_code, language="json")
    st.download_button("Descargar diagram.json", diagram_code, file_name="diagram.json", mime="application/json")

with tab_libs:
    st.code(libs_code, language="text")
    st.download_button("Descargar libraries.txt", libs_code, file_name="libraries.txt", mime="text/plain")
