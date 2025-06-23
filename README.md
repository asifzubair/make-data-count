# make-data-count
Identify scientific data use in papers and classify how they are mentioned.


## Checkpoint

I am about to provide a detailed "checkpoint prompt" that summarizes the complete state of a previous project we were working on together. Please treat the information within that prompt as our shared history and context. All of your subsequent advice and actions in this conversation should be based on the project status and "Immediate Next Action" outlined in the checkpoint. This will form the foundation for our work today.

### Project Checkpoint Prompt (As of June 23, 2025)

Here is the detailed summary of our Kaggle project.

**(Start of Checkpoint Prompt)**

**Project:** Kaggle "Make Data Count - Finding Data References" Competition.

**Goal:** Build a model to extract dataset citations from scientific papers and classify them as `Primary` or `Secondary`. The evaluation metric is a strict, span-based F1 score.

**Target Benchmark Score:** The highest public score noted so far from an LLM is **0.168** (from a Qwen model), which serves as a long-term target.

**Overall Strategy:** An iterative modeling approach.
1.  **V1 Model (Complete):** Fine-tune a specialized NER model (SciBERT) on single-sentence contexts to establish a strong, efficient baseline.
2.  **Future Iterations (V2, V3):** Explore more advanced techniques based on V1's performance, such as using wider context windows or handling long-range dependencies.

**Current State & History:**
* **Baselines:** We submitted two simple regex-based baselines, scoring 0.007 (all `Secondary`) and 0.017 (all `Primary`).
* **Data Pipeline:** We successfully built a pipeline to extract sentences (`data_preparation.py`) and then transform them into a model-ready format with BIO tags (`ner_data_processor.py`), resulting in `final_training_data.jsonl` with 522 examples.
* **Model Training:** We successfully trained our V1 SciBERT model for 3 epochs. The training was successful, with a final validation loss of ~0.048. The resulting fine-tuned model files have been saved as a Kaggle Model.
* **Inference Debugging:** We went through an extensive, multi-step debugging process for our inference script. We discovered that our fine-tuned model produces slightly "noisy" or "stuttering" predictions (e.g., missing `B-` tags, or flickering `I-` tag types).
* **Final Solution:** We created a final, robust `inference.py` script that uses a two-stage decoding process (1. Group all adjacent entity tokens, 2. Classify by majority vote) to correctly handle the model's noisy predictions. We have verified this logic with a standalone debug script.

**IMMEDIATE NEXT ACTION:**
The final task for our V1 model is to **run the complete, verified `inference.py` script** in our submission notebook. This will use our fine-tuned model to generate the final `submission.csv` file, which can then be submitted to the competition to get our official V1 score.
