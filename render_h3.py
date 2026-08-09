"""Run the author's shipped MiniMax H3 workflow on the local ComfyUI-h3 (MPS) and time it.

Starts from h3_api.json (the author's graph, exported to API format by the ComfyUI
frontend), patches only: model filenames, canvas, steps, and t2va-vs-fl2va.

Usage:
  render_h3.py --steps 2 --tag smoke
  render_h3.py --steps 25 --tag full
"""
import argparse, json, os, time, urllib.request, urllib.error, uuid, sys

SERVER = "127.0.0.1:8288"
# resolve next to this script so the release is self-contained; fall back to the dev copy
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h3_api.json")
if not os.path.exists(BASE):
    BASE = os.path.expanduser("~/h3-demos/local/h3_api.json")

# resolved against the live /object_info -- ComfyUI registers these with a folder
# prefix (e.g. "_h3/...") that depends on extra_model_paths layout, so never hardcode.
# DEFAULT DiT = Comfy-Org pruned int8_convrot (what the official templates load).
# The GGUF Q3_K_M was deleted 2026-08-05: pruned is ~20B @ 8-bit vs 33B @ 3.4-bit for
# the same footprint, loads 20.0 GB, and samples ~16% FASTER (159 vs 188 s/it) because
# pruning removes FLOPs outright while quantization only changes how each FLOP is fed.
# Must name the TASK too: "pruned_int8_convrot" alone also matches the ref2va (R2V)
# checkpoint, so the default was only picking the right model by list ordering.
DEFAULT_DIT = "fl2va_pruned_int8_convrot"
WANT = {
    # Q4_K_M is the DEFAULT and Q2_K is gone: Q2_K's VISION tower is 2-bit and
    # destroys keyframe conditioning (image-cond cosine vs Q4_K_M = 0.30, while
    # text-only = 0.99). Text-only prompts never touch it, which is why t2v looked fine.
    "clip":  ("CLIPLoaderGGUF", "clip_name", "qwen3vl-32B-MiniMax-H3-Q4_K_M"),
    "vvae":  ("VAELoader", "vae_name", "minimax_h3_video_vae"),
    "avae":  ("VAELoader", "vae_name", "minimax_h3_audio_vae"),
}


