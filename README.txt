DOUS DECKHAND
=============

QUICK START
-------------
Installing on a new computer (once):
  1. Right-click "DOUS-Deckhand.zip" > Extract All... > change the location to
     C:\DOUS Deckhand > Extract. (Or, if you have the folder rather than the
     zip, paste the "DOUS Deckhand" folder into This PC > Windows (C:).)
     You should end up with C:\DOUS Deckhand containing INSTALL - run once.bat.
  2. Set PC Matic to ask instead of block: click the ^ arrow next to the
     clock (bottom-right), click the green SuperShield icon, then
     Protection Level > Block Notification Method > Prompt for Override.
     (The installer also walks you through this and the switch back in
     step 5, if it finds PC Matic - but do it first, or PC Matic may stop
     the installer from opening at all.)
  3. Open C:\DOUS Deckhand and double-click "INSTALL - run once.bat".
     Whenever PC Matic pops up, click ALWAYS ALLOW (not just Allow).
     Click Yes if Windows asks for permission. If the Topaz installer
     appears, click through it accepting the defaults - the pad model
     (T-LBK460, connection HSB/HSX) is set automatically afterwards.
     Wait for "Done".
  4. Open the app from the desktop icon, capture a signature and
     generate one PDF - click ALWAYS ALLOW on any PC Matic pop-ups.
  5. Set PC Matic back: SuperShield icon > Protection Level > Block
     Notification Method > Display Only.
  6. Leave C:\DOUS Deckhand where it is - the app runs from there.

Already have an earlier version on this computer? (keeps everything)
(Earlier versions were called "TRA App" / "DOUS TRA-TBT App".)
  1. Extract the new version to C:\DOUS Deckhand as in step 1 above. If
     this computer already has a C:\DOUS Deckhand, extract to a new
     folder instead (e.g. C:\DOUS Deckhand NEW) - never over the old one.
  2. Pause PC Matic as in step 2 above.
  3. Double-click "UPDATE - keep existing data.bat" in the NEW folder. It
     finds the old copy, brings over every hitch setup, crew roster,
     signature, History and timesheet record, then puts the "DOUS
     Deckhand" icon on the desktop (replacing the old one). The old
     folder is left untouched as a backup - delete it once you've
     checked the new one.
  4. Set PC Matic back as in step 5 above.
  5. On Hitch Setup, check each crew member's Official Position (used on
     timesheets) and add the Client and timesheet output folder.

Every day:
  - Double-click the "DOUS Deckhand" icon on the desktop.
    (Or use a Chrome bookmark to http://127.0.0.1:5000/)

New hitch: set it up on the Hitch Setup tab (details below).
Something wrong? See "IF SOMETHING GOES WRONG" near the bottom.

Everything below is the detailed reference.


What this is
-------------
A small local app that replaces the manual "export master data, import
into each TRA, retype the date, chase down signatures" routine. You set
up each hitch/project once, then each day pick which TRAs are needed and
get fully populated, dated, signed PDFs filed automatically.

It also makes the weekly timesheets (see WEEKLY TIMESHEETS below).

Everything runs locally on this computer. No internet connection is
needed to USE it day to day, and no data ever leaves this machine.


STEP 1 - INSTALL (ONCE PER COMPUTER)
--------------------------------------
Put the "DOUS Deckhand" folder on the C: drive so it's C:\DOUS Deckhand (This PC >
Windows (C:)). That's the recommended spot: the Desktop is OneDrive and
most other places are the NAS, which can stop it working. Other local
folders may work too -- if the installer has trouble, it will suggest
moving to C:\DOUS Deckhand. Leave it there afterward; the app runs from that
folder. Then double-click:

    INSTALL - run once.bat

PC Matic SuperShield blocks the installer and the app by default. Switch
it to "Prompt for Override" first and click ALWAYS ALLOW on every pop-up
during the install and the first use of the app, then switch it back to
"Display Only" (steps in the Quick Start above). No IT help is needed.

