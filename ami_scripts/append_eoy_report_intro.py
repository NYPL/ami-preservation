#!/usr/bin/env python3

import argparse
from PyPDF2 import PdfReader, PdfWriter
import os

def append_intro_to_pdf(intro_pdf, stats_pdf, output_pdf):
    reader_intro = PdfReader(intro_pdf)
    reader_stats = PdfReader(stats_pdf)
    writer = PdfWriter()

    # Add all pages from the intro PDF
    for page in reader_intro.pages:
        writer.add_page(page)

    # Add all pages from the stats PDF
    for page in reader_stats.pages:
        writer.add_page(page)

    with open(output_pdf, "wb") as f_out:
        writer.write(f_out)

    print(f"Output PDF saved as: {output_pdf}")

def main():
    parser = argparse.ArgumentParser(description="Append an introductory PDF to an existing PDF report.")
    parser.add_argument("-i", "--intro", required=True, help="Path to the introductory PDF file")
    parser.add_argument("-s", "--stats", required=True, help="Path to the statistics PDF file")
    parser.add_argument("-o", "--output", help="Output PDF file path", default=None)

    args = parser.parse_args()

    if not args.output:
        # Default output path on the user's desktop
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        stats_filename = os.path.basename(args.stats)
        # Assume PDF extension and append '_w_Intro' before the extension
        output_filename = stats_filename.replace(".pdf", "_w_Intro.pdf")
        args.output = os.path.join(desktop_path, output_filename)

    append_intro_to_pdf(args.intro, args.stats, args.output)

if __name__ == "__main__":
    main()
