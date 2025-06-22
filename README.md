# make-data-count
Identify scientific data use in papers and classify how they are mentioned.


## Checkpoints

## Jun 22, 8:23am

**Project:** Kaggle "Make Data Count - Finding Data References" Competition.

**Goal:** Build a model to extract dataset citations from scientific papers and classify them as `Primary` or `Secondary`.

**Overall Strategy:** An iterative approach.
1.  **Baselines (Complete):** Established initial scores using simple DOI extraction with 'Secondary' (0.007) and 'Primary' (0.017) labels. Confirmed that the public test set distribution differs from the training set.
2.  **V1 Model (In Progress):** Build a SciBERT Token Classification (NER) model using a single sentence of context. This is our current focus.
3.  **Future Iterations (V2, V3):** Future improvements will include using a wider context window (more sentences) and tackling long-range dependencies (e.g., bibliographic references like `[1]`).

**Current State:**
* All data preparation for the V1 model is **complete**.
* We have created an offline Kaggle Model for `scibert-scivocab-cased`.
* We have created a code dataset containing our modular scripts.
* We have a processed data file, `final_training_data.jsonl`, containing 522 examples with aligned BIO tags.
* We have the complete `train.py` script ready to run.

**IMMEDIATE NEXT ACTION:**
The next step is to create a new Kaggle Notebook with a **GPU accelerator** and **Internet OFF**. This notebook will use our code dataset, our offline model, and our processed data as inputs. The only task of the notebook is to execute the `train.py` script (`!python /path/to/train.py`) to fine-tune the SciBERT model and save the final fine-tuned model files to the output.

---

