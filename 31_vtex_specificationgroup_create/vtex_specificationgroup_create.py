#!/usr/bin/env python3
"""
vtex_specificationgroup_create.py

Creates VTEX specification groups via API from CSV file.

Reads a CSV file with category ID and group name columns and creates
specification groups in VTEX catalog using the
/api/catalog/pvt/specificationgroup endpoint. Column names are configurable,
so this can use either the historical CategoryId,Name input or step 61 output
with Category ID plus a fixed Name.

Features:
- Rate limiting with configurable delay between requests
- Exponential backoff for rate limit errors (429)
- Dry-run mode for testing without creating groups
- Comprehensive error handling and retry logic
- Export results to JSON and CSV
- Generate detailed markdown reports

Usage:
    python3 vtex_specificationgroup_create.py input.csv
    python3 vtex_specificationgroup_create.py input.csv --dry-run
    python3 vtex_specificationgroup_create.py input.csv --delay 2.0
    python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py 61_sku_spec_matcher/resultado_20260601_214458_category_ids.csv \
        --category-id-column "Category ID" --fixed-name "Especificaciones (SKU)" --dry-run

CSV Format:
    CategoryId,Name
    1309,PUM
    1310,Medidas

Step 61 CSV Format:
    Category ID
    893
    1528

Environment Variables (.env):
    X-VTEX-API-AppKey=your_app_key
    X-VTEX-API-AppToken=your_app_token
    VTEX_ACCOUNT_NAME=your_account
    VTEX_ENVIRONMENT=vtexcommercestable

Output Files:
    - TIMESTAMP_specificationgroup_creation_successful.json (full API responses)
    - TIMESTAMP_specificationgroup_creation_successful.csv (Id, GroupId, CategoryId, Name, Position, StatusCode)
    - TIMESTAMP_specificationgroup_creation_failed.json (error details)
    - TIMESTAMP_specificationgroup_creation_failed.csv (errors for manual review)
    - TIMESTAMP_specificationgroup_creation_REPORT.md (comprehensive report)
"""

import csv
import json
import os
import sys
import time
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Retrieve VTEX credentials
VTEX_APP_KEY = os.getenv('X-VTEX-API-AppKey')
VTEX_APP_TOKEN = os.getenv('X-VTEX-API-AppToken')
VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT_NAME')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')


