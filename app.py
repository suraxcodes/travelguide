
import streamlit as st
import asyncio

try:
    import nest_asyncio
    nest_asyncio.apply()  # Allows asyncio.run() inside Streamlit's event loop
except ImportError:
    pass  # nest_asyncio not installed; asyncio.run() may raise on some setups

try:
    from GoaInsight import smart_content_generation as _smart_content_generation
    _BACKEND_AVAILABLE = True
except ImportError:
    _BACKEND_AVAILABLE = False

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GoaInsight: AI Travel Guide",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── MASTER CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&family=Rajdhani:wght@300;400;500;600&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --cyan:#00f5ff; --pink:#ff2d78; --green:#39ff14; --yellow:#ffe600;
  --bg0:#020408;  --bg1:#060d14;  --bg2:#0a1520;
  --border:rgba(0,245,255,0.15); --glow-c:rgba(0,245,255,0.35);
}
.stApp{background:var(--bg0);font-family:'Rajdhani',sans-serif;color:rgba(255,255,255,0.8)}
.stApp::before{content:'';position:fixed;inset:0;z-index:999;pointer-events:none;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.07) 2px,rgba(0,0,0,0.07) 4px)}
.stApp::after{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:linear-gradient(rgba(0,245,255,0.025) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,245,255,0.025) 1px,transparent 1px);
  background-size:44px 44px}
.block-container{padding:0!important;max-width:100%!important}
section[data-testid="stSidebar"]{display:none!important}
.stDeployButton{display:none}
header[data-testid="stHeader"]{display:none}

/* topbar */
.topbar{position:sticky;top:0;z-index:200;background:rgba(2,4,8,0.96);
  border-bottom:1px solid var(--cyan);
  box-shadow:0 0 28px rgba(0,245,255,0.1),inset 0 -1px 0 var(--cyan);
  padding:0 28px;display:flex;align-items:center;justify-content:space-between;height:52px}
.topbar-logo{font-family:'Orbitron',monospace;font-size:1.05rem;font-weight:900;
  letter-spacing:0.12em;color:var(--cyan);
  text-shadow:0 0 14px var(--cyan),0 0 30px rgba(0,245,255,0.4);
  display:flex;align-items:center;gap:10px}
.slash{color:var(--pink)}
.topbar-status{display:flex;align-items:center;gap:20px}
.status-pill{display:flex;align-items:center;gap:6px;
  font-family:'Share Tech Mono',monospace;font-size:0.68rem;letter-spacing:0.1em;
  color:rgba(255,255,255,0.4)}
.status-dot{width:6px;height:6px;border-radius:50%}
.status-dot.active{background:var(--green);box-shadow:0 0 8px var(--green);animation:blink 2s infinite}
.status-dot.warn{background:var(--yellow);box-shadow:0 0 8px var(--yellow)}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.topbar-time{font-family:'Share Tech Mono',monospace;font-size:0.72rem;color:var(--cyan);letter-spacing:0.1em}

/* panel */
.panel::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:0.35}
.panel-header{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid rgba(0,245,255,0.1)}
.panel-title{font-family:'Orbitron',monospace;font-size:0.8rem;font-weight:700;
  letter-spacing:0.18em;color:var(--cyan);text-transform:uppercase;
  text-shadow:0 0 8px rgba(0,245,255,0.5)}
.panel-badge{font-family:'Share Tech Mono',monospace;font-size:0.6rem;
  color:rgba(255,255,255,0.25);border:1px solid rgba(255,255,255,0.1);
  padding:2px 8px;border-radius:2px}

/* inputs */
.stTextInput>div>div{background:rgba(0,245,255,0.03)!important;
  border:1px solid rgba(0,245,255,0.25)!important;border-radius:4px!important;
  color:var(--cyan)!important;font-family:'Share Tech Mono',monospace!important;
  font-size:0.82rem!important;transition:all .2s!important}
.stTextInput>div>div:focus-within{border-color:var(--cyan)!important;
  box-shadow:0 0 0 1px var(--cyan),0 0 20px rgba(0,245,255,0.15)!important}
