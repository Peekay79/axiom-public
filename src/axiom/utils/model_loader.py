# ─────────────────────────────────────────────────────────────
# 🚨 Quantized Model Loading – Permanent Note for Axiom Developers
#
# 🔥 CORE LESSON:
#   • Always load 4-bit / 8-bit bits-and-bytes models with device_map="auto".
#   • NEVER call .to() on a quantized model – it breaks placement.
#
# ✅ Safe pattern implemented below using BitsAndBytesConfig.
# ─────────────────────────────────────────────────────────────

import logging
import os

import torch

# ─────────────────────────────────────────────
# 🧠 Debug: Confirm transformers version and source
# ─────────────────────────────────────────────
import transformers
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
)

print(
    f"[DEBUG] Transformers version: {transformers.__version__} loaded from {transformers.__file__}"
)

# ─────────────────────────────────────────────
# (Optional) .to() protection patch -- disabled by default.
# Uncomment if you run legacy code that might still call .to().
# ─────────────────────────────────────────────
# _orig_to = PreTrainedModel.to
# def _patched_to(self, *args, **kwargs):
#     if getattr(self, "is_loaded_in_4bit", False) or getattr(self, "is_loaded_in_8bit", False):
#         print("🛡️  Blocked .to() on quantized model")
#         return self
#     return _orig_to(self, *args, **kwargs)
# PreTrainedModel.to = _patched_to

# ─────────────────────────────────────────────
# 📁  Default model path & offload dir
# ─────────────────────────────────────────────
DEFAULT_MODEL_PATH = os.environ.get(
    "MODEL_PATH", "/workspace/models/Meta-Llama-3-70B-Instruct"
)
OFFLOAD_PATH = os.environ.get("OFFLOAD_PATH", "/workspace/offload")


# ─────────────────────────────────────────────
# 📦  Tokenizer loader
# ─────────────────────────────────────────────
def load_tokenizer(model_path: str | None = None):
    model_path = model_path or DEFAULT_MODEL_PATH
    tok = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        use_fast=False,
    )
    tok.pad_token = tok.eos_token
    return tok


# ─────────────────────────────────────────────
# 🧠  Model loader (4-bit, device_map="auto")
# ─────────────────────────────────────────────
def load_model(model_path: str | None = None):
    model_path = model_path or DEFAULT_MODEL_PATH

    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_cfg,
        device_map="auto",  # allow automatic placement incl. offload
        trust_remote_code=True,
        offload_folder=OFFLOAD_PATH,
    )

    model.eval()
    return model


# ─────────────────────────────────────────────
# 📦 + 🧠  Convenience wrapper
# ─────────────────────────────────────────────
def load_model_and_tokenizer(model_path: str | None = None):
    tokenizer = load_tokenizer(model_path)
    model = load_model(model_path)
    return model, tokenizer
