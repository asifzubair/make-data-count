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

if jats_results:
    print(f"SUCCESS: Found {len(jats_results)} potential references for JATS file.")
    print("Sample of resolved references:")
    pprint(jats_results[:3])
    assert len(jats_results) > 0, "Expected to find references in JATS file"
else:
    print("No references found in JATS file.")
    # Depending on expectations, this could be an assertion failure too
    # For now, let's assume some files might legitimately have no refs,
    # but for these specific test files, we expect them.
    assert False, "Expected to find references in JATS file, but none were found."


# --- Test 2: The TEI file ---
print(f"\n--- Testing ReferenceResolver on TEI file: {TEI_ARTICLE_FILENAME} ---")
tei_parser = XMLParser(TEI_ARTICLE_PATH) # Ensure this path is correct for your environment
tei_resolver = ReferenceResolver(tei_parser, nlp)
tei_results = tei_resolver.resolve_references()

if tei_results:
    print(f"SUCCESS: Found {len(tei_results)} potential references for TEI file.")
    print("Sample of resolved references:")
    pprint(tei_results[:3])
    assert len(tei_results) > 0, "Expected to find references in TEI file"
else:
    print("No references found in TEI file.")
    # Similar to JATS, for this specific test file, we expect references.
    assert False, "Expected to find references in TEI file, but none were found."
