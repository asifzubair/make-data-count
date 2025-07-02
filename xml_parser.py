import re
from bs4 import BeautifulSoup, Doctype
import bs4 # Added for bs4.element.Tag
import os
from pprint import pprint
from tqdm import tqdm # Should be used by the calling script if looping, not by parser itself
import logging
from abc import ABC, abstractmethod
import copy # Added for deepcopy

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Abstract Base Class for Specific Parsers ---
class BaseSpecificXMLParser(ABC):
    def __init__(self, soup: BeautifulSoup | None, xml_path: str, parser_used_for_soup: str | None):
        self.soup = soup
        self.xml_path = xml_path
        self.parser_used_for_soup = parser_used_for_soup
        self._bib_map_cache = None
        self._pointer_map_cache = None # List[dict]
        self._full_text_cache = None
        # self._title_cache = None # For future use
        # self._authors_cache = None # For future use

    @abstractmethod
    def parse_bibliography(self) -> dict:
        pass

    @abstractmethod
    def extract_full_text_excluding_bib(self) -> str:
        pass

    @abstractmethod
    def extract_pointers_with_context(self) -> list[dict]:
        pass

    def _find_contextual_parent_text(self, tag, max_depth=5) -> str:
        context_parent_tags = ['p', 'div', 'li', 'section', 'article-section', 'body', 'article-body', 'text', 'abstract', 'caption', 'title']
        current_tag = tag
        for _ in range(max_depth):
            parent = current_tag.parent
            if not parent: break
            if parent.name and parent.name.lower() in context_parent_tags:
                return ' '.join(parent.get_text(separator=' ', strip=True).split())
            current_tag = parent
        if tag.parent: # Fallback to immediate parent
            return ' '.join(tag.parent.get_text(separator=' ', strip=True).split())
        return ' '.join(tag.get_text(separator=' ', strip=True).split()) # Fallback to tag itself if no parent

# --- Concrete Parser Implementations ---
class JATSParser(BaseSpecificXMLParser):
    def parse_bibliography(self) -> dict:
        if not self.soup: return {}
        bibliography_map = {}
        ref_list = self.soup.find('ref-list')
        if not ref_list: return {}
        references = ref_list.find_all('ref')
        for ref in references:
            key = None
            label_element = ref.find('label')
            if label_element and label_element.text: key = label_element.text.strip().strip('.')
            if not key:
                ref_id = ref.get('id')
                if ref_id: key = ref_id.strip()
            if key:
                citation_element = ref.find('mixed-citation') or ref.find('element-citation')
                if citation_element:
                    bibliography_map[key] = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
        return bibliography_map

    def extract_full_text_excluding_bib(self) -> str:
        if not self.soup: return ""
        # Work on a copy of the soup to safely decompose elements
        temp_soup_for_text = BeautifulSoup(str(self.soup), self.parser_used_for_soup)

        # Remove all ref-list tags first, wherever they might be
        for ref_list_tag in temp_soup_for_text.find_all('ref-list'):
            ref_list_tag.decompose()

        body_content_parts = []
        body_element = temp_soup_for_text.find('body')
        if body_element:
            body_content_parts.append(body_element.get_text(separator=' ', strip=True))

        article_text_element = temp_soup_for_text.find('article-text')
        if article_text_element:
            # Avoid double-counting if article_text_element is the body or inside it
            if not body_element or (body_element and not body_element.find(lambda tag: tag == article_text_element)):
                 body_content_parts.append(article_text_element.get_text(separator=' ', strip=True))

        if not body_content_parts: # If no body or article-text, use root (with front/back potentially removed)
            front_matter = temp_soup_for_text.find('front')
            if front_matter: front_matter.decompose()
            # Back matter decomposition needs to be careful not to remove Data Availability Statements if they are there
            # For JATS, DAS is often <sec sec-type="data-availability"> or <notes notes-type="data-availability">
            # These are often children of <back> but not <ref-list>
            # So, only remove <ref-list> from <back>, not the whole <back>
            # This is already handled by the global ref-list removal above.
            body_content_parts.append(temp_soup_for_text.get_text(separator=' ', strip=True))

        return ' '.join(part.strip() for part in body_content_parts if part.strip()).strip()

    def extract_pointers_with_context(self) -> list[dict]:
        if not self.soup: return []
        pointers_list = []
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = f"[{target_id.lstrip('#')}]"
                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id.lstrip('#'), "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text, "citation_tag_name": tag.name, "citation_tag_attributes": tag.attrs
                })
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}): # Fallback
            target = tag.get('target')
            if target:
                target_id = target.lstrip('#')
                if not any(p['target_id'] == target_id and p['citation_tag_name'] == 'xref' for p in pointers_list):
                    text = tag.get_text(separator=' ', strip=True)
                    if not text.strip(): text = f"[{target_id}]"
                    context_text = self._find_contextual_parent_text(tag)
                    pointers_list.append({
                        "target_id": target_id, "in_text_citation_string": ' '.join(text.split()),
                        "context_text": context_text, "citation_tag_name": tag.name, "citation_tag_attributes": tag.attrs
                    })
        return pointers_list

