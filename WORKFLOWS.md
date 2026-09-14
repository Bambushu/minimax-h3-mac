# Which workflow

| file | nodes | extra packs | use it for |
|---|---|---|---|
| `MacMax_FOXYDIT_v20_AppleSilicon.json` | 80 + 12 notes | 6 packs, plus 2 optional | **current**. T2V / I2V / FFLF / R2V plus Motion Context; FL2VA + Turbo 8 + Spectrum is the viewing default |
| `MacMax_MiniMaxH3_AppleSilicon.json` | 32 + 4 notes | 3, plus 2 optional | simpler legacy T2V / I2V / FLF graph, retained for comparisons |
| `h3_mac_FOXYDIT_filmmaking.json` | 62 | 8 packs and a 2nd 21 GB DiT, plus 2 optional | legacy Foxy R2V rig, retained for comparisons only |

`./install_node_packs.sh [macmax|foxydit|v20|extras|all]` installs the packs. Run it with nothing
rendering. Both workflows need the same three: ComfyUI-GGUF, ComfyUI-AppleSilicon-FP8 and
ComfyUI-Spectrum-MiniMax-H3 (pinned v0.2.3, its node ships enabled). `ResolutionSelector` is
ComfyUI core, not a custom node.

The two optional packs, ComfyUI-H3-Motion-Context and ComfyUI-ClipProj, are covered in the
README. Every node they add ships bypassed, so neither is needed to render. Without them those
nodes show red, which is cosmetic while bypassed.

For scripted T2V/I2V/FLF runs use `render_h3.py`; `--dump-graph out.json` emits the API graph.
It works from `h3_api.json`, its own base graph, not an export of Foxy v20, so it is not the R2V
driver. Do not assume a control added to the UI workflow also exists in that script.

To rebuild and install the current R2V workflow on this Mac:

```sh
python3 build_mac_v20.py --install ~/ComfyUI-h3/user/default/workflows
```

This writes `MacMax_H3_R2V_CURRENT.json`. The source workflow remains
`minimaxH3T2VI2VREF2VAdvanced_v20.json`; change the derivation script, not the generated JSON.

## MacMax

Laid out in reading order, grouped by what you touch:

```
1 - EDIT THESE      canvas, duration, seed, steps
2 - PROMPT          the prompt and frame-count maths
3 - MODE            two collapsed LoadImage nodes
MODELS (set once)   DiT, text encoder, both VAEs
SPEED               Spectrum (on), EasyCache (off), sigma shift
SAMPLING            internals
OUTPUT              decode, mux, save
EXTRAS              audio preview, 1080p export, audio stem
CHAINING + LOW-RAM  Motion Context, ClipProj
```

Defaults: 0.6 MP at 5s, 20 steps, Spectrum ON (degree 1 / warmup 1), EasyCache present but
OFF. It also exposes `MiniMaxH3SigmaShift` (12/3), which the shipped ComfyUI template omits.

**Modes.** The two `LoadImage` nodes ship collapsed and bypassed. Leave both off for T2V,
enable the first for I2V, enable both for FLF. `MiniMaxH3ImageToVideo` already takes optional
`first_frame` and `last_frame`, so no switches or extra packs are needed.

MacMax does not do R2V. Carrying identity from reference stills needs
`MiniMaxH3ReferenceToVideo`; use the Foxydit port.

**Extras**, all ComfyUI core:

- `PreviewAudio`, active. H3's headline feature is the audio, so hear it without leaving ComfyUI
- 1080x1920 export chain, bypassed. Render at 0.6 MP and upscale for delivery rather than
  paying 3x to render at 1.03 MP. Target is fixed 1080x1920, so set it yourself for landscape
- `SaveAudio`, bypassed. The audio stem alone

**Chaining + low-RAM group**, from the optional packs:

