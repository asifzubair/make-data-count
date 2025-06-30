# --- Test Block ---
# This new test block iterates over all training XML files to check parser coverage.

# Ensure xml_parser is imported (assuming it's in the same directory or PYTHONPATH)
from xml_parser import XMLParser
import os
from tqdm import tqdm
from collections import Counter
import logging

# Configure basic logging for this script, if XMLParser's logging isn't chatty enough
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Path to the training XML directory (adjust if necessary for Kaggle environment)
# It's good practice to make this configurable if possible, e.g., via an environment variable or argument.
TRAIN_XML_DIR = os.environ.get("TRAIN_XML_DIR", "/kaggle/input/make-data-count-finding-data-references/train/XML")

print(f"--- Testing XMLParser Class on training set from: {TRAIN_XML_DIR} ---")

# Check if the directory exists
if not os.path.isdir(TRAIN_XML_DIR):
    print(f"ERROR: Training XML directory not found at {TRAIN_XML_DIR}")
    print("Please set the TRAIN_XML_DIR environment variable or update the script.")
    # Exit or raise an error if the directory is critical and not found
    # For now, we'll create dummy lists to avoid crashing the rest of the script logic
    all_train_files = []
    total_files = 0
else:
    # Find all XML files in the training directory
    try:
        all_train_files = [f for f in os.listdir(TRAIN_XML_DIR) if f.endswith('.xml')]
    except FileNotFoundError:
        print(f"ERROR: Could not list files in {TRAIN_XML_DIR}. Please check the path and permissions.")
        all_train_files = [] # Ensure it's an empty list to prevent further errors
    total_files = len(all_train_files)

success_count = 0
# Store more details about file processing: list of dictionaries
# Each dict: {'filename': str, 'bs4_parser': str,
#             'bib_map_success': bool, 'bib_format': str or None,
#             'full_text_success': bool, 'full_text_len': int,
#             'pointer_map_success': bool, 'pointer_map_len': int}
processing_results = []

# Counters
bib_extraction_success_count = 0
full_text_success_count = 0
pointer_map_success_count = 0 # Added for this step

parser_usage_stats = Counter() # Overall BS4 parser usage
bib_format_stats = Counter()   # Overall detected bib formats
# Could add counters for pointer types if get_pointer_map provides method details
# For now, just overall success (non-empty map)


if total_files > 0:
    # Loop through each file with a progress bar
    for filename in tqdm(all_train_files, desc="Processing Training XMLs"):
        file_path = os.path.join(TRAIN_XML_DIR, filename)
        parser = XMLParser(file_path)

        result_entry = {
            'filename': filename,
            'bs4_parser': parser.parser_used if parser.parser_used else 'N/A',
            'bib_map_success': False, 'bib_format': None,
            'full_text_success': False, 'full_text_len': 0,
            'pointer_map_success': False, 'pointer_map_len': 0
        }

        if parser.soup is None:
            processing_results.append(result_entry)
            continue

        parser_usage_stats[result_entry['bs4_parser']] += 1

        # 1. Bibliography Map
        bib_map = parser.get_bibliography_map()
        if bib_map:
            bib_extraction_success_count += 1
            result_entry['bib_map_success'] = True
        result_entry['bib_format'] = parser.bibliography_format_used
        if parser.bibliography_format_used:
            bib_format_stats[parser.bibliography_format_used] += 1
        else:
            bib_format_stats['None_Detected'] += 1 # If bib_map is empty, format might be None

        # 2. Full Text Extraction
        full_text = parser.get_full_text()
        if full_text and full_text.strip():
            full_text_success_count += 1
            result_entry['full_text_success'] = True
        result_entry['full_text_len'] = len(full_text)

        # 3. Pointer Map Extraction
        pointer_map = parser.get_pointer_map()
        if pointer_map:
            pointer_map_success_count += 1
            result_entry['pointer_map_success'] = True
        result_entry['pointer_map_len'] = len(pointer_map)

        processing_results.append(result_entry)


# --- Final Report ---
print("\n" + "="*70)
print("--- XML PARSER EXTRACTION REPORT ---")
print(f"Target Directory: {TRAIN_XML_DIR}")
print(f"Total XML files found and attempted: {total_files}")

if total_files > 0:
    print("\n--- Overall Success Rates ---")
    bib_success_rate = (bib_extraction_success_count / total_files) * 100
    print(f"Bibliography Extraction Success: {bib_extraction_success_count}/{total_files} ({bib_success_rate:.2f}%)")

    full_text_success_rate = (full_text_success_count / total_files) * 100
    print(f"Full Text Extraction Success (non-empty): {full_text_success_count}/{total_files} ({full_text_success_rate:.2f}%)")

    pointer_map_success_rate = (pointer_map_success_count / total_files) * 100
    print(f"Pointer Map Extraction Success (non-empty): {pointer_map_success_count}/{total_files} ({pointer_map_success_rate:.2f}%)")

    print("\n--- BS4 Parser Usage (Overall, for files where soup was not None) ---")
    if parser_usage_stats:
        for parser_name, count in parser_usage_stats.items():
            print(f"  - {parser_name}: {count} files")
    else:
        print("  No BS4 parser usage stats to report (or all files failed before BS4 parsing).")

    print("\n--- Detected Bibliography Format (Overall) ---")
    if bib_format_stats:
        for format_name, count in bib_format_stats.items():
            print(f"  - {format_name}: {count} files")
    else:
        print("  No bibliography formats detected.")

else:
    print("No files found to generate a report.")

# Detailed report on files that had issues with any of the extraction steps
files_with_any_failure = [
    r for r in processing_results
    if not r['bib_map_success'] or \
       not r['full_text_success'] or \
       (r['bib_map_success'] and not r['pointer_map_success']) # Pointer map failure is more significant if bib_map was expected
]

if files_with_any_failure:
    print(f"\n--- Details for {len(files_with_any_failure)} Files With One or More Extraction Issues ---")
    # Print details for the first 10 such files
    for i, result in enumerate(files_with_any_failure):
        if i < 10:
            issues = []
            if not result['bib_map_success']:
                issues.append(f"BibMap Fail (format: {result['bib_format'] if result['bib_format'] else 'None'})")
            if not result['full_text_success']:
                issues.append(f"FullText Fail (len: {result['full_text_len']})")
            if not result['pointer_map_success']:
                # Report pointer map "failure" (i.e. empty map) - it's not always an error but good to note.
                # Especially if bib_map was found, as pointers might be expected.
                issues.append(f"PointerMap Empty (len: {result['pointer_map_len']}{', BibSucceed' if result['bib_map_success'] else ''})")

            print(f"  - File: {result['filename']}, BS4: {result['bs4_parser']}, Issues: {'; '.join(issues)}")
        elif i == 10:
            print(f"  ... and {len(files_with_any_failure) - 10} more files with issues.")
            break


print("="*50)
# Note: The XMLParser class itself now does logging.INFO/WARNING/ERROR for parsing attempts.
# This script's output focuses on the aggregate results and success/failure of get_bibliography_map().
