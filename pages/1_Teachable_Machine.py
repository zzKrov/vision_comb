from pathlib import Path
import re
import time

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

from ui_theme import (
    inject_theme,
    render_topbar,
    svg_idle_reticle,
    svg_step_capture,
    svg_step_frame,
    svg_step_result,
)

# Pega aquí el ID numérico de tu proyecto en Wokwi si deseas que cargue por defecto
# Ejemplo: "437217078075500545"
DEFAULT_WOKWI_ID = ""

st.set_page_config(
    page_title="Clasificación · Visión",
    page_icon="◻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()
render_topbar(active="tm")

ROOT = Path(__file__).resolve().parent.parent


@st.cache_resource(show_spinner=False)
def load_keras_model(model_path: str):
    from keras.models import load_model

    return load_model(model_path, compile=False)


@st.cache_data(show_spinner=False)
def load_labels(labels_path: str) -> list[str]:
    p = Path(labels_path)
    if not p.exists():
        return ["Clase 0", "Clase 1"]
    labels = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        labels.append(parts[1].strip() if len(parts) == 2 else parts[0])
    return labels or ["Clase 0", "Clase 1"]


def predict_image(model, pil_img: Image.Image) -> tuple[np.ndarray, float]:
    t0 = time.perf_counter()
    rgb = ImageOps.fit(pil_img.convert("RGB"), (224, 224), Image.Resampling.LANCZOS)
    arr = np.asarray(rgb, dtype=np.float32)
    normalized = (arr / 127.5) - 1.0
    batch = np.expand_dims(normalized, axis=0)
    preds = model(batch, training=False).numpy()[0]
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return preds, elapsed_ms


def extract_wokwi_id(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    match = re.search(r"wokwi\.com/projects/(\d+)", raw)
    if match:
        return match.group(1)
    if raw.isdigit():
        return raw
    return ""


def read_wokwi_file(filename: str, fallback: str) -> str:
    p = ROOT / "wokwi" / filename
    return p.read_text(encoding="utf-8") if p.exists() else fallback


# Encabezado
st.markdown(
    """
<div class="eq-header">
  <h1 class="eq-title">Clasificación</h1>
  <p class="eq-subtitle">Compara una imagen con las clases guardadas en tu modelo.</p>
</div>
    """,
    unsafe_allow_html=True,
)

# Instrucciones con SVG animados
s1, s2, s3 = st.columns(3, gap="medium")
with s1:
    st.markdown(
        f"""
<div class="eq-step">
  {svg_step_frame()}
  <div>
    <span class="eq-step-num">01</span>
    <p class="eq-step-title">Encuadra</p>
    <p class="eq-step-text">Coloca el sujeto en el centro con buena luz.</p>
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
    <p class="eq-step-text">Usa la cámara o sube una fotografía.</p>
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
    <p class="eq-step-title">Resultado</p>
    <p class="eq-step-text">Revisa la clase principal y su porcentaje.</p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:1.4rem;'></div>", unsafe_allow_html=True)

# Cargar modelo y etiquetas
model_file = ROOT / "keras_model.h5"
labels_file = ROOT / "labels.txt"

if not model_file.exists():
    st.error("No se encontró `keras_model.h5` en la raíz del repositorio.")
    st.stop()

with st.spinner("Cargando modelo..."):
    model = load_keras_model(str(model_file))
labels = load_labels(str(labels_file))

# Zona principal: entrada y resultado
col_in, col_out = st.columns([1.05, 0.95], gap="large")

pil_input = None
with col_in:
    st.markdown(
        """
<div class="eq-frame" style="margin-bottom:0.75rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <span style="font-size:0.86rem;color:#8B929E;">Entrada de imagen</span>
</div>
        """,
        unsafe_allow_html=True,
    )
    source = st.radio(
        "Origen",
        ["Cámara", "Archivo"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if source == "Cámara":
        cam_img = st.camera_input("Toma una foto", label_visibility="collapsed")
        if cam_img is not None:
            pil_input = Image.open(cam_img)
    else:
        up_img = st.file_uploader(
            "Sube una imagen",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )
        if up_img is not None:
            pil_input = Image.open(up_img)
            st.image(pil_input, width="stretch")

with col_out:
    if pil_input is None:
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
        preds, elapsed_ms = predict_image(model, pil_input)
        n_classes = min(len(labels), len(preds))
        scores = [(i, labels[i], float(preds[i])) for i in range(n_classes)]
        top_idx, top_label, top_conf = max(scores, key=lambda x: x[2])

        st.session_state["tm_last_idx"] = top_idx
        st.session_state["tm_last_label"] = top_label
        st.session_state["tm_last_conf"] = top_conf

        st.markdown(
            f"""
<div class="eq-result-box">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <p style="font-size:0.78rem;color:#8B929E;margin:0 0 0.25rem 0;text-transform:uppercase;letter-spacing:0.08em;">Clase detectada</p>
  <p class="eq-result-label">{top_label}</p>
  <p class="eq-result-meta">{top_conf * 100:.1f} % · {elapsed_ms:.0f} ms</p>
</div>
            """,
            unsafe_allow_html=True,
        )

        bars_html = ['<div class="eq-frame">']
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

# ---------------------------------------------------------------------------
# Sección Wokwi en marco propio
# ---------------------------------------------------------------------------
st.markdown('<hr class="eq-divider">', unsafe_allow_html=True)
st.markdown(
    """
<div class="eq-header" style="margin-bottom:1rem;">
  <h2 style="font-size:1.35rem;font-weight:600;margin:0 0 0.25rem 0;">Simulación en Wokwi</h2>
  <p class="eq-subtitle">Integra tu circuito en esta página pegando su enlace o ID, o usa los archivos incluidos.</p>
</div>
    """,
    unsafe_allow_html=True,
)

default_val = st.secrets.get("WOKWI_PROJECT_ID", DEFAULT_WOKWI_ID) if hasattr(st, "secrets") else DEFAULT_WOKWI_ID
wokwi_input = st.text_input(
    "Enlace o ID del proyecto en Wokwi",
    value=default_val,
    placeholder="https://wokwi.com/projects/437217078075500545",
)
wokwi_id = extract_wokwi_id(wokwi_input)

DEFAULT_INO = """#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

const int LED_CARLOS = 8;
const int LED_OTRO   = 9;
const int BTN_CARLOS = 2;
const int BTN_OTRO   = 3;

int estado = -1;

void aplicarEstado(int nuevo) {
  if (nuevo == estado) return;
  estado = nuevo;
  lcd.clear();
  lcd.setCursor(0, 0);
  if (estado == 0) {
    digitalWrite(LED_CARLOS, HIGH);
    digitalWrite(LED_OTRO, LOW);
    lcd.print("Clase: 0");
    lcd.setCursor(0, 1);
    lcd.print("Carlos");
    Serial.println("Estado 0: Carlos");
  } else {
    digitalWrite(LED_CARLOS, LOW);
    digitalWrite(LED_OTRO, HIGH);
    lcd.print("Clase: 1");
    lcd.setCursor(0, 1);
    lcd.print("Sin Carlos");
    Serial.println("Estado 1: Sin Carlos");
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_CARLOS, OUTPUT);
  pinMode(LED_OTRO, OUTPUT);
  pinMode(BTN_CARLOS, INPUT_PULLUP);
  pinMode(BTN_OTRO, INPUT_PULLUP);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Listo");
  lcd.setCursor(0, 1);
  lcd.print("Envia 0 o 1");
}

void loop() {
  if (digitalRead(BTN_CARLOS) == LOW) {
    aplicarEstado(0);
    delay(200);
  }
  if (digitalRead(BTN_OTRO) == LOW) {
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
    { "type": "wokwi-led", "id": "led0", "top": 60, "left": 330, "attrs": { "color": "cyan", "label": "Carlos" } },
    { "type": "wokwi-led", "id": "led1", "top": 60, "left": 390, "attrs": { "color": "red", "label": "Sin Carlos" } },
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
    last_idx = st.session_state.get("tm_last_idx", None)
    last_lbl = st.session_state.get("tm_last_label", "Sin lectura")

    if wokwi_id:
        embed_url = f"https://wokwi.com/projects/{wokwi_id}?embed=1"
        st.markdown(
            f"""
<div class="eq-frame" style="padding:0.75rem;">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
    <span style="font-size:0.82rem;color:#8B929E;">Proyecto #{wokwi_id}</span>
    <span class="eq-pill">Señal actual: {f"{last_idx} · {last_lbl}" if last_idx is not None else "—"}</span>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        components.html(
            f'<iframe src="{embed_url}" style="width:100%;height:520px;border:1px solid rgba(226,232,240,0.16);background:#090A0C;" allowfullscreen></iframe>',
            height=535,
        )
    else:
        led0_fill = "#9EC5FF" if last_idx == 0 else "#252932"
        led1_fill = "#E07A7A" if last_idx == 1 else "#252932"
        lcd_line1 = f"Clase: {last_idx}" if last_idx is not None else "Esperando"
        lcd_line2 = last_lbl[:16] if last_idx is not None else "Envia 0 o 1"

        st.markdown(
            f"""
<div class="eq-frame">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <div style="display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center;justify-content:space-between;">
    <div style="flex:1;min-width:240px;">
      <p style="margin:0 0 0.4rem 0;font-weight:600;">Vista previa del circuito</p>
      <p style="margin:0;color:#8B929E;font-size:0.88rem;line-height:1.5;">
        Crea un proyecto en Wokwi con <code>sketch.ino</code>, <code>diagram.json</code> y <code>libraries.txt</code>,
        y pega el enlace arriba para ver el simulador real dentro de este marco.
      </p>
    </div>
    <svg width="290" height="110" viewBox="0 0 290 110" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="8" width="168" height="94" stroke="rgba(214,228,255,0.28)" fill="#0D1117"/>
      <rect x="12" y="20" width="148" height="70" fill="#122132" stroke="rgba(158,197,255,0.4)"/>
      <text x="22" y="48" fill="#D6E4FF" font-family="JetBrains Mono, monospace" font-size="13">{lcd_line1}</text>
      <text x="22" y="72" fill="#9EC5FF" font-family="JetBrains Mono, monospace" font-size="13">{lcd_line2}</text>
      <circle cx="215" cy="40" r="12" fill="{led0_fill}" stroke="rgba(214,228,255,0.35)"/>
      <text x="206" y="70" fill="#8B929E" font-family="JetBrains Mono, monospace" font-size="11">0</text>
      <circle cx="260" cy="40" r="12" fill="{led1_fill}" stroke="rgba(214,228,255,0.35)"/>
      <text x="251" y="70" fill="#8B929E" font-family="JetBrains Mono, monospace" font-size="11">1</text>
    </svg>
  </div>
</div>
            """,
            unsafe_allow_html=True,
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
