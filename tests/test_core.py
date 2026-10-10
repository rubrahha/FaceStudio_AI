import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np

from faceflow.engine import FaceEngine, photo_metrics
from faceflow.storage import Gallery

class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Gallery(Path(self.tmp.name) / 'test.sqlite3')
    def tearDown(self): self.tmp.cleanup()
    def feature(self, index=0):
        a = np.zeros(128, dtype=np.float32)
        a[index] = 1
        return a.tolist()
    def test_enroll_and_match(self):
        person_id = self.db.enroll('Alex',self.feature())
        self.assertTrue(person_id > 0)
        result=self.db.match(self.feature())
        self.assertEqual(result['name'],'Alex')
        self.assertEqual(result['similarity'],1)
        self.assertIsNone(self.db.match(self.feature(1)))
    def test_multiple_samples_and_delete(self):
        ident=self.db.enroll('Alex',self.feature())
        self.db.enroll('alex',self.feature(2))
        self.assertEqual(self.db.list_people()[0]['samples'],2)
        self.assertTrue(self.db.delete(ident))
        self.assertEqual(self.db.list_people(),[])
        self.assertIsNone(self.db.match(self.feature()))
    def test_invalid_names_and_features(self):
        for name in ['a','', 'x'*65,'../../wrong','abc\nnext']:
            with self.assertRaises(ValueError): self.db.enroll(name,self.feature())
        with self.assertRaises(ValueError): self.db.enroll('Valid',[1,2,3])
    def test_delete_all(self):
        self.db.enroll('Alex',self.feature())
        self.db.enroll('Sam',self.feature(1))
        self.db.delete_all()
        self.assertEqual(self.db.list_people(),[])

class FaceTests(unittest.TestCase):
    def test_metrics_bounded(self):
        img=np.ones((100,100,3),np.uint8)*120
        m=photo_metrics(img,300,300,(60,60,100,100))
        self.assertGreaterEqual(m['photo_aesthetics_score'],0)
        self.assertLessEqual(m['photo_aesthetics_score'],100)
        self.assertGreater(len(m['capture_tips']),0)
    def test_no_face_blank_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng=FaceEngine(Path(tmp))
            data=eng.analyze(np.zeros((250,250,3),dtype=np.uint8))
            self.assertEqual(data['face_count'],0)
            self.assertFalse(eng.status()['face_recognition'])
            self.assertEqual(eng.status()['face_detection'],'OpenCV basic fallback')

    def test_live_skips_eye_smile_heuristics(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng=FaceEngine(Path(tmp))
            fake_face=np.array([30,30,80,80,0.8],dtype=np.float32)
            with patch.object(eng, '_detect', return_value=[fake_face]):
                r=eng.analyze(np.ones((200,200,3),dtype=np.uint8)*140,
                              fast=True,want_features=False)
            self.assertEqual(r['face_count'],1)
            self.assertIsNone(r['faces'][0]['eyes_visible_estimate'])
            self.assertIsNone(r['faces'][0]['smile_pattern_detected'])
            self.assertIsNone(r['faces'][0]['feature'])

if __name__=='__main__': unittest.main()
