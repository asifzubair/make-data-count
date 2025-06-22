import os
import pandas as pd
import re
from lxml import etree
import spacy # Using spaCy for robust sentence splitting
from tqdm import tqdm

# Import settings from our config file
import config 

# --- Text Extraction (similar to our baseline) ---
def extract_text_from_xml(xml_file_path):
    try:
        tree = etree.parse(xml_file_path)
        full_text = tree.xpath("string()")
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        return ""

# --- Our New Function ---
def find_label_and_context(article_text, dataset_label):
    """
    Finds the start and end position of a dataset label within a text 
    and returns the sentence(s) it appears in.
    
    Args:
        article_text (str): The full text of the scientific paper.
        dataset_label (str): The dataset identifier string we are looking for.
        
    Returns:
        A dictionary containing the context and span, or None if not found.
    """
    
    # Use regex to find the label. `re.escape` handles special characters in the label.
    # `\b` ensures we match whole words to avoid matching "123" inside "GSE12345".
    match = re.search(r'\b' + re.escape(dataset_label) + r'\b', article_text, re.IGNORECASE)
    
    if not match:
        return None # Label not found in the text
        
    # If we found it, get the character start and end positions
    span_start, span_end = match.span()
    
    # Now, find the full sentence containing this span
    # We will use spaCy for accurate sentence splitting
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(article_text)
    
    for sentence in doc.sents:
        # Check if the found span is within the character range of this sentence
        if sentence.start_char <= span_start and span_end <= sentence.end_char:
            return {
                "label_span": (span_start, span_end),
                "context_sentence": sentence.text,
                "found_text": match.group(0)
            }
            
    return None # Should be rare, but possible if sentence logic fails

def process_data():
    print("Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    print("Loading training labels...")
    labels_df = pd.read_csv(config.TRAIN_LABELS_PATH)
    labels_df = labels_df[labels_df['type'] != 'Missing'].copy()

    print("Reading and caching all training article texts...")
    article_texts = {}
    # Note: If memory becomes an issue on a huge dataset, we could read files one-by-one inside the main loop.
    # For this dataset, caching in memory is faster.
    for article_file in tqdm(os.listdir(config.TRAIN_XML_DIR), desc="Reading XMLs"):
        article_id = article_file.replace('.xml', '')
        file_path = os.path.join(config.TRAIN_XML_DIR, article_file)
        article_texts[article_id] = extract_text_from_xml(file_path)

    print("\nStarting optimized extraction process...")
    processed_data = []
    found_count = 0
    not_found_count = 0
    
    # --- The Main Optimization ---
    # Group labels by article so we only process each article once.
    grouped_labels = labels_df.groupby('article_id')

    for article_id, group in tqdm(grouped_labels, desc="Processing Articles"):
        # Get the cached text for the current article
        article_text = article_texts.get(article_id)
        if not article_text:
            # This article's text couldn't be loaded, so all its labels are "not found"
            not_found_count += len(group)
            continue
            
        # Process the entire article with spaCy ONCE
        doc = nlp(article_text)
        sentences = list(doc.sents) # Get a list of sentences

        # Now, loop through all labels associated with THIS article
        for _, row in group.iterrows():
            dataset_label = row['dataset_id']
            
            # Use regex to find the label within the full text
            match = re.search(re.escape(dataset_label), article_text, re.IGNORECASE)
            
            if not match:
                not_found_count += 1
                continue

            # Find the sentence containing the match from our pre-processed list
            span_start, span_end = match.span()
            found_context = None
            for sentence in sentences:
                if sentence.start_char <= span_start and span_end <= sentence.end_char:
                    found_context = sentence.text
                    break # Found the sentence, no need to look further

            if found_context:
                found_count += 1
                processed_data.append({
                    'article_id': article_id,
                    'dataset_id': dataset_label,
                    'dataset_type': row['type'],
                    'label_span': (span_start, span_end),
                    'context_sentence': found_context,
                    'found_text': match.group(0)
                })
            else:
                # This case is rare but could happen if a match spans sentence boundaries
                not_found_count += 1

    print("\n--- Processing Complete ---")
    print(f"Successfully found context for {found_count} labels.")
    print(f"Could not find {not_found_count} labels in their article text.")
    
    if processed_data:
        processed_df = pd.DataFrame(processed_data)
        save_path = os.path.join(config.OUTPUT_DIR, 'processed_training_data.csv')
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        processed_df.to_csv(save_path, index=False)
        print(f"\nProcessed data saved to {save_path}")
        print("Sample of processed data:")
        print(processed_df.head())
    else:
        print("\nNo data was processed successfully.")

if __name__ == "__main__":
    process_data()
