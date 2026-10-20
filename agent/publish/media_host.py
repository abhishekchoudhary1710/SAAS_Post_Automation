"""Instagram's API fetches media from a public URL, so files need a temporary public home.

Three routes (the third lives in pipeline._instagram_urls):
  * GitHub `media` branch (default, zero signup). The run force-pushes an orphan branch
    holding only this run's files, then uses raw.githubusercontent.com URLs. The repo
    must be public for raw URLs to work; Instagram copies the file within minutes and
    the branch is rewritten on the next run, so nothing accumulates.
  * Cloudinary (set CLOUDINARY_URL) for a private repo. Free tier is more than enough.
  * Facebook's own copy: on a private repo the agent posts to Facebook first and hands
    Instagram the CDN URL of the photo or video Facebook stored.

Facebook and YouTube accept direct uploads and never touch this module.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import requests

from ..config import ROOT, env, now_ist


class MediaHostError(RuntimeError):
    pass


def host(files: list[pathlib.Path], settings) -> dict[str, str]:
    """Return {str(local path): public URL} for every file."""
    files = [pathlib.Path(f) for f in files]
    if settings.cloudinary_url:
        return _cloudinary(files, settings.cloudinary_url)
    return _github_branch(files)


_PUBLIC_CACHE: dict[str, bool] = {}


def repo_is_public(slug: str | None = None) -> bool:
    """True when raw.githubusercontent.com will serve this repo's files to anyone."""
    slug = slug or repo_slug()
    if slug in _PUBLIC_CACHE:
        return _PUBLIC_CACHE[slug]
    headers = {"Accept": "application/vnd.github+json"}
    token = env("GITHUB_TOKEN") or env("MEDIA_PUSH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(f"https://api.github.com/repos/{slug}", headers=headers, timeout=30)
        public = response.status_code == 200 and not response.json().get("private", True)
    except (requests.RequestException, ValueError):
        public = False
    _PUBLIC_CACHE[slug] = public
    return public


def strategy(settings) -> str | None:
    """Which host Instagram media will use: cloudinary, github, facebook, or None."""
    if settings.cloudinary_url:
        return "cloudinary"
    try:
        if repo_is_public():
            return "github"
    except MediaHostError:
        pass
    if settings.has_meta and "facebook" in settings.platforms:
        return "facebook"
    return None


# ----------------------------------------------------------------------------- github branch
def repo_slug() -> str:
    slug = env("GITHUB_REPOSITORY")
    if slug:
        return slug
    try:
        url = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise MediaHostError("cannot find the GitHub repo: set GITHUB_REPOSITORY or add an origin remote") from exc
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if not match:
        raise MediaHostError(f"origin is not a GitHub URL: {url}")
    return match.group(1)


def _redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


def _git(args: list[str], cwd: str, secret: str | None = None) -> None:
    proc = subprocess.run(["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise MediaHostError("git " + " ".join(_redact(a, secret) for a in args[:2]) + " failed: "
                             + _redact(proc.stderr.strip()[-800:], secret))


def _github_branch(files: list[pathlib.Path], branch: str = "media", wait: bool = True) -> dict[str, str]:
    slug = repo_slug()
    token = env("GITHUB_TOKEN") or env("MEDIA_PUSH_TOKEN")
    push_url = f"https://x-access-token:{token}@github.com/{slug}.git" if token else f"https://github.com/{slug}.git"
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    tmp = tempfile.mkdtemp(prefix="sarthi-media-")
    names: dict[str, str] = {}
    for f in files:
        digest = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
        name = f"{stamp}-{digest}{f.suffix.lower()}"
        shutil.copyfile(f, os.path.join(tmp, name))
        names[str(f)] = name
    pathlib.Path(tmp, "README.md").write_text(
        "Scratch branch. Media files waiting to be picked up by Instagram's API. "
        "Rewritten on every run; nothing here is kept.\n", encoding="utf-8")
    _git(["init", "-q"], tmp)
    _git(["checkout", "-q", "-b", branch], tmp)
    _git(["add", "-A"], tmp)
    _git(["-c", "user.name=sarthi-social-agent", "-c", "user.email=actions@users.noreply.github.com",
          "commit", "-q", "-m", f"media {stamp}"], tmp)
    _git(["push", "-q", "--force", push_url, branch], tmp, secret=token)
    shutil.rmtree(tmp, ignore_errors=True)
    urls = {local: f"https://raw.githubusercontent.com/{slug}/{branch}/{name}" for local, name in names.items()}
    if wait:
        _wait_public(list(urls.values()), slug)
    return urls


def _wait_public(urls: list[str], slug: str, timeout: float = 240.0) -> None:
    deadline = time.time() + timeout
    pending = list(urls)
    while pending and time.time() < deadline:
        still = []
        for url in pending:
            try:
                response = requests.get(url, stream=True, timeout=30)
                ok = response.status_code == 200
                response.close()
            except requests.RequestException:
                ok = False
            if not ok:
                still.append(url)
        pending = still
        if pending:
            time.sleep(8)
    if pending:
        raise MediaHostError(
            f"{len(pending)} file(s) are not reachable on raw.githubusercontent.com after {int(timeout)}s. "
            f"If the repo {slug} is private, raw URLs do not work: make it public or set CLOUDINARY_URL.")


# ----------------------------------------------------------------------------- cloudinary
def _cloudinary(files: list[pathlib.Path], cloudinary_url: str) -> dict[str, str]:
    match = re.match(r"cloudinary://([^:]+):([^@]+)@([^/]+)", cloudinary_url.strip())
    if not match:
        raise MediaHostError("CLOUDINARY_URL must look like cloudinary://API_KEY:API_SECRET@CLOUD_NAME")
    api_key, api_secret, cloud = match.groups()
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    urls: dict[str, str] = {}
    for f in files:
        resource = "video" if f.suffix.lower() in (".mp4", ".mov", ".m4v") else "image"
        timestamp = int(time.time())
        public_id = f"sarthi-social/{stamp}-{f.stem}"
        signature = hashlib.sha1(f"public_id={public_id}&timestamp={timestamp}{api_secret}".encode()).hexdigest()
        with open(f, "rb") as handle:
            response = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud}/{resource}/upload",
                data={"api_key": api_key, "timestamp": timestamp, "public_id": public_id, "signature": signature},
                files={"file": handle}, timeout=900)
        try:
            data = response.json()
        except ValueError as exc:
            raise MediaHostError(f"Cloudinary replied {response.status_code}: {response.text[:300]}") from exc
        if "secure_url" not in data:
            raise MediaHostError(f"Cloudinary upload failed: {data}")
        urls[str(f)] = data["secure_url"]
    return urls