.stTextInput input{color:var(--cyan)!important}
.stTextInput input::placeholder{color:rgba(0,245,255,0.25)!important}
.stTextArea>div>div{background:rgba(0,245,255,0.02)!important;
  border:1px solid rgba(0,245,255,0.15)!important;border-radius:4px!important;
  color:rgba(255,255,255,0.65)!important;font-family:'Rajdhani',sans-serif!important}

/* buttons */
.stButton>button{background:transparent!important;border:1px solid var(--cyan)!important;
  color:var(--cyan)!important;font-family:'Orbitron',monospace!important;
  font-size:0.62rem!important;font-weight:700!important;letter-spacing:0.14em!important;
  text-transform:uppercase!important;border-radius:3px!important;padding:10px 20px!important;
  transition:all .2s!important;text-shadow:0 0 8px var(--cyan)!important;
  box-shadow:0 0 12px rgba(0,245,255,0.15),inset 0 0 12px rgba(0,245,255,0.03)!important}
.stButton>button:hover{background:rgba(0,245,255,0.08)!important;
  box-shadow:0 0 24px rgba(0,245,255,0.4),inset 0 0 20px rgba(0,245,255,0.06)!important;
  transform:translateY(-1px)!important}
.stButton>button[kind="secondary"]{border-color:var(--pink)!important;color:var(--pink)!important;
  text-shadow:0 0 8px var(--pink)!important;box-shadow:0 0 12px rgba(255,45,120,0.15)!important}
.stButton>button[kind="secondary"]:hover{background:rgba(255,45,120,0.07)!important;
  box-shadow:0 0 24px rgba(255,45,120,0.35)!important}

/* chat */
.bubble-user{background:rgba(255,45,120,0.08);border:1px solid rgba(255,45,120,0.3);
  border-radius:2px 12px 12px 12px;padding:12px 16px;margin:8px 0;
  color:rgba(255,255,255,0.85);font-size:0.88rem;font-family:'Rajdhani',sans-serif;
  line-height:1.5;text-align:right;box-shadow:0 0 12px rgba(255,45,120,0.1);
  animation:fadeIn .25s ease}
.bubble-ai{background:rgba(0,245,255,0.04);border:1px solid rgba(0,245,255,0.2);
  border-radius:12px 12px 12px 2px;padding:12px 16px;margin:8px 0;
  color:rgba(255,255,255,0.8);font-size:0.88rem;font-family:'Rajdhani',sans-serif;
  line-height:1.5;box-shadow:0 0 12px rgba(0,245,255,0.08);animation:fadeIn .25s ease}
.bubble-ai .ai-label{font-family:'Share Tech Mono',monospace;font-size:0.6rem;
  color:var(--cyan);letter-spacing:0.12em;display:block;margin-bottom:6px}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.stChatInput>div{background:rgba(0,245,255,0.03)!important;
  border:1px solid rgba(0,245,255,0.2)!important;border-radius:4px!important}
.stChatInput textarea{color:rgba(255,255,255,0.8)!important;font-family:'Rajdhani',sans-serif!important}

/* widgets */
.widget{background:var(--bg2);border:1px solid rgba(0,245,255,0.1);border-radius:4px;
  padding:14px 16px;margin-bottom:10px;position:relative;transition:all .2s}
.widget:hover{border-color:rgba(0,245,255,0.3);box-shadow:0 0 16px rgba(0,245,255,0.08)}
.widget-label{font-family:'Share Tech Mono',monospace;font-size:0.6rem;
  color:rgba(255,255,255,0.3);letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px}
.widget-value{font-family:'Orbitron',monospace;font-size:1.1rem;color:var(--cyan);
  text-shadow:0 0 10px rgba(0,245,255,0.5)}
.widget-sub{font-size:0.75rem;color:rgba(255,255,255,0.35);margin-top:3px}
.widget.pink .widget-value{color:var(--pink);text-shadow:0 0 10px rgba(255,45,120,0.5)}
.widget.green .widget-value{color:var(--green);text-shadow:0 0 10px rgba(57,255,20,0.4)}
.widget.yellow .widget-value{color:var(--yellow);text-shadow:0 0 10px rgba(255,230,0,0.4)}

