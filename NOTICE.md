# Attribution and licensing

This pack contains one original workflow and two modified redistributions of other
people's work. Both are included with credit; both will be removed on request by their
authors, open an issue or contact MAD IT.

---

## `MacMax_MiniMaxH3_AppleSilicon.json`, ours

By MAD IT. Derived from ComfyUI's own shipped template
`comfyui_workflow_templates/templates/video_minimax_h3_t2v.json`, flattened out of its
subgraph and retuned. Nothing in it is a reimplementation of the H3 nodes themselves; those
are ComfyUI core.

That template is MIT licensed, Copyright (c) 2023-present Comfy Org. Its copyright and
permission notice are reproduced in full in `LICENSE-MIT.txt`, as that licence requires.

## `h3_mac_FOXYDIT_filmmaking.json`, MODIFIED from foxfuressence

- Original author: foxfuressence
- Source: https://civitai.com/models/2834514, model version 3201486, downloaded
  2026-08-07
- Licence / permission: **redistribution of this modified copy was approved by
  foxfuressence, on condition of attribution** (granted 2026-08-07; the exchange is
  recorded in `PERMISSION-foxydits.md`). Attribution is given here, in `WORKFLOWS.md`, and
  in an "APPLE SILICON PORT - READ ME" note inside the graph itself. Removed on request at
  any time.
- Modifications made on 2026-08-07. No original node was deleted. Ten existing nodes were
  changed across the eleven listed modifications (node 145 appears twice: its cached preview
  was scrubbed and its frame-rate link severed) and one note was added, as reported by the
  generator (`make_foxydit_mac.py`):
  1. `SolAttnPatch` set to BYPASS, Sol-Attn requires triton, which has no Apple Silicon build
  2. `PathchSageAttentionKJ` set to BYPASS, SageAttention is CUDA-only
  3. `CLIPLoader` → `CLIPLoaderGGUF` (Q4_K_M, type `minimax`), the NVFP4-AWQ encoder is CUDA-only
  4. `EasyCache` threshold retuned 0.3 to 0.2, left BYPASSED as shipped. A seed-controlled
     A/B on MPS showed it smears mouths and teeth, so it stays a b-roll-only toggle
  5. `SpectrumApplyMiniMaxH3` ENABLED (the original ships it bypassed), and its parameters
     changed from degree 4 / warmup 5 to degree 1 / warmup 1. Re-measured on MPS it holds
     faces where EasyCache does not, at -27% wall. The original's own rule is kept: use
     Spectrum or EasyCache and never both, so EasyCache remains bypassed
  5b. `VHS_VideoCombine`'s frame_rate link severed and the widget pinned to 24. The link fed
     60 (the RIFE out-rate); with RIFE bypassed, renders played 2.5x fast
  6. `RIFEInterpolation` set to BYPASS. That node type is not registered by any version
     of ComfyUI-Frame-Interpolation on any platform (it provides `RIFE VFI`), so the
     original fails prompt validation as shipped, on any OS
  7. The one active `LoadImage` (node 137) set to BYPASS. It pointed at a file on the
     author's machine that is not distributed, so pressing Run gave a missing-file error
  8. Cached `videopreview` blobs removed from nodes 145 and 638. These held the author's
     own absolute output path; they are stale UI preview state and carry no graph meaning
  9. A stale CUDA/Windows note banner-prefixed as not applying on Mac
  10. One "APPLE SILICON PORT - READ ME" note added

  `LoadAudioUI` was already bypassed upstream and is not registered on Mac. It was left
  exactly as found and is not counted as a modification.

## Optional node packs referenced by both workflows

Neither is bundled here. Both workflows carry nodes from them, shipped bypassed, and the
installer clones them under the `extras` target.

- **ComfyUI-H3-Motion-Context** by NikoDemon80,
  [github.com/NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context).
  Chaining. It lifts a ComfyUI check that rejected pinned frames other than the first or
  last, which is what makes clip continuation possible at all.
- **ComfyUI-ClipProj** by NicoLab28,
  [github.com/nicolab28/ComfyUI-ClipProj](https://github.com/nicolab28/ComfyUI-ClipProj),
  with projection matrices from
  [huggingface.co/NicoLab28/ClipProj-MiniMax-H3](https://huggingface.co/NicoLab28/ClipProj-MiniMax-H3)
  (matrices MIT). The smaller text encoder.

Their licences are their own. Support both authors.

## Upstream versions are pinned above on purpose

Both originals will keep evolving. These ports are snapshots of the versions and dates
listed; they are not tracking forks. Check the source links for newer releases.

## If you find these useful

Support the original authors, foxfuressence on CivitAI, darksidewalker on GitHub. The
structure of both of those workflows is their work; all we did was disable the parts that
have no Apple Silicon equivalent.


## Licence for everything else in this pack

`MacMax_MiniMaxH3_AppleSilicon.json`, `README.md`, `WORKFLOWS.md`, `NOTICE.md`,
`install_node_packs.sh`, `render_h3.py`, `h3_api.json` and `prompt_vertical.txt` are released
by MAD IT under the MIT licence. Full text in `LICENSE-MIT.txt`. Use, modify and redistribute
them freely, with attribution.

`h3_mac_FOXYDIT_filmmaking.json` is governed by foxfuressence's terms on CivitAI and
redistributed here by his permission with attribution. That file is aggregated alongside the
MIT-licensed files, not derived from them.
