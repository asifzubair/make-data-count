# inference.py (Final, Robust, Two-Stage Decoder)

import os
import re
import pandas as pd
from lxml import etree
import torch
import spacy
from tqdm import tqdm
from collections import Counter
from transformers import AutoTokenizer, AutoModelForTokenClassification

import config

def load_model_and_tokenizer():
    model_path = config.FINE_TUNED_MODEL_PATH
    print(f"Loading fine-tuned model from: {model_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model directory not found at {model_path}.")
    model = AutoModelForTokenClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model.to(config.DEVICE)
    model.eval()
    return model, tokenizer

def extract_text_from_xml(xml_file_path):
    # ... (this function is correct, no changes needed) ...
    try:
        tree = etree.parse(xml_file_path)
        full_text = tree.xpath("string()")
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        return ""

def normalize_doi(text):
    # ... (this function is correct, no changes needed) ...
    text = text.strip(" .,;")
    if 'doi.org' in text:
        text = "https://"+text[text.find("doi.org"):]
    elif text.lower().startswith("10."):
        text = f"https://doi.org/{text}"
    return text

def decode_predictions(original_text, offsets, preds):
    """
    Decodes predictions using a robust, two-stage approach.
    1. Find all contiguous entity boundaries (any B- or I- tag).
    2. Determine the type of the whole entity by majority vote.
    """
    labels = [config.ID_TO_LABEL.get(p, 'O') for p in preds]
    
    # Step 1: Group all adjacent B- and I- tags
    entity_groups = []
    current_group_indices = []
    for i, label in enumerate(labels):
        if offsets[i] == (0,0): continue

        if label[0] in 'BI':
            current_group_indices.append(i)
        else: # It's 'O', so the entity (if any) has ended
            if current_group_indices:
                entity_groups.append(current_group_indices)
                current_group_indices = []
    # Add any lingering group
    if current_group_indices:
        entity_groups.append(current_group_indices)

    # Step 2: Determine type by majority vote and extract text
    final_entities = []
    for indices in entity_groups:
        # Get all the labels for the tokens in this group
        group_labels = [labels[i] for i in indices]
        
        # Get just the types (e.g., 'primary', 'secondary')
        group_types = [label.split('-')[1] for label in group_labels if '-' in label]
        
        if not group_types: continue

        # Majority vote to determine the final type for the whole span
        final_type = Counter(group_types).most_common(1)[0][0]
        
        # Get character spans and slice from original text
        start_char = offsets[indices[0]][0]
        end_char = offsets[indices[-1]][1]
        entity_text = original_text[start_char:end_char]
        
        final_entities.append({"text": entity_text, "type": final_type})
        
    return final_entities


def main():
    """Main inference pipeline."""
    print("--- RUNNING SCRIPT VERSION 9.0 (two-stage robust decoder) ---")
    model, tokenizer = load_model_and_tokenizer()
    nlp = spacy.load("en_core_web_sm")
    # ... (the rest of the main function is correct and does not need changes) ...
    all_predictions = []
    test_files = os.listdir(config.TEST_XML_DIR)

    for filename in tqdm(test_files, desc="Predicting on Test Articles"):
        if not filename.endswith('.xml'): continue
        article_id = filename.replace('.xml', '')
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        
        full_text = extract_text_from_xml(file_path)
        if not full_text: continue

        article_entities = []
        doc = nlp(full_text)

        for sentence in doc.sents:
            sentence_text = sentence.text
            inputs = tokenizer(sentence_text, return_tensors="pt", truncation=True, max_length=512, return_offsets_mapping=True).to(config.DEVICE)
            offsets = inputs.pop("offset_mapping")[0].tolist()

            with torch.no_grad():
                logits = model(**inputs).logits
            
            predicted_ids = torch.argmax(logits, dim=2)[0].tolist()
            found_entities = decode_predictions(sentence_text, offsets, predicted_ids)
            article_entities.extend(found_entities)

        for entity in article_entities:
            dataset_id = normalize_doi(entity['text'])
            dataset_type = entity['type'].capitalize()
            all_predictions.append((article_id, dataset_id, dataset_type))

    unique_predictions = sorted(list(set(all_predictions)))
    submission_df = pd.DataFrame(unique_predictions, columns=['article_id', 'dataset_id', 'type'])
    if not submission_df.empty:
        submission_df.insert(0, 'row_id', range(len(submission_df)))
    else:
        submission_df['row_id'] = []

    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    print(f"\nSubmission file created successfully at {config.SUBMISSION_FILE}")
    print("Sample of final submission:")
    print(submission_df.head())


if __name__ == "__main__":
    main()