No internet connection is needed -- everything is bundled in
DOUS Deckhand\app\installers. It installs Python (only if the computer doesn't
already have it -- silently, for this user only, no admin needed), the
Python packages the app uses, and Topaz SigWeb, then:
  - puts a "DOUS Deckhand" icon on the desktop
  - sets the app to start silently every time the computer starts
  - opens the app

That's it -- nothing else ever needs to be run. There is NO black
command window to keep open; the app runs quietly in the background.


DAILY USE - OPENING THE APP
-----------------------------
Either of these works, any time, even right after a restart:
  - Double-click the "DOUS Deckhand" icon on the desktop. It opens in
    its own window like a normal program.
  - Or bookmark http://127.0.0.1:5000/ in Chrome and use the bookmark.

There's nothing to "turn on" or "shut down" -- just open it, use it,
and close the window when done.


REQUIREMENTS ON THE COMPUTER YOU INSTALL THIS ON
--------------------------------------------------
- 64-bit Windows 10 or 11. Python doesn't need to be installed
  beforehand -- the installer adds Python 3.13 from
  DOUS Deckhand\app\installers if no 64-bit Python 3.10+ is found. (An existing
  suitable Python is used as-is.)
- Keep the whole "DOUS Deckhand" folder together. Inside it:
    INSTALL - run once.bat, UNINSTALL.bat, README.txt
    templates\TRA and templates\TBT  - the blank TRA / TBT PDFs
    app\                             - the program, its installers and
                                       its saved data


FIRST-TIME SETUP ON A NEW HITCH
---------------------------------
1. Open the app, go to the "Hitch Setup" tab.
2. Fill in the Hitch Name (e.g. PRJ###### - Day Supervisor / Night
   Supervisor), Project # (PRJ######), Location (vessel name) and
   Equipment (e.g. HD59). Sub Location (ROV Deck),
   Approver (OCM) and Responsible Person (SHIFT SUPERVISOR) come
   pre-filled -- change them if needed. Each box shows an example in grey.
3. Crew roster: six standard rows are always there -- Day Shift
   Supervisor / SPT / Tech and Night Shift Supervisor / SPT / Tech, with
   positions pre-filled. Type in the names. Use "+ Add crew member" for
   anyone else.
   The DAY SHIFT SUPERVISOR is the TRA/TBT approver and the NIGHT SHIFT
   SUPERVISOR is the 2nd approver -- their names and positions fill the
   approval / TBT Leader block on every document automatically.
4. Set the output folder to the project's HSE folder -- use "Browse..."
   (e.g. ...\PRJ######\HSE). This is per-project, so update it at the
   start of each new hitch/project. REQUIRED: nothing is generated until
   it's set. Inside it, the app files every document automatically:
       HSE\01 SIGNED TRA's\03 March\<TRA name> 03152026.pdf
       HSE\02 SIGNED TBT's\03 March\<TBT name> 03152026.pdf
   TRAs and TBTs go in their own folder, sorted into month folders
   (01 January, 02 February ... 12 December) by the document's date.
   Any of these folders that don't exist yet are created automatically.
5. Click "Save Hitch Setup".

Re-visit this tab any time something changes (new crew member, different
project, etc.) -- it only needs to be redone when something actually
changes, not every day.


SIGNATURES
-----------
Go to the "Signatures" tab. For each person, click "Capture" and sign
once. That signature is then reused automatically on every TRA/TBT that
lists that person, every day, until someone clicks "Re-capture" or
"Clear" for them.

Topaz signature pad (T-L460-HSB-R; in SigWeb this is "T-LBK460, T-LBK463,
TF-LBK460 or TF-LBK463" with connection "HSB/HSX" -- the installer sets
this automatically, whatever was picked): when the pad is plugged in
and Topaz SigWeb is installed, the signature window shows a "Sign on
Topaz Pad" button. Click it, sign on the pad (the signature appears on
screen as you sign), then click "Save Signature". Without SigWeb or the
pad, the button doesn't appear and you can still sign with the mouse,
touchscreen or stylus.

