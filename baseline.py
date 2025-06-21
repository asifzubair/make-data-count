# baseline.py

import os
import re
import pandas as pd
from lxml import etree
from tqdm import tqdm

# Import settings from our config file
import config 

# A simple regex to find DOIs. It's not perfect, but it's great for a baseline.
# It looks for '10.' followed by numbers, a slash, and more characters.
DOI_PATTERN = r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b'

def extract_text_from_xml(xml_file_path):
    """
    Parses an XML file and extracts all text content.
    A simplified version for our baseline.
    """
    try:
        tree = etree.parse(xml_file_path)
        # The string() XPath function gets all descendant text, which is perfect for us.
        full_text = tree.xpath("string()") 
        # Clean up whitespace
        return re.sub(r'\s+', ' ', full_text).strip()
    except Exception:
        # Silently fail for now if a file is broken
        return ""

def main():
    """
    Main function to run the baseline pipeline.
    """
    print("Starting baseline model...")
    
    # --- 1. Load Test File Paths ---
    # We only need to process the test XML files
    test_files = [os.path.join(config.TEST_XML_DIR, f) for f in os.listdir(config.TEST_XML_DIR) if f.endswith('.xml')]
    
    print(f"Found {len(test_files)} test XML files to process.")
    
    # --- 2. Process Files and Generate Predictions ---
    predictions = []
    
    for xml_path in tqdm(test_files, desc="Processing test files"):
        # The article_id is the filename without the .xml extension
        article_id = os.path.basename(xml_path).replace('.xml', '')
        
        # Extract all text from the article
        text = extract_text_from_xml(xml_path)
        if not text:
            continue
            
        # Find all DOI matches in the text
        doi_matches = re.finditer(DOI_PATTERN, text, re.IGNORECASE)
        
        # For each DOI found, create a prediction row
        for match in doi_matches:
            found_doi = match.group(0)
            predictions.append({
                "article_id": article_id,
                "dataset_id": f"https://doi.org/{found_doi}", # Format as a full URL
                "type": "Secondary" # Assign the majority class
            })
            
    print(f"Found {len(predictions)} potential DOI mentions in total.")
    
    # --- 3. Create and Save Submission File ---
    if not predictions:
        print("No predictions were made. Creating an empty submission file.")
        submission_df = pd.DataFrame(columns=['row_id', 'article_id', 'dataset_id', 'type'])
    else:
        submission_df = pd.DataFrame(predictions)
        # Ensure no duplicate (article_id, dataset_id) pairs
        submission_df = submission_df.drop_duplicates()
        # Add the row_id column
        submission_df.insert(0, 'row_id', range(len(submission_df)))
    
    submission_df.to_csv(config.SUBMISSION_FILE, index=False)
    
    print(f"\nSubmission file created at: {config.SUBMISSION_FILE}")
    print("Baseline script finished successfully!")
    print("\nSubmission Head:")
    print(submission_df.head())

if __name__ == '__main__':
    main()