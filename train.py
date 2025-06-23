# train.py (Corrected)

import os
import pandas as pd
from datasets import Dataset, DatasetDict
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer, DataCollatorForTokenClassification
from sklearn.model_selection import train_test_split
import torch

import config

def train_model():
    print("--- Starting Model Training ---")
    print(f"Using device: {config.DEVICE}")

    # --- 1. Load the processed data ---
    final_data_path = '/kaggle/input/data-preparation/output/final_training_data.jsonl'
    print(f"Loading model-ready data from {final_data_path}...")
    df = pd.read_json(final_data_path, lines=True)

    # --- THE FIX IS HERE: Rename 'bio_labels' column to 'labels' ---
    # The Trainer specifically looks for a column named "labels"
    df.rename(columns={'bio_labels': 'labels'}, inplace=True)

    train_df, val_df = train_test_split(df, test_size=0.1, random_state=42, shuffle=True)
    train_dataset_hf = Dataset.from_pandas(train_df)
    val_dataset_hf = Dataset.from_pandas(val_df)
    
    dataset_dict = DatasetDict({'train': train_dataset_hf, 'validation': val_dataset_hf})
    print(f"Data split into {len(dataset_dict['train'])} training and {len(dataset_dict['validation'])} validation samples.")
    
    tokenizer = AutoTokenizer.from_pretrained(config.MODEL_PATH)

    # --- AND HERE: Create a function to tokenize the text ---
    def tokenize_function(examples):
        # The tokenizer will turn the text in 'context_sentence' into 'input_ids' and 'attention_mask'
        return tokenizer(examples["context_sentence"], truncation=True, padding="max_length", max_length=config.MAX_SEQ_LEN)

    # Use .map() to apply the tokenization to the entire dataset
    print("Tokenizing dataset...")
    tokenized_datasets = dataset_dict.map(tokenize_function, batched=True)

    # Now the dataset has the columns: 'input_ids', 'attention_mask', and 'labels'
    # We can remove the old text columns as they are no longer needed
    tokenized_datasets = tokenized_datasets.remove_columns(['article_id', 'dataset_id', 'dataset_type', 'label_span', 'context_sentence', 'found_text', '__index_level_0__'])
    # --- END OF FIX ---


    # --- 2. Load Model ---
    print(f"Loading model from offline path: {config.MODEL_PATH}")
    model = AutoModelForTokenClassification.from_pretrained(
        config.MODEL_PATH,
        num_labels=len(config.LABEL_MAP),
        id2label=config.ID_TO_LABEL,
        label2id=config.LABEL_MAP,
        ignore_mismatched_sizes=True
    )
    model.to(config.DEVICE)


    # --- 3. Set Up the Trainer ---
    print("Configuring training arguments...")
    training_args = TrainingArguments(
        output_dir=os.path.join(config.OUTPUT_DIR, "scibert-finetuned-checkpoints"),
        num_train_epochs=config.EPOCHS,
        per_device_train_batch_size=config.BATCH_SIZE,
        per_device_eval_batch_size=config.BATCH_SIZE,
        learning_rate=config.LEARNING_RATE,
        warmup_steps=50,
        weight_decay=0.01,
        # We will log, evaluate, and save at the end of each epoch
        logging_strategy="epoch",
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        remove_unused_columns=False
    )
    
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

    trainer = Trainer(
        model=model,
        args=training_args,
        # Pass the newly tokenized datasets to the trainer
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator
    )

    # --- 4. Start Training ---
    print("\nStarting fine-tuning...")
    trainer.train()
    print("--- Fine-tuning complete! ---")

    # --- 5. Save the Final Model ---
    final_model_path = os.path.join(config.OUTPUT_DIR, "scibert-finetuned-final")
    print(f"Saving the best model to: {final_model_path}")
    trainer.save_model(final_model_path)
    tokenizer.save_pretrained(final_model_path)
    print("Model and tokenizer saved successfully!")


if __name__ == "__main__":
    train_model()