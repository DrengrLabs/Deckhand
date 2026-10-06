"""In-app updates from the private GitHub repository's Releases.

Every release (published with tools\\make_release.py) carries:
  manifest.json            version, release notes, SHA-256 of every file
  app-update.zip           program files (small) -- everything except the
                           templates and the big one-time installers
  templates.zip            the TRA/TBT/timesheet templates (downloaded only
                           if this computer's templates differ)
  DOUS-Deckhand.zip        full package, for brand-new computers

The app reads app\\update_config.json ({"repo": ..., "token": ...}) -- the
token is a READ-ONLY key for that one repository, added to release builds
only (never committed). Saved data (app_data) is never touched; every
downloaded file is checked against the manifest before anything changes.
"""
import datetime
import hashlib
import io
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
import zipfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))            # ...\DOUS Deckhand\app
ROOT_DIR = os.path.dirname(APP_DIR)                              # ...\DOUS Deckhand
CONFIG_FILE = os.path.join(APP_DIR, "update_config.json")
API = "https://api.github.com"
# Never written by an update, whatever a package contains.
PROTECTED = ("app/app_data/", "app/update_config.json.local")
CHECK_CACHE_SECONDS = 3600

_lock = threading.Lock()
_cache = {"at": 0, "result": None}


def _config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            cfg = json.load(fh)
        if cfg.get("repo") and cfg.get("token"):
            return cfg
    except (OSError, ValueError):
        pass
    return None


