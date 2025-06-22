import os
import pandas as pd
from transformers import AutoTokenizer
from tqdm import tqdm

import config

def process_and_align_labels():
    print("Loading pre-processed data...")
    df = pd.read_csv(config.OUTPUT_DIR + 'processed_training_data.csv')
    
    print(f"Loading tokenizer: {config.MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(config.MODEL_PATH)
    
    all_token_labels = []
    
    print("Aligning character spans to token-level BIO labels...")
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Aligning Labels"):
        context = str(row['context_sentence'])
        label_type = row['dataset_type']
        found_text = str(row['found_text'])

        # --- THE FIX IS HERE ---
        # Instead of using the old span, find the start of the label within the CONTEXT sentence
        label_start_in_context = context.find(found_text)
        
        if label_start_in_context == -1:
            # As a safeguard, if the found_text isn't in the context, skip it.
            # This indicates a data cleaning issue from the previous step.
            # We'll create a dummy list of labels so the dataframe shapes match.
            tokenized_inputs = tokenizer(context, max_length=config.MAX_SEQ_LEN, padding="max_length", truncation=True)
            all_token_labels.append([config.LABEL_MAP['O']] * len(tokenized_inputs['input_ids'][0]))
            continue

        label_end_in_context = label_start_in_context + len(found_text)
        # --- END OF FIX ---

        tokenized_inputs = tokenizer(
            context,
            max_length=config.MAX_SEQ_LEN,
            padding="max_length",
            truncation=True,
            return_offsets_mapping=True,
        )

        offsets = tokenized_inputs["offset_mapping"]
        token_labels = [config.LABEL_MAP['O']] * len(offsets)
        
        is_first_token = True
        for i, (start_char, end_char) in enumerate(offsets):
            if start_char == end_char == 0:
                continue

            # Check if the token's span overlaps with our NEW, relative label span
            if start_char >= label_start_in_context and end_char <= label_end_in_context:
                if is_first_token:
                    token_labels[i] = config.LABEL_MAP[f'B-{label_type.lower()}']
                    is_first_token = False
                else:
                    token_labels[i] = config.LABEL_MAP[f'I-{label_type.lower()}']

        all_token_labels.append(token_labels)

    df['bio_labels'] = all_token_labels
    
    print("\n--- Label Alignment Complete ---")
    
    final_save_path = os.path.join(config.OUTPUT_DIR, 'final_training_data.jsonl')
    df.to_json(final_save_path, orient='records', lines=True)
    
    print(f"Final model-ready data saved to: {final_save_path}")
    
    # --- Verification Step ---
    print("\nVerifying a sample:")
    sample_index = 0
    sample_row = df.iloc[sample_index]
    # We need to re-tokenize for verification to get the token strings
    tokens = tokenizer.convert_ids_to_tokens(tokenizer(sample_row['context_sentence'])['input_ids'])
    labels = [config.ID_TO_LABEL[label_id] for label_id in sample_row['bio_labels']]
    
    print("Sample Context:", sample_row['context_sentence'])
    print("\nZipped Tokens and Labels (Corrected):")
    for token, label in list(zip(tokens, labels))[:40]: # Print more tokens
        if label != 'O':
            print(f"-> {token:<20} {label}")
        else:
            print(f"   {token:<20} {label}")

if __name__ == '__main__':
    process_and_align_labels()