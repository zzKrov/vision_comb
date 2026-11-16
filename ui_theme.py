import hashlib
import random
import streamlit as st

WOKWI_PROJECT_ID = "480802023080679425"

COCO_ES = {
    "person": "Persona",
    "bicycle": "Bicicleta",
    "car": "Automóvil",
    "motorcycle": "Motocicleta",
    "airplane": "Avión",
    "bus": "Autobús",
    "train": "Tren",
    "truck": "Camión",
    "boat": "Bote",
    "traffic light": "Semáforo",
    "fire hydrant": "Hidrante",
    "stop sign": "Señal de pare",
    "parking meter": "Parquímetro",
    "bench": "Banca",
    "bird": "Pájaro",
    "cat": "Gato",
    "dog": "Perro",
    "horse": "Caballo",
    "sheep": "Oveja",
    "cow": "Vaca",
    "elephant": "Elefante",
    "bear": "Oso",
    "zebra": "Cebra",
    "giraffe": "Jirafa",
    "backpack": "Mochila",
    "umbrella": "Paraguas",
    "handbag": "Bolso",
    "tie": "Corbata",
    "suitcase": "Maleta",
    "frisbee": "Frisbee",
    "skis": "Esquís",
    "snowboard": "Tabla de nieve",
    "sports ball": "Balón",
    "kite": "Cometa",
    "baseball bat": "Bate",
    "baseball glove": "Guante",
    "skateboard": "Patineta",
    "surfboard": "Tabla de surf",
    "tennis racket": "Raqueta",
    "bottle": "Botella",
    "wine glass": "Copa",
    "cup": "Taza",
    "fork": "Tenedor",
    "knife": "Cuchillo",
    "spoon": "Cuchara",
    "bowl": "Tazón",
    "banana": "Banano",
    "apple": "Manzana",
    "sandwich": "Sándwich",
    "orange": "Naranja",
    "broccoli": "Brócoli",
    "carrot": "Zanahoria",
    "hot dog": "Perro caliente",
    "pizza": "Pizza",
    "donut": "Dona",
    "cake": "Pastel",
    "chair": "Silla",
    "couch": "Sofá",
    "potted plant": "Planta",
    "bed": "Cama",
    "dining table": "Mesa",
    "toilet": "Inodoro",
    "tv": "Televisor",
    "laptop": "Portátil",
    "mouse": "Ratón",
    "remote": "Control remoto",
    "keyboard": "Teclado",
    "cell phone": "Celular",
    "microwave": "Microondas",
    "oven": "Horno",
    "toaster": "Tostadora",
    "sink": "Lavabo",
    "refrigerator": "Refrigerador",
    "book": "Libro",
    "clock": "Reloj",
    "vase": "Jarrón",
    "scissors": "Tijeras",
    "teddy bear": "Peluche",
    "hair drier": "Secador",
    "toothbrush": "Cepillo",
}

MISSION_POOL = [
    "Persona",
    "Celular",
    "Taza",
    "Botella",
    "Portátil",
    "Libro",
    "Teclado",
    "Ratón",
    "Silla",
    "Mochila",
    "Reloj",
    "Control remoto",
    "Tijeras",
    "Manzana",
    "Banano",
    "Planta",
]

RANKS = [
    (0, "Observador"),
    (150, "Analista"),
    (400, "Especialista"),
    (800, "Maestro"),
]


def translate_label(raw_name: str) -> str:
    return COCO_ES.get(raw_name.lower(), raw_name.capitalize())