/* tags */
.tag{display:inline-block;padding:3px 10px;margin:3px;
  border:1px solid rgba(0,245,255,0.25);background:rgba(0,245,255,0.05);
  color:var(--cyan);border-radius:2px;font-family:'Share Tech Mono',monospace;
  font-size:0.65rem;letter-spacing:0.06em}
.tag.pink{border-color:rgba(255,45,120,0.3);background:rgba(255,45,120,0.05);color:var(--pink)}
.tag.green{border-color:rgba(57,255,20,0.3);background:rgba(57,255,20,0.05);color:var(--green)}
.tag.insight{border-color:var(--cyan);background:rgba(0,245,255,0.1);color:var(--cyan);text-shadow:0 0 5px var(--cyan)}

/* flags */
.flag-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.flag-chip{display:flex;align-items:center;gap:8px;padding:8px 12px;
  background:var(--bg2);border:1px solid rgba(255,255,255,0.06);border-radius:3px;font-size:0.78rem}
.flag-chip .icon{font-size:1rem}
.flag-chip .name{color:rgba(255,255,255,0.45);flex:1}
.flag-chip .val{font-family:'Share Tech Mono',monospace;font-size:0.65rem}
.flag-chip.on{border-color:rgba(57,255,20,0.2)}
.flag-chip.on .val{color:var(--green);text-shadow:0 0 6px var(--green)}
.flag-chip.off .val{color:rgba(255,255,255,0.18)}

/* map */
.map-shell{border:1px solid rgba(0,245,255,0.2);border-radius:4px;overflow:hidden;
  box-shadow:0 0 30px rgba(0,245,255,0.08)}
.map-hud{background:rgba(2,4,8,0.9);padding:10px 16px;
  border-bottom:1px solid rgba(0,245,255,0.15);
  display:flex;justify-content:space-between;align-items:center}
.map-hud-title{font-family:'Orbitron',monospace;font-size:0.65rem;color:var(--cyan);letter-spacing:0.12em}
.map-hud-coords{font-family:'Share Tech Mono',monospace;font-size:0.65rem;color:rgba(57,255,20,0.8)}
.map-shell iframe{width:100%;height:300px;border:none;display:block;
  filter:saturate(0.45) hue-rotate(160deg) brightness(0.65) contrast(1.25)}
.map-footer{background:rgba(2,4,8,0.9);padding:6px 16px;text-align:right}
.map-footer a{font-family:'Share Tech Mono',monospace;font-size:0.62rem;
  color:rgba(0,245,255,0.5);text-decoration:none}

/* transport */
.transport-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.t-item{background:var(--bg2);border:1px solid rgba(255,255,255,0.06);
  border-radius:3px;padding:10px;display:flex;align-items:center;justify-content:space-between}
.t-item .t-label{font-size:0.78rem;color:rgba(255,255,255,0.4)}
.t-item .t-val{font-family:'Share Tech Mono',monospace;font-size:0.72rem}
.t-item.on{border-color:rgba(57,255,20,0.25)}
.t-item.on .t-val{color:var(--green)}
.t-item.off .t-val{color:rgba(255,255,255,0.18)}

::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--bg0)}
::-webkit-scrollbar-thumb{background:rgba(0,245,255,0.25);border-radius:2px}
.stSpinner>div{border-top-color:var(--cyan)!important}
.stAlert{background:rgba(0,245,255,0.04)!important;border:1px solid rgba(0,245,255,0.2)!important;
  border-radius:4px!important;color:rgba(255,255,255,0.65)!important;font-family:'Rajdhani',sans-serif!important}
label{color:rgba(255,255,255,0.35)!important;font-family:'Rajdhani',sans-serif!important}
.stImage img{border:1px solid rgba(0,245,255,0.2)!important;border-radius:4px!important;
  filter:saturate(0.85) contrast(1.05)}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'output' not in st.session_state:
    st.session_state.output = {}

out = st.session_state.output

# ── TOPBAR ────────────────────────────────────────────────────────────────────
st.markdown("""

""", unsafe_allow_html=True)

