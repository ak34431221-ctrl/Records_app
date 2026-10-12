import base64
import hashlib
import io
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image, ImageOps

try:
    from st_img_pastebutton import paste
except Exception:  # if the package is missing, the paste button is hidden
    paste = None

MAX_IMAGES = 5

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
        "Could not connect to the database. Add SUPABASE_URL and SUPABASE_KEY "
        "in the Streamlit app Settings > Secrets."
    )
    st.stop()

TABLE_URL = f"{SUPABASE_URL}/rest/v1/records"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
if not SUPABASE_KEY.startswith("sb_"):  # legacy JWT key
    HEADERS["Authorization"] = f"Bearer {SUPABASE_KEY}"

LIST_COLUMNS = "id,name,number,uid,trnx_id,problem,image_count"


def api(method, params=None, json=None):
    r = requests.request(
        method, TABLE_URL, headers=HEADERS, params=params, json=json, timeout=30
    )
    r.raise_for_status()
    return r


def fetch_records():
    # Records marked as deleted stay in the database but are hidden here.
    params = {
        "select": LIST_COLUMNS,
        "order": "id.desc",
        "or": "(deleted.eq.false,deleted.is.null)",
    }
    return api("GET", params=params).json()


def fetch_images_b64(rid):
    rows = api("GET", params={"select": "images", "id": f"eq.{rid}"}).json()
    return (rows[0].get("images") or []) if rows else []


@st.cache_data(show_spinner=False, ttl=3600)
def get_images(rid):
    try:
        return [base64.b64decode(b) for b in fetch_images_b64(rid)]
    except Exception:
        return []


def prepare_image(raw: bytes) -> str:
    """Shrink the photo (max 1280px), convert to JPEG, return base64 text."""
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
    ("editing_id", None),
    ("ver", 0),
    ("exist_b64", []),      # photos already saved (when editing)
    ("pasted_list", []),    # newly pasted photos (bytes)
    ("last_paste_hash", None),
    ("cur_up", []),
):
    st.session_state.setdefault(k, v)


def clear_form():
    st.session_state.f_name = ""
    st.session_state.f_number = ""
    st.session_state.f_uid = ""
    st.session_state.f_trnx = ""
    st.session_state.f_problem = ""
    st.session_state.editing_id = None
    st.session_state.exist_b64 = []
    st.session_state.pasted_list = []
    st.session_state.last_paste_hash = None
    st.session_state.cur_up = []
    st.session_state.ver += 1  # resets the uploader and the paste button


def uploaded_bytes():
    ver = st.session_state.ver
    files = st.session_state.get(f"up_{ver}") or st.session_state.cur_up or []
    return [f.getvalue() for f in files]


def total_images():
    return (
        len(st.session_state.exist_b64)
        + len(uploaded_bytes())
        + len(st.session_state.pasted_list)
    )


def remove_item(kind, i):
    lst = st.session_state.exist_b64 if kind == "exist" else st.session_state.pasted_list
    if 0 <= i < len(lst):
        lst.pop(i)


def save_record():
    name = st.session_state.f_name.strip()
    number = st.session_state.f_number.strip()
    uid = st.session_state.f_uid.strip()
    trnx = st.session_state.f_trnx.strip()
    problem = st.session_state.f_problem.strip()

    new_raw = uploaded_bytes() + list(st.session_state.pasted_list)
    n_total = len(st.session_state.exist_b64) + len(new_raw)

    if not (name or number or uid or trnx or problem or n_total):
        st.session_state.flash = ("warning", "Please fill in something before saving.")
        return
    if n_total > MAX_IMAGES:
        st.session_state.flash = (
            "warning",
            f"You can add up to {MAX_IMAGES} photos. Please remove {n_total - MAX_IMAGES}.",
        )
        return

    images = list(st.session_state.exist_b64)
    try:
        images += [prepare_image(b) for b in new_raw]
    except Exception:
        st.session_state.flash = ("error", "Could not read one of the photos. Please use a different photo.")
        return

    payload = {
        "name": name,
        "number": number,
        "uid": uid,
        "trnx_id": trnx,
        "problem": problem,
        "images": images,
        "image_count": len(images),
    }

    try:
        if st.session_state.editing_id:
            api("PATCH", params={"id": f"eq.{st.session_state.editing_id}"}, json=payload)
            msg = "Updated."
        else:
            api("POST", json=payload)
            msg = "Saved."
    except Exception as e:
        st.session_state.flash = ("error", f"Could not save: {e}")
        return
    get_images.clear()
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
    if rec.get("image_count"):
        try:
            st.session_state.exist_b64 = fetch_images_b64(rec["id"])
        except Exception as e:
            st.session_state.flash = ("error", f"Could not load photos: {e}")