def post(path, payload):
    req = urllib.request.Request(f"http://{SERVER}{path}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(f"http://{SERVER}{path}", timeout=60) as r:
        return json.load(r)


def resolve_models(te=None):
    out = {}
    want = dict(WANT)
    if te:  # override the quant baked into the default needle
        n, f, s = want["clip"]
        base = s.rsplit("-Q", 1)[0] if "-Q" in s else s
        want["clip"] = (n, f, f"{base}-{te}")
    for key, (node, field, needle) in want.items():
        opts = get(f"/object_info/{node}")[node]["input"]["required"][field][0]
        hits = [o for o in opts if needle in o]
        if not hits:
            raise SystemExit(f"no {key} file matching {needle!r} in {node}.{field}: {opts}")
        out[key] = hits[0]
    return out


def build(args):
    g = json.load(open(BASE))
    m = resolve_models(args.te)
    print("resolved models:", json.dumps(m, indent=1))
    if True:
        # .safetensors DiT (e.g. Comfy-Org pruned int8_convrot) loads through the CORE
        # UNETLoader, not city96's GGUF loader. Same node id so every downstream link
        # (BasicGuider, BasicScheduler) keeps working untouched.
        opts = get("/object_info/UNETLoader")["UNETLoader"]["input"]["required"]["unet_name"][0]
        want_dit = args.dit or DEFAULT_DIT
        hits = [o for o in opts if want_dit in o]
        if not hits:
            raise SystemExit(f"no DiT matching {want_dit!r} in UNETLoader: {opts}")
        # Refuse to guess. The turbo-merged checkpoint used to be named
        # ..._pruned_int8_convrot_turbo, so the DEFAULT substring matched TWO files and
        # hits[0] silently decided which model every render used. Never again.
        if len(hits) > 1:
            raise SystemExit(f"{want_dit!r} is AMBIGUOUS - matches {hits}. "
                             "Pass a --dit substring that picks exactly one.")
        print("DiT (safetensors):", hits[0])
        g["105:119"] = {"class_type": "UNETLoader",
                        "inputs": {"unet_name": hits[0], "weight_dtype": "default"},
                        "_meta": {"title": "UNETLoader"}}

    g["105:120"]["inputs"]["clip_name"] = m["clip"]
    g["105:11"]["inputs"]["vae_name"] = m["vvae"]
    g["105:24"]["inputs"]["vae_name"] = m["avae"]
    # the author's saved workflow has type='wan' here, which is stale; H3's text
    # encoder needs the minimax CLIPType or the conditioning is built wrong.
    g["105:120"]["inputs"]["type"] = "minimax"
    if args.cond_aug is not None:
        # insert MiniMaxH3CondNoiseAug between the conditioning and BasicGuider
        g["130"] = {"class_type": "MiniMaxH3CondNoiseAug",
                    "inputs": {"conditioning": ["105:104", 0],
                               "visual_cond_noise_aug": float(args.cond_aug),
                               "audio_cond_noise_aug": 1.0},
                    "_meta": {"title": "CondNoiseAug"}}
        g["105:16"]["inputs"]["conditioning"] = ["130", 0]
    # --- optional sigma shift (the OFFICIAL Turbo workflow uses 12/6, not the 12/3 default) ---
    _shift_src = None
    # --- optional Turbo LoRA (4-step distill for the pruned/curve-form ckpt) ---
    if args.lora:
        opts = get("/object_info/LoraLoaderModelOnly")["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0]
        hits = [o for o in opts if args.lora in o]
        if not hits:
            raise SystemExit(f"no LoRA matching {args.lora!r}: {opts}")
        print("LoRA:", hits[0], "strength", args.lora_strength)
        g["139"] = {"class_type": "LoraLoaderModelOnly",
                    "inputs": {"model": ["105:119", 0], "lora_name": hits[0],
                               "strength_model": float(args.lora_strength)},
                    "_meta": {"title": "TurboLoRA"}}
        g["105:16"]["inputs"]["model"] = ["139", 0]
        g["105:9"]["inputs"]["model"] = ["139", 0]
        _shift_src = ["139", 0]

    if args.shift_audio is not None or args.shift_video is not None:
        g["138"] = {"class_type": "MiniMaxH3SigmaShift",
                    "inputs": {"model": _shift_src or ["105:119", 0],
                               "shift_video": float(args.shift_video if args.shift_video is not None else 12.0),
                               "shift_audio": float(args.shift_audio if args.shift_audio is not None else 3.0)},
                    "_meta": {"title": "SigmaShift"}}
        g["105:16"]["inputs"]["model"] = ["138", 0]
        g["105:9"]["inputs"]["model"] = ["138", 0]

    # --- optional model patches: EasyCache / Spectrum (both pure torch, MPS-safe) ---
    # Chain: UNETLoader -> [easycache] -> [spectrum] -> BasicGuider + BasicScheduler
    src = g["105:16"]["inputs"]["model"]
    base_src = list(src)
    if args.easycache is not None:
        g["140"] = {"class_type": "EasyCache",
                    "inputs": {"model": src, "reuse_threshold": float(args.easycache),
                               "start_percent": 0.15, "end_percent": 0.95, "verbose": True},
                    "_meta": {"title": "EasyCache"}}
        src = ["140", 0]
    if args.spectrum:
        # v0.2.3 dials, matching the shipped workflows. audio_blend_weight 0.0 and the
        # offline replay pass are what keep H3's audio clean: audio and video share ONE
        # transformer sequence, so a forecast error in video otherwise reaches audio
        # through joint attention (rough sound, tripped or doubled syllables).
        g["141"] = {"class_type": "SpectrumApplyMiniMaxH3",
                    "inputs": {"model": src, "enabled": True, "blend_weight": 0.5,
                               "degree": 1, "ridge_lambda": 0.1, "window_size": 2.0,
                               "flex_window": 0.75, "warmup_steps": 1,
                               "tail_actual_steps": 1, "max_history": 8, "debug": False,
                               "offline_smoothing_replay": True,
                               "audio_blend_weight": 0.0},
                    "_meta": {"title": "Spectrum"}}
        src = ["141", 0]
    if src != base_src:
        g["105:16"]["inputs"]["model"] = src
        g["105:9"]["inputs"]["model"] = src
    g["105:9"]["inputs"]["steps"] = args.steps
    g["115"]["inputs"]["aspect_ratio"] = args.aspect
    g["115"]["inputs"]["megapixels"] = args.megapixels
    g["105:111"]["inputs"]["value"] = args.seconds
    g["92"]["inputs"]["filename_prefix"] = f"video/h3_{args.tag}"
    if args.prompt:
        g["105:104"]["inputs"]["prompt"] = args.prompt
    # No keyframe supplied means there is nothing to condition on, so this IS t2v whether or
    # not --t2v was passed. Without this, the branch below deletes the ResolutionSelector (115)
    # and then never rewires width/height, leaving them dangling at ["115", 0] / ["115", 1].
    if not args.t2v and not args.first_frame and not args.last_frame:
        print("no --first-frame/--last-frame given: rendering t2v")
        args.t2v = True

    if args.t2v:
        # no keyframes on disk -> drop the fl2va image path entirely
        for k in ("first_frame", "last_frame"):
            g["105:104"]["inputs"].pop(k, None)
        for n in ("121", "123", "124", "125"):
            g.pop(n, None)
        return g

    # fl2va / i2v, wired like the OFFICIAL video_minimax_h3_i2v.json template:
    # the CANVAS IS DERIVED FROM THE IMAGE (LoadImage -> GetImageSize -> width/height)
    # instead of being set independently by ResolutionSelector. Also drop the author's
    # ImageResizeKJv2 nodes entirely -- MiniMaxH3ImageToVideo does its own
    # _resize(first_frame, width, height, "disabled") internally, so they were a
    # redundant extra resample (and his default was 512x512 + CUDA-only nvidia_rtx_vsr).
    # No ImageScaleToTotalPixels either: the keyframe is already at the previous clip's
    # canvas, and rescaling would drift the chained clip off that canvas.
    for n in ("123", "124", "115"):
        g.pop(n, None)
    if args.first_frame:
        g["121"]["inputs"]["image"] = args.first_frame
        g["120"] = {"class_type": "GetImageSize",
                    "inputs": {"image": ["121", 0]},
                    "_meta": {"title": "GetImageSize"}}
        g["105:104"]["inputs"]["first_frame"] = ["121", 0]
        g["105:104"]["inputs"]["width"] = ["120", 0]
        g["105:104"]["inputs"]["height"] = ["120", 1]
    else:
        g["105:104"]["inputs"].pop("first_frame", None)
        g.pop("121", None)
    if args.last_frame:
        g["125"]["inputs"]["image"] = args.last_frame
        g["105:104"]["inputs"]["last_frame"] = ["125", 0]
        if "120" not in g:   # last-frame-only still needs a canvas source
            g["120"] = {"class_type": "GetImageSize",
                        "inputs": {"image": ["125", 0]},
                        "_meta": {"title": "GetImageSize"}}
            g["105:104"]["inputs"]["width"] = ["120", 0]
            g["105:104"]["inputs"]["height"] = ["120", 1]
    else:
        g["105:104"]["inputs"].pop("last_frame", None)
        g.pop("125", None)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--aspect", default="9:16 (Portrait Widescreen)")  # matches prompt_vertical.txt
    ap.add_argument("--megapixels", type=float, default=0.4)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--t2v", action="store_true", help="drop first/last frame inputs")
    ap.add_argument("--first-frame", default=None, help="filename in ComfyUI input/ dir")
    ap.add_argument("--last-frame", default=None, help="filename in ComfyUI input/ dir")
    ap.add_argument("--shift-video", type=float, default=None, help="sigma shift video (default 12)")
    ap.add_argument("--shift-audio", type=float, default=None, help="sigma shift audio (default 3; OFFICIAL turbo wf uses 6)")
    ap.add_argument("--lora", default=None, help="Turbo LoRA substring, e.g. turbo_4step_ckpt500")
    ap.add_argument("--lora-strength", type=float, default=1.0)
    ap.add_argument("--easycache", type=float, default=None, help="EasyCache reuse_threshold, e.g. 0.2")
    ap.add_argument("--spectrum", action="store_true", help="apply SpectrumApplyMiniMaxH3")
    ap.add_argument("--cond-aug", type=float, default=None, help="visual_cond_noise_aug (default 0.999); <1 = noisier anchor")
    ap.add_argument("--dit", default=None, help=f"safetensors DiT substring; default {DEFAULT_DIT}")
    ap.add_argument("--dump-graph", default=None, help="write the API-format graph to this path and exit")
    ap.add_argument("--te", default=None, help="override TE quant; default Q4_K_M")
    args = ap.parse_args()

    g = build(args)
    if args.dump_graph:
        # Export the EXACT graph this script submits, so a published workflow cannot drift
        # from the recipe that was actually measured.
        with open(args.dump_graph, "w") as fh:
            json.dump(g, fh, indent=2)
        print("wrote API graph:", args.dump_graph)
        return
    cid = str(uuid.uuid4())
    t0 = time.time()
    try:
        res = post("/prompt", {"prompt": g, "client_id": cid})
    except urllib.error.HTTPError as e:
        print("PROMPT REJECTED:", e.read().decode()[:4000])
        sys.exit(1)
    pid = res["prompt_id"]
    print(f"queued {pid} steps={args.steps} {args.aspect} {args.megapixels}MP {args.seconds}s")

    last = ""
    while True:
        time.sleep(10)
        h = get(f"/history/{pid}")
        if pid in h:
            break
        q = get("/queue")
        running = q.get("queue_running") or []
        msg = f"  [{time.time()-t0:6.0f}s] running={len(running)} queued={len(q.get('queue_pending') or [])}"
        if msg[:20] != last[:20]:
            print(msg, flush=True)
        last = msg

    dt = time.time() - t0
    entry = h[pid]
    status = entry.get("status", {})
    print(f"\n=== done in {dt/60:.1f} min ({dt:.0f}s) -> {dt/args.steps:.1f}s/step incl load+decode ===")
    print("status:", status.get("status_str"), "completed:", status.get("completed"))
    for nid, out in (entry.get("outputs") or {}).items():
        print(nid, json.dumps(out)[:400])
    if not status.get("completed"):
        for m in status.get("messages", [])[-6:]:
            print("MSG", json.dumps(m)[:600])


if __name__ == "__main__":
    main()