SigWeb is installed automatically by "INSTALL - run once.bat" (from the
DOUS Deckhand\app\installers folder) -- it needs admin permission once. The
installer also writes the pad settings into C:\Windows\SigPlus.ini
(TabletType=6, TabletComPort=9, TabletModel=SigLiteLCD1X5) and fixes a
computer where SigWeb was set to a different pad; it keeps a backup as
SigPlus.ini.dous-backup. To install SigWeb by hand, run
DOUS Deckhand\app\installers\sigweb.exe and choose the model/connection above. UNINSTALL.bat does not
remove SigWeb; remove it from Windows Settings > Apps if ever needed.

NOTE: a reused signature is a visual stamp, not a fresh digital signing
event the way the old Acrobat/Topaz process was. This has been agreed as
acceptable for this workflow -- it trades a small amount of per-day
rigor for a large amount of saved time. If that ever needs to change for
a specific document, just click "Re-capture" before generating it so
that person signs fresh that day.


DAILY USE
----------
1. Go to the "Today" tab. The date defaults to today (your computer's own
   local date, not UTC). Need to prep tomorrow's paperwork late tonight?
   Just change the date field to tomorrow's date before adding TRAs/TBTs
   -- nothing else about the process changes.
2. Click "+ Add TRA" or "+ Add TBT", search/pick the one you need.
3. Check off which crew members are actually on that task, confirm the
   approver, fill in the task detail if the form asks for one. You can't
   select more crew than that document has signature rows for -- the app
   blocks it and tells you how many rows are available.
4. Anyone without a saved signature shows "No signature" with a
   "Capture" button right there -- draw it on the spot if needed.
5. Click "Generate PDF". The filled, dated, signed PDF is filed in the
   project's HSE folder (01 SIGNED TRA's or 02 SIGNED TBT's, then the
   month folder), named "<name> MMDDYYYY.pdf", and
   opens automatically in your PDF viewer so you can confirm it looks
   right. If generating fails for any reason (output folder unreachable,
   the file already open elsewhere, etc.) you'll get a clear message
   explaining why -- nothing fails silently.
6. If something new comes up later in the day (a LOTO, a Working at
   Heights task, etc.), just click "+ Add TRA"/"+ Add TBT" again --
   there's no limit to how many times you can do this per day.
7. Already-generated TRAs/TBTs for the day are listed on the Today tab,
   with "View" (opens the PDF), "Edit / Regenerate" (if something needs
   correcting) and "Remove".


WEEKLY TIMESHEETS
-------------------
The "Timesheets" tab makes each person's official DeepOcean Weekly
Timesheet as a PDF, signed, and files it automatically.

