"""Unit test to verify backend endpoints fallback gracefully when DB is offline."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'backend') not in sys.path:
    sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient
from main import app


class TestOfflineFallbackEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.project_id = '92961605-5553-4df1-b74e-9a3bed5e14f5'

    def test_get_projects_fallback(self):
        res = self.client.get('/projects/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('projects', data)
        self.assertGreaterEqual(len(data['projects']), 1)
        self.assertEqual(data['projects'][0]['id'], self.project_id)

    def test_get_project_by_id_fallback(self):
        res = self.client.get(f'/projects/{self.project_id}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['id'], self.project_id)
        self.assertIn('name', data)

    def test_get_project_assets_fallback(self):
        res = self.client.get(f'/assets/project/{self.project_id}?page=1&limit=50')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 10)
        self.assertEqual(data['items'][0]['page_order'], 1)
        self.assertEqual(data['items'][9]['page_order'], 10)

    def test_story_analysis_fallback(self):
        res = self.client.get(f'/projects/{self.project_id}/story-analysis')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('status', data)

    def test_short_script_fallback(self):
        res = self.client.get(f'/projects/{self.project_id}/short-script')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('status', data)
        self.assertFalse(data['script_approved'])


if __name__ == '__main__':
    unittest.main()
