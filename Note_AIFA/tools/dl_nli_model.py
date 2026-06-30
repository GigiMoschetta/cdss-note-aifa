"""Download the new multilingual NLI model into the local HuggingFace cache.

Usage:
    python3 tools/dl_nli_model.py
"""
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"

print(f"Downloading {MODEL_ID} ...")
AutoTokenizer.from_pretrained(MODEL_ID)
AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
print("Done.")
