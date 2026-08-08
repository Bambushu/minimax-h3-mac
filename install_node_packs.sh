#!/bin/zsh
# Custom node packs for the three MiniMax H3 Apple Silicon workflows.
#
#   MacMax   needs 2 packs: ComfyUI-GGUF, ComfyUI-AppleSilicon-FP8.
#   Foxydit  needs those 2 plus 6 more.
#   DaSiWa   needs those 2 plus 3 more.
#
# ResolutionSelector is ComfyUI CORE (comfy_extras/nodes_resolution.py). No Resolution-Master
# or KJNodes pack is needed for it.
#
# Pass a target: ./install_node_packs.sh macmax | foxydit | dasiwa | all   (default: all)
#
# DO NOT RUN THIS WHILE A RENDER IS IN FLIGHT. It writes into the venv and the custom_nodes
# dir, and a half-installed pack breaks ComfyUI on next start.
set -e
TARGET="${1:-all}"
COMFY="${COMFY_ROOT:-$HOME/ComfyUI-h3}"
CN=$COMFY/custom_nodes
PY=$COMFY/venv/bin/python
[[ -d $CN ]] || { echo "No custom_nodes at $CN. Set COMFY_ROOT to your ComfyUI checkout."; exit 1 }
[[ -x $PY ]] || { echo "No venv python at $PY. Set COMFY_ROOT to your ComfyUI checkout."; exit 1 }
cd $CN

clone(){ [[ -d "$(basename $1 .git)" ]] && echo "have $(basename $1 .git)" || git clone --depth 1 "$1"; }

PACKS=()

# --- REQUIRED BY ALL THREE ------------------------------------------------------------
# GGUF: the stock NVFP4-AWQ text encoder is CUDA-only, every workflow here loads the GGUF one.
# AppleSilicon-FP8: the int8_convrot checkpoint will not load without it. Launch ComfyUI with
# ASFP8_INT8_EXT=1.
clone https://github.com/city96/ComfyUI-GGUF.git
clone https://github.com/pawel-mazurkiewicz/ComfyUI-AppleSilicon-FP8.git
PACKS+=(ComfyUI-GGUF ComfyUI-AppleSilicon-FP8)
# ComfyUI-GGUF reports IMPORT FAILED without this exact version
$PY -m pip install -q "gguf==0.18.0" || echo "  WARN: gguf==0.18.0 failed to install"

# Spectrum: BOTH workflows now ship it ENABLED. It forecasts skipped sampling steps from a
# fitted curve instead of reusing a cached state, so fast-changing detail like a mouth
# survives. Measured on MPS at 0.6 MP/5s/20 steps, same seed: 34:27 vs 47:21 uncached (-27%),
# 8 of 20 steps forecast, faces intact. EasyCache is faster (31:16) but visibly smears mouths
# and teeth, so it ships BYPASSED in both. Never enable both at once.
# PINNED to v0.1.5: Spectrum v0.1.6+ targets a LATER ComfyUI that changed H3's native
# sampling/audio path. On the ComfyUI 0.30.0 this pack is measured on, v0.1.5 is the matching
# version (it also carries an Apple MPS fix). If you move to a newer ComfyUI, update Spectrum
# to latest instead - and know that none of this pack's numbers were measured there.
clone https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git
( cd $CN/ComfyUI-Spectrum-MiniMax-H3 && git fetch -q --depth 1 origin tag v0.1.5 2>/dev/null && git -c advice.detachedHead=false checkout -q v0.1.5 || echo "  WARN: could not pin Spectrum v0.1.5, using cloned HEAD" )
PACKS+=(ComfyUI-Spectrum-MiniMax-H3)

if [[ $TARGET == foxydit || $TARGET == all ]]; then
  # --- FOXYDIT (filmmaking rig) -------------------------------------------------------
  clone https://github.com/rgthree/rgthree-comfy.git
  clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
  clone https://github.com/yolain/ComfyUI-Easy-Use.git
  clone https://github.com/kijai/ComfyUI-KJNodes.git
  clone https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git
  # Spectrum is installed above, for every target.
  PACKS+=(rgthree-comfy ComfyUI-VideoHelperSuite ComfyUI-Easy-Use ComfyUI-KJNodes
          ComfyUI-Frame-Interpolation)
fi

if [[ $TARGET == dasiwa || $TARGET == all ]]; then
  # --- DASIWA (director) --------------------------------------------------------------
  clone https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes.git
  clone https://github.com/rgthree/rgthree-comfy.git
  clone https://github.com/kijai/ComfyUI-KJNodes.git
  PACKS+=(ComfyUI-DaSiWa-Nodes rgthree-comfy ComfyUI-KJNodes)
fi

# requirements, minus the NVIDIA-only lines. nvidia-vfx is imported by NOTHING in the DaSiWa
# pack (only its RTX upscaler node needs it) and will fail to install on Mac. Same for triton,
# sageattention, flash-attn and xformers, none of which have Apple Silicon builds.
for d in ${(u)PACKS}; do
  if [[ -f $CN/$d/requirements.txt ]]; then
    grep -viE '^(nvidia|triton|sageattention|flash-attn|xformers)' $CN/$d/requirements.txt \
      > "${TMPDIR:-/tmp}/req_$d.txt" || true
    echo "installing $d requirements (NVIDIA/triton lines stripped)"
    $PY -m pip install -q -r "${TMPDIR:-/tmp}/req_$d.txt" || echo "  WARN: some requirements failed for $d"
  fi
done

cat <<'EOF'

Done. Restart ComfyUI with:
  ASFP8_INT8_EXT=1 python main.py --port 8288 --reserve-vram 10 --cache-none --disable-smart-memory

Then load a workflow. On first load the model loaders may show red: these files use bare
stock filenames, so if your models live in subfolders you re-pick them once. That is expected.

These node types stay unresolved on Apple Silicon and ship BYPASSED on purpose. Do not enable
them: SolAttnPatch, MiniMaxH3MemoryEfficientSageAttentionPatch, RIFEInterpolation, LoadAudioUI.
EOF
