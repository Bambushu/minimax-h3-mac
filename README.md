# MacMax Turbo

MiniMax H3 generates video with native stereo audio in one pass. This runs it locally on a Mac from a single workflow, `MacMax_MiniMaxH3_AppleSilicon.json`, with an optional turbo-LoRA fast path.

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

ComfyUI 0.30.0 in its own checkout and venv. Stay on 0.30.0: the Spectrum author reports a later update breaking their node and degrading MiniMax audio.

Required node packs:
- **ComfyUI-AppleSilicon-FP8**
- **ComfyUI-GGUF** - plus `pip install gguf==0.18.0`
- **ComfyUI-Spectrum-MiniMax-H3** - pin **v0.2.3**

Optional, both ship bypassed:
- **ComfyUI-H3-Motion-Context** - chaining
- **ComfyUI-ClipProj** - smaller text encoder

`./install_node_packs.sh macmax` clones the required three. `extras` adds the optional two.

```bash
ASFP8_INT8_EXT=1 python main.py --port 8288 \
    --reserve-vram 10 --cache-none --disable-smart-memory
```

H3 loads three models in sequence and never needs two at once, hence the memory flags.

Take one commit on top of 0.30.0: [PR #15446](https://github.com/Comfy-Org/ComfyUI/pull/15446) streams the VAE in temporal chunks. `git cherry-pick -x 2a68ce3`.

48 GB is what everything here was measured on. 32 GB works too.

## Render times

Base int8 path, 0.5 MP vertical, Spectrum on, chunked VAE, ClipProj encoder.

| shot | steps | wall |
|---|---|---|
| 3s image to video | 20 | ~14 min |
| 5s text to video | 20 | ~24 min |
| 5s image to video, chained link | 20 | ~39 min |

## Settings

| lever | verdict |
|---|---|
| **Spectrum, degree 1** | **ships ON.** -27% wall, faces hold |
| EasyCache 0.2 | -34% but smears mouths and teeth. Ships bypassed. Never alongside Spectrum |
| steps | base path 20; Parasyte turbo path 8 |
| `history_storage` | `system_ram`. On unified memory `vram` buys nothing |
| ASFP8 int8 kernel, mtlflashattn | no measurable gain on H3 shapes |
| SageAttention, Sol-Attn | CUDA only |

The workflow ships sampler `euler`, not the stock templates' `res_multistep`. Scheduler stays `simple`.

## Turbo LoRA

The turbo LoRA is **PlagueKind "Parasyte"** (`H3-PK-Parasyte-Turbo.safetensors`, 2.1 GB), which replaced the older lightx2v turbo. It already sits in the workflow, bypassed by default.

**It needs the GGUF DiT.** The int8 base checkpoint has no cheap LoRA patch path — a bf16 LoRA forces it toward full precision and OOMs. To switch to the turbo path: un-bypass the pruned GGUF DiT (`Unet Loader (GGUF)`, [MiniMax-H3-FL2VA-Pruned-Q5_K_M.gguf](https://huggingface.co/Abiray/MiniMax-H3-Pruned-GGUF), 14 GB) and the `LoraLoaderModelOnly` carrying Parasyte at strength 1.0, bypass the base `UNETLoader`, and drop the step count (~8).

The base int8 path at 20-25 steps stays the quality lane; its scene detail is visibly finer. Turbo is for volume and previz.

The older lightx2v turbo LoRA is deprecated and no longer used.

## Chaining

The workflow ships a Motion Context block that continues a clip: motion carries across the cut, the scene holds, and so does the audio bed. Needs [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).

Chaining needs a latent from the clip you are continuing. Un-bypass Save Latent and render the first clip; it writes about 7 MB under `output/h3_context/`. For the continuation, also un-bypass Motion Context, Trim and Load Latent, set Load Latent's `clip_index` to the clip you are continuing from and Save Latent's to this one, queue.

All four ship bypassed, so the pack stays optional.

**The continuation comes back exactly 22 frames shorter.** Those are the pinned context frames and Trim removes them so the files concatenate cleanly.

Three rules:
- **Write each beat to fill the whole clip.**
- **Lock framing in clip 1.** Every later clip inherits it.
- **Resolution must match** across chained clips.

## Smaller text encoder

The workflow carries a bypassed `ClipProj Loader`. It swaps the 14.6 GB GGUF encoder for Qwen3-VL-8B fp8 plus a 380 MB projection matrix, about 3.7 GB lighter, encoding on CPU. Needs [ComfyUI-ClipProj](https://github.com/nicolab28/ComfyUI-ClipProj) and a matrix from [NicoLab28/ClipProj-MiniMax-H3](https://huggingface.co/NicoLab28/ClipProj-MiniMax-H3).

**It buys length, not speed.** 5s renders fit on 48 GB, which they did not before.

**The projection is an approximation, and proper nouns are where it shows.** Keep the GGUF loader for any line carrying brand names, proper nouns or technical terms, and reach for ClipProj when you need the length.

## Limits

One machine, one model config, and several correlations rest largely on one prompt, so the times are a strong prior rather than a law. No metric here evaluates audio beyond whether Whisper recovered the words. Chaining is validated at 5s links; longer links are reported elsewhere to fall apart around 15s. The 2K upscaler and prompt-expander are not open-sourced.