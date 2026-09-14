#!/usr/bin/env python3
"""Derive the Apple Silicon port of the FOXYDIT v20 workflow.

    python3 build_mac_v20.py [SOURCE.json]

Emits two files from one source, because the two audiences need different model paths:

  MacMax_FOXYDIT_v20_AppleSilicon.json   PUBLIC — plain filenames, for a stock ComfyUI install
  .local/MacMax_H3_R2V_Foxy_v20_LOCAL.json
                                         OURS — the `_h3/` subfolder layout this Mac uses

Pass ``--install /path/to/ComfyUI/user/default/workflows`` to copy the local build there as
``MacMax_H3_R2V_CURRENT.json``. The old workflow files are left intact for comparison.

DERIVE, DO NOT FORK. When v21 lands, drop it in and re-run this. A hand-edited copy drifts from
upstream and nobody can tell which changes were deliberate.

WHAT CHANGES

The derivation swaps the five model-loader nodes below, applies explicit measured Mac defaults,
and inserts one optional four-node Motion Context branch. The MC branch is bypassed by default,
so the ordinary Foxy path is unchanged until chaining is requested.

v20 ships for a Blackwell pod: int8_convrot DiT and video VAE, nvfp4 text encoder. On Apple
Silicon the GGUF pair is the right stack — not because int8_convrot cannot load (MacMax ships it
active, and ComfyUI-AppleSilicon-FP8 handles the fp8 wall) but because on this box it has **no
LoRA patch path and OOMs**, which rules out the 8-step turbo LoRA that makes local H3 usable at
all. The audio VAE is already fp32 and portable, so it is left alone.

⚠ THE TRAP THIS SCRIPT EXISTS TO AVOID. Two of the swaps are CLASS changes, and the GGUF loaders
have FEWER widgets than the core ones:

    UNETLoader  [unet_name, weight_dtype]  ->  UnetLoaderGGUF  [unet_name]        drop 1 slot
    CLIPLoader  [clip_name, type, device]  ->  CLIPLoaderGGUF  [clip_name, type]  drop 1 slot

Retyping a node without deleting the vacated slots leaves every later value shifted by one. That
exact bug shipped once before: an IC-LoRA received a text-encoder FILENAME as its lora_name and a
LoRA filename as a FLOAT strength, and it failed silently. So each swap asserts the incoming
widget layout first and refuses to run if upstream changed it.
"""
import argparse
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "minimaxH3T2VI2VREF2VAdvanced_v20.json")
PUB = os.path.join(HERE, "MacMax_FOXYDIT_v20_AppleSilicon.json")
LOC = os.path.join(HERE, ".local", "MacMax_H3_R2V_Foxy_v20_LOCAL.json")

