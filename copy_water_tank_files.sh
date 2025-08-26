#!/bin/bash

# === Usage ===
if [ -z "$1" ]; then
  echo "Usage: $0 <destination_prefix> [manifest_file] [--quiet]"
  exit 1
fi

DEST_PREFIX="$1"
MANIFEST=""
QUIET=false

# === Parse optional arguments ===
for arg in "${@:2}"; do
  if [[ "$arg" == "--quiet" ]]; then
    QUIET=true
  elif [[ "$arg" == *.manifest ]]; then
    MANIFEST="$arg"
  fi
done

# === Auto-detect manifest file if not provided ===
if [ -z "$MANIFEST" ]; then
  matches=(*.manifest)
  if [ ${#matches[@]} -eq 0 ]; then
    echo "❌ No .manifest file found in current directory."
    exit 1
  elif [ ${#matches[@]} -gt 1 ]; then
    echo "❌ Multiple .manifest files found. Please specify one explicitly."
    printf ' - %s\n' "${matches[@]}"
    exit 1
  else
    MANIFEST="${matches[0]}"
    $QUIET || echo "📄 Using manifest: $MANIFEST"
  fi
else
  $QUIET || echo "📄 Using specified manifest: $MANIFEST"
fi

$QUIET || echo "📦 Destination prefix: $DEST_PREFIX"

# === Locate start of plugin file list ===
START_LINE=$(grep -n "^##### List all plugin files" "$MANIFEST" | cut -d: -f1)
if [ -z "$START_LINE" ]; then
  echo "❌ Manifest header not found in $MANIFEST."
  exit 1
fi

$QUIET || echo "🔍 Found plugin file list starting at line $START_LINE"

# === Process plugin file entries ===
tail -n +$((START_LINE + 1)) "$MANIFEST" | while read -r line; do
  # Skip empty lines
  if [ -z "$line" ]; then
    continue
  fi

  FILE=$(echo "$line" | awk '{print $1}')
  REL_PATH=$(echo "$line" | awk '{print $2}')
  DEST_DIR="$DEST_PREFIX/$REL_PATH"

  $QUIET || echo "📁 Preparing to copy '$FILE' → '$DEST_DIR/'"

  mkdir -p "$DEST_DIR"
  $QUIET || echo "✅ Ensured directory exists: $DEST_DIR"

  if [ -f "$FILE" ]; then
    cp "$FILE" "$DEST_DIR/"
    $QUIET || echo "📤 Copied '$FILE' to '$DEST_DIR/'"
  else
    echo "⚠️ File not found: $FILE — skipping"
  fi
done

$QUIET || echo "🎉 All done!"
