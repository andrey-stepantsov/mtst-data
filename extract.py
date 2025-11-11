import pdfplumber
import pprint

def extract_tables_from_pdf(pdf_path):
    """
    Extracts tables from each page of a PDF file using pdfplumber
    and prints the raw extracted data.
    """
    print(f"Extracting tables from: {pdf_path}")
    all_extracted_tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                print(f"\n--- Page {i+1} ---")
                tables = page.extract_tables()
                if tables:
                    print(f"Found {len(tables)} table(s) on page {i+1}.")
                    for j, table in enumerate(tables):
                        print(f"Table {j+1} on page {i+1}:")
                        pprint.pprint(table)
                        all_extracted_tables.append(table)
                else:
                    print(f"No tables found on page {i+1}.")
    except Exception as e:
        print(f"An error occurred: {e}")
    return all_extracted_tables

if __name__ == "__main__":
    pdf_file_path = "data/2028-motivational-standards-single-age.pdf"
    extract_tables_from_pdf(pdf_file_path)
