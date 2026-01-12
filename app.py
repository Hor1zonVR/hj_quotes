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


# ---------- Copy button (Spotify-ish pill) ----------
def copy_button(text_to_copy: str, element_id: str, label: str = "Copy"):
    safe = (text_to_copy or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    html = f"""
    <div>
      <button id="{element_id}" class="spotify-pill" title="Copy to clipboard">
        <span style="margin-right:8px;">📋</span>{label}
      </button>

      <script>
        (function() {{
          const btn = document.getElementById("{element_id}");
          if (!btn) return;
          if (btn.dataset.bound === "1") return;
          btn.dataset.bound = "1";

          btn.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText("{safe}");
              const old = btn.innerHTML;
              btn.innerHTML = "✅ Copied";
              setTimeout(() => btn.innerHTML = old, 900);
            }} catch (e) {{
              const old = btn.innerHTML;
              btn.innerHTML = "❌ Failed";
              setTimeout(() => btn.innerHTML = old, 900);
            }}
          }});
        }})();
      </script>
    </div>
    """
    components.html(html, height=56)


# ---------- Session ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "username" not in st.session_state:
    st.session_state.username = ""

if "pending_delete_quote_id" not in st.session_state:
    st.session_state.pending_delete_quote_id = None

if "pending_delete_quote_label" not in st.session_state:
    st.session_state.pending_delete_quote_label = ""


# ---------- Page config + Spotify-ish CSS ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
      /* ===== Spotify-ish theme ===== */
      :root{
        --bg0:#0b0f0c;         /* app background */
        --bg1:#121212;         /* card background */
        --bg2:#181818;         /* hover/raised */
        --stroke:#2a2a2a;      /* borders */
        --text:#ffffff;
        --muted:#b3b3b3;
        --green:#1DB954;       /* Spotify green */
        --green2:#1ed760;      /* hover green */
      }

      /* App canvas */
      .stApp {
        background: radial-gradient(1200px 700px at 15% -10%, rgba(29,185,84,0.18), transparent 55%),
                    radial-gradient(900px 600px at 95% 0%, rgba(29,185,84,0.10), transparent 45%),
                    var(--bg0);
        color: var(--text);
      }

      /* Container width padding */
      .block-container { padding-top: 1.1rem; padding-bottom: 2.2rem; }

      /* Sidebar */
      section[data-testid="stSidebar"]{
        background: linear-gradient(180deg, rgba(18,18,18,0.98), rgba(12,12,12,0.98));
        border-right: 1px solid rgba(255,255,255,0.06);
      }

      /* Headings spacing */
      h1, h2, h3 { letter-spacing: -0.02em; }

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
        background: rgba(18,18,18,0.9) !important;
      }
      .stSelectbox div[data-baseweb="select"] > div{
        border-radius: 14px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        background: rgba(18,18,18,0.9) !important;
      }

      /* Primary buttons -> green pill */
      .stButton > button[kind="primary"]{
        background: var(--green) !important;
        color: #0b0f0c !important;
        border: 1px solid rgba(0,0,0,0.0) !important;
        border-radius: 999px !important;
        font-weight: 800 !important;
      }
      .stButton > button[kind="primary"]:hover{
        background: var(--green2) !important;
      }

      /* Normal buttons */
      .stButton > button{
        border-radius: 999px !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        background: rgba(255,255,255,0.04) !important;
        font-weight: 700 !important;
      }
      .stButton > button:hover{
        background: rgba(255,255,255,0.07) !important;
        border-color: rgba(255,255,255,0.18) !important;
      }

      /* Tabs */
      button[data-baseweb="tab"]{
        border-radius: 999px !important;
        margin-right: 8px !important;
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
      }
      button[data-baseweb="tab"][aria-selected="true"]{
        background: rgba(29,185,84,0.14) !important;
        border-color: rgba(29,185,84,0.35) !important;
      }

      /* Captions muted */
      .stCaption, .stMarkdown p, .stMarkdown span {
        color: var(--text);
      }
      .muted { color: var(--muted); }

      /* Custom pill used by copy button (inside components.html) */
      .spotify-pill{
        width:100%;
        padding:10px 12px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.04);
        color: white;
        cursor:pointer;
        font-weight: 800;
        letter-spacing: 0.01em;
      }
      .spotify-pill:hover{
        background: rgba(255,255,255,0.07);
        border-color: rgba(255,255,255,0.18);
      }

      /* Make dividers subtle */
      hr { border-color: rgba(255,255,255,0.08) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Refresh ----------
st_autorefresh(interval=POLL_SECONDS * 1000, key="refresh")

# ---------- Header ----------
lh, rh = st.columns([1.4, 1])
with lh:
    st.title(APP_TITLE)
    st.caption("Spotify-ish dark • neon green • clean cards")
with rh:
    st.caption(f"Auto-refresh: every {POLL_SECONDS}s")


# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("Settings")
    st.session_state.username = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="Enter your name",
    )
    st.divider()
    if st.button("🔄 Refresh now", use_container_width=True):
        clear_cache_and_rerun()
    st.caption("Tip: Use search + sort to find quotes fast.")


# ---------- Tabs ----------
tab_quotes, tab_chat = st.tabs(["📚 Quotes", "💬 Chat"])


# ==========================================
# ================ QUOTES ==================
# ==========================================
with tab_quotes:
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

        for qid, q_text, q_author, created_raw in normalized:
            label = f"“{q_text}”" if q_text else "“(empty)”"
            to_copy = q_text + (f" — {q_author}" if q_author else "")

            with st.container(border=True):
                st.markdown(f"### {label}")
                if q_author:
                    st.caption(f"— {q_author}")
                if show_meta and created_raw:
                    st.caption(f"Added: {pretty_ts(created_raw)}")

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
with tab_chat:
    st.subheader("Chat")

    if not st.session_state.username.strip():
        st.warning("Set a username in the sidebar to chat.")
    else:
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
