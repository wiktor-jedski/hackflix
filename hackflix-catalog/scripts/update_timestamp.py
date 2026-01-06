#!/usr/bin/env python3
"""
Update last_updated timestamp in catalog.json

Automatically updates the timestamp to current UTC time in ISO 8601 format.
Run this before committing changes to catalog.json.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def update_timestamp(catalog_path: str = "catalog.json") -> bool:
    """
    Update the last_updated timestamp in catalog.json

    Args:
        catalog_path: Path to catalog.json file

    Returns:
        True if successful, False otherwise
    """
    catalog_file = Path(catalog_path)

    if not catalog_file.exists():
        print(f"❌ Error: Catalog file not found: {catalog_path}")
        return False

    try:
        # Load catalog
        with open(catalog_file, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        # Get old timestamp
        old_timestamp = catalog.get('last_updated', 'unknown')

        # Generate new timestamp (UTC, ISO 8601 format)
        new_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Update timestamp
        catalog['last_updated'] = new_timestamp

        # Write back to file (pretty-printed with 2-space indent)
        with open(catalog_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
            f.write('\n')  # Add trailing newline

        print(f"✅ Updated timestamp in {catalog_path}")
        print(f"   Old: {old_timestamp}")
        print(f"   New: {new_timestamp}")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in catalog file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        catalog_path = sys.argv[1]
    else:
        catalog_path = "catalog.json"

    success = update_timestamp(catalog_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
