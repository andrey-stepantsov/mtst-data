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

def test_is_general_title_row():
    assert is_general_title_row("USA Swimming 2024-2028 Single Age Motivational Standards") is True
    assert is_general_title_row("Some other title") is False

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
