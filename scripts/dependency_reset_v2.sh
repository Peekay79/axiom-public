#!/bin/bash
set -e

echo "=== NUCLEAR DEPENDENCY RESET v2 ==="

# 1. Complete Python package purge
echo "🧼 Purging ALL ML packages..."
pip uninstall -y transformers accelerate bitsandbytes torch torchvision torchaudio tokenizers numpy scipy || true
pip uninstall -y transformers accelerate bitsandbytes torch torchvision torchaudio tokenizers numpy scipy || true

# 2. Clear all caches
echo "🗑️  Clearing all caches..."
pip cache purge
python -m pip cache purge

# 3. Remove any lingering compiled extensions
echo "🔥 Removing compiled cache..."
find /usr/local/lib/python3.10/dist-packages -name "*.pyc" -delete || true
find /usr/local/lib/python3.10/dist-packages -name "__pycache__" -type d -exec rm -rf {} + || true

# 4. Install NumPy first (compatible version)
echo "📐 Installing compatible NumPy..."
pip install numpy==1.26.4

# 5. Install PyTorch (this will get correct NumPy compatibility)
echo "⚡ Installing PyTorch..."
pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 torchaudio==2.1.2+cu118 --index-url https://download.pytorch.org/whl/cu118

# 6. Install tokenizers FIRST (before transformers)
echo "🔤 Installing compatible tokenizers..."
pip install tokenizers==0.15.2

# 7. Install remaining stack
echo "📦 Installing transformers stack..."
pip install transformers==4.38.2
pip install accelerate==0.27.2
pip install bitsandbytes==0.42.0

# 8. Verification
echo "🔍 Final verification..."
python3 -c "
import sys
print('Python:', sys.version)

import numpy as np
print('✅ NumPy:', np.__version__)

import torch
print('✅ PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available())

import tokenizers
print('✅ Tokenizers:', tokenizers.__version__)

import transformers
print('✅ Transformers:', transformers.__version__)

import accelerate
print('✅ Accelerate:', accelerate.__version__)

import bitsandbytes as bnb
print('✅ BitsAndBytes:', bnb.__version__)

# Critical test
from transformers import BitsAndBytesConfig
config = BitsAndBytesConfig(load_in_4bit=True)
print('✅ BitsAndBytesConfig test: PASSED')

print('🎉 ALL DEPENDENCIES VERIFIED')
"

echo "✅ Nuclear reset v2 complete!"
