# config.py

import re
import torch
import os

class LLMPipelineConfig:
    """
    Configures the LLM pipeline with customizable parameters and sensible defaults.
    """
    def __init__(self,
                 model_path: str = "/kaggle/input/qwen2.5/transformers/7b-instruct-awq/1",
                 quantization: str = "awq",
                 dtype: str = "half",
                 max_model_len: int = 4096,
                 gpu_memory_utilization: float = 0.95,
                 device: str = "cuda"):

        self.LLM_MODEL_PATH = model_path
        self.LLM_QUANTIZATION_METHOD = quantization
        self.LLM_DTYPE = dtype
        self.LLM_MAX_MODEL_LEN = max_model_len
        self.LLM_GPU_MEMORY_UTILIZATION = gpu_memory_utilization
        
        self.DEVICE = "cuda" if torch.cuda.is_available() and device == "cuda" else "cpu"
        self.TENSOR_PARALLEL_SIZE = torch.cuda.device_count() if self.DEVICE == "cuda" else 1

    # --- Data Paths ---
    TEST_XML_DIR = '/kaggle/input/make-data-count-finding-data-references/test/XML/'
    SUBMISSION_FILE_PATH = '/kaggle/working/submission.csv'
    TRAIN_XML_DIR_DEV = '/kaggle/input/make-data-count-finding-data-references/train/XML/'

    # --- Regex patterns for pre-filtering and validation ---
    DOI_PATTERN = re.compile(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', re.IGNORECASE)
    
    ACCESSION_PATTERNS = [
        re.compile(r'\b(GSE|SRP|EMPIAR|PDB|E-GEOD|IPR|PF|CVCL|SAMN|PRJNA|ERR|SRR|CHEMBL|NM_|NP_)\w+', re.IGNORECASE),
        re.compile(r'\b(PXD|E-PROT)-\d+', re.IGNORECASE),
        re.compile(r'\b\d{1,2}\.\d{2}\.\d{2}\.\d{1,3}\b'), # CATH domain IDs
        re.compile(r'Q\d{4,5}[A-Z]\d?'), # UniProt IDs
        re.compile(r'rs\d+'), # RS IDs
        re.compile(r'pdb\s\w+', re.IGNORECASE), # PDB + 4-char code
        re.compile(r'\b(?:pubmed|pmc|pmid)\s+\d+', re.IGNORECASE), # PubMed IDs
    ]

    REFERENCE_KEYWORDS = {
        'doi', 'accession', 'available', 'deposited', 'database', 'repository', 
        'dryad', 'zenodo', 'figshare', 'genbank', 'seanoe', 'pdb', 'geo', 
        'arrayexpress', 'biosample', 'bioproject', 'massive.ucsd.edu', 
        'chembl', 'dataset', 'reference', 'supplementary material', 
        'supplemental data', 'data in'
    }

"""
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
# We keep this to remember the original source of our model
MODEL_HUB_NAME = 'allenai/scibert_scivocab_cased' 

# NEW: This is the path to our offline Kaggle Model.
# This is what our training and inference code will actually use.
# (Make sure 'scibert-scivocab-cased-offline' matches the name you gave your Kaggle Model)
MODEL_PATH = '/kaggle/input/scibert-scivocab-cased/pytorch/default/1/scibert_offline_model/'

# NEW: Path to our final, fine-tuned model for inference
# (Make sure 'finetuned-model-v1' matches the name of your input folder)
FINE_TUNED_MODEL_PATH = '/kaggle/input/finetuned-model-v1/output/scibert-finetuned-final/'


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
"""