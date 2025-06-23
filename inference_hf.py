# inference.py (FINAL - Using the official Hugging Face pipeline)

import os
import re
import pandas as pd
from lxml import etree
from tqdm import tqdm
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification

import config

def main():
    """Main inference pipeline using the high-level pipeline() function."""
    print("--- RUNNING SCRIPT (Official Hugging Face Pipeline Version) ---")
    
    # --- 1. Load Model and Create Pipeline ---
    model_path = config.FINE_TUNED_MODEL_PATH
    print(f"Loading fine-tuned model from: {model_path}")
    
    model = AutoModelForTokenClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    # This one line handles tokenization, long text (sliding window), and decoding!
    ner_pipeline = pipeline(
        "token-classification",
        model=model,
        tokenizer=tokenizer,
        device=0 if config.DEVICE.type == 'cuda' else -1, # Use GPU if available
        aggregation_strategy="simple" # This strategy groups B- and I- tags automatically
    )

    # --- 2. Process Test Files ---
    all_predictions = []
    test_files = os.listdir(config.TEST_XML_DIR)

    for filename in tqdm(test_files, desc="Predicting on Test Articles"):
        if not filename.endswith('.xml'): continue
        article_id = filename.replace('.xml', '')
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        
        try:
            tree = etree.parse(file_path)
            full_text = tree.xpath("string()")
            full_text = re.sub(r'\s+', ' ', full_text).strip()
        except Exception:
            continue
            
        if not full_text: continue

        # The pipeline handles the long text automatically
        try:
            entities = ner_pipeline(full_text)
        except Exception as e:
            # print(f"Error processing article {article_id}: {e}")
            continue

        for entity in entities:
            # The pipeline gives us the text and type directly
            dataset_id = entity['word'].strip(" .,;")
            dataset_type = entity['entity_group'].capitalize()

            # Normalize DOIs
            if 'doi.org' in dataset_id:
                dataset_id = "https://"+dataset_id[dataset_id.find("doi.org"):]
            elif dataset_id.lower().startswith("10."):
                dataset_id = f"https://doi.org/{dataset_id}"
            
            all_predictions.append((article_id, dataset_id, dataset_type))

    # --- 3. Final Formatting ---
    print(f"\nFound {len(all_predictions)} total potential citations.")
    unique_predictions = sorted(list(set(all_predictions)))
    print(f"Found {len(unique_predictions)} unique citations after deduplication.")
    
    submission_df = pd.DataFrame(unique_predictions, columns=['article_id', 'dataset_id', 'type'])
    if not submission_df.empty:
        submission_df.insert(0, 'row_id', range(len(submission_df)))
    else:
        submission_df = pd.DataFrame(columns=['row_id', 'article_id', 'dataset_id', 'type'])

    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    print(f"\nSubmission file created successfully at {config.SUBMISSION_FILE}")
    print("Sample of final submission:")
    print(submission_df.head())


if __name__ == "__main__":
    main()