#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Extract environment variables from .zshrc for NYPL AMIP deployment
# Includes all exported variables in a single file
# -----------------------------------------------------------------------------

set -euo pipefail

# Source file (default ~/.zshrc) and output file
tmp_src="${1:-$HOME/.zshrc}"
OUTPUT_FILE="nypl-amip-env.txt"

# Verify source exists
if [[ ! -f "$tmp_src" ]]; then
    echo "Error: $tmp_src not found"
    echo "Usage: $0 [path_to_shell_profile]"
    exit 1
fi

echo "Extracting environment variables from $tmp_src..."

# Pull all export lines
grep -E '^[[:space:]]*export[[:space:]]+[A-Za-z_][A-Za-z0-9_]*=' "$tmp_src" > temp_exports.txt || true

# Start combined output
{
  echo "# NYPL AMIP Environment Variables"
  echo "# Generated on $(date '+%a %b %d %T %Z %Y') from $tmp_src"
  echo "# SENSITIVE - DO NOT commit to version control"
  echo "# Includes both sensitive and non-sensitive variables"
  echo ""
} > "$OUTPUT_FILE"

# Define patterns for variables considered sensitive
sensitive_patterns=(API_KEY SECRET TOKEN PASSWORD PASS KEY CREDENTIAL AUTH PRIVATE)

echo "Processing export statements..."
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  # Remove 'export '
  clean_line="${line#export }"
  var_name="${clean_line%%=*}"

  # Determine sensitivity
  is_sensitive=false
  for pat in "${sensitive_patterns[@]}"; do
    if [[ "$var_name" == *"$pat"* ]]; then
      is_sensitive=true
      break
    fi
  done

  # Append to combined file
  echo "$clean_line" >> "$OUTPUT_FILE"
  if [[ "$is_sensitive" == true ]]; then
    echo "  🔒 $var_name (sensitive)"
  else
    echo "  📝 $var_name"
  fi
done < temp_exports.txt

# Clean up
echo "" && rm -f temp_exports.txt

echo "✅ Extraction complete!"
echo "📄 Output file: $OUTPUT_FILE"
