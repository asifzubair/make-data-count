# --- Test Block ---
# This new test block iterates over all training XML files to check parser coverage.

TRAIN_XML_DIR = "/kaggle/input/make-data-count-finding-data-references/train/XML"

print("--- Testing XMLParser Class on the full training set ---")

# Find all XML files in the training directory
all_train_files = [f for f in os.listdir(TRAIN_XML_DIR) if f.endswith('.xml')]
total_files = len(all_train_files)
success_count = 0
failed_files = []

# Loop through each file with a progress bar
for filename in tqdm(all_train_files, desc="Processing Training XMLs"):
    file_path = os.path.join(TRAIN_XML_DIR, filename)
    
    # Instantiate the parser for the current file
    parser = XMLParser(file_path)
    
    # Try to get the bibliography map
    bib_map = parser.get_bibliography_map()
    
    if bib_map:
        success_count += 1
    else:
        failed_files.append(filename)

# --- Final Report ---
print("\n" + "="*40)
print("--- XML PARSER COVERAGE REPORT ---")
print(f"Total XML files in training set: {total_files}")
print(f"Successfully parsed bibliographies for: {success_count}")

if total_files > 0:
    coverage_percentage = (success_count / total_files) * 100
    print(f"Parser Coverage: {coverage_percentage:.2f}%")
else:
    print("No files found to calculate coverage.")

if failed_files:
    print(f"\nCould not parse bibliographies for the following {len(failed_files)} files:")
    # Print the first 5 failed files as a sample
    for f in failed_files[:5]:
        print(f"  - {f}")
print("="*40)

