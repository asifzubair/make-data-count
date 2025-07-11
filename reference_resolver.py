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
        # self.document_pointers is now a list of dicts
        logging.info(f"RR: Starting resolve_references. Document pointers available: {len(self.document_pointers)}")
        
        # The main loop now iterates through the contextual pointers from XMLParser
        for i, pointer_info in enumerate(self.document_pointers):
            target_id = pointer_info["target_id"]
            in_text_citation_string = pointer_info["in_text_citation_string"]
            # context_text is the paragraph-level context from XMLParser
            context_text_from_parser = pointer_info["context_text"]

            logging.debug(f"RR: Processing pointer {i+1}/{len(self.document_pointers)}: target_id='{target_id}', text='{in_text_citation_string}', context='{context_text_from_parser[:100]}...'")

            full_ref_text = self.bib_map.get(target_id)

            if full_ref_text:
                logging.info(f"RR: Bib entry for '{target_id}' (linked by '{in_text_citation_string}') found: '{full_ref_text[:100]}...'")

                # DOI search is removed. We add the entry if the bib_ref_text is found.

                # De-duplication: Check if this exact context, pointer, and bib entry has already been added.
                is_already_added = False
                for res_cit in resolved_citations:
                    if res_cit["target_id_from_bib"] == target_id and \
                       res_cit["in_text_citation_string"] == in_text_citation_string and \
                       res_cit["context_sentence"] == context_text_from_parser and \
                       res_cit["bibliography_entry_text"] == full_ref_text: # Check all key fields
                        is_already_added = True
                        logging.debug(f"RR: Duplicate resolved reference skipped: TargetID: {target_id}, Pointer: '{in_text_citation_string}'")
                        break

                if not is_already_added:
                    citation_data = {
                        "context_sentence": context_text_from_parser,
                        "in_text_citation_string": in_text_citation_string,
                        "bibliography_entry_text": full_ref_text,
                        "target_id_from_bib": target_id
                        # Optional: could add pointer_info["citation_tag_name"], pointer_info["citation_tag_attributes"]
                    }
                    resolved_citations.append(citation_data)
                    logging.info(f"RR: Added resolved link: TargetID='{target_id}', Pointer='{in_text_citation_string}', Context='{context_text_from_parser[:50]}...'")
            else:
                logging.warning(f"RR: Pointer target_id '{target_id}' for in-text string '{in_text_citation_string}' not found in bib_map.")
                            
        logging.info(f"RR: resolve_references finished. Total resolved links: {len(resolved_citations)}")
        return resolved_citations