def init_game_state() -> None:
    defaults = {
        "gm_points": 0,
        "gm_streak": 0,
        "gm_scans": 0,
        "gm_unlocked": [],
        "gm_mission": "Celular",
        "gm_seen_hashes": [],
        "gm_last_events": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def next_mission() -> None:
    current = st.session_state.get("gm_mission", "Celular")
    choices = [m for m in MISSION_POOL if m != current]
    st.session_state["gm_mission"] = random.choice(choices)


def reset_game_state() -> None:
    st.session_state["gm_points"] = 0
    st.session_state["gm_streak"] = 0
    st.session_state["gm_scans"] = 0
    st.session_state["gm_unlocked"] = []
    st.session_state["gm_mission"] = random.choice(MISSION_POOL)
    st.session_state["gm_seen_hashes"] = []
    st.session_state["gm_last_events"] = []


def get_rank_info(points: int) -> tuple[str, int, int]:
    current_name = RANKS[0][1]
    current_floor = 0
    next_target = RANKS[1][0]
    for idx, (threshold, title) in enumerate(RANKS):
        if points >= threshold:
            current_name = title
            current_floor = threshold
            next_target = RANKS[idx + 1][0] if idx + 1 < len(RANKS) else threshold
    return current_name, current_floor, next_target


def register_scan(
    image_bytes: bytes,
    detected_objects: list[str],
    tm_label: str | None = None,
) -> list[str]:
    """Evalúa logros, desbloqueos y misión sin duplicar la misma imagen."""
    init_game_state()
    img_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    if img_hash in st.session_state["gm_seen_hashes"]:
        return st.session_state.get("gm_last_events", [])

    st.session_state["gm_seen_hashes"].append(img_hash)
    st.session_state["gm_scans"] += 1

    events = []
    gained = 0
    unique_objs = list(dict.fromkeys(detected_objects))

    if unique_objs or tm_label:
        gained += 15
        events.append("+15 pts · Lectura registrada")

    unlocked = st.session_state["gm_unlocked"]
    new_items = [obj for obj in unique_objs if obj not in unlocked]
    if new_items:
        unlocked.extend(new_items)
        bonus = 25 * len(new_items)
        gained += bonus
        events.append(f"+{bonus} pts · Descubierto: {', '.join(new_items)}")

    mission = st.session_state["gm_mission"]
    if mission in unique_objs:
        st.session_state["gm_streak"] += 1
        streak_bonus = min(50, (st.session_state["gm_streak"] - 1) * 15)
        total_m = 100 + streak_bonus
        gained += total_m
        events.append(f"+{total_m} pts · Misión completada ({mission})")
        next_mission()
    elif unique_objs:
        st.session_state["gm_streak"] = 0

    if tm_label and "sin" not in tm_label.lower() and "Persona" in unique_objs:
        gained += 40
        events.append(f"+40 pts · Coincidencia ({tm_label} + Persona)")

    st.session_state["gm_points"] += gained
    st.session_state["gm_last_events"] = events
    return events


def inject_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg: #090A0C;
  --surface: #111317;
  --surface-2: #161920;
  --border: rgba(226, 232, 240, 0.12);
  --border-strong: rgba(214, 228, 255, 0.42);
  --text: #F4F5F7;
  --muted: #8B929E;
  --accent: #D6E4FF;
  --ok: #9EC5FF;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
}

[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stDecoration"],
#MainMenu,
footer {
  display: none !important;
}

header[data-testid="stHeader"] {
  background: transparent !important;
  height: 0 !important;
  min-height: 0 !important;
  overflow: hidden !important;
}

.stApp {
  background-color: var(--bg);
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.022) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.022) 1px, transparent 1px);
  background-size: 64px 64px;
  color: var(--text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
  max-width: 1200px !important;
  padding-top: 1.4rem !important;
  padding-bottom: 3.5rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  animation: eqFadeUp 0.42s var(--ease) both;
}

@keyframes eqFadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.eq-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text);
}

.eq-brand-mark {
  width: 18px;
  height: 18px;
  border: 1px solid var(--accent);
  position: relative;
  display: inline-block;
  transition: transform 0.35s var(--ease);
}

.eq-brand-mark::after {
  content: "";
  position: absolute;
  inset: 4px;
  background: var(--accent);
}

.eq-brand:hover .eq-brand-mark {
  transform: rotate(90deg);
}

