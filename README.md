# MiniMax H3 on Apple Silicon

MiniMax H3 generates video with native stereo audio in one pass. It runs locally on a Mac.
This is the config that worked, what each setting costs, and what didn't work.

Measured on a 48 GB M5 Pro, ComfyUI 0.30.0, torch 2.13, over roughly 40 renders on
2026-08-04 to 08-07. One machine, mostly one prompt. Treat the numbers as a strong prior,
not a law.

Three workflows ship here. See `WORKFLOWS.md` for which to use and what each one contains.

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

ComfyUI 0.30.0 in its own checkout and venv, and stay on 0.30.0: everything here was
measured there, and the Foxydit author reports a later ComfyUI update breaks the Spectrum
node and degrades MiniMax audio (2026-08-07, unverified here but from the person who would
know). Custom nodes:

- ComfyUI-AppleSilicon-FP8, required, the int8 path will not load without it
- ComfyUI-GGUF, plus `pip install gguf==0.18.0` or it reports IMPORT FAILED
- ComfyUI-Spectrum-MiniMax-H3, pinned to v0.2.3. MacMax ships with Spectrum enabled, so
  without this pack the node will not resolve and the graph will not run. Delete the node
  and reconnect sigma shift to the sampler if you would rather not add it

`ResolutionSelector` is ComfyUI core (`comfy_extras/nodes_resolution.py`).
`./install_node_packs.sh macmax` clones all three and pins gguf. The Foxydit port needs more; run it
with `foxydit` or `all`.

```bash
ASFP8_INT8_EXT=1 python main.py --port 8288 \
    --reserve-vram 10 --cache-none --disable-smart-memory
```

H3 loads three models in sequence (encoder 15 GB, DiT 20 GB, VAEs 6 GB) and never needs two
at once, which is why the memory flags are there.

48 GB unified memory is what this was measured on. 32 GB is untested and expected to be
tight. Below 32 GB is not recommended.

## Cost

Same canvas, 768x1376 vertical, 3s, seed 6120072732051.

| steps | EasyCache | wall | layout vs uncached 20-step |
|---|---|---|---|
| 20 | on (0.2) | 27 min | 0.991 |
| 20 | off | 47 min | reference |
| 15 | on (0.2) | 25.3 min | 0.940 |
| 15 | off | 35 min | 0.940 |

All four transcribe the test line exactly.

Other canvases, uncached. The last column is wall clock divided by steps, so it carries model
load and decode with it. Sampling-only rates are lower and are the ones to compare against
the EasyCache numbers: the 768x1376 3s run samples at 131.6 s/step against a 142.1 wall rate,
because 3:29 of its 47.4 minutes is fixed overhead.

| canvas | secs | steps | wall | wall/step |
|---|---|---|---|---|
| 864x480 | 3s | 20 | 16.5 min | 49.5 |
| 768x1376 | 3s | 20 | 47.4 min | 142.1 |
| 768x1376 + keyframe | 3s | 20 | 57.1 min | 171.2 |
| 768x1376 | 5s | 20 | 116.8 min | 350.4 |

Keyframe conditioning costs about 17.6% per step.

## Cost is a token budget

Tokens scale with megapixels times seconds. Resolution and duration are not separate limits.

Sampling rate only, uncached, so these are comparable to each other:

| config | tokens | s/step | source |
|---|---|---|---|
| 1.03 MP at 3s | ~22k | 131.6 | 20-step uncached run |
| 0.6 MP at 5s | ~22k | 137.8 | steps 2-6 of the MacMax proof render, before its cache's first skip |
| 1.03 MP at 5s | ~37k | ~340 | wall-derived, no clean sampling figure |

The first two are 4.7% apart on twice the duration at 58% of the area, which is what the
token model predicts. About 22k tokens is comfortable; 37k runs but costs roughly three times
the wall clock and sits near the memory floor. Want 5s shots, drop to 0.6 MP. Want 1.03 MP,
keep to 3s.

Length cost is superlinear for the same reason: at 4 steps, 5s (124 frames) took 27 min and
8s (192 frames) took 89 min. 1.55x the frames, 3.3x the clock. 8s fits in memory. 10s is
untested, not refuted.

## Speedups

| lever | result |
|---|---|
| **Spectrum, degree 1** | **ships ON in both workflows.** -27% (34:27 vs 47:21 uncached) at the 0.6 MP/5s default, 8 of 20 steps forecast. Faces hold: teeth and lips stay defined, no artefacts |
| EasyCache 0.2 | faster still (31:16, -34%) but it **smears mouths and teeth**. Ships bypassed. Fine for faceless b-roll, where the artefacts have nothing to damage. Never run it alongside Spectrum |
| ASFP8 int8 kernel | no measurable gain on H3 shapes |
| mtlflashattn | no gain at 15k tokens |
| SageAttention, Sol-Attn | CUDA only, no Apple Silicon build |

Both accelerators skip sampling steps, but not the same way. EasyCache **reuses** a cached
state; Spectrum **forecasts** the skipped step from a fitted curve. That difference is why
fast-changing detail like a mouth survives one and not the other.

Measured on face crops resized to a common size, same seed and prompt, so resolution cannot
win for free:

