import re
import pdfplumber

def parse_time_to_seconds(time_str):
    """
    Parses a time string (M:SS.ss or SS.ss) into total seconds.
    Handles optional asterisk. Returns float or None if invalid.
    """
    if not time_str:
        return None
    
    time_str = time_str.replace('*', '').strip()
    
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            try:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            except ValueError:
                return None
    else:
        try:
            return float(time_str)
        except ValueError:
            return None

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

def is_whitespace_row(cleaned_row):
    return not cleaned_row

def is_general_title_row(cleaned_row):
    # "USA Swimming 2024-2028 Motivational Standards"
    if len(cleaned_row) == 1:
        return "USA Swimming 2024-2028 Motivational Standards" in cleaned_row[0]
    return False

def is_timestamp_row(cleaned_row):
    # Example: "10/10/2025 12:58:55 AM"
    if len(cleaned_row) == 1:
        timestamp_pattern = r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} (AM|PM)"
        return re.fullmatch(timestamp_pattern, cleaned_row[0]) is not None
    return False

def is_page_number_row(cleaned_row):
    # Example: "Page 1 of 14"
    if len(cleaned_row) == 1:
        page_pattern = r"Page \d+ of \d+"
        return re.fullmatch(page_pattern, cleaned_row[0]) is not None
    return False

def is_cut_order_header_row(cleaned_row):
    expected_cut_order = ["B", "BB", "A", "AA", "AAA", "AAAA", "Event", "AAAA", "AAA", "AA", "A", "BB", "B"]
    return cleaned_row == expected_cut_order

def is_age_gender_header_row(cleaned_row):
    # Examples from OCR output: ["10 Girls", "Event", "10 Boys"], ["11-12 Girls", "Event", "11-12 Boys"]
    if len(cleaned_row) == 3 and cleaned_row[1] == "Event":
        age_gender_pattern = r"(\d+ & under|\d+-\d+|\d+) (Girls|Boys)"
        if re.fullmatch(age_gender_pattern, cleaned_row[0]) and re.fullmatch(age_gender_pattern, cleaned_row[2]):
            return True
    return False

def is_data_row(row):
    """
    Checks if a cleaned row is a valid data row and performs sanity checks.
    Returns (True, None) if valid, or (False, "reason") if invalid.
    """
    if len(row) != 13:
        return False, "Incorrect number of columns"

    # The middle column (index 6) must be the event name.
    event = row[6]
    if not event or not any(char.isalpha() for char in event):
        return False, "Blank or invalid event cell"
    
    standards_left = row[:6]
    standards_right = row[7:]

    # Check if all standards columns contain digits and convert to seconds for comparison
    parsed_left = []
    for item in standards_left:
        if item and not any(char.isdigit() for char in item.replace('*', '')):
            return False, f"Non-time value in left standards column: {item}"
        parsed_left.append(parse_time_to_seconds(item))

    parsed_right = []
    for item in standards_right:
        if item and not any(char.isdigit() for char in item.replace('*', '')):
            return False, f"Non-time value in right standards column: {item}"
        parsed_right.append(parse_time_to_seconds(item))

    # Check descending order for left 6 standards (ignoring None values)
    comparable_left = [t for t in parsed_left if t is not None]
    for i in range(len(comparable_left) - 1):
        if comparable_left[i] < comparable_left[i+1]:
            return False, "Left standards not in descending order"

    # Check ascending order for right 6 standards (ignoring None values)
    comparable_right = [t for t in parsed_right if t is not None]
    for i in range(len(comparable_right) - 1):
        if comparable_right[i] > comparable_right[i+1]:
            return False, "Right standards not in ascending order"
            
    return True, None

def process_and_clean_tables(raw_tables):
    """
    Takes raw extracted tables, cleans them, filters for data rows, and prints them.
    """
    print("\n--- Cleaning Data and Filtering for Data Rows ---")
    all_data_rows = []
    flagged_rows = []
    
    for table_idx, table in enumerate(raw_tables):
        for row_idx, raw_row in enumerate(table):
            cleaned = clean_row(raw_row)

            if is_whitespace_row(cleaned):
                continue
            if is_general_title_row(cleaned):
                print(f"Skipping general title row: {cleaned}")
                continue
            if is_timestamp_row(cleaned):
                print(f"Skipping timestamp row: {cleaned}")
                continue
            if is_page_number_row(cleaned):
                print(f"Skipping page number row: {cleaned}")
                continue
            if is_cut_order_header_row(cleaned):
                print(f"Skipping cut order header row: {cleaned}")
                continue
            if is_age_gender_header_row(cleaned):
                print(f"Skipping age and gender header row: {cleaned}")
                continue

            is_valid_data, reason = is_data_row(cleaned)
            if is_valid_data:
                all_data_rows.append(cleaned)
            else:
                flagged_rows.append((cleaned, reason, table_idx, row_idx))
                # print(f"Flagged row (Table {table_idx+1}, Row {row_idx+1}): {cleaned} - Reason: {reason}")
    
    # Print the cleaned data rows to inspect them
    print("\n--- Valid Data Rows ---")
    for row in all_data_rows:
        print(row)
    
    if flagged_rows:
        print("\n--- Flagged Rows for Review ---")
        for row, reason, table_idx, row_idx in flagged_rows:
            print(f"Table {table_idx+1}, Row {row_idx+1}: {row} - Reason: {reason}")
        
    return all_data_rows

if __name__ == "__main__":
    pdf_file_path = "data/2028-motivational-standards-single-age.pdf"
    raw_tables = extract_tables_from_pdf(pdf_path=pdf_file_path)
    
    if raw_tables:
        cleaned_data = process_and_clean_tables(raw_tables)
        print(f"\nFound {len(cleaned_data)} valid data rows.")
