#!/bin/zsh
# Custom node packs for the MiniMax H3 Apple Silicon workflow (MacMax_MiniMaxH3_AppleSilicon.json).
#
#   Base: ComfyUI-GGUF, ComfyUI-AppleSilicon-FP8.
#   Turbo: ComfyUI-PlagueKind-Nodes + comfyui-obvpm.
#   Optional (2): ComfyUI-H3-Motion-Context (chaining), ComfyUI-ClipProj (smaller text encoder).
#
# ResolutionSelector is ComfyUI CORE (comfy_extras/nodes_resolution.py). No extra pack for it.
#
# Pass a target: ./install_node_packs.sh macmax | turbo | extras | all   (default: turbo)
#
# DO NOT RUN THIS WHILE A RENDER IS IN FLIGHT. It writes into the venv and the custom_nodes
# dir, and a half-installed pack breaks ComfyUI on next start.
set -e
TARGET="${1:-turbo}"
case "$TARGET" in
  macmax|turbo|extras|all) ;;
  *) echo "Usage: $0 macmax|turbo|extras|all" >&2; exit 2 ;;
esac
COMFY="${COMFY_ROOT:-$HOME/ComfyUI-h3}"
CN=$COMFY/custom_nodes
PY=$COMFY/venv/bin/python
[[ -d $CN ]] || { echo "No custom_nodes at $CN. Set COMFY_ROOT to your ComfyUI checkout."; exit 1 }
[[ -x $PY ]] || { echo "No venv python at $PY. Set COMFY_ROOT to your ComfyUI checkout."; exit 1 }
cd $CN

clone(){ [[ -d "$(basename $1 .git)" ]] && echo "have $(basename $1 .git)" || git clone --depth 1 "$1"; }

PACKS=()

# --- REQUIRED --------------------------------------------------------------------
# GGUF: the stock NVFP4-AWQ text encoder is CUDA-only; this workflow loads the GGUF one.
# AppleSilicon-FP8: the int8_convrot checkpoint will not load without it. Launch ComfyUI with
# ASFP8_INT8_EXT=1.
clone https://github.com/city96/ComfyUI-GGUF.git
clone https://github.com/pawel-mazurkiewicz/ComfyUI-AppleSilicon-FP8.git
PACKS+=(ComfyUI-GGUF ComfyUI-AppleSilicon-FP8)
# ComfyUI-GGUF reports IMPORT FAILED without this exact version
$PY -m pip install -q "gguf==0.18.0"

if [[ $TARGET == extras || $TARGET == all ]]; then
  # --- OPTIONAL: chaining + the smaller text encoder -----------------------------------
  # Both ship BYPASSED in the workflow, so neither is needed to render. Without the packs
  # their node types show red, which is cosmetic while bypassed. Delete the nodes if you
  # would rather not see it.
  clone https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context.git
  clone https://github.com/nicolab28/ComfyUI-ClipProj.git
  PACKS+=(ComfyUI-H3-Motion-Context ComfyUI-ClipProj)
fi

# Turbo uses the same node-pack revisions as the local compatibility test.
if [[ $TARGET == turbo || $TARGET == extras || $TARGET == all ]]; then
  clone https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes.git
  clone https://github.com/obvpm/comfyui-obvpm.git
  ( cd "$CN/ComfyUI-PlagueKind-Nodes" && git fetch --depth 1 origin aaec055cd642b3292df18e69824c012d345ebfe8 && git checkout --detach aaec055cd642b3292df18e69824c012d345ebfe8 )
  ( cd "$CN/comfyui-obvpm" && git fetch --depth 1 origin 704fe3edea3e69f113219319c87bdf4c74abc5cd && git checkout --detach 704fe3edea3e69f113219319c87bdf4c74abc5cd )
  PACKS+=(ComfyUI-PlagueKind-Nodes comfyui-obvpm)
fi

# Install each pack's requirements, minus the NVIDIA-only lines (they fail on Mac; same for
# triton, sageattention, flash-attn and xformers, none of which have Apple Silicon builds).
for d in ${(u)PACKS}; do
  if [[ -f $CN/$d/requirements.txt ]]; then
    grep -viE '^(nvidia|triton|sageattention|flash-attn|xformers)' $CN/$d/requirements.txt \
      > "${TMPDIR:-/tmp}/req_$d.txt" || true
    echo "installing $d requirements (NVIDIA/triton lines stripped)"
    $PY -m pip install -q -r "${TMPDIR:-/tmp}/req_$d.txt"
  fi
done

cat <<'EOF'

Done. Restart ComfyUI with:
  ASFP8_INT8_EXT=1 python main.py --port 8288 --reserve-vram 10 --cache-none --disable-smart-memory

Then load MacMax_MiniMaxH3_AppleSilicon.json. Its loaders use bare stock filenames, so re-pick
them once if your models live in subfolders.

Do not use Spectrum or EasyCache with turbo LoRAs. Motion Context and ClipProj require extras; their blocks
also ship bypassed. See the workflow notes before enabling optional blocks.
EOF