- All four Motion Context nodes ship bypassed. Un-bypass `Save Latent` on a clip you may want
  to continue; it writes a ~7 MB latent. To continue one, also un-bypass `Motion Context`,
  `Trim` and `Load Latent`. Motion Context refuses to run with nothing to pin, so it cannot be
  left on by accident
- `ClipProj Loader`, bypassed and unconnected. Un-bypass and wire its `CLIP` output where the
  GGUF loader's went

Twelve nodes ship bypassed: two mode nodes, EasyCache, four export nodes, four chaining
nodes and ClipProj. Enabling any is one click.

API node counts once model paths are repointed: 20 as shipped, 21 with the first `LoadImage`,
22 with both, 24 with all four chaining nodes enabled, 24 with the export extras, plus one more
in any state with EasyCache.

## Foxydit port

Original by foxfuressence, [civitai.com/models/2834514](https://civitai.com/models/2834514),
version 3201486. Redistributed with permission, see `NOTICE.md`. Structure unchanged:
T2V/I2V/FFLF and REF2VA toggling, four reference picture slots plus video and audio, VRAM
cleaning, group bypassers.

Bypassed for Mac, left visible rather than deleted:

- `SolAttnPatch`, Sol-Attn needs triton, no Apple Silicon build
- `PathchSageAttentionKJ`, SageAttention is CUDA only
- `RIFEInterpolation`, see below

`CLIPLoader` swapped to `CLIPLoaderGGUF`. Spectrum enabled at degree 1 / warmup 1 rather than
upstream's degree 4 / warmup 5; EasyCache stays bypassed. Never both, per the original's own
note.

The port severs the link feeding `VHS_VideoCombine`'s frame rate and pins it to 24. That link
carried 60 for the RIFE branch, and with RIFE bypassed every render played 2.5x fast with
chopped audio. Reconnect it if you wire `RIFE VFI` in.

This rig needs a second checkpoint. It ships with the ref2va DiT active
(`minimax_h3_ref2va_pruned_int8_convrot.safetensors`, ~21 GB, same Comfy-Org repo) and the
fl2va one bypassed. Toggle the two UNETLoaders to switch paths.

Same optional blocks as MacMax. Trim sits on the raw decode, ahead of the RIFE branch, so
pinned frames come off before anything downstream sees them. API node counts: 28 as shipped,
32 with all four chaining nodes enabled.

**RIFE.** The original ships `RIFEInterpolation` active, but no version of
ComfyUI-Frame-Interpolation registers that node type; it provides `RIFE VFI` with a different
signature, so left active the graph fails validation on any platform. RIFE itself works on
Apple Silicon: `RIFE VFI` with `rife47.pth`, float32, ensemble on, took 8 frames of a 608x1056
clip to 15 in 12 s on MPS. Delete the bypassed node and wire `RIFE VFI` in its place.

## Expected red nodes

Both workflows use bare stock model filenames. If your models sit in subfolders ComfyUI
rejects the prompt at validation. Re-pick the file in each loader once.

Foxydit additionally leaves six node types unresolved on a Mac: `SolAttnPatch`,
`MiniMaxH3MemoryEfficientSageAttentionPatch`, `RIFEInterpolation`, `LoadAudioUI`, and
rgthree's `Fast Groups Bypasser` and `Label`. They ship bypassed, so ComfyUI drops them when
building the API prompt. Do not un-bypass them.

If you write your own validator: 46 boundary links in the Foxydit subgraph use negative
sentinel IDs (`-10`, `-20`) for subgraph inputs and outputs. Those are valid.

## Verified

Clean install, ComfyUI 0.30.0. Both workflows load, validate and render end to end from the
shipped files, with the documented model-path repoints as the only edits.

- MacMax: 608x1056, 24 fps, 5.167 s, h264 + AAC stereo, 31:48 total with Spectrum v0.2.3
  enabled, zero fallbacks
- Foxydit: rendered twice on the REF2VA path with one reference image, at 0.5 MP and at
  768x1376. Reference images do not ship, point Picture 1 at your own

## EasyCache, if you enable it

It is a b-roll tool. At 0.6 MP with a face in frame it visibly breaks up the mouth; at 1.03 MP
the same test came back clean, because more face pixels means the cached-step error hurts
proportionally less. Rule of thumb: faces at 0.6 MP and below, off; faces at ~1 MP, judge your
own output; no faces, on.

| canvas | saving |
|---|---|
| 0.6 MP at 5s | -42% sampling, -36% wall |
| 1.03 MP at 3s | -43% |
| 0.4 MP | -13% |

Skipped steps: 9 of 20, or 5 of 15.

## Metrics

Correlations here come from `compare_render.py`: Pearson correlation of mean-centred greyscale
frames, 32x32 for layout, 128x128 for detail, sampled at four points in the clip. Luma only,
so it cannot see colour shifts, and it cannot resolve a mouth. "Above 0.8 is the same
composition" is a convention here, not a validated boundary. No LPIPS, SSIM or FVD. No metric
here evaluates audio beyond levels and Whisper transcripts.


## MacMax FOXYDIT v20

The Apple Silicon port of the v20 pod workflow. One graph, four modes, laid out as numbered
groups you switch on and off rather than four separate files.

```
1..4  <Picture N>        reference images for REF2VA and I2V
5     <Audio 1>          + 5.1 force custom audio to latent
6     <Video 1>          video reference
1..4  attention/speed    Sage-Attn, Comfy-Kitchen attention, Sol-Attn, Spectrum
7..9  SHIFT, LoRA, temporal upsample
5     VFI                frame interpolation 24 -> 48 fps
```

**Requires ComfyUI 0.32.0 or newer.** `ModelAttentionBackend` is an ACTIVE node and only exists
from 0.31.0. 0.32.0 also calls `comfy_kitchen.int8_attention_is_available()`, so bump that package
at the same time or ComfyUI will not start:

```sh
python -m pip install -U 'comfy-kitchen>=0.2.31'
```

### Current Mac defaults

The saved graph is a practical viewing recipe, not an attempt to make one setting masquerade as
every lane:

| lane | model / acceleration | steps | canvas | use |
|---|---|---:|---:|---|
| **default / viewing** | FL2VA Q5 + Turbo 8 LoRA 1.0 + Spectrum degree 1, warmup 1 | 8 | 0.5 MP | choose refs, motion and prompt |
| **detail check** | same, Spectrum bypassed | 8 | 0.5 MP | compare when skin, texture or identity looks too smooth |
| **base-quality experiment** | Turbo LoRA bypassed + Spectrum degree 1 | 20-25 | choose deliberately | very slow; reserve for a justified final A/B |

`er_sde` + `beta` remains the v20 R2V sampler pair. Ref2VA Q5 remains in the graph as a one-click
checkpoint A/B, but FL2VA ships active because it has been the better general-purpose model
through the R2V conditioning node.

All four `<Picture N>` loaders ship bypassed. Pick a real file and enable one or more slots before
an R2V render. This replaces upstream's broken default, which enabled a private author image that
does not ship. With no picture slots enabled, the conditioning node remains valid for non-R2V use.

There is no PlagueKind SLA node in the local Apple Silicon install. That is the pod/CUDA lane;
Spectrum is the supported local accelerator. Do not enable EasyCache alongside Spectrum.

VFI and temporal de-rope alter time, not spatial resolution. They are not the Foxy latent 2x
upscaler and are not documented as an upscale lane here.

### Motion Context in v20

The derived v20 graph now carries the same native H3 AV-latent continuation path as the smaller
MacMax workflow. It is intentionally bypassed by default:

- **Clip 1:** enable only `Save THIS clip AV latent`; Save index `1`
- **Clip 2:** enable Load, Motion Context, Trim and Save; Load `1`, Save `2`
- **Clip 3:** Load `2`, Save `3`; continue the same pattern

The save uses fixed numbered slots, so re-rolling clip 2 overwrites clip 2 instead of accidentally
conditioning the retry on its rejected output. Resolution and FPS must stay fixed across a chain.
At the default 22-frame context window, continuation clips finish exactly 22 frames shorter after
picture and audio are trimmed together. No compositing or decoded-frame round trip is involved.

This branch requires the optional `ComfyUI-H3-Motion-Context` pack (`install_node_packs.sh extras`
or `all`). Leaving all four nodes bypassed keeps it genuinely optional.

### What differs from the pod original

The pod file targets Blackwell. Five loader nodes are swapped for the Apple Silicon stack. The
derivation also applies the explicit Mac defaults above and fixes the local LoRA path:

| node | pod | here |
|---|---|---|
| DiT x2 | `*_int8_convrot.safetensors` via `UNETLoader` | `MiniMax-H3-{Ref2VA,FL2VA}-Pruned-Q5_K_M.gguf` via `UnetLoaderGGUF` |
| text encoder | `qwen3vl_32b_..._nvfp4_awq` | `qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf` via `CLIPLoaderGGUF` |
| video VAE | `minimax_h3_video_vae_int8_convrot` | `minimax_h3_video_vae_fp16` |
| audio VAE | stock filename | same format, local `_h3/vae/` path |

int8_convrot *can* load on Apple Silicon — MacMax ships it active — but here it has no LoRA patch
path and OOMs, which rules out the 8-step turbo LoRA. GGUF keeps that option open. The audio VAE
is fp32 and unchanged.

Regenerate rather than hand-edit: `python3 build_mac_v20.py [SOURCE.json]`. Add `--install` with
the workflow directory to refresh the stable `MacMax_H3_R2V_CURRENT.json` copy. It asserts each
loader's incoming widget layout and refuses to run if upstream moved, because the two class swaps
drop a widget slot each (`UNETLoader` has `weight_dtype`, `UnetLoaderGGUF` does not) and a silent
one-slot shift is how a previous port fed a filename into a float parameter.

### Nodes that stay red, and why that is fine

`SolAttnPatch` and `MiniMaxH3MemoryEfficientSageAttentionPatch` are CUDA/triton and ship
**bypassed**. `LoadAudioUI` is bypassed too and its pack is not installed by default. Red while
bypassed is cosmetic.

`Fast Groups Bypasser (rgthree)` is a **frontend-only** node — it has no Python class and never
appears in `/object_info`. A graph checker will report it missing; it is not.

`LoadImageCrop` is the exception: it is **ACTIVE**, so the workflow will not render without
`comfyui-obvpm`. `install_node_packs.sh v20` pulls it. That pack is not in the ComfyUI-Manager
registry, so Manager's "install missing nodes" will not find it for you.


### First run: checks before anything renders

Verified on a pod 2026-08-16 — each of these produced a failed queue in under a second.

1. **Choose your references.** The generated Mac port now bypasses all four author-image loaders,
   so a missing private filename no longer kills the queue. Re-point and enable the slots you want
   for R2V; do not merely edit the filename while leaving the node bypassed.
2. **`ComfyUI-MAINodes` is an undeclared optional dependency.** The "9. Temporal Upsample Pass"
   group uses `H3JerkOracle`, `H3TimeSmear`, `H3V2VInit`, `H3ExactRecover` and `H3InjectSchedule`.
   They ship bypassed, so it renders without them, but they will show red and no pack-metadata
   scan finds them — those nodes carry no `cnr_id`.
3. **Length may not be what you asked for.** Pinning `length` on the H3 node gave 56 frames for a
   requested 49; the graph recomputes it from the "Video Length (seconds)" primitive and the
   frame-count maths. Set the seconds value, then check the output rather than assuming.

For reference, a working pod run: REF2VA, 768x832, 8 steps, `er_sde`, **66 seconds** on an RTX
5090, identity carried cleanly from a single reference image.
