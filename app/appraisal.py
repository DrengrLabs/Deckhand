"""Performance appraisals on DeepOcean's "Performance Appraisal" form (rev 1).

The blank form (templates\\EVAL\\DOUS Performance Appraisal rev 1.pdf) is the
Word form exported by Word itself, so the layout is exact: pages 1-4 are the
guidelines, scoring standard and definitions; page 5 onward is the form.
The positions below (PDF points, top-left origin) were measured from that
export's table borders. Text is written in Calibri, which every Windows PC
has (the Word form's Aptos is a cloud font that often isn't installed).
"""
import datetime
import os

import pymupdf

from pdf_engine import _trim_signature

SCORES = ["7", "6", "5", "4", "3", "2", "1", "N"]
SCORE_NAMES = {
    "7": "Outstanding", "6": "Above Expectations", "5": "Meets Expectations",
    "4": "Developing Towards Expectations", "3": "Developing", "2": "Improvement Required",
    "1": "Unacceptable", "N": "Not Observed / Not Applicable",
}
SCORE_STANDARD = {
    "7": "Demonstrates exceptional, sustained performance that clearly exceeds normal expectations. "
         "Requires no supervision, actively develops others, and is regularly sought out for guidance.",
    "6": "Demonstrates strong understanding and consistently performs above expectations. Works effectively "
         "without supervision, regularly takes initiative, supports the crew, and actively seeks improvement "
         "opportunities.",
    "5": "Demonstrates the expected knowledge, skill, and attitude for the position, safely and effectively "
         "performs required tasks without supervision, contributes positively to the crew, and consistently "
         "meets expectations.",
    "4": "Demonstrates reasonable understanding and a willingness to learn. Works safely and performs tasks "
         "effectively but may require occasional guidance or support in certain areas.",
    "3": "Demonstrates basic understanding and can perform many tasks safely with appropriate instruction and "
         "supervision. Requires regular guidance and additional experience to achieve the expected competency "
         "level.",
    "2": "Demonstrates limited engagement, initiative, or commitment to development. Requires close supervision "
         "and need significant improvement to meet expected standards.",
    "1": "Does not demonstrate the minimum knowledge, skills, attitude, or situational awareness required to "
         "perform safely and effectively. Presents a potential risk to themselves, others, or operations and "
         "requires immediate corrective action.",
    "N": "The appraiser has not directly observed the employee performing the activity, the criterion does not "
         "apply, or the appraiser lacks sufficient knowledge to provide a fair assessment.",
}
# Scores the form says must be backed by supporting examples or documents.
NEEDS_EXAMPLES = ("1", "2", "6", "7")

SECTIONS = [
    ("Section I - Health, Safety and the Environment", ["Health", "Safety", "The Environment"]),
    ("Section II - Attitude", ["Teamwork", "Initiative", "Personal Presentation", "Punctuality", "Leadership"]),
    ("Section III - Technical Skill Sets", ["Mechanical", "Hydraulic", "Electrical", "Electronic",
                                           "Computer Systems / Software", "Telemetry System",
                                           "Productivity", "Quality"]),
    ("Section IV - Operational Skills", ["HammerHead", "Pre / Post Dive Checks", "Launch & Recovery",
                                         "Navigation / Sonar Use", "ROV / TMS OPs", "Manipulator",
                                         "Logs / Overlay / Video", "Overall Piloting Skill"]),
    ("Section V - Administrative Skills", ["System Paperwork", "Inventory Control", "Shepherd",
                                           "E-tool Issues/EFRs"]),
]
OVERALL = "Overall"
SUBJECTS = [s for _, subjects in SECTIONS for s in subjects]

# Section 4 of the form ("Definitions for Appraisal Subjects").
DEFINITIONS = {
    "Health": "Maintains personal wellness and avoids occupational hazards",
    "Safety": "Complies with procedures; recognizes risk; uses stop-work authority; intervenes when unsafe "
              "acts or conditions are observed.",
    "The Environment": "Minimizes or eliminates waste and environmental harm",
    "Teamwork": "Communicates respectfully; shares information; supports crew objectives; works effectively "
                "across disciplines.",
    "Initiative": "Takes ownership of tasks and results; identifies problems before they occur; volunteers for "
                  "appropriate additional responsibilities; seeks learning opportunities.",
    "Personal Presentation": "Clean, generally tidy and exhibits good personal hygiene",
    "Punctuality": "Regularly arrives for work on time; reliable and shows a respect for others time",
    "Leadership": "Supports and develops colleagues; leads by example; maintains standards; communicates "
                  "expectations; influences others positively.",
    "Productivity": "Plans and completes work efficiently while maintaining safety, quality, and procedural "
                    "compliance.",
    "Quality": "Completes work accurately; checks results; follows requirements; addresses deficiencies "
               "promptly; takes ownership of tasks and results",
}