class TEIParser(BaseSpecificXMLParser):
    def parse_bibliography(self) -> dict:
        if not self.soup: return {}
        bibliography_map = {}
        bib_list = self.soup.find('listBibl')
        if not bib_list: return {}
        references = bib_list.find_all('biblStruct')
        for ref in references:
            ref_id = ref.get('xml:id')
            note = ref.find('note', attrs={'type': 'raw_reference'})
            if ref_id and note:
                raw_ref_text = note.get_text(separator=' ', strip=True)
                if raw_ref_text: bibliography_map[ref_id] = re.sub(r'\s+', ' ', raw_ref_text).strip()
        return bibliography_map

    def extract_full_text_excluding_bib(self) -> str:
        if not self.soup: return ""
        text_element = self.soup.find('text')
        if text_element:
            temp_text_element = BeautifulSoup(str(text_element), self.parser_used_for_soup)
            for list_bibl_tag in temp_text_element.find_all('listBibl'): list_bibl_tag.decompose()
            body_element = temp_text_element.find('body')
            if body_element: return ' '.join(body_element.get_text(separator=' ', strip=True).split())
            return ' '.join(temp_text_element.get_text(separator=' ', strip=True).split())
        return ""

    def extract_pointers_with_context(self) -> list[dict]:
        if not self.soup: return []
        pointers_list = []
        for tag_name in ['ref', 'ptr']: # Check both <ref> and <ptr>
            for tag in self.soup.find_all(tag_name):
                target = tag.get('target')
                if target and target.startswith('#'):
                    target_id = target.lstrip('#')
                    # Avoid adding duplicate if ref already processed this target_id for ptr
                    if tag_name == 'ptr' and any(p['target_id'] == target_id for p in pointers_list): continue

                    text = tag.get_text(separator=' ', strip=True)
                    if not text.strip(): text = f"[{target_id}]"
                    context_text = self._find_contextual_parent_text(tag)
                    pointers_list.append({
                        "target_id": target_id, "in_text_citation_string": ' '.join(text.split()),
                        "context_text": context_text, "citation_tag_name": tag.name, "citation_tag_attributes": tag.attrs
                    })
        return pointers_list

