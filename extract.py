import re
import pdfplumber
import json
import argparse
import logging

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
    logging.info(f"Extracting text lines from: {pdf_path}")
    all_lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                logging.info(f"Processing page {i+1}...")
                # Using extract_text_lines with layout=True is key.
                # It preserves horizontal spacing, which helps differentiate columns.
                page_lines = page.extract_text_lines(layout=True, strip=True)
                for line in page_lines:
                    all_lines.append(line['text'])
    except Exception as e:
        logging.error(f"An error occurred during extraction: {e}")
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
                items[i+1] in ("FR", "BK", "BR", "FL", "IM", "FR-R", "MED-R") and
                items[i+2] in ("SCY", "SCM", "LCM")):
            new_items.append(f"{items[i]} {items[i+1]} {items[i+2]}")
            i += 3
            continue

        # Merge pattern: Time split across two cells (e.g., "2", ":17.99")
        if i + 1 < len(items) and items[i].isdigit() and items[i+1].startswith(':'):
            merged_time = items[i] + items[i+1]
            i += 2
            # Check if the next item is an asterisk
            if i < len(items) and items[i] == '*':
                merged_time += " *"
                i += 1
            new_items.append(merged_time)
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
    return "motivational" in line_text.lower()

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
    age_gender_pattern = r"(\d+ & over|\d+ & under|\d+-\d+|\d+)\s+(Girls|Boys)"
    full_pattern = re.compile(rf"^{age_gender_pattern}\s+(?:Event\s+)?{age_gender_pattern}$")
    
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
    event_pattern = re.compile(r'^\d{2,4}\s+(FR|BK|BR|FL|IM|FR-R|MED-R)\s+(SCY|SCM|LCM)$')
    if not event_pattern.match(event):
        return False, f"Invalid event format: {event}"

    standards_left = row[:6]
    standards_right = row[7:]
    time_columns = standards_left + standards_right

    # Check time format
    time_pattern = re.compile(r'^(?:\d{1,2}:)?\d{2}\.\d{2}(?:\s*\*)?$')
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
    logging.info("\n--- Parsing and Structuring Data ---")
    structured_data = []
    flagged_rows = []
    
    # State variables to hold the current context
    left_context, right_context = None, None

    i = 0
    while i < len(text_lines):
        line_text = text_lines[i]

        # 1. Check for junk rows on the raw line string.
        if is_whitespace_row(line_text):
            i += 1
            continue
        if is_general_title_row(line_text):
            i += 1
            continue
        if is_timestamp_row(line_text):
            i += 1
            continue
        if is_page_number_row(line_text):
            i += 1
            continue

        # 2. Check for age/gender header on the raw line string.
        new_left, new_right = parse_age_gender_header(line_text)
        if new_left:
            left_context, right_context = new_left, new_right
            logging.info(f"Context updated: {left_context} | {right_context}")
            i += 1
            continue

        # 3. If not a junk/context row, split into items and clean them.
        items = line_text.split()
        cleaned = clean_row(items)

        if not cleaned:
            i += 1
            continue

        # --- START: New logic to handle split relay rows ---
        # A split relay row's first part is expected to have 6 standards left,
        # 2 event parts (distance and type), and 6 standards right, totaling 14 elements.
        is_split_relay_part1 = (
            len(cleaned) == 14 and
            cleaned[6].isdigit() and
            cleaned[7] in ("FR-R", "MED-R")
        )

        if is_split_relay_part1 and i + 1 < len(text_lines):
            next_line_text = text_lines[i+1]
            cleaned_next_row = clean_row(next_line_text.split())
            if len(cleaned_next_row) == 1 and cleaned_next_row[0] in ("SCY", "SCM", "LCM"):
                course = cleaned_next_row[0]
                event_str = f"{cleaned[6]} {cleaned[7]} {course}"
                
                # Reconstruct the row with the merged event
                # This combines the distance and type at indices 6 and 7 with the course.
                # The result will be a 13-element row, matching is_data_row's expectation.
                merged_row = cleaned[:6] + [event_str] + cleaned[8:]
                cleaned = merged_row
                i += 1 # Increment to skip the course line we just consumed
        # --- END: New logic ---

        # 4. Check for the "Cut order" header on the cleaned row.
        if is_cut_order_header_row(cleaned):
            i += 1
            continue

        # 5. Process as a potential data row.
        is_valid_data, reason = is_data_row(cleaned)
        if is_valid_data:
            if not left_context or not right_context:
                reason = "Data row found without age/gender context"
                flagged_rows.append((cleaned, reason, i + 1))
                i += 1
                continue
            
            event = cleaned[6]
            
            # Split contexts into age and gender
            left_age, left_gender = left_context.rsplit(' ', 1)
            right_age, right_gender = right_context.rsplit(' ', 1)

            left_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_LEFT, cleaned[:6]) if time}
            if left_standards:
                structured_data.append({
                    "age": left_age,
                    "gender": left_gender,
                    "event": event,
                    "standards": left_standards
                })

            right_standards = {label: time for label, time in zip(CUT_ORDER_LABELS_RIGHT, cleaned[7:]) if time}
            if right_standards:
                structured_data.append({
                    "age": right_age,
                    "gender": right_gender,
                    "event": event,
                    "standards": right_standards
                })
        else:
            # It's not a header, not data, not junk we know about. Flag it.
            flagged_rows.append((cleaned, reason, i + 1))
        
        i += 1 # Main loop increment

    if flagged_rows:
        logging.warning("\n--- Flagged Rows for Review ---")
        for row, reason, line_num in flagged_rows:
            logging.warning(f"Line {line_num}: {row} - Reason: {reason}")

    return structured_data

def main():
    """
    Main function to parse command-line arguments and run the extraction process.
    """
    parser = argparse.ArgumentParser(description="Extract motivational standards from a USA Swimming PDF.")
    parser.add_argument("input_pdf", help="Path to the input PDF file.")
    parser.add_argument("output_json", help="Path for the output JSON file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output for debugging.")
    args = parser.parse_args()

    # Configure logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    # Use a basic format that doesn't include the log level name for cleaner output
    logging.basicConfig(level=log_level, format='%(message)s')

    text_lines = extract_lines_from_pdf(pdf_path=args.input_pdf)
    
    if text_lines:
        structured_data = parse_and_structure_data(text_lines)
        print(f"\n--- Found {len(structured_data)} structured data records ---")
        
        # Write the structured data to a JSON file
        try:
            with open(args.output_json, 'w') as f:
                json.dump(structured_data, f, indent=4)
            print(f"Successfully wrote {len(structured_data)} records to {args.output_json}")
        except Exception as e:
            print(f"An error occurred while writing to JSON file: {e}")

if __name__ == "__main__":
    main()