| | wall | fine detail | faces |
|---|---|---|---|
| uncached | 47:21 | 0.381 | reference |
| EasyCache 0.2 | 31:16 | **0.405** | mouths and teeth visibly smeared |
| Spectrum d1 | 34:27 | 0.368 | teeth and lips hold |

Note that EasyCache scores the **highest** on fine detail while looking the **worst**. It is
not resolving detail, it is injecting spurious high-frequency edge noise, so any sharpness
metric rewards it. Earlier versions of this pack recommended EasyCache on exactly that kind
of evidence: a 0.991 layout correlation computed on 32x32 thumbnails that cannot resolve a
mouth. If you benchmark a cache, look at a face at full size before you trust a number.

Cutting steps remains the worse lever: 15 steps costs 0.940 layout correlation for -25%.
Use 20 steps with Spectrum on.

### Spectrum v0.2.3, and one Apple Silicon finding

This pack now pins **v0.2.3**, not v0.1.5. If you took an earlier copy, update: MacMax ships
Spectrum enabled, and v0.1.5 degrades H3's audio.

Why that happens is specific to H3. It does not generate audio and video as separate streams -
they are packed into one transformer sequence and interact through joint attention on different
shifted timestep schedules. v0.1.5 applied a single shared blend weight to both, so a forecast
error in video reached audio and came back as rough or distorted sound, tripped words and
doubled syllables. Zeroing the audio blend alone does not fix it, because the next *actual*
transformer call still sees the modified video state alongside the audio. v0.2.1+ separates the
controls and adds a transformer-free replay pass that rebuilds skipped steps from anchors on
both sides of the gap.

Measured here on ComfyUI 0.30.0, 28 runs, zero fallbacks:

| | |
|---|---|
| actual transformer calls at 20 steps | 11 (+ 9 forecast), unchanged from v0.1.5 |
| replay pass cost | ~3.3 s, and **zero** transformer blocks |
| `history_storage=vram` vs `system_ram` | **22.2 min vs 21.9 min, frames bit-identical** |

That last row is the Apple Silicon part. Upstream suggests `vram` to avoid host-to-device
copies. On unified memory there is no copy to avoid - it is the same physical RAM - so the
setting buys nothing here. **Leave it on `system_ram`.**

One softer observation, offered as a single data point rather than a result: on a macro water
prompt at a fixed seed, `euler` produced properly domed droplets with real depth falloff where
`res_multistep` gave flat, gel-like discs, and euler also forecast one more step (11 actual / 9
forecast vs 12 / 8). Both workflows here still ship `res_multistep`. Worth an A/B on your own
content before changing anything.

## Previz

Previz at the final resolution with 10-12 steps. Never lower the resolution.

| change | layout | verdict |
|---|---|---|
| 0.2 MP vs 0.4 MP, 10 steps both | 0.257 | different shot |
| 0.3 MP vs 0.4 MP, 10 steps both | 0.361 | different shot |
| 0.4 MP at 10 vs 0.4 MP at 20 | 0.832 | same composition |

Measured at 0.2 to 0.4 MP and applied at 1.03 MP, so it is an extrapolation resting largely
on one prompt. Dropping resolution saves 16-24% and costs the whole composition.

Below about 6 steps, speech breaks before video does. At 4 steps the picture is clean but
dialogue loops or vanishes. Judge audio at 10+ steps.

## Dead ends

**Turbo LoRA does not pay off.** It cannot run at runtime: three attempts OOM'd
byte-identically (MPS allocated 37.20 GiB, max allowed 37.44) across a 2.6x canvas change
and a 4 GB `--reserve-vram` change. Identical numbers mean the allocation is
workload-independent, so canvas and step count are not levers, and `--reserve-vram` does not
set that ceiling. The LoRA targets 208 layers, 99.2% of the checkpoint, and a layer carrying
a LoRA falls back to a float linear on a dequantized weight, bypassing the int8 kernel.
Merged offline it loads and renders but gives no speedup at 10 steps and unusable speech at
4, indistinguishable from base. Untested at runtime on CUDA.

**Latent-space chaining is impossible.** Slicing clip A's last latent as clip B's keyframe
cannot work on a causal VAE. Probed with identical frames: the first latent of a sequence is
bit-identical to a single-frame encode (1.000000), the last is 49.20% different (0.873).
That is causal temporal positioning, not content. The decode-encode round trip costs about
8% pixel error per hop, and hop2/hop1 is 0.77, so drift converges rather than compounding.

**ConvRot weights are stored rotated.** comfy_kitchen stores `W_rot = W @ H_blockT` and
`dequantize()` rotates back, so `qdata.float() * scale` is not the native-basis weight. The
difference measured 136.62%. Merging an unrotated delta into it produces a checkpoint that
loads fine and renders plausibly while being wrong. Use
`comfy_kitchen.tensor.int8.TensorWiseINT8Layout` in both directions. A dequant-requant round
trip matching the stored int8 exactly proves only self-consistency within the stored basis,
not that the basis is native.

## Limits

One machine, one model config. The cost table will not transfer directly. The previz
protocol and several correlations rest largely on one prompt. No metric here evaluates audio
beyond whether Whisper recovered the words. The 2K upscaler and prompt-expander are not
open-sourced.
