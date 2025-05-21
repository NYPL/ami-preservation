#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

def load_markdown(path):
    return path.read_text(encoding='utf-8')

def save_markdown(path, content):
    path.write_text(content, encoding='utf-8')

def check_heading_structure(lines):
    issues = []
    last_level = 0
    for i, line in enumerate(lines):
        if line.startswith('#'):
            level = len(re.match(r'#+', line).group())
            if last_level and abs(level - last_level) > 1:
                issues.append((i + 1, f"Skipped heading level from {last_level} to {level}: {line.strip()}"))
            last_level = level
            if i > 0 and lines[i - 1].strip() != "":
                issues.append((i + 1, f"Missing blank line before heading: {line.strip()}"))
    return issues

def check_spacing_rules(lines):
    issues = []
    for i, line in enumerate(lines[:-1]):
        if line.strip() == '' and lines[i + 1].strip() == '':
            issues.append((i + 2, "Multiple blank lines in a row"))
    if lines and lines[-1].strip() == "":
        issues.append((len(lines), "Trailing blank line at end of file"))
    return issues

def check_anchors(lines):
    issues = []
    anchor_set = set()
    for i, line in enumerate(lines):
        if line.startswith('<a name="'):
            match = re.search(r'<a name="([^"]+)">', line)
            if match:
                anchor = match.group(1)
                if '_' in anchor:
                    issues.append((i + 1, f"Inconsistent anchor format (should use kebab-case): {anchor}"))
                if anchor in anchor_set:
                    issues.append((i + 1, f"Duplicate anchor: {anchor}"))
                anchor_set.add(anchor)
    return issues, anchor_set

def check_toc_references(lines, anchors):
    toc_pattern = re.compile(r'- \[.+?\]\(#(.+?)\)')
    issues = []
    for i, line in enumerate(lines):
        matches = toc_pattern.findall(line)
        for m in matches:
            if m not in anchors:
                issues.append((i + 1, f"TOC references missing or unmatched anchor: {m}"))
    return issues

def check_table_alignment(lines):
    issues = []
    table_start = False
    header_cols = 0
    for i, line in enumerate(lines):
        if "|" in line:
            cols = [col.strip() for col in line.split("|") if col.strip()]
            if "---" in line and not table_start:
                header_cols = len(cols)
                table_start = True
            elif table_start:
                if len(cols) != header_cols:
                    issues.append((i + 1, f"Table row column mismatch: expected {header_cols}, got {len(cols)}"))
        else:
            table_start = False
    return issues

def check_list_formatting(lines):
    issues = []
    for i, line in enumerate(lines):
        if line.startswith("\t"):
            issues.append((i + 1, "Tab character used for list indentation"))
        if re.match(r'^\s*[\*-]', line):
            bullet = line.strip()[0]
            if bullet != "*":
                issues.append((i + 1, f"Inconsistent list style, found '{bullet}'"))
    return issues

def check_filename_examples(lines):
    issues = []
    nypl_pattern = re.compile(r'division_[a-z0-9]+_v\d+f?\d*r?\d*_pm\.(mkv|flac|mp4|cue|json)')
    for i, line in enumerate(lines):
        if '```' in line or line.strip().startswith('    '):
            continue  # skip code blocks
        if 'division_' in line and not nypl_pattern.search(line):
            issues.append((i + 1, f"Possible malformed filename example: {line.strip()}"))
    return issues

def clean_markdown(lines):
    cleaned_lines = []
    last_line_blank = False
    anchor_seen = set()
    for i, line in enumerate(lines):
        # Strip trailing whitespace
        line = line.rstrip()

        # Normalize list style to '*'
        if re.match(r'^\s*[\*-]', line):
            line = re.sub(r'^(\s*)[\*-]', r'\1*', line)

        # Remove tab characters from list indent
        line = line.replace('\t', '  ')

        # Normalize anchors to kebab-case
        if line.startswith('<a name="'):
            match = re.search(r'<a name="([^"]+)">', line)
            if match:
                anchor = match.group(1)
                kebab = anchor.replace('_', '-')
                if kebab in anchor_seen:
                    kebab += f"-{i}"
                anchor_seen.add(kebab)
                line = f'<a name="{kebab}"></a>'

        # Ensure blank line before headings
        if line.startswith('#') and cleaned_lines and cleaned_lines[-1].strip() != "":
            cleaned_lines.append("")

        # Collapse multiple blank lines
        if line.strip() == "":
            if not last_line_blank:
                cleaned_lines.append("")
            last_line_blank = True
        else:
            cleaned_lines.append(line)
            last_line_blank = False

    return '\n'.join(cleaned_lines).rstrip() + '\n'

def main():
    parser = argparse.ArgumentParser(description="Enhanced Markdown linter and fixer for NYPL digital asset specs.")
    parser.add_argument("-i", "--input", type=Path, required=True, help="Input Markdown file")
    parser.add_argument("-o", "--output", type=Path, help="Write cleaned Markdown to this file")
    args = parser.parse_args()

    content = load_markdown(args.input)
    lines = content.splitlines()

    issues = []
    issues += check_heading_structure(lines)
    issues += check_spacing_rules(lines)
    anchor_issues, anchors = check_anchors(lines)
    issues += anchor_issues
    issues += check_toc_references(lines, anchors)
    issues += check_table_alignment(lines)
    issues += check_list_formatting(lines)
    issues += check_filename_examples(lines)

    if issues:
        print("Issues found:")
        for line_num, msg in sorted(issues):
            print(f"Line {line_num}: {msg}")
    else:
        print("✅ Your file is all good. No formatting issues found!")

    if args.output:
        cleaned = clean_markdown(lines)
        save_markdown(args.output, cleaned)
        print(f"🧼 Cleaned file written to: {args.output}")

if __name__ == "__main__":
    main()
