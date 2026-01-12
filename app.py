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


# ---------- Copy button ----------
def copy_button(text_to_copy: str, element_id: str, label: str = "Copy"):
    safe = (text_to_copy or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    html = f"""
    <div>
      <button id="{element_id}" style="
          width:100%;
          padding:8px 10px;
          border-radius:12px;
          border:1px solid rgba(255,255,255,0.14);
          background: rgba(255,255,255,0.06);
          color: white;
          cursor:pointer;
          font-weight: 600;
      " title="Copy to clipboard">
        📋 {label}
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
    components.html(html, height=54)


# ---------- Session ----------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "username" not in st.session_state:
    st.session_state.username = ""

if "pending_delete_quote_id" not in st.session_state:
    st.session_state.pending_delete_quote_id = None

if "pending_delete_quote_label" not in st.session_state:
    st.session_state.pending_delete_quote_label = ""


# ---------- Page config + styling ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
      /* Slightly cleaner spacing */
      .block-container { padding-top: 1.1rem; padding-bottom: 2.0rem; }

      /* Make bordered containers look like “cards” */
      [data-testid="stVerticalBlockBorderWrapper"]{
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        background: rgba(255,255,255,0.03) !important;
      }

      /* Buttons nicer */
      .stButton > button {
        border-radius: 12px !important;
        padding: 0.55rem 0.75rem !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
      }

      /* Sidebar polish */
      section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.08);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Refresh ----------
st_autorefresh(interval=POLL_SECONDS * 1000, key="refresh")

# ---------- Header ----------
left_h, right_h = st.columns([1, 1])
with left_h:
    st.title(APP_TITLE)
    st.caption("Save quotes. Copy instantly. Chat with friends.")
with right_h:
    st.write("")  # spacer
    st.write("")  # spacer
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

    st.caption("Tip: Use the search box on Quotes to find anything fast.")


# ---------- Tabs ----------
tab_quotes, tab_chat = st.tabs(["📚 Quotes", "💬 Chat"])


# ==========================================
# ================ QUOTES ==================
# ==========================================
with tab_quotes:
    top = st.container(border=True)
    with top:
        st.subheader("Quotes")
        c1, c2, c3 = st.columns([2.2, 1.2, 1.2])

        with c1:
            q_search = st.text_input("Search", placeholder="Search quotes or authors…")

        with c2:
            sort_mode = st.selectbox("Sort", ["Newest first", "Oldest first", "Author A–Z"])

        with c3:
            show_meta = st.toggle("Show dates", value=True)

    # Add quote card
    with st.container(border=True):
        st.markdown("#### Add a quote")
        with st.form("add_quote", clear_on_submit=True):
            text = st.text_area("Quote", height=90, placeholder="Write your quote…")
            author = st.text_input("Author (optional)", placeholder="e.g., Marcus Aurelius")
            submitted = st.form_submit_button("Add Quote", use_container_width=True)

            if submitted and text.strip():
                post_data(
                    "/quotes",
                    {"text": text.strip(), "author": author.strip(), "created_at": now_iso_z()},
                )
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
        items = list(quotes.items())

        # Clean + normalize before filtering/sorting
        normalized = []
        for qid, q in items:
            q_text = clean_quote_text(q.get("text") or "")
            q_author = (q.get("author") or "").strip()
            created_raw = (q.get("created_at") or "").strip()
            normalized.append((qid, q_text, q_author, created_raw))

        # Filter
        if q_search.strip():
            needle = q_search.strip().lower()
            normalized = [
                row for row in normalized
                if needle in (row[1] or "").lower() or needle in (row[2] or "").lower()
            ]

        # Sort
        if sort_mode == "Newest first":
            normalized.sort(key=lambda r: r[3] or "", reverse=True)
        elif sort_mode == "Oldest first":
            normalized.sort(key=lambda r: r[3] or "")
        else:  # Author A–Z
            normalized.sort(key=lambda r: (r[2] or "").lower())

        st.markdown("#### Your quotes")
        st.caption(f"{len(normalized)} shown")

        for qid, q_text, q_author, created_raw in normalized:
            label = f"“{q_text}”" if q_text else "“(empty)”"
            to_copy = q_text + (f" — {q_author}" if q_author else "")

            row = st.container(border=True)
            with row:
                # Content
                st.markdown(f"### {label}")
                if q_author:
                    st.caption(f"— {q_author}")
                if show_meta and created_raw:
                    st.caption(f"Added: {pretty_ts(created_raw)}")

                # Actions
                a1, a2, a3 = st.columns([1.2, 1.0, 8.0])
                with a1:
                    copy_button(to_copy, element_id=f"copy_btn_{qid}", label="Copy")
                with a2:
                    if st.button("🗑 Delete", key=f"ask_del_{qid}", use_container_width=True):
                        st.session_state.pending_delete_quote_id = qid
                        st.session_state.pending_delete_quote_label = (
                            f"“{q_text}”" + (f" — {q_author}" if q_author else "")
                        )
                        st.rerun()
                with a3:
                    st.write("")  # spacer


# ==========================================
# ================= CHAT ===================
# ==========================================
with tab_chat:
    st.subheader("Chat")

    if not st.session_state.username.strip():
        st.warning("Set a username in the sidebar to chat.")
    else:
        # Messages
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

        # Composer
        with st.container(border=True):
            st.markdown("#### Send a message")
            with st.form("send_msg", clear_on_submit=True):
                msg = st.text_input("Message", placeholder="Type a message…")
                sent = st.form_submit_button("Send", use_container_width=True)

                if sent and msg.strip():
                    post_data(
                        "/chat",
                        {"user": st.session_state.username.strip(), "text": msg.strip(), "ts": now_iso_z()},
                    )
                    st.toast("Sent ✅")
                    clear_cache_and_rerun()
