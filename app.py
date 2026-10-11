import requests
import streamlit as st

st.set_page_config(page_title="Records", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 2rem; max-width: 1100px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Supabase (free database) ----------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    if SUPABASE_URL.endswith("/rest/v1"):
        SUPABASE_URL = SUPABASE_URL[: -len("/rest/v1")]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error(
        "Database connect kora hoy ni. Streamlit-er App settings > Secrets e "
        "SUPABASE_URL ar SUPABASE_KEY dao."
    )
    st.stop()

TABLE_URL = f"{SUPABASE_URL}/rest/v1/records"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
if not SUPABASE_KEY.startswith("sb_"):  # purono (legacy) JWT key hole
    HEADERS["Authorization"] = f"Bearer {SUPABASE_KEY}"


def api(method, params=None, json=None):
    r = requests.request(
        method, TABLE_URL, headers=HEADERS, params=params, json=json, timeout=15
    )
    r.raise_for_status()
    return r


def fetch_records():
    r = api("GET", params={"select": "*", "order": "id.desc"})
    return r.json()


# ---------- Form state ----------
for k, v in (
    ("f_name", ""),
    ("f_number", ""),
    ("f_uid", ""),
    ("f_trnx", ""),
    ("f_problem", ""),
    ("editing_id", None),
):
    st.session_state.setdefault(k, v)


def clear_form():
    st.session_state.f_name = ""
    st.session_state.f_number = ""
    st.session_state.f_uid = ""
    st.session_state.f_trnx = ""
    st.session_state.f_problem = ""
    st.session_state.editing_id = None


def save_record():
    name = st.session_state.f_name.strip()
    number = st.session_state.f_number.strip()
    uid = st.session_state.f_uid.strip()
    trnx = st.session_state.f_trnx.strip()
    problem = st.session_state.f_problem.strip()
    if not (name or number or uid or trnx or problem):
        st.session_state.flash = ("warning", "Kichu likho, tarpor Save dao.")
        return
    payload = {
        "name": name,
        "number": number,
        "uid": uid,
        "trnx_id": trnx,
        "problem": problem,
    }
    try:
        if st.session_state.editing_id:
            api("PATCH", params={"id": f"eq.{st.session_state.editing_id}"}, json=payload)
            msg = "Update hoyeche."
        else:
            api("POST", json=payload)
            msg = "Save hoyeche."
    except Exception as e:
        st.session_state.flash = ("error", f"Save hoy ni: {e}")
        return
    clear_form()
    st.session_state.flash = ("success", msg)


def start_edit(rec):
    st.session_state.f_name = rec.get("name") or ""
    st.session_state.f_number = rec.get("number") or ""
    st.session_state.f_uid = rec.get("uid") or ""
    st.session_state.f_trnx = rec.get("trnx_id") or ""
    st.session_state.f_problem = rec.get("problem") or ""
    st.session_state.editing_id = rec["id"]


def delete_record(rid):
    try:
        api("DELETE", params={"id": f"eq.{rid}"})
    except Exception as e:
        st.session_state.flash = ("error", f"Delete hoy ni: {e}")
        return
    if st.session_state.editing_id == rid:
        clear_form()


# ---------- UI ----------
st.markdown("### Records")

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])

left, right = st.columns([1, 1], gap="large")

with left:
    if st.session_state.editing_id:
        st.info("Edit korcho. Bodle Save dao, ba Remove diye batil koro.")
    st.text_input("Name", key="f_name")
    st.text_input("Number", key="f_number")
    st.text_input("ID", key="f_uid")
    st.text_input("TrnxID", key="f_trnx")
    st.text_area("Problem", key="f_problem", height=220)

    b1, b2 = st.columns(2)
    b1.button("Save", type="primary", use_container_width=True, on_click=save_record)
    b2.button("Remove", use_container_width=True, on_click=clear_form)

with right:
    st.markdown("**Saved**")
    try:
        records = fetch_records()
    except Exception as e:
        records = []
        st.error(f"Saved list ana jay ni: {e}")

    if not records:
        st.caption("Ekhono kichu save kora nai.")

    for rec in records:
        with st.container(border=True):
            st.markdown(f"**{rec.get('name') or '-'}**  ·  ID: {rec.get('uid') or '-'}")
            if rec.get("number") or rec.get("trnx_id"):
                st.caption(
                    f"Number: {rec.get('number') or '-'}  ·  TrnxID: {rec.get('trnx_id') or '-'}"
                )
            if rec.get("problem"):
                st.text(rec["problem"])
            e_col, d_col = st.columns(2)
            e_col.button(
                "Edit",
                key=f"edit_{rec['id']}",
                use_container_width=True,
                on_click=start_edit,
                args=(rec,),
            )
            d_col.button(
                "Delete",
                key=f"del_{rec['id']}",
                use_container_width=True,
                on_click=delete_record,
                args=(rec["id"],),
            )