RECOMMENDED_ACTIONS = ["Competency assessment", "Task exposure", "Training", "Mentoring",
                       "Additional responsibility"]
CAREER_PROGRESS = [
    "Requires further development before assuming additional responsibility.",
    "Ready for increased responsibility.",
    "Growing in the current role.",
    "Ready and effective in the current role.",
    "Recommend consideration for promotion",
]

# Suggestions for the short-answer lines in section 6 (the appraiser can
# pick one, edit it, or type their own; their own can be saved to the list).
PHRASES = {
    "strengths": [
        "Safety-focused; uses stop-work authority when needed",
        "Strong fault-finding and troubleshooting",
        "Reliable, punctual and hard-working",
        "Works well with the crew and communicates clearly",
        "Good hydraulic knowledge",
        "Good electrical / electronic fault-finding",
        "Confident, smooth pilot",
        "Skilled with the manipulator",
        "Thorough pre / post dive checks; keeps the system well maintained",
        "Keeps accurate logs, overlay and paperwork",
        "Takes initiative without being asked",
        "Calm and effective under pressure",
        "Willing to learn and takes feedback well",
        "Helps train and support newer crew members",
    ],
    "development": [
        "Hydraulic fault-finding",
        "Electrical / electronic fault-finding",
        "Telemetry system knowledge",
        "Piloting in strong current or poor visibility",
        "Manipulator tasks",
        "Navigation and sonar interpretation",
        "Launch & recovery operations",
        "Logs, overlay and video",
        "Completing paperwork and EFRs on time",
        "Inventory control and spares management",
        "Planning work ahead",
        "Communicating with the client and bridge",
        "Leading the shift / supervising others",
    ],
    "action_plan": [
        "Complete the competency assessment for the current grade",
        "Shadow a senior pilot tech on system fault-finding",
        "Log more supervised flying time, including manipulator tasks",
        "Lead pre / post dive checks with senior oversight",
        "Run the system paperwork and EFRs for a rotation",
        "Lead launch & recovery under supervision",
        "Study the system drawings and manuals for the telemetry system",
        "Take ownership of inventory control for the spread",
        "Attend the next available training course",
        "Mentor a newer crew member",
        "Act up as Senior Pilot Tech for part of a rotation",
        "Act up as Supervisor for part of a rotation",
        "Continue current performance",
    ],
}
# A new appraisal starts with every subject (and Overall) at 5 - Meets
# Expectations; the appraiser changes only what's different.
STANDARD_SCORE = "5"

# Official Position (Hitch Setup) -> the form's grade, and who appraises
# each grade (section 3). OCM / NOCM are appraised outside this form.
GRADES = {
    "OCM": "OCM", "NOCM": "NOCM", "ROV Supervisor": "SUPV", "ROV Senior Pilot/Technician": "SPT",
    "ROV Pilot/Technician I": "PTI", "ROV Pilot/Technician II": "PTII",
}
FORM_GRADES = ("SUPV", "SPT", "PTI", "PTII")
APPRAISED_BY = {
    "SUPV": ("OCM", "NOCM"),
    "SPT": ("SUPV",),
    "PTI": ("SUPV", "SPT"),
    "PTII": ("SUPV", "SPT"),
}
APPRAISED_BY_TEXT = {"SUPV": "the OCM or NOCM", "SPT": "a Supervisor",
                     "PTI": "a Supervisor or Senior Pilot Tech", "PTII": "a Supervisor or Senior Pilot Tech"}
# "Leadership, for example, is not a subject that a PTII or PTI should be appraised on."
DEFAULT_NOT_APPLICABLE = {"PTI": ["Leadership"], "PTII": ["Leadership"]}

