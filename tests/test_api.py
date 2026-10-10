import io
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image

from faceflow.app import app

client = TestClient(app)


def make_image():
    img=Image.new('RGB',(200,200),(128,128,128))
    buf=io.BytesIO()
    img.save(buf,format='JPEG')
    return buf.getvalue()


class AppApiTests(unittest.TestCase):
    def test_home_and_status(self):
        resp=client.get('/')
        self.assertEqual(resp.status_code,200)
        self.assertIn('FaceStudio AI',resp.text)
        status=client.get('/api/status')
        self.assertEqual(status.status_code,200)
        self.assertTrue(status.json()['engine']['local_only'])
        self.assertEqual(status.headers['x-frame-options'],'DENY')

    def test_analyze_in_memory(self):
        r=client.post('/api/analyze',files={'file':('sample.jpg',make_image(),'image/jpeg')})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['face_count'],0)
        self.assertNotIn('feature',str(r.json()))

    def test_bad_upload(self):
        r=client.post('/api/analyze',files={'file':('x.txt',b'hello','text/plain')})
        self.assertEqual(r.status_code,415)
        r=client.post('/api/analyze',files={'file':('x.png',b'bad-image','image/png')})
        self.assertEqual(r.status_code,400)

    def test_cross_origin_forbidden(self):
        r=client.get('/api/status',headers={'Origin':'https://untrusted.example'})
        self.assertEqual(r.status_code,403)

    def test_enroll_needs_consent(self):
        r=client.post('/api/enroll',data={'name':'Alex','consent':'false'},files={'file':('a.jpg',make_image(),'image/jpeg')})
        self.assertEqual(r.status_code,400)

    def test_mass_delete_needs_confirmation(self):
        r=client.delete('/api/people')
        self.assertEqual(r.status_code,400)

    def test_live_flag_uses_fast_backend(self):
        blank = {'width': 200, 'height': 200, 'face_count': 0, 'faces': []}
        with patch('faceflow.app.engine.analyze', return_value=blank) as inference:
            r=client.post('/api/analyze', data={'live':'true', 'recognize':'false',
                                                'estimate_age':'false', 'estimate_appearance':'false'},
                          files={'file':('frame.jpg',make_image(),'image/jpeg')})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['face_count'],0)
            self.assertTrue(inference.call_args.kwargs['fast'])
            self.assertFalse(inference.call_args.kwargs['want_features'])

    def test_ui_starts_on_live_camera(self):
        html=client.get('/').text
        self.assertIn('id="page-live"',html)
        self.assertIn('id="cameraToggle"',html)
        self.assertIn('id="allowCamera"',html)
        self.assertIn('id="page-photo"',html)
        self.assertIn('id="page-people"',html)

if __name__=='__main__':unittest.main()
