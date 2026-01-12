import streamlit as st
import requests
import uuid
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ================= CONFIG =================
FIREBASE_DB_URL = "https://quotesaver-e8fae-default-rtdb.europe-west1.firebasedatabase.app"
POLL_SECONDS = 2
APP_TITLE = "HJ Quotes"
CACHE_TTL_SECONDS = 2
# ==========================================


def fb(path: str) -> str:
    return f"{FIREBASE_DB_URL}{path}.json"


# ---------- Helpers ----------
def now() -> str:
    return datetime.utcnow().isoformat() + "Z"


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
    # Ensure the next run fetches fresh data after writes/deletes
    st.cache_data.clear()
    st.rerun()


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
    .big-font { font-size:18px !important; line-height:1.4; }
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
# Refresh app view every POLL_SECONDS without manual sleep/rerun loops.
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
                    "created_at": now(),
                },
            )
            clear_cache_and_rerun()

    # ---- Delete confirmation modal-ish section ----
    if st.session_state.pending_delete_quote_id:
        with st.container(border=True):
            st.warning("Delete quote?")
            st.write(st.session_state.pending_delete_quote_label)

            c1, c2, c3 = st.columns([1, 1, 6])
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
            key=lambda x: x[1].get("created_at", ""),
            reverse=True,
        )

        for qid, q in items:
            q_text = (q.get("text") or "").strip()
            q_author = (q.get("author") or "").strip()
            created = q.get("created_at", "")

            label = f"“{q_text}”" if q_text else "“(empty)”"
            if q_author:
                author_line = f"— {q_author}"
            else:
                author_line = ""

            left, right = st.columns([9, 1], vertical_alignment="top")
            with left:
                st.markdown(
                    f"""
                    <div class="quote-card">
                        <div class="big-font">{label}</div>
                        {"<div class='quote-author'>" + author_line + "</div>" if author_line else ""}
                        {"<div class='muted'>Added: " + created + "</div>" if created else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with right:
                if st.button("🗑", key=f"ask_del_{qid}", help="Delete"):
                    st.session_state.pending_delete_quote_id = qid
                    st.session_state.pending_delete_quote_label = label + (f" {author_line}" if author_line else "")
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

        # Chat usually shows oldest -> newest (new messages at bottom)
        items = sorted(messages.items(), key=lambda x: x[1].get("ts", ""))

        chat_box = st.container()
        with chat_box:
            if not items:
                st.info("No chat messages yet.")
            else:
                for mid, m in items:
                    user = (m.get("user") or "").strip()
                    text = (m.get("text") or "").strip()
                    ts = m.get("ts", "")

                    st.markdown(
                        f"""
                        <div class="chat">
                            <b>{user}:</b> {text}<br/>
                            <span class="muted">{ts}</span>
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
                        "ts": now(),
                    },
                )
                clear_cache_and_rerun()
