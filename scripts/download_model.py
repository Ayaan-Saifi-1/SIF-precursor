"""Fetch pinned public weights. This does not train a SIF classifier."""
import os,sys,json
from pathlib import Path
os.environ.setdefault("HF_HUB_DISABLE_XET","1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING","1")
from huggingface_hub import snapshot_download
root=Path(__file__).resolve().parents[1]/"ml"/"models"
revision="51d8f1e5e3c351273d81f3210fe1de16647cbd9e"
snapshot_download("adanish91/safetybert",revision=revision,local_dir=root/"safetybert",
                  allow_patterns=["config.json","model.safetensors","README.md"])
# The publisher's quick start specifies bert-base-cased. Validate vocabulary
# shape against the checkpoint rather than assuming the model card's conflicting
# prose description ("uncased") is correct.
config=json.loads((root/"safetybert"/"config.json").read_text())
vocab=config["vocab_size"]
if vocab==28996:
    repo="google-bert/bert-base-cased"; tok_revision="cd5ef92a9fb2f889e972770a36d4ed042daf221e"
elif vocab==30522:
    repo="google-bert/bert-base-uncased"
    from huggingface_hub import HfApi
    tok_revision=HfApi().model_info(repo).sha
else: raise RuntimeError(f"Unrecognised vocabulary size {vocab}; tokenizer needs explicit verification.")
snapshot_download(repo,revision=tok_revision,local_dir=root/"tokenizer",
    allow_patterns=["config.json","tokenizer.json","tokenizer_config.json","vocab.txt","special_tokens_map.json"])
from transformers import AutoTokenizer
tokenizer=AutoTokenizer.from_pretrained(root/"tokenizer",local_files_only=True)
assert len(tokenizer)==vocab,"Tokenizer vocabulary does not match checkpoint."
(root/"provenance.json").write_text(json.dumps(dict(model="adanish91/safetybert",model_revision=revision,
    tokenizer=repo,tokenizer_revision=tok_revision,vocab_size=vocab,source="https://huggingface.co/adanish91/safetybert"),indent=2))
print(f"SafetyBERT installed; verified vocabulary size {vocab}.")
