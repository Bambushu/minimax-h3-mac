# Which workflow

| file | nodes | extra packs | use it for |
|---|---|---|---|
| `MacMax_MiniMaxH3_AppleSilicon.json` | 26 + 3 notes | 2 | default. T2V, I2V and FLF in one graph |
| `h3_mac_FOXYDIT_filmmaking.json` | 56 | 8 packs, plus a 2nd 21 GB DiT | full rig: 4 reference pictures, video, audio, REF2VA |

`./install_node_packs.sh [macmax|foxydit|all]` installs the packs. Run it with nothing
rendering. MacMax needs exactly two: ComfyUI-GGUF and ComfyUI-AppleSilicon-FP8. Both are
installed for every target because all three workflows need them. `ResolutionSelector` is
ComfyUI core, not a custom node.

For scripted runs use `render_h3.py`. `--dump-graph out.json` emits the API graph. It works
from `h3_api.json`, which is its own base graph and is not an export of MacMax: the two have
diverged and `h3_api.json` still carries `ImageResizeKJv2` and `UnetLoaderGGUF`.

## MacMax

Laid out in reading order, grouped by what you touch:

```
1 - EDIT THESE      canvas, duration, seed, steps
2 - PROMPT          the prompt and frame-count maths
3 - MODE            two collapsed LoadImage nodes
MODELS (set once)   DiT, text encoder, both VAEs
SPEED (leave alone) EasyCache, sigma shift
SAMPLING            internals
OUTPUT              decode, mux, save
EXTRAS              audio preview, 1080p export, audio stem
```

The two `LoadImage` nodes ship collapsed and bypassed. Leave both off for T2V, enable the
first for I2V, enable both for FLF. `MiniMaxH3ImageToVideo` already takes optional
`first_frame` and `last_frame`, so no switches or extra packs are needed.

MacMax does not do R2V. Carrying identity from reference stills uses a different
conditioning node (`MiniMaxH3ReferenceToVideo`); the Foxydit port covers that.

Defaults are 0.6 MP at 5s, 20 steps, EasyCache present but OFF (see the face warning under
Numbers that matter). It also exposes `MiniMaxH3SigmaShift` (12/3), which the shipped ComfyUI
template omits.

### Extras

All ComfyUI core, so the two-pack requirement still holds.

- `PreviewAudio`, active. H3's headline feature is the audio and there was no way to hear it
  without leaving ComfyUI to open the file. Free to run.
- 1080x1920 export chain, bypassed: `ImageScale` (lanczos) into a second `CreateVideo` and
  `SaveVideo`. This is the practical half of the token budget. Cost is tokens, so render at
  0.6 MP and upscale for delivery rather than paying three times as much to render at
  1.03 MP. The target is a fixed 1080x1920, correct for the 9:16 default but wrong if you
  switch to landscape, in which case set it yourself.
- `SaveAudio`, bypassed. The audio stem on its own for editing.

Seven nodes ship bypassed: the two mode nodes, EasyCache, and the four export nodes.
Everything else is
active. Enabling any of them is one click.

Verified in ComfyUI: 26 functional nodes and 3 notes, no missing node types, no console
errors, no overlapping nodes, every functional node inside a group (the three notes sit
above the graph as a header row, deliberately outside).

MacMax has been rendered end to end from this exact file. See the table below.

API node counts once the model paths are repointed: 19 as shipped (cache off), 20 with the
first `LoadImage` enabled, 21 with both, 23 with the four export extras also enabled, plus
one more in each state if you enable EasyCache. The three
modes were checked by serialising the prompt: both bypassed gives no `first_frame` or
`last_frame`, enabling the first adds `first_frame`, enabling both adds `last_frame`.

On first load the four model loaders may show red. The workflow uses bare stock filenames.
If your models sit in subfolders, re-pick them once. That is the only expected error in
MacMax. The two ports additionally show their bypassed unregistered nodes in red (six types,
listed under What was actually verified); that is normal, not a broken install.

## Foxydit port

