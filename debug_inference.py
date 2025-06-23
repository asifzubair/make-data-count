# debug_inference.py

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
import config # Assumes config.py is in the same directory

def debug_single_sentence():
    """
    Loads the model and runs prediction on one hardcoded sentence to see the raw output.
    """
    # --- 1. Load Model and Tokenizer ---
    model_path = config.FINE_TUNED_MODEL_PATH
    print(f"--- Loading Model and Tokenizer from {model_path} ---")
    model = AutoModelForTokenClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model.to(config.DEVICE)
    model.eval()

    # --- 2. Define a single, problematic sentence ---
    # We'll use a sentence that should contain one of the DOIs from your last output.
    sentence_text = "Further data can be found at https://doi.org/10.1007/s00265-016-2240-x."
    print(f"\n--- Debugging Sentence ---\n'{sentence_text}'\n")

    # --- 3. Tokenize and Predict ---
    inputs = tokenizer(sentence_text, return_tensors="pt").to(config.DEVICE)
    token_ids = inputs["input_ids"][0]
    tokens = tokenizer.convert_ids_to_tokens(token_ids)

    with torch.no_grad():
        logits = model(**inputs).logits
    
    predictions = torch.argmax(logits, dim=2)
    predicted_label_ids = predictions[0].tolist()

    # --- 4. Print the Detailed Results ---
    print(f"{'TOKEN':<25} | {'PREDICTED LABEL ID':<20} | {'PREDICTED LABEL NAME'}")
    print("-" * 70)

    for token, label_id in zip(tokens, predicted_label_ids):
        # We only care about the tokens within the original sentence, not padding
        if token in [tokenizer.cls_token, tokenizer.sep_token, tokenizer.pad_token]:
            continue
            
        label_name = config.ID_TO_LABEL.get(label_id, "!!! UNKNOWN ID !!!")
        
        # Highlight the important ones
        if label_name != 'O':
            print(f"-> {token:<22} | {label_id:<20} | {label_name}")
        else:
            print(f"   {token:<22} | {label_id:<20} | {label_name}")

if __name__ == '__main__':
    debug_single_sentence()