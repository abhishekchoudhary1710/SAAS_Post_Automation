"""Facebook Page and Instagram publishing through the Graph API, with one Page access token.

Facebook takes direct uploads (photos, multi-photo posts, Reels through the resumable
upload endpoint). Instagram wants public URLs and a two-step container -> publish flow.
"""

from __future__ import annotations

import json
import os
import pathlib
import time

import requests

GRAPH = "https://graph.facebook.com/{v}/{path}"
RUPLOAD = "https://rupload.facebook.com/video-upload/{v}/{video_id}"


class MetaError(RuntimeError):
    pass


class Meta:
    def __init__(self, page_id: str, token: str, ig_user_id: str | None = None, version: str = "v23.0"):
        self.page_id = page_id
        self.token = token
        self.ig_user_id = ig_user_id
        self.version = version
        self.last_photo_ids: list[str] = []
        self.last_video_id: str | None = None

    # -- plumbing -----------------------------------------------------------
    def _url(self, path: str) -> str:
        return GRAPH.format(v=self.version, path=path.lstrip("/"))

    @staticmethod
    def _check(response: requests.Response):
        try:
            data = response.json()
        except ValueError as exc:
            raise MetaError(f"non-JSON reply {response.status_code}: {response.text[:300]}") from exc
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            raise MetaError(f"{err.get('type', 'GraphError')} {err.get('code')}/{err.get('error_subcode')}: "
                            f"{err.get('message')} {err.get('error_user_msg') or ''}".strip())
        if response.status_code >= 400:
            raise MetaError(f"HTTP {response.status_code}: {data}")
        return data

    def get(self, path: str, **params):
        params["access_token"] = self.token
        return self._check(requests.get(self._url(path), params=params, timeout=60))

    def post(self, path: str, files=None, **params):
        params["access_token"] = self.token
        return self._check(requests.post(self._url(path), data=params, files=files, timeout=900))

    def whoami(self) -> dict:
        info = {"page": self.get("me", fields="id,name")}
        if self.ig_user_id:
            info["instagram"] = self.get(self.ig_user_id, fields="id,username")
        return info

    # -- facebook page ------------------------------------------------------
    def fb_photos(self, paths: list[str | pathlib.Path], message: str) -> str:
        paths = [str(p) for p in paths]
        if len(paths) == 1:
            with open(paths[0], "rb") as handle:
                data = self.post(f"{self.page_id}/photos", files={"source": handle}, caption=message)
            self.last_photo_ids = [data["id"]]
            return data.get("post_id") or data["id"]
        ids = []
        for path in paths:
            with open(path, "rb") as handle:
                data = self.post(f"{self.page_id}/photos", files={"source": handle}, published="false")
            ids.append(data["id"])
        self.last_photo_ids = list(ids)
        params = {"message": message}
        for i, media_id in enumerate(ids):
            params[f"attached_media[{i}]"] = json.dumps({"media_fbid": media_id})
        return self.post(f"{self.page_id}/feed", **params)["id"]

    def fb_reel(self, path: str | pathlib.Path, description: str) -> str:
        path = str(path)
        start = self.post(f"{self.page_id}/video_reels", upload_phase="start")
        video_id = start["video_id"]
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            response = requests.post(
                RUPLOAD.format(v=self.version, video_id=video_id), data=handle, timeout=900,
                headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size),
                         "Content-Type": "application/octet-stream"})
        data = self._check(response)
        if data.get("success") is False:
            raise MetaError(f"reel binary upload failed: {data}")
        self.post(f"{self.page_id}/video_reels", upload_phase="finish", video_id=video_id,
                  video_state="PUBLISHED", description=description)
        self._wait_fb_video(video_id)
        self.last_video_id = video_id
        return video_id

    def fb_video(self, path: str | pathlib.Path, description: str) -> str:
        """Plain video post, the fallback when the Reels endpoint refuses a file."""
        with open(str(path), "rb") as handle:
            video_id = self.post(f"{self.page_id}/videos", files={"source": handle}, description=description)["id"]
        self.last_video_id = video_id
        return video_id

    def photo_source(self, photo_id: str) -> str:
        """Public CDN URL of a photo already uploaded to the Page; Instagram can fetch from it."""
        images = self.get(photo_id, fields="images").get("images") or []
        if not images:
            raise MetaError(f"photo {photo_id} has no downloadable image yet")
        return images[0]["source"]

    def video_source(self, video_id: str, attempts: int = 8) -> str:
        """Public CDN URL of a video already uploaded to the Page, once processing has finished."""
        last = "no source yet"
        for _ in range(attempts):
            data = self.get(video_id, fields="source,status")
            if data.get("source"):
                return data["source"]
            last = str(data.get("status"))
            time.sleep(15)
        raise MetaError(f"video {video_id} never exposed a source URL ({last})")

    def _wait_fb_video(self, video_id: str, timeout: float = 600.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status = self.get(video_id, fields="status").get("status") or {}
            except MetaError:
                return  # status is best-effort; the publish call already succeeded
            state = str(status.get("video_status") or "").lower()
            if state in ("ready", "published"):
                return
            if state in ("error", "upload_failed", "expired"):
                raise MetaError(f"Facebook reel processing failed: {status}")
            time.sleep(10)

    # -- instagram ----------------------------------------------------------
    def _require_ig(self) -> str:
        if not self.ig_user_id:
            raise MetaError("IG_USER_ID is not set")
        return self.ig_user_id

    def _publish(self, container_id: str) -> str:
        ig = self._require_ig()
        last: Exception | None = None
        for attempt in range(4):
            try:
                return self.post(f"{ig}/media_publish", creation_id=container_id)["id"]
            except MetaError as exc:  # "media not ready" style errors clear after a short wait
                last = exc
                time.sleep(12 * (attempt + 1))
        raise MetaError(f"media_publish kept failing: {last}")

    def _wait_container(self, container_id: str, timeout: float = 600.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.get(container_id, fields="status_code,status")
            code = data.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise MetaError(f"Instagram container {container_id} {code}: {data.get('status')}")
            time.sleep(8)
        raise MetaError(f"Instagram container {container_id} did not finish within {int(timeout)}s")

    def ig_image(self, image_url: str, caption: str) -> str:
        ig = self._require_ig()
        container = self.post(f"{ig}/media", image_url=image_url, caption=caption)["id"]
        self._wait_container(container)
        return self._publish(container)

    def ig_carousel(self, image_urls: list[str], caption: str) -> str:
        ig = self._require_ig()
        children = []
        for url in image_urls[:10]:
            children.append(self.post(f"{ig}/media", image_url=url, is_carousel_item="true")["id"])
        for child in children:
            self._wait_container(child)
        container = self.post(f"{ig}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
        self._wait_container(container)
        return self._publish(container)

    def ig_reel(self, video_url: str, caption: str, cover_url: str | None = None, share_to_feed: bool = True) -> str:
        ig = self._require_ig()
        params = {"media_type": "REELS", "video_url": video_url, "caption": caption,
                  "share_to_feed": "true" if share_to_feed else "false"}
        if cover_url:
            params["cover_url"] = cover_url
        container = self.post(f"{ig}/media", **params)["id"]
        self._wait_container(container, timeout=900)
        return self._publish(container)

    def ig_permalink(self, media_id: str) -> str:
        try:
            return self.get(media_id, fields="permalink")["permalink"]
        except MetaError:
            return f"https://www.instagram.com/ (media id {media_id})"
