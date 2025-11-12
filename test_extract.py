import subprocess
import json
import pytest
from extract import (
    parse_time_to_seconds,
    clean_row,
    is_whitespace_row,
    is_general_title_row,
    is_timestamp_row,
    is_page_number_row,
    is_cut_order_header_row,
    parse_age_gender_header,
    is_data_row,
    parse_and_structure_data,
)

# --- Constants for Data Integrity Checks ---
CUT_ORDER = ["B", "BB", "A", "AA", "AAA", "AAAA"]

EXPECTED_AGES = {
    "2028-motivational-standards-single-age": {
        "10", "11", "12", "13", "14", "15", "16", "17", "18"
    },
    "2028-motivational-standards-age-group": {
        "10 & under", "11-12", "13-14", "15-16", "17-18"
    },
}

# --- Test Utility Functions ---

@pytest.mark.parametrize("time_str, expected", [
    ("1:05.39", 65.39),
    ("59.89", 59.89),
    ("1:05.39*", 65.39),
    ("59.89 *", 59.89),
    ("2:00.00", 120.0),
    ("", None),
    (None, None),
    ("invalid", None),
    ("1:2:3", None),
])
def test_parse_time_to_seconds(time_str, expected):
    assert parse_time_to_seconds(time_str) == expected

@pytest.mark.parametrize("items, expected", [
    # Test event merging
    (["50", "FR", "SCY", "other"], ["50 FR SCY", "other"]),
    # Test time merging with colon
    (["1", ":05.39", "other"], ["1:05.39", "other"]),
    # Test time merging with asterisk
    (["1:05.39", "*", "other"], ["1:05.39 *", "other"]),
    # Test no merging
    (["item1", "item2", "item3"], ["item1", "item2", "item3"]),
    # Test multiple merges
    (["50", "FR", "SCY", "1", ":05.39", "*"], ["50 FR SCY", "1:05.39 *"]),
    ([], []),
])
def test_clean_row(items, expected):
    assert clean_row(items) == expected

# --- Test Row Classification Functions ---

def test_is_whitespace_row():
    assert is_whitespace_row("   \t\n") is True
    assert is_whitespace_row("not empty") is False

@pytest.mark.parametrize("line, expected", [
    ("USA Swimming 2024-2028 Motivational Standards", True),
    ("2028-motivational-standards-age-group", True),
    ("some other title", False),
    ("MOTIVATIONAL", True),
])
def test_is_general_title_row(line, expected):
    assert is_general_title_row(line) == expected

def test_is_timestamp_row():
    assert is_timestamp_row("Generated 09/01/2023 10:30:00 AM") is True
    assert is_timestamp_row("No timestamp here") is False

def test_is_page_number_row():
    assert is_page_number_row("Some text Page 1 of 10") is True
    assert is_page_number_row("Just a page") is False

def test_is_cut_order_header_row():
    with_event = ["B", "BB", "A", "AA", "AAA", "AAAA", "Event", "AAAA", "AAA", "AA", "A", "BB", "B"]
    without_event = ["B", "BB", "A", "AA", "AAA", "AAAA", "AAAA", "AAA", "AA", "A", "BB", "B"]
    invalid = ["B", "BB", "A", "AA", "AAA", "AAAA"]
    assert is_cut_order_header_row(with_event) is True
    assert is_cut_order_header_row(without_event) is True
    assert is_cut_order_header_row(invalid) is False

@pytest.mark.parametrize("line, expected", [
    ("10 Girls      Event      10 Boys", ("10 Girls", "10 Boys")),
    ("11-12 Boys    Event      11-12 Girls", ("11-12 Boys", "11-12 Girls")),
    ("15 & over Girls Event 15 & over Boys", ("15 & over Girls", "15 & over Boys")),
    ("10 & under Girls  10 & under Boys", ("10 & under Girls", "10 & under Boys")), # Without "Event"
    ("Not a header", (None, None)),
])
def test_parse_age_gender_header(line, expected):
    assert parse_age_gender_header(line) == expected

# --- Test Data Validation ---

