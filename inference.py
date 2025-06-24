# inference.py (Version 1.1 - Batched for Speed)

import os
import re
import pandas as pd
from lxml import etree
import torch
import spacy
from tqdm import tqdm
from collections import Counter
from transformers import AutoTokenizer, AutoModelForTokenClassification

# Using a self-contained config
class SimpleConfig:
    FINE_TUNED_MODEL_PATH = '/kaggle/input/finetuned-model-v1/output/scibert-finetuned-final/'
    TEST_XML_DIR = '/kaggle/input/make-data-count-finding-data-references/test/XML/'
    SUBMISSION_FILE = '/kaggle/working/submission.csv'
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    ID_TO_LABEL = {
        0: 'O', 1: 'B-primary', 2: 'I-primary',
        3: 'B-secondary', 4: 'I-secondary',
    }

config = SimpleConfig()


def load_model_and_tokenizer():
    # ... (This function is correct, no changes needed) ...
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
    # ... (This function is correct, no changes needed) ...
    try:
        tree = etree.parse(xml_file_path)
        full_text = tree.xpath("string()")
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        return ""

def normalize_text(text):
    # ... (This function is correct, no changes needed) ...
    return text.strip(" .,;")

def decode_predictions(original_text, offsets, preds):
    # ... (This function is correct, no changes needed) ...
    labels = [config.ID_TO_LABEL.get(p, 'O') for p in preds[:len(offsets)]]
    entity_groups_indices, current_group = [], []
    for i, label in enumerate(labels):
        if offsets[i] == (0,0): continue
        if label[0] in 'BI': current_group.append(i)
        else:
            if current_group: entity_groups_indices.append(current_group)
            current_group = []
    if current_group: entity_groups_indices.append(current_group)
    final_entities = []
    for indices in entity_groups_indices:
        if not indices: continue
        group_labels = [labels[i] for i in indices]
        group_types = [label.split('-')[1] for label in group_labels if '-' in label]
        if not group_types: continue
        final_type = Counter(group_types).most_common(1)[0][0]
        start_char, end_char = offsets[indices[0]][0], offsets[indices[-1]][1]
        entity_text = original_text[start_char:end_char]
        final_entities.append({"text": entity_text, "type": final_type})
    return final_entities


def main():
    """Main inference pipeline with BATCHING for speed."""
    print("--- RUNNING BATCHED INFERENCE SCRIPT (V1.1) ---")
    model, tokenizer = load_model_and_tokenizer()
    nlp = spacy.load("en_core_web_sm")
    all_predictions = []
    test_files = os.listdir(config.TEST_XML_DIR)
    
    # Define a batch size for inference
    INFERENCE_BATCH_SIZE = 16

    for filename in tqdm(test_files, desc="Predicting on Test Articles"):
        if not filename.endswith('.xml'): continue
        article_id = filename.replace('.xml', '')
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        
        full_text = extract_text_from_xml(file_path)
        if not full_text: continue

        doc = nlp(full_text)
        sentences = [s.text for s in doc.sents if len(s.text.strip()) > 5]
        article_entities = []

        # --- THE BATCHING LOGIC ---
        for i in range(0, len(sentences), INFERENCE_BATCH_SIZE):
            batch_sentences = sentences[i : i + INFERENCE_BATCH_SIZE]
            
            inputs = tokenizer(
                batch_sentences,
                return_tensors="pt",
                truncation=True,
                max_length=512, # The tokenizer pads all sentences in the batch to the same length
                padding="max_length",
                return_offsets_mapping=True
            ).to(config.DEVICE)
            
            offsets_batch = inputs.pop("offset_mapping")

            with torch.no_grad():
                logits = model(**inputs).logits
            
            predictions_batch = torch.argmax(logits, dim=2)

            # Now, decode each sentence in the batch
            for j in range(len(batch_sentences)):
                sentence_text = batch_sentences[j]
                sentence_offsets = offsets_batch[j].tolist()
                sentence_preds = predictions_batch[j].tolist()
                
                found_entities = decode_predictions(sentence_text, sentence_offsets, sentence_preds)
                article_entities.extend(found_entities)
        # --- END OF BATCHING LOGIC ---

        for entity in article_entities:
            dataset_id = normalize_text(entity['text'])
            if 'doi.org' in dataset_id:
                dataset_id = "https://"+dataset_id[dataset_id.find("doi.org"):]
            elif dataset_id.lower().startswith("10."):
                dataset_id = f"https://doi.org/{dataset_id}"
            
            dataset_type = entity['type'].capitalize()
            all_predictions.append((article_id, dataset_id, dataset_type))

    unique_predictions = sorted(list(set(all_predictions)))
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