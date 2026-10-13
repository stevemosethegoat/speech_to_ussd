"""
Single-stage Whisper fine-tuning for Swahili ASR.

Usage:
    python -m src.asr.finetune_whisper \
        --csv data/processed/train_stage1.csv \
        --base-model openai/whisper-small \
        --output-dir models/whisper_swahili \
        --epochs 3 \
        --batch-size 4 \
        --lora
"""

import argparse
from pathlib import Path

import pandas as pd
import torch
from datasets import Audio, Dataset
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_MODEL = "openai/whisper-small"
DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "train_stage1.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "models" / "whisper_swahili"


# ============================================================
# DATA LOADING
# ============================================================

def load_dataframe(csv_path: Path, sample: int | None = None) -> pd.DataFrame:
    """
    Load a single-schema CSV. Accepts either:
        - audio + transcript
        - resampled_audio_path + transcript
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"\nDataset not found:\n{csv_path}\n")

    print(f"Loading dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Columns found: {list(df.columns)}")
    print(f"Rows found: {len(df)}")

    # Normalize audio column name
    if "resampled_audio_path" in df.columns and "audio" not in df.columns:
        df = df.rename(columns={"resampled_audio_path": "audio"})

    for col in ("audio", "transcript"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df[df["transcript"].notna() & (df["transcript"].astype(str).str.strip() != "")]
    df = df[df["audio"].notna() & (df["audio"].astype(str).str.strip() != "")]
    df = df.reset_index(drop=True)

    # Resolve audio paths
    def resolve(p):
        path = Path(str(p))
        if path.is_absolute():
            return str(path)
        candidate = PROJECT_ROOT / path
        if candidate.exists():
            return str(candidate)
        candidate = csv_path.parent / path
        if candidate.exists():
            return str(candidate)
        return str(path)

    df["audio"] = df["audio"].apply(resolve)

    # Drop missing audio files
    before = len(df)
    df = df[df["audio"].apply(lambda p: Path(p).exists())].copy()
    removed = before - len(df)
    if removed:
        print(f"Removed {removed} rows with missing audio files.")

    # Optional sampling
    if sample is not None:
        if sample <= 0:
            raise ValueError("--sample must be > 0")
        if sample < len(df):
            df = df.sample(n=sample, random_state=42)
        df = df.reset_index(drop=True)

    print(f"Valid rows: {len(df)}")
    if len(df) == 0:
        raise ValueError("No valid audio/transcript pairs were found.")
    return df


# ============================================================
# DATASET PREPARATION
# ============================================================

def prepare_dataset(df: pd.DataFrame, processor: WhisperProcessor) -> Dataset:
    """Convert dataframe into HF Dataset with input_features and labels."""
    dataset = Dataset.from_pandas(df[["audio", "transcript"]], preserve_index=False)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))

    def prepare_example(example):
        audio = example["audio"]
        input_features = processor.feature_extractor(
            audio["array"], sampling_rate=audio["sampling_rate"]
        ).input_features[0]
        labels = processor.tokenizer(example["transcript"]).input_ids
        return {"input_features": input_features, "labels": labels}

    dataset = dataset.map(
        prepare_example,
        remove_columns=dataset.column_names,
        num_proc=1,
    )
    return dataset


# ============================================================
# DATA COLLATOR
# ============================================================

class DataCollatorSpeechSeq2Seq:
    def __init__(self, processor):
        self.processor = processor

    def __call__(self, features):
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)

        if (
            labels.shape[1] > 0
            and torch.all(labels[:, 0] == self.processor.tokenizer.bos_token_id)
        ):
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch


# ============================================================
# TRAINING
# ============================================================

def train_whisper(
    dataset: Dataset,
    base_model: str,
    output_dir: Path,
    processor: WhisperProcessor,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    gradient_accumulation_steps: int,
    save_steps: int,
    logging_steps: int,
    use_lora: bool,
    dataloader_workers: int,
):
    print()
    print("=" * 60)
    print("Loading Whisper model")
    print("=" * 60)
    print(f"Base model: {base_model}")

    model = WhisperForConditionalGeneration.from_pretrained(base_model)
    model.generation_config.language = "swahili"
    model.generation_config.task = "transcribe"
    model.config.forced_decoder_ids = None

    # Optional LoRA
    if use_lora:
        from peft import LoraConfig, get_peft_model
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    # Gradient checkpointing needs to be enabled on the model
    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    data_collator = DataCollatorSpeechSeq2Seq(processor)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Device detection
    use_cuda = torch.cuda.is_available()
    use_fp16 = use_cuda and torch.cuda.get_device_capability(0)[0] >= 7
    use_bf16 = use_cuda and torch.cuda.is_bf16_supported()

    print(f"CUDA available: {use_cuda}")
    print(f"Using fp16:     {use_fp16}")
    print(f"Using bf16:     {use_bf16}")

    # Warmup: smaller for small datasets
    warmup_steps = min(500, max(50, len(dataset) // 50))

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=2,
        fp16=use_fp16,
        bf16=use_bf16,
        gradient_checkpointing=True,
        predict_with_generate=False,
        remove_unused_columns=False,
        report_to="none",
        dataloader_num_workers=dataloader_workers,
        dataloader_pin_memory=use_cuda,
        load_best_model_at_end=False,
    )

    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=dataset,
        data_collator=data_collator,
        processing_class=processor,
    )

    print()
    print("=" * 60)
    print("Starting training")
    print("=" * 60)
    trainer.train()

    print()
    print("=" * 60)
    print("Saving model")
    print("=" * 60)
    trainer.save_model(str(output_dir))
    processor.save_pretrained(str(output_dir))
    print(f"Model saved to: {output_dir}")


# ============================================================
# ARGUMENT PARSER
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Single-stage Whisper fine-tuning")
    parser.add_argument("--csv", type=Path, default=None, help="Path to dataset CSV")
    parser.add_argument("--base-model", type=str, default=None, help="Base Whisper model")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--save-steps", type=int, default=500)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--sample", type=int, default=None, help="Use only N examples")
    parser.add_argument("--lora", action="store_true", help="Enable LoRA (fewer trainable params)")
    parser.add_argument("--dataloader-workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    csv_path = args.csv if args.csv is not None else DEFAULT_CSV
    base_model = args.base_model if args.base_model is not None else DEFAULT_BASE_MODEL
    output_dir = args.output_dir if args.output_dir is not None else DEFAULT_OUTPUT

    print()
    print("=" * 60)
    print("WHISPER FINE-TUNING (single-stage)")
    print("=" * 60)
    print(f"Dataset:        {csv_path}")
    print(f"Base model:     {base_model}")
    print(f"Output:         {output_dir}")
    print(f"Epochs:         {args.epochs}")
    print(f"Batch size:     {args.batch_size}")
    print(f"Grad accum:     {args.gradient_accumulation_steps}")
    print(f"Learning rate:  {args.learning_rate}")
    print(f"LoRA:           {args.lora}")
    print("=" * 60)

    df = load_dataframe(csv_path=csv_path, sample=args.sample)

    print()
    print("Loading Whisper processor...")
    processor = WhisperProcessor.from_pretrained(
        base_model, language="swahili", task="transcribe"
    )

    print()
    print("Preparing audio dataset...")
    dataset = prepare_dataset(df=df, processor=processor)
    print(f"Prepared examples: {len(dataset)}")

    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY RUN — validation passed")
        print("=" * 60)
        print(f"Dataset rows : {len(df)}")
        print(f"Examples     : {len(dataset)}")
        print("No training was run.")
        return

    train_whisper(
        dataset=dataset,
        base_model=base_model,
        output_dir=output_dir,
        processor=processor,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        save_steps=args.save_steps,
        logging_steps=args.logging_steps,
        use_lora=args.lora,
        dataloader_workers=args.dataloader_workers,
    )

    print()
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Model: {output_dir}")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