# ---- measured layout (0-based page numbers) ----
FORM_PAGE = 4
HEADER = {
    "employee_name": (108.26, 165.5, 292.37, 191.18), "employee_title": (292.85, 165.5, 472.06, 191.18),
    "appraiser_name": (108.26, 217.85, 292.37, 243.65), "appraiser_title": (292.85, 217.85, 472.06, 243.65),
    "days": (108.26, 270.29, 292.37, 296.09), "date": (292.85, 270.29, 472.06, 296.09),
    "vessel": (108.26, 322.73, 292.37, 348.53), "location": (292.85, 322.73, 472.06, 348.53),
}
SCORE_COLUMNS = {
    "7": (172.22, 214.61), "6": (215.09, 257.45), "5": (257.93, 300.41), "4": (300.89, 343.27),
    "3": (343.75, 386.23), "2": (386.71, 429.07), "1": (429.55, 472.06), "N": (472.54, 514.9),
}
SCORE_ROWS = {   # subject -> (page, y0, y1)
    "Health": (4, 416.35, 437.11), "Safety": (4, 437.59, 458.35), "The Environment": (4, 458.83, 479.71),
    "Teamwork": (4, 546.22, 566.98), "Initiative": (4, 567.46, 588.22),
    "Personal Presentation": (4, 588.7, 624.22), "Punctuality": (4, 624.7, 645.6),
    "Leadership": (4, 646.08, 666.84),
    "Mechanical": (5, 156.5, 177.26), "Hydraulic": (5, 177.74, 198.5), "Electrical": (5, 198.98, 219.89),
    "Electronic": (5, 220.37, 241.13), "Computer Systems / Software": (5, 241.61, 291.89),
    "Telemetry System": (5, 292.37, 328.01), "Productivity": (5, 328.49, 349.25),
    "Quality": (5, 349.73, 370.51),
    "HammerHead": (5, 436.99, 457.75), "Pre / Post Dive Checks": (5, 458.23, 493.87),
    "Launch & Recovery": (5, 494.35, 529.9), "Navigation / Sonar Use": (5, 530.38, 565.9),
    "ROV / TMS OPs": (5, 566.38, 587.26), "Manipulator": (5, 587.74, 608.5),
    "Logs / Overlay / Video": (5, 608.98, 644.52), "Overall Piloting Skill": (5, 645.0, 680.64),
    "System Paperwork": (6, 178.58, 214.13), "Inventory Control": (6, 214.61, 235.49),
    "Shepherd": (6, 235.97, 256.73), "E-tool Issues/EFRs": (6, 257.21, 292.73),
    "Overall": (6, 379.99, 400.87),
}
DEV_PAGE = 7
DEV_LINES = {    # text starts at x, on the line spanning y0-y1 (after the printed "1." "2." "3.")
    "strengths": [(85.08, 192.33, 205.81), (85.08, 207.72, 221.2), (85.08, 223.2, 236.68)],
    "development": [(85.08, 272.04, 285.52), (85.08, 287.52, 301.0), (85.08, 302.88, 316.36)],
    "action_plan": [(85.08, 472.46, 485.94), (85.08, 487.97, 501.45), (85.08, 503.33, 516.81)],
}
DEV_LINE_RIGHT = 540.0
CHECK_BOXES = {  # the printed "[   ]" before each option
    "actions": [(90.02, 357.92, 104.35, 372.57), (90.02, 372.56, 104.35, 387.21), (90.02, 387.2, 104.35, 401.85),
                (90.02, 401.84, 104.35, 416.49), (90.02, 416.48, 104.35, 431.13)],
    "career": [(90.02, 599.87, 104.35, 614.52), (90.02, 614.51, 104.35, 629.16), (90.02, 629.17, 104.35, 643.82),
               (90.02, 643.81, 104.35, 658.46), (90.02, 658.45, 104.35, 673.1)],
}
SIGN_PAGE = 8
COMMENT_BOXES = {"appraiser_comments": (72.5, 137.18, 539.62, 197.9),
                 "employee_comments": (72.5, 255.17, 539.62, 315.89)}
# Signature lines are printed underscores spanning x 108-494; the appraiser's
# runs y 345.7-360.3 with "Date" under it at x 360, the employee's y 419-433.6.
APPRAISER_SIG = (114.0, 321.0, 340.0, 357.0)
APPRAISER_DATE = (360.0, 336.0, 494.0, 357.0)
EMPLOYEE_SIG = (114.0, 394.5, 340.0, 430.5)

SIZE_HEADER = 11.0
SIZE_MARK = 13.0
SIZE_LINE = 11.0
SIZE_COMMENT = 10.0

_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _font(bold=False):
    path = os.path.join(_FONTS, "calibrib.ttf" if bold else "calibri.ttf")
    return pymupdf.Font(fontfile=path) if os.path.exists(path) else pymupdf.Font("hebo" if bold else "helv")


def grade_for(official_position):
    return GRADES.get((official_position or "").strip(), "")


def initials(name):
    """'John Smith' -> 'JS' (first and last name)."""
    parts = [p for p in name.replace(".", " ").split() if p]
    if not parts:
        return ""
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def file_name(employee, appraiser, date):
    """The form's naming rule: Eval_JJ_BB_28-Aug-26.pdf"""
    return f"Eval_{initials(employee)}_{initials(appraiser)}_{date.day:02d}-{_MONTHS[date.month - 1]}-{date:%y}.pdf"


def us_date(d):
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def missing_scores(scores):
    """Subjects (and Overall) without a score -- N counts as a score."""
    return [s for s in SUBJECTS + [OVERALL] if scores.get(s) not in SCORES]


