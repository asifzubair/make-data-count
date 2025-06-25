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

            # Find pointer references within the sentence
            # Use BeautifulSoup to parse just the sentence for <ref> tags
            sent_soup = BeautifulSoup(sentence_text, 'html.parser')
            pointer_tags = sent_soup.find_all('ref', attrs={'type': 'bibr'})

            for tag in pointer_tags:
                target_id = tag.get('target')
                if target_id:
                    clean_target_id = target_id.lstrip('#')
                    full_ref_text = self.bib_map.get(clean_target_id)
                    
                    if full_ref_text:
                        # Search for a DOI within the full reference text from the map
                        doi_match_in_ref = self._direct_doi_pattern.search(full_ref_text)
                        if doi_match_in_ref:
                            resolved_citations.append({
                                "context": sentence_text,
                                "id": doi_match_in_ref.group(0),
                                "method": "pointer_resolution"
                            })
                            
        return resolved_citations