class VTEXSpecificationGroupCreator:
    """Creates VTEX specification groups via API from CSV data."""

    def __init__(self, delay=1.0, timeout=30, dry_run=False):
        """Initialize the specification group creator.

        Args:
            delay: Delay between requests in seconds (default: 1.0)
            timeout: Request timeout in seconds (default: 30)
            dry_run: If True, validate without creating groups (default: False)
        """
        self.delay = delay
        self.timeout = timeout
        self.dry_run = dry_run

        # Validate credentials
        self.validate_credentials()

        # Setup session with authentication headers
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-VTEX-API-AppKey': VTEX_APP_KEY,
            'X-VTEX-API-AppToken': VTEX_APP_TOKEN
        })

        # Build API endpoint URL
        self.base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"
        self.endpoint = f"{self.base_url}/api/catalog/pvt/specificationgroup"

        # Tracking lists
        self.successful_groups = []
        self.failed_groups = []
        self.total_processed = 0

        print(f"🔧 Endpoint: {self.endpoint}")
        print(f"⏱️  Delay: {self.delay}s between requests")
        print(f"🕐 Timeout: {self.timeout}s per request")
        if self.dry_run:
            print("🧪 DRY-RUN MODE: No groups will be created")

    def validate_credentials(self):
        """Validates all VTEX credentials are configured."""
        missing = []
        if not VTEX_APP_KEY:
            missing.append('X-VTEX-API-AppKey')
        if not VTEX_APP_TOKEN:
            missing.append('X-VTEX-API-AppToken')
        if not VTEX_ACCOUNT:
            missing.append('VTEX_ACCOUNT_NAME')

        if missing:
            raise ValueError(f"Missing VTEX credentials in .env: {', '.join(missing)}")

        print(f"✅ Credenciales VTEX configuradas para cuenta: {VTEX_ACCOUNT}")

    def load_specification_groups_from_csv(
        self,
        csv_file,
        category_column='CategoryId',
        name_column='Name',
        fixed_name=None,
        encoding='utf-8-sig',
        deduplicate=True
    ):
        """Load specification group data from CSV file.

        Args:
            csv_file: Path to CSV file
            category_column: Column name containing the VTEX category ID
            name_column: Column name containing the specification group name
            fixed_name: Fixed specification group name to use for every row
            encoding: CSV file encoding
            deduplicate: If True, process each CategoryId only once

        Returns:
            List of dictionaries with CategoryId and Name
        """
        groups = []
        seen_category_ids = set()
        fixed_name_value = fixed_name.strip() if fixed_name is not None else None

        with open(csv_file, 'r', encoding=encoding, newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            # Validate headers
            if category_column not in fieldnames:
                raise ValueError(
                    f"CSV must have '{category_column}' column. "
                    f"Found: {fieldnames}"
                )
            if fixed_name_value is None and name_column not in fieldnames:
                raise ValueError(
                    f"CSV must have '{name_column}' column when --fixed-name is not used. "
                    f"Found: {fieldnames}"
                )

            for i, row in enumerate(reader, start=2):  # start=2 (line 1 is header)
                # Validate CategoryId
                raw_category_id = row.get(category_column) or ''
                try:
                    category_id = int(raw_category_id.strip())
                except ValueError:
                    print(f"⚠️  Line {i}: Invalid {category_column} '{raw_category_id}' - skipping")
                    continue

                if deduplicate and category_id in seen_category_ids:
                    print(f"⚠️  Line {i}: Duplicate CategoryId '{category_id}' - skipping")
                    continue

                # Validate Name
                name = fixed_name_value if fixed_name_value is not None else (row.get(name_column) or '').strip()
                if not name:
                    print(f"⚠️  Line {i}: Empty Name - skipping")
                    continue

                seen_category_ids.add(category_id)
                groups.append({
                    'CategoryId': category_id,
                    'Name': name,
                    'line_number': i
                })

        print(f"✅ Loaded {len(groups)} specification groups from CSV")
        return groups

    def create_specification_group(self, group_data, retry_count=0):
        """Create a specification group in VTEX.

        Args:
            group_data: Dictionary with CategoryId and Name
            retry_count: Current retry count (for exponential backoff)

        Returns:
            True if successful, False otherwise
        """
        MAX_RETRIES = 3
        BACKOFF_FACTOR = 2

        category_id = group_data['CategoryId']
        name = group_data['Name']
        payload = {
            'CategoryId': category_id,
            'Name': name
        }

        # Apply rate limiting (except on retries)
        if not self.dry_run and self.total_processed > 0 and retry_count == 0:
            time.sleep(self.delay)

        # Dry-run mode
        if self.dry_run:
            print(f"  [DRY-RUN] Would create: CategoryId={category_id}, Name='{name}'")
            # Simulate a response similar to what the API would return
            simulated_group_id = f"SIMULATED-{self.total_processed + 1}"
            self.successful_groups.append({
                'group_data': group_data,
                'response': {
                    'Id': simulated_group_id,
                    'CategoryId': category_id,
                    'Name': name,
                    'Position': self.total_processed + 1,
                    'message': 'DRY-RUN mode'
                },
                'payload': payload,
                'status_code': 200,
                'category_id': category_id,
                'name': name,
                'group_id': simulated_group_id,
                'position': self.total_processed + 1,
                'timestamp': datetime.now().isoformat()
            })
            self.total_processed += 1
            return True

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout
            )

            # Success
            if response.status_code in [200, 201]:
                response_data = response.json() if response.text else {}
                group_id = response_data.get('Id', 'N/A')

                result = {
                    'group_data': group_data,
                    'response': response_data,
                    'payload': payload,
                    'status_code': response.status_code,
                    'category_id': category_id,
                    'name': name,
                    'group_id': group_id,
                    'position': response_data.get('Position', 'N/A'),
                    'timestamp': datetime.now().isoformat()
                }
                self.successful_groups.append(result)
                self.total_processed += 1
                print(f"  ✅ Created: {name} (CategoryId: {category_id}, GroupId: {group_id})")
                return True

            # Rate limit - retry with exponential backoff
            elif response.status_code == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                    print(f"  ⚠️  Rate limit. Waiting {wait_time}s... (retry {retry_count+1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    return self.create_specification_group(group_data, retry_count + 1)
                else:
                    error_result = {
                        'group_data': group_data,
                        'error': 'Rate limit exceeded - max retries reached',
                        'status_code': 429,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.failed_groups.append(error_result)
                    print(f"  ❌ Failed: {name} - Rate limit exceeded")
                    return False

            # Other errors
            else:
                error_text = response.text if response.text else 'No error message'
                error_result = {
                    'group_data': group_data,
                    'error': error_text,
                    'status_code': response.status_code,
                    'category_id': category_id,
                    'name': name,
                    'timestamp': datetime.now().isoformat()
                }
                self.failed_groups.append(error_result)
                print(f"  ❌ Failed: {name} - Status {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            error_result = {
                'group_data': group_data,
                'error': f'Request timeout after {self.timeout}s',
                'category_id': category_id,
                'name': name,
                'timestamp': datetime.now().isoformat()
            }
            self.failed_groups.append(error_result)
            print(f"  ❌ Failed: {name} - Timeout")
            return False

        except requests.exceptions.RequestException as e:
            error_result = {
                'group_data': group_data,
                'error': f'Request error: {str(e)}',
                'category_id': category_id,
                'name': name,
                'timestamp': datetime.now().isoformat()
            }
            self.failed_groups.append(error_result)
            print(f"  ❌ Failed: {name} - {str(e)}")
            return False

    def process_all_groups(self, groups):
        """Process all specification groups.

        Args:
            groups: List of group dictionaries
        """
        total = len(groups)
        print(f"\n{'='*70}")
        print(f"Processing {total} specification groups...")
        print(f"{'='*70}\n")

        start_time = time.time()

        for i, group in enumerate(groups, 1):
            print(f"[{i}/{total}] CategoryId: {group['CategoryId']}, Name: '{group['Name']}'")
            self.create_specification_group(group)

            # Progress report every 10 items
            if i % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / i
                remaining = (total - i) * avg_time
                print(f"\n📊 Progress: {i}/{total} - Successful: {len(self.successful_groups)}, Failed: {len(self.failed_groups)}")
                print(f"⏱️  Elapsed: {elapsed:.1f}s, Estimated remaining: {remaining:.1f}s\n")

        duration = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"✅ Processing complete!")
        print(f"⏱️  Total duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        print(f"{'='*70}\n")

    def export_results(self, output_prefix="specificationgroup_creation"):
        """Export successful and failed results to JSON and CSV files.

        Args:
            output_prefix: Prefix for output filenames
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.successful_groups:
            success_file = f"{timestamp}_{output_prefix}_successful.json"
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump(self.successful_groups, f, ensure_ascii=False, indent=2)
            print(f"✅ Successful groups exported to: {success_file}")

            # Also export successful as CSV with Id/GroupId for easy reference
            success_csv = f"{timestamp}_{output_prefix}_successful.csv"
            with open(success_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=['Id', 'GroupId', 'CategoryId', 'Name', 'Position', 'StatusCode']
                )
                writer.writeheader()
                for item in self.successful_groups:
                    group_id = item.get('group_id', 'N/A')
                    writer.writerow({
                        'Id': group_id,
                        'GroupId': group_id,
                        'CategoryId': item['category_id'],
                        'Name': item['name'],
                        'Position': item.get('position', 'N/A'),
                        'StatusCode': item.get('status_code', 'N/A')
                    })
            print(f"✅ Successful groups CSV exported to: {success_csv}")

        if self.failed_groups:
            failed_file = f"{timestamp}_{output_prefix}_failed.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_groups, f, ensure_ascii=False, indent=2)
            print(f"❌ Failed groups exported to: {failed_file}")

            # Also export failed as CSV for easy review
            failed_csv = f"{timestamp}_{output_prefix}_failed.csv"
            with open(failed_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['CategoryId', 'Name', 'Error', 'StatusCode'])
                writer.writeheader()
                for item in self.failed_groups:
                    writer.writerow({
                        'CategoryId': item['group_data']['CategoryId'],
                        'Name': item['group_data']['Name'],
                        'Error': item.get('error', 'Unknown error'),
                        'StatusCode': item.get('status_code', 'N/A')
                    })
            print(f"❌ Failed groups CSV exported to: {failed_csv}")

    def _format_successful_table(self):
        """Format successful groups as markdown table."""
        if not self.successful_groups:
            return "_No successful creations_"

        table = "| CategoryId | Name | GroupId | Position | Timestamp |\n"
        table += "|------------|------|---------|----------|------------|\n"

        for item in self.successful_groups[:20]:  # Limit to 20 entries
            group_id = item.get('group_id', 'N/A')
            position = item.get('position', 'N/A')
            table += f"| {item['category_id']} | {item['name']} | {group_id} | {position} | {item['timestamp']} |\n"

        if len(self.successful_groups) > 20:
            table += f"\n_... and {len(self.successful_groups) - 20} more_\n"

        return table

    def _format_failed_table(self):
        """Format failed groups as markdown table."""
        if not self.failed_groups:
            return "_No failures_"

        table = "| CategoryId | Name | Error | Status Code |\n"
        table += "|------------|------|-------|-------------|\n"

        for item in self.failed_groups:
            error = item.get('error', 'Unknown error')
            # Truncate long errors
            if len(error) > 50:
                error = error[:47] + "..."
            table += f"| {item['group_data']['CategoryId']} | {item['group_data']['Name']} | {error} | {item.get('status_code', 'N/A')} |\n"

        return table

    def _generate_recommendations(self):
        """Generate recommendations based on results."""
        recommendations = []

        if not self.failed_groups:
            recommendations.append("✅ All specification groups were created successfully!")
            recommendations.append("- No further action required")
        else:
            recommendations.append("⚠️ Some specification groups failed to create:")
            recommendations.append(f"- Review the failed groups in the CSV export")
            recommendations.append(f"- Check error messages for common patterns")
            recommendations.append(f"- Verify CategoryId values exist in VTEX")
            recommendations.append(f"- Fix errors and re-run with failed groups CSV")

        return "\n".join(recommendations)

    def generate_markdown_report(self, report_file):
        """Generate comprehensive markdown report.

        Args:
            report_file: Path to output markdown file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total = len(self.successful_groups) + len(self.failed_groups)
        success_count = len(self.successful_groups)
        failed_count = len(self.failed_groups)
        success_rate = (success_count / total * 100) if total > 0 else 0

        report = f"""# VTEX Specification Group Creation Report

**Generated:** {timestamp}
**VTEX Account:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}
**Mode:** {'DRY-RUN (Simulation)' if self.dry_run else 'Production'}

## Summary

| Metric | Value |
|--------|-------|
| **Total Processed** | {total} |
| **✅ Successful** | {success_count} ({success_rate:.1f}%) |
| **❌ Failed** | {failed_count} ({100-success_rate:.1f}%) |

## Successful Creations

{self._format_successful_table()}

## Failed Creations

{self._format_failed_table()}

## Recommendations

{self._generate_recommendations()}

---
*Generated by VTEX Specification Group Creator*
"""

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📄 Report generated: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Create VTEX specification groups from CSV file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create specification groups
  python3 vtex_specificationgroup_create.py groups.csv

  # Dry-run mode (test without creating)
  python3 vtex_specificationgroup_create.py groups.csv --dry-run

  # Custom delay and timeout
  python3 vtex_specificationgroup_create.py groups.csv --delay 2.0 --timeout 60

  # Step 61 category IDs with a fixed SKU specification group name
  python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py 61_sku_spec_matcher/resultado_20260601_214458_category_ids.csv \\
    --category-id-column "Category ID" --fixed-name "Especificaciones (SKU)" \\
    --output-prefix sku_specificationgroup_creation --dry-run

CSV Format:
  CategoryId,Name
  1309,PUM
  1310,Medidas
  1311,Características Técnicas

Step 61 CSV Format:
  Category ID
  893
  1528

Output Files:
  - YYYYMMDD_HHMMSS_specificationgroup_creation_successful.json (full API responses)
  - YYYYMMDD_HHMMSS_specificationgroup_creation_successful.csv (Id/GroupId reference)
  - YYYYMMDD_HHMMSS_specificationgroup_creation_failed.json (error details)
  - YYYYMMDD_HHMMSS_specificationgroup_creation_failed.csv (errors for review)
  - YYYYMMDD_HHMMSS_specificationgroup_creation_REPORT.md (full report)
        '''
    )

    parser.add_argument('input_csv', help='CSV file with configurable category ID and name columns')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--output-prefix', default='specificationgroup_creation',
                       help='Prefix for output files')
    parser.add_argument('--category-id-column', default='CategoryId',
                       help='CSV column containing the VTEX category ID (default: CategoryId)')
    parser.add_argument('--name-column', default='Name',
                       help='CSV column containing the group name when --fixed-name is not used (default: Name)')
    parser.add_argument('--fixed-name', default=None,
                       help='Fixed specification group name to use for every row')
    parser.add_argument('--encoding', default='utf-8-sig',
                       help='CSV file encoding (default: utf-8-sig)')
    parser.add_argument('--no-deduplicate', action='store_true',
                       help='Process duplicate category IDs instead of skipping repeats')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulation mode: validate data without creating groups')

    args = parser.parse_args()

    # Validate CSV file exists
    if not os.path.exists(args.input_csv):
        print(f"Error: CSV file not found - {args.input_csv}")
        sys.exit(1)

    try:
        # Initialize creator
        creator = VTEXSpecificationGroupCreator(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run
        )

        # Load groups from CSV
        groups = creator.load_specification_groups_from_csv(
            args.input_csv,
            category_column=args.category_id_column,
            name_column=args.name_column,
            fixed_name=args.fixed_name,
            encoding=args.encoding,
            deduplicate=not args.no_deduplicate
        )

        if not groups:
            print("No valid groups found in CSV file")
            sys.exit(1)

        # Process all groups
        creator.process_all_groups(groups)

        # Export results
        creator.export_results(args.output_prefix)

        # Generate report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{timestamp}_{args.output_prefix}_REPORT.md"
        creator.generate_markdown_report(report_file)

        # Final statistics
        print(f"\n{'='*70}")
        print(f"FINAL STATISTICS")
        print(f"{'='*70}")
        print(f"Total processed:  {creator.total_processed}")
        print(f"✅ Successful:    {len(creator.successful_groups)}")
        print(f"❌ Failed:        {len(creator.failed_groups)}")
        print(f"{'='*70}\n")

        # Exit code based on results
        if creator.failed_groups:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