# ── 3-COLUMN DASHBOARD ────────────────────────────────────────────────────────
left, center, right = st.columns([1.1, 2.8, 1.3], gap="small")

# ╔═══════════ LEFT ═══════════╗
with left:
    st.markdown('<div class="panel" style="border-right:1px solid rgba(0,245,255,0.1)">', unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-bottom:22px">
      <div style="font-family:'Share Tech Mono',monospace;font-size:0.58rem;
        color:rgba(0,245,255,0.4);letter-spacing:0.16em;margin-bottom:6px">INPUT NODE</div>
      <div style="font-family:'Orbitron',monospace;font-size:1rem;font-weight:900;
        color:#fff;letter-spacing:0.06em;line-height:1.25">
        GOA<br><span style="color:#00f5ff;text-shadow:0 0 14px #00f5ff">INSIGHT</span>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="panel-header"><span class="panel-title">⌖ SCAN DESTINATION</span></div>', unsafe_allow_html=True)
    topic = st.text_input("dest", placeholder="ENTER Location", label_visibility="collapsed")
    details = st.text_area("ctx", placeholder="Additional info", height=60, label_visibility="collapsed")
    c1, c2 = st.columns(2)
    with c1: scan_btn = st.button("⬡ SCAN", use_container_width=True)
    with c2: clear_btn = st.button("↺ CLR", type="secondary", use_container_width=True)

    if clear_btn:
        for k in ['output','generated','content_type','goa_db']:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-header"><span class="panel-title">⬡ SYSTEM STATUS</span></div>', unsafe_allow_html=True)

    db_ok   = st.session_state.get('goa_db') is not None
    has_data= bool(out)
    ctype   = st.session_state.get('content_type','')

    st.markdown(f"""
    <div class="widget {'green' if db_ok else ''}">
      <div class="widget-label">MongoDB Node</div>
      <div class="widget-value">{'ONLINE' if db_ok else 'OFFLINE'}</div>
      <div class="widget-sub">{'Connection active' if db_ok else 'Fallback: JSON mode'}</div>
    </div>
    <div class="widget {'green' if has_data else ''}">
      <div class="widget-label">Data Buffer</div>
      <div class="widget-value">{'LOADED' if has_data else 'EMPTY'}</div>
      <div class="widget-sub">{'Destination ready' if has_data else 'Awaiting scan'}</div>
    </div>
    <div class="widget pink">
      <div class="widget-label">AI Engine</div>
      <div class="widget-value">READY</div>
      <div class="widget-sub">gpt-4o-mini active</div>
    </div>
    {"f'<div class=widget yellow><div class=widget-label>Content Type</div><div class=widget-value style=font-size:.82rem>' + ctype.upper() + '</div></div>'" if ctype else ''}
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ╔═══════════ CENTER ═══════════╗
with center:
    st.markdown('<div class="panel" style="">', unsafe_allow_html=True)

    # Chat
    st.markdown('<div class="panel-header"><span class="panel-title">⬡ GOAINSIGHT TERMINAL</span><span class="panel-badge">LIVE</span></div>', unsafe_allow_html=True)

    if not st.session_state.chat_messages:
        st.markdown("""
        <div style="text-align:center;padding:24px 20px;
          border:1px dashed rgba(0,245,255,0.1);border-radius:4px;margin-bottom:14px">
          <div style="font-family:'Share Tech Mono',monospace;font-size:0.72rem;
            color:rgba(0,245,255,0.22);letter-spacing:0.1em;line-height:2">
            > GOAINSIGHT AI TERMINAL READY<br>> ENTER QUERY TO BEGIN<br>> TYPE DESTINATION OR COMMAND_
          </div>
        </div>""", unsafe_allow_html=True)

    for m in st.session_state.chat_messages:
        css = "bubble-user" if m["role"] == "user" else "bubble-ai"
        label = '<span class="ai-label">INSIGHT·AI ></span>' if m["role"] == "assistant" else ""
        st.markdown(f'<div class="{css}">{label}{m["content"]}</div>', unsafe_allow_html=True)

    user_prompt = st.chat_input("ENTER QUERY // DESTINATION // COMMAND…")
    if user_prompt:
        st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
        with st.spinner("PROCESSING…"):
            try:
                if not _BACKEND_AVAILABLE:
                    raise ImportError("GoaInsight not available")
                output, *_ , content_type, goa_db, _ = asyncio.run(_smart_content_generation(user_prompt.strip(), None))
                st.session_state.output = output
                title = output.get("title", user_prompt.title())
                short = output.get("shortDescription","")
                tags  = output.get("tags",[])
                chips = "".join([f"<span class='tag {'pink' if i%3==1 else 'green' if i%3==2 else ''}'>{t}</span>" for i,t in enumerate(tags[:8])])
                reply = f"<strong style='color:#00f5ff'>{title}</strong><br>"
                if short: reply += f"<span style='color:rgba(255,255,255,0.55)'>{short}</span><br>"
                if chips: reply += f"<div style='margin-top:8px'>{chips}</div>"
            except ImportError:
                reply = (f"<strong style='color:#00f5ff'>TARGET: {user_prompt.upper()}</strong><br>"
                         "<span style='color:rgba(255,255,255,0.5)'>Scan complete. Connect backend to unlock full intel.</span><br>"
                         "<span class='tag'>travel</span> <span class='tag pink'>destination</span> <span class='tag insight'>ai-scan</span>")
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    # Results block
    if out:
        st.markdown('<div style="margin:20px 0 10px;border-top:1px solid rgba(0,245,255,0.1);padding-top:18px"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="panel-header"><span class="panel-title">⬡ INTEL REPORT // {out.get("title","DESTINATION").upper()[:28]}</span><span class="panel-badge">CLASSIFIED</span></div>', unsafe_allow_html=True)

        desc = out.get("shortDescription","")
        if desc:
            st.markdown(f"""<div style="background:rgba(0,245,255,0.03);border-left:2px solid var(--cyan);
              padding:12px 16px;margin-bottom:12px;border-radius:0 4px 4px 0">
              <div style="font-family:'Share Tech Mono',monospace;font-size:0.6rem;color:rgba(0,245,255,0.4);
                letter-spacing:0.12em;margin-bottom:6px">SYNOPSIS</div>
              <div style="font-size:0.9rem;color:rgba(255,255,255,0.65);line-height:1.6">{desc}</div>
            </div>""", unsafe_allow_html=True)

        seo = out.get("seoTitle",[])
        if seo:
            titles: list = seo if isinstance(seo,list) else [seo] # type: ignore
            rows = "".join([f'<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.85rem;color:rgba(255,255,255,0.5)"><span style="color:rgba(0,245,255,0.4);font-family:Share Tech Mono,monospace;margin-right:8px">[{i:02d}]</span>{t}</div>' for i,t in enumerate(titles[:3],1)]) # type: ignore
            st.markdown(f'<div style="background:rgba(0,0,0,0.3);border:1px solid rgba(0,245,255,0.1);border-radius:4px;padding:14px 16px;margin-bottom:12px"><div class="widget-label" style="margin-bottom:10px">SEO VECTORS</div>{rows}</div>', unsafe_allow_html=True)

        tags = out.get("tags",[])
        if tags:
            chips = "".join([f"<span class='tag {'pink' if i%3==1 else 'green' if i%3==2 else ''}'>{t}</span>" for i,t in enumerate(tags[:16])])
            st.markdown(f'<div style="margin-bottom:12px"><div class="widget-label" style="margin-bottom:8px">TAG MATRIX</div>{chips}</div>', unsafe_allow_html=True)

        tip = out.get("guidelines","")
        if tip:
            st.markdown(f'<div style="background:rgba(255,230,0,0.04);border:1px solid rgba(255,230,0,0.15);border-radius:4px;padding:14px 16px;margin-bottom:12px"><div style="font-family:Share Tech Mono,monospace;font-size:0.6rem;color:rgba(255,230,0,0.5);letter-spacing:0.12em;margin-bottom:8px">⚠ FIELD PROTOCOLS</div><div style="font-size:0.88rem;color:rgba(255,255,255,0.6);line-height:1.6">{tip}</div></div>', unsafe_allow_html=True)

        content = out.get("text","")
        if content and "<p>No content" not in content:
            st.markdown(f'<div style="background:rgba(0,0,0,0.25);border:1px solid rgba(255,255,255,0.06);border-radius:4px;padding:16px;margin-bottom:12px;max-height:260px;overflow-y:auto"><div class="widget-label" style="margin-bottom:10px">FULL INTELLIGENCE REPORT</div><div style="font-size:0.88rem;color:rgba(255,255,255,0.55);line-height:1.8">{content}</div></div>', unsafe_allow_html=True)

        gallery   = [i for i in out.get("gallery",[])   if isinstance(i,str) and (i.startswith("http") or i.startswith("data:"))]
        thumbnail = [i for i in out.get("thumbnail",[]) if isinstance(i,str) and (i.startswith("http") or i.startswith("data:"))]
        all_imgs  = (gallery[:2] + thumbnail[:1]) # type: ignore
        if all_imgs:
            st.markdown('<div class="widget-label" style="margin-bottom:8px">VISUAL FEED</div>', unsafe_allow_html=True)
            cols = st.columns(len(all_imgs))
            for col, img in zip(cols, all_imgs):
                with col: st.image(img, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ╔═══════════ RIGHT ═══════════╗
with right:
    st.markdown('<div class="panel" style="border-left:1px solid rgba(0,245,255,0.1)">', unsafe_allow_html=True)

    loc = out.get("location",{}) if out else {}
    st.markdown('<div class="panel-header"><span class="panel-title">⬡ GEO TRACKER</span></div>', unsafe_allow_html=True)

    if loc and loc.get("latitude") and loc.get("longitude"):
        lat = float(str(loc["latitude"])); lon = float(str(loc["longitude"]))
        addr = loc.get("address", out.get("title",""))
        st.markdown(f"""<div class="map-shell">
          <div class="map-hud">
            <span class="map-hud-title">📡 {out.get('title','TARGET')[:16].upper()}</span>
            <span class="map-hud-coords">{lat:.4f} / {lon:.4f}</span>
          </div>
          <iframe src="https://www.openstreetmap.org/export/embed.html?bbox={lon-.012}%2C{lat-.012}%2C{lon+.012}%2C{lat+.012}&layer=mapnik&marker={lat}%2C{lon}" scrolling="no"></iframe>
          <div class="map-footer"><a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}" target="_blank">⬡ EXPAND ↗</a></div>
        </div>
        <div style="font-family:'Share Tech Mono',monospace;font-size:0.62rem;color:rgba(255,255,255,0.28);padding:8px 0 14px;line-height:1.6">📌 {addr}</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div style="height:180px;border:1px dashed rgba(0,245,255,0.1);border-radius:4px;
          display:flex;align-items:center;justify-content:center;margin-bottom:14px">
          <div style="text-align:center;color:rgba(0,245,255,0.18);font-family:'Share Tech Mono',monospace;font-size:0.65rem;letter-spacing:0.1em">
            NO SIGNAL<br>SCAN DESTINATION
          </div></div>""", unsafe_allow_html=True)

    # Transport
    st.markdown('<div class="panel-header" style="margin-top:6px"><span class="panel-title">⬡ TRANSPORT GRID</span></div>', unsafe_allow_html=True)
    ways = out.get("ways",{}) if out else {}
    def tw(v): return ("on","ACTIVE") if v else ("off","NULL")
    st.markdown(f"""<div class="transport-grid">
      <div class="t-item {tw(ways.get('walkingOnly',False))[0]}"><span class="t-label">🚶 Walk</span><span class="t-val">{tw(ways.get('walkingOnly',False))[1]}</span></div>
      <div class="t-item {tw(ways.get('byBoat',False))[0]}"><span class="t-label">⛵ Boat</span><span class="t-val">{tw(ways.get('byBoat',False))[1]}</span></div>
      <div class="t-item {tw(ways.get('byCar',False))[0]}"><span class="t-label">🚗 Drive</span><span class="t-val">{tw(ways.get('byCar',False))[1]}</span></div>
      <div class="t-item {tw(ways.get('byPublicTransport',False))[0]}"><span class="t-label">🚌 Transit</span><span class="t-val">{tw(ways.get('byPublicTransport',False))[1]}</span></div>
    </div>""", unsafe_allow_html=True)

    # Flags
    st.markdown('<div class="panel-header" style="margin-top:16px"><span class="panel-title">⬡ FLAG REGISTER</span></div>', unsafe_allow_html=True)
    flags = [
        ("🟢","Active",       out.get("active",False)         if out else False),
        ("⭐","Featured",     out.get("featured",False)       if out else False),
        ("💑","Couples",      out.get("coupleFriendly",False) if out else False),
        ("👥","Groups",       out.get("groupFriendly",False)  if out else False),
        ("🧒","Kids",         out.get("kidsFriendly",False)   if out else False),
        ("🔥","Trending",     out.get("trending",False)       if out else False),
        ("🌧️","Monsoon",     out.get("monsoon",False)        if out else False),
        ("🕐","Open Now",     out.get("isOpen",False)         if out else False),
    ]
    rows = "".join([f'<div class="flag-chip {"on" if v else "off"}"><span class="icon">{icon}</span><span class="name">{name}</span><span class="val">{"ON" if v else "--"}</span></div>' for icon,name,v in flags])
    st.markdown(f'<div class="flag-row">{rows}</div>', unsafe_allow_html=True)


# ── Process scan ──────────────────────────────────────────────────────────────
if scan_btn and topic.strip():
    with st.spinner("INITIATING DEEP SCAN…"):
        try:
            if not _BACKEND_AVAILABLE:
                raise ImportError("GoaInsight not available")
            output, saved_file, thumbnail_file, json_file, content_type, goa_db, formatted_json = asyncio.run(
                _smart_content_generation(topic.strip(), details.strip() or None)
            )
            st.session_state.update({'output':output,'generated':True,'saved_file':saved_file,
                'thumbnail_file':thumbnail_file,'json_file':json_file,
                'content_type':content_type,'goa_db':goa_db})
        except ImportError:
            st.warning("⚠ Backend module not found — showing demo data.", icon="⚠")
            st.session_state.update({
                'output':{
                    'title':topic.title(),
                    'shortDescription':f'{topic.title()} — a high-value node in the intelligence grid. Rich culture, coastal access, and local operators report excellent conditions.',
                    'location':{'latitude':'15.2993','longitude':'74.1240','address':f'{topic.title()}, Goa, India'},
                    'tags':['beach','culture','nightlife','food','heritage','coastal','goa','explore'],
                    'guidelines':'Maintain operational security. Hydrate. Respect local protocols.',
                    'text':f'<p>{topic.title()} is a prime destination. Engage with local guides for best access.</p>',
                    'seoTitle':[f'Visit {topic.title()} — NEXUS Travel Guide 2025',f'{topic.title()} Decoded: What To Do & See'],
                    'active':True,'featured':True,'coupleFriendly':True,'groupFriendly':True,
                    'kidsFriendly':False,'trending':True,'monsoon':False,'isOpen':True,
                    'ways':{'walkingOnly':False,'byBoat':False,'byCar':True,'byPublicTransport':True},
                    'thumbnail':[],'gallery':[],
                },'generated':True,'content_type':'destination','goa_db':None
            })
        st.toast("⬡ SCAN COMPLETE")
        st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="border-top:1px solid rgba(0,245,255,0.1);padding:12px 28px;
  display:flex;justify-content:space-between;align-items:center;
  background:rgba(2,4,8,0.95);position:relative;z-index:1">
  <div style="font-family:'Share Tech Mono',monospace;font-size:0.6rem;color:rgba(255,255,255,0.18);letter-spacing:0.1em">
    GOAINSIGHT // TRAVEL·GUIDE·OS v2.4.1</div>
  <div style="font-family:'Share Tech Mono',monospace;font-size:0.6rem;color:rgba(0,245,255,0.3)">
    DEV: SURAJ GAWAS // ALL SYSTEMS NOMINAL</div>
</div>
""", unsafe_allow_html=True)