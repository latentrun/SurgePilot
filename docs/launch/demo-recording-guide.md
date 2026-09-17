# SurgePilot Demo Recording Guide

- Status: recording instructions only
- Target length: **60–120 seconds**
- Primary outcome: show that the AI-authorship story is backed by a working distributed system
- Current artifact state: **No demo video is included** in this repository

Do not claim that a recording exists until the owner has reviewed the exported file and the public
URL resolves anonymously.

## 1. Safe preparation

Record a real local candidate, not a designed animation or a fabricated dashboard.

1. Use a clean browser profile at 1440×900 or 1920×1080, 100% zoom, and light cursor
   highlighting. Keep the product UI in English for the English-first launch.
2. Start the complete source stack before recording:

   ```bash
   make start-full-stack
   ```

3. Create only synthetic demo data: `demo@example.invalid`, `Demo API`, a low-load Scenario, a
   Test Plan, and the bundled Demo Load Node. Follow [`../site/docs/first-run.md`](../site/docs/first-run.md).
4. Complete one authorized low-load Run against a local disposable target. Keep its real report
   ready in a separate tab. Do not point the demo at a third-party service.
5. Open these tabs in order:
   - the local production preview of the Pages build;
   - repository evidence (`AI-AUTHORSHIP.md`, an ADR, and a test file);
   - the local self-hosted SurgePilot instance;
   - the completed Run Report.
6. Turn off notifications, password-manager overlays, browser sync UI, and unrelated applications.

### Mandatory redaction review

Do not record any of the following:

- `.env`, `.env.*`, secret files, terminal history, cookies, passwords, API tokens, a Personal
  Access Token, SSH keys, or credential forms with real values;
- a personal email, account avatar, browser bookmarks, local username, home-directory path, or
  notification;
- a private IP, internal hostname, VPN details, customer URL, private repository URL, or cloud
  account identifier;
- a real target payload, request header, response body, Dependency File, MinIO object, or debug
  trace that may contain confidential data.

Use `.example.invalid` identities and local/demo addresses. Blur is a fallback, not permission to
capture a secret: if sensitive material entered a raw recording, discard that take.

## 2. 90-second storyboard

| Time | Picture | Narration or caption |
| --- | --- | --- |
| 0–8 s | Marketing hero and “100% by AI agents” headline | “Can AI agents carry a real distributed system from requirements to release?” |
| 8–20 s | Scroll from responsibility boundary to repository evidence | “The claim has a precise human/AI boundary and links to the actual PRD, decisions, contracts, and gates.” |
| 20–34 s | Scenario Designer with a prepared request flow | “SurgePilot turns API flows into reusable Scenarios.” |
| 34–48 s | Test Plan and low, clearly visible load settings | “Test Plans bind environment, load intent, and pass/fail criteria.” |
| 48–62 s | Load Nodes and the initialized Demo node | “Independent Runners execute on Load Nodes instead of inside the control plane.” |
| 62–78 s | Start the authorized Run, then use a clearly labeled cut | “The Run is snapshot-based and guarded by an explicit state machine.” |
| 78–92 s | The pre-completed real Run Report and artifacts | “The report keeps the real verdict, metrics, diagnostics, and artifacts together.” |
| 92–105 s | Repository page with Star action | “Inspect the evidence, run it yourself, and Star the repository if the experiment is useful.” |

If the live Run takes longer, cut to the previously completed real report and add a small
“earlier completed demo run” caption. Do not accelerate a status transition or present edited
numbers as live output.

## 3. Record with OBS Studio

1. Install and open **OBS Studio**.
2. Create a 1920×1080, 30 fps scene with one Window Capture source for the clean browser profile.
3. Disable desktop audio unless it is intentionally used. Use a microphone only after a short test
   confirms understandable speech without background notifications.
4. Record each storyboard segment as a separate take. Pause between actions; do not race the UI.
5. Export the OBS master as MKV to reduce corruption risk, then remux it to MP4 from
   **File → Remux Recordings**.
6. Watch the entire raw export at 1× speed and repeat the redaction checklist before editing.

Screen-recording tools built into the operating system are acceptable if they can capture only the
intended window and export a local master without uploading it to a third party.

## 4. Encode and validate with ffmpeg

Keep the raw recording outside the repository. Convert an approved input to a web-friendly MP4:

```bash
ffmpeg -i surgepilot-demo-master.mp4 \
  -vf "scale='min(1920,iw)':-2:flags=lanczos,fps=30" \
  -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart \
  surgepilot-demo.mp4
```

For a silent social cut, remove audio explicitly:

```bash
ffmpeg -i surgepilot-demo-master.mp4 -t 90 \
  -vf "scale=1280:-2:flags=lanczos,fps=30" \
  -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
  -an -movflags +faststart surgepilot-demo-social.mp4
```

Inspect duration, dimensions, codecs, and audio before upload:

```bash
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=index,codec_name,width,height,r_frame_rate \
  -of json surgepilot-demo.mp4
```

## 5. Acceptance before publication

- [ ] Duration is 60–120 seconds and the hook is visible in the first eight seconds.
- [ ] Every product state shown came from the reviewed candidate; no metric or status was invented.
- [ ] The human/AI boundary is visible or linked, not reduced to “no human participated.”
- [ ] Text remains readable on a 720p playback window and captions match the visible actions.
- [ ] No secret, Personal Access Token, email, private IP, internal host, or personal path appears.
- [ ] The final frame links to `https://github.com/latentrun/SurgePilot` without claiming a Star count.
- [ ] The owner reviewed both the master and final encode before any upload.

Only after those checks pass should the runbook record the final video URL and add it to the
README, marketing site, or launch drafts.
