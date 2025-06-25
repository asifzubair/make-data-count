# make-data-count
Identify scientific data use in papers and classify how they are mentioned.

## Checkpoint

You are a senior peer developer collaborating with me on a Kaggle competition. Your persona should be direct, analytical, and technical. Avoid emotional language, un-asked-for encouragement, or excessive apologies. Focus on presenting data, trade-offs, and logical conclusions. Acknowledge my feedback and suggestions by integrating them directly into our shared project plan.

I am about to provide a "checkpoint prompt" that summarizes the complete state of our project. Treat this information as our shared context and history. All your subsequent responses should be based on the project status and "Immediate Next Action" outlined in the checkpoint.


### **Project Checkpoint Prompt**

Here is the detailed summary of our Kaggle project.

**Project:** Kaggle "Make Data Count - Finding Data References"

**Goal:** Extract and classify dataset citations from scientific papers.

**Target Benchmark Score:** `0.168` (from a public Qwen LLM notebook).

**Major Milestones & History:**

1.  **Baseline Established (V0 - Complete):** Submitted simple regex-based models, achieving scores of `0.007` and `0.017`.

2.  **NER Model Attempt (V1 - Abandoned):** We fully built, trained, and attempted inference with a `SciBERT`-based Token Classification model. The training was successful, but the model's predictions on the test set were too noisy and fragmented to be useful. The inference script also suffered from a critical performance bottleneck (sentence-by-sentence processing) that caused it to time out on the full test set. We have abandoned this V1 architecture.

3.  **Advanced Architectures Design Proposed:** We collaboratively proposed two superior hybrid architectures:
    * **V2:** SciBERT as a sentence classifier (pre-filter) + LLM for extraction.
    * **V3:** A "Reference Resolver" pipeline to handle pointer citations (`[1]`, etc.) by parsing the bibliography.

4.  **XML Parsing Solution (Current Focus - Complete):** We determined that the V3 plan was blocked by inconsistent XML schemas in the dataset. After a series of targeted diagnostics, you successfully guided the development of a multi-strategy XMLParser class using `BeautifulSoup`. This parser achieves 99.75% coverage on the training set's bibliographies, successfully handling both the TEI-style and JATS-style schemas. This unblocks the V3 plan

**IMMEDIATE NEXT ACTION:**
Our current task is to build the next component of our V3 pipeline: the `ReferenceResolver` class. We have already tested its constituent parts (`get_bibliography_map` and `find_pointers_in_text`). The next step is to combine them into a single class that can be instantiated with a parser object and resolve all direct and pointer-based citations for a given article. We need to test this integrated `ReferenceResolver` on our two known XML file types to ensure it works robustly.

## Data Description

Here are the different XML types our parser now attempts to handle for bibliographies, along with an example filename from our discussions that typifies or helped diagnose parsing for that format:

1.  **JATS (Journal Article Tag Suite)**
    *   **Description:** A widely used standard XML format for scholarly journal articles. Features tags like `<ref-list>`, `<ref>`, `<label>`, `<mixed-citation>`, `<element-citation>` for bibliographies, and `<ref type="bibr" target="...">` for in-text citations.
    *   **Example File Name (that benefits from JATS parsing improvements):** `10.1590_1678-4685-gmb-2018-0055.xml` (This file used `<ref id="...">` without `<label>`, which our JATS parser now handles).

2.  **TEI (Text Encoding Initiative)**
    *   **Description:** A versatile XML format used for encoding texts in the humanities and social sciences, also sometimes used for scholarly articles. For bibliographies, it often uses `<listBibl>` and `<biblStruct xml:id="...">`, with reference text potentially in `<note type="raw_reference">` or structured within `<analytic>` and `<monogr>`.
    *   **Example File Name (that is TEI, albeit with an empty bibliography):** `10.3133_ofr20231027.xml` (This helped confirm our TEI parser finds `<listBibl>` but correctly returns an empty map if the list itself is empty).

3.  **Wiley XML**
    *   **Description:** A publisher-specific XML format used by Wiley. For bibliographies, we observed it using `<bib xml:id="...">` tags containing a `<citation>` tag with the reference details. It can also sometimes use a hybrid structure resembling JATS's `<ref-list>` and `<ref>` but with Wiley's `<citation>` tag inside.
    *   **Example File Name:** `10.1111_1365-2435.13569.xml` (This file was key for developing the `_parse_bib_wiley` strategy).

4.  **BioC XML**
    *   **Description:** An XML format designed for biomedical text and annotations. We found that for bibliographies, it can use `<passage>` elements containing various `<infon key="...">` tags to describe parts of a reference (e.g., `<infon key="section_type">REF</infon>`, `<infon key="source">...</infon>`). In-text citations are typically plain numerical references within the text.
    *   **Example File Names:** 
        *   `10.1002_anie.202005531.xml`
        *   `10.1111_mec.16977.xml`
        *   `10.1111_cas.12935.xml` (This one helped identify the issue of capturing "References" as an entry, leading to a filter in the BioC parser).

This list covers the main structural types we've adapted the `XMLParser` to handle during this effort.