def delete_record(rid):
    """Soft delete: hide from the app, but keep the row in the database."""
    try:
        api(
            "PATCH",
            params={"id": f"eq.{rid}"},
            json={
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        st.session_state.flash = ("error", f"Could not delete: {e}")
        return
    get_images.clear()
    if st.session_state.editing_id == rid:
        clear_form()
    st.session_state.flash = ("success", "Deleted from the app. A copy is kept in the database.")


def image_grid(imgs, kind=None):
    """Show photos in 3 columns. If kind is given, add a remove button under each."""
    for start in range(0, len(imgs), 3):
        cols = st.columns(3)
        for j, b in enumerate(imgs[start:start + 3]):
            i = start + j
            with cols[j]:
                st.image(b, use_container_width=True)
                if kind:
                    st.button(
                        "✕ Remove",
                        key=f"rm_{kind}_{i}",
                        on_click=remove_item,
                        args=(kind, i),
                        use_container_width=True,
                    )


# ---------- UI ----------
st.markdown("### Records")

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])

left, right = st.columns([1, 1], gap="large")

with left:
    if st.session_state.editing_id:
        st.info("Editing a record. Press Save to update, or Remove to cancel.")
    st.text_input("Name", key="f_name")
    st.text_input("Number", key="f_number")
    st.text_input("ID", key="f_uid")
    st.text_input("TrnxID", key="f_trnx")

    st.markdown(f"**Photo** (up to {MAX_IMAGES})")
    ver = st.session_state.ver
    up_files = st.file_uploader(
        "Drag and drop photos here, or click Browse files",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"up_{ver}",
    )
    st.session_state.cur_up = up_files or []

    if paste is not None:
        pasted = paste(label="📋 Paste from clipboard", key=f"pp_{ver}")
        if pasted and isinstance(pasted, str) and "," in pasted:
            h = hashlib.md5(pasted.encode()).hexdigest()
            if h != st.session_state.last_paste_hash:
                st.session_state.last_paste_hash = h
                try:
                    st.session_state.pasted_list.append(
                        base64.b64decode(pasted.split(",", 1)[1])
                    )
                except Exception:
                    pass
    else:
        st.caption("Paste button could not load. Use drag and drop or Browse files.")

    exist_imgs = [base64.b64decode(b) for b in st.session_state.exist_b64]
    new_uploaded = uploaded_bytes()
    pasted_imgs = list(st.session_state.pasted_list)

    if exist_imgs:
        st.caption("Saved photos")
        image_grid(exist_imgs, "exist")
    if pasted_imgs:
        st.caption("Pasted photos")
        image_grid(pasted_imgs, "paste")
    if new_uploaded:
        st.caption("Uploaded photos (use the x in the upload list above to remove)")
        image_grid(new_uploaded)

    n = total_images()
    if n > MAX_IMAGES:
        st.warning(f"Total {n} photos. Maximum is {MAX_IMAGES}, please remove {n - MAX_IMAGES}.")
    else:
        st.caption(f"Photos: {n} / {MAX_IMAGES}")

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
        st.error(f"Could not load saved records: {e}")

    if not records:
        st.caption("Nothing saved yet.")

    for rec in records:
        with st.container(border=True):
            st.markdown(f"**{rec.get('name') or '-'}**  ·  ID: {rec.get('uid') or '-'}")
            if rec.get("number") or rec.get("trnx_id"):
                st.caption(
                    f"Number: {rec.get('number') or '-'}  ·  TrnxID: {rec.get('trnx_id') or '-'}"
                )
            if rec.get("problem"):
                st.text(rec["problem"])
            if rec.get("image_count"):
                imgs = get_images(rec["id"])
                if imgs:
                    image_grid(imgs)
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
