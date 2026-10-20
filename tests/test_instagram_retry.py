"""A failed Instagram upload must retry on a fresh container, never on the broken one (15 Sep 2026)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.publish.meta import Meta
from agent.quality import file_hash


def ok_response():
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"success": True}
    return response


class InstagramRetryTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.video = self.folder / "reel.mp4"
        self.video.write_bytes(b"video" * 5000)
        self.state_path = self.folder / "instagram-upload.json"
        self.meta = Meta("page", "token", "ig-user", "v23.0")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def write_state(self, **state):
        self.state_path.write_text(json.dumps({"sha256": file_hash(self.video), **state}))

    def test_never_uploaded_container_is_replaced_not_reused(self):
        self.write_state(container="broken", uri="https://rupload.facebook.com/ig-api-upload/v23.0/broken",
                         uploaded=False)
        fresh = {"id": "fresh", "uri": "https://rupload.facebook.com/ig-api-upload/v23.0/fresh"}
        with patch.object(Meta, "get") as get, patch.object(Meta, "post", return_value=fresh) as create, \
                patch("agent.publish.meta.requests.post", return_value=ok_response()) as upload, \
                patch.object(Meta, "_wait_container"), patch.object(Meta, "_publish", return_value="media-1"):
            self.assertEqual(self.meta.ig_reel_file(self.video, "caption"), "media-1")
        get.assert_not_called()
        create.assert_called_once()
        self.assertTrue(upload.call_args[0][0].endswith("/fresh"))
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["container"], "fresh")
        self.assertEqual(state["published_id"], "media-1")

    def test_uploaded_container_resumes_without_a_second_upload(self):
        self.write_state(container="done", uri="https://rupload.facebook.com/ig-api-upload/v23.0/done",
                         uploaded=True)
        with patch.object(Meta, "get", return_value={"status_code": "FINISHED"}), \
                patch.object(Meta, "post") as create, \
                patch("agent.publish.meta.requests.post") as upload, \
                patch.object(Meta, "_wait_container"), patch.object(Meta, "_publish", return_value="media-2"):
            self.assertEqual(self.meta.ig_reel_file(self.video, "caption"), "media-2")
        create.assert_not_called()
        upload.assert_not_called()

    def test_already_published_is_returned_without_touching_meta(self):
        self.write_state(container="done", uploaded=True, published_id="media-3")
        with patch.object(Meta, "get") as get, patch.object(Meta, "post") as create:
            self.assertEqual(self.meta.ig_reel_file(self.video, "caption"), "media-3")
        get.assert_not_called()
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