class WileyParser(BaseSpecificXMLParser):
    def parse_bibliography(self) -> dict:
        if not self.soup: return {}
        bibliography_map = {}
        processed_keys = set()
        direct_bib_tags = self.soup.find_all('bib')
        for bib_tag in direct_bib_tags:
            key = bib_tag.get('xml:id')
            if key:
                citation_element = bib_tag.find('citation') or bib_tag.find('citation-alternatives') and bib_tag.find('citation-alternatives').find('citation')
                if citation_element:
                    bibliography_map[key] = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                    processed_keys.add(key)
        ref_list_tag = self.soup.find('ref-list')
        if ref_list_tag:
            for ref_tag in ref_list_tag.find_all('ref'):
                key = ref_tag.get('id')
                if key and key not in processed_keys:
                    citation_element = ref_tag.find('citation') or ref_tag.find('citation-alternatives') and ref_tag.find('citation-alternatives').find('citation')
                    if citation_element:
                        bibliography_map[key] = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
        if bibliography_map: logger.info(f"WileyParser: Parsed bibliography for {self.xml_path}")
        return bibliography_map

    def extract_full_text_excluding_bib(self) -> str:
        if not self.soup: return ""
        temp_soup = BeautifulSoup(str(self.soup), self.parser_used_for_soup)
        for section in temp_soup.find_all(['ref-list', 'references', 'ce:bibliography', 'bibliography']): section.decompose()
        for component in temp_soup.find_all('component', attrs={'type': 'references'}): component.decompose()
        body_element = temp_soup.find('body')
        if body_element: return ' '.join(body_element.get_text(separator=' ', strip=True).split())
        return ' '.join(temp_soup.get_text(separator=' ', strip=True).split())

    def extract_pointers_with_context(self) -> list[dict]:
        if not self.soup: return []
        pointers_list = []
        def _add_pointer(tag, target_attr_name, id_prefix=''):
            target_val = tag.get(target_attr_name)
            if target_val and (id_prefix == '' or target_val.startswith(id_prefix)):
                target_id = target_val.lstrip(id_prefix)
                text_content = tag.get_text(separator=' ', strip=True)
                if not text_content.strip(): text_content = f"[{target_id}]"
                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id, "in_text_citation_string": ' '.join(text_content.split()),
                    "context_text": context_text, "citation_tag_name": tag.name, "citation_tag_attributes": tag.attrs
                })
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}): _add_pointer(tag, 'rid')
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}): _add_pointer(tag, 'target', '#')
        for tag in self.soup.find_all('link'): _add_pointer(tag, 'href', '#')

        # Fallback for generic <ref target="..."> not already caught
        processed_targets = {p['target_id'] for p in pointers_list if p['citation_tag_name'] == 'ref'}
        for tag in self.soup.find_all('ref'):
            if tag.attrs.get('type') == 'bibr': continue
            target = tag.get('target')
            if target and target.startswith('#') and re.match(r'#([a-zA-Z0-9\-_.:]+)', target):
                if target.lstrip('#') not in processed_targets:
                     _add_pointer(tag, 'target', '#')
        return pointers_list

class BioCParser(BaseSpecificXMLParser):
    def parse_bibliography(self) -> dict:
        if not self.soup: return {}
        bibliography_map = {}
        passages = self.soup.find_all('passage')
        ref_counter = 0
        for passage in passages:
            is_reference_passage = False; passage_infons = {}
            for infon in passage.find_all('infon'):
                key = infon.get('key')
                if key:
                    passage_infons[key] = infon.text.strip()
                    if key == 'section_type' and infon.text.strip().upper() == 'REF': is_reference_passage = True
            if is_reference_passage:
                text_content_str = ' '.join(passage.find('text').get_text(separator=' ', strip=True).split()) if passage.find('text') else ""
                source = passage_infons.get('source', '')
                if not source and text_content_str.lower().startswith("see ref") and len(passage_infons) < 3: continue
                # ... (rest of BioC bib parsing logic as before) ...
                ref_parts = []
                authors = passage_infons.get('authors_str'); title = passage_infons.get('title', ''); year = passage_infons.get('year')
                fpage = passage_infons.get('fpage'); lpage = passage_infons.get('lpage')
                if authors: ref_parts.append(authors)
                if title: ref_parts.append(title)
                if source: ref_parts.append(f"Source: {source}")
                if year: ref_parts.append(f"Year: {year}")
                if fpage and lpage: ref_parts.append(f"pp. {fpage}-{lpage}")
                elif fpage: ref_parts.append(f"p. {fpage}")
                # Simplified text_content_str addition
                if text_content_str and not any(text_content_str in part for part in ref_parts if part) and \
                   not any(val_info == text_content_str for val_info in passage_infons.values() if val_info):
                     ref_parts.append(text_content_str)

                if not ref_parts and not source and not title and not year : continue
                ref_string = ". ".join(filter(None, ref_parts))
                if not ref_string.strip(): continue

                common_bib_titles_to_skip = ["references", "bibliography", "literature cited", "reference list"]
                if ref_string.strip().lower() in common_bib_titles_to_skip and \
                   not (passage_infons.get('source') or passage_infons.get('year') or passage_infons.get('fpage') or passage_infons.get('authors_str')):
                    logger.info(f"BioCParser: Skipping likely section title: '{ref_string}' in {self.xml_path}")
                    continue
                ref_counter += 1; bibliography_map[str(ref_counter)] = ref_string
        if bibliography_map: logger.info(f"BioCParser: Parsed bibliography for {self.xml_path} (found {len(bibliography_map)} refs)")
        return bibliography_map

    def extract_full_text_excluding_bib(self) -> str:
        if not self.soup: return ""
        text_parts = []
        for passage in self.soup.find_all('passage'):
            is_ref_passage = any(
                infon.get('key') in ['section_type', 'type'] and infon.text.strip().upper() in ['REF', 'REFERENCES', 'BIBLIOGRAPHY', 'BIBR']
                for infon in passage.find_all('infon')
            )
            if not is_ref_passage and passage.find('text'):
                text_parts.append(passage.find('text').get_text(separator=' ', strip=True))
        return ' '.join(text_parts)

    def extract_pointers_with_context(self) -> list[dict]:
        if not self.soup: return []
        pointers_list = []
        for ann_tag in self.soup.find_all('annotation'):
            is_citation_annotation = False; target_id_from_infon = None; in_text_citation_string = None
            infons = ann_tag.find_all('infon')
            temp_attrs = {infon.get('key'): infon.text for infon in infons if infon.get('key')}
            for infon_tag in infons:
                key_attr = infon_tag.get('key')
                if key_attr == 'type' and infon_tag.text.lower() in ['citation', 'reference', 'bibr', 'ref']: is_citation_annotation = True
                if key_attr in ['referenced_bib_id', 'target_bib_id', 'targetid', 'rid', 'target_id', 'target']:
                    target_id_from_infon = infon_tag.text.strip().lstrip('#')
            if is_citation_annotation and target_id_from_infon:
                text_tag = ann_tag.find('text')
                in_text_citation_string = text_tag.text.strip() if text_tag and text_tag.text.strip() else f"[{target_id_from_infon}]"
                context_text = self._find_contextual_parent_text(ann_tag)
                pointers_list.append({
                    "target_id": target_id_from_infon, "in_text_citation_string": ' '.join(in_text_citation_string.split()),
                    "context_text": context_text, "citation_tag_name": ann_tag.name, "citation_tag_attributes": temp_attrs
                })
        return pointers_list