@pytest.mark.parametrize("row, expected_valid, expected_reason", [
    # Valid row
    (["3:09.09", "2:55.89", "2:42.59", "2:35.99", "2:29.39", "2:22.79", "200 FR SCY", "2:16.19", "2:22.59", "2:35.39", "2:48.19", "3:00.99", "3:13.79"], True, None),
    # Valid row with empty standards
    (["", "2:55.89", "2:42.59", "2:35.99", "2:29.39", "2:22.79", "200 FR SCY", "2:16.19", "2:22.59", "2:35.39", "2:48.19", "3:00.99", ""], True, None),
    # Invalid column count
    (["1:00.00", "200 FR SCY", "1:00.00"], False, "Incorrect number of columns"),
    # Invalid event format
    (["3:09.09", "2:55.89", "2:42.59", "2:35.99", "2:29.39", "2:22.79", "200 FREE SCY", "2:16.19", "2:22.59", "2:35.39", "2:48.19", "3:00.99", "3:13.79"], False, "Invalid event format: 200 FREE SCY"),
    # Invalid time format
    (["3:09.09", "2:55.89", "2:42.59", "2:35.99", "2:29.39", "2:22.79", "200 FR SCY", "2:16", "2:22.59", "2:35.39", "2:48.19", "3:00.99", "3:13.79"], False, "Invalid time format in standards column: 2:16"),
    # Left standards not descending
    (["3:09.09", "2:55.89", "2:42.59", "2:35.99", "2:40.00", "2:22.79", "200 FR SCY", "2:16.19", "2:22.59", "2:35.39", "2:48.19", "3:00.99", "3:13.79"], False, "Left standards not in descending order"),
    # Right standards not ascending
    (["3:09.09", "2:55.89", "2:42.59", "2:35.99", "2:29.39", "2:22.79", "200 FR SCY", "2:16.19", "2:22.59", "2:20.00", "2:48.19", "3:00.99", "3:13.79"], False, "Right standards not in ascending order"),
])
def test_is_data_row(row, expected_valid, expected_reason):
    is_valid, reason = is_data_row(row)
    assert is_valid == expected_valid
    assert reason == expected_reason

# --- Test Main Parsing Logic ---

def test_parse_and_structure_data():
    sample_lines = [
        "USA Swimming 2024-2028 Single Age Motivational Standards", # Title
        "10 Girls      Event      10 Boys", # Context
        "B BB A AA AAA AAAA Event AAAA AAA AA A BB B", # Cut order header (raw)
        "3:09.09 2:55.89 2:42.59 2:35.99 2:29.39 2:22.79 200 FR SCY 2:16.19 2:22.59 2:35.39 2:48.19 3:00.99 3:13.79", # Data
        "   ", # Whitespace
        "This is a flagged row that doesn't match any pattern", # Flagged row
    ]
    
    expected_data = [
        {
            "age": "10", "gender": "Girls", "event": "200 FR SCY",
            "standards": {
                "B": "3:09.09", "BB": "2:55.89", "A": "2:42.59",
                "AA": "2:35.99", "AAA": "2:29.39", "AAAA": "2:22.79"
            }
        },
        {
            "age": "10", "gender": "Boys", "event": "200 FR SCY",
            "standards": {
                "AAAA": "2:16.19", "AAA": "2:22.59", "AA": "2:35.39",
                "A": "2:48.19", "BB": "3:00.99", "B": "3:13.79"
            }
        }
    ]

    structured_data = parse_and_structure_data(sample_lines)
    assert structured_data == expected_data

