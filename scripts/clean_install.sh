#!/bin/bash
set -e  # Exit on any error

echo "=== NUCLEAR CLEAN INSTALL FOR LLAMA 70B ==="

# 1. Nuke all suspect installations
echo "🧼 Removing suspect installations..."
rm -rf /mnt/data/tools/transformers || true
rm -rf /mnt/data/tools/accelerate || true
rm -rf /mnt/data/tools/bitsandbytes || true
rm -rf /mnt/data/tools/torch || true

# 2. Clear pip cache completely
echo "🗑️  Clearing pip cache..."
pip cache purge

# 3. Uninstall everything related to transformers stack
echo "🔥 Uninstalling existing packages..."
pip uninstall -y transformers accelerate bitsandbytes torch torchvision torchaudio || true
pip uninstall -y transformers accelerate bitsandbytes torch torchvision torchaudio || true  # Run twice to catch stragglers

# 4. Install PyTorch first (specific CUDA version)
echo "⚡ Installing PyTorch 2.1.2+cu118..."
pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 torchaudio==2.1.2+cu118 --index-url https://download.pytorch.org/whl/cu118

# 5. Install the exact working stack
echo "📦 Installing transformers stack..."
pip install --no-cache-dir \
    transformers==4.38.2 \
    accelerate==0.27.2 \
    bitsandbytes==0.42.0 \
    numpy==1.24.4

# 6. Verify installation
echo "🔍 Verifying installation..."
python3 -c "
import sys
print('Python path:', sys.executable)

import transformers
print('✅ Transformers:', transformers.__version__, 'from', transformers.__file__)

import accelerate  
print('✅ Accelerate:', accelerate.__version__, 'from', accelerate.__file__)

import bitsandbytes
print('✅ BitsAndBytes:', bitsandbytes.__version__, 'from', bitsandbytes.__file__)

import torch
print('✅ PyTorch:', torch.__version__, 'CUDA available:', torch.cuda.is_available())

# Test the specific import that was failing
from transformers import BitsAndBytesConfig
config = BitsAndBytesConfig(load_in_4bit=True)
print('✅ BitsAndBytesConfig test passed')
"

echo "✅ Clean install complete!"
echo "Now run your model loader - it should work correctly."
