"""Weekly timesheets on DeepOcean's official "Weekly Timesheet" form.

The blank form (templates\\TS\\DOUS Weekly Timesheet.pdf) is the official
workbook's per-person sheet -- page 1 the timesheet, page 2 the training
checklist -- saved by Excel itself so the layout is exact. Only page 1 is
filled in; page 2 goes to HR blank unless completed by hand. CELLS are that page's fill-in cells (PDF points), measured from the
same export; SIZES are the text sizes Excel draws there (the sheet prints at
93%). Everything is written centred, in Calibri, like the workbook.
"""
import datetime
import os

import pymupdf

from pdf_engine import _trim_signature

DAY_CODES = {"O": "Offshore", "T": "Travel", "S": "Shop", "M": "Other"}

OFFICIAL_POSITIONS = [
    "OCM", "NOCM", "ROV Supervisor", "ROV Senior Pilot/Technician",
    "ROV Pilot/Technician I", "ROV Pilot/Technician II",
]

ACKNOWLEDGEMENT = ("By signing below, employee acknowledges that the information reported "
                   "above for the pay period shown is true and complete days & hours "
                   "performed during this period.")

PERSONNEL_FOLDER = "1 - DOUS PERSONNEL"
CONTRACTOR_FOLDER = "2 - CONTRACTOR TIMESHEETS"

CELLS = {
    "NAME": (122.24, 85.62, 327.97, 108.06),
    "WEEK": (475.0, 85.62, 594.06, 108.06),
    "POS": (122.24, 108.06, 327.97, 130.5),
    "SUPSIG": (475.0, 108.06, 594.06, 130.5),
    "CLIENT": (13.5, 214.28, 122.24, 233.36),
    "VESSEL": (122.24, 214.28, 223.91, 233.36),
    "PROJ": (223.91, 214.28, 327.97, 233.36),
    "SYS": (327.97, 214.28, 386.77, 233.36),
    "D1": (386.77, 214.28, 416.17, 233.36),
    "D2": (416.17, 214.28, 445.6, 233.36),
    "D3": (445.6, 214.28, 475.0, 233.36),
    "D4": (475.0, 214.28, 504.4, 233.36),
    "D5": (504.4, 214.28, 533.82, 233.36),
    "D6": (533.82, 214.28, 563.22, 233.36),
    "D7": (563.22, 214.28, 594.06, 233.36),
    # rotated date headers: Operations, then Preapproved Overtime
    "DH1": (386.77, 147.32, 416.17, 214.28),
    "DH2": (416.17, 147.32, 445.6, 214.28),
    "DH3": (445.6, 147.32, 475.0, 214.28),
    "DH4": (475.0, 147.32, 504.4, 214.28),
    "DH5": (504.4, 147.32, 533.82, 214.28),
    "DH6": (533.82, 147.32, 563.22, 214.28),
    "DH7": (563.22, 147.32, 594.06, 214.28),
    "OH1": (386.77, 307.43, 416.17, 374.39),
    "OH2": (416.17, 307.43, 445.6, 374.39),
    "OH3": (445.6, 307.43, 475.0, 374.39),
    "OH4": (475.0, 307.43, 504.4, 374.39),
    "OH5": (504.4, 307.43, 533.82, 374.39),
    "OH6": (533.82, 307.43, 563.22, 374.39),
    "OH7": (563.22, 307.43, 594.06, 374.39),
    # Days: Offshore, Travel, Shop, Other, TOTAL (bold); Hours: O/T, Training, TOTAL
    "C1": (416.17, 568.6, 445.6, 585.64),
    "C2": (416.17, 585.64, 445.6, 602.92),
    "C3": (416.17, 602.92, 445.6, 620.2),
    "C4": (416.17, 620.2, 445.6, 637.48),
    "C5": (416.17, 637.48, 445.6, 654.76),
    "H1": (533.82, 568.6, 594.06, 585.64),
    "H2": (533.82, 585.64, 594.06, 602.92),
    "H3": (533.82, 602.92, 594.06, 620.2),
    "EMPSIG": (122.24, 681.64, 327.97, 701.22),
    "DATE": (475.0, 681.64, 594.06, 701.22),
}
SIZE_HEADER = 14.52        # name / week / position / date signed
SIZE_ROW = 9.96            # operations line + day codes
SIZE_TOTAL = 12.72         # day & hour totals
SIZE_DATE_HDR = 13.02      # rotated dates (14pt at 93%)

_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _font(bold=False):
    path = os.path.join(_FONTS, "calibrib.ttf" if bold else "calibri.ttf")
    return pymupdf.Font(fontfile=path) if os.path.exists(path) else pymupdf.Font("hebo" if bold else "helv")


def short_date(d):
    """Excel's US short date, as the workbook shows it: 10/4/2026."""
    return f"{d.month}/{d.day}/{d.year}"