# node id -> (expected class, expected widget layout, new class, new widgets)
# "PFX" is substituted per-variant: "" for the public file, "_h3/" for this Mac.
SWAPS = {
    620: ("UNETLoader", ["minimax_h3_ref2va_pruned_int8_convrot.safetensors", "default"],
          "UnetLoaderGGUF", ["PFXMiniMax-H3-Ref2VA-Pruned-Q5_K_M.gguf"]),
    646: ("UNETLoader", ["minimax_h3_fl2va_pruned_int8_convrot.safetensors", "default"],
          "UnetLoaderGGUF", ["PFXMiniMax-H3-FL2VA-Pruned-Q5_K_M.gguf"]),
    128: ("CLIPLoader", ["qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "minimax", "default"],
          "CLIPLoaderGGUF", ["PFXqwen3vl-32B-MiniMax-H3-Q4_K_M.gguf", "minimax"]),
    # same class, value only: the int8 video VAE has no Apple Silicon story, fp16 does
    # VPFX, not PFX: this Mac keeps its VAEs one level deeper (_h3/vae/) than its DiTs (_h3/),
    # while a stock install has them flat. One prefix cannot serve both.
    119: ("VAELoader", ["minimax_h3_video_vae_int8_convrot.safetensors"],
          "VAELoader", ["VPFXminimax_h3_video_vae_fp16.safetensors"]),
    # The audio VAE needs no FORMAT change — fp32 is portable. It still needs the path rewrite,
    # which I initially skipped by reasoning "portable, leave it alone". That reasoning was right
    # about the format and wrong about the path: validation against the live rig caught it
    # pointing at a file that does not exist locally.
    120: ("VAELoader", ["minimax_h3_audio_vae_fp32.safetensors"],
          "VAELoader", ["VPFXminimax_h3_audio_vae_fp32.safetensors"]),
}
NAMED = {"UnetLoaderGGUF": ["unet_name"], "CLIPLoaderGGUF": ["clip_name", "type"],
         "VAELoader": ["vae_name"]}


def add_motion_context(g):
    """Insert the native H3 AV-latent continuation block into Foxy v20.

    The branch is bypassed by default. Save alone records clip 1; enabling Motion Context,
    Load, Trim and Save continues later clips without a decode/re-encode round trip.
    """
    by_id = {n["id"]: n for n in g["nodes"]}
    links = {x[0]: x for x in g["links"]}
    required = {119, 120, 121, 125, 126, 648, 682, 702, 703, 721, 729}
    missing = required - by_id.keys()
    if missing:
        raise SystemExit(f"Motion Context insertion points disappeared: {sorted(missing)}")

    # Assert the exact links we are about to intercept. Silent topology drift here would make
    # MC look enabled while the guider or mux still used the untrimmed path.
    expected = {
        1191: (648, 0, 126, 1, "CONDITIONING"),
        1459: (648, 0, 721, 1, "CONDITIONING"),
        1381: (703, 0, 729, 0, "IMAGE"),
        1296: (121, 0, 702, 1, "AUDIO"),
    }
    for lid, exp in expected.items():
        got = tuple(links.get(lid, [None])[1:])
        if got != exp:
            raise SystemExit(f"link {lid} moved: got {got}, expected {exp}; re-map MC explicitly")

    # Existing links become the upstream halves of the inserted nodes.
    links[1191][3:5] = [99010, 0]   # conditioning switch -> MC
    links[1459][1:3] = [99010, 0]   # MC -> optional temporal guider
    links[1381][3:5] = [99011, 0]   # decoded frames -> trim
    links[1296][3:5] = [99011, 2]   # decoded audio -> trim
    by_id[126]["inputs"][1]["link"] = 1482
    by_id[729]["inputs"][0]["link"] = 1487
    by_id[702]["inputs"][1]["link"] = 1488

    def add_link(lid, source, source_slot, target, target_slot, typ):
        g["links"].append([lid, source, source_slot, target, target_slot, typ])

    add_link(1482, 99010, 0, 126, 1, "CONDITIONING")
    add_link(1483, 119, 0, 99010, 1, "VAE")
    add_link(1484, 682, 0, 99010, 2, "LATENT")
    add_link(1485, 99013, 0, 99010, 6, "LATENT")
    add_link(1486, 99010, 1, 99011, 1, "INT")
    add_link(1487, 99011, 0, 729, 0, "IMAGE")
    add_link(1488, 99011, 1, 702, 1, "AUDIO")
    add_link(1489, 125, 0, 99012, 0, "LATENT")

    # Keep origin-node output link lists in sync with the graph link table.
    by_id[119]["outputs"][0]["links"].append(1483)
    by_id[682]["outputs"][0]["links"].append(1484)
    by_id[125]["outputs"][0]["links"].append(1489)
    by_id[648]["outputs"][0]["links"] = [1191]

    common = {"flags": {}, "order": 0, "mode": 4, "properties": {},
              "color": "#263238", "bgcolor": "#37474f"}
    mc = {
        **common, "id": 99010, "type": "MiniMaxH3MotionContext",
        "pos": [-1032, 7068], "size": [432, 360],
        "inputs": [
            {"name": "conditioning", "type": "CONDITIONING", "link": 1191},
            {"name": "vae", "type": "VAE", "link": 1483},
            {"name": "latent", "type": "LATENT", "link": 1484},
            {"name": "context_length", "type": "COMBO", "widget": {"name": "context_length"}, "link": None},
            {"name": "audio_context_length", "type": "INT", "widget": {"name": "audio_context_length"}, "link": None},
            {"name": "context_frames", "type": "IMAGE", "shape": 7, "link": None},
            {"name": "context_latent", "type": "LATENT", "shape": 7, "link": 1485},
            {"name": "audio_vae", "type": "VAE", "shape": 7, "link": None},
            {"name": "context_audio", "type": "AUDIO", "shape": 7, "link": None},
        ],
        "outputs": [
            {"name": "conditioning", "type": "CONDITIONING", "links": [1482, 1459]},
            {"name": "trim_frames", "type": "INT", "links": [1486]},
        ],
        "widgets_values": ["22", 22],
        "title": "Motion Context — enable for clips 2+",
    }
    trim = {
        **common, "id": 99011, "type": "MiniMaxH3MotionContextTrim",
        "pos": [-564, 7068], "size": [432, 252],
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": 1381},
            {"name": "trim_frames", "type": "INT", "widget": {"name": "trim_frames"}, "link": 1486},
            {"name": "audio", "type": "AUDIO", "shape": 7, "link": 1296},
            {"name": "fps", "type": "FLOAT", "shape": 7, "widget": {"name": "fps"}, "link": None},
            {"name": "match_tail", "type": "BOOLEAN", "shape": 7, "widget": {"name": "match_tail"}, "link": None},
        ],
        "outputs": [
            {"name": "images", "type": "IMAGE", "links": [1487]},
            {"name": "audio", "type": "AUDIO", "links": [1488]},
        ],
        "widgets_values": [0, 24.0, True],
        "title": "Trim pinned head + keep AV sync",
    }
    save = {
        **common, "id": 99012, "type": "MiniMaxH3MotionContextSaveLatent",
        "pos": [-1500, 7248], "size": [432, 180],
        "inputs": [
            {"name": "latent", "type": "LATENT", "link": 1489},
            {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}, "link": None},
            {"name": "clip_index", "type": "INT", "widget": {"name": "clip_index"}, "link": None},
        ],
        "outputs": [{"name": "latent_path", "type": "STRING", "links": None}],
        "widgets_values": ["h3_context/macmax_chain/clip", 1],
        "title": "Save THIS clip AV latent",
    }
    load = {
        **common, "id": 99013, "type": "MiniMaxH3MotionContextLoadLatent",
        "pos": [-1500, 7068], "size": [432, 156],
        "inputs": [
            {"name": "latent_path", "type": "STRING", "widget": {"name": "latent_path"}, "link": None},
            {"name": "clip_index", "type": "INT", "widget": {"name": "clip_index"}, "link": None},
        ],
        "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1485]}],
        "widgets_values": ["h3_context/macmax_chain", 1],
        "title": "Load clip to CONTINUE FROM",
    }
    note = {
        "id": 99014, "type": "MarkdownNote", "pos": [-1500, 7464], "size": [1368, 264],
        "flags": {}, "order": 0, "mode": 0, "inputs": [], "outputs": [],
        "title": "MOTION CONTEXT — exact sequence", "properties": {},
        "widgets_values": [("## Motion Context (native AV latent; no post compositing)\n\n"
                            "**Clip 1:** enable only **Save**, set Save index `1`. Queue.\n\n"
                            "**Clip 2+:** enable **Load + Motion Context + Trim + Save**. Set Load "
                            "to the accepted previous clip and Save to the current clip: `1 -> 2`, "
                            "then `2 -> 3`. Re-rolls overwrite their own numbered slot safely.\n\n"
                            "Keep resolution and FPS identical across the chain. The default 22-frame "
                            "window is removed from both picture and sound; continuation clips are "
                            "therefore exactly 22 frames shorter. That is the mechanical proof MC ran.")],
        "color": "#173b35", "bgcolor": "#0d211e",
    }
    g["nodes"].extend([mc, trim, save, load, note])
    g.setdefault("groups", []).append({
        "id": len(g.get("groups", [])) + 1,
        "title": "10. MOTION CONTEXT — optional continuous chain",
        "bounding": [-1512, 7008, 1392, 744], "color": "#2f9292", "font_size": 24,
        "flags": {}})
    g["last_node_id"] = max(g.get("last_node_id", 0), 99014)
    g["last_link_id"] = max(g.get("last_link_id", 0), 1489)


