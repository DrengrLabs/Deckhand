# DOUS Deckhand

Local Windows app for DeepOcean US ROV crews: fills and signs the daily
TRA / TBT forms and the weekly timesheets from one hitch setup, and files
the PDFs into the project's HSE and timesheet folders.

- **Using / installing it:** see `README.txt` (that's the crew-facing guide
  shipped in every release).
- **Downloads:** the [Releases](../../releases) page. `DOUS-Deckhand.zip` is
  the full package for a new computer; installed copies update themselves
  from the latest release.

## Layout

```
INSTALL - run once.bat / UPDATE - keep existing data.bat / UNINSTALL.bat
README.txt                     crew guide
templates/TRA, TBT, TS         blank official forms (read-only)
app/                           the program (Python + Flask, runs locally)
  installers/                  one-time installers (Python, SigWeb, packages) -
                               kept out of git, included in release zips
tools/make_release.py          publishes a release
```

## Publishing an update

On the maintainer's laptop (GitHub CLI logged in, the read-only update key
in `..\update-token.txt`, one-time installers present in `app\installers`):

```
python tools\make_release.py 1.2.0 "What changed"
```

That bumps `app/VERSION`, commits and pushes, and creates the GitHub
release with the full zip, the small update package, the templates package
and a manifest of SHA-256 fingerprints. Installed copies show
"Update available" the next time they open.

## Never committed

Saved data (`app/app_data`, except the template fingerprints), the update
key, and the large installers - see `.gitignore`.
