# MacMax Turbo

**v1.2** — MiniMax H3 generates video with native stereo audio in one pass. This runs it locally
on a Mac, now with an optional turbo-LoRA fast path (see [Turbo LoRA](#turbo-lora)).

One graph — text-to-video, image-to-video, first/last frame — each with native audio.

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

`./install_node_packs.sh macmax` clones the required three. `extras` adds the optional two.

```bash
ASFP8_INT8_EXT=1 python main.py --port 8288 \
    --reserve-vram 10 --cache-none --disable-smart-memory
```

H3 loads three models in sequence and never needs two at once, hence the memory flags.

Take one commit on top of 0.30.0: [PR #15446](https://github.com/Comfy-Org/ComfyUI/pull/15446)
streams the VAE in temporal chunks. Upstream measured peak VRAM down 58% encode / 83% decode
at identical output; not separately benchmarked here, but it was in place for the times below.
`git cherry-pick -x 2a68ce3`.

48 GB is what everything here was measured on. 32 GB works too, reported by users rather than
tested here; expect to stay at the shorter durations.

## Render times

Base int8 path, 0.5 MP vertical, Spectrum on, chunked VAE, ClipProj encoder.

| shot | steps | wall |
|---|---|---|
| 3s image to video | 20 | ~14 min |
| 5s text to video | 20 | ~24 min |
| 5s image to video, chained link | 20 | ~39 min |

On the [Turbo LoRA](#turbo-lora) GGUF path, 0.6 MP, the step count drops to one of two per lane
(4 silent, 6 with audio) and so does the clock:

| shot | steps | wall |
|---|---|---|
| 3s silent | 4 | ~7 min |
| 4s spoken | 6 | ~11 min |

Cost tracks megapixels x seconds. A first-frame image adds little; duration and resolution are
the levers.

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
prior. On the base path, below 6 steps speech breaks before the picture does; the turbo LoRA
shifts that floor down (4 silent, 6 with audio, see [Turbo LoRA](#turbo-lora)).

## Settings

| lever | verdict |
|---|---|
| **Spectrum, degree 1** | **ships ON.** -27% wall, faces hold |
| EasyCache 0.2 | -34% but smears mouths and teeth. Ships bypassed, fine for faceless b-roll. Never alongside Spectrum |
| steps | base path 20 (15 costs real layout for -25%); turbo path 4 silent / 6 with audio |
| `history_storage` | `system_ram`. On unified memory `vram` buys nothing (22.2 vs 21.9 min, bit-identical) |
| ASFP8 int8 kernel, mtlflashattn | no measurable gain on H3 shapes |
| SageAttention, Sol-Attn | CUDA only |

Both accelerators skip steps differently: EasyCache reuses a cached state, Spectrum forecasts
from a fitted curve. That is why fast-changing detail like a mouth survives one and not the
other. Sharpness metrics *reward* EasyCache because it injects high-frequency edge noise, so
judge a cache on a full-size face, not a number.

The workflow ships sampler `euler`, not the stock templates' `res_multistep`. Scheduler stays
`simple`.

## Turbo LoRA

lightx2v distills the sampler into far fewer steps. Their **4-step v1.1** LoRA
(`minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors`, the `_comfyui_bf16` variant,
2.0 GB, from [lightx2v/Minimax-h3-Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo)) is the
fast path — trained on FL2VA, the text-, image- and first/last-frame modes this graph runs. It
patches the GGUF DiT cleanly, with no missing keys.

**It needs a GGUF DiT.** The int8 checkpoint in the Models table has no cheap LoRA patch path: a
bf16 LoRA forces it toward full precision and OOMs. Swap the diffusion model for the pruned GGUF
([MiniMax-H3-FL2VA-Pruned-Q5_K_M.gguf](https://huggingface.co/Abiray/MiniMax-H3-Pruned-GGUF),
14 GB), load it through **ComfyUI-GGUF**'s `Unet Loader (GGUF)`, then insert a
`LoraLoaderModelOnly` at strength 1.0 between that loader and the sampler.

Two step counts, one per lane:

| lane | steps | why |
|---|---|---|
| **silent b-roll** | **4** | the LoRA's design point. About 1.8x faster than the older 8-step LoRA run at 8 steps, and slightly sharper. More steps buy nothing here: 4, 6 and 8 are a flat plateau. |
| **anything with audio** (speech, foley, ambience) | **6** | 4-step audio is faintly tinny; 6 cleans it and the picture holds. |

Measured on the 48 GB M5, 0.6 MP, ClipProj encoder: 3s silent at 4 steps ran ~7 min against ~12 for
the 8-step LoRA at 8 steps; 4s spoken at 6 steps ran ~10 min. Whisper recovered the words verbatim
at every step count from 6 up — **the tinniness at 4 steps is audible, not transcribable**, the same
caveat as everywhere else here: audio is judged by ear, not a metric.

The base int8 path at 20-25 steps stays the quality lane; its scene detail is visibly finer. Turbo
is for volume and previz, not the hero render.

## Chaining

The workflow ships a Motion Context block that continues a clip: motion carries across the
cut, the scene holds, and so does the audio bed. Needs
[ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

Chaining needs a latent from the clip you are continuing. Un-bypass Save Latent and render the
first clip; it writes about 7 MB under `output/h3_context/`. For the continuation, also
un-bypass Motion Context, Trim and Load Latent, set Load Latent's `clip_index` to the clip you
are continuing from and Save Latent's to this one, queue.

All four ship bypassed, so the pack stays genuinely optional. The cost is that you have to
decide a clip is continuable before you render it, not after.

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

The workflow carries a bypassed `ClipProj Loader`. It swaps the 14.6 GB GGUF encoder for
Qwen3-VL-8B fp8 plus a 380 MB projection matrix, about 3.7 GB lighter, encoding on CPU. Needs
[ComfyUI-ClipProj](https://github.com/nicolab28/ComfyUI-ClipProj) and a matrix from
[NicoLab28/ClipProj-MiniMax-H3](https://huggingface.co/NicoLab28/ClipProj-MiniMax-H3).
Un-bypass and wire its `CLIP` output where the GGUF loader's went.

**It buys length, not speed.** 5s renders fit on 48 GB, which they did not before. Two
same-seed reruns against the GGUF encoder held identity, wardrobe, scene and a verbatim spoken
line at the same wall clock. Sampling dominates either way.

**The projection is an approximation, and proper nouns are where it shows.** Measured on one
same-seed, same-prompt pair, the only difference being the encoder:

```
ClipProj : "Any camera is fine, Apple, Andrian or your dakes top at home."
GGUF     : "Any camera is fine, Apple, Android, or your desktop at home."
```

So keep the GGUF loader for any line carrying brand names, proper nouns or technical terms, and
reach for ClipProj when you need the length. **The GGUF encoder is also lighter in practice than
its file size suggests** — ComfyUI frees it once the prompt is encoded, so wired memory during
sampling sits at the DiT plus VAEs (measured 21-24 GB at 0.6 MP). ClipProj ships `mode: resident`,
which pins its weights for the whole render; `streaming` or `dynamic` make them pageable.

## Limits

One machine, one model config, and several correlations rest largely on one prompt, so the
times are a strong prior rather than a law. No metric here evaluates audio beyond whether
Whisper recovered the words. Chaining is validated at 5s links; longer links are reported
elsewhere to fall apart around 15s. Audio carried across ambience beds, not tested on a
musical build. The 2K upscaler and prompt-expander are not open-sourced.
