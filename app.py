import streamlit as st
import requests
import uuid
import time
from datetime import datetime

# ================= CONFIG =================
FIREBASE_DB_URL = "https://quotesaver-e8fae-default-rtdb.europe-west1.firebasedatabase.app"
POLL_SECONDS = 2
APP_TITLE = "HJ Quotes"
# ==========================================

def fb(path):
    return f"{FIREBASE_DB_URL}{path}.json"

# ---------- Helpers ----------
def now():
    return datetime.utcnow().isoformat() + "Z"

def get_data(path):
    r = requests.get(fb(path), timeout=8)
    return r.json() if r.ok else {}

def post_data(path, data):
    requests.post(fb(path), json=data, timeout=8)

def delete_data(path):
    requests.delete(fb(path), timeout=8)

# ---------- Session ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "username" not in st.session_state:
    st.session_state.username = ""

if "page" not in st.session_state:
    st.session_state.page = "Quotes"

# ---------- UI ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
    .big-font { font-size:20px !important; }
    .quote { padding:12px; border-radius:10px; background:#1f2937; margin-bottom:10px; }
    .chat { padding:8px; border-radius:8px; margin-bottom:6px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title(APP_TITLE)

# ---------- Username ----------
with st.sidebar:
    st.header("Settings")
    st.session_state.username = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="Enter your name"
    )

    st.divider()
    st.session_state.page = st.radio(
        "Navigation",
        ["Quotes", "Chat"]
    )

# ==========================================
# ================ QUOTES ==================
# ==========================================
if st.session_state.page == "Quotes":
    st.subheader("Quotes")

    with st.form("add_quote", clear_on_submit=True):
        text = st.text_area("Quote", height=80)
        author = st.text_input("Author (optional)")
        submitted = st.form_submit_button("Add Quote")

        if submitted and text.strip():
            post_data("/quotes", {
                "text": text.strip(),
                "author": author.strip(),
                "created_at": now()
            })
            st.experimental_rerun()

    quotes = get_data("/quotes") or {}

    for qid, q in sorted(quotes.items(), key=lambda x: x[1].get("created_at", "")):
        label = f"“{q.get('text','')}”"
        if q.get("author"):
            label += f" — {q['author']}"

        st.markdown(f"<div class='quote big-font'>{label}</div>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 8])
        with col1:
            if st.button("🗑", key=f"del_{qid}"):
                delete_data(f"/quotes/{qid}")
                st.experimental_rerun()

# ==========================================
# ================= CHAT ===================
# ==========================================
if st.session_state.page == "Chat":
    st.subheader("Chat")

    if not st.session_state.username.strip():
        st.warning("Set a username in the sidebar to chat.")
    else:
        messages = get_data("/chat") or {}

        for mid, m in sorted(messages.items(), key=lambda x: x[1].get("ts","")):
            st.markdown(
                f"<div class='chat'><b>{m['user']}:</b> {m['text']}</div>",
                unsafe_allow_html=True
            )

        with st.form("send_msg", clear_on_submit=True):
            msg = st.text_input("Message")
            sent = st.form_submit_button("Send")

            if sent and msg.strip():
                post_data("/chat", {
                    "user": st.session_state.username,
                    "text": msg.strip(),
                    "ts": now()
                })
                st.experimental_rerun()

# ---------- Auto refresh ----------
time.sleep(POLL_SECONDS)
st.experimental_rerun()
