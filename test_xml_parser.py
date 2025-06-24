# --- Test Block ---
# This new test block iterates over all training XML files to check parser coverage.

# Ensure xml_parser is imported (assuming it's in the same directory or PYTHONPATH)
from xml_parser import XMLParser
import os
from tqdm import tqdm
from collections import Counter

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
# Store more details about failed files: list of tuples (filename, parser_used)
failed_file_details = []

# Counters for parser usage
parser_usage_on_success = Counter()
parser_usage_on_failure = Counter()

if total_files > 0:
    # Loop through each file with a progress bar
    for filename in tqdm(all_train_files, desc="Processing Training XMLs"):
        file_path = os.path.join(TRAIN_XML_DIR, filename)

        # Instantiate the parser for the current file
        parser = XMLParser(file_path) # XMLParser now includes logging for its init

        # Try to get the bibliography map
        bib_map = parser.get_bibliography_map()

        if bib_map:
            success_count += 1
            if parser.parser_used:
                parser_usage_on_success[parser.parser_used] += 1
        else:
            # Record the filename and the parser that was attempted or None if parsing failed early
            failed_file_details.append((filename, parser.parser_used if hasattr(parser, 'parser_used') else 'N/A (init failed)'))
            if hasattr(parser, 'parser_used') and parser.parser_used:
                parser_usage_on_failure[parser.parser_used] += 1
            elif not hasattr(parser, 'parser_used') or parser.soup is None : # File might not exist or couldn't be read
                 parser_usage_on_failure['N/A (file/read error or no parser success)'] +=1


# --- Final Report ---
print("\n" + "="*50)
print("--- XML PARSER COVERAGE REPORT ---")
print(f"Total XML files in training set: {total_files}")
print(f"Successfully parsed bibliographies for: {success_count}")

if total_files > 0:
    coverage_percentage = (success_count / total_files) * 100
    print(f"Parser Coverage: {coverage_percentage:.2f}%")

    print("\n--- Parser Usage Stats (Successful Parses) ---")
    if parser_usage_on_success:
        for parser_name, count in parser_usage_on_success.items():
            print(f"  - {parser_name}: {count} files")
    else:
        print("  No successful parses to report usage stats for.")

else:
    print("No files found to calculate coverage.")

if failed_file_details:
    print(f"\n--- Details for {len(failed_file_details)} Failed Files ---")
    # Print details for the first 10 failed files as a sample, or all if less than 10
    for i, (filename, parser_attempt) in enumerate(failed_file_details):
        if i < 10: # Limit the output for brevity in reports
            print(f"  - File: {filename}, Parser Attempted: {parser_attempt}")
        elif i == 10:
            print(f"  ... and {len(failed_file_details) - 10} more failed files.")
            break

    print("\n--- Parser Usage Stats (Failed Parses) ---")
    if parser_usage_on_failure:
        for parser_name, count in parser_usage_on_failure.items():
            print(f"  - {parser_name}: {count} files")
    else:
        print("  No failed parses to report usage stats for (or parser info was N/A).")

print("="*50)
# Note: The XMLParser class itself now does logging.INFO/WARNING/ERROR for parsing attempts.
# This script's output focuses on the aggregate results and success/failure of get_bibliography_map().

