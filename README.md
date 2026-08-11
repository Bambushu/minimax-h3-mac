# MiniMax H3 on Apple Silicon

MiniMax H3 generates video with native stereo audio in one pass. This runs it locally on a Mac.

Two workflows. See `WORKFLOWS.md` for which to use.

Measured on a 48 GB M5 Pro, ComfyUI 0.30.0, torch 2.13.

## Models

Four files, about 41 GB, relative to `ComfyUI/models/`.

| path | file | size |
|---|---|---|
| `diffusion_models/` | [minimax_h3_fl2va_pruned_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors) | 20.9 GB |
| `text_encoders/` | [qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf](https://huggingface.co/realrebelai/MiniMax-H3_GGUFs/resolve/main/qwen3vl-32B-MiniMax-H3-Q4_K_M.gguf) | 14.6 GB |
| `vae/` | [minimax_h3_video_vae_fp16.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors) | 5.2 GB |
| `vae/` | [minimax_h3_audio_vae_fp32.safetensors](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors) | 0.6 GB |

Use the GGUF text encoder. The stock NVFP4-AWQ one is CUDA only.

## Setup

ComfyUI 0.30.0 in its own checkout and venv. Stay on 0.30.0: the Spectrum author reports a
later update breaking their node and degrading MiniMax audio. Not verified here.

Required node packs:

- **ComfyUI-AppleSilicon-FP8** - the int8 path will not load without it
- **ComfyUI-GGUF** - plus `pip install gguf==0.18.0`
- **ComfyUI-Spectrum-MiniMax-H3** - pin **v0.2.3**. Ships enabled, so the graph will not run
  without it. Earlier versions degrade audio

Optional, both ship bypassed:

- **ComfyUI-H3-Motion-Context** - chaining
- **ComfyUI-ClipProj** - smaller text encoder

`./install_node_packs.sh macmax` clones the required three. `foxydit` adds the port's extras,
`extras` the optional two, `all` everything.

```bash
ASFP8_INT8_EXT=1 python main.py --port 8288 \
    --reserve-vram 10 --cache-none --disable-smart-memory
```

H3 loads three models in sequence and never needs two at once, hence the memory flags.

Take one commit on top of 0.30.0: [PR #15446](https://github.com/Comfy-Org/ComfyUI/pull/15446)
streams the VAE in temporal chunks. Upstream measured peak VRAM down 58% encode / 83% decode
at identical output; not separately benchmarked here, but it was in place for the times below.
`git cherry-pick -x 2a68ce3`.

48 GB is the tested floor. 32 GB is untested and expected to be tight.

## Render times

0.5 MP vertical, 20 steps, Spectrum on, chunked VAE, ClipProj encoder.

| shot | wall |
|---|---|
| 3s image to video | ~14 min |
| 5s text to video | ~24 min |
| 3s reference to video, with a spoken line | ~29 min |
| 5s reference to video, chained link | ~39 min |

**References cost more than duration.** A 3s render carrying two reference images is slower
than a 5s one carrying none. Budget by megapixels x seconds x references.

## Sizing

Cost tracks megapixels x seconds, not resolution and duration separately. About 22k tokens is
comfortable on 48 GB, 37k runs at roughly 3x the clock and sits near the memory floor.

| you want | use |
|---|---|
| 5s shots | 0.6 MP |
| 1.03 MP | 3s |

Length is superlinear past that: at 4 steps, 5s took 27 min and 8s took 89 min. 8s fits. 10s
untested.

Previz at the **final** resolution, 10-12 steps. Dropping resolution saves 16-24% and changes
the composition entirely: layout correlation 0.26-0.36 across a 2x area change, against 0.83
for a step change at fixed resolution. Measured at 0.2-0.4 MP on one prompt, so treat it as a
prior. Below 6 steps speech breaks before the picture does.

## Settings

| lever | verdict |
|---|---|
| **Spectrum, degree 1** | **ships ON.** -27% wall, faces hold |
| EasyCache 0.2 | -34% but smears mouths and teeth. Ships bypassed, fine for faceless b-roll. Never alongside Spectrum |
| steps | 20. 15 costs real layout for -25% |
| `history_storage` | `system_ram`. On unified memory `vram` buys nothing (22.2 vs 21.9 min, bit-identical) |
| ASFP8 int8 kernel, mtlflashattn | no measurable gain on H3 shapes |
| SageAttention, Sol-Attn | CUDA only |

Both accelerators skip steps differently: EasyCache reuses a cached state, Spectrum forecasts
from a fitted curve. That is why fast-changing detail like a mouth survives one and not the
other. Sharpness metrics *reward* EasyCache because it injects high-frequency edge noise, so
judge a cache on a full-size face, not a number.

Both workflows ship sampler `euler`, not the stock templates' `res_multistep`. Scheduler stays
`simple`.

## Chaining

Both workflows ship a Motion Context block that continues a clip: motion carries across the
cut, the scene holds, and so does the audio bed. Needs
[ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

Every render saves its latent, about 7 MB, under `output/h3_context/`. To continue one:
un-bypass Motion Context, Trim and Load Latent, set Load Latent's `clip_index` to the clip you
are continuing from and Save Latent's to this one, queue.

**The continuation comes back exactly 22 frames shorter.** Those are the pinned context frames
and Trim removes them so the files concatenate cleanly. That length difference is the free
proof it engaged, and the first thing to check.

Measured on two 5s clips at 544x960: join correlation 0.95, frame difference across the cut
inside the clips' own internal motion. Nine links ran as one sequence, 39s continuous.
`samples/sample_MotionContext_chain_25s.mp4` is the first 25s, hard concatenated, no
crossfades, no level matching.

Three rules:

- **Write each beat to fill the whole clip.** If the action finishes early the model fills the
  rest by cutting to an animated version of one of your reference images. Reseeding does not
  fix it, rewriting the beat does.
- **Lock framing in clip 1.** Every later clip inherits it.
- **Resolution must match** across chained clips. The node refuses rather than falling back.

The pack also accepts decoded pixels via `context_frames`, but that pays a lossy round trip on
both streams. Use the latent.

## Smaller text encoder

Both workflows carry a bypassed `ClipProj Loader`. It swaps the 14.6 GB GGUF encoder for
Qwen3-VL-8B fp8 plus a 380 MB projection matrix, about 3.7 GB lighter, encoding on CPU. Needs
[ComfyUI-ClipProj](https://github.com/nicolab28/ComfyUI-ClipProj) and a matrix from
[NicoLab28/ClipProj-MiniMax-H3](https://huggingface.co/NicoLab28/ClipProj-MiniMax-H3).
Un-bypass and wire its `CLIP` output where the GGUF loader's went.

**It buys length, not speed.** 5s renders fit on 48 GB, which they did not before. Two
same-seed reruns against the GGUF encoder held identity, wardrobe, scene and a verbatim spoken
line at the same wall clock. Sampling dominates either way.

The projection is an approximation; the author reports proper nouns as a weak spot. Eyeball
output before trusting it on a job.

## Limits

One machine, one model config, and several correlations rest largely on one prompt, so the
times are a strong prior rather than a law. No metric here evaluates audio beyond whether
Whisper recovered the words. Chaining is validated at 5s links; longer links are reported
elsewhere to fall apart around 15s. Audio carried across ambience beds, not tested on a
musical build. The 2K upscaler and prompt-expander are not open-sourced.
