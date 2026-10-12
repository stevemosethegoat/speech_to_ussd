"""Merge a LoRA adapter into its base Whisper model.

Usage:
    python scripts/merge_lora.py \
        --base openai/whisper-small \
        --adapter models/whisper_swahili_smoke \
        --output models/whisper_smoke_merged
"""
import argparse
from pathlib import Path

import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from peft import PeftModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="openai/whisper-small")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading base:    {args.base}")
    base = WhisperForConditionalGeneration.from_pretrained(
        args.base, torch_dtype=torch.float32
    )

    print(f"Loading adapter: {args.adapter}")
    model = PeftModel.from_pretrained(base, args.adapter)

    print("Merging LoRA into base weights...")
    merged = model.merge_and_unload()

    print(f"Saving merged model to {out}")
    merged.save_pretrained(str(out))

    print("Saving processor...")
    proc = WhisperProcessor.from_pretrained(
        args.base, language="swahili", task="transcribe"
    )
    proc.save_pretrained(str(out))

    print("Done.")
    for f in sorted(out.iterdir()):
        size_mb = f.stat().st_size / 1e6
        print(f"  {f.name:35s}  {size_mb:8.2f} MB")


if __name__ == "__main__":
    main()
