# Original PDF Data Description

The original PDF document contains various tables that are structured using whitespace alignment. These tables may not have explicit borders or gridlines, making them challenging to extract using traditional methods. The goal is to accurately extract these tables while preserving their structure and content.

Each document contains a series of tables that are separated by general title rows, whitespace rows, rows contaning timesamps, page numbering rows, and two different types of subtabe header rows.

## Subtable header "Cut ordrer" rows

A "cut order" header row is always a sequence of text values:

"B", "BB", "A", "AA", "AAA", "AAAA", "Event", "AAAA", "AAA", "AA", "A", "BB", "B"

This row indicates the reader the values to the left of the "Event" column will be in the descending order, and the values to the right will be in ascending order.

## Subtable header "Age and Gender" rows

The "Age and Gender" header row contains information about the age and gender of the atheletes for which data provided in the following data rows. The age could be described either by a number, a dash separated number pair, or a text value of "10 & under". The gender is indicated by words "Girls" or "Boys". Examples of such header rows include:

- "10 & under Girls, 10 & under Boys"
- "11-12 Girls, 11-12 Boys"
- "11 Girls, 11 Boys"

## Event column

The "Event" column contains the name of the swimming event. The event names may include various distances and styles, such as "50 FR LCM", "100 BK SCY", "200 IM LCM", etc.

The pattern of the event names is always of 3 parts as follows:

- A numeric distance value (e.g., 50, 100, 200, 400, 800, 1500)
- A style abbreviation (e.g., FR for Freestyle, BK for Backstroke, BR for Breaststroke, FL for Butterfly, IM for Individual Medley)
- A pool type abbreviation (e.g., LCM for Long Course Meters, SCY for Short Course Yards)

## Standards columns

The standards columns contain time values that represent the motivational standards for each event. The time values are formatted as "M:SS.ss" or "SS.ss", where "M" is minutes, "SS" is seconds, and "ss" is hundredths of a second. Some cells may be empty, indicating that no standard is provided for that specific cut or event.

There always 12 standards columns in total, 6 to the left of the "Event" column and 6 to the right, corresponding to the cut order described in the "Cut order" header row.

The asterisk symbol (*) may appear next to some time values, following the value, indicating a special note or condition associated with that standard. The asterisk should be preserved during the extraction process.

## Staddards sanity check

Each data row should contain exactly 13 cells: 12 standards cells and 1 event cell. The event cell should always be located in the middle of the row, with 6 standards cells to its left and 6 standards cells to its right. If a row does not conform to this structure, it should be flagged for review.

In a given row, the time values in the left 6 standards cells should be in descending order (from fastest to slowest), while the time values in the right 6 standards cells should be in ascending order (from slowest to fastest). Empty cells should be ignored when performing this check. If the order is not maintained, the row should be flagged for review. A rows contaning blank event cell should also be flagged for review.

## Data to ignore

General Title rows, whitespace rows, rows contaning timestamps, and page numbering rows should be ignored during the extraction process. The general title rows typically contain text "USA Swimming 2024-2028 Motivational Standards". The page numbering rows contain text in a form of a pattern "Page K of N" where "K" and "N" are integer numbers.