One-time setup on Hitch Setup:
  - Client (e.g. Shell) -- with the vessel (Location), Project # and
    Equipment (used as the timesheet's System, e.g. HD59) this fills the
    timesheet's Operations line. It can be changed for a particular week
    on the Timesheets tab.
  - Timesheet output folder: select the project's
    "7 - TIMESHEETS & MILEAGE REPORT" folder.
  - In the crew roster, for each person: Official Position (the title
    used on timesheets -- the short Position stays on TRAs/TBTs), Shift
    (fixed by row for the six standard rows) and Contractor (tick for
    contractors).

Each week:
  1. Timesheets tab: pick the week. It always ends on a Sunday -- picking
     any other day jumps to the Sunday that ends that week; the arrows
     move a week at a time.
  2. Check each person's days: O = Offshore, T = Travel, S = Shop,
     M = Other, blank = not working (everyone starts as all O). Changes
     save as you go. Untick anyone who shouldn't get a timesheet.
  3. Click "Generate Timesheets". For each person, a window shows their
     week and totals with the timesheet's acknowledgement wording; THAT
     PERSON reads it and clicks "I acknowledge - sign & save" (per HR, this
     confirmation is required before their signature is applied). "Skip"
     leaves them out; "Stop" ends the run.

Signatures: the employee's own signature, plus the supervisor's -- the
Day Shift Supervisor for day-shift crew, the Night Shift Supervisor for
night-shift crew. Supervisors sign their own timesheet as both.

Files are named DOUS-TS-WK40-J. Smith-10042026.pdf (week number, first
initial and last name, week-ending date) and saved as:
  7 - TIMESHEETS & MILEAGE REPORT\1 - DOUS PERSONNEL\John Smith\2026\ 
  (contractors: ...\2 - CONTRACTOR TIMESHEETS\<name>\<year>\)
Missing folders are created automatically.

Each PDF is the full official timesheet: page 1 (the timesheet) and page
2 (the training checklist). Overtime and training hours are rarely used
and are left blank to fill in by hand if needed.

A "View" button opens any timesheet already made for the week. TRAs/TBTs
on the Today tab have the same "View" button.


HISTORY
--------
The "History" tab lists every date that's had at least one TRA generated
for the currently active hitch, newest first, with a count and an
at-a-glance "All signed" / "Some unsigned" badge. Click "View" on any
date to jump to the Today tab with that date loaded -- Edit/Regenerate
and Remove both work there exactly the same as for today's date.


MULTIPLE HITCHES
------------------
The dropdown at the top of the app (next to the logo) switches between
hitch/project profiles. Each one has its own completely separate Setup,
crew roster, output folder, Today list, and History -- switching never
mixes one project's data into another's.

- "+ New Hitch" creates a new, empty profile (you'll be asked to name
  it) and switches to it immediately. You land on Hitch Setup to fill
  it in.
- The name shown in the dropdown is whatever you put in the "Hitch
  Name" field on the Hitch Setup tab -- rename it any time.
- The one thing NOT split per-hitch is the signature library (the
  Signatures tab) -- a crew member's captured signature is shared and
  reused across every hitch they appear on, by design.


TRA vs TBT TEMPLATES
----------------------
Blank TRA templates live in DOUS Deckhand\templates\TRA and blank TBT
templates in DOUS Deckhand\templates\TBT -- the folder a PDF sits in decides
whether it shows up under "+ Add TRA" or "+ Add TBT". Only PDFs directly
in each folder count; anything in a subfolder is ignored.

TBTs are built on the DeepOcean DO-HSE-FRM-070 Toolbox Talk form and
numbered to match their paired TRA where one exists (e.g. the LOTO TBT is
DOUS-TBT-027, paired with DOUS-TRA-027 LOCKOUT - TAGOUT). On a TBT the
sign-off block is the "TBT Leader" -- it uses the same approver / 2nd
approver names from Hitch Setup. TBTs share the same Hitch Setup fields
as the TRAs -- "Project #" fills the TRA's Project box and the TBT's
Project No. box, and "Approver (dept)" also fills the TBT's Offshore
Manager. The TBT's old "Project Name" box is intentionally left blank
(only project numbers are used now), and so is the Assigned Medic /
First Aider box.

Each TBT's topic content (Parts 1-9 ticks and text) is pre-printed from
the original TBT and its paired TRA. The shift time is pre-printed as
0000-2400 and the Part 11 leader confirmations are pre-ticked "Yes". Up
to 27 attendees fit per TBT.

Current TBT set:
  Paired with a TRA (same number):
    DOUS-TBT-001 Pre or Post Dive Checks      DOUS-TBT-019 Hydraulic Tooling Integration and Testing
    DOUS-TBT-003 System Maintenance           DOUS-TBT-021 Survey Equipment Testing (TRA-021 / 022)
    DOUS-TBT-006 Working at Heights           DOUS-TBT-023 Pumping Out LARS Drip Pan
    DOUS-TBT-007 Unstacking and Stacking      DOUS-TBT-025 Painting ROV Equipment
                 System (TRA-007 / 008)       DOUS-TBT-027 Lockout - Tagout
    DOUS-TBT-015 Low Voltage Troubleshooting
  General safety topics (numbered from 100):
    100 Back Safety            103 Fire Extinguishers     106 Hearing Protection
    101 Blood Borne Pathogens  104 General Housekeeping   107 Heart Attacks
    102 Eye Protection         105 Hand Washing           108 Suspension Trauma


PROTECTING THE BLANK TEMPLATES
---------------------------------
The blank templates in DOUS Deckhand\templates are marked read-only at the
Windows file level, so they can't be accidentally overwritten --
including by opening one in Acrobat and saving over it. If you ever
need to legitimately update a template (fix a typo, adjust a layout),
you'll need to clear the read-only flag first (right-click the file ->
Properties -> uncheck "Read-only") before editing it, then you can
re-enable it afterward.

