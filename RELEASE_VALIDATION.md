# Release validation — 2026-09-15

The supported paths below completed functional checks. Cache renders executed,
but user review rejected their visible output artifacts; they are not release passes. These are functional release checks, not a
claim that every prompt, duration or Mac memory size produces the same quality.

## Render matrix

Hardware: 48 GB M5 Pro, MPS. Main installation: ComfyUI `0a33ed6c` (0.34.0 plus
11 upstream commits), frontend 1.51.9, PyTorch 2.13.0.

Except where stated, the mode tests used 0.1 MP (256×416), a 3-second setting
(73 frames), seed 77001, Parasyte 1.5, 8 steps, ER-SDE/beta57, shift 12/3,
AdaLN strip. The two base-model tests used 20 steps, Euler/Simple, shift 6/3.
The source pictures were frames from the shipped T2V demo, not external client assets.

| Check | Result | Wall time |
|---|---|---:|
| Motion Context continuation | PASS | 3m 29s |
| Fresh-install Parasyte render | PASS | 2m 48s |
| ClipProj 8B encoder | PASS | 3m 00s |
| EasyCache + Parasyte | FAIL — visible artifacts | 2m 51s |
| First/last frame | PASS | 3m 41s |
| GGUF base + 1080p export + audio stem | PASS | 5m 14s |
| Image-to-video + save chain latent | PASS | 3m 48s |
| Pruned int8 base | PASS | 3m 36s |
| Spectrum + Parasyte | FAIL — visible artifacts | 1m 58s |

Every saved video and audio output passed a full ffmpeg decode. Every video had
73 frames and stereo audio, except the continuation: **51 frames**, exactly the
required **22-frame trim**, with audio/video durations within 35 ms. The extra
resize output was **1080×1920**, and the separate audio stem decoded successfully.
The chain starter saved a latent and the continuation loaded that exact clip slot.
Representative frames from image conditioning, continuation, ClipProj and the
clean installation were inspected.

The normal default T2V demo was separately tested at **0.2 MP / 5 seconds / 8 steps**
(352×608, 124 frames, 6m54s) and at 0.4 MP (480×864, 12m52s). Whisper recovered the
entire scripted line from the 0.2 MP default. See README for the timing conditions.
The shorter mode checks are not full-dialogue tests or perceptual audio scores.

## Clean installation

A separate checkout of the **v0.34.0 tag**, a new Python 3.12 venv and newly installed
requirements were used. The actual `install_node_packs.sh all` completed; the server
booted and **every execution node in the workflow resolved**. It then completed an
MPS Parasyte render. No local source patches or existing site-packages were copied.
The existing model files were shared by path to avoid downloading them twice.

Fresh environment: PyTorch **2.14.0**, installed frontend **1.51.9**. The core tag's
minimum frontend is 1.49.6. Node pack revisions from that test:

| Pack | Revision |
|---|---|
| ComfyUI-GGUF | `6ea2651` |
| ComfyUI-AppleSilicon-FP8 | `74734a1` |
| ComfyUI-Spectrum-MiniMax-H3 (tested, subsequently removed from release) | `9395bf9` (v0.2.3) |
| ComfyUI-PlagueKind-Nodes | `aaec055` |
| comfyui-obvpm | `704fe3e` |
| ComfyUI-H3-Motion-Context | `5335715` |
| ComfyUI-ClipProj | `c01ba8f` |

The optional int8 checkpoint was downloaded and its safetensors data length checked
before the successful base-path render. No partial download was used.

## Release scope

The retained modes and optional blocks passed the functional checks above.
EasyCache and Spectrum were removed after user review found visible artifacts with Parasyte. Keep the shipped
starter settings conservative. Larger resolutions, long chains, other hardware,
combined caches and arbitrary model/LoRA substitutions are outside this test matrix.
Do not combine Spectrum or EasyCache with turbo LoRAs. Successful execution and
valid media encoding did not establish acceptable visual quality. Existing default sample video and timing
claims refer to the tested 48 GB configuration.
