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


def fb(path: str) -> str:
    return f"{FIREBASE_DB_URL}{path}.json"


def now_iso_z() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def pretty_ts(iso_z: str) -> str:
    """Convert '2025-10-23T00:50:27Z' -> '23 Oct 2025, 00:50 UTC' """
    try:
        dt = datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso_z


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


# ---------- Fix for old “HTML got saved into quote text” ----------
_MUTED_ADDED_DIV_RE = re.compile(
    r'<div\s+class=(["\'])muted\1>\s*Added:\s*.*?</div>',
    flags=re.IGNORECASE | re.DOTALL,
)

_ANY_HTML_TAG_RE = re.compile(r"</?[^>]+>")

def clean_quote_text(text: str) -> str:
    """
    Removes the accidentally-saved 'Added: ...' div and (only if HTML is present)
    strips remaining HTML tags so old polluted quotes display normally.
    """
    if not text:
        return ""

    s = text.strip()

    # Remove the specific polluted chunk
    s2 = _MUTED_ADDED_DIV_RE.sub("", s).strip()

    # If it still looks like HTML got saved, strip any remaining tags
    if "<div" in s2.lower() or "</div" in s2.lower() or "<span" in s2.lower() or "<br" in s2.lower():
        s2 = _ANY_HTML_TAG_RE.sub("", s2)
        s2 = re.sub(r"\s{2,}", " ", s2).strip()

    return s2


# ---------- Copy button ----------
def copy_button(text_to_copy: str, key: str, label: str = "📋 Copy"):
    # Escape for safe JS string
    safe = (text_to_copy or "").replace("\\", "\\\\").replace('"', '\\"')
    html = f"""
    <button
      style="
        width:100%;
        padding:7px 10px;
        border-radius:10px;
        border:1px solid #374151;
        background:#111827;
        color:white;
        cursor:pointer;
      "
      onclick='navigator.clipboard.writeText("{safe}")'
      title="Copy to clipboard"
    >
      {label}
    </button>
    """
    components.html(html, height=46, key=key)


# ---------- Session ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "username" not in st.session_state:
    st.session_state.username = ""

if "page" not in st.session_state:
    st.session_state.page = "Quotes"

# Delete confirmation state
if "pending_delete_quote_id" not in st.session_state:
    st.session_state.pending_delete_quote_id = None

if "pending_delete_quote_label" not in st.session_state:
    st.session_state.pending_delete_quote_label = ""


# ---------- UI ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
    .big-font { font-size:18px !important; line-height:1.45; }
    .quote-card {
        padding:14px;
        border-radius:12px;
        background:#111827;
        border:1px solid #374151;
        margin-bottom:10px;
    }
    .quote-author { color:#9ca3af; font-size:14px; margin-top:8px; }
    .chat {
        padding:10px;
        border-radius:10px;
        margin-bottom:8px;
        background:#0b1220;
        border:1px solid #1f2937;
    }
    .muted { color:#9ca3af; font-size:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_TITLE)

# ---------- Auto refresh ----------
st_autorefresh(interval=POLL_SECONDS * 1000, key="refresh")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    st.session_state.username = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="Enter your name",
    )

    st.divider()
    st.session_state.page = st.radio("Navigation", ["Quotes", "Chat"])

    st.divider()
    if st.button("🔄 Refresh now"):
        clear_cache_and_rerun()


# ==========================================
# ================ QUOTES ==================
# ==========================================
if st.session_state.page == "Quotes":
    st.subheader("Quotes")

    with st.form("add_quote", clear_on_submit=True):
        text = st.text_area("Quote", height=90, placeholder="Write your quote…")
        author = st.text_input("Author (optional)", placeholder="e.g., Marcus Aurelius")
        submitted = st.form_submit_button("Add Quote")

        if submitted and text.strip():
            post_data(
                "/quotes",
                {
                    "text": text.strip(),
                    "author": author.strip(),
                    "created_at": now_iso_z(),
                },
            )
            clear_cache_and_rerun()

    # ---- Delete confirmation box ----
    if st.session_state.pending_delete_quote_id:
        with st.container(border=True):
            st.warning("Delete quote?")
            st.write(st.session_state.pending_delete_quote_label)

            c1, c2, _ = st.columns([1, 1, 6])
            with c1:
                if st.button("✅ Confirm delete", type="primary"):
                    delete_data(f"/quotes/{st.session_state.pending_delete_quote_id}")
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    clear_cache_and_rerun()
            with c2:
                if st.button("✖ Cancel"):
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    st.rerun()

    quotes = get_data_cached("/quotes") or {}

    if not quotes:
        st.info("No quotes yet — add one above.")
    else:
        # Newest first
        items = sorted(
            quotes.items(),
            key=lambda x: (x[1].get("created_at") or ""),
            reverse=True,
        )

        for qid, q in items:
            q_text_raw = q.get("text") or ""
            q_text = clean_quote_text(q_text_raw)
            q_author = (q.get("author") or "").strip()
            created_raw = (q.get("created_at") or "").strip()

            label = f"“{q_text}”" if q_text else "“(empty)”"

            author_html = f'<div class="quote-author">— {q_author}</div>' if q_author else ""
            created_html = f'<div class="muted">Added: {pretty_ts(created_raw)}</div>' if created_raw else ""

            # quote | copy | delete
            left, cpy, delc = st.columns([8, 1.2, 0.8], vertical_alignment="top")

            with left:
                st.markdown(
                    f"""
                    <div class="quote-card">
                        <div class="big-font">{label}</div>
                        {author_html}
                        {created_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with cpy:
                to_copy = q_text + (f" — {q_author}" if q_author else "")
                copy_button(to_copy, key=f"copy_{qid}", label="📋 Copy")

            with delc:
                if st.button("🗑", key=f"ask_del_{qid}", help="Delete"):
                    st.session_state.pending_delete_quote_id = qid
                    st.session_state.pending_delete_quote_label = (
                        f"“{q_text}”" + (f" — {q_author}" if q_author else "")
                    )
                    st.rerun()


# ==========================================
# ================= CHAT ===================
# ==========================================
if st.session_state.page == "Chat":
    st.subheader("Chat")

    if not st.session_state.username.strip():
        st.warning("Set a username in the sidebar to chat.")
    else:
        messages = get_data_cached("/chat") or {}

        # Oldest -> newest
        items = sorted(messages.items(), key=lambda x: (x[1].get("ts") or ""))

        if not items:
            st.info("No chat messages yet.")
        else:
            for _, m in items:
                user = (m.get("user") or "").strip()
                text = (m.get("text") or "").strip()
                ts_raw = (m.get("ts") or "").strip()

                ts_html = f'<span class="muted">{pretty_ts(ts_raw)}</span>' if ts_raw else ""

                st.markdown(
                    f"""
                    <div class="chat">
                        <b>{user}:</b> {text}<br/>
                        {ts_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with st.form("send_msg", clear_on_submit=True):
            msg = st.text_input("Message", placeholder="Type a message…")
            sent = st.form_submit_button("Send")

            if sent and msg.strip():
                post_data(
                    "/chat",
                    {
                        "user": st.session_state.username.strip(),
                        "text": msg.strip(),
                        "ts": now_iso_z(),
                    },
                )
                clear_cache_and_rerun()
