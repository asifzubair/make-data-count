# inference.py (Final Corrected Version)

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
    text = text.strip(" .,") # Remove common trailing characters
    if text.lower().startswith("10."):
        return f"https://doi.org/{text}"
    return text

def decode_predictions(original_text, offsets, preds):
    """
    Decodes a sequence of BIO predictions into named entity spans.
    This is a new, much simpler and more robust implementation.
    """
    preds = preds[:len(offsets)] # Ensure preds is not longer than offsets
    
    entities = []
    # Loop through each token's prediction
    for i, pred_id in enumerate(preds):
        label = config.ID_TO_LABEL.get(pred_id)
        
        # If we see a 'B-' tag, we know a new entity starts here
        if label.startswith("B-"):
            entity_type = label.split("-")[1]
            start_char = offsets[i][0]
            end_char = offsets[i][1]
            
            # Look ahead to find all consecutive 'I-' tags of the same type
            for j in range(i + 1, len(preds)):
                next_label = config.ID_TO_LABEL.get(preds[j])
                if next_label == f"I-{entity_type}":
                    # Extend the end character position
                    end_char = offsets[j][1]
                else:
                    # The entity has ended
                    break
            
            # Slice the final text from the original sentence
            entity_text = original_text[start_char:end_char]
            entities.append({"text": entity_text, "type": entity_type})

    return entities


def main():
    """Main inference pipeline."""
    print("--- RUNNING SCRIPT VERSION 5.0 (robust decoding) ---")
    print("--- Starting Inference ---")
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

        article_entities = []
        doc = nlp(full_text)

        for sentence in doc.sents:
            sentence_text = sentence.text
            inputs = tokenizer(
                sentence_text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                return_offsets_mapping=True
            ).to(config.DEVICE)
            
            offsets = inputs.pop("offset_mapping")[0].tolist()

            with torch.no_grad():
                logits = model(**inputs).logits
            
            predictions = torch.argmax(logits, dim=2)
            predicted_token_class_ids = predictions[0].tolist()
            
            found_entities = decode_predictions(sentence_text, offsets, predicted_token_class_ids)
            article_entities.extend(found_entities)

        for entity in article_entities:
            dataset_id = normalize_doi(entity['text'])
            dataset_type = entity['type'].capitalize()
            all_predictions.append((article_id, dataset_id, dataset_type))

    print(f"\nFound {len(all_predictions)} total potential citations.")
    unique_predictions = sorted(list(set(all_predictions)))
    print(f"Found {len(unique_predictions)} unique citations after deduplication.")
    
    submission_df = pd.DataFrame(unique_predictions, columns=['article_id', 'dataset_id', 'type'])
    submission_df.insert(0, 'row_id', range(len(submission_df)))
    
    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    print(f"\nSubmission file created successfully at {config.SUBMISSION_FILE}")
    print("Sample of final submission:")
    print(submission_df.head())


if __name__ == "__main__":
    main()