Original by foxfuressence, [civitai.com/models/2834514](https://civitai.com/models/2834514),
version 3201486. Redistributed with permission, see `NOTICE.md`. Structure unchanged:
T2V/I2V/FFLF and REF2VA toggling, four reference picture slots plus video and audio, VRAM
cleaning, group bypassers.

Bypassed for Mac, left visible rather than deleted:

- `SolAttnPatch`, Sol-Attn needs triton and there is no Apple Silicon build
- `PathchSageAttentionKJ`, SageAttention is CUDA only
- `RIFEInterpolation`, see below

`CLIPLoader` swapped to `CLIPLoaderGGUF`.

The original's own note says to use Spectrum or EasyCache, never both. This port ships both
bypassed: a seed-controlled A/B showed step caching visibly degrades faces on MPS. For
b-roll, enable one; EasyCache measured better on both axes (-43% wall at layout 0.991,
against Spectrum's -20% at 0.956). An earlier build of this port had both active, which the
author explicitly warns against.

The Spectrum figure is for v0.1.5, the version that matches ComfyUI 0.30.0 and the one the
installer pins. Its author has since released v0.1.8 (degree 1) claiming about -45% with no
visible quality loss, but that targets a later ComfyUI that changed H3's sampling and audio
path, and it is unmeasured here. If you chase it, you leave every number in this pack behind.

The port also severs the link feeding VHS_VideoCombine's frame rate and pins it to 24. That
link carried 60 for the RIFE branch, and with RIFE bypassed every render played 2.5x fast
with chopped audio, measured on a real render. Reconnect it if you wire `RIFE VFI` in.

This rig needs a second checkpoint. It ships with the ref2va DiT active
(`minimax_h3_ref2va_pruned_int8_convrot.safetensors`, about 21 GB, same Comfy-Org repo) and
the fl2va one bypassed. Toggle the two UNETLoaders to switch paths.

### The RIFE bug is upstream, not a Mac problem

The original ships `RIFEInterpolation` active. No version of ComfyUI-Frame-Interpolation
registers that node type; it provides `RIFE VFI` with a different signature. Left active the
graph fails prompt validation on any platform.

RIFE itself works on Apple Silicon. Measured: `RIFE VFI` with `rife47.pth`, float32,
ensemble on, took 8 frames of a 608x1056 clip to 15 in 12 seconds on MPS, including the
first-run checkpoint download. To use it, delete the bypassed node and wire `RIFE VFI` in
its place. `multiplier` 2 doubles the frame rate.

## What was actually verified

Clean install of the node packs, 2026-08-07, ComfyUI 0.30.0. What follows is what the logs
prove, not more:

| workflow | loads in the UI | server accepted the prompt | full render completed |
|---|---|---|---|
| MacMax | yes | yes, after repointing 4 model paths | yes |
| Foxydit | yes, 56 nodes | yes, after repointing | yes |

MacMax was rendered end to end from md5 `f59d355f58922e84b7593f5302beba94`, loaded in the
ComfyUI frontend and queued through its own `graphToPrompt()`. The only edits before pressing
run were the four documented model-path repoints. Result: 608x1056, 24 fps, 5.167 s, h264
plus AAC stereo, total 48:54 uncached. An earlier build was also rendered with EasyCache
enabled (total 31:16, cache skipped 9 of 20 steps).

**The shipped file has since changed** (Spectrum now enabled by default), so its md5 no
longer matches that render. The Spectrum figures quoted here - 34:27, 8 of 20 steps forecast,
faces intact - were measured at the same canvas, seed, steps and Spectrum dials (degree 1,
warmup 1) through the scripted driver rather than the GUI. A fresh end-to-end frontend render
of the current file is pending; until it lands, treat the provenance above as covering the
graph structure and the uncached and EasyCache numbers, not the Spectrum row.

Foxydit was rendered end to end twice on the REF2VA path with one reference image: once at
the original's 0.5 MP defaults (which also exposed the 60 fps playback bug this port now
fixes) and once at 768x1376, 24 fps, 3.04 s with stereo audio, uncached. It needs reference
images, which do not ship; point the Picture 1 loader at your own.

validation, not accepted:

```
Failed to validate prompt for output 2568:
* VAELoader: Value not in list: 'MiniMaxH3/minimax_h3_audio_vae_fp32.safetensors' not in [...]
```

That is the model-path problem, not a porting problem, and it is fixed by re-picking the
otherwise unproven.

uses its author's. All three need the same one-time re-pick if your layout differs.

Six node types stay unresolved on a Mac install: `SolAttnPatch`,
`MiniMaxH3MemoryEfficientSageAttentionPatch`, `RIFEInterpolation`, `LoadAudioUI`, and
rgthree's `Fast Groups Bypasser` and `Label`. They ship bypassed, so ComfyUI drops them when
building the API prompt and the graph still validates, but they show red in the editor. Do
not un-bypass them.

which does not exist. This is not something this port introduced: the upstream original has
the same two, byte for byte, and ComfyUI loads it anyway. Flagged here so nobody spends an
afternoon on it.

If you write your own validator, note that the other 46 boundary links in that subgraph use
negative sentinel IDs (`-10`, `-20`) for the subgraph's own inputs and outputs. Those are
valid. A naive check that requires every link endpoint to be a real node ID will report all
48 as broken.

## What "layout correlation" means

Every correlation here comes from `compare_render.py`. It is a crude structural metric, not
a perceptual one. No LPIPS, no SSIM, no FVD.

- layout: Pearson correlation of mean-centred 32x32 greyscale frames, sampled at 5%, 35%,
  65% and 95% of the clip, averaged
- detail: the same at 128x128
- motion: Pearson correlation of per-frame motion-energy curves, 12 samples, each the mean
  absolute difference between consecutive 64x64 luma frames

Luma only, so it cannot see colour shifts. The "above 0.8 is the same composition" threshold
is our convention, not a validated boundary. Two clips can score 0.99 and still differ
visibly. Sample size is roughly 40 renders on one machine, and for the correlations
specifically, one prompt at one canvas. No metric here evaluates audio; audio claims are
levels and Whisper transcripts only.

## Numbers that matter

Cost is a token budget: tokens scale with megapixels times seconds. About 22k is
comfortable, which is 1.03 MP at 3s (131.6 s/step) or 0.6 MP at 5s (137.8 s/step). Both are
sampling-only rates from uncached runs, so they are comparable to each other. 1.03 MP at 5s
is about 37k tokens, runs, and costs three times the wall clock.

EasyCache is a b-roll tool at low resolution. A seed-controlled A/B at the MacMax defaults
(same seed, prompt and canvas, cache the only variable) showed visible pixel breakup around
the mouth and face with the cache on and a clean result with it off. The structural layout
metric scores them 0.991-similar because it is computed on thumbnails that cannot resolve a
mouth. The workflows therefore ship their caches bypassed.

Canvas changes the verdict: the same test at 1.03 MP / 3s with the cache on came back clean,
in stills and in motion. More face pixels means the cached-step error hurts proportionally
less. Rule of thumb: faces at 0.6 MP and below, cache off; faces at ~1 MP, cache is usable,
judge your own output; no faces, cache on.

For shots without faces it pays off differently by canvas, so quote the one that matches
your render:

| canvas | EasyCache saving | layout |
|---|---|---|
| 0.6 MP at 5s (the shipped default) | -42% | not measured at this canvas |
| 1.03 MP at 3s | -43% | 0.991 |
| 0.4 MP | about -13% | 0.997 |

The default-canvas figure comes from the MacMax proof render. The cache's first skipped step
in that run came after step 6 (visible in the per-step rates), so steps 2-6 are uncached and
cost 137.8 s/step, which projects to 45.9 min for 20 uncached steps. Actual cached sampling
was 26.6 min, so -42%. Same run, same seed, same process, which makes it a tighter comparison
than two separate runs. ComfyUI's own counter reports 1.82x for the same render; that is
computed from skipped steps, not wall clock, and does not include the steps before the cache
engages.

Those are sampling-only figures. Wall clock adds a fixed ~3.5 min of model loading either
way, so the two full renders of this workflow (48:54 uncached, 31:16 cached, different
builds) show about -36% wall. Quote -42% for sampling, -36% for total wall at this canvas.

Skipped-step counts, since the ratio is what people quote: 9 of 20 at 20 steps, 5 of 15 at
15 steps. Cutting steps instead costs 0.940 for -25%.

Below about 6 steps, speech breaks before video does.

Full detail and the dead ends are in `README.md`.
