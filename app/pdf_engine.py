"""Core PDF introspection/fill engine for the TRA/TBT templates.

Reads a blank TRA template and figures out, purely from the PDF's own
field names and widget positions, which text fields are the shared
project info, which text fields + signature fields belong to each crew
row, and which belong to the approver block. No per-template config
needed -- every template uses the same "Name / Position / Signature"
row layout, so rows are matched by vertical position on the page.
"""
import os
import re
import tempfile
import pymupdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import IndirectObject, NameObject

COMMON_FIELDS = [
    "Project If Applicable",
    "Location  Worksite",
    "Sub Location  Area",
    "Approver",
    "Responsible Person",
    "Equipment",
    # TBT (DO-HSE-FRM-070) header fields. (The form's old "Project Name"
    # box is deliberately left blank -- only project numbers are used now.)
    "Offshore Manager",
]
TASK_FIELD = "Task  Activity"
TODAY_FIELD = "Today"
APPROVER_NAME_FIELD = "TRATBT Approver Name"
APPROVER_POSITION_FIELD = "TRATBT Approver Position"

NAME_ROW_RE = re.compile(r"^Name\.(\d+)\.0$")
POS_ROW_RE = re.compile(r"^Name\.(\d+)\.1$")

ROW_TOLERANCE = 12  # points of vertical slack when matching a row's signature widget


def _fq_name(annot):
    """Fully-qualified field name by walking the /Parent chain."""
    parts = []
    obj = annot
    seen = set()
    while obj is not None:
        oid = id(obj)
        if oid in seen:
            break
        seen.add(oid)
        t = obj.get("/T")
        if t is not None:
            parts.append(str(t))
        parent = obj.get("/Parent")
        obj = parent.get_object() if isinstance(parent, IndirectObject) else parent
    return ".".join(reversed(parts))


def _field_type(annot):
    obj = annot
    seen = set()
    while obj is not None:
        oid = id(obj)
        if oid in seen:
            break
        seen.add(oid)
        ft = obj.get("/FT")
        if ft is not None:
            return str(ft)
        parent = obj.get("/Parent")
        obj = parent.get_object() if isinstance(parent, IndirectObject) else parent
    return None


def _y_center(rect):
    return (float(rect[1]) + float(rect[3])) / 2.0