class GenericFallbackParser(BaseSpecificXMLParser):
    def parse_bibliography(self) -> dict:
        # Tries a sequence of bib parsing strategies.
        # This is effectively what the main XMLParser.get_bibliography_map used to do as its fallback.
        # Order: JATS, TEI, Wiley, BioC
        # This avoids re-implementing all _parse_bib_* methods here or making them static.
        # It creates temporary specific parser instances to attempt parsing.
        if not self.soup: return {}

        parsers_to_try = [JATSParser, TEIParser, WileyParser, BioCParser]
        bib_map = {}
        for parser_class in parsers_to_try:
            # logger.debug(f"GenericFallbackParser: Trying {parser_class.__name__} for bib parsing on {self.xml_path}")
            # We need to pass the soup and other details from the *GenericFallbackParser* instance
            temp_parser = parser_class(self.soup, self.xml_path, self.parser_used_for_soup)
            bib_map = temp_parser.parse_bibliography()
            if bib_map:
                # If a specific parser succeeds, we could assume its type for `bibliography_format_used`
                # This interaction needs to be handled carefully in the main XMLParser class.
                # For now, this method just returns the bib_map. The main XMLParser sets bibliography_format_used.
                logger.info(f"GenericFallbackParser: Bib parsing for {self.xml_path} succeeded using {parser_class.__name__} rules.")
                return bib_map

        logger.warning(f"GenericFallbackParser: No bibliography found using any specific strategy for {self.xml_path}")
        return {}

    def extract_full_text_excluding_bib(self) -> str:
        if not self.soup: return ""
        logger.info(f"GenericFallbackParser: Using generic fallback text extraction for {self.xml_path}")
        if not self.parser_used_for_soup: # Should be set if soup exists
            logging.warning(f"GenericFallbackParser: self.parser_used_for_soup is None for {self.xml_path}. Defaulting to lxml-xml for temp_soup.")
            # This situation implies an issue in XMLParser.__init__ not setting parser_used_for_soup when soup is valid.
            # However, to prevent crash here, we can default, though it might hide the root cause.
            # A better fix would be to ensure parser_used_for_soup is always set if self.soup is not None.
            # For now, this is a defensive measure.
            effective_parser = 'lxml-xml'
        else:
            effective_parser = self.parser_used_for_soup # Not strictly needed if using deepcopy directly on self.soup

        # temp_soup = BeautifulSoup(str(self.soup), effective_parser)
        if not self.soup: return "" # Should be caught by __init__ but defensive
        temp_soup = copy.deepcopy(self.soup) # Use deepcopy

        tags_to_remove_lower = [t.lower() for t in ['ref-list', 'listbibl', 'references', 'bibliography', 'back', 'notes', 'fn-group']]

        # Iterate over all tags and decompose if name matches (case-insensitive)
        # This is more exhaustive than relying on find_all with regex if that was failing.
        temp_soup = copy.deepcopy(self.soup)

        temp_soup = copy.deepcopy(self.soup)

        tags_to_remove_lower = [t.lower() for t in ['ref-list', 'listbibl', 'references', 'bibliography', 'back', 'notes', 'fn-group']]
        decomposed_count = 0

        # Iterate over a list of tags to avoid issues with modifying the tree while iterating
        tags_found_to_decompose = []
        for tag in temp_soup.find_all(True): # Find all tags
            if tag.name and tag.name.lower() in tags_to_remove_lower:
                tags_found_to_decompose.append(tag)

        if tags_found_to_decompose:
            logger.info(f"GenericFallbackParser: Found {len(tags_found_to_decompose)} tags for decomposition: {[t.name for t in tags_found_to_decompose]} in {self.xml_path}")
            for tag_to_decompose in tags_found_to_decompose:
                tag_to_decompose.decompose()
                decomposed_count += 1
        else:
            logger.debug(f"GenericFallbackParser: No tags matched for decomposition in {self.xml_path}")

        return ' '.join(temp_soup.get_text(separator=' ', strip=True).split())

    def extract_pointers_with_context(self) -> list[dict]:
        if not self.soup: return []
        pointers_list = []
        for tag_type, id_attr, id_prefix in [
            (('ref', {'type': 'bibr'}), 'target', '#'),
            (('xref', {'ref-type': 'bibr'}), 'rid', '')
        ]:
            find_args, find_kwargs = (tag_type[0], tag_type[1]) if isinstance(tag_type, tuple) else (tag_type, {})
            for tag in self.soup.find_all(find_args, **find_kwargs):
                target_val = tag.get(id_attr)
                if target_val:
                    target_id = target_val.lstrip(id_prefix)
                    text = tag.get_text(separator=' ', strip=True)
                    if not text.strip(): text = f"[{target_id}]"
                    context_text = self._find_contextual_parent_text(tag)
                    pointers_list.append({
                        "target_id": target_id, "in_text_citation_string": ' '.join(text.split()),
                        "context_text": context_text, "citation_tag_name": tag.name, "citation_tag_attributes": tag.attrs
                    })
        return pointers_list

