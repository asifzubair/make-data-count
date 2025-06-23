# inference.py (Final version with post-processing merge)

import os
import re
import pandas as pd
from lxml import etree
import torch
import spacy
from tqdm import tqdm
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
    try:
        tree = etree.parse(xml_file_path)
        full_text = tree.xpath("string()")
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        return ""

def normalize_doi(text):
    return text.strip(" .,")

def decode_predictions(original_text, offsets, preds):
    entities = []
    for i, pred_id in enumerate(preds):
        label = config.ID_TO_LABEL.get(pred_id)
        if label and label.startswith("B-"):
            entity_type = label.split("-")[1]
            start_char, end_char = offsets[i]
            
            for j in range(i + 1, len(preds)):
                next_label = config.ID_TO_LABEL.get(preds[j])
                if not (next_label and next_label == f"I-{entity_type}"):
                    break
                end_char = offsets[j][1]
            
            entity_text = original_text[start_char:end_char]
            entities.append({"text": entity_text, "type": entity_type, "start": start_char, "end": end_char})
    return entities

def merge_adjacent_entities(entities):
    """Merges adjacent or overlapping entities of the same type."""
    if not entities:
        return []

    # Sort entities by their start position
    entities.sort(key=lambda x: x['start'])
    
    merged = []
    current_entity = entities[0]

    for next_entity in entities[1:]:
        # Check if entities are adjacent (with up to 2 chars of separation) and same type
        if next_entity['start'] <= current_entity['end'] + 2 and next_entity['type'] == current_entity['type']:
            # Merge by extending the end position
            current_entity['end'] = max(current_entity['end'], next_entity['end'])
            # Update text to reflect merged span
            current_entity['text'] = current_entity['text'] + next_entity['text'][current_entity['end'] - next_entity['start']:]
        else:
            merged.append(current_entity)
            current_entity = next_entity
            
    merged.append(current_entity)
    return merged

def main():
    print("--- RUNNING SCRIPT VERSION 6.0 (with post-processing merge) ---")
    model, tokenizer = load_model_and_tokenizer()
    nlp = spacy.load("en_core_web_sm")
    all_predictions = []
    test_files = os.listdir(config.TEST_XML_DIR)

    for filename in tqdm(test_files, desc="Predicting on Test Articles"):
        if not filename.endswith('.xml'): continue
        article_id = filename.replace('.xml', '')
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        full_text = extract_text_from_xml(file_path)
        if not full_text: continue

        doc = nlp(full_text)
        article_entities = []

        for sentence in doc.sents:
            sentence_text = sentence.text
            inputs = tokenizer(sentence_text, return_tensors="pt", truncation=True, max_length=512, return_offsets_mapping=True).to(config.DEVICE)
            offsets = inputs.pop("offset_mapping")[0].tolist()

            with torch.no_grad():
                logits = model(**inputs).logits
            
            predicted_ids = torch.argmax(logits, dim=2)[0].tolist()
            
            # Use character offsets relative to the whole document for merging
            sent_start_char = sentence.start_char
            
            found_entities = decode_predictions(sentence_text, offsets, predicted_ids)
            for entity in found_entities:
                # Adjust start/end to be relative to the full document text
                entity['start'] += sent_start_char
                entity['end'] += sent_start_char
                article_entities.append(entity)

        # Post-processing step to merge fragments for the whole article
        merged_article_entities = merge_adjacent_entities(article_entities)

        for entity in merged_article_entities:
            # Re-slice the text from the full document now that we have the final merged span
            dataset_id = normalize_doi(full_text[entity['start']:entity['end']])
            # Special check for DOIs
            if 'doi.org' in dataset_id:
                 dataset_id = "https://"+dataset_id[dataset_id.find("doi.org"):]

            dataset_type = entity['type'].capitalize()
            all_predictions.append((article_id, dataset_id, dataset_type))

    unique_predictions = sorted(list(set(all_predictions)))
    submission_df = pd.DataFrame(unique_predictions, columns=['article_id', 'dataset_id', 'type'])
    submission_df.insert(0, 'row_id', range(len(submission_df)))
    
    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    print(f"\nSubmission file created successfully at {config.SUBMISSION_FILE}")
    print("Sample of final submission:")
    print(submission_df.head())

if __name__ == "__main__":
    main()
    