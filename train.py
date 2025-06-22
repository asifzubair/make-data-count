# train.py

import os
import pandas as pd
from datasets import Dataset, DatasetDict
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer
import torch
from sklearn.model_selection import train_test_split

# Import our project settings
import config

def train_model():
    """
    Main function to load data, set up the model and trainer, and run fine-tuning.
    """
    print("--- Starting Model Training ---")
    print(f"Using device: {config.DEVICE}")

    # --- 1. Load the final, processed dataset ---
    # This file comes from the output of our ner_data_processor.py script
    final_data_path = '/kaggle/input/data-preparation/output/final_training_data.jsonl'
    
    print(f"Loading model-ready data from {final_data_path}...")
    if not os.path.exists(final_data_path):
        print(f"Error: Processed data file not found at {final_data_path}")
        print("Please make sure the output from the data processing notebook is added as an input source.")
        return

    df = pd.read_json(final_data_path, lines=True)

    # The 'bio_labels' column is currently a list of lists. We need to handle it correctly.
    # We will create a custom dataset class to feed this to the trainer.
    
    # Split the dataframe into training and validation sets
    train_df, val_df = train_test_split(df, test_size=0.1, random_state=42)

    train_dataset_hf = Dataset.from_pandas(train_df)
    val_dataset_hf = Dataset.from_pandas(val_df)
    
    dataset_dict = DatasetDict({
        'train': train_dataset_hf,
        'validation': val_dataset_hf
    })
    print(f"Data split into {len(dataset_dict['train'])} training and {len(dataset_dict['validation'])} validation samples.")


    # --- 2. Load Tokenizer and Model ---
    print(f"Loading model and tokenizer from offline path: {config.MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(config.MODEL_PATH)
    
    model = AutoModelForTokenClassification.from_pretrained(
        config.MODEL_PATH,
        num_labels=len(config.LABEL_MAP),
        id2label=config.ID_TO_LABEL,
        label2id=config.LABEL_MAP,
        ignore_mismatched_sizes=True,
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
        logging_dir='./logs',
        logging_steps=10,
        eval_steps=10,
        save_strategy="steps",
        save_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none"
    )
    
    # We need a data collator to handle padding and tensor conversion for our specific task
    from transformers import DataCollatorForTokenClassification
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset_dict["train"],
        eval_dataset=dataset_dict["validation"],
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
    tokenizer.save_pretrained(final_model_path) # Also save the tokenizer with the model
    print("Model and tokenizer saved successfully!")


if __name__ == "__main__":
    train_model()