# --- The XMLParser Class (Facade/Factory) ---
# This class encapsulates all parsing logic for a single XML file.

class XMLParser:
    """
    A robust parser for handling various academic XML formats found in the dataset.
    It initializes with a file path and provides methods to extract key components.
    """
    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.soup = None
        self.parser_used_for_soup = None # Renamed from parser_used for clarity
        self.bibliography_format_used = None # Set by get_bibliography_map based on successful strategy
        self.schema_type = "unknown_or_error"
        self.specific_parser_instance: BaseSpecificXMLParser | None = None

        if not os.path.exists(xml_path):
            logger.warning(f"File not found: {xml_path}")
            return

        try:
            with open(xml_path, 'r', encoding='utf-8') as f: content = f.read()
            try:
                self.soup = BeautifulSoup(content, 'lxml-xml')
                if self.soup and self.soup.find(): self.parser_used_for_soup = 'lxml-xml'
                else: self.soup = None # Ensure soup is None if parsing was not truly successful
            except Exception: self.soup = None
            if self.soup is None:
                self.soup = BeautifulSoup(content, 'html.parser')
                if self.soup and self.soup.find(): self.parser_used_for_soup = 'html.parser'
                else: self.soup = None
            if self.parser_used_for_soup:
                 logger.info(f"Successfully parsed {xml_path} with {self.parser_used_for_soup}")
            else:
                 logger.error(f"Could not parse XML file: {xml_path} with any available BS4 parser.")
                 return # Essential to return if soup is None

        except Exception as e_file:
            logger.error(f"Error reading file {xml_path}: {e_file}")
            return # self.soup remains None

        if self.soup:
            self.schema_type = self._detect_schema()
            logger.info(f"XMLParser: Initialized for {self.xml_path}. Detected schema: {self.schema_type}. BS4 parser: {self.parser_used_for_soup}")

            parser_args = (self.soup, self.xml_path, self.parser_used_for_soup)
            if self.schema_type == "jats": self.specific_parser_instance = JATSParser(*parser_args)
            elif self.schema_type == "tei": self.specific_parser_instance = TEIParser(*parser_args)
            elif self.schema_type == "wiley": self.specific_parser_instance = WileyParser(*parser_args)
            elif self.schema_type == "bioc": self.specific_parser_instance = BioCParser(*parser_args)
            else: # "unknown" or "unknown_or_error" (if soup was valid but schema unknown)
                logger.warning(f"XMLParser: Using GenericFallbackParser for {self.xml_path} due to schema: {self.schema_type}")
                self.specific_parser_instance = GenericFallbackParser(*parser_args)
        else:
            logger.error(f"XMLParser: self.soup is None for {self.xml_path}. Cannot instantiate specific parser.")
            # self.specific_parser_instance remains None

    def _detect_schema(self) -> str:
        """
        Detects the XML schema type based on characteristic tags and DOCTYPE/namespaces.
        Order of checks is important.
        """
        if not self.soup:
            # This case should ideally be handled before calling _detect_schema,
            # as __init__ already checks if self.soup is None.
            # However, as a safeguard:
            logger.error(f"SCHEMA_DETECT ({self.xml_path}): Soup is None at detection time.")
            return 'unknown_or_error'

        # 1. Check DOCTYPE first
        doctype_obj = next((item for item in self.soup.contents if isinstance(item, Doctype)), None)
        if doctype_obj:
            doctype_str = str(doctype_obj).upper()
            if "JATS (Z39.96)" in doctype_str:
                logger.info(f"Schema detected for {self.xml_path}: jats (DOCTYPE JATS (Z39.96))")
                return 'jats'
            if "BIOC.DTD" in doctype_str:
                logger.info(f"Schema detected for {self.xml_path}: bioc (DOCTYPE BioC.dtd)")
                return 'bioc'

        # 2. Check root element name and namespaces
        root_element = self.soup.find()
        if root_element:
            root_name_lower = root_element.name.lower() if root_element.name else ""
            root_xmlns = root_element.get('xmlns', '').lower()
            if root_name_lower == 'tei' and root_xmlns == "http://www.tei-c.org/ns/1.0":
                logger.info(f"Schema detected for {self.xml_path}: tei (root <tei> with TEI namespace)")
                return 'tei'
            wiley_ns = "http://www.wiley.com/namespaces/wiley"
            if root_xmlns == wiley_ns:
                 logger.info(f"Schema detected for {self.xml_path}: wiley (root element with Wiley namespace)")
                 return 'wiley'
            if self.soup.find(lambda tag: isinstance(tag, bs4.element.Tag) and tag.name and tag.name.lower() == 'component' and tag.get('xmlns', '').lower() == wiley_ns):
                logger.info(f"Schema detected for {self.xml_path}: wiley (<component> with Wiley namespace)")
                return 'wiley'

        # 3. Fallback to tag-based heuristics
        # BioC heuristic
        passages = self.soup.find_all('passage')
        is_bioc_struct = self.soup.find('collection') and self.soup.find('document') and passages
        if passages:
            for passage in passages:
                for infon in passage.find_all('infon'):
                    key = infon.get('key')
                    if key in ['section_type', 'type'] and infon.text.strip().upper() in ['REF', 'REFERENCES', 'BIBLIOGRAPHY', 'BIBR']:
                        if not (self.soup.find('journal-meta') or self.soup.find('component', attrs={'type': 'references'})):
                            logger.info(f"Schema detected for {self.xml_path}: bioc (heuristic: REF passage infon)")
                            return 'bioc'
        if is_bioc_struct and self.soup.find('infon'):
            if not (self.soup.find('journal-meta') or self.soup.find('component', attrs={'type': 'references'}) or \
                    self.soup.find('listBibl') or self.soup.find('ref-list')):
                logger.info(f"Schema detected for {self.xml_path}: bioc (heuristic: general BioC structure)")
                return 'bioc'
        # Wiley heuristic
        if self.soup.find('component', attrs={'type': 'references'}):
            logger.info(f"Schema detected for {self.xml_path}: wiley (heuristic: component type='references')")
            return 'wiley'
        if self.soup.find('doi_batch_id'):
            logger.info(f"Schema detected for {self.xml_path}: wiley (heuristic: doi_batch_id)")
            return 'wiley'
        # JATS heuristic
        has_ref_list = self.soup.find('ref-list')
        has_structural_jats = (self.soup.find('front') and self.soup.find('article-meta') and self.soup.find('journal-meta')) or \
                              self.soup.find('article', attrs={'article-type': True})
        if has_ref_list and has_structural_jats:
            logger.info(f"Schema detected for {self.xml_path}: jats (heuristic: ref-list and JATS structural tags)")
            return 'jats'
        # TEI heuristic
        if self.soup.find('listBibl') and self.soup.find('teiHeader'):
            logger.info(f"Schema detected for {self.xml_path}: tei (heuristic: listBibl and teiHeader)")
            return 'tei'
        # Wiley <bib xml:id> heuristic
        if self.soup.find('bib', attrs={'xml:id': True}):
            if not (self.soup.find('teiHeader') or has_structural_jats):
                logger.info(f"Schema detected for {self.xml_path}: wiley (heuristic: bib xml:id and not strong TEI/JATS)")
                return 'wiley'
        # JATS-like Wiley or simple JATS fallback
        if has_ref_list and self.soup.find('ref'):
            ref_list_tag = self.soup.find('ref-list')
            if ref_list_tag and (first_ref := ref_list_tag.find('ref')) and first_ref.find('citation'):
                logger.info(f"Schema detected for {self.xml_path}: wiley (heuristic: JATS-like ref-list with <citation>)")
                return 'wiley'
            logger.info(f"Schema detected for {self.xml_path}: jats (heuristic fallback: ref-list and ref tags)")
            return 'jats'
        logger.warning(f"XML schema not confidently detected for {self.xml_path}. Defaulting to 'unknown'.")
        return 'unknown'

    def get_bibliography_map(self) -> dict:
        if not self.specific_parser_instance:
            logger.warning(f"get_bibliography_map: No specific parser for {self.xml_path}")
            return {}
        if self.specific_parser_instance._bib_map_cache is None:
            logger.debug(f"XMLParser: Cache miss for bib_map on {self.xml_path}. Calling specific parser ({self.schema_type}).")
            bib_map_result = self.specific_parser_instance.parse_bibliography()
            self.specific_parser_instance._bib_map_cache = bib_map_result
            # Set bibliography_format_used based on the schema type of the parser that produced the map
            if bib_map_result:
                self.bibliography_format_used = self.schema_type
                # If GenericFallbackParser was used, it might have its own way to report what sub-parser worked.
                # For now, if GenericFallbackParser, this will be 'unknown'.
                if isinstance(self.specific_parser_instance, GenericFallbackParser) and not bib_map_result:
                     # If generic failed, try a hard sequence (this duplicates some logic from old get_bib_map)
                    logging.info(f"GenericFallbackParser failed for bib map on {self.xml_path}, trying sequence.")
                    for schema_name, ConcreteParser in [("jats", JATSParser), ("tei", TEIParser), ("wiley", WileyParser), ("bioc", BioCParser)]:
                        temp_parser = ConcreteParser(self.soup, self.xml_path, self.parser_used_for_soup)
                        bib_map_result = temp_parser.parse_bibliography()
                        if bib_map_result:
                            self.bibliography_format_used = schema_name
                            self.specific_parser_instance._bib_map_cache = bib_map_result # Update cache with successful result
                            logger.info(f"Bib map for {self.xml_path} found by fallback to {schema_name}")
                            break
            else: # No bib map found by the primary specific parser
                self.bibliography_format_used = self.schema_type # or 'none' if schema_type itself was unknown and generic failed
        return self.specific_parser_instance._bib_map_cache if self.specific_parser_instance._bib_map_cache is not None else {}


    def get_full_text(self) -> str:
        if not self.specific_parser_instance:
            logger.warning(f"get_full_text: No specific parser for {self.xml_path}")
            return ""
        if self.specific_parser_instance._full_text_cache is None:
            logger.debug(f"XMLParser: Cache miss for full_text on {self.xml_path}. Calling specific parser ({self.schema_type}).")
            self.specific_parser_instance._full_text_cache = self.specific_parser_instance.extract_full_text_excluding_bib()
        return self.specific_parser_instance._full_text_cache

    def get_pointer_map(self) -> list[dict]:
        if not self.specific_parser_instance:
            logger.warning(f"get_pointer_map: No specific parser for {self.xml_path}")
            return []
        if self.specific_parser_instance._pointer_map_cache is None:
            logger.debug(f"XMLParser: Cache miss for pointer_map on {self.xml_path}. Calling specific parser ({self.schema_type}).")
            self.specific_parser_instance._pointer_map_cache = self.specific_parser_instance.extract_pointers_with_context()
        return self.specific_parser_instance._pointer_map_cache
