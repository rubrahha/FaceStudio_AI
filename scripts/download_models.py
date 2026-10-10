"""Resumable, opt-in face model downloader; never blocks the normal launch on extras."""
from __future__ import annotations
import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MODELS=ROOT/'models'
FILES={
 'core':[
  ('face_detection_yunet_2023mar.onnx', ['https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx'],150_000),
  ('face_recognition_sface_2021dec.onnx',['https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx'],30_000_000),
 ],
 'extras':[
  ('age_deploy.prototxt',['https://raw.githubusercontent.com/eveningglow/age-and-gender-classification/master/model/deploy_age2.prototxt'],1000),
  ('age_net.caffemodel',['https://huggingface.co/AjaySharma/genderDetection/resolve/main/age_net.caffemodel','https://raw.githubusercontent.com/eveningglow/age-and-gender-classification/master/model/age_net.caffemodel'],30_000_000),
  ('gender_deploy.prototxt',['https://raw.githubusercontent.com/eveningglow/age-and-gender-classification/master/model/deploy_gender2.prototxt'],1000),
  ('gender_net.caffemodel',['https://raw.githubusercontent.com/eveningglow/age-and-gender-classification/master/model/gender_net.caffemodel'],30_000_000),
 ]
}
CORE_SHA256={
 'face_detection_yunet_2023mar.onnx':'8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
 'face_recognition_sface_2021dec.onnx':'0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79',
}
# Published model SHA; validates third-party mirrored age weights where available.
EXTRA_SHA256={'age_net.caffemodel':'6dde5d07df5ca1d66ff39e525693f05ccfb9d2c437e188fdd1a10d42e57fabd6'}
SHA256={**CORE_SHA256, **EXTRA_SHA256}

def checksum(file):
 h=hashlib.sha256()
 with open(file,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()

def download(filename, urls, minimum):
 MODELS.mkdir(exist_ok=True,parents=True)
 dest=MODELS/filename
 expected=SHA256.get(filename)
 if dest.exists() and dest.stat().st_size>minimum and (not expected or checksum(dest)==expected):
  print(f'  CACHED {filename} — already installed',flush=True)
  return True
 if dest.exists():
  print(f'  WARNING {filename} is incomplete/corrupt; keeping a backup.',flush=True)
  dest.rename(dest.with_suffix(dest.suffix+'.invalid'))
 part=dest.with_suffix(dest.suffix+'.part')
 for url in urls:
  for attempt in range(2):
   existing=part.stat().st_size if part.exists() else 0
   try:
    print(f'  GET {filename} — {existing /1048576:.1f} MB already cached',flush=True)
    headers={'User-Agent':'FaceStudioAI/3.0'}
    if existing: headers['Range']=f'bytes={existing}-'
    req=urllib.request.Request(url,headers=headers)
    # Short connection timeout. Read progress is visible; Ctrl+C preserves the .part file.
    with urllib.request.urlopen(req,timeout=22) as response:
     if response.geturl().split(':',1)[0]!='https': raise ValueError('Unsafe redirect')
     status=response.status
     if status==416:
      part.unlink(missing_ok=True)
      continue
     resume=bool(existing and status==206)
     if existing and status!=206:
      print('  Server does not support resume; restarting this file.',flush=True)
     downloaded=existing if resume else 0
     size=int(response.headers.get('Content-Length') or 0)+(existing if resume else 0)
     last=time.monotonic()
     with part.open('ab' if resume else 'wb') as target:
      while True:
       block=response.read(256*1024)
       if not block: break
       target.write(block)
       downloaded+=len(block)
       now=time.monotonic()
       if now-last>=1.5:
        msg=f'  ... {downloaded /1048576:.1f}'
        msg+=f' / {size/1048576:.1f} MB' if size else ' MB'
        print(msg,flush=True)
        last=now
    if part.stat().st_size<minimum: raise ValueError('Downloaded model is too small')
    if expected and checksum(part)!=expected:
     # A fully downloaded but mismatching model must not be resumed forever.
     part.unlink(missing_ok=True)
     raise ValueError('SHA256 mismatch. File discarded.')
    part.replace(dest)
    print(f'  READY {filename} ({dest.stat().st_size/1048576:.1f} MB)',flush=True)
    return True
   except (urllib.error.URLError,TimeoutError,ValueError,OSError) as exc:
    print(f'  Retry {attempt+1}/2: {str(exc)[:140]}',flush=True)
    # Preserve partial data for an interrupted download or next manual retry.
 print(f'  UNAVAILABLE {filename} — optional features can be used later',flush=True)
 return False

def main():
 parser=argparse.ArgumentParser()
 choice=parser.add_mutually_exclusive_group(required=True)
 choice.add_argument('--core',action='store_true')
 choice.add_argument('--extras',action='store_true')
 choice.add_argument('--age',action='store_true')
 choice.add_argument('--all',action='store_true')
 args=parser.parse_args()
 groups=['core','extras'] if args.all else ['age'] if args.age else ['extras'] if args.extras else ['core']
 success=[]
 for group in groups:
  print(f'\n[{group.upper()}] Checking model cache...',flush=True)
  for item in (FILES['extras'][:2] if group == 'age' else FILES[group]):success.append(download(*item))
 print('\nDownload complete. Restart the FaceStudio server or click Reload models in Settings.',flush=True)
 return 0 if all(success) else 1

if __name__=='__main__':sys.exit(main())
