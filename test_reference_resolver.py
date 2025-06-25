# --- Test Block ---

import spacy
from referece_resolver import ReferenceResolver
from xml_parser import XMLParser

# Load the spaCy model once
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_sm")

# Define our test files
JATS_ARTICLE_FILENAME = "10.1002_chem.201903120.xml"
JATS_ARTICLE_PATH = f"/kaggle/input/{JATS_ARTICLE_FILENAME}" 

TEI_ARTICLE_FILENAME = "10.1002_2017jc013030.xml"
TEI_ARTICLE_PATH = f"/kaggle/input/make-data-count-finding-data-references/test/XML/{TEI_ARTICLE_FILENAME}"

# --- Test 1: The JATS file ---
print(f"\n--- Testing ReferenceResolver on JATS file: {JATS_ARTICLE_FILENAME} ---")
jats_parser = XMLParser(JATS_ARTICLE_PATH)
jats_resolver = ReferenceResolver(jats_parser, nlp)
jats_results = jats_resolver.resolve_references()

if jats_results:
    print(f"SUCCESS: Found {len(jats_results)} potential references.")
    print("Sample of resolved references:")
    pprint(jats_results[:3])
else:
    print("No references found in this file.")


# --- Test 2: The TEI file ---
print(f"\n--- Testing ReferenceResolver on TEI file: {TEI_ARTICLE_FILENAME} ---")
tei_parser = XMLParser(TEI_ARTICLE_PATH)
tei_resolver = ReferenceResolver(tei_parser, nlp)
tei_results = tei_resolver.resolve_references()

if tei_results:
    print(f"SUCCESS: Found {len(tei_results)} potential references.")
    print("Sample of resolved references:")
    pprint(tei_results[:3])
else:
    print("No references found in this file.")
