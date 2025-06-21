# config.py

import torch

# --- File and Directory Paths ---
# Using f-strings for clarity, assuming a standard Kaggle environment
DATA_ROOT = "/kaggle/input/make-data-count-finding-data-references/"
TRAIN_LABELS_PATH = f"{DATA_ROOT}train_labels.csv"
TRAIN_XML_DIR = f"{DATA_ROOT}train/XML/"
TEST_XML_DIR = f"{DATA_ROOT}test/XML/"

# Where to save our outputs
OUTPUT_DIR = "/kaggle/working/output/"
SUBMISSION_FILE = "/kaggle/working/submission.csv"


# --- Model Configuration ---
# The name of the model from the Hugging Face Hub that we plan to use
MODEL_NAME = 'allenai/scibert_scivocab_cased' 


# --- Training Hyperparameters ---
MAX_SEQ_LEN = 512    # Max sequence length for the transformer model
BATCH_SIZE = 8        # Batch size for training. Adjust based on GPU memory.
EPOCHS = 3            # Number of training epochs
LEARNING_RATE = 2e-5  # Learning rate for the AdamW optimizer


# --- Hardware Configuration ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


# --- Labeling Configuration ---
# Mapping labels to integers for our future token classification model
LABEL_MAP = {
    'O': 0,           # Outside of any special token
    'B-primary': 1,   # Beginning of a primary citation
    'I-primary': 2,   # Inside of a primary citation
    'B-secondary': 3, # Beginning of a secondary citation
    'I-secondary': 4, # Inside of a secondary citation
}

# Inverse mapping to convert model predictions back to strings
ID_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}