# --- Test Block ---

import spacy
from pprint import pprint # Added import
from reference_resolver import ReferenceResolver # Corrected typo
from xml_parser import XMLParser

# Load the spaCy model once
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_sm")

# Define our test files (now local samples)
JATS_ARTICLE_FILENAME = "sample_jats.xml"
JATS_ARTICLE_PATH = JATS_ARTICLE_FILENAME # Assuming it's in the same directory

TEI_ARTICLE_FILENAME = "sample_tei.xml"
TEI_ARTICLE_PATH = TEI_ARTICLE_FILENAME # Assuming it's in the same directory

# --- Test 1: The JATS file ---
print(f"\n--- Testing ReferenceResolver on JATS file: {JATS_ARTICLE_PATH} ---")
jats_parser = XMLParser(JATS_ARTICLE_PATH)
jats_resolver = ReferenceResolver(jats_parser, nlp)
jats_results = jats_resolver.resolve_references()

# Expected fields in each result dictionary (DOI field is no longer guaranteed by ReferenceResolver)
EXPECTED_FIELDS = {"context_sentence", "in_text_citation_string", "bibliography_entry_text", "target_id_from_bib"}

if jats_results:
    print(f"Found {len(jats_results)} resolved references for JATS file (sample_jats.xml).")
    pprint(jats_results[:3])
    assert len(jats_results) == 1, f"Expected 1 resolved reference from JATS sample, got {len(jats_results)}. Results: {jats_results}"
    for result in jats_results:
        assert EXPECTED_FIELDS.issubset(result.keys()), f"JATS result missing expected fields: {result}. Got: {result.keys()}"
        # Specific check for the expected JATS pointer resolution
        if result["target_id_from_bib"] == "r1":
            assert result["in_text_citation_string"] == "[1]", "Incorrect in_text_citation_string for JATS pointer r1"
            assert result["bibliography_entry_text"] == "Reference 1. Another DOI: 10.5678/ref.jats.", "Incorrect bib text for JATS r1"
            assert "This is a JATS article. Here is a direct DOI: 10.1234/jats.example. And a pointer [1] ." in result["context_sentence"]
else:
    print("No references found in JATS file (sample_jats.xml).")
    assert False, "Expected 1 resolved reference from JATS sample, but none were found."


# --- Test 2: The TEI file ---
print(f"\n--- Testing ReferenceResolver on TEI file: {TEI_ARTICLE_FILENAME} ---")
tei_parser = XMLParser(TEI_ARTICLE_PATH)
tei_resolver = ReferenceResolver(tei_parser, nlp)
tei_results = tei_resolver.resolve_references()

if tei_results:
    print(f"Found {len(tei_results)} resolved references for TEI file (sample_tei.xml).")
    pprint(tei_results[:3])
    assert len(tei_results) == 1, f"Expected 1 resolved reference from TEI sample, got {len(tei_results)}. Results: {tei_results}"
    for result in tei_results:
        assert EXPECTED_FIELDS.issubset(result.keys()), f"TEI result missing expected fields: {result}. Got: {result.keys()}"
        # Specific check for the expected TEI pointer resolution
        if result["target_id_from_bib"] == "tei_ref1":
            assert result["in_text_citation_string"] == "(Author, 2023)", "Incorrect in_text_citation_string for TEI pointer tei_ref1"
            assert result["bibliography_entry_text"] == "Author (2023). TEI Reference with DOI 10.9999/tei.ref.doi.", "Incorrect bib text for TEI tei_ref1"
            assert "This is a TEI article. Pointer to ref (Author, 2023) . Direct DOI: 10.1000/tei.example." in result["context_sentence"]
else:
    print("No references found in TEI file (sample_tei.xml).")
    assert False, "Expected 1 resolved reference from TEI sample, but none were found."