[data-testid="stPageLink-NavLink"] {
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  border-radius: 2px !important;
  padding: 0.45rem 0.9rem !important;
  transition: all 0.25s var(--ease) !important;
  justify-content: center !important;
}

[data-testid="stPageLink-NavLink"] p {
  font-size: 0.84rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.04em !important;
  color: var(--muted) !important;
  transition: color 0.25s var(--ease) !important;
}

[data-testid="stPageLink-NavLink"]:hover {
  border-color: var(--border-strong) !important;
  background: var(--surface-2) !important;
  transform: translateY(-1px);
}

[data-testid="stPageLink-NavLink"]:hover p {
  color: var(--text) !important;
}

[data-testid="stPageLink-NavLink"][aria-current="page"] {
  border-color: var(--accent) !important;
  background: rgba(214, 228, 255, 0.08) !important;
}

[data-testid="stPageLink-NavLink"][aria-current="page"] p {
  color: var(--accent) !important;
}

.eq-header { margin-bottom: 1.5rem; }

.eq-title {
  font-size: clamp(1.85rem, 3vw, 2.4rem);
  font-weight: 600;
  letter-spacing: -0.025em;
  line-height: 1.12;
  color: var(--text);
  margin: 0 0 0.4rem 0;
}

.eq-subtitle {
  font-size: 0.95rem;
  color: var(--muted);
  margin: 0;
}

.eq-hud {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 768px) {
  .eq-hud { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.eq-hud-cell {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 0.85rem 1rem;
  transition: border-color 0.25s var(--ease), transform 0.25s var(--ease);
}

.eq-hud-cell:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.eq-hud-k {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 0.2rem;
}

.eq-hud-v {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.08rem;
  font-weight: 500;
  color: var(--accent);
}

.eq-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 1.35rem;
  overflow: hidden;
  transition: transform 0.35s var(--ease), border-color 0.35s var(--ease), background-color 0.35s var(--ease);
}

.eq-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 20%, rgba(214, 228, 255, 0.05) 50%, transparent 80%);
  transform: translateX(-100%);
  transition: transform 0.7s var(--ease);
  pointer-events: none;
}

.eq-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-strong);
  background: var(--surface-2);
}

.eq-card:hover::before { transform: translateX(100%); }

.eq-card-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text);
  margin: 0.75rem 0 0.3rem 0;
}

.eq-card-desc {
  font-size: 0.88rem;
  color: var(--muted);
  line-height: 1.48;
  margin: 0;
}

.eq-frame {
  position: relative;
  border: 1px solid var(--border);
  background: var(--surface);
  padding: 1.15rem;
  transition: border-color 0.3s var(--ease);
}

.eq-frame:hover { border-color: rgba(214, 228, 255, 0.28); }

.eq-corner {
  position: absolute;
  width: 10px;
  height: 10px;
  pointer-events: none;
  transition: transform 0.3s var(--ease);
}

.eq-corner.tl { top: -1px; left: -1px; border-top: 2px solid var(--accent); border-left: 2px solid var(--accent); }
.eq-corner.tr { top: -1px; right: -1px; border-top: 2px solid var(--accent); border-right: 2px solid var(--accent); }
.eq-corner.bl { bottom: -1px; left: -1px; border-bottom: 2px solid var(--accent); border-left: 2px solid var(--accent); }
.eq-corner.br { bottom: -1px; right: -1px; border-bottom: 2px solid var(--accent); border-right: 2px solid var(--accent); }

.eq-frame:hover .eq-corner.tl, .eq-card:hover .eq-corner.tl { transform: translate(-2px, -2px); }
.eq-frame:hover .eq-corner.tr, .eq-card:hover .eq-corner.tr { transform: translate(2px, -2px); }
.eq-frame:hover .eq-corner.bl, .eq-card:hover .eq-corner.bl { transform: translate(-2px, 2px); }
.eq-frame:hover .eq-corner.br, .eq-card:hover .eq-corner.br { transform: translate(2px, 2px); }

