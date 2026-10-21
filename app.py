import base64
import hashlib
import io
import math
import re
from datetime import date, datetime, timezone

import requests
import streamlit as st
from PIL import Image, ImageOps

try:
    from st_img_pastebutton import paste
except Exception:  # if the package is missing, the paste button is hidden
    paste = None

st.set_page_config(page_title="My Tools", page_icon="🧰", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem; max-width: 1100px;}
    /* Tabs as boxes */
    div[data-baseweb="tab-list"] {gap: 10px; flex-wrap: wrap;}
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {display: none !important;}
    button[data-baseweb="tab"] {
        background: #ffffff; border: 1px solid #e3e7ee; border-radius: 10px;
        padding: 8px 18px; height: auto;
    }
    button[data-baseweb="tab"] p {font-size: 15px; color: #6b7280 !important;}
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #4f7cff; border-color: #4f7cff;
    }
    button[data-baseweb="tab"][aria-selected="true"] p {color: #ffffff !important;}

    /* Billing */
    .card {
        background: #ffffff; border: 1px solid #eef0f3;
        border-radius: 14px; padding: 14px 16px; margin-top: 12px;
        color: #1f2937;
    }
    .row {display: flex; justify-content: space-between; padding: 5px 0;
          font-size: 15px; color: #6b7280;}
    .row b {color: #1f2937; font-weight: 500;}
    .row b.blue {color: #4f7cff; font-weight: 600;}
    .opt-title {font-size: 13px; color: #9ca3af; margin-bottom: 4px;}
    .total {font-size: 26px; font-weight: 600; color: #1f2937;}
    .pair {display: flex; justify-content: space-between; gap: 12px;}
    .pair > div {flex: 1;}
    .sub {font-size: 12px; color: #9ca3af;}
    .round {font-size: 26px; font-weight: 600; color: #4f7cff;}

    /* OLT commands */
    .label {font-size: 13px; color: #6b7280; margin: 14px 0 4px;}
    div[data-testid="stCodeBlock"] pre {
        background: #ffffff !important;
        border: 1px solid #eef0f3;
        border-radius: 12px;
    }
    div[data-testid="stCodeBlock"] code {color: #1f2937 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

S = st.session_state


def narrow():
    """Centered, narrower column for the small tools."""
    _, mid, _ = st.columns([1, 2, 1])
    return mid


# =====================================================================
# 1. BILLING
# =====================================================================
ONU_DEPOSIT = 500
MONTH_DAYS = 31
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
YEARS = list(range(2020, 2036))


def round_up_5(x):
    n = math.floor(x + 0.5)
    return math.ceil(n / 5) * 5


def billing_tab():
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Dhaka")).date()
    except Exception:
        today = date.today()

    st.markdown("### Billing")
    st.markdown("Connection date")
    c_day, c_month, c_year = st.columns([1, 2, 1.3])
    sel_day = c_day.selectbox("Date", list(range(1, 32)), index=today.day - 1, key="bl_day")
    sel_month = c_month.selectbox(
        "Month",
        list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda m: f"{m} - {MONTHS[m - 1]}",
        key="bl_month",
    )
    sel_year = c_year.selectbox(
        "Year",
        YEARS,
        index=YEARS.index(today.year) if today.year in YEARS else 0,
        key="bl_year",
    )
    package = st.number_input("Package (Tk)", min_value=0, value=0, step=50, key="bl_pkg")

    signature = (sel_day, sel_month, sel_year, package)

    if st.button("Calculate", use_container_width=True, key="bl_calc"):
        try:
            connection_date = date(sel_year, sel_month, sel_day)
        except ValueError:
            connection_date = None

        if connection_date is None:
            result = ("error", "This date does not exist. Please check the date and month.")
        elif package <= 0:
            result = ("warning", "Enter a package amount.")
        else:
            running_days = max(0, MONTH_DAYS - connection_date.day + 1)
            running_month = running_days * (package / MONTH_DAYS)
            option1 = running_month + ONU_DEPOSIT
            option2 = running_month + package + ONU_DEPOSIT
            html = f"""
            <div class="card">
              <div class="row">Connection date<b>{connection_date.strftime('%d-%m-%Y')}</b></div>
              <div class="row">Running days<b>{running_days} days</b></div>
              <div class="row">Running month<b>{running_month:.0f} Tk</b></div>
              <div class="row">Running month (round figure)<b class="blue">{round_up_5(running_month)} Tk</b></div>
              <div class="row">ONU deposit<b>{ONU_DEPOSIT} Tk</b></div>
            </div>
            <div class="card">
              <div class="opt-title">Option 1 · Running + ONU</div>
              <div class="pair">
                <div><div class="sub">Total</div><div class="total">{option1:.0f} Tk</div></div>
                <div><div class="sub">Round figure</div><div class="round">{round_up_5(option1)} Tk</div></div>
              </div>
            </div>
            <div class="card">
              <div class="opt-title">Option 2 · Running + 1 month advance + ONU</div>
              <div class="pair">
                <div><div class="sub">Total</div><div class="total">{option2:.0f} Tk</div></div>
                <div><div class="sub">Round figure</div><div class="round">{round_up_5(option2)} Tk</div></div>
              </div>
              <div class="row">Advance<b>{package} Tk</b></div>
            </div>
            """
            result = ("html", html)
        S.bl_result = (signature, result)

    # Show the last result only while the inputs are unchanged.
    saved = S.get("bl_result")
    if saved and saved[0] == signature:
        kind, content = saved[1]
        if kind == "html":
            st.markdown(content, unsafe_allow_html=True)
        else:
            getattr(st, kind)(content)


# =====================================================================
# 2. RECORDS (Supabase)
# =====================================================================
MAX_IMAGES = 5

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    if SUPABASE_URL.endswith("/rest/v1"):
        SUPABASE_URL = SUPABASE_URL[: -len("/rest/v1")]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
    DB_OK = True
except Exception:
    SUPABASE_URL = SUPABASE_KEY = ""
    DB_OK = False

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
if SUPABASE_KEY and not SUPABASE_KEY.startswith("sb_"):  # legacy JWT key
    HEADERS["Authorization"] = f"Bearer {SUPABASE_KEY}"

LIST_COLUMNS = "id,name,number,uid,trnx_id,problem,image_count"


def api(method, params=None, json=None, table="records"):
    r = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HEADERS,
        params=params,
        json=json,
        timeout=30,
    )
    r.raise_for_status()
    return r


@st.cache_data(show_spinner=False, ttl=15)
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


for _k, _v in (
    ("r_name", ""),
    ("r_number", ""),
    ("r_uid", ""),
    ("r_trnx", ""),
    ("r_problem", ""),
    ("r_editing_id", None),
    ("r_ver", 0),
    ("r_exist_b64", []),   # photos already saved (when editing)
    ("r_pasted", []),      # newly pasted photos (bytes)
    ("r_last_hash", None),
    ("r_cur_up", []),
):
    S.setdefault(_k, _v)


def r_clear_form():
    S.r_name = ""
    S.r_number = ""
    S.r_uid = ""
    S.r_trnx = ""
    S.r_problem = ""
    S.r_editing_id = None
    S.r_exist_b64 = []
    S.r_pasted = []
    S.r_last_hash = None
    S.r_cur_up = []
    S.r_ver += 1  # resets the uploader and the paste button


def r_uploaded_bytes():
    files = S.get(f"r_up_{S.r_ver}") or S.r_cur_up or []
    return [f.getvalue() for f in files]


def r_total_images():
    return len(S.r_exist_b64) + len(r_uploaded_bytes()) + len(S.r_pasted)


def r_remove_item(kind, i):
    lst = S.r_exist_b64 if kind == "exist" else S.r_pasted
    if 0 <= i < len(lst):
        lst.pop(i)


def r_save():
    name = S.r_name.strip()
    number = S.r_number.strip()
    uid = S.r_uid.strip()
    trnx = S.r_trnx.strip()
    problem = S.r_problem.strip()

    new_raw = r_uploaded_bytes() + list(S.r_pasted)
    n_total = len(S.r_exist_b64) + len(new_raw)

    if not (name or number or uid or trnx or problem or n_total):
        S.r_flash = ("warning", "Please fill in something before saving.")
        return
    if n_total > MAX_IMAGES:
        S.r_flash = (
            "warning",
            f"You can add up to {MAX_IMAGES} photos. Please remove {n_total - MAX_IMAGES}.",
        )
        return

    images = list(S.r_exist_b64)
    try:
        images += [prepare_image(b) for b in new_raw]
    except Exception:
        S.r_flash = ("error", "Could not read one of the photos. Please use a different photo.")
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
        if S.r_editing_id:
            api("PATCH", params={"id": f"eq.{S.r_editing_id}"}, json=payload)
            msg = "Updated."
        else:
            api("POST", json=payload)
            msg = "Saved."
    except Exception as e:
        S.r_flash = ("error", f"Could not save: {e}")
        return
    get_images.clear()
    fetch_records.clear()
    r_clear_form()
    S.r_flash = ("success", msg)


def r_start_edit(rec):
    r_clear_form()
    S.r_name = rec.get("name") or ""
    S.r_number = rec.get("number") or ""
    S.r_uid = rec.get("uid") or ""
    S.r_trnx = rec.get("trnx_id") or ""
    S.r_problem = rec.get("problem") or ""
    S.r_editing_id = rec["id"]
    if rec.get("image_count"):
        try:
            S.r_exist_b64 = fetch_images_b64(rec["id"])
        except Exception as e:
            S.r_flash = ("error", f"Could not load photos: {e}")


def r_delete(rid):
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
        S.r_flash = ("error", f"Could not delete: {e}")
        return
    get_images.clear()
    fetch_records.clear()
    if S.r_editing_id == rid:
        r_clear_form()
    S.r_flash = ("success", "Deleted from the app. A copy is kept in the database.")


def r_image_grid(imgs, kind=None):
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
                        key=f"r_rm_{kind}_{i}",
                        on_click=r_remove_item,
                        args=(kind, i),
                        use_container_width=True,
                    )


def records_tab():
    st.markdown("### Records")

    if not DB_OK:
        st.error(
            "Could not connect to the database. Add SUPABASE_URL and SUPABASE_KEY "
            "in the Streamlit app Settings > Secrets."
        )
        return

    flash = S.pop("r_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    left, right = st.columns([1, 1], gap="large")

    with left:
        if S.r_editing_id:
            st.info("Editing a record. Press Save to update, or Remove to cancel.")
        st.text_input("Name", key="r_name")
        st.text_input("Number", key="r_number")
        st.text_input("ID", key="r_uid")
        st.text_input("TrnxID", key="r_trnx")

        st.markdown(f"**Photo** (up to {MAX_IMAGES})")
        ver = S.r_ver
        up_files = st.file_uploader(
            "Drag and drop photos here, or click Browse files",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"r_up_{ver}",
        )
        S.r_cur_up = up_files or []

        if paste is not None:
            pasted = paste(label="📋 Paste from clipboard", key=f"r_pp_{ver}")
            if pasted and isinstance(pasted, str) and "," in pasted:
                h = hashlib.md5(pasted.encode()).hexdigest()
                if h != S.r_last_hash:
                    S.r_last_hash = h
                    try:
                        S.r_pasted.append(base64.b64decode(pasted.split(",", 1)[1]))
                    except Exception:
                        pass
        else:
            st.caption("Paste button could not load. Use drag and drop or Browse files.")

        exist_imgs = [base64.b64decode(b) for b in S.r_exist_b64]
        new_uploaded = r_uploaded_bytes()
        pasted_imgs = list(S.r_pasted)

        if exist_imgs:
            st.caption("Saved photos")
            r_image_grid(exist_imgs, "exist")
        if pasted_imgs:
            st.caption("Pasted photos")
            r_image_grid(pasted_imgs, "paste")
        if new_uploaded:
            st.caption("Uploaded photos (use the x in the upload list above to remove)")
            r_image_grid(new_uploaded)

        n = r_total_images()
        if n > MAX_IMAGES:
            st.warning(f"Total {n} photos. Maximum is {MAX_IMAGES}, please remove {n - MAX_IMAGES}.")
        else:
            st.caption(f"Photos: {n} / {MAX_IMAGES}")

        st.text_area("Problem", key="r_problem", height=220)

        b1, b2 = st.columns(2)
        b1.button("Save", type="primary", use_container_width=True, on_click=r_save, key="r_save")
        b2.button("Remove", use_container_width=True, on_click=r_clear_form, key="r_remove")

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
                        r_image_grid(imgs)
                e_col, d_col = st.columns(2)
                e_col.button(
                    "Edit",
                    key=f"r_edit_{rec['id']}",
                    use_container_width=True,
                    on_click=r_start_edit,
                    args=(rec,),
                )
                d_col.button(
                    "Delete",
                    key=f"r_del_{rec['id']}",
                    use_container_width=True,
                    on_click=r_delete,
                    args=(rec["id"],),
                )


# =====================================================================
# 3. OLT COMMANDS
# =====================================================================
def olt_clean(text):
    """Removes anything inside () and the words Huawei / Bdcom / V.Sol."""
    text = re.sub(r"\([^)]*\)?", " ", text)
    text = re.sub(r"(?i)huawei|bdcom|v\.?\s?sol", " ", text)
    return re.sub(r"\s+", " ", text).strip()


COPY_HTML = """
<style>
  body {margin:0; font-family:"Source Sans Pro",-apple-system,"Segoe UI",Roboto,sans-serif;
        color:#1f2937; background:transparent;}
  .item {margin:0 0 12px;}
  .lbl {font-size:13px; color:#6b7280; margin:0 0 4px;}
  .box {display:flex; gap:8px; align-items:flex-start; background:#ffffff;
        border:1px solid #eef0f3; border-radius:12px; padding:10px 12px;}
  .cmd {flex:1; margin:0; font-family:ui-monospace,Consolas,"Courier New",monospace;
        font-size:13px; line-height:19px; white-space:pre-wrap; word-break:break-all;
        color:#1f2937;}
  button {flex:none; border:1px solid #e3e7ee; background:#f7f9fc; border-radius:8px;
          padding:4px 10px; font-size:12px; cursor:pointer; color:#4b5563;}
  button.ok {background:#4f7cff; border-color:#4f7cff; color:#ffffff;}
</style>
<div id="root"></div>
<script>
  const ITEMS = __ITEMS__;

  function selectText(el) {
    const r = document.createRange();
    r.selectNodeContents(el);
    const s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  function legacyCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    return ok;
  }

  async function doCopy(text, el, btn) {
    let ok = legacyCopy(text);                       // works in most embedded windows
    if (!ok) {
      try {
        if (navigator.clipboard) { await navigator.clipboard.writeText(text); ok = true; }
      } catch (e) {}
    }
    if (!ok) { selectText(el); }                     // last resort: select, then Ctrl+C
    btn.textContent = ok ? "Copied" : "Press Ctrl+C";
    btn.classList.toggle("ok", ok);
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("ok"); }, 1600);
  }

  const root = document.getElementById("root");
  ITEMS.forEach(([name, cmd]) => {
    const item = document.createElement("div");
    item.className = "item";
    const lbl = document.createElement("div");
    lbl.className = "lbl";
    lbl.textContent = name;
    const box = document.createElement("div");
    box.className = "box";
    const pre = document.createElement("pre");
    pre.className = "cmd";
    pre.textContent = cmd;
    const btn = document.createElement("button");
    btn.textContent = "Copy";
    btn.addEventListener("click", () => doCopy(cmd, pre, btn));
    box.appendChild(pre);
    box.appendChild(btn);
    item.appendChild(lbl);
    item.appendChild(box);
    root.appendChild(item);
  });
</script>
"""


def olt_show(items):
    """Command list with a Copy button that also works inside embedded windows."""
    try:
        import json
        import streamlit.components.v1 as components

        data = json.dumps(items).replace("</", "<\\/")
        height = 12
        for _, cmd in items:
            lines = sum(max(1, math.ceil(len(line) / 44)) for line in cmd.split("\n"))
            height += 17 + 4 + lines * 19 + 22 + 12
        components.html(COPY_HTML.replace("__ITEMS__", data), height=height, scrolling=False)
    except Exception:
        for name, cmd in items:
            st.markdown(f'<div class="label">{name}</div>', unsafe_allow_html=True)
            st.code(cmd, language="bash", wrap_lines=True)


S.setdefault("olt_rmac_b", "")
S.setdefault("olt_rmac_h", "")


def olt_sync(src, dst):
    """Keeps the Router MAC box in the BDCOM and HUAWEI tabs the same."""
    S[dst] = S[src]


def olt_router_mac(key, other):
    """Router MAC box (shown at the top of each tab). Returns (last4, huawei_format)."""
    raw = olt_clean(
        st.text_input(
            "Router MAC (full)",
            placeholder="14EB-B66B-6EB3",
            key=key,
            on_change=olt_sync,
            args=(key, other),
        )
    )
    digits = re.sub(r"[^0-9A-Fa-f]", "", raw).upper()
    last4 = digits[-4:] if len(digits) >= 4 else ""
    huawei_mac = "-".join(digits[i:i + 4] for i in range(0, len(digits), 4)) if digits else ""
    if last4:
        st.caption(f"Last 4 digit: {last4}")
    return last4, huawei_mac


def olt_tab():
    st.markdown("### OLT Commands")

    c1, c2 = st.columns(2)
    pon = c1.number_input("Pon", min_value=0, value=1, step=1, key="olt_pon")
    onu = c2.number_input("Onu", min_value=0, value=1, step=1, key="olt_onu")

    tab_b, tab_h = st.tabs(["BDCOM", "HUAWEI"])

    with tab_b:
        last4, _ = olt_router_mac("olt_rmac_b", "olt_rmac_h")
        b_sn = olt_clean(
            st.text_input("ONU MAC / SN", placeholder="ECOM-9D03FF9B", key="olt_b_sn")
        )
        olt_show([
            ("Find Onu (ONU MAC)", f"show gpon onu-information sn {b_sn or '<ONU MAC>'}"),
            ("Find Onu (Router MAC)", f"show mac address-table | include {last4 or '<Router MAC>'}"),
            ("Onu Info", f"show gpon interface gpon 0/{pon}:{onu} onu basic-info"),
            ("Onu Power", f"show gpon interface gpon 0/{pon}:{onu} onu optical-transceiver-diagnosis"),
            ("Onu Power check in PON", f"show gpon onu-optical-transceiver-diagnosis interface gpon 0/{pon}"),
            ("Check Port", f"show gpon interface gpon 0/{pon}:{onu} onu port 1 state"),
            ("Reboot", f"gpon reboot onu interface gpon 0/{pon}:{onu}"),
            ("Mac Address Show", f"show mac address-table interface gpon 0/{pon}:{onu}"),
            ("Total Inactive Onu in PON", f"show gpon inactive-onu interface gpon 0/{pon}"),
            ("Total Losi in PON", f"show gpon inactive-onu interface gpon 0/{pon} | include losi"),
            ("All PON Status", "show interface brief"),
            ("PON Port Open Check", f"show interface range gpon 0/{pon}"),
        ])

    with tab_h:
        _, huawei_mac = olt_router_mac("olt_rmac_h", "olt_rmac_b")
        e1, e2 = st.columns([3, 1])
        h_raw = olt_clean(e1.text_input("ONU MAC", placeholder="4577CE9A", key="olt_h_sn"))
        h_parts = [t for t in re.split(r"[:\-\s]+", h_raw) if t]
        h_sn = re.sub(r"(?i)^(hwtc|htwc)", "", h_parts[-1]).upper() if h_parts else ""
        slot = e2.number_input("Slot 0/_", min_value=0, value=1, step=1, key="olt_h_slot")

        olt_show([
            ("Find Onu (ONU MAC)", f"display ont info by-sn {h_sn or '<ONU MAC>'}"),
            ("Find Onu (Router MAC)", f"display location {huawei_mac or '<Router MAC>'}"),
            ("Onu Info", f"display ont optical-info {pon} {onu}"),
            ("Reset", f"ont reset {pon} {onu}"),
            ("Onu All Power", f"display ont optical-info history rx {pon} {onu}"),
            ("Total Inactive Onu in PON", f"display ont info summary {pon}"),
            ("Total Losi in PON", f"display ont info summary {pon} | include LOSi/LOBi"),
            ("Total Offline Onu in PON", f"display ont info summary {pon} | include offline"),
            (
                "Port Check (exit the interface first)",
                f"quit\ninterface gpon 0/{slot}\ndisplay ont port state {pon} {onu} eth-port all",
            ),
        ])


# =====================================================================
# 3b. CHECKLIST (runs in the browser, nothing is saved)
# =====================================================================
CHECK_ITEMS = [
    "Onu and Router Light",
    "Onu Status",
    "Power",
    "Router Mac",
    "Port up/down",
    "ERP Login Success or failed",
    "Mikrotic Bandwidth",
    "Mikrotic PPP",
]

CHECK_HTML = """
<style>
  * {box-sizing: border-box;}
  body {margin:0; font-family:"Source Sans Pro",-apple-system,"Segoe UI",Roboto,sans-serif;
        color:#1f2937; background:transparent;}
  .row {display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);
        gap:8px; align-items:stretch; margin:0 0 10px;}
  .head {border-radius:8px; padding:10px 12px; font-size:14px; font-weight:600;
         color:#ffffff; display:flex; align-items:center; line-height:1.2;
         word-break:break-word; min-height:42px;}
  .head.red {background:#ef4444;}
  .head.green {background:#22c55e;}
  input {width:100%; min-width:0; min-height:42px; background:#ffffff;
         border:1.5px solid #94a3b8; border-radius:8px; padding:9px 12px;
         font-size:14px; color:#1f2937; font-family:inherit; outline:none;
         box-shadow:0 1px 2px rgba(15,23,42,0.08);}
  input::placeholder {color:#94a3b8; opacity:1;}
  input:focus {border-color:#4f7cff; box-shadow:0 0 0 3px rgba(79,124,255,0.18);}
  .clear {margin-top:4px; width:100%; border:1px solid #e3e7ee; background:#ffffff;
          border-radius:8px; padding:9px; font-size:14px; color:#4b5563; cursor:pointer;}
  @media (max-width: 340px) {
    .row {grid-template-columns:minmax(0,1fr);}
  }
</style>
<div id="list"></div>
<button class="clear" id="clear">Clear all</button>
<script>
  const ITEMS = __ITEMS__;
  const list = document.getElementById("list");
  const rows = [];

  function setState(row, ok) {
    row.head.classList.toggle("green", ok);
    row.head.classList.toggle("red", !ok);
  }

  function hasText(row) { return row.input.value.trim() !== ""; }

  // Focus the next EMPTY box after position idx (wraps around). If none is left, leave the box.
  function focusNextEmpty(idx) {
    for (let k = 1; k < rows.length; k++) {
      const j = (idx + k) % rows.length;
      if (!hasText(rows[j])) { rows[j].input.focus(); return; }
    }
    rows[idx].input.blur();
  }

  ITEMS.forEach(function (name, idx) {
    const wrap = document.createElement("div");
    wrap.className = "row";

    const head = document.createElement("div");
    head.className = "head red";
    head.textContent = name;

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Write Here and Press Enter";
    input.setAttribute("aria-label", name);
    input.autocomplete = "off";

    const row = { head: head, input: input };

    // Empty box = red. Writing something and pressing Enter = green, then jump to the next empty box.
    input.addEventListener("input", function () {
      if (!hasText(row)) { setState(row, false); }
    });
    input.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || e.isComposing) { return; }
      e.preventDefault();
      if (hasText(row)) { setState(row, true); }
      focusNextEmpty(idx);
    });
    setState(row, false);               // red until you fill the box

    wrap.appendChild(head);
    wrap.appendChild(input);
    list.appendChild(wrap);
    rows.push(row);
  });

  document.getElementById("clear").addEventListener("click", function () {
    rows.forEach(function (r) { r.input.value = ""; setState(r, false); });
    if (rows.length) { rows[0].input.focus(); }
  });

  // Make the frame exactly as tall as the content (when the browser allows it).
  function fit() {
    try { window.frameElement.style.height = (document.documentElement.scrollHeight + 4) + "px"; }
    catch (e) {}
  }
  fit();
  window.addEventListener("resize", fit);
  if (window.ResizeObserver) { new ResizeObserver(fit).observe(document.body); }
</script>
"""


def checklist_tab():
    import json
    import streamlit.components.v1 as components

    st.markdown("### Checklist")
    html = CHECK_HTML.replace("__ITEMS__", json.dumps(CHECK_ITEMS).replace("</", "<\\/"))
    components.html(html, height=len(CHECK_ITEMS) * 56 + 70, scrolling=True)


# =====================================================================
# 4. CUSTOMER INFO (Supabase, table: customers)
# =====================================================================
CU_TABLE = "customers"
# (label, session/widget key, database column)
CU_FIELDS = [
    ("Name", "cu_name", "name"),
    ("Contact", "cu_contact", "contact"),
    ("Building Name", "cu_building", "building"),
    ("Building Number", "cu_building_no", "building_no"),
    ("Floor", "cu_floor", "floor"),
    ("Road Name", "cu_road_name", "road_name"),
    ("Road Number", "cu_road_no", "road_no"),
    ("Block/Sector", "cu_block", "block"),
    ("Area", "cu_area", "area"),
    ("Details Billing Info", "cu_billing", "billing"),
]
CU_COLUMNS = "id," + ",".join(col for _, _, col in CU_FIELDS)

for _label, _key, _col in CU_FIELDS:
    S.setdefault(_key, "")
S.setdefault("cu_editing_id", None)


@st.cache_data(show_spinner=False, ttl=15)
def cu_fetch():
    # Customers marked as deleted stay in the database but are hidden here.
    params = {
        "select": CU_COLUMNS,
        "order": "id.desc",
        "or": "(deleted.eq.false,deleted.is.null)",
    }
    return api("GET", params=params, table=CU_TABLE).json()


def cu_clear():
    for _, key, _ in CU_FIELDS:
        S[key] = ""
    S.cu_editing_id = None


def cu_save():
    values = {col: S[key].strip() for _, key, col in CU_FIELDS}
    if not any(values.values()):
        S.cu_flash = ("warning", "Please fill in something before saving.")
        return
    try:
        if S.cu_editing_id:
            api("PATCH", params={"id": f"eq.{S.cu_editing_id}"}, json=values, table=CU_TABLE)
            msg = "Updated."
        else:
            api("POST", json=values, table=CU_TABLE)
            msg = "Saved."
    except Exception as e:
        S.cu_flash = ("error", f"Could not save: {e}")
        return
    cu_fetch.clear()
    cu_clear()
    S.cu_flash = ("success", msg)


def cu_start_edit(rec):
    cu_clear()
    for _, key, col in CU_FIELDS:
        S[key] = rec.get(col) or ""
    S.cu_editing_id = rec["id"]


def cu_delete(rid):
    """Soft delete: hide from the app, but keep the row in the database."""
    try:
        api(
            "PATCH",
            params={"id": f"eq.{rid}"},
            json={
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
            table=CU_TABLE,
        )
    except Exception as e:
        S.cu_flash = ("error", f"Could not delete: {e}")
        return
    cu_fetch.clear()
    if S.cu_editing_id == rid:
        cu_clear()
    S.cu_flash = ("success", "Deleted from the app. A copy is kept in the database.")


def cu_file_text(rec):
    lines = [f"{label} : {rec.get(col) or ''}" for label, _, col in CU_FIELDS]
    return "\n".join(lines) + "\n"


def customer_tab():
    st.markdown("### Customer Info")

    if not DB_OK:
        st.error(
            "Could not connect to the database. Add SUPABASE_URL and SUPABASE_KEY "
            "in the Streamlit app Settings > Secrets."
        )
        return

    flash = S.pop("cu_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    left, right = st.columns([1, 1], gap="large")

    with left:
        if S.cu_editing_id:
            st.info("Editing a customer. Press Save to update, or Remove all to cancel.")
        for label, key, _ in CU_FIELDS:
            if key in ("cu_area", "cu_billing"):
                st.text_area(label, key=key, height=130)
            else:
                st.text_input(label, key=key)

        b1, b2 = st.columns(2)
        b1.button("Save", type="primary", use_container_width=True, on_click=cu_save, key="cu_save")
        b2.button("Remove all", use_container_width=True, on_click=cu_clear, key="cu_remove")

    with right:
        st.markdown("**Saved**")
        try:
            rows = cu_fetch()
        except Exception as e:
            rows = []
            st.error(f"Could not load saved customers: {e}")

        if not rows:
            st.caption("Nothing saved yet.")

        for rec in rows:
            with st.container(border=True):
                st.markdown(f"**{rec.get('name') or '-'}**  ·  {rec.get('contact') or '-'}")
                for label, _, col in CU_FIELDS[2:]:
                    if rec.get(col):
                        st.text(f"{label}: {rec[col]}")
                safe = re.sub(r'[\\/:*?"<>|]+', "_", rec.get("name") or rec.get("contact") or "customer")
                e_col, d_col, n_col = st.columns(3)
                e_col.button(
                    "Edit",
                    key=f"cu_edit_{rec['id']}",
                    use_container_width=True,
                    on_click=cu_start_edit,
                    args=(rec,),
                )
                d_col.button(
                    "Delete",
                    key=f"cu_del_{rec['id']}",
                    use_container_width=True,
                    on_click=cu_delete,
                    args=(rec["id"],),
                )
                n_col.download_button(
                    "Notepad",
                    data=cu_file_text(rec).encode("utf-8-sig"),
                    file_name=f"{safe}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key=f"cu_dl_{rec['id']}",
                )


# =====================================================================
# 5. PAYMENT (Supabase, table: payments)
# =====================================================================
PAY_TABLE = "payments"
PAY_COLUMNS = "id,name,uid,date_time,bkash,nagad,cash_memo,trnx_id"

for _k, _v in (
    ("pay_name", ""),
    ("pay_id", ""),
    ("pay_datetime", ""),
    ("pay_bkash", ""),
    ("pay_nagad", ""),
    ("pay_cash", ""),
    ("pay_trnx", ""),
    ("pay_editing_id", None),
):
    S.setdefault(_k, _v)


@st.cache_data(show_spinner=False, ttl=15)
def pay_fetch():
    # Payments marked as deleted stay in the database but are hidden here.
    params = {
        "select": PAY_COLUMNS,
        "order": "id.desc",
        "or": "(deleted.eq.false,deleted.is.null)",
    }
    return api("GET", params=params, table=PAY_TABLE).json()


def pay_clear_form():
    S.pay_name = ""
    S.pay_id = ""
    S.pay_datetime = ""
    S.pay_bkash = ""
    S.pay_nagad = ""
    S.pay_cash = ""
    S.pay_trnx = ""
    S.pay_editing_id = None


def pay_save():
    values = {
        "name": S.pay_name.strip(),
        "uid": S.pay_id.strip(),
        "date_time": S.pay_datetime.strip(),
        "bkash": S.pay_bkash.strip(),
        "nagad": S.pay_nagad.strip(),
        "cash_memo": S.pay_cash.strip(),
        "trnx_id": S.pay_trnx.strip(),
    }
    if not any(values.values()):
        S.pay_flash = ("warning", "Please fill in something before saving.")
        return
    try:
        if S.pay_editing_id:
            api("PATCH", params={"id": f"eq.{S.pay_editing_id}"}, json=values, table=PAY_TABLE)
            msg = "Updated."
        else:
            api("POST", json=values, table=PAY_TABLE)
            msg = "Saved."
    except Exception as e:
        S.pay_flash = ("error", f"Could not save: {e}")
        return
    pay_fetch.clear()
    pay_clear_form()
    S.pay_flash = ("success", msg)


def pay_start_edit(rec):
    pay_clear_form()
    S.pay_name = rec.get("name") or ""
    S.pay_id = rec.get("uid") or ""
    S.pay_datetime = rec.get("date_time") or ""
    S.pay_bkash = rec.get("bkash") or ""
    S.pay_nagad = rec.get("nagad") or ""
    S.pay_cash = rec.get("cash_memo") or ""
    S.pay_trnx = rec.get("trnx_id") or ""
    S.pay_editing_id = rec["id"]


def pay_delete(rid):
    """Soft delete: hide from the app, but keep the row in the database."""
    try:
        api(
            "PATCH",
            params={"id": f"eq.{rid}"},
            json={
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
            table=PAY_TABLE,
        )
    except Exception as e:
        S.pay_flash = ("error", f"Could not delete: {e}")
        return
    pay_fetch.clear()
    if S.pay_editing_id == rid:
        pay_clear_form()
    S.pay_flash = ("success", "Deleted from the app. A copy is kept in the database.")


def pay_file_text(rec):
    lines = [
        f"Name : {rec.get('name') or ''}",
        f"ID : {rec.get('uid') or ''}",
        f"Date and Time : {rec.get('date_time') or ''}",
        f"Bkash : {rec.get('bkash') or ''}",
        f"Nagad : {rec.get('nagad') or ''}",
        f"Hand Cash Memo/Name : {rec.get('cash_memo') or ''}",
        f"TrnxID : {rec.get('trnx_id') or ''}",
    ]
    return "\n".join(lines) + "\n"


def payment_tab():
    st.markdown("### Payment")

    if not DB_OK:
        st.error(
            "Could not connect to the database. Add SUPABASE_URL and SUPABASE_KEY "
            "in the Streamlit app Settings > Secrets."
        )
        return

    flash = S.pop("pay_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    left, right = st.columns([1, 1], gap="large")

    with left:
        if S.pay_editing_id:
            st.info("Editing a payment. Press Save to update, or Remove all to cancel.")
        st.text_input("Name", key="pay_name")
        st.text_input("ID", key="pay_id")
        st.text_input("Date and Time", key="pay_datetime")

        p1, p2, p3 = st.columns(3)
        p1.text_input("Bkash", key="pay_bkash")
        p2.text_input("Nagad", key="pay_nagad")
        p3.text_input("Hand Cash Memo/Name", key="pay_cash")
        st.text_input("TrnxID", key="pay_trnx")

        b1, b2 = st.columns(2)
        b1.button("Save", type="primary", use_container_width=True, on_click=pay_save, key="pay_save")
        b2.button("Remove all", use_container_width=True, on_click=pay_clear_form, key="pay_remove")

    with right:
        st.markdown("**Saved**")
        try:
            rows = pay_fetch()
        except Exception as e:
            rows = []
            st.error(f"Could not load saved payments: {e}")

        if not rows:
            st.caption("Nothing saved yet.")

        for rec in rows:
            with st.container(border=True):
                st.markdown(f"**{rec.get('name') or '-'}**  ·  ID: {rec.get('uid') or '-'}")
                if rec.get("date_time"):
                    st.caption(rec["date_time"])
                for label, key in (
                    ("Bkash", "bkash"),
                    ("Nagad", "nagad"),
                    ("Hand Cash Memo/Name", "cash_memo"),
                    ("TrnxID", "trnx_id"),
                ):
                    if rec.get(key):
                        st.text(f"{label}: {rec[key]}")
                safe = re.sub(r'[\\/:*?"<>|]+', "_", rec.get("name") or rec.get("uid") or "payment")
                e_col, d_col, n_col = st.columns(3)
                e_col.button(
                    "Edit",
                    key=f"pay_edit_{rec['id']}",
                    use_container_width=True,
                    on_click=pay_start_edit,
                    args=(rec,),
                )
                d_col.button(
                    "Delete",
                    key=f"pay_del_{rec['id']}",
                    use_container_width=True,
                    on_click=pay_delete,
                    args=(rec["id"],),
                )
                n_col.download_button(
                    "Notepad",
                    data=pay_file_text(rec).encode("utf-8-sig"),
                    file_name=f"{safe}_payment.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key=f"pay_dl_{rec['id']}",
                )


# =====================================================================
# 0. NOTES (Supabase, table: notes)
# =====================================================================
NOTE_TABLE = "notes"
NOTE_COLUMNS = "id,content,created_at"

S.setdefault("nt_text", "")
S.setdefault("nt_editing_id", None)


def nt_time(iso):
    """Shows the saved time in Bangladesh time, e.g. 12 Oct 2026, 3:45 PM."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo("Asia/Dhaka"))
        except Exception:
            pass
        return f"{dt.day} {dt.strftime('%b %Y')}, {int(dt.strftime('%I'))}:{dt.strftime('%M %p')}"
    except Exception:
        return ""


@st.cache_data(show_spinner=False, ttl=15)
def nt_fetch():
    # Notes marked as deleted stay in the database but are hidden here.
    params = {
        "select": NOTE_COLUMNS,
        "order": "id.desc",
        "or": "(deleted.eq.false,deleted.is.null)",
    }
    return api("GET", params=params, table=NOTE_TABLE).json()


def nt_clear():
    S.nt_text = ""
    S.nt_editing_id = None


def nt_save():
    text = S.nt_text.strip()
    if not text:
        S.nt_flash = ("warning", "Write something before saving.")
        return
    try:
        if S.nt_editing_id:
            api("PATCH", params={"id": f"eq.{S.nt_editing_id}"}, json={"content": text}, table=NOTE_TABLE)
            msg = "Updated."
        else:
            api("POST", json={"content": text}, table=NOTE_TABLE)
            msg = "Saved."
    except Exception as e:
        S.nt_flash = ("error", f"Could not save: {e}")
        return
    nt_fetch.clear()
    nt_clear()
    S.nt_flash = ("success", msg)


def nt_start_edit(rec):
    nt_clear()
    S.nt_text = rec.get("content") or ""
    S.nt_editing_id = rec["id"]


def nt_delete(rid):
    """Soft delete: hide from the app, but keep the row in the database."""
    try:
        api(
            "PATCH",
            params={"id": f"eq.{rid}"},
            json={
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
            table=NOTE_TABLE,
        )
    except Exception as e:
        S.nt_flash = ("error", f"Could not delete: {e}")
        return
    nt_fetch.clear()
    if S.nt_editing_id == rid:
        nt_clear()
    S.nt_flash = ("success", "Deleted from the app. A copy is kept in the database.")


def notes_tab():
    st.markdown("### Notes")

    if not DB_OK:
        st.error(
            "Could not connect to the database. Add SUPABASE_URL and SUPABASE_KEY "
            "in the Streamlit app Settings > Secrets."
        )
        return

    flash = S.pop("nt_flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    left, right = st.columns([1, 1], gap="large")

    with left:
        if S.nt_editing_id:
            st.info("Editing a note. Press Save to update, or Remove all to cancel.")
        st.text_area(
            "Note",
            key="nt_text",
            height=260,
            placeholder="Write your note here. Drag the bottom-right corner of the box to make it bigger or smaller.",
        )
        b1, b2 = st.columns(2)
        b1.button("Save", type="primary", use_container_width=True, on_click=nt_save, key="nt_save")
        b2.button("Remove all", use_container_width=True, on_click=nt_clear, key="nt_remove")

    with right:
        st.markdown("**Saved**")
        try:
            rows = nt_fetch()
        except Exception as e:
            rows = []
            st.error(f"Could not load saved notes: {e}")

        if not rows:
            st.caption("Nothing saved yet.")

        for rec in rows:
            with st.container(border=True):
                when = nt_time(rec.get("created_at") or "")
                if when:
                    st.caption(when)
                st.text(rec.get("content") or "")
                e_col, d_col = st.columns(2)
                e_col.button(
                    "Edit",
                    key=f"nt_edit_{rec['id']}",
                    use_container_width=True,
                    on_click=nt_start_edit,
                    args=(rec,),
                )
                d_col.button(
                    "Delete",
                    key=f"nt_del_{rec['id']}",
                    use_container_width=True,
                    on_click=nt_delete,
                    args=(rec["id"],),
                )


# =====================================================================
# MAIN: top tabs
# =====================================================================
tab_notes, tab_billing, tab_records, tab_olt, tab_check, tab_customer, tab_payment = st.tabs(
    ["Notes", "Billing", "Records", "OLT Commands", "Checklist", "Customer Info", "Payment"]
)

with tab_notes:
    notes_tab()

with tab_billing:
    with narrow():
        billing_tab()

with tab_records:
    records_tab()

with tab_olt:
    with narrow():
        olt_tab()

with tab_check:
    with narrow():
        checklist_tab()

with tab_customer:
    customer_tab()

with tab_payment:
    payment_tab()
