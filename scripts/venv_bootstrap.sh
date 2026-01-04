#!/usr/bin/env bash
set -euo pipefail

PY311=${PY311:-/workspace/python311/bin/python3.11}
VENV=${VENV:-/mnt/data/venv}

echo "🟦 Using Python: $PY311"
if [[ ! -x "$PY311" ]]; then
  echo "❌ $PY311 not found"; exit 1
fi

echo "🟦 Creating venv at $VENV ..."
"$PY311" -m venv "$VENV"
source "$VENV/bin/activate"

python -m pip install -U pip setuptools wheel

# Make sure pins match constraints
sed -i -E 's/^transformers==[0-9.]+/transformers==4.41.0/' requirements_clean.txt || true
grep -q '^tokenizers==' requirements_clean.txt && \
  sed -i -E 's/^tokenizers==[0-9.]+/tokenizers==0.19.1/' requirements_clean.txt || \
  echo 'tokenizers==0.19.1' >> requirements_clean.txt

# Install CUDA 11.8 torch first (matches constraints)
pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu118 \
  torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0+cu118

# Then the rest with constraints
pip install --no-cache-dir -c constraints.txt -r requirements_clean.txt

# Hard pins some tools like to bump
pip install --no-cache-dir "numpy==1.26.4" "protobuf==4.25.3" "typing_extensions>=4.14.0" "tokenizers<0.20"

# Try CUDA llama-cpp; fallback to CPU if it fails
if ! CMAKE_ARGS="-DGGML_CUDA=on -DGGML_CUDA_F16=1" pip install --no-cache-dir --force-reinstall llama-cpp-python; then
  pip install --no-cache-dir --force-reinstall llama-cpp-python
fi

python - <<'PY'
import sys, numpy, typing_extensions as te
print("✅ Python", sys.version.split()[0])
print("✅ NumPy", numpy.__version__)
print("✅ typing_extensions", getattr(te, "__version__", "unknown"))
import transformers, tokenizers, torch, llama_cpp
print("✅ transformers", transformers.__version__)
print("✅ tokenizers", tokenizers.__version__)
print("✅ torch", torch.__version__, "CUDA:", torch.cuda.is_available())
print("✅ llama_cpp at", llama_cpp.__file__)
PY

echo "🎉 Venv ready."