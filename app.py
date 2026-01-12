import re
import uuid
import time
import html as html_lib
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

# ================= CONFIG =================
FIREBASE_DB_URL = "https://quotesaver-e8fae-default-rtdb.europe-west1.firebasedatabase.app"
POLL_SECONDS = 2                 # used ONLY for Chat refresh now
APP_TITLE = "HJ Quotes"
CACHE_TTL_SECONDS = 10           # a bit higher because we now do optimistic UI
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


def post_data_return_key(path: str, data: dict) -> str | None:
    # Firebase RTDB POST returns {"name": "<generated_key>"}
    r = requests.post(fb(path), json=data, timeout=8)
    if not r.ok:
        return None
    try:
        return (r.json() or {}).get("name")
    except Exception:
        return None


def put_value(path: str, value):
    requests.put(fb(path), json=value, timeout=8)


def delete_data(path: str):
    requests.delete(fb(path), timeout=8)


def refresh_all_data():
    """Hard refresh: clear cache and reload quotes/collections into session."""
    st.cache_data.clear()
    st.session_state.quotes = get_data_cached("/quotes") or {}
    st.session_state.collections = get_data_cached("/collections") or {}
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


# ---------- Copy button (fast + animated, stays green) ----------
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
          transition: transform 120ms ease, filter 160ms ease, background 160ms ease;
          will-change: transform;
        }}
        .hj-copy:hover {{
          background: #1ed760;
          filter: drop-shadow(0 10px 18px rgba(29,185,84,0.18));
        }}
        .hj-copy:active {{ transform: scale(0.97); }}
        .hj-copy.hj-copied {{ animation: hjCopied 350ms ease; }}
        @keyframes hjCopied {{
          0%   {{ transform: scale(1); }}
          50%  {{ transform: scale(1.03); }}
          100% {{ transform: scale(1); }}
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

              btn.classList.remove("hj-copied");
              void btn.offsetWidth;
              btn.classList.add("hj-copied");

              btn.innerText = "✅ Copied";
              setTimeout(() => {{
                btn.innerText = old;
                btn.classList.remove("hj-copied");
              }}, 900);
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
    st.session_state.page = "Quotes"  # Quotes / Chat

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "ALL"  # ALL / FAV / COL

if "selected_collection_id" not in st.session_state:
    st.session_state.selected_collection_id = None

if "pending_delete_quote_id" not in st.session_state:
    st.session_state.pending_delete_quote_id = None

if "pending_delete_quote_label" not in st.session_state:
    st.session_state.pending_delete_quote_label = ""

# Smooth feedback
if "pulse_hero" not in st.session_state:
    st.session_state.pulse_hero = False

# Last-action glow
if "last_action_qid" not in st.session_state:
    st.session_state.last_action_qid = None
if "last_action_ts" not in st.session_state:
    st.session_state.last_action_ts = 0.0


def mark_last_action(qid: str | None):
    st.session_state.last_action_qid = qid
    st.session_state.last_action_ts = time.time()


def should_flash(qid: str) -> bool:
    if st.session_state.last_action_qid != qid:
        return False
    return (time.time() - float(st.session_state.last_action_ts or 0.0)) <= 1.1


# ---------- Load data once per session (then optimistic updates) ----------
if "quotes" not in st.session_state:
    st.session_state.quotes = get_data_cached("/quotes") or {}

if "collections" not in st.session_state:
    st.session_state.collections = get_data_cached("/collections") or {}


# ---------- Page config + Spotify-ish UI ----------
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
      :root{
        --bg0:#0b0f0c;
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

      .block-container { padding-top: 1.0rem; padding-bottom: 2.2rem; }

      section[data-testid="stSidebar"]{
        background: linear-gradient(180deg, rgba(18,18,18,0.98), rgba(12,12,12,0.98));
        border-right: 1px solid rgba(255,255,255,0.06);
      }

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

      [data-testid="stVerticalBlockBorderWrapper"]{
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        background: rgba(18,18,18,0.85) !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease, border-color 160ms ease;
        will-change: transform;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:hover{
        background: rgba(24,24,24,0.92) !important;
        border-color: rgba(255,255,255,0.10) !important;
        transform: translateY(-2px);
        box-shadow: 0 14px 40px rgba(0,0,0,0.45);
      }

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

      .stButton > button[kind="primary"]{
        background: var(--green) !important;
        color: #0b0f0c !important;
        border: 1px solid rgba(0,0,0,0.0) !important;
        border-radius: 999px !important;
        font-weight: 900 !important;
      }
      .stButton > button[kind="primary"]:hover{ background: var(--green2) !important; }

      .stButton > button{
        border-radius: 999px !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        background: rgba(255,255,255,0.04) !important;
        font-weight: 800 !important;
        transition: transform 120ms ease, background 160ms ease, border-color 160ms ease;
      }
      .stButton > button:active{ transform: scale(0.97); }

      section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] p,
      section[data-testid="stSidebar"] span{
        color: var(--text) !important;
      }

      section[data-testid="stSidebar"] div[role="radiogroup"] > label{
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.03);
        border-radius: 16px;
        padding: 12px 12px;
        margin: 8px 0;
      }
      section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
        border-color: rgba(29,185,84,0.45) !important;
        background: rgba(29,185,84,0.16) !important;
      }

      /* Hero pulse */
      @keyframes hjPulse { 0%{transform:scale(1)} 50%{transform:scale(1.03)} 100%{transform:scale(1)} }
      .hj-pulse { animation: hjPulse 320ms ease; }

      /* Quote body + glow highlight */
      @keyframes hjGlow {
        0%   { box-shadow: 0 0 0 rgba(29,185,84,0.0); border-color: rgba(255,255,255,0.10); }
        30%  { box-shadow: 0 0 0 6px rgba(29,185,84,0.10), 0 18px 50px rgba(0,0,0,0.55); border-color: rgba(29,185,84,0.55); }
        100% { box-shadow: 0 0 0 rgba(29,185,84,0.0); border-color: rgba(255,255,255,0.10); }
      }
      .hj-quote-body{
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.02);
        padding: 12px 14px;
        margin-bottom: 10px;
      }
      .hj-quote-body.hj-flash{ animation: hjGlow 1050ms ease; }
      .hj-quote-text{ font-size: 1.15rem; font-weight: 800; letter-spacing: -0.01em; }
      .hj-quote-meta{ margin-top: 8px; color: rgba(255,255,255,0.72); font-size: 0.85rem; }

      hr { border-color: rgba(255,255,255,0.08) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Derived collection lists ----------
collections = st.session_state.collections
quotes = st.session_state.quotes

collection_name_by_id = {cid: (c.get("name") or "Untitled").strip() for cid, c in collections.items()}
collection_ids_sorted = sorted(collection_name_by_id.keys(), key=lambda cid: collection_name_by_id[cid].lower())


# ---------- Sidebar: left rail ----------
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
    st.markdown("### Library")
    view_options = ["All Quotes", "❤️ Favourites"] + [f"📁 {collection_name_by_id[cid]}" for cid in collection_ids_sorted]
    view_choice = st.radio(label="", options=view_options, index=0, label_visibility="collapsed")

    if view_choice == "All Quotes":
        st.session_state.view_mode = "ALL"
        st.session_state.selected_collection_id = None
    elif view_choice == "❤️ Favourites":
        st.session_state.view_mode = "FAV"
        st.session_state.selected_collection_id = None
    else:
        st.session_state.view_mode = "COL"
        selected_name = view_choice.replace("📁 ", "", 1)
        matched = None
        for cid, nm in collection_name_by_id.items():
            if nm == selected_name:
                matched = cid
                break
        st.session_state.selected_collection_id = matched

    st.divider()
    st.markdown("### Create collection")
    with st.form("create_collection", clear_on_submit=True):
        new_name = st.text_input("Name", placeholder="e.g. Stoicism", label_visibility="collapsed")
        make = st.form_submit_button("Create", use_container_width=True)
        if make and new_name.strip():
            cid = post_data_return_key("/collections", {"name": new_name.strip(), "created_at": now_iso_z()})
            if cid:
                # optimistic add
                st.session_state.collections[cid] = {"name": new_name.strip(), "created_at": now_iso_z()}
                st.session_state.pulse_hero = True
                st.toast("Collection created ✅")
                st.rerun()

    st.divider()
    st.markdown("### Settings")
    st.session_state.username = st.text_input("Username", value=st.session_state.username, placeholder="Enter your name")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Refresh", use_container_width=True):
            refresh_all_data()
    with c2:
        st.caption("Fast UI")

    st.caption("Tip: Quotes don’t auto-refresh anymore (only Chat does).")


# ---------- Hero (pulse after actions) ----------
hero_class = "hj-hero hj-pulse" if st.session_state.pulse_hero else "hj-hero"
st.session_state.pulse_hero = False

st.markdown(
    f"""
    <div class="{hero_class}">
      <h1>{APP_TITLE}</h1>
      <div class="sub">Favourites • Collections • Optimistic UI (no laggy full refresh on clicks)</div>
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

    # Add quote
    with st.container(border=True):
        st.markdown("#### Add a quote")
        with st.form("add_quote", clear_on_submit=True):
            text = st.text_area("Quote", height=90, placeholder="Write your quote…")
            author = st.text_input("Author (optional)", placeholder="e.g., Marcus Aurelius")
            submitted = st.form_submit_button("Add Quote", use_container_width=True)

            if submitted and text.strip():
                payload = {
                    "text": text.strip(),
                    "author": author.strip(),
                    "created_at": now_iso_z(),
                    "fav_by": {},
                    "collections": {},
                }
                qid = post_data_return_key("/quotes", payload)
                if qid:
                    # optimistic add (instant)
                    st.session_state.quotes[qid] = payload
                    st.session_state.pulse_hero = True
                    mark_last_action(qid)
                    st.toast("Quote added ✅")
                    st.rerun()

    # Delete confirmation
    if st.session_state.pending_delete_quote_id:
        with st.container(border=True):
            st.warning("Delete quote?")
            st.write(st.session_state.pending_delete_quote_label)
            a, b, _ = st.columns([1, 1, 6])
            with a:
                if st.button("✅ Confirm delete", type="primary", use_container_width=True):
                    qid = st.session_state.pending_delete_quote_id
                    delete_data(f"/quotes/{qid}")
                    # optimistic remove
                    st.session_state.quotes.pop(qid, None)
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    st.session_state.pulse_hero = True
                    mark_last_action(None)
                    st.toast("Deleted 🗑️")
                    st.rerun()
            with b:
                if st.button("✖ Cancel", use_container_width=True):
                    st.session_state.pending_delete_quote_id = None
                    st.session_state.pending_delete_quote_label = ""
                    st.rerun()

    # Normalize quotes
    uid = st.session_state.user_id
    normalized = []
    for qid, q in (st.session_state.quotes or {}).items():
        q_text = clean_quote_text(q.get("text") or "")
        q_author = (q.get("author") or "").strip()
        created_raw = (q.get("created_at") or "").strip()

        fav_by = q.get("fav_by") or {}
        is_fav = bool(fav_by.get(uid))

        q_cols = q.get("collections") or {}
        col_ids = [cid for cid, v in q_cols.items() if v]

        normalized.append((qid, q_text, q_author, created_raw, is_fav, col_ids))

    # View filter
    if st.session_state.view_mode == "FAV":
        normalized = [r for r in normalized if r[4] is True]

    if st.session_state.view_mode == "COL" and st.session_state.selected_collection_id:
        wanted = st.session_state.selected_collection_id
        normalized = [r for r in normalized if wanted in set(r[5])]

    # Search
    if q_search.strip():
        needle = q_search.strip().lower()
        normalized = [
            r for r in normalized
            if needle in (r[1] or "").lower() or needle in (r[2] or "").lower()
        ]

    # Sort
    if sort_mode == "Newest first":
        normalized.sort(key=lambda r: r[3] or "", reverse=True)
    elif sort_mode == "Oldest first":
        normalized.sort(key=lambda r: r[3] or "")
    else:
        normalized.sort(key=lambda r: (r[2] or "").lower())

    # Title
    with st.container(border=True):
        title = "All Quotes"
        if st.session_state.view_mode == "FAV":
            title = "❤️ Favourites"
        if st.session_state.view_mode == "COL" and st.session_state.selected_collection_id:
            title = f"📁 {collection_name_by_id.get(st.session_state.selected_collection_id, 'Collection')}"
        st.markdown(f"#### {title}")
        st.caption(f"{len(normalized)} shown")

    # Render
    for qid, q_text, q_author, created_raw, is_fav, col_ids in normalized:
        flash = should_flash(qid)

        safe_quote = html_lib.escape(q_text or "")
        safe_author = html_lib.escape(q_author or "")
        label_text = f"“{safe_quote}”" if safe_quote else "“(empty)”"

        meta_bits = []
        if q_author:
            meta_bits.append(f"— {safe_author}")
        if show_meta and created_raw:
            meta_bits.append(f"Added: {html_lib.escape(pretty_ts(created_raw))}")
        meta_html = " • ".join(meta_bits)

        to_copy = (q_text or "") + (f" — {q_author}" if q_author else "")

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="hj-quote-body {'hj-flash' if flash else ''}">
                  <div class="hj-quote-text">{label_text}</div>
                  {"<div class='hj-quote-meta'>" + meta_html + "</div>" if meta_html else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Actions row (NO cache clears, optimistic updates)
            a1, a2, a3, a4, _ = st.columns([1.2, 0.95, 1.6, 1.0, 6.0])

            with a1:
                copy_button(to_copy, element_id=f"copy_btn_{qid}", label="Copy")

            with a2:
                fav_label = "💚 Fav" if not is_fav else "✅ Faved"
                if st.button(fav_label, key=f"fav_{qid}", use_container_width=True):
                    # optimistic UI first
                    q = st.session_state.quotes.get(qid, {})
                    q.setdefault("fav_by", {})
                    if is_fav:
                        q["fav_by"].pop(uid, None)
                        delete_data(f"/quotes/{qid}/fav_by/{uid}")
                    else:
                        q["fav_by"][uid] = True
                        put_value(f"/quotes/{qid}/fav_by/{uid}", True)

                    st.session_state.quotes[qid] = q
                    st.session_state.pulse_hero = True
                    mark_last_action(qid)
                    st.rerun()

            with a3:
                with st.expander("📁 Collections", expanded=False):
                    # Map names <-> ids
                    name_to_id = {v: k for k, v in collection_name_by_id.items()}
                    all_names = [collection_name_by_id[cid] for cid in collection_ids_sorted]
                    current_names = [collection_name_by_id[cid] for cid in col_ids if cid in collection_name_by_id]

                    selected = st.multiselect(
                        "Add to collections",
                        options=all_names,
                        default=current_names,
                        key=f"ms_{qid}",
                    )

                    if st.button("Save collections", key=f"save_cols_{qid}", type="primary", use_container_width=True):
                        desired_ids = set(name_to_id[n] for n in selected if n in name_to_id)
                        current_ids = set(col_ids)

                        to_add = desired_ids - current_ids
                        to_remove = current_ids - desired_ids

                        # optimistic local update
                        q = st.session_state.quotes.get(qid, {})
                        q.setdefault("collections", {})
                        for cid in to_add:
                            q["collections"][cid] = True
                            put_value(f"/quotes/{qid}/collections/{cid}", True)
                        for cid in to_remove:
                            q["collections"].pop(cid, None)
                            delete_data(f"/quotes/{qid}/collections/{cid}")

                        st.session_state.quotes[qid] = q
                        st.session_state.pulse_hero = True
                        mark_last_action(qid)
                        st.toast("Collections updated ✅")
                        st.rerun()

            with a4:
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
    # Auto-refresh ONLY here (this is the main “speed fix”)
    st_autorefresh(interval=POLL_SECONDS * 1000, key="refresh_chat")

    with st.container(border=True):
        st.subheader("Chat")
        if not st.session_state.username.strip():
            st.warning("Set a username in the sidebar to chat.")

    if st.session_state.username.strip():
        # Chat can be fetched live; it’s okay here because the page is already refreshing
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
                    st.markdown(f"**{html_lib.escape(user)}:** {html_lib.escape(text)}")
                    if ts_raw:
                        st.caption(pretty_ts(ts_raw))

        with st.container(border=True):
            st.markdown("#### Send a message")
            with st.form("send_msg", clear_on_submit=True):
                msg = st.text_input("Message", placeholder="Type a message…")
                sent = st.form_submit_button("Send", use_container_width=True)

                if sent and msg.strip():
                    requests.post(
                        fb("/chat"),
                        json={"user": st.session_state.username.strip(), "text": msg.strip(), "ts": now_iso_z()},
                        timeout=8,
                    )
                    st.session_state.pulse_hero = True
                    st.toast("Sent ✅")
                    st.rerun()