.eq-step {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 0.95rem 1.05rem;
  display: flex;
  align-items: center;
  gap: 0.9rem;
  transition: border-color 0.3s var(--ease), transform 0.3s var(--ease);
}

.eq-step:hover {
  border-color: var(--border-strong);
  transform: translateY(-2px);
}

.eq-step-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: var(--accent);
  letter-spacing: 0.08em;
  display: block;
}

.eq-step-title { font-size: 0.92rem; font-weight: 600; color: var(--text); margin: 0 0 0.1rem 0; }
.eq-step-text { font-size: 0.81rem; color: var(--muted); margin: 0; line-height: 1.35; }

.eq-result-box {
  border: 1px solid var(--border-strong);
  background: linear-gradient(180deg, rgba(214, 228, 255, 0.06) 0%, var(--surface) 100%);
  padding: 1.2rem;
  margin-bottom: 0.9rem;
  position: relative;
}

.eq-result-label { font-size: 1.65rem; font-weight: 600; letter-spacing: -0.02em; color: var(--text); margin: 0; }
.eq-result-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: var(--accent); margin-top: 0.3rem; }

.eq-bar-row { margin-bottom: 0.78rem; }
.eq-bar-head { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.28rem; }
.eq-bar-name { color: var(--text); font-weight: 500; }
.eq-bar-pct { font-family: 'JetBrains Mono', monospace; color: var(--muted); }
.eq-bar-track { width: 100%; height: 6px; background: rgba(255, 255, 255, 0.07); overflow: hidden; }
.eq-bar-fill { height: 100%; background: var(--muted); transform-origin: left center; animation: eqBarReveal 0.6s var(--ease) both; }
.eq-bar-fill.is-top { background: var(--accent); }

@keyframes eqBarReveal {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}

.eq-idle {
  border: 1px dashed var(--border);
  background: var(--surface);
  padding: 2rem 1.2rem;
  text-align: center;
}

.eq-idle p { color: var(--muted); font-size: 0.88rem; margin: 0.65rem 0 0 0; }

.eq-pill {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--accent);
  border: 1px solid var(--border);
  background: var(--surface-2);
  padding: 0.24rem 0.6rem;
  margin: 0.22rem 0.2rem 0 0;
  transition: border-color 0.25s var(--ease), transform 0.25s var(--ease);
}

.eq-pill:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.eq-pill.is-locked {
  color: var(--muted);
  opacity: 0.55;
}

.eq-event {
  border-left: 2px solid var(--accent);
  background: rgba(214, 228, 255, 0.05);
  padding: 0.45rem 0.75rem;
  margin-bottom: 0.45rem;
  font-size: 0.84rem;
  color: var(--text);
  animation: eqFadeUp 0.35s var(--ease) both;
}

.eq-divider { border: none; border-top: 1px solid var(--border); margin: 2rem 0 1.4rem 0; }

@keyframes eqPulse {
  0%, 100% { opacity: 0.38; transform: scale(0.96); }
  50%      { opacity: 1;    transform: scale(1.03); }
}

