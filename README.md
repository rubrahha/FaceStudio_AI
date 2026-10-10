# FaceStudio AI · Live Fun Studio v4

A local-first facial effects playground for Windows: live webcam face detection, age-range estimates (optional model), 10 instant browser filters, animated face distortions, and an opt-in celebrity-lookalike gallery.

> **Status:** Local prototype. Not a production biometric-identification service. Celebrity matches are entertainment-only suggestions and may be inaccurate. Photo scores measure image quality, not attractiveness. Appearance estimates do not determine gender identity.

## Quick start · Windows 10/11

Prerequisites: Python 3.12, PowerShell, Chrome or Edge, webcam (optional for photo uploads), internet for the initial model download.

1. Download this repository (`Code > Download ZIP`) or clone it.
2. Double-click `LAUNCH.bat` (or run `powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1` and then `.\START.ps1`).
3. Open **http://127.0.0.1:8765** and click **Start Camera**, allowing camera permission.
4. If you want age estimates, use **More options → Enable age guess**. This is an optional large model download; other features work without it.

## Features

- **Live Camera:** Mirrored camera feed, face detection/landmarks and live insights; camera stops when you change tabs.
- **10 filters:** Natural, Glow, Noir, Vintage, Color Pop, Cool, Golden, Dreamy, Neon and Comic.
- **Animated face effects:** Normal, Big Eyes, Big Smile and Funhouse; crown and sunglasses overlays. These are playful real-time transformations, **not photorealistic face replacement**.
- **Age-range estimate:** Uses an optional pretrained model; otherwise correctly shows unavailable rather than inventing an age.
- **Celebrity Twin:** Opt-in import of reference portraits and local similarity comparisons; a celebrity name catalog is *not* a preinstalled trained face database. Portrait licensing for commercial reuse must be checked separately.
- **Upload Photo:** Analyze a local image; save selfies with applied effects.
- **My People:** Enroll/delete consenting users' face templates in a local SQLite database. Do not use as access-control authentication.

## How it works

Python/FastAPI runs locally on `127.0.0.1:8765`; OpenCV YuNet and SFace handle face detection and recognition. The HTML/CSS/JavaScript frontend draws filters in the browser. Initial pretrained models are downloaded to `models/` and are **not** included in the repository.

### Privacy

- No camera frames are sent to an external celebrity website; optional gallery import fetches reference portraits when you request it.
- Local SQLite databases in `data/` may contain sensitive biometric templates and are **ignored by Git**. They are not encrypted at rest. Restrict OS access and use full-disk encryption.
- Obtain informed consent from anyone you record or enroll. Avoid children without appropriate guardian consent.
- Do not publish `data/`, `models/`, `.env`, `*.sqlite3`, or local uploads. Keep the app bound to localhost unless you implement strong security.

### Commercial deployment notice

This is an educational / entertainment-oriented **local prototype**, not a production-ready commercial website. Public deployment requires authentication, encryption and retention/deletion policies for biometric data, threat modeling, abuse controls, accessibility testing, model/image license review, and legal review of applicable privacy rules. Do not claim that age, attractiveness, gender, or celebrity identity can be established accurately from a face image.

## Developer guide

- Install: `powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1`
- Launch: `powershell -ExecutionPolicy Bypass -File .\START.ps1`
- Tests: `powershell -ExecutionPolicy Bypass -File .\RUN_TESTS.ps1`
- Optional models: `DOWNLOAD_AGE.ps1` or `DOWNLOAD_EXTRAS.ps1`
- Sources and license notes: [`MODEL_SOURCES.md`](MODEL_SOURCES.md)

**Never commit local model weights, downloaded portraits, face templates, virtual environments, or personal images.**
