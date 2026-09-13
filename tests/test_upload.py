import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from agent.config import Settings, load_json
from agent.publish.youtube import upload_short


class UploadRecoveryTests(unittest.TestCase):
    def test_connection_loss_queries_server_and_skips_accepted_bytes(self):
        token = Mock()
        token.json.return_value = {'access_token': 'test-token'}
        start = Mock(headers={'Location': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test'})
        empty = Mock(status_code=308, headers={})
        accepted = Mock(status_code=308, headers={'Range': 'bytes=0-1048575'})
        done = Mock(status_code=200)
        done.json.return_value = {'id': 'finished'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reel.mp4'
            path.write_bytes(b'a' * (1024 * 1024) + b'last')
            with patch('requests.post', side_effect=[token, start]), patch('requests.put',
                       side_effect=[empty, requests.ConnectionError(), accepted, done]) as put, patch('time.sleep'):
                self.assertEqual(upload_short(Settings.from_env(), path, 'Title', 'Description', []), 'finished')
                self.assertEqual(put.call_args_list[-1].kwargs['data'], b'last')
                self.assertEqual(put.call_args_list[2].kwargs['headers']['Content-Range'], 'bytes */1048580')
            self.assertEqual(load_json(Path(folder) / 'youtube-upload.json')['video_id'], 'finished')
            with patch('requests.post') as post:
                self.assertEqual(upload_short(Settings.from_env(), path, 'Title', 'Description', []), 'finished')
                post.assert_not_called()
