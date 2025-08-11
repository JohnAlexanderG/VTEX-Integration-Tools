#!/usr/bin/env python3
"""
VTEX Response Extractor

This script extracts the 'response' values from a JSON file containing VTEX product creation results
and exports them to a new JSON file.

Usage:
    python3 extract_response.py input.json output.json [--indent INDENT]

Arguments:
    input.json    - Input JSON file containing response data
    output.json   - Output JSON file for extracted responses
    --indent      - JSON formatting indent (default: 4)

Example:
    python3 extract_response.py vtex_creation_successful.json responses.json --indent 4
"""

import json
import argparse
import sys
from pathlib import Path


def extract_responses(input_file, output_file, indent=4):
    """
    Extract response values from JSON file and save to new file.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output JSON file
        indent: JSON formatting indent
    """
    try:
        # Read input JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        responses = []
        
        # Handle both single object and list of objects
        if isinstance(data, list):
            for item in data:
                if 'response' in item:
                    responses.append(item['response'])
        elif isinstance(data, dict):
            if 'response' in data:
                responses.append(data['response'])
        
        # Write extracted responses to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(responses, f, indent=indent, ensure_ascii=False)
        
        print(f"Extracted {len(responses)} responses from {input_file}")
        print(f"Saved to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {input_file}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract 'response' values from JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('input_file', help='Input JSON file')
    parser.add_argument('output_file', help='Output JSON file')
    parser.add_argument('--indent', type=int, default=4, 
                       help='JSON formatting indent (default: 4)')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not Path(args.input_file).exists():
        print(f"Error: Input file {args.input_file} does not exist")
        sys.exit(1)
    
    extract_responses(args.input_file, args.output_file, args.indent)


if __name__ == "__main__":
    main()