def configure_recipe(g, local):
    """Apply the measured Mac defaults without further topology changes."""
    by_id = {n["id"]: n for n in g["nodes"]}

    # Upstream ships one of the author's private reference files active, which makes a fresh
    # install fail validation immediately. Keep all four slots visible but bypassed until the
    # user selects a real local image. With no refs the conditioning node can still render;
    # enabling one or more slots turns the same graph into R2V.
    for node in g["nodes"]:
        if node.get("type") == "LoadImageCrop":
            node["mode"] = 4

    # FL2VA is the better general-purpose checkpoint for this R2V node on our Mac. Keep the
    # Ref2VA loader in place as a one-click alternative; the rgthree Any Switch selects the
    # only loader that is not bypassed.
    by_id[620]["mode"] = 4
    by_id[646]["mode"] = 0

    # Local R2V testing found the 8-step design point and LoRA strength 1.0 on the useful
    # quality/time plateau. The local LoRA is stored at models/loras/, not MINIMAX/.
    lora = by_id[674]["widgets_values"][2]
    lora["strength"] = 1.0
    if local:
        lora["lora"] = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
    if "widgets_values_named" in by_id[674]:
        by_id[674]["widgets_values_named"]["lora_1"] = dict(lora)

    # The viewing/default lane is deliberately 0.5 MP. Paying for a 1 MP Mac render before a
    # shot is approved is a poor trade. Resolution remains a visible dial in the workflow.
    by_id[115]["widgets_values"][1] = 0.5
    if "widgets_values_named" in by_id[115]:
        by_id[115]["widgets_values_named"]["megapixels"] = 0.5

    # Spectrum is the acceleration node that actually runs on Apple Silicon. PlagueKind SLA is
    # CUDA/Triton-side and is intentionally not inserted here. Degree 1 / warmup 1 is the tested
    # conservative Mac setting; upstream's degree 4 / warmup 5 was never our local recipe.
    spectrum = by_id[655]
    spectrum["mode"] = 0
    spectrum["widgets_values"][2] = 1
    spectrum["widgets_values"][6] = 1
    if "widgets_values_named" in spectrum:
        spectrum["widgets_values_named"]["degree"] = 1
        spectrum["widgets_values_named"]["warmup_steps"] = 1

    recipe_note = ("## Current Mac recipe — controls, not folklore\n\n"
                   "**Before R2V:** choose a local file in one or more `<Picture N>` loaders, "
                   "then un-bypass those slots. All four ship bypassed so the author's missing "
                   "private image cannot break a fresh install.\n\n"
                   "**Default / viewing:** FL2VA Q5 GGUF, Turbo 8-step LoRA at 1.0, "
                   "8 steps, 0.5 MP, `er_sde` + `beta`, Spectrum ON at degree 1 / warmup 1.\n\n"
                   "**Detail check:** same recipe, but bypass Spectrum. This costs more and is "
                   "the first comparison to make when texture or identity looks too smooth.\n\n"
                   "**True base-quality experiment:** disable the Turbo LoRA, use 20-25 steps, "
                   "and keep Spectrum degree 1. This is dramatically slower on a Mac; do not "
                   "confuse it with the normal local viewing lane.\n\n"
                   "**Model:** FL2VA ships active because it behaved better through the R2V "
                   "conditioning path. Ref2VA remains beside it as an explicit A/B switch.\n\n"
                   "**SLA:** not present here. PlagueKind SLA is the pod/CUDA lane; Spectrum is "
                   "the supported Mac accelerator. Do not enable EasyCache with Spectrum.\n\n"
                   "**Upscaling:** VFI and temporal de-rope are not spatial 2x upscalers. This "
                   "graph deliberately does not label them as the Foxy latent 2x pass.\n")
    g["nodes"].append({
        "id": 99002, "type": "MarkdownNote", "pos": [-2904, 5036], "size": [444, 492],
        "flags": {}, "order": 0, "mode": 0, "inputs": [], "outputs": [],
        "title": "CURRENT MAC RECIPE — start here", "properties": {},
        "widgets_values": [recipe_note], "color": "#173b35", "bgcolor": "#0d211e"})
    g["last_node_id"] = max(g.get("last_node_id", 0), 99002)