def introspect(path):
    """Return a structured description of a template's fillable layout."""
    reader = PdfReader(path)
    widgets = []  # (fq_name, field_type, page_index, rect)

    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for a in annots:
            ao = a.get_object()
            if ao.get("/Subtype") != "/Widget":
                continue
            fq = _fq_name(ao)
            ft = _field_type(ao)
            rect = ao.get("/Rect")
            if rect is None:
                continue
            widgets.append((fq, ft, page_index, [float(x) for x in rect]))

    by_name = {}
    for fq, ft, page_index, rect in widgets:
        by_name.setdefault(fq, []).append((ft, page_index, rect))

    # crew rows, keyed by row index
    rows = {}
    for fq, entries in by_name.items():
        m = NAME_ROW_RE.match(fq)
        if m:
            idx = int(m.group(1))
            rows.setdefault(idx, {})["name_field"] = fq
            rows[idx]["page"] = entries[0][1]
            rows[idx]["rect"] = entries[0][2]
        m = POS_ROW_RE.match(fq)
        if m:
            idx = int(m.group(1))
            rows.setdefault(idx, {})["position_field"] = fq

    sig_widgets = [
        (fq, page_index, rect)
        for fq, entries in by_name.items()
        for (ft, page_index, rect) in entries
        if ft == "/Sig"
    ]
    sig_lookup = {fq: (page_index, rect) for fq, page_index, rect in sig_widgets}

    unmatched_sigs = list(sig_widgets)

    def sig_for_name(page, name_rect, taken):
        """The signature box belonging to a name field: same page, same row,
        and the nearest one to the name's right.

        Checking horizontal position (not just the row) matters for forms
        with several name/signature pairs side-by-side on one row, like the
        3-column TBT attendee table -- otherwise every name in a row would
        compete for whichever box happens to be vertically closest.
        """
        name_x0 = min(name_rect[0], name_rect[2])
        name_x1 = max(name_rect[0], name_rect[2])
        y = _y_center(name_rect)
        best, best_key = None, None
        for fq, p, rect in unmatched_sigs:
            if fq in taken or p != page:
                continue
            dy = abs(_y_center(rect) - y)
            sig_x0 = min(rect[0], rect[2])
            if dy > ROW_TOLERANCE or sig_x0 < name_x0:
                continue
            key = (max(0.0, sig_x0 - name_x1), dy)
            if best_key is None or key < best_key:
                best, best_key = fq, key
        return best

    taken = set()
    crew_rows = []
    for idx in sorted(rows):
        row = rows[idx]
        if "name_field" not in row:
            continue
        sig = sig_for_name(row["page"], row["rect"], taken)
        if sig:
            taken.add(sig)
        sig_page, sig_rect = sig_lookup.get(sig, (None, None))
        crew_rows.append(
            {
                "index": idx,
                "name_field": row.get("name_field"),
                "position_field": row.get("position_field"),
                "sig_field": sig,
                "sig_page": sig_page,
                "sig_rect": sig_rect,
                "page": row["page"],
            }
        )

    # Approver block(s): any signature widget not claimed by a crew row.
    approver_sigs = [
        {"sig_field": fq, "sig_page": p, "sig_rect": rect}
        for fq, p, rect in sig_widgets
        if fq not in taken
    ]

    has_approver_text = APPROVER_NAME_FIELD in by_name
    has_task_field = TASK_FIELD in by_name

    return {
        "path": path,
        "common_fields": [f for f in COMMON_FIELDS if f in by_name],
        "task_field": TASK_FIELD if has_task_field else None,
        "today_field": TODAY_FIELD if TODAY_FIELD in by_name else None,
        "approver_name_field": APPROVER_NAME_FIELD if has_approver_text else None,
        "approver_position_field": APPROVER_POSITION_FIELD if APPROVER_POSITION_FIELD in by_name else None,
        "approver_sig_fields": approver_sigs,
        "crew_rows": crew_rows,
        "num_pages": len(reader.pages),
    }


_DA_FONT_RE = re.compile(r"/([^\s/]+)\s+([\d.]+)\s+Tf")
_measure_fonts = {}


def _measure_font(da_font_name):
    """A pymupdf Font approximating the field's font, for measuring width."""
    key = da_font_name.lower()
    if key not in _measure_fonts:
        font = None
        if "calibri" in key:
            fname = "calibrib.ttf" if "bold" in key else "calibri.ttf"
            path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fname)
            if os.path.exists(path):
                font = pymupdf.Font(fontfile=path)
        _measure_fonts[key] = font or pymupdf.Font("helv")
    return _measure_fonts[key]


def _shrink_to_fit(page, text_values):
    """Lower a field's font size just enough that its value fits the box.

    Without this, a long value (e.g. a long crew name in the narrow TBT
    attendee column) spills out of its box over the neighbouring cell
    once flattened. Only ever shrinks; short values keep the form's size.
    """
    from pypdf.generic import TextStringObject

    for annot_ref in page.get("/Annots") or []:
        annot = annot_ref.get_object()
        if annot.get("/Subtype") != "/Widget":
            continue
        value = text_values.get(_fq_name(annot))
        if not value or "/Rect" not in annot:
            continue
        da = annot.get("/DA")
        holder = annot
        while da is None and holder.get("/Parent") is not None:
            holder = holder["/Parent"].get_object()
            da = holder.get("/DA")
        match = _DA_FONT_RE.search(str(da or ""))
        if not match:
            continue
        font_name, size = match.group(1), float(match.group(2))
        rect = [float(v) for v in annot["/Rect"]]
        width = abs(rect[2] - rect[0]) - 7  # the fill step pads text in from the box edge
        height = abs(rect[3] - rect[1])
        size = size or min(10.0, height * 0.7)
        text_w = _measure_font(font_name).text_length(str(value), fontsize=size)
        if text_w <= width or text_w == 0:
            continue
        new_size = max(5.0, int(size * width / text_w * 10) / 10)
        new_da = str(da)[: match.start(2)] + str(new_size) + str(da)[match.end(2):]
        annot[NameObject("/DA")] = TextStringObject(new_da)


