import re
import uuid
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

# ================= CONFIG =================
FIREBASE_DB_URL = "https://quotesaver-e8fae-default-rtdb.europe-west1.firebasedatabase.app"
POLL_SECONDS = 2
APP_TITLE = "HJ Quotes"
CACHE_TTL_SECONDS = 2
# ==========================================


# ---------- Firebase helpers ----------
def fb(path: str) -> str:
    return f"{FIREBASE_DB_URL}{path}.json"


def _safe_json(resp):
    try:
        return resp.json() if resp.ok else {}
    except Exception:
        return {}


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_data_cached(path: str):
    r = requests.get(fb(path), timeout=8)
    return _safe_json(r) or {}


def post_data(path: str, data: dict):
    requests.post(fb(path), json=data, timeout=8)


def delete_data(path: str):
    requests.delete(fb(path), timeout=8)


def clear_cache_and_rerun():
    st.cache_data.clear()
    st.rerun()


# ---------- Time helpers ----------
def now_iso_z() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def pretty_ts(iso_z: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso_z


# ---------- Clean old “HTML got saved into quote text” ----------
_MUTED_ADDED_DIV_RE = re.compile(
    r'<div\s+class=(["\'])muted\1>\s*Added:\s*.*?</div>',
    flags=re.IGNORECASE | re.DOTALL,
)
_ANY_HTML_TAG_RE = re.compile(r"</?[^>]+>")


def clean_quote_text(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    s = _MUTED_ADDED_DIV_RE.sub("", s).strip()
    lower = s.lower()
    if "<div" in lower or "</div" in lower or "<span" in lower or "<br" in lower or "<p" in lower:
        s = _ANY_HTML_TAG_RE.sub("", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
    return s


# ---------- Copy button (fully self-styled so it never turns white) ----------
def copy_button(text_to_copy: str, element_id: str, label: str = "Copy"):
    safe = (text_to_copy or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    html = f"""
    <div style="width:100%;">
      <style>
        .hj-copy {{
          width: 100%;
          padding: 10px 12px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.12);
          background: #1DB954;
          color: #0b0f0c;
          cursor: pointer;
          font-weight: 900;
          letter-spacing: 0.01em;
        }}
        .hj-copy:hover {{
          background: #1ed760;
        }}
      </style>

      <button id="{element_id}" class="hj-copy" title="Copy to clipboard">📋 {label}</button>

      <script>
        (function() {{
          const btn = document.getElementById("{element_id}");
          if (!btn) return;
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";

          btn.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText("{safe}");
              const old = btn.innerText;
              btn.innerText = "✅ Copied";
              setTimeout(() => btn.innerText = old, 900);
            }} catch (e) {{
              const old = btn.innerText;
              btn.innerText = "❌ Failed";
              setTimeout(() => btn.innerText = old, 900);
            }}
          }});
        }})();
      </script>
    </div>
    """
    components.html(html, height=60)


# ---------- Session ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "username" not in st.session_state:
    st.session_state.username = ""

if "page" not in st.session_state:
    st.session_state.page = "Quotes"

if "pending_delete_quote_id" not in st.session_state:
    st.session_state.pending_delete_quote_id = None

if "pending_delete_quote_label" not in st.session_state:
    st.session_state.pending_delete_quote_label = ""


# ---------- Page config + Spotify-ish UI ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
      :root{
        --bg0:#0b0f0c;
        --bg1:#121212;
        --bg2:#181818;
        --stroke:rgba(255,255,255,0.10);
        --text:#ffffff;
        --muted:#b3b3b3;
        --green:#1DB954;
        --green2:#1ed760;
      }

      .stApp {
        background:
          radial-gradient(1200px 700px at 15% -10%, rgba(29,185,84,0.22), transparent 55%),
          radial-gradient(900px 600px at 95% 0%, rgba(29,185,84,0.12), transparent 45%),
          var(--bg0);
        color: var(--text);
      }

      .block-container {
        padding-top: 1.0rem;
        padding-bottom: 2.2rem;
      }

      /* Sidebar “left rail” look */
      section[data-testid="stSidebar"]{
        background: linear-gradient(180deg, rgba(18,18,18,0.98), rgba(12,12,12,0.98));
        border-right: 1px solid rgba(255,255,255,0.06);
      }

      /* Hero header card */
      .hj-hero {
        border-radius: 18px;
        padding: 18px 18px;
        border: 1px solid rgba(255,255,255,0.10);
        background:
          radial-gradient(900px 350px at 20% 0%, rgba(29,185,84,0.35), transparent 55%),
          rgba(18,18,18,0.70);
        box-shadow: 0 14px 40px rgba(0,0,0,0.35);
        margin-bottom: 14px;
      }
      .hj-hero h1 { margin: 0; letter-spacing: -0.03em; }
      .hj-hero .sub { color: var(--muted); margin-top: 6px; }

      /* Streamlit bordered containers -> Spotify cards */
      [data-testid="stVerticalBlockBorderWrapper"]{
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        background: rgba(18,18,18,0.85) !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      }
      [data-testid="stVerticalBlockBorderWrapper"]:hover{
        background: rgba(24,24,24,0.92) !important;
        border-color: rgba(255,255,255,0.10) !important;
      }

      /* Inputs */
      .stTextInput input, .stTextArea textarea {
        border-radius: 14px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        background: rgba(18,18,18,0.92) !important;
      }
      .stSelectbox div[data-baseweb="select"] > div{
        border-radius: 14px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        background: rgba(18,18,18,0.92) !important;
      }

      /* Primary buttons -> Spotify green pill */
      .stButton > button[kind="primary"]{
        background: var(--green) !important;
        color: #0b0f0c !important;
        border: 1px solid rgba(0,0,0,0.0) !important;
        border-radius: 999px !important;
        font-weight: 900 !important;
      }
      .stButton > button[kind="primary"]:hover{
        background: var(--green2) !important;
      }

      /* Regular buttons */
      .stButton > button{
        border-radius: 999px !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        background: rgba(255,255,255,0.04) !important;
        font-weight: 800 !important;
      }
      .stButton > button:hover{
        background: rgba(255,255,255,0.07) !important;
        border-color: rgba(255,255,255,0.18) !important;
      }

      /* Make radio nav bigger + remove weird red text by forcing colors */
      section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span{
        color: var(--text) !important;
      }

      /* Radio options padding / pill feel */
      section[data-testid="stSidebar"] div[role="radiogroup"] > label{
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.03);
        border-radius: 14px;
        padding: 10px 12px;
        margin: 8px 0;
      }

      /* “Selected” styling (best-effort; Streamlit DOM can vary slightly) */
      section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
        border-color: rgba(29,185,84,0.45) !important;
        background: rgba(29,185,84,0.16) !important;
      }

      /* Dividers subtle */
      hr { border-color: rgba(255,255,255,0.08) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Refresh ----------
st_autorefresh(interval=POLL_SECONDS * 1000, key="refresh")

# ---------- Sidebar “left rail” navigation ----------
with st.sidebar:
    st.markdown("### Navigation")
    st.session_state.page = st.radio(
        label="",
        options=["Quotes", "Chat"],
        index=0 if st.session_state.page == "Quotes" else 1,
        format_func=lambda x: "📚  Quotes" if x == "Quotes" else "💬  Chat",
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### Settings")
    st.session_state.username = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="Enter your name",
    )

    c_a, c_b = st.columns(2)
    with c_a:
        if st.button("🔄 Refresh", use_container_width=True):
            clear_cache_and_rerun()
    with c_b:
        st.caption(f"{POLL_SECONDS}s poll")

    st.divider()
    st.caption("Tip: Search + sort on Quotes like a playlist.")


# ---------- Hero header ----------
st.markdown(
    f"""
    <div class="hj-hero">
      <h1>{APP_TITLE}</h1>
      <div class="sub">Spotify-ish layout • left rail • playlist-style cards • copy in one tap</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# ================ QUOTES ==================
# ==========================================
if st.session_state.page == "Quotes":
    with st.container(border=True):
        st.subheader("Quotes")
        c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
        with c1:
            q_search = st.text_input("Search", placeholder="Search quotes or authors…")
        with c2:
            sort_mode = st.selectbox("Sort", ["Newest first", "Oldest first", "Author A–Z"])
        with c3:
            show_meta = st.toggle("Show dates", value=True)

    with st.container(border=True):
        st.markdown("#### Add a quote")
        with st.form("add_quote", clear_on_submit=True):
            text = st.text_area("Quote", height=90, placeholder="Write your quote…")
            author = st.text_input("Author (optional)", placeholder="e.g., Marcus Aurelius")
            submitted = st.form_submit_button("Add Quote", use_container_width=True)

            if submitted and text.strip():
                post_data("/quotes", {"text": text.strip(), "author": author.strip(), "created_at": now_iso_z()})
                st.toast("Quote added ✅")
                clear_cache_and_rerun()

    # Delete confirmation
    if st.session_state.pending_delete_quote_id:
        with st.container(border=True):
            st.warning("Delete quote?")
            st.write(st.session_state.pending_delete_quote_label)
            a, b, _ = st.columns([1, 1, 6])
            with a:
                if st.button("✅ Confirm delete", type="primary", use_container_width=True):
                    delete_data(f"/quotes/{st.session_state.pending_delete_quote_id}")
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    st.toast("Deleted 🗑️")
                    clear_cache_and_rerun()
            with b:
                if st.button("✖ Cancel", use_container_width=True):
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    st.rerun()

    quotes = get_data_cached("/quotes") or {}
    if not quotes:
        st.info("No quotes yet — add one above.")
    else:
        normalized = []
        for qid, q in quotes.items():
            q_text = clean_quote_text(q.get("text") or "")
            q_author = (q.get("author") or "").strip()
            created_raw = (q.get("created_at") or "").strip()
            normalized.append((qid, q_text, q_author, created_raw))

        # Filter
        if q_search.strip():
            needle = q_search.strip().lower()
            normalized = [r for r in normalized if needle in (r[1] or "").lower() or needle in (r[2] or "").lower()]

        # Sort
        if sort_mode == "Newest first":
            normalized.sort(key=lambda r: r[3] or "", reverse=True)
        elif sort_mode == "Oldest first":
            normalized.sort(key=lambda r: r[3] or "")
        else:
            normalized.sort(key=lambda r: (r[2] or "").lower())

        st.markdown("#### Your quotes")
        st.caption(f"{len(normalized)} shown")

        # Playlist-style list (card per item, tight)
        for qid, q_text, q_author, created_raw in normalized:
            label = f"“{q_text}”" if q_text else "“(empty)”"
            to_copy = q_text + (f" — {q_author}" if q_author else "")

            with st.container(border=True):
                st.markdown(f"### {label}")
                meta_line = []
                if q_author:
                    meta_line.append(f"— {q_author}")
                if show_meta and created_raw:
                    meta_line.append(f"Added: {pretty_ts(created_raw)}")
                if meta_line:
                    st.caption(" • ".join(meta_line))

                a1, a2, _ = st.columns([1.2, 1.0, 8.0])
                with a1:
                    copy_button(to_copy, element_id=f"copy_btn_{qid}", label="Copy")
                with a2:
                    if st.button("🗑 Delete", key=f"ask_del_{qid}", use_container_width=True):
                        st.session_state.pending_delete_quote_id = qid
                        st.session_state.pending_delete_quote_label = (
                            f"“{q_text}”" + (f" — {q_author}" if q_author else "")
                        )
                        st.rerun()


# ==========================================
# ================= CHAT ===================
# ==========================================
if st.session_state.page == "Chat":
    with st.container(border=True):
        st.subheader("Chat")
        if not st.session_state.username.strip():
            st.warning("Set a username in the sidebar to chat.")

    if st.session_state.username.strip():
        messages = get_data_cached("/chat") or {}
        items = sorted(messages.items(), key=lambda x: (x[1].get("ts") or ""))

        if not items:
            st.info("No chat messages yet.")
        else:
            for _, m in items:
                user = (m.get("user") or "").strip()
                text = (m.get("text") or "").strip()
                ts_raw = (m.get("ts") or "").strip()

                with st.container(border=True):
                    st.markdown(f"**{user}:** {text}")
                    if ts_raw:
                        st.caption(pretty_ts(ts_raw))

        with st.container(border=True):
            st.markdown("#### Send a message")
            with st.form("send_msg", clear_on_submit=True):
                msg = st.text_input("Message", placeholder="Type a message…")
                sent = st.form_submit_button("Send", use_container_width=True)

                if sent and msg.strip():
                    post_data("/chat", {"user": st.session_state.username.strip(), "text": msg.strip(), "ts": now_iso_z()})
                    st.toast("Sent ✅")
                    clear_cache_and_rerun()
