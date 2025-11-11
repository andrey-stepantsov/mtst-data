import pdfplumber

def extract_tables_from_pdf(pdf_path):
    """
    Extracts tables from each page of a PDF file using pdfplumber.
    """
    print(f"Extracting tables from: {pdf_path}")
    all_extracted_tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                print(f"Processing page {i+1}...")
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                }
                tables = page.extract_tables(table_settings)
                if tables:
                    # Add all tables found on the page to our list
                    all_extracted_tables.extend(tables)
                else:
                    print(f"No tables found on page {i+1}.")
    except Exception as e:
        print(f"An error occurred during extraction: {e}")
    return all_extracted_tables

def clean_row(row):
    """
    Cleans a single row of data by removing empty items and merging known split-item patterns.
    """
    # 1. Basic cleaning: remove None, strip whitespace, filter empty strings
    items = [item.strip() for item in row if item and item.strip()]
    if not items:
        return []

    # 2. Iteratively merge known split patterns.
    # A while loop is used because we are modifying the list as we iterate.
    i = 0
    while i < len(items) - 1:
        current = items[i]
        next_item = items[i+1]

        # Merge pattern: Event name split across two cells (e.g., "50 FR", "SCY")
        if next_item in ("SCY", "SCM", "LCM") and any(char.isalpha() for char in current):
            items[i] = f"{current} {next_item}"
            items.pop(i+1)
            continue  # Re-check the newly merged item against the next one

        # Merge pattern: Time split across two cells (e.g., "2", ":17.99")
        if current.isdigit() and next_item.startswith(':'):
            items[i] = current + next_item
            items.pop(i+1)
            continue

        # Merge pattern: Time followed by a "*"
        if next_item == '*':
            items[i] = f"{current} *"
            items.pop(i+1)
            continue

        i += 1
    return items

def is_data_row(row):
    """
    Checks if a cleaned row is a valid data row.
    A valid data row has 13 columns: 6 times, 1 event, 6 times.
    """
    if len(row) != 13:
        return False

    # The middle column (index 6) must be the event name.
    event = row[6]
    if not any(char.isalpha() for char in event):
        return False
    
    # All other columns must be times (i.e., contain at least one digit).
    time_columns = row[:6] + row[7:]
    for item in time_columns:
        if not any(char.isdigit() for char in item):
            return False
            
    return True

def process_and_clean_tables(raw_tables):
    """
    Takes raw extracted tables, cleans them, filters for data rows, and prints them.
    """
    print("\n--- Cleaning Data and Filtering for Data Rows ---")
    all_data_rows = []
    for table in raw_tables:
        for row in table:
            cleaned = clean_row(row)
            if is_data_row(cleaned):
                all_data_rows.append(cleaned)
    
    # Print the cleaned data rows to inspect them
    for row in all_data_rows:
        print(row)
        
    return all_data_rows

if __name__ == "__main__":
    pdf_file_path = "data/2028-motivational-standards-single-age.pdf"
    raw_tables = extract_tables_from_pdf(pdf_path=pdf_file_path)
    
    if raw_tables:
        cleaned_data = process_and_clean_tables(raw_tables)
        print(f"\nFound {len(cleaned_data)} valid data rows.")