def _trim_signature(path, margin=4):
    """The signature image cropped to just its ink (plus a small margin).

    Signatures are captured in a wide box that's mostly empty space; placed
    as-is, that empty space gets scaled into the PDF's signature box too and
    the ink comes out tiny. Trimming first lets the ink fill the box.
    Ink = visibly opaque pixels (or, for an image without transparency,
    anything noticeably darker than white).
    """
    pix = pymupdf.Pixmap(path)
    if pix.n - pix.alpha < 3:                      # grey/odd colourspace -> RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    w, h, n = pix.width, pix.height, pix.n
    samples = pix.samples
    # Map each byte to 1 (ink) or 0 so ink can be located with bytes.find.
    if pix.alpha:
        is_ink = bytes(1 if v > 40 else 0 for v in range(256))
        channel = n - 1                            # alpha channel
    else:
        is_ink = bytes(1 if v < 200 else 0 for v in range(256))
        channel = 0                                # red is enough for dark ink
    top = bottom = left = right = None
    stride = w * n
    for y in range(h):
        row = samples[y * stride + channel:(y + 1) * stride:n].translate(is_ink)
        first = row.find(b"\x01")
        if first < 0:
            continue
        last = row.rfind(b"\x01")
        top = y if top is None else top
        bottom = y
        left = first if left is None else min(left, first)
        right = last if right is None else max(right, last)
    if top is None:
        return pix                                 # blank image -- nothing to trim
    clip = pymupdf.IRect(max(0, left - margin), max(0, top - margin),
                         min(w, right + 1 + margin), min(h, bottom + 1 + margin))
    out = pymupdf.Pixmap(pix.colorspace, clip, pix.alpha)
    out.clear_with(0)
    out.copy(pix, clip)
    out.set_origin(0, 0)
    return out


