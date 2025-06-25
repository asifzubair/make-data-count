import re
from bs4 import BeautifulSoup
import os
from pprint import pprint
import spacy
from tqdm import tqdm
import logging

from xml_parser import XMLParser

# Configure basic logging for this module if not configured globally
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
# logger = logging.getLogger(__name__) # Using a named logger
# For simplicity in this tool, direct logging.info, assuming a handler is configured.

# --- The ReferenceResolver Class ---

class ReferenceResolver:
    def __init__(self, parser: XMLParser, nlp_model):
        """
        Initializes with a parser object and a spaCy model.
        """
        self.parser = parser
        self.nlp = nlp_model
        self.bib_map = self.parser.get_bibliography_map()
        self.full_text = self.parser.get_full_text()
        self.sentences = list(self.nlp(self.full_text).sents)
        self.document_pointers = self.parser.get_pointer_map() # Updated method name
        
        # Pre-compile regex patterns for efficiency
        self._pre_filter_keywords = ['doi', 'accession', 'available', 'deposited', 'database', 'repository', 'dryad', 'zenodo', 'figshare', 'genbank', 'seanoe']
        self._direct_doi_pattern = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE)

    def _is_candidate(self, sentence_text: str) -> bool:
        """Fast pre-filter to check if a sentence is worth processing further."""
        logging.debug(f"RR: _is_candidate evaluating: '{sentence_text[:100]}...'")
        lower_sentence = sentence_text.lower()
        if any(keyword in lower_sentence for keyword in self._pre_filter_keywords):
            logging.debug(f"RR: _is_candidate: True (keyword match)")
            return True
        if self._direct_doi_pattern.search(lower_sentence):
            logging.debug(f"RR: _is_candidate: True (DOI pattern match)")
            return True
        # Check for bracketed or parenthetical citations (author-year or complex numeric)
        if re.search(r'(\[|\()\s?[\w\s,.-]+(et al|\d{4})[.,]?\s?(\]|\))', lower_sentence):
            logging.debug(f"RR: _is_candidate: True (author-year/complex numeric citation pattern)")
            return True
        # Check for simple numeric bracketed citations like [1], [12], [1, 2]
        if re.search(r'\[\s*\d+(?:\s*,\s*\d+)*\s*\]', lower_sentence):
            logging.debug(f"RR: _is_candidate: True (simple numeric citation pattern)")
            return True
        logging.debug(f"RR: _is_candidate: False")
        return False

    def resolve_references(self) -> list:
        """
        Processes the entire document to find and resolve all references.
        """
        resolved_citations = []
        logging.info(f"RR: Starting resolve_references. Found {len(self.sentences)} sentences. Document pointers available: {len(self.document_pointers)}")
        
        for i, sent in enumerate(self.sentences):
            sentence_text = sent.text
            logging.debug(f"RR: Processing sentence {i+1}/{len(self.sentences)}: '{sentence_text[:100]}...'")

            is_candidate_sentence = self._is_candidate(sentence_text)
            if not is_candidate_sentence:
                logging.debug(f"RR: Sentence {i+1} skipped by _is_candidate.")
                continue

            logging.info(f"RR: Sentence {i+1} IS a candidate. Checking {len(self.document_pointers)} pointers.")

            # Direct DOI detection logic removed as per new strategy.

            # Logic for pointer resolution using self.document_pointers
            for ptr_idx, (target_id, pointer_text_in_document) in enumerate(self.document_pointers.items()):
                logging.debug(f"RR: Sentence {i+1}, Pointer {ptr_idx+1}/{len(self.document_pointers)}: Checking for '{pointer_text_in_document}'")
                # Check if the specific pointer text (e.g., "[1]", "(Author 2020)") appears in the current sentence
                if pointer_text_in_document in sentence_text:
                    logging.info(f"RR: Sentence {i+1}: Found pointer text '{pointer_text_in_document}' targeting bib ID '{target_id}'.")
                    full_ref_text = self.bib_map.get(target_id) # target_id is already clean from parser
                    
                    if full_ref_text:
                        logging.debug(f"RR: Bib entry for '{target_id}': '{full_ref_text[:100]}...'")
                        # Search for a DOI within the full reference text from the map
                        doi_match_in_ref = self._direct_doi_pattern.search(full_ref_text)
                        if doi_match_in_ref:
                            found_doi = doi_match_in_ref.group(0)
                            logging.info(f"RR: DOI '{found_doi}' found in bib entry for '{target_id}'.")
                            # Basic de-duplication
                            is_already_added = False
                            for res_cit in resolved_citations:
                                if res_cit["doi"] == found_doi and \
                                   res_cit["context_sentence"] == sentence_text and \
                                   res_cit["bibliography_entry_text"] == full_ref_text:
                                    is_already_added = True
                                    logging.debug(f"RR: Duplicate citation skipped: DOI '{found_doi}', Context: '{sentence_text[:50]}...'")
                                    break

                            if not is_already_added:
                                citation_data = {
                                    "doi": found_doi,
                                    "context_sentence": sentence_text,
                                    "in_text_citation_string": pointer_text_in_document,
                                    "bibliography_entry_text": full_ref_text,
                                    "target_id_from_bib": target_id
                                }
                                resolved_citations.append(citation_data)
                                logging.info(f"RR: Added resolved citation: {citation_data}")
                        else:
                            logging.debug(f"RR: No DOI found in bib entry for '{target_id}'.")
                    else:
                        logging.warning(f"RR: Pointer target_id '{target_id}' for text '{pointer_text_in_document}' not found in bib_map.")
                # else:
                    # logging.debug(f"RR: Pointer text '{pointer_text_in_document}' not found in current sentence.")
                            
        logging.info(f"RR: resolve_references finished. Total resolved citations: {len(resolved_citations)}")
        return resolved_citations
