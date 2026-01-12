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
    Removes accidentally-saved 'Added: ...' div and strips remaining tags
    only when it looks like HTML got saved into the quote text.
    """
    if not text:
        return ""

    s = text.strip()
    s = _MUTED_ADDED_DIV_RE.sub("", s).strip()

    lower = s.lower()
    if "<div" in lower or "</div" in lower or "<span" in lower or "<br" in lower or "<p" in lower:
        s = _ANY_HTML_TAG_RE.sub("", s)
        s = re.sub(r"\s{2,}", " ", s).strip()

    return s


# ---------- Copy button ----------
def copy_button(text_to_copy: str, element_id: str, label: str = "📋 Copy"):
    safe = (text_to_copy or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    html = f"""
    <div>
      <button id="{element_id}" style="
          width:100%;
          padding:7px 10px;
          border-radius:10px;
          border:1px solid #374151;
          background:#111827;
          color:white;
          cursor:pointer;
      " title="Copy to clipboard">
        {label}
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
    components.html(html, height=52)


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
    /* Small cosmetic improvements */
    .stButton>button { border-radius: 10px; }
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
                {"text": text.strip(), "author": author.strip(), "created_at": now_iso_z()},
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
        items = sorted(
            quotes.items(),
            key=lambda x: (x[1].get("created_at") or ""),
            reverse=True,
        )

        for qid, q in items:
            q_text = clean_quote_text(q.get("text") or "")
            q_author = (q.get("author") or "").strip()
            created_raw = (q.get("created_at") or "").strip()

            label = f"“{q_text}”" if q_text else "“(empty)”"

            # quote | copy | delete
            left, cpy, delc = st.columns([8, 1.3, 0.7], vertical_alignment="top")

            with left:
                # Streamlit-native UI (no HTML injection → no raw HTML appearing)
                with st.container(border=True):
                    st.markdown(f"### {label}")
                    if q_author:
                        st.caption(f"— {q_author}")
                    if created_raw:
                        st.caption(f"Added: {pretty_ts(created_raw)}")

            with cpy:
                to_copy = q_text + (f" — {q_author}" if q_author else "")
                copy_button(to_copy, element_id=f"copy_btn_{qid}", label="📋 Copy")

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

        with st.form("send_msg", clear_on_submit=True):
            msg = st.text_input("Message", placeholder="Type a message…")
            sent = st.form_submit_button("Send")

            if sent and msg.strip():
                post_data(
                    "/chat",
                    {"user": st.session_state.username.strip(), "text": msg.strip(), "ts": now_iso_z()},
                )
                clear_cache_and_rerun()
