"""Local SafetyBERT only. Never downloads models during a report request."""
import os
from functools import lru_cache
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.environ.get("SAFETYBERT_PATH", ROOT/"ml"/"models"/"safetybert"))
TOKENIZER_DIR = Path(os.environ.get("SAFETYBERT_TOKENIZER_PATH", ROOT/"ml"/"models"/"tokenizer"))

@lru_cache(maxsize=1)
def load_encoder():
    import torch
    from transformers import AutoTokenizer, AutoModel
    if not (MODEL_DIR/"model.safetensors").exists():
        raise RuntimeError("SafetyBERT checkpoint is not installed. Run scripts/download_model.py.")
    torch.set_num_threads(int(os.environ.get("TORCH_NUM_THREADS","4")))
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_DIR,local_files_only=True,trust_remote_code=False)
    model = AutoModel.from_pretrained(MODEL_DIR,local_files_only=True,trust_remote_code=False,use_safetensors=True,add_pooling_layer=False)
    model.eval()
    return tokenizer, model

@lru_cache(maxsize=512)
def encode(text):
    import torch
    import numpy as np
    tokenizer, model = load_encoder()
    # Chunk rather than discard evidence beyond the encoder's context length.
    inputs = tokenizer(text,return_tensors="pt",max_length=512,truncation=True,
                       return_overflowing_tokens=True,stride=64,padding=True)
    inputs.pop("overflow_to_sample_mapping",None)
    with torch.inference_mode():
        hidden=model(**inputs).last_hidden_state
        mask=inputs["attention_mask"].unsqueeze(-1)
        pooled=(hidden*mask).sum(dim=1)/mask.sum(dim=1).clamp(min=1)
        vec=pooled.mean(dim=0).cpu().numpy()
    return np.asarray(vec / max(np.linalg.norm(vec),1e-9),dtype=np.float32)
