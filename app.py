import base64
import io

import requests
import streamlit as st
from PIL import Image, ImageOps

try:
    from st_img_pastebutton import paste
except Exception:  # package na thakle paste button hide thakbe
    paste = None

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

LIST_COLUMNS = "id,name,number,uid,trnx_id,problem,has_image"


def api(method, params=None, json=None):
    r = requests.request(
        method, TABLE_URL, headers=HEADERS, params=params, json=json, timeout=20
    )
    r.raise_for_status()
    return r


def fetch_records():
    return api("GET", params={"select": LIST_COLUMNS, "order": "id.desc"}).json()


@st.cache_data(show_spinner=False, ttl=3600)
def get_image(rid):
    try:
        rows = api("GET", params={"select": "image", "id": f"eq.{rid}"}).json()
        b64 = rows[0].get("image") if rows else None
        return base64.b64decode(b64) if b64 else None
    except Exception:
        return None


def prepare_image(raw: bytes) -> str:
    """Chhobi chhoto kore (max 1280px) JPEG banay, tarpor base64 text."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


# ---------- Form state ----------
for k, v in (
    ("f_name", ""),
    ("f_number", ""),
    ("f_uid", ""),
    ("f_trnx", ""),
    ("f_problem", ""),
    ("f_rmimg", False),
    ("editing_id", None),
    ("editing_has_image", False),
    ("ver", 0),
    ("cur_up", None),
    ("cur_paste", None),
):
    st.session_state.setdefault(k, v)


def clear_form():
    st.session_state.f_name = ""
    st.session_state.f_number = ""
    st.session_state.f_uid = ""
    st.session_state.f_trnx = ""
    st.session_state.f_problem = ""
    st.session_state.f_rmimg = False
    st.session_state.editing_id = None
    st.session_state.editing_has_image = False
    st.session_state.cur_up = None
    st.session_state.cur_paste = None
    st.session_state.ver += 1  # uploader ar paste button reset


def staged_image_bytes():
    """Ekhon baachha/paste kora chhobi (thakle) bytes hishabe."""
    ver = st.session_state.ver
    up = st.session_state.get(f"up_{ver}") or st.session_state.cur_up
    if up is not None:
        return up.getvalue()
    pasted = st.session_state.get(f"pp_{ver}") or st.session_state.cur_paste
    if pasted and isinstance(pasted, str) and "," in pasted:
        try:
            return base64.b64decode(pasted.split(",", 1)[1])
        except Exception:
            return None
    return None


def save_record():
    name = st.session_state.f_name.strip()
    number = st.session_state.f_number.strip()
    uid = st.session_state.f_uid.strip()
    trnx = st.session_state.f_trnx.strip()
    problem = st.session_state.f_problem.strip()
    raw = staged_image_bytes()

    if not (name or number or uid or trnx or problem or raw):
        st.session_state.flash = ("warning", "Kichu likho, tarpor Save dao.")
        return

    payload = {
        "name": name,
        "number": number,
        "uid": uid,
        "trnx_id": trnx,
        "problem": problem,
    }
    if raw:
        try:
            payload["image"] = prepare_image(raw)
            payload["has_image"] = True
        except Exception:
            st.session_state.flash = ("error", "Chhobi ta pora jay ni. Onno chhobi dao.")
            return
    elif st.session_state.editing_id and st.session_state.f_rmimg:
        payload["image"] = None
        payload["has_image"] = False

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
    get_image.clear()
    clear_form()
    st.session_state.flash = ("success", msg)


def start_edit(rec):
    clear_form()
    st.session_state.f_name = rec.get("name") or ""
    st.session_state.f_number = rec.get("number") or ""
    st.session_state.f_uid = rec.get("uid") or ""
    st.session_state.f_trnx = rec.get("trnx_id") or ""
    st.session_state.f_problem = rec.get("problem") or ""
    st.session_state.editing_id = rec["id"]
    st.session_state.editing_has_image = bool(rec.get("has_image"))


def delete_record(rid):
    try:
        api("DELETE", params={"id": f"eq.{rid}"})
    except Exception as e:
        st.session_state.flash = ("error", f"Delete hoy ni: {e}")
        return
    get_image.clear()
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

    st.markdown("**Photo**")
    ver = st.session_state.ver
    up_file = st.file_uploader(
        "Drag and drop kore dao, ba Browse files e tap koro",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"up_{ver}",
    )
    pasted = None
    if paste is not None:
        pasted = paste(label="📋 Clipboard theke paste koro", key=f"pp_{ver}")
    else:
        st.caption("Paste button load hoy ni. Drag and drop ba Browse use koro.")

    st.session_state.cur_up = up_file
    st.session_state.cur_paste = pasted

    preview = staged_image_bytes()
    if preview:
        st.image(preview, caption="Ei chhobi ta save hobe", use_container_width=True)
    elif st.session_state.editing_id and st.session_state.editing_has_image:
        current = get_image(st.session_state.editing_id)
        if current and not st.session_state.f_rmimg:
            st.image(current, caption="Ekhonkar chhobi", use_container_width=True)
        st.checkbox("Ei chhobi ta muche dao", key="f_rmimg")

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
            if rec.get("has_image"):
                img = get_image(rec["id"])
                if img:
                    st.image(img, use_container_width=True)
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
