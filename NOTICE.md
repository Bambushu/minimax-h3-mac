# Attribution and licensing

This release ships one workflow: `MacMax_MiniMaxH3_AppleSilicon.json`, adapted by
MAD IT from ComfyUI’s `video_minimax_h3_t2v.json` template. Its subgraph was
flattened and the workflow retuned for Apple Silicon. H3 execution nodes come
from ComfyUI core; they are not reimplemented here.

The upstream template is MIT licensed, Copyright (c) 2023-present Comfy Org.
Its copyright and permission notice are reproduced in [LICENSE-MIT.txt](LICENSE-MIT.txt).

## External dependencies

The installer retrieves these node packs; their source code is not bundled in
this release. Each retains its own license and authorship:

- [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) — city96.
- [ComfyUI-AppleSilicon-FP8](https://github.com/pawel-mazurkiewicz/ComfyUI-AppleSilicon-FP8) — pawel-mazurkiewicz.
- [ComfyUI-PlagueKind-Nodes](https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes) and [Parasyte LoRA](https://huggingface.co/Plaguekind/H3-Lora) — PlagueKind.
- [comfyui-obvpm](https://github.com/obvpm/comfyui-obvpm) — obvpm.
- [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) — NikoDemon80.
- [ComfyUI-ClipProj](https://github.com/nicolab28/ComfyUI-ClipProj) and [H3 projection matrices](https://huggingface.co/NicoLab28/ClipProj-MiniMax-H3) — NicoLab28.

Model weights are downloaded separately. Refer to each model repository linked
in the README for its licensing and credits. This repository’s MIT license does
not relicense those weights or external dependencies.

## This pack

The workflow, documentation, installer, `render_h3.py`, `h3_api.json` and
`prompt_vertical.txt` are released by MAD IT under the MIT license in
[LICENSE-MIT.txt](LICENSE-MIT.txt).

Earlier revisions included modified third-party workflows. Those files are no
longer distributed in the current release; their historical attribution and
permission records remain in the corresponding repository history.