def test_parse_and_structure_data_age_group():
    """
    Tests the parsing and structuring of data from the age-group PDF format,
    including split relay event rows.
    """
    sample_lines = [
        "USA Swimming 2024-2028 Motivational Standards",  # Title
        "11-12 Girls      Event      11-12 Boys",  # Context
        "B BB A AA AAA AAAA Event AAAA AAA AA A BB B",  # Cut order header
        # Standard individual event row
        "35.59 33.29 30.99 29.89 28.79 27.59 50 FR SCY 27.59 28.79 29.99 31.19 33.59 35.99",
        # Split relay event row
        "2:41.19 * 2:29.69 * 2:18.19 * 2:12.39 * 2:06.69 * 2:00.89 * 200 MED-R 1:55.59 * 2:01.09 * 2:06.59 * 2:12.09 * 2:23.09 * 2:34.09 *",
        "SCY",
    ]

    expected_data = [
        {
            "age": "11-12", "gender": "Girls", "event": "50 FR SCY",
            "standards": {
                "B": "35.59", "BB": "33.29", "A": "30.99",
                "AA": "29.89", "AAA": "28.79", "AAAA": "27.59"
            }
        },
        {
            "age": "11-12", "gender": "Boys", "event": "50 FR SCY",
            "standards": {
                "AAAA": "27.59", "AAA": "28.79", "AA": "29.99",
                "A": "31.19", "BB": "33.59", "B": "35.99"
            }
        },
        {
            "age": "11-12", "gender": "Girls", "event": "200 MED-R SCY",
            "standards": {
                "B": "2:41.19 *", "BB": "2:29.69 *", "A": "2:18.19 *",
                "AA": "2:12.39 *", "AAA": "2:06.69 *", "AAAA": "2:00.89 *"
            }
        },
        {
            "age": "11-12", "gender": "Boys", "event": "200 MED-R SCY",
            "standards": {
                "AAAA": "1:55.59 *", "AAA": "2:01.09 *", "AA": "2:06.59 *",
                "A": "2:12.09 *", "BB": "2:23.09 *", "B": "2:34.09 *"
            }
        }
    ]

    structured_data = parse_and_structure_data(sample_lines)
    assert structured_data == expected_data


@pytest.mark.parametrize("pdf_name", [
    "2028-motivational-standards-single-age",
    "2028-motivational-standards-age-group",
])
def test_end_to_end_extraction(pdf_name, tmp_path):
    """
    Tests the full extraction process from PDF to JSON and compares the
    output to a known-good "golden" file.
    """
    input_pdf = f"data/{pdf_name}.pdf"
    golden_json_path = f"test/data/{pdf_name}.json"
    output_json_path = tmp_path / f"{pdf_name}.json"

    # Run the extraction script as a subprocess
    result = subprocess.run(
        ["python", "extract.py", input_pdf, str(output_json_path)],
        capture_output=True,
        text=True
    )

    # Ensure the script ran successfully
    assert result.returncode == 0, f"Script failed for {pdf_name}: {result.stderr}"
    assert output_json_path.exists(), "Output JSON file was not created."

    # Load the contents of the newly generated JSON file
    with open(output_json_path, 'r') as f:
        generated_data = json.load(f)

    # Load the contents of the "golden" JSON file
    with open(golden_json_path, 'r') as f:
        golden_data = json.load(f)

    # Compare the data
    assert generated_data == golden_data, "Generated JSON does not match the golden file."

@pytest.mark.parametrize("json_file_name", [
    "2028-motivational-standards-single-age",
    "2028-motivational-standards-age-group",
])
def test_data_integrity(json_file_name):
    """
    Loads the golden JSON files and performs data integrity checks:
    1. Times must be monotonically decreasing from B to AAAA.
    2. All expected genders (Girls, Boys) must be present.
    3. All expected age groups for that file type must be present.
    """
    json_path = f"test/data/{json_file_name}.json"
    with open(json_path, 'r') as f:
        data = json.load(f)

    found_genders = set()
    found_ages = set()

    for record in data:
        found_genders.add(record["gender"])
        found_ages.add(record["age"])

        # Check 1: Verify that times are monotonically decreasing
        standards = record["standards"]
        times_in_seconds = [parse_time_to_seconds(standards.get(cut)) for cut in CUT_ORDER]
        
        # Filter out None values for events that don't have all standards
        valid_times = [t for t in times_in_seconds if t is not None]

        for i in range(1, len(valid_times)):
            # Each time must be less than or equal to the previous (slower) one
            assert valid_times[i] <= valid_times[i-1], (
                f"Time standards are not decreasing for {record['age']} {record['gender']} {record['event']}.\n"
                f"  - Got {valid_times[i-1]} for {CUT_ORDER[i-1]}.\n"
                f"  - Got {valid_times[i]} for {CUT_ORDER[i]}."
            )

    # Check 2: Verify all genders are present
    assert found_genders == {"Girls", "Boys"}, f"Missing or unexpected genders in {json_file_name}.json"

    # Check 3: Verify all age groups are present for the file type
    expected_age_set = EXPECTED_AGES[json_file_name]
    assert found_ages == expected_age_set, f"Missing or unexpected age groups in {json_file_name}.json"