def _version_tuple(v):
    parts = []
    for p in str(v).lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(url, token, accept="application/vnd.github+json", timeout=20):
    """GET from the GitHub API. Asset downloads redirect to a storage URL
    that must be fetched WITHOUT the GitHub key, so redirects are followed
    by hand."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": accept,
        "User-Agent": "DOUS-Deckhand", "X-GitHub-Api-Version": "2022-11-28"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
            plain = urllib.request.Request(e.headers["Location"], headers={"User-Agent": "DOUS-Deckhand"})
            with urllib.request.urlopen(plain, timeout=max(timeout, 300)) as resp:
                return resp.read(), dict(resp.headers)
        raise


def _asset(release, name):
    return next((a for a in release.get("assets", []) if a.get("name") == name), None)


def _download_asset(cfg, release, name):
    a = _asset(release, name)
    if not a:
        raise RuntimeError(f"The release is missing {name}.")
    data, _ = _get(f"{API}/repos/{cfg['repo']}/releases/assets/{a['id']}", cfg["token"],
                   accept="application/octet-stream", timeout=60)
    return data


def current_version():
    with open(os.path.join(APP_DIR, "VERSION"), encoding="utf-8") as fh:
        return fh.read().strip()


def check(force=False):
    """Is a newer release available? Never raises -- offline / no key / any
    problem just reports no update (with a reason for the log)."""
    with _lock:
        if not force and _cache["result"] and time.time() - _cache["at"] < CHECK_CACHE_SECONDS:
            return _cache["result"]
    cfg = _config()
    result = {"current": current_version(), "available": False}
    if not cfg:
        result["reason"] = "updates not configured"
    else:
        try:
            body, headers = _get(f"{API}/repos/{cfg['repo']}/releases/latest", cfg["token"], timeout=8)
            release = json.loads(body)
            latest = release.get("tag_name", "")
            result.update(latest=latest.lstrip("vV"), notes=release.get("body") or "",
                          published=release.get("published_at", ""))
            result["available"] = _version_tuple(latest) > _version_tuple(result["current"])
            expires = headers.get("github-authentication-token-expiration")
            if expires:
                result["key_expires"] = expires
                try:
                    exp = datetime.datetime.strptime(expires[:10], "%Y-%m-%d").date()
                    result["key_expires_soon"] = (exp - datetime.date.today()).days <= 30
                except ValueError:
                    pass
        except Exception as e:                     # offline, blocked, key revoked...
            result["reason"] = f"couldn't check: {e}"
    with _lock:
        _cache.update(at=time.time(), result=result)
    return result


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_target(rel):
    """Where a package entry goes -- refusing anything outside the app
    folder or inside saved data."""
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or rel.endswith("/") or ".." in rel.split("/") or ":" in rel:
        return None
    if any(rel.lower().startswith(p) for p in PROTECTED):
        return None
    target = os.path.normpath(os.path.join(ROOT_DIR, rel))
    if not target.startswith(os.path.normpath(ROOT_DIR) + os.sep):
        return None
    return target


def _extract_verified(zip_bytes, manifest_files, only_prefix=None):
    """Check every entry against the manifest first; only then write."""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    plan = []
    for name in z.namelist():
        if name.endswith("/"):
            continue
        rel = name.replace("\\", "/")
        if only_prefix and not rel.startswith(only_prefix):
            continue
        target = _safe_target(rel)
        if target is None:
            continue
        data = z.read(name)
        expected = manifest_files.get(rel)
        if expected is None or _sha256(data) != expected:
            raise RuntimeError(f"Update file failed its check ({rel}) - nothing was changed.")
        plan.append((rel, target, data))
    written = []
    for rel, target, data in plan:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.exists(target):
            try:
                os.chmod(target, 0o666)            # templates are read-only on purpose
            except OSError:
                pass
        tmp = target + ".updating"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
        written.append(rel)
    return written


def install():
    """Download, verify and apply the latest release. Returns a summary;
    the caller restarts the app afterwards to load the new code."""
    cfg = _config()
    if not cfg:
        raise RuntimeError("Updates aren't set up on this copy of the app.")
    body, _ = _get(f"{API}/repos/{cfg['repo']}/releases/latest", cfg["token"])
    release = json.loads(body)
    manifest = json.loads(_download_asset(cfg, release, "manifest.json"))
    files = manifest["files"]

    app_zip = _download_asset(cfg, release, "app-update.zip")
    if _sha256(app_zip) != manifest["app_zip_sha256"]:
        raise RuntimeError("The update download was damaged - nothing was changed. Try again.")

    # Templates only if any on this computer differ from the release's.
    need_templates = False
    for rel, sha in files.items():
        if rel.startswith("templates/"):
            path = os.path.join(ROOT_DIR, *rel.split("/"))
            if not os.path.exists(path) or _file_sha256(path) != sha:
                need_templates = True
                break
    tpl_zip = None
    if need_templates:
        tpl_zip = _download_asset(cfg, release, "templates.zip")
        if _sha256(tpl_zip) != manifest["templates_zip_sha256"]:
            raise RuntimeError("The templates download was damaged - nothing was changed. Try again.")

    written = _extract_verified(app_zip, files)
    changed_templates = []
    if tpl_zip:
        changed_templates = _extract_verified(tpl_zip, files, only_prefix="templates/")
        for rel in changed_templates:
            path = os.path.join(ROOT_DIR, *rel.split("/"))
            try:
                os.chmod(path, 0o444)              # back to read-only
            except OSError:
                pass
        _forget_template_fingerprints(changed_templates)

    with _lock:
        _cache.update(at=0, result=None)
    return {"version": manifest["version"], "files": len(written) + len(changed_templates),
            "templates_updated": len(changed_templates)}


def _forget_template_fingerprints(rels):
    """Updated templates are verified against the release, so drop their old
    tamper-check fingerprints; the app records the new ones on next start."""
    path = os.path.join(APP_DIR, "app_data", "template_baselines.json")
    try:
        with open(path, encoding="utf-8") as fh:
            baselines = json.load(fh)
    except (OSError, ValueError):
        return
    for rel in rels:
        parts = rel.split("/")                     # templates/TRA/x.pdf, templates/TBT/x.pdf
        if len(parts) == 3:
            key = parts[2] if parts[1] == "TRA" else f"{parts[1]}/{parts[2]}"
            baselines.pop(key, None)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(baselines, fh, indent=2)
