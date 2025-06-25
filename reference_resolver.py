import re
from bs4 import BeautifulSoup
import os
from pprint import pprint
import spacy
from tqdm import tqdm

from xml_parser import XMLParser

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
        lower_sentence = sentence_text.lower()
        if any(keyword in lower_sentence for keyword in self._pre_filter_keywords):
            return True
        if self._direct_doi_pattern.search(lower_sentence):
            return True
        # A simple check for bracketed or parenthetical citations
        if re.search(r'(\[|\()\s?[\w\s,.-]+(et al|\d{4})[.,]?\s?(\]|\))', lower_sentence):
             return True
        return False

    def resolve_references(self) -> list:
        """
        Processes the entire document to find and resolve all references.
        """
        resolved_citations = []
        
        for sent in self.sentences:
            sentence_text = sent.text
            if not self._is_candidate(sentence_text):
                continue

            # Find direct DOIs within the candidate sentence
            for match in self._direct_doi_pattern.finditer(sentence_text):
                resolved_citations.append({
                    "context": sentence_text,
                    "id": match.group(0),
                    "method": "direct_doi"
                })

            # New logic for pointer resolution using self.document_pointers
            for target_id, pointer_text_in_document in self.document_pointers.items():
                # Check if the specific pointer text (e.g., "[1]", "(Author 2020)") appears in the current sentence
                if pointer_text_in_document in sentence_text:
                    full_ref_text = self.bib_map.get(target_id) # target_id is already clean from parser
                    
                    if full_ref_text:
                        # Search for a DOI within the full reference text from the map
                        doi_match_in_ref = self._direct_doi_pattern.search(full_ref_text)
                        if doi_match_in_ref:
                            # Avoid adding duplicate if direct DOI and pointer resolve to same DOI in same sentence
                            # This is a basic check; more sophisticated duplicate handling might be needed
                            is_duplicate = False
                            for res_cit in resolved_citations:
                                if res_cit["id"] == doi_match_in_ref.group(0) and res_cit["context"] == sentence_text:
                                    is_duplicate = True
                                    break
                            if not is_duplicate:
                                resolved_citations.append({
                                    "context": sentence_text,
                                    "id": doi_match_in_ref.group(0),
                                    "method": "pointer_resolution"
                                })
                            
        return resolved_citations