def week_number(week_ending):
    """ISO week of the Mon-Sun week the Sunday ends (10/04/2026 -> 40)."""
    return week_ending.isocalendar()[1]


def initial_last(name):
    """'John Smith' -> 'J. Smith'."""
    parts = name.split()
    if len(parts) < 2:
        return name.strip()
    return f"{parts[0][0].upper()}. {parts[-1]}"


def file_name(name, week_ending):
    """DOUS-TS-WK40-J. Smith-10042026.pdf"""
    return f"DOUS-TS-WK{week_number(week_ending):02d}-{initial_last(name)}-{week_ending:%m%d%Y}.pdf"


def output_dir(ts_folder, name, contractor, week_ending):
    """<7 - TIMESHEETS & MILEAGE REPORT>\\1 - DOUS PERSONNEL\\John Smith\\2026"""
    group = CONTRACTOR_FOLDER if contractor else PERSONNEL_FOLDER
    return os.path.join(ts_folder, group, name.strip(), str(week_ending.year))


def totals(codes):
    counts = {c: sum(1 for x in codes if x == c) for c in DAY_CODES}
    counts["TOTAL"] = sum(counts.values())
    return counts


def fill_timesheet(template_path, out_path, *, name, official_position, week_ending,
                   ops, codes, employee_sig=None, supervisor_sig=None):
    """Write one person's timesheet PDF.

    ops: {"client", "vessel", "project", "system"}; codes: 7 day codes
    (Mon..Sun), each "O"/"T"/"S"/"M" or "".
    """
    doc = pymupdf.open(template_path)
    page = doc[0]
    regular, bold = _font(), _font(bold=True)
    writer = pymupdf.TextWriter(page.rect, color=(0, 0, 0))

    def put(key, text, size, font=regular):
        if text in (None, ""):
            return
        text = str(text)
        r = pymupdf.Rect(CELLS[key])
        width = font.text_length(text, fontsize=size)
        if width > r.width - 4:                       # shrink long text to fit
            size *= (r.width - 4) / width
            width = font.text_length(text, fontsize=size)
        baseline = (r.y0 + r.y1) / 2 + (font.ascender + font.descender) / 2 * size
        writer.append(((r.x0 + r.x1 - width) / 2, baseline), text, font=font, fontsize=size)

    put("NAME", name, SIZE_HEADER)
    put("POS", official_position, SIZE_HEADER)
    put("WEEK", short_date(week_ending), SIZE_HEADER)
    put("DATE", short_date(week_ending), SIZE_HEADER)
    put("CLIENT", ops.get("client"), SIZE_ROW)
    put("VESSEL", ops.get("vessel"), SIZE_ROW)
    put("PROJ", ops.get("project"), SIZE_ROW)
    put("SYS", ops.get("system"), SIZE_ROW)
    for i, code in enumerate(codes[:7], start=1):
        put(f"D{i}", code, SIZE_ROW)
    # The workbook hides zeros, so only non-zero totals are shown; hours
    # (overtime / training) are rarely used and left for hand entry.
    t = totals(codes)
    for key, code in (("C1", "O"), ("C2", "T"), ("C3", "S"), ("C4", "M")):
        put(key, t[code] or "", SIZE_TOTAL)
    put("C5", t["TOTAL"] or "", SIZE_TOTAL, font=bold)
    writer.write_text(page)

    # Rotated dates (reading bottom-to-top) over both day grids.
    monday = week_ending - datetime.timedelta(days=6)
    for i in range(7):
        text = short_date(monday + datetime.timedelta(days=i))
        width = regular.text_length(text, fontsize=SIZE_DATE_HDR)
        for prefix in ("DH", "OH"):
            r = pymupdf.Rect(CELLS[f"{prefix}{i + 1}"])
            x = (r.x0 + r.x1) / 2 + (regular.ascender + regular.descender) / 2 * SIZE_DATE_HDR
            y = r.y1 - (r.height - width) / 2
            tw = pymupdf.TextWriter(page.rect, color=(0, 0, 0))
            tw.append((x, y), text, font=regular, fontsize=SIZE_DATE_HDR)
            tw.write_text(page, morph=(pymupdf.Point(x, y), pymupdf.Matrix(90)))

    for key, sig in (("EMPSIG", employee_sig), ("SUPSIG", supervisor_sig)):
        if sig and os.path.exists(sig):
            r = pymupdf.Rect(CELLS[key])
            page.insert_image(pymupdf.Rect(r.x0 + 4, r.y0 + 1, r.x1 - 4, r.y1 - 1),
                              pixmap=_trim_signature(sig), keep_proportion=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.subset_fonts()
    doc.save(out_path, garbage=3, deflate=True)
    doc.close()