As a second layer of protection, the app remembers a fingerprint of
each template's original content the first time it ever sees it. If a
template's content ever changes afterward -- read-only bypassed, or
you intentionally update it -- the app detects the mismatch and BLOCKS
generating from that template until it's sorted out, rather than
silently using the changed file. If you intentionally update a
template and see this warning, delete the matching entry in
DOUS Deckhand\app\app_data\template_baselines.json so the app accepts the new
version as the new normal.


WHERE THE DATA LIVES
----------------------
Everything the app remembers (hitch setup, signature library, which
TRAs were generated on which day) is stored as plain files under:

    DOUS Deckhand\app\app_data\

Don't delete that folder unless you intend to wipe the app's memory.
It's safe to back it up (e.g. copy the whole "DOUS Deckhand" folder) if you
want a snapshot before starting a new hitch.


UPDATES
--------
The app checks for a newer version each time it opens (when the
computer has internet). If there is one, a bar appears at the top:
"Update available ... Install update". Click it, read what's new, and
click "Install now" -- it downloads, checks the files and restarts
itself in about 10 seconds. Hitches, crew, signatures, History and
timesheets are always kept. Offline? Nothing happens; it simply checks
again next time.

If PC Matic pops up after an update, click ALWAYS ALLOW.


IF SOMETHING GOES WRONG
--------------------------
- The app won't open: double-click run.bat (in DOUS Deckhand\app). It
  starts the app with a visible black window that shows any error
  message -- most commonly Python isn't installed/on PATH, or something
  else is already using port 5000. The app also keeps a log at
  DOUS Deckhand\app\app_data\app.log.
- "Windows cannot access the specified device, path, or file" when
  double-clicking the installer or the app: PC Matic SuperShield is
  blocking it. Set SuperShield to Prompt for Override (SuperShield icon >
  Protection Level > Block Notification Method), run it again and click
  ALWAYS ALLOW, then set it back to Display Only. The items PC Matic
  needs to allow are INSTALL - run
  once.bat, python.exe and pythonw.exe (in the Python install folder --
  usually %LOCALAPPDATA%\Programs\Python\Python313), and the two
  installers in DOUS Deckhand\app\installers (python-3.13.16-amd64.exe,
  sigweb.exe).
- "The package install FAILED": the installer shows Python's own error
  message and saves it to DOUS Deckhand\install_error_log.txt.
- After updating the app's files (a new version), restart the computer
  (or end "pythonw.exe" in Task Manager and open the app again) so the
  new version is the one running.
- The "Browse..." folder dialog doesn't appear: it sometimes opens
  behind the app window -- check the taskbar.
- To reset all saved data and start over: end "pythonw.exe" in Task
  Manager, delete the DOUS Deckhand\app\app_data folder, then open the app
  again.


UNINSTALLING
-------------
Double-click "UNINSTALL.bat" in the DOUS Deckhand folder. It lists exactly what
it will remove and asks you to type YES first. It then:
  - stops the app
  - removes the desktop icon and the start-with-Windows shortcut
  - removes the "DOUS Deckhand" folder, templates included

This also removes all hitch setups, crew rosters, signatures and History
stored in the app. Signed PDFs already saved to project output folders
are NOT touched. Everything goes to the Recycle Bin rather than being
permanently deleted, so it can be restored from there if needed.
