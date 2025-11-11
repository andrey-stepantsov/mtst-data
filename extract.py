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

def extract_lines_from_pdf(pdf_path):
    """
    Extracts text lines from each page of a PDF, preserving layout.
    Returns a single flat list of all text lines.
    """
    print(f"Extracting text lines from: {pdf_path}")
    all_lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                print(f"Processing page {i+1}...")
                # Using extract_text_lines with layout=True is key.
                # It preserves horizontal spacing, which helps differentiate columns.
                page_lines = page.extract_text_lines(layout=True, strip=True)
                for line in page_lines:
                    all_lines.append(line['text'])
    except Exception as e:
        print(f"An error occurred during extraction: {e}")
    return all_lines

def clean_row(items):
    """
    Cleans a list of string items by merging known multi-part patterns.
    This version builds a new list, which is safer and cleaner.
    """
    if not items:
        return []

    new_items = []
    i = 0
    time_pattern = re.compile(r"^(?:\d{1,2}:)?\d{2}\.\d{2}$")

    while i < len(items):
        # Merge pattern: Event name split across three cells (e.g., "50", "FR", "SCY")
        if (i + 2 < len(items) and
                items[i].isdigit() and
                items[i+1] in ("FR", "BK", "BR", "FL", "IM") and
                items[i+2] in ("SCY", "SCM", "LCM")):
            new_items.append(f"{items[i]} {items[i+1]} {items[i+2]}")
            i += 3
            continue

        # Merge pattern: Time split across two cells (e.g., "2", ":17.99")
        if i + 1 < len(items) and items[i].isdigit() and items[i+1].startswith(':'):
            new_items.append(items[i] + items[i+1])
            i += 2
            continue

        # Merge pattern: Time followed by a "*"
        if i + 1 < len(items) and time_pattern.match(items[i]) and items[i+1] == '*':
            new_items.append(f"{items[i]} *")
            i += 2
            continue
        
        # If no pattern matches, just append the current item.
        new_items.append(items[i])
        i += 1
    return new_items

def is_whitespace_row(line_text):
    """Checks if a line string is effectively empty."""
    return not line_text.strip()

def is_general_title_row(line_text):
    """Checks for the main title string in a raw row."""
    row_str = line_text
    return "USA Swimming 2024-2028 Motivational Standards" in row_str

def is_timestamp_row(line_text):
    """Checks for a timestamp string in a raw row."""
    row_str = line_text
    timestamp_pattern = r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} (AM|PM)"
    return re.search(timestamp_pattern, row_str) is not None

def is_page_number_row(line_text):
    """Checks for a page number string in a raw row."""
    row_str = line_text
    page_pattern = r"Page \d+ of \d+"
    return re.search(page_pattern, row_str) is not None

def is_cut_order_header_row(cleaned_row):
    """
    Checks if a cleaned row is a "Cut order" header.
    It can be a 13-element list with "Event" or a 12-element list without it.
    """
    expected_with_event = ["B", "BB", "A", "AA", "AAA", "AAAA", "Event", "AAAA", "AAA", "AA", "A", "BB", "B"]
    expected_without_event = ["B", "BB", "A", "AA", "AAA", "AAAA", "AAAA", "AAA", "AA", "A", "BB", "B"]
    
    return cleaned_row == expected_with_event or cleaned_row == expected_without_event


def parse_age_gender_header(line_text):
    """
    Parses a line string to see if it's an age/gender header.
    If it is, returns (left_context, right_context). Otherwise, (None, None).
    Example format: "10 Girls      Event      10 Boys"
    """
    # This pattern is more flexible about the spacing around "Event"
    age_gender_pattern = r"(\d+ & under|\d+-\d+|\d+)\s+(Girls|Boys)"
    full_pattern = re.compile(f"^{age_gender_pattern}\s+Event\s+{age_gender_pattern}$")
    
    match = full_pattern.match(line_text.strip())
    if match:
        # Reconstruct the full context strings
        left_context = f"{match.group(1)} {match.group(2)}"
        right_context = f"{match.group(3)} {match.group(4)}"
        return left_context, right_context
        
    return None, None

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

def parse_and_structure_data(text_lines):
    """
    Takes a list of raw text lines, classifies each line, and builds a
    structured list of data records.
    """
    print("\n--- Parsing and Structuring Data ---")
    structured_data = []
    flagged_rows = []
    
    # State variables to hold the current context
    left_context, right_context = None, None

    for line_idx, line_text in enumerate(text_lines):
        # 1. Check for junk rows on the raw line string.
        if is_whitespace_row(line_text) or \
           is_general_title_row(line_text) or \
           is_timestamp_row(line_text) or \
           is_page_number_row(line_text):
            continue

        # 2. Check for age/gender header on the raw line string.
        new_left, new_right = parse_age_gender_header(line_text)
        if new_left:
            left_context, right_context = new_left, new_right
            print(f"Context updated: {left_context} | {right_context}")
            continue

        # 3. If not a junk/context row, split into items and clean them.
        items = line_text.split()
        cleaned = clean_row(items)

        if not cleaned:
            continue

        # 4. Check for the "Cut order" header on the cleaned row.
        if is_cut_order_header_row(cleaned):
            continue

        # 5. Process as a potential data row.
        is_valid_data, reason = is_data_row(cleaned)
        if is_valid_data:
            if not left_context or not right_context:
                reason = "Data row found without age/gender context"
                flagged_rows.append((cleaned, reason, line_idx + 1))
                continue
            
            event = cleaned[6]
            
            left_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_LEFT, cleaned[:6]) if time}
            if left_standards:
                structured_data.append({
                    "age_gender_group": left_context,
                    "event": event,
                    "standards": left_standards
                })

            right_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_RIGHT, cleaned[7:]) if time}
            if right_standards:
                structured_data.append({
                    "age_gender_group": right_context,
                    "event": event,
                    "standards": right_standards
                })
        else:
            # It's not a header, not data, not junk we know about. Flag it.
            flagged_rows.append((cleaned, reason, line_idx + 1))

    if flagged_rows:
        print("\n--- Flagged Rows for Review ---")
        for row, reason, line_num in flagged_rows:
            print(f"Line {line_num}: {row} - Reason: {reason}")

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