def needs_examples(scores):
    return [s for s in SUBJECTS + [OVERALL] if scores.get(s) in NEEDS_EXAMPLES]


def fill_appraisal(template_path, out_path, data, appraiser_sig=None, employee_sig=None):
    """Write one appraisal PDF.

    data: employee_name, employee_title, appraiser_name, appraiser_title,
    days, date (datetime.date), vessel, location, scores {subject: "7".."1"/"N"},
    strengths/development/action_plan (3 lines each), actions [labels],
    career (one label), appraiser_comments, employee_comments.
    """
    doc = pymupdf.open(template_path)
    regular, bold = _font(), _font(bold=True)
    writers = {}

    def writer(pno):
        if pno not in writers:
            writers[pno] = pymupdf.TextWriter(doc[pno].rect, color=(0, 0, 0))
        return writers[pno]

    def centred(pno, rect, text, size, font):
        if text in (None, ""):
            return
        text = str(text)
        r = pymupdf.Rect(rect)
        width = font.text_length(text, fontsize=size)
        if width > r.width - 6:
            size *= (r.width - 6) / width
            width = font.text_length(text, fontsize=size)
        baseline = (r.y0 + r.y1) / 2 + (font.ascender + font.descender) / 2 * size
        writer(pno).append(((r.x0 + r.x1 - width) / 2, baseline), text, font=font, fontsize=size)

    def left(pno, x, y0, y1, text, size, font, right=DEV_LINE_RIGHT):
        text = (text or "").strip()
        if not text:
            return
        width = font.text_length(text, fontsize=size)
        if width > right - x:
            size *= (right - x) / width
        baseline = (y0 + y1) / 2 + (font.ascender + font.descender) / 2 * size
        writer(pno).append((x, baseline), text, font=font, fontsize=size)

    # Page 5 header
    d = data["date"]
    for key in ("employee_name", "employee_title", "appraiser_name", "appraiser_title", "vessel", "location"):
        centred(FORM_PAGE, HEADER[key], data.get(key), SIZE_HEADER, bold)
    centred(FORM_PAGE, HEADER["days"], data.get("days"), SIZE_HEADER, bold)
    centred(FORM_PAGE, HEADER["date"], us_date(d), SIZE_HEADER, bold)

    # Scores: an X in the chosen column
    for subject, score in (data.get("scores") or {}).items():
        if subject in SCORE_ROWS and score in SCORE_COLUMNS:
            pno, y0, y1 = SCORE_ROWS[subject]
            x0, x1 = SCORE_COLUMNS[score]
            centred(pno, (x0, y0, x1, y1), "X", SIZE_MARK, bold)

    # Section 6/7
    for key, slots in DEV_LINES.items():
        for (x, y0, y1), text in zip(slots, data.get(key) or []):
            left(DEV_PAGE, x, y0, y1, text, SIZE_LINE, regular)
    for label in data.get("actions") or []:
        if label in RECOMMENDED_ACTIONS:
            centred(DEV_PAGE, CHECK_BOXES["actions"][RECOMMENDED_ACTIONS.index(label)], "X", 10, bold)
    if data.get("career") in CAREER_PROGRESS:
        centred(DEV_PAGE, CHECK_BOXES["career"][CAREER_PROGRESS.index(data["career"])], "X", 10, bold)

    centred(SIGN_PAGE, APPRAISER_DATE, us_date(d), SIZE_HEADER, regular)
    for pno, w in writers.items():
        w.write_text(doc[pno])

    # Comment boxes: wrapped text, shrunk until it fits
    page = doc[SIGN_PAGE]
    fontfile = os.path.join(_FONTS, "calibri.ttf")
    for key, rect in COMMENT_BOXES.items():
        text = (data.get(key) or "").strip()
        if not text:
            continue
        r = pymupdf.Rect(rect) + (5, 4, -5, -3)
        size = SIZE_COMMENT
        while True:
            kwargs = {"fontname": "CalibriC", "fontfile": fontfile} if os.path.exists(fontfile) else {"fontname": "helv"}
            shape = page.new_shape()
            if shape.insert_textbox(r, text, fontsize=size, **kwargs) >= 0 or size <= 5:
                shape.commit()
                break
            size -= 0.5

    for rect, sig in ((APPRAISER_SIG, appraiser_sig), (EMPLOYEE_SIG, employee_sig)):
        if sig and os.path.exists(sig):
            page.insert_image(pymupdf.Rect(rect), pixmap=_trim_signature(sig), keep_proportion=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.subset_fonts()
    doc.save(out_path, garbage=3, deflate=True)
    doc.close()


def available_path(path):
    """Never overwrite a signed appraisal: add (2), (3)... if the name is taken."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


def parse_date(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()
