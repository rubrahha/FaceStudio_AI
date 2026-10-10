# Pre-trained model sources, acknowledgments, and limitations

**Model weights are deliberately not packed into this ZIP.** The download script obtains them directly on the user's computer when requested. This avoids shipping large third-party models without a full redistribution review.

### Core (recommended)

| Filename | Upstream | License described upstream |
| --- | --- | --- |
| `face_detection_yunet_2023mar.onnx` | https://huggingface.co/opencv/face_detection_yunet | OpenCV Zoo / YuNet model directory: MIT |
| `face_recognition_sface_2021dec.onnx` | https://huggingface.co/opencv/face_recognition_sface | OpenCV Zoo / SFace model directory: Apache-2.0 |

- YuNet info: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- SFace info: https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- SFace commercial/data provenance issue (as of October 2026, do not assume resolved): https://github.com/opencv/opencv_zoo/issues/313

### Optional legacy age and appearance models

| Filename | Upstream |
| --- | --- |
| `age_deploy.prototxt` | https://github.com/eveningglow/age-and-gender-classification/tree/master/model |
| `gender_deploy.prototxt` | Same |
| `age_net.caffemodel` | https://github.com/eveningglow/age-and-gender-classification/tree/master/model |
| `gender_net.caffemodel` | Same |

The legacy Caffe models are commonly associated with the Adience age/gender classification research. The attribution and **redistribution/commercial terms for weights and underlying training data are not verified here**. For deployment to users, investigate their rights and suitability or replace them with appropriately licensed and audited models.

These are **statistical predictions**, not proven individual characteristics. Age ranges are coarse; binary appearance labels are model labels, not gender identity. Calibration, fairness audits, biometric compliance and performance validation are required for any serious use.

### Initial recognition threshold

The OpenCV SFace tutorial uses an example cosine threshold of `0.363` for its demonstration. This application starts at **0.45** as a deliberately more conservative local-galler​y threshold; it is a configuration choice rather than a scientifically validated or calibrated production operating point.

See https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html

### FaceStudio 3 entertainment reference gallery

**No celebrity photographs or celebrity model weight files are included in the update.** The optional starter downloader queries the public English Wikipedia page-images API for a fixed list of names and downloads thumbnails from Wikimedia CDN after a user's explicit click. Photo creators retain their rights; file-specific licences and attribution requirements differ. The app saves only feature vectors and a link to each Wikipedia biography as a convenience source; it does **not** verify commercial photographic reproduction rights. Users are responsible for rights to images they manually provide. Do not republish imported imagery without checking the file-description page's licence.

Age model fallback mirror: `https://huggingface.co/AjaySharma/genderDetection/resolve/main/age_net.caffemodel` with a known SHA256 digest from its hosting metadata. A failed download preserves a `.part` file and can be retried; normal app startup does not trigger this download.

## v4 extension note

FaceStudio v4 adds **no new bundled weights**. The opt-in **Enable age guess**
button uses the existing fixed Caffe age model URLs defined in
`scripts/download_models.py`. It downloads the age files only, without pulling
the optional appearance model. The expanded celebrity catalog is **names only**;
user-approved portrait imports are fetched on demand from Wikipedia and
processed in memory. Browser camera looks and radial face-morph effects are
hand-written JavaScript, not neural style transfer or age progression.

**Commercial use:** The rights to each third-party model and reference portrait
must be checked independently. Wikipedia article thumbnails are not inherently
freely redistributable and can have different licensing/attribution requirements.
Do not sell or host a gallery until permissions and privacy compliance are met.
