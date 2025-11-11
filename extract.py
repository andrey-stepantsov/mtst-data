import re
import pdfplumber

# These are the standard names for the columns, based on the "Cut order" header.
CUT_ORDER_LABELS_LEFT = ["B", "BB", "A", "AA", "AAA", "AAAA"]
CUT_ORDER_LABELS_RIGHT = ["AAAA", "AAA", "AA", "A", "BB", "B"]

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

        # Merge pattern: "10", "&", "under"
        if current == "10" and next_item == "&" and i + 2 < len(items) and items[i+2] == "under":
            items[i] = "10 & under"
            items.pop(i+1)
            items.pop(i+1)
            continue

        # Merge pattern: Age and Gender (e.g., "10", "Girls" or "11-12", "Boys")
        age_pattern = re.compile(r"^\d+(?:-\d+)?$") # Matches "10", "11-12"
        if (age_pattern.match(current) or current == "10 & under") and next_item in ("Girls", "Boys"):
            items[i] = f"{current} {next_item}"
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

    # Check event format
    event = row[6]
    event_pattern = re.compile(r'^\d{2,4}\s+(FR|BK|BR|FL|IM)\s+(SCY|SCM|LCM)$')
    if not event_pattern.match(event):
        return False, f"Invalid event format: {event}"

    standards_left = row[:6]
    standards_right = row[7:]
    time_columns = standards_left + standards_right

    # Check time format
    time_pattern = re.compile(r'^(?:\d{1,2}:)?\d{2}\.\d{2}(?:\s+\*)?$')
    for item in time_columns:
        if item and not time_pattern.match(item):
            return False, f"Invalid time format in standards column: {item}"

    # Convert to seconds for order comparison
    parsed_left = [parse_time_to_seconds(t) for t in standards_left]
    parsed_right = [parse_time_to_seconds(t) for t in standards_right]

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

def parse_and_structure_data(raw_tables):
    """
    Takes raw extracted tables, cleans them, and builds a structured list of data records.
    Each record contains the age/gender context and the standards for an event.
    """
    print("\n--- Parsing and Structuring Data ---")
    structured_data = []
    flagged_rows = []
    
    # State variables to hold the current context
    left_context, right_context = None, None

    for table_idx, table in enumerate(raw_tables):
        for row_idx, raw_row in enumerate(table):
            cleaned = clean_row(raw_row)

            # Skip junk rows
            if is_whitespace_row(cleaned) or \
               is_general_title_row(cleaned) or \
               is_timestamp_row(cleaned) or \
               is_page_number_row(cleaned) or \
               is_cut_order_header_row(cleaned):
                continue

            # Check for age/gender header to update the context
            if is_age_gender_header_row(cleaned):
                left_context = cleaned[0]
                right_context = cleaned[2]
                print(f"Context updated: {left_context} | {right_context}")
                continue

            # Process as a potential data row
            is_valid_data, reason = is_data_row(cleaned)
            if is_valid_data:
                if not left_context or not right_context:
                    reason = "Data row found without age/gender context"
                    flagged_rows.append((cleaned, reason, table_idx, row_idx))
                    continue
                
                event = cleaned[6]
                
                # Create record for the left context (e.g., Girls)
                left_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_LEFT, cleaned[:6]) if time}
                if left_standards:
                    structured_data.append({
                        "age_gender_group": left_context,
                        "event": event,
                        "standards": left_standards
                    })

                # Create record for the right context (e.g., Boys)
                right_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_RIGHT, cleaned[7:]) if time}
                if right_standards:
                    structured_data.append({
                        "age_gender_group": right_context,
                        "event": event,
                        "standards": right_standards
                    })
            else:
                # It's not a header, not data, not junk we know about. Flag it.
                flagged_rows.append((cleaned, reason, table_idx, row_idx))

    if flagged_rows:
        print("\n--- Flagged Rows for Review ---")
        for row, reason, table_idx, row_idx in flagged_rows:
            print(f"Table {table_idx+1}, Row {row_idx+1}: {row} - Reason: {reason}")

    return structured_data

if __name__ == "__main__":
    pdf_file_path = "data/2028-motivational-standards-single-age.pdf"
    raw_tables = extract_tables_from_pdf(pdf_path=pdf_file_path)
    
    if raw_tables:
        structured_data = parse_and_structure_data(raw_tables)
        print(f"\n--- Found {len(structured_data)} structured data records ---")
        
        # Example of how to print the structured data
        for record in structured_data[:5]: # Print first 5 records as a sample
            print(record)
        
        if len(structured_data) > 5:
            print(f"... and {len(structured_data) - 5} more records.")
