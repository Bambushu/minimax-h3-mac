# Which workflow

| file | nodes | extra packs | use it for |
|---|---|---|---|
| `MacMax_MiniMaxH3_AppleSilicon.json` | 32 + 4 notes | 3, plus 2 optional | default. T2V, I2V and FLF in one graph |
| `h3_mac_FOXYDIT_filmmaking.json` | 62 | 8 packs and a 2nd 21 GB DiT, plus 2 optional | full rig: 4 reference pictures, video, audio, REF2VA |

`./install_node_packs.sh [macmax|foxydit|extras|all]` installs the packs. Run it with nothing
rendering. Both workflows need the same three: ComfyUI-GGUF, ComfyUI-AppleSilicon-FP8 and
ComfyUI-Spectrum-MiniMax-H3 (pinned v0.2.3, its node ships enabled). `ResolutionSelector` is
ComfyUI core, not a custom node.

The two optional packs, ComfyUI-H3-Motion-Context and ComfyUI-ClipProj, are covered in the
README. Every node they add ships bypassed, so neither is needed to render. Without them those
nodes show red, which is cosmetic while bypassed.

For scripted runs use `render_h3.py`; `--dump-graph out.json` emits the API graph. It works
from `h3_api.json`, its own base graph, not an export of MacMax.

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
