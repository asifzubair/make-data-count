# inference_profiler.py

import os
import re
import pandas as pd
from lxml import etree
import torch
import spacy
from tqdm import tqdm
from collections import Counter
from transformers import AutoTokenizer, AutoModelForTokenClassification
import time # Import the time module

class SimpleConfig:
    FINE_TUNED_MODEL_PATH = '/kaggle/input/finetuned-model-v1/output/scibert-finetuned-final/'
    TEST_XML_DIR = '/kaggle/input/make-data-count-finding-data-references/test/XML/'
    SUBMISSION_FILE = '/kaggle/working/submission.csv'
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    ID_TO_LABEL = {0: 'O', 1: 'B-primary', 2: 'I-primary', 3: 'B-secondary', 4: 'I-secondary'}
config = SimpleConfig()

# All helper functions (load_model, extract_text, normalize_text, decode_predictions) remain the same
def load_model_and_tokenizer(): # ... same as before
    model_path=config.FINE_TUNED_MODEL_PATH; print(f"Loading from: {model_path}"); model=AutoModelForTokenClassification.from_pretrained(model_path); tokenizer=AutoTokenizer.from_pretrained(model_path); model.to(config.DEVICE); model.eval(); return model, tokenizer
def extract_text_from_xml(xml_file_path): # ... same as before
    try: tree=etree.parse(xml_file_path); full_text=tree.xpath("string()"); return re.sub(r'\s+',' ',full_text).strip()
    except Exception: return ""
def normalize_text(text): # ... same as before
    return text.strip(" .,;")
def decode_predictions(original_text, offsets, preds): # ... same as before
    labels=[config.ID_TO_LABEL.get(p,'O') for p in preds[:len(offsets)]]; entity_groups_indices,current_group=[],[];
    for i,label in enumerate(labels):
        if offsets[i]==(0,0): continue
        if label[0] in 'BI': current_group.append(i)
        else:
            if current_group: entity_groups_indices.append(current_group)
            current_group=[]
    if current_group: entity_groups_indices.append(current_group)
    final_entities=[];
    for indices in entity_groups_indices:
        if not indices: continue
        group_labels=[labels[i] for i in indices]; group_types=[label.split('-')[1] for label in group_labels if '-' in label]
        if not group_types: continue
        final_type=Counter(group_types).most_common(1)[0][0]; start_char,end_char=offsets[indices[0]][0],offsets[indices[-1]][1]; entity_text=original_text[start_char:end_char]; final_entities.append({"text":entity_text,"type":final_type})
    return final_entities


def main():
    """Main inference pipeline with TIMING PROFILING."""
    print("--- RUNNING PROFILING SCRIPT ---")
    model, tokenizer = load_model_and_tokenizer()
    nlp = spacy.load("en_core_web_sm")
    
    timings = []
    test_files = os.listdir(config.TEST_XML_DIR)

    for filename in tqdm(test_files, desc="Profiling Test Articles"):
        if not filename.endswith('.xml'): continue
        
        # --- Start Timer for entire article ---
        t_article_start = time.time()

        # --- Time XML Parsing ---
        t_xml_start = time.time()
        file_path = os.path.join(config.TEST_XML_DIR, filename)
        full_text = extract_text_from_xml(file_path)
        t_xml_end = time.time()
        if not full_text: continue

        # --- Time spaCy Processing ---
        t_spacy_start = time.time()
        doc = nlp(full_text)
        sentences = [s.text for s in doc.sents if len(s.text.strip()) > 5]
        t_spacy_end = time.time()

        # --- Time Model Inference (batched) ---
        t_inference_start = time.time()
        INFERENCE_BATCH_SIZE = 16
        for i in range(0, len(sentences), INFERENCE_BATCH_SIZE):
            batch_sentences = sentences[i : i + INFERENCE_BATCH_SIZE]
            inputs = tokenizer(batch_sentences, return_tensors="pt", truncation=True, max_length=512, padding="max_length", return_offsets_mapping=True).to(config.DEVICE)
            inputs.pop("offset_mapping") # Not used in this simplified timing
            with torch.no_grad():
                _ = model(**inputs).logits # Just run inference, ignore output for timing
        t_inference_end = time.time()
        
        t_article_end = time.time()

        # Record the timings for this article
        timings.append({
            'xml_parse_time': t_xml_end - t_xml_start,
            'spacy_time': t_spacy_end - t_spacy_start,
            'inference_time': t_inference_end - t_inference_start,
            'total_article_time': t_article_end - t_article_start,
            'num_sentences': len(sentences)
        })

    # --- Print Final Report ---
    print("\n\n--- PROFILING REPORT ---")
    if timings:
        timing_df = pd.DataFrame(timings)
        print("Summary statistics for processing time per article (in seconds):")
        print(timing_df.describe())
    else:
        print("No articles were processed to generate a timing report.")


if __name__ == "__main__":
    main()