@keyframes eqSpinSlow {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

@keyframes eqScanLine {
  0%, 100% { transform: translateY(-9px); opacity: 0.3; }
  50%      { transform: translateY(9px);  opacity: 1; }
}

@keyframes eqBalanceA {
  0%, 100% { width: 14px; }
  50%      { width: 26px; }
}

@keyframes eqBalanceB {
  0%, 100% { width: 26px; }
  50%      { width: 14px; }
}

.svg-pulse { transform-origin: center; animation: eqPulse 2.8s ease-in-out infinite; }
.svg-spin  { transform-origin: center; animation: eqSpinSlow 14s linear infinite; }
.svg-scan  { animation: eqScanLine 2.6s ease-in-out infinite; }
.svg-bar-a { animation: eqBalanceA 2.4s ease-in-out infinite; }
.svg-bar-b { animation: eqBalanceB 2.4s ease-in-out infinite; }

[data-testid="stCameraInput"] > div,
[data-testid="stFileUploader"] section {
  border: 1px solid var(--border) !important;
  border-radius: 2px !important;
  background: var(--surface) !important;
  transition: border-color 0.25s var(--ease) !important;
}

[data-testid="stCameraInput"] > div:hover,
[data-testid="stFileUploader"] section:hover {
  border-color: var(--border-strong) !important;
}

[data-testid="stCameraInput"] button,
.stButton > button,
.stDownloadButton > button {
  border-radius: 2px !important;
  border: 1px solid var(--border-strong) !important;
  background: var(--surface-2) !important;
  color: var(--text) !important;
  transition: all 0.25s var(--ease) !important;
}

[data-testid="stCameraInput"] button:hover,
.stButton > button:hover,
.stDownloadButton > button:hover {
  border-color: var(--accent) !important;
  background: rgba(214, 228, 255, 0.12) !important;
  transform: translateY(-1px);
}

.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { background: transparent; color: var(--muted); border-radius: 0; padding: 0.5rem 0.9rem; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 2px solid var(--accent) !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar() -> None:
    left, right = st.columns([1.2, 2.2], vertical_alignment="center")
    with left:
        st.markdown(
            """
<div class="eq-brand">
  <span class="eq-brand-mark"></span>
  <span>Visión</span>
</div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link("Inicio.py", label="Inicio", width="stretch")
        with c2:
            st.page_link("pages/1_Teachable_Machine.py", label="Clasificación", width="stretch")
        with c3:
            st.page_link("pages/2_YOLO.py", label="Exploración", width="stretch")

    st.markdown(
        '<hr style="border:none;border-top:1px solid rgba(226,232,240,0.12);margin:0.65rem 0 1.4rem 0;">',
        unsafe_allow_html=True,
    )


def render_hud() -> None:
    init_game_state()
    pts = st.session_state["gm_points"]
    streak = st.session_state["gm_streak"]
    unlocked = st.session_state["gm_unlocked"]
    mission = st.session_state["gm_mission"]
    rank, _, _ = get_rank_info(pts)

    st.markdown(
        f"""
<div class="eq-hud">
  <div class="eq-hud-cell">
    <span class="eq-hud-k">Puntos · {rank}</span>
    <span class="eq-hud-v">{pts}</span>
  </div>
  <div class="eq-hud-cell">
    <span class="eq-hud-k">Racha</span>
    <span class="eq-hud-v">{streak}</span>
  </div>
  <div class="eq-hud-cell">
    <span class="eq-hud-k">Colección</span>
    <span class="eq-hud-v">{len(unlocked)} / {len(COCO_ES)}</span>
  </div>
  <div class="eq-hud-cell">
    <span class="eq-hud-k">Misión actual</span>
    <span class="eq-hud-v">{mission}</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_mission_bar(key_prefix: str) -> None:
    init_game_state()
    mission = st.session_state["gm_mission"]
    c1, c2 = st.columns([3.2, 1], vertical_alignment="center")
    with c1:
        st.markdown(
            f"""
<div class="eq-step" style="padding:0.75rem 1rem;">
  {svg_target_reticle()}
  <div>
    <span class="eq-step-num">OBJETIVO ACTIVO · +100 PTS</span>
    <p class="eq-step-title" style="margin:0;">Encuentra: {mission}</p>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("Cambiar objetivo", key=f"{key_prefix}_new_mission", width="stretch"):
            next_mission()
            st.rerun()


def render_collection_grid() -> None:
    init_game_state()
    unlocked = set(st.session_state["gm_unlocked"])
    extra = sorted(unlocked - set(MISSION_POOL))
    catalog = MISSION_POOL + extra
    pills = []
    for item in catalog:
        if item in unlocked:
            pills.append(f'<span class="eq-pill">✓ {item}</span>')
        else:
            pills.append(f'<span class="eq-pill is-locked">· {item}</span>')
    st.markdown(
        f"""
<div class="eq-frame">
  <span class="eq-corner tl"></span><span class="eq-corner tr"></span>
  <span class="eq-corner bl"></span><span class="eq-corner br"></span>
  <p style="margin:0 0 0.55rem 0;font-size:0.85rem;color:#8B929E;">Objetos descubiertos</p>
  <div>{"".join(pills)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def svg_hero_emblem() -> str:
    return """
<svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="4" y="4" width="48" height="48" stroke="rgba(214,228,255,0.28)" stroke-width="1"/>
  <rect x="12" y="12" width="32" height="32" stroke="#D6E4FF" stroke-width="1.2" class="svg-pulse"/>
  <line x1="28" y1="2" x2="28" y2="54" stroke="rgba(214,228,255,0.45)" stroke-width="1"/>
  <line x1="2" y1="28" x2="54" y2="28" stroke="rgba(214,228,255,0.45)" stroke-width="1"/>
  <circle cx="28" cy="28" r="4" fill="#D6E4FF"/>
</svg>
"""


def svg_target_reticle() -> str:
    return """
<svg width="38" height="38" viewBox="0 0 38 38" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">
  <circle cx="19" cy="19" r="14" stroke="rgba(214,228,255,0.35)" stroke-width="1.2"/>
  <circle cx="19" cy="19" r="7" stroke="#D6E4FF" stroke-width="1.2" stroke-dasharray="3 3" class="svg-spin"/>
  <circle cx="19" cy="19" r="2.5" fill="#D6E4FF" class="svg-pulse"/>
</svg>
"""


def svg_step_frame() -> str:
    return """
<svg width="44" height="44" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">
  <path d="M5 13V5H13M33 5H41V13M41 33V41H33M13 41H5V33" stroke="#D6E4FF" stroke-width="1.5"/>
  <circle cx="23" cy="19" r="4.5" stroke="#8B929E" stroke-width="1.3"/>
  <path d="M14 33C14 28.5 18 26 23 26C28 26 32 28.5 32 33" stroke="#8B929E" stroke-width="1.3"/>
  <line x1="9" y1="23" x2="37" y2="23" stroke="#D6E4FF" stroke-width="1" class="svg-scan"/>
</svg>
"""


def svg_step_capture() -> str:
    return """
<svg width="44" height="44" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">
  <circle cx="23" cy="23" r="17" stroke="rgba(214,228,255,0.35)" stroke-width="1.2"/>
  <g class="svg-spin">
    <circle cx="23" cy="23" r="11" stroke="#D6E4FF" stroke-width="1.2" stroke-dasharray="5 4"/>
  </g>
  <circle cx="23" cy="23" r="4.2" fill="#D6E4FF" class="svg-pulse"/>
</svg>
"""


def svg_step_result() -> str:
    return """
<svg width="44" height="44" viewBox="0 0 46 46" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">
  <rect x="5" y="7" width="36" height="32" stroke="rgba(214,228,255,0.28)" stroke-width="1.2"/>
  <rect x="10" y="15" width="22" height="4" fill="#D6E4FF" class="svg-bar-a"/>
  <rect x="10" y="25" width="14" height="4" fill="#8B929E" class="svg-bar-b"/>
</svg>
"""


def svg_idle_reticle() -> str:
    return """
<svg width="56" height="56" viewBox="0 0 58 58" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="9" y="9" width="40" height="40" stroke="rgba(214,228,255,0.25)" stroke-width="1"/>
  <path d="M9 19V9H19M39 9H49V19M49 39V49H39M19 49H9V39" stroke="#D6E4FF" stroke-width="1.5" class="svg-pulse"/>
  <line x1="15" y1="29" x2="43" y2="29" stroke="#D6E4FF" stroke-width="1" class="svg-scan"/>
</svg>
"""