def build(src, prefix, vprefix, out_path, label, local=False):
    with open(src) as f:
        g = json.load(f)
    by_id = {n["id"]: n for n in g["nodes"]}
    for nid, (old_cls, old_w, new_cls, new_w) in SWAPS.items():
        n = by_id.get(nid)
        if n is None:
            raise SystemExit(f"node {nid} is gone from {os.path.basename(src)} — re-derive the SWAPS table")
        if n["type"] != old_cls:
            raise SystemExit(f"node {nid} is {n['type']}, expected {old_cls} — upstream changed, STOP")
        if list(n.get("widgets_values") or []) != old_w:
            raise SystemExit(f"node {nid} widgets are {n.get('widgets_values')}, expected {old_w}.\n"
                             f"  Upstream layout moved. Fix the SWAPS table rather than letting values shift.")
        n["type"] = new_cls
        # REPLACE the list outright, never edit in place: the GGUF loaders have fewer widgets and
        # a leftover slot is what shifts every later value.
        n["widgets_values"] = [w.replace("VPFX", vprefix).replace("PFX", prefix)
                               if isinstance(w, str) else w for w in new_w]
        n["widgets_values_named"] = dict(zip(NAMED[new_cls], n["widgets_values"]))
        p = n.setdefault("properties", {})
        p["Node name for S&R"] = new_cls
        p.pop("models", None)          # stale download hints point at the CUDA files
        # a node's declared input slots must match the new class too, or the frontend rebuilds
        # them from the old one and the link ids no longer line up
        keep = {"model", "clip", "vae"}
        n["inputs"] = [i for i in (n.get("inputs") or []) if i.get("name") in keep]

    add_motion_context(g)
    configure_recipe(g, local)

    note = ("## Apple Silicon port of FOXYDIT v20\n\n"
            "Derived by `build_mac_v20.py`, not hand-edited. Five loader nodes differ from the pod "
            "original:\n\n"
            "- both DiT loaders -> **UnetLoaderGGUF** (Q5_K_M)\n"
            "- text encoder -> **CLIPLoaderGGUF** (qwen3vl-32B Q4_K_M)\n"
            "- video VAE -> **fp16** (the int8_convrot one is CUDA-side)\n"
            "- audio VAE unchanged in format, path only\n"
            "- optional native-AV **Motion Context** continuation block added, bypassed by default\n\n"
            "int8_convrot *can* load on Apple Silicon, but it has no LoRA patch path here and "
            "OOMs, which rules out the 8-step turbo LoRA. GGUF keeps that option open.\n\n"
            "`SolAttnPatch` and `LoadAudioUI` show red without their packs. Both ship **bypassed**, "
            "so that is cosmetic. SolAttn is triton/CUDA and will never run here — leave it "
            "bypassed.\n")
    g["nodes"].append({
        "id": 99001, "type": "MarkdownNote", "pos": [-2904, 4700], "size": [444, 300],
        "flags": {}, "order": 0, "mode": 0, "inputs": [], "outputs": [],
        "title": "READ ME — Apple Silicon port",
        "properties": {}, "widgets_values": [note], "color": "#222", "bgcolor": "#000"})
    g["last_node_id"] = max(g.get("last_node_id", 0), 99001)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(g, f, indent=1)
    print(f"{label:8s} -> {out_path}")
    for nid in SWAPS:
        n = {x["id"]: x for x in g["nodes"]}[nid]
        print(f"           {nid:>4} {n['type']:16s} {n['widgets_values']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=DEFAULT_SRC)
    parser.add_argument("--install", metavar="WORKFLOW_DIR",
                        help="also install the local build under a stable, logical filename")
    args = parser.parse_args()

    build(args.source, "", "", PUB, "PUBLIC")
    build(args.source, "_h3/", "_h3/vae/", LOC, "LOCAL", local=True)
    if args.install:
        os.makedirs(args.install, exist_ok=True)
        installed = os.path.join(args.install, "MacMax_H3_R2V_CURRENT.json")
        shutil.copy2(LOC, installed)
        print(f"INSTALLED -> {installed}")
    print("\nboth derived from", os.path.basename(args.source))


if __name__ == "__main__":
    main()