def fill_template(
    template_path,
    output_path,
    common_values,
    crew,
    today_str,
    task_value=None,
    approver_name=None,
    approver_position=None,
    signature_images=None,
):
    """Fill a blank TRA template for one day and write a flattened PDF.

    common_values: dict subset of COMMON_FIELDS -> text
    crew: list of {"name": str, "position": str} in display order
    today_str: date string for the Today field (e.g. "10/03/2026")
    signature_images: dict keyed by crew index (int) -> PNG path, plus
        "approver" -> a PNG path or a list of 1-2 PNG paths (e.g. a day
        supervisor and a night supervisor). Most templates have exactly
        one native approver signature box; when 2 approver images are
        supplied but only 1 native box exists, that box is split in half
        so both signatures still appear independently. Only rows/approver
        blocks with an entry get a signature stamped; everything else is
        left as a blank "sign here" box.
    """
    signature_images = signature_images or {}
    info = introspect(template_path)

    text_values = {}
    for field in info["common_fields"]:
        if field in common_values and common_values[field]:
            text_values[field] = common_values[field]
    if info["today_field"]:
        text_values[info["today_field"]] = today_str
    if info["task_field"] and task_value:
        text_values[info["task_field"]] = task_value
    if info["approver_name_field"] and approver_name:
        text_values[info["approver_name_field"]] = approver_name
    if info["approver_position_field"] and approver_position:
        text_values[info["approver_position_field"]] = approver_position

    for i, row in enumerate(info["crew_rows"]):
        if i >= len(crew):
            break
        person = crew[i]
        if row["name_field"]:
            text_values[row["name_field"]] = person.get("name", "")
        if row["position_field"]:
            text_values[row["position_field"]] = person.get("position", "")

    # Fill + flatten all text fields with pypdf.
    reader = PdfReader(template_path)
    writer = PdfWriter(clone_from=reader)

    root = writer._root_object
    names_ref = root.get("/Names")
    if names_ref is not None:
        names = names_ref.get_object()
        if "/JavaScript" in names:
            del names[NameObject("/JavaScript")]

    for page in writer.pages:
        _shrink_to_fit(page, text_values)
        writer.update_page_form_field_values(page, text_values, auto_regenerate=False, flatten=True)

    fd, intermediate_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(intermediate_path, "wb") as fh:
        writer.write(fh)

    # Stamp signature images, looked up by field name via pymupdf's own
    # widget rects (pypdf's raw /Rect uses a bottom-left origin; pymupdf's
    # widget.rect is already in its own top-left-origin space, so we read
    # the rect fresh here rather than reusing the one from introspect()).
    doc = pymupdf.open(intermediate_path)

    # Each entry is (page_index, field_name, [image_path, ...]). One image
    # fills the whole widget; more than one means that widget's box gets
    # divided evenly (left-to-right) among them.
    sig_targets = []
    for i, row in enumerate(info["crew_rows"]):
        if i < len(crew) and i in signature_images and row["sig_field"]:
            sig_targets.append((row["sig_page"], row["sig_field"], [signature_images[i]]))

    approver_images = signature_images.get("approver") or []
    if isinstance(approver_images, str):
        approver_images = [approver_images]
    approver_fields = sorted(
        info["approver_sig_fields"],
        key=lambda a: (a["sig_page"], a["sig_rect"][0] if a["sig_rect"] else 0),
    )
    if approver_images and approver_fields:
        if len(approver_images) <= len(approver_fields):
            # One image per native box (the common case: 1 image, 1 box;
            # or e.g. 2 images filling a template that already has 2 boxes).
            for field, image_path in zip(approver_fields, approver_images):
                sig_targets.append((field["sig_page"], field["sig_field"], [image_path]))
        else:
            # More approver images than native boxes (e.g. a day + night
            # supervisor on a template with only one approver signature
            # box) -- split that one box among all the images rather than
            # letting the last image silently overwrite the others.
            field = approver_fields[0]
            sig_targets.append((field["sig_page"], field["sig_field"], approver_images))

    trimmed = {}

    def signature_pixmap(path):
        if path not in trimmed:
            trimmed[path] = _trim_signature(path)
        return trimmed[path]

    by_page = {}
    for page_index, field_name, images in sig_targets:
        by_page.setdefault(page_index, []).append((field_name, images))

    for page_index, targets in by_page.items():
        page = doc[page_index]
        remaining = dict(targets)
        for widget in list(page.widgets() or []):
            if widget.field_name in remaining:
                rect = widget.rect
                images = remaining.pop(widget.field_name)
                page.delete_widget(widget)
                pad = 1
                full_width = rect.x1 - rect.x0
                slot_width = full_width / len(images)
                for slot, image_path in enumerate(images):
                    x0 = rect.x0 + slot * slot_width
                    x1 = x0 + slot_width
                    img_rect = pymupdf.Rect(x0 + pad, rect.y0 + pad, x1 - pad, rect.y1 - pad)
                    page.insert_image(img_rect, pixmap=signature_pixmap(image_path), keep_proportion=True)

    # Filled text is already burned into the page by the flatten step, but
    # pypdf leaves the field widgets sitting on top -- so the finished
    # record stayed editable in Acrobat. Remove the widgets for every field
    # we filled. Empty ones (blank attendee rows, unsigned boxes) are kept
    # on purpose so a late arrival can still be added by hand.
    filled = set(text_values)
    for page in doc:
        for widget in list(page.widgets() or []):
            if widget.field_name in filled:
                page.delete_widget(widget)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    try:
        os.remove(intermediate_path)
    except OSError:
        pass  # best-effort cleanup; Windows may briefly hold the handle
    return output_path


if __name__ == "__main__":
    import glob
    import json
    import sys

    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "TRA")
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    for p in sorted(glob.glob(folder + r"\*.pdf")):
        import os

        base = os.path.basename(p)
        if "Master" in base:
            continue
        if targets and base not in targets:
            continue
        info = introspect(p)
        print("=" * 80)
        print(base)
        print(" common:", info["common_fields"], "task:", info["task_field"], "today:", info["today_field"])
        print(" approver name/pos:", info["approver_name_field"], info["approver_position_field"])
        print(" approver sig fields:", info["approver_sig_fields"])
        print(" crew rows:")
        for r in info["crew_rows"]:
            print("   ", r)
