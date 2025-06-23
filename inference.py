# inference.py

import os
import re
import pandas as pd
from lxml import etree
import torch
import spacy
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForTokenClassification

# Import our project settings
import config

def load_model_and_tokenizer():
    """Loads the fine-tuned model and tokenizer from the specified path."""
    # NOTE: The path in config.py must now point to the output of our training notebook
    model_path = config.FINE_TUNED_MODEL_PATH
    print(f"Loading fine-tuned model from: {model_path}")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model directory not found at {model_path}. Did you add the training output as a data source?")

    model = AutoModelForTokenClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model.to(config.DEVICE)
    model.eval() # Set the model to evaluation mode
    return model, tokenizer

def extract_text_from_xml(xml_file_path):
    """Parses an XML file and extracts all text content."""
    try:
        tree = etree.parse(xml_file_path)
        full_text = tree.xpath("string()")
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        return ""

def normalize_doi(text):
    """Converts a found DOI to the standard https://doi.org/ format."""
    if text.lower().startswith("10."):
        return f"https://doi.org/{text}"
    # Add other normalizations if needed, but this is a good start
    return text

def decode_predictions(tokens, preds, tokenizer):
    """
    Decodes a sequence of BIO predictions back into named entity spans.
    """
    predictions = []
    current_entity_tokens = []
    current_entity_type = None

    for token, pred_id in zip(tokens, preds):
        label = config.ID_TO_LABEL.get(pred_id)

        if label is None:
            continue

        if label.startswith("B-"):
            # If we were already in an entity, save it before starting a new one
            if current_entity_tokens:
                entity_text = tokenizer.decode(tokenizer.convert_tokens_to_ids(current_entity_tokens))
                predictions.append({"text": entity_text, "type": current_entity_type})
            
            current_entity_tokens = [token]
            current_entity_type = label.split("-")[1]

        elif label.startswith("I-") and current_entity_type == label.split("-")[1]:
            # If the token is inside an entity of the same type, append it
            current_entity_tokens.append(token)
        else:
            # If it's 'O' or a different entity type, and we were in an entity, save it
            if current_entity_tokens:
                entity_text = tokenizer.decode(tokenizer.convert_tokens_to_ids(current_entity_tokens))
                predictions.append({"text": entity_text, "type": current_entity_type})
            current_entity_tokens = []
            current_entity_type = None
            
    # Save any lingering entity at the end of the sequence
    if current_entity_tokens:
        entity_text = tokenizer.decode(tokenizer.convert_tokens_to_ids(current_entity_tokens))
        predictions.append({"text": entity_text, "type": current_entity_type})
        
    return predictions

def main():
    """Main inference pipeline."""
    print("--- Starting Inference ---")
    model, tokenizer = load_model_and_tokenizer()
    nlp = spacy.load("en_core_web_sm")

    all_predictions = []
    test_files = os.listdir(config.TEST_XML_DIR)

    for filename in tqdm(test_files, desc="Predicting on Test Articles"):
        if not filename.endswith('.xml'):
            continue
            
        article_id = filename.replace('.xml', '')
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        
        full_text = extract_text_from_xml(file_path)
        if not full_text:
            continue

        article_entities = []
        doc = nlp(full_text)

        # Process sentence by sentence to handle long documents
        for sentence in doc.sents:
            inputs = tokenizer(
                sentence.text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding="max_length"
            ).to(config.DEVICE)
            
            with torch.no_grad():
                logits = model(**inputs).logits
            
            predictions = torch.argmax(logits, dim=2)
            predicted_token_class_ids = predictions[0].tolist()

            tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
            
            found_entities = decode_predictions(tokens, predicted_token_class_ids, tokenizer)
            article_entities.extend(found_entities)

        # Post-process the entities found for this article
        for entity in article_entities:
            # Normalize DOIs
            dataset_id = normalize_doi(entity['text'])
            # The type is already capitalized correctly by our config (e.g., 'primary' -> 'Primary')
            dataset_type = entity['type'].capitalize()
            
            all_predictions.append((article_id, dataset_id, dataset_type))

    # --- Final Formatting ---
    print(f"\nFound {len(all_predictions)} total potential citations.")
    
    # Apply uniqueness rule: (article_id, dataset_id, type) must be unique
    unique_predictions = sorted(list(set(all_predictions)))
    print(f"Found {len(unique_predictions)} unique citations after deduplication.")
    
    # Create submission DataFrame
    submission_df = pd.DataFrame(unique_predictions, columns=['article_id', 'dataset_id', 'type'])
    submission_df.insert(0, 'row_id', range(len(submission_df)))
    
    # Save submission file
    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    print(f"\nSubmission file created successfully at {config.SUBMISSION_FILE}")
    print("Sample of final submission:")
    print(submission_df.head())


if __name__ == "__main__":
    main()