#!/usr/bin/env python3
"""
vtex_specification_create.py

Creates VTEX specifications within specification groups via API.

Reads JSON file with specification group creation responses and creates
specifications using the /api/catalog/pvt/specification endpoint.

Features:
- Rate limiting with configurable delay between requests
- Exponential backoff for rate limit errors (429)
- Dry-run mode for testing without creating specifications
- Comprehensive error handling and retry logic
- Export results to JSON and CSV
- Generate detailed markdown reports
- Flexible specification definition via JSON file or default values

Usage:
    python3 vtex_specification_create.py groups.json specs.json
    python3 vtex_specification_create.py groups.json specs.json --dry-run
    python3 vtex_specification_create.py groups.json specs.json --delay 2.0

Input Groups JSON Format (from specification group creation):
    [
      {
        "response": {
          "Id": 168,
          "CategoryId": 118,
          "Name": "PUM_CAT"
        },
        "status_code": 200
      }
    ]

Input Specifications JSON Format:
    [
      {
        "Name": "VALOR UNIDAD DE MEDIDA",
        "FieldTypeId": 4,
        "IsFilter": false,
        "IsRequired": false,
        "IsOnProductDetails": true,
        "IsStockKeepingUnit": true,
        "IsActive": true,
        "IsTopMenuLinkActive": false,
        "IsSideMenuLinkActive": false
      }
    ]

Environment Variables (.env):
    X-VTEX-API-AppKey=your_app_key
    X-VTEX-API-AppToken=your_app_token
    VTEX_ACCOUNT_NAME=your_account
    VTEX_ENVIRONMENT=vtexcommercestable

Output Files:
    - TIMESTAMP_specification_creation_successful.json (full API responses)
    - TIMESTAMP_specification_creation_successful.csv (FieldId, CategoryId, GroupId, Name)
    - TIMESTAMP_specification_creation_failed.json (error details)
    - TIMESTAMP_specification_creation_failed.csv (errors for manual review)
    - TIMESTAMP_specification_creation_REPORT.md (comprehensive report)
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


class VTEXSpecificationCreator:
    """Creates VTEX specifications within groups via API from JSON data."""

    def __init__(self, delay=1.0, timeout=30, dry_run=False):
        """Initialize the specification creator.

        Args:
            delay: Delay between requests in seconds (default: 1.0)
            timeout: Request timeout in seconds (default: 30)
            dry_run: If True, validate without creating specifications (default: False)
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
        self.endpoint = f"{self.base_url}/api/catalog/pvt/specification"

        # Tracking lists
        self.successful_specs = []
        self.failed_specs = []
        self.total_processed = 0

        print(f"🔧 Endpoint: {self.endpoint}")
        print(f"⏱️  Delay: {self.delay}s between requests")
        print(f"🕐 Timeout: {self.timeout}s per request")
        if self.dry_run:
            print("🧪 DRY-RUN MODE: No specifications will be created")

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

    def load_specification_groups(self, groups_file):
        """Load specification groups from JSON file.

        Args:
            groups_file: Path to JSON file with specification group creation responses

        Returns:
            List of dictionaries with CategoryId and FieldGroupId
        """
        with open(groups_file, 'r', encoding='utf-8') as f:
            groups_data = json.load(f)

        groups = []
        for item in groups_data:
            # Validate structure
            if 'response' not in item:
                print(f"⚠️  Skipping item without 'response' field: {item}")
                continue

            response = item['response']
            if 'Id' not in response or 'CategoryId' not in response:
                print(f"⚠️  Skipping item without Id or CategoryId: {response}")
                continue

            groups.append({
                'FieldGroupId': response['Id'],
                'CategoryId': response['CategoryId'],
                'GroupName': response.get('Name', 'N/A')
            })

        print(f"✅ Loaded {len(groups)} specification groups from JSON")
        return groups

    def load_specifications(self, specs_file):
        """Load specification definitions from JSON file.

        Args:
            specs_file: Path to JSON file with specification definitions

        Returns:
            List of dictionaries with specification properties
        """
        with open(specs_file, 'r', encoding='utf-8') as f:
            specs_data = json.load(f)

        if not isinstance(specs_data, list):
            specs_data = [specs_data]

        # Validate each specification has required fields
        required_fields = ['Name', 'FieldTypeId']
        specs = []
        for i, spec in enumerate(specs_data):
            missing = [field for field in required_fields if field not in spec]
            if missing:
                print(f"⚠️  Spec {i+1}: Missing required fields {missing} - skipping")
                continue
            specs.append(spec)

        print(f"✅ Loaded {len(specs)} specification definitions from JSON")
        return specs

    def create_specification(self, group, spec_template, retry_count=0):
        """Create a specification in VTEX.

        Args:
            group: Dictionary with FieldGroupId and CategoryId
            spec_template: Dictionary with specification properties
            retry_count: Current retry count (for exponential backoff)

        Returns:
            True if successful, False otherwise
        """
        MAX_RETRIES = 3
        BACKOFF_FACTOR = 2

        category_id = group['CategoryId']
        field_group_id = group['FieldGroupId']
        spec_name = spec_template['Name']

        # Apply rate limiting (except on retries)
        if self.total_processed > 0 and retry_count == 0:
            time.sleep(self.delay)

        # Dry-run mode
        if self.dry_run:
            print(f"  [DRY-RUN] Would create: '{spec_name}' in Group {field_group_id} (Category {category_id})")
            simulated_field_id = f"SIMULATED-{self.total_processed + 1}"
            self.successful_specs.append({
                'group_data': group,
                'spec_template': spec_template,
                'response': {
                    'Id': simulated_field_id,
                    'FieldGroupId': field_group_id,
                    'CategoryId': category_id,
                    'Name': spec_name,
                    'FieldTypeId': spec_template.get('FieldTypeId', 4),
                    'Position': self.total_processed + 1,
                    'IsFilter': spec_template.get('IsFilter', False),
                    'IsRequired': spec_template.get('IsRequired', False),
                    'IsActive': spec_template.get('IsActive', True),
                    'message': 'DRY-RUN mode'
                },
                'status_code': 200,
                'field_id': simulated_field_id,
                'category_id': category_id,
                'field_group_id': field_group_id,
                'name': spec_name,
                'field_type_id': spec_template.get('FieldTypeId', 4),
                'description': '',
                'position': self.total_processed + 1,
                'is_filter': spec_template.get('IsFilter', False),
                'is_required': spec_template.get('IsRequired', False),
                'is_active': spec_template.get('IsActive', True),
                'default_value': '',
                'timestamp': datetime.now().isoformat()
            })
            self.total_processed += 1
            return True

        # Prepare request body
        body = {
            'FieldTypeId': spec_template.get('FieldTypeId', 4),
            'CategoryId': category_id,
            'FieldGroupId': field_group_id,
            'Name': spec_name,
            'IsFilter': spec_template.get('IsFilter', False),
            'IsRequired': spec_template.get('IsRequired', False),
            'IsOnProductDetails': spec_template.get('IsOnProductDetails', True),
            'IsStockKeepingUnit': spec_template.get('IsStockKeepingUnit', True),
            'IsActive': spec_template.get('IsActive', True),
            'IsTopMenuLinkActive': spec_template.get('IsTopMenuLinkActive', False),
            'IsSideMenuLinkActive': spec_template.get('IsSideMenuLinkActive', False)
        }

        try:
            response = self.session.post(
                self.endpoint,
                json=body,
                timeout=self.timeout
            )

            # Success
            if response.status_code in [200, 201]:
                response_data = response.json() if response.text else {}
                field_id = response_data.get('Id', 'N/A')

                result = {
                    'group_data': group,
                    'spec_template': spec_template,
                    'response': response_data,
                    'status_code': response.status_code,
                    'field_id': field_id,
                    'category_id': category_id,
                    'field_group_id': field_group_id,
                    'name': spec_name,
                    'field_type_id': response_data.get('FieldTypeId', 'N/A'),
                    'description': response_data.get('Description', ''),
                    'position': response_data.get('Position', 'N/A'),
                    'is_filter': response_data.get('IsFilter', False),
                    'is_required': response_data.get('IsRequired', False),
                    'is_active': response_data.get('IsActive', True),
                    'default_value': response_data.get('DefaultValue', ''),
                    'timestamp': datetime.now().isoformat()
                }
                self.successful_specs.append(result)
                self.total_processed += 1
                print(f"  ✅ Created: '{spec_name}' (FieldId: {field_id}, Group: {field_group_id})")
                return True

            # Rate limit - retry with exponential backoff
            elif response.status_code == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                    print(f"  ⚠️  Rate limit. Waiting {wait_time}s... (retry {retry_count+1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    return self.create_specification(group, spec_template, retry_count + 1)
                else:
                    error_result = {
                        'group_data': group,
                        'spec_template': spec_template,
                        'error': 'Rate limit exceeded - max retries reached',
                        'status_code': 429,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.failed_specs.append(error_result)
                    print(f"  ❌ Failed: '{spec_name}' - Rate limit exceeded")
                    return False

            # Other errors
            else:
                error_text = response.text if response.text else 'No error message'
                error_result = {
                    'group_data': group,
                    'spec_template': spec_template,
                    'error': error_text,
                    'status_code': response.status_code,
                    'category_id': category_id,
                    'field_group_id': field_group_id,
                    'name': spec_name,
                    'timestamp': datetime.now().isoformat()
                }
                self.failed_specs.append(error_result)
                print(f"  ❌ Failed: '{spec_name}' - Status {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            error_result = {
                'group_data': group,
                'spec_template': spec_template,
                'error': f'Request timeout after {self.timeout}s',
                'category_id': category_id,
                'field_group_id': field_group_id,
                'name': spec_name,
                'timestamp': datetime.now().isoformat()
            }
            self.failed_specs.append(error_result)
            print(f"  ❌ Failed: '{spec_name}' - Timeout")
            return False

        except requests.exceptions.RequestException as e:
            error_result = {
                'group_data': group,
                'spec_template': spec_template,
                'error': f'Request error: {str(e)}',
                'category_id': category_id,
                'field_group_id': field_group_id,
                'name': spec_name,
                'timestamp': datetime.now().isoformat()
            }
            self.failed_specs.append(error_result)
            print(f"  ❌ Failed: '{spec_name}' - {str(e)}")
            return False

    def process_all_specifications(self, groups, specifications):
        """Process all specification creations.

        Args:
            groups: List of group dictionaries
            specifications: List of specification templates
        """
        total = len(groups) * len(specifications)
        print(f"\n{'='*70}")
        print(f"Processing {total} specifications ({len(groups)} groups × {len(specifications)} specs)...")
        print(f"{'='*70}\n")

        start_time = time.time()
        processed = 0

        for i, group in enumerate(groups, 1):
            group_name = group.get('GroupName', 'N/A')
            print(f"\n[Group {i}/{len(groups)}] '{group_name}' (ID: {group['FieldGroupId']}, Category: {group['CategoryId']})")

            for j, spec in enumerate(specifications, 1):
                processed += 1
                print(f"  [{j}/{len(specifications)}] Creating: '{spec['Name']}'")
                self.create_specification(group, spec)

            # Progress report every 10 groups
            if i % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / processed
                remaining = (total - processed) * avg_time
                print(f"\n📊 Progress: {processed}/{total} - Successful: {len(self.successful_specs)}, Failed: {len(self.failed_specs)}")
                print(f"⏱️  Elapsed: {elapsed:.1f}s, Estimated remaining: {remaining:.1f}s\n")

        duration = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"✅ Processing complete!")
        print(f"⏱️  Total duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        print(f"{'='*70}\n")

    def export_results(self, output_prefix="specification_creation"):
        """Export successful and failed results to JSON and CSV files.

        Args:
            output_prefix: Prefix for output filenames
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.successful_specs:
            success_file = f"{timestamp}_{output_prefix}_successful.json"
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump(self.successful_specs, f, ensure_ascii=False, indent=2)
            print(f"✅ Successful specifications exported to: {success_file}")

            # Export successful as CSV
            success_csv = f"{timestamp}_{output_prefix}_successful.csv"
            with open(success_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'FieldId', 'CategoryId', 'FieldGroupId', 'Name',
                    'FieldTypeId', 'Position', 'IsRequired', 'IsFilter', 'IsActive'
                ])
                writer.writeheader()
                for item in self.successful_specs:
                    writer.writerow({
                        'FieldId': item.get('field_id', 'N/A'),
                        'CategoryId': item['category_id'],
                        'FieldGroupId': item['field_group_id'],
                        'Name': item['name'],
                        'FieldTypeId': item.get('field_type_id', 'N/A'),
                        'Position': item.get('position', 'N/A'),
                        'IsRequired': item.get('is_required', False),
                        'IsFilter': item.get('is_filter', False),
                        'IsActive': item.get('is_active', True)
                    })
            print(f"✅ Successful specifications CSV exported to: {success_csv}")

        if self.failed_specs:
            failed_file = f"{timestamp}_{output_prefix}_failed.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_specs, f, ensure_ascii=False, indent=2)
            print(f"❌ Failed specifications exported to: {failed_file}")

            # Export failed as CSV
            failed_csv = f"{timestamp}_{output_prefix}_failed.csv"
            with open(failed_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['CategoryId', 'FieldGroupId', 'Name', 'Error', 'StatusCode'])
                writer.writeheader()
                for item in self.failed_specs:
                    writer.writerow({
                        'CategoryId': item.get('category_id', 'N/A'),
                        'FieldGroupId': item.get('field_group_id', 'N/A'),
                        'Name': item.get('name', 'N/A'),
                        'Error': item.get('error', 'Unknown error'),
                        'StatusCode': item.get('status_code', 'N/A')
                    })
            print(f"❌ Failed specifications CSV exported to: {failed_csv}")

    def _format_successful_table(self):
        """Format successful specifications as markdown table."""
        if not self.successful_specs:
            return "_No successful creations_"

        table = "| FieldId | Name | FieldTypeId | CategoryId | GroupId | Position | Required | Filter |\n"
        table += "|---------|------|-------------|------------|---------|----------|----------|--------|\\n"

        for item in self.successful_specs[:20]:  # Limit to 20 entries
            field_id = item.get('field_id', 'N/A')
            position = item.get('position', 'N/A')
            is_required = '✓' if item.get('is_required', False) else ''
            is_filter = '✓' if item.get('is_filter', False) else ''
            table += f"| {field_id} | {item['name']} | {item.get('field_type_id', 'N/A')} | {item['category_id']} | {item['field_group_id']} | {position} | {is_required} | {is_filter} |\n"

        if len(self.successful_specs) > 20:
            table += f"\n_... and {len(self.successful_specs) - 20} more_\n"

        return table

    def _format_failed_table(self):
        """Format failed specifications as markdown table."""
        if not self.failed_specs:
            return "_No failures_"

        table = "| CategoryId | FieldGroupId | Name | Error | Status Code |\n"
        table += "|------------|--------------|------|-------|-------------|\\n"

        for item in self.failed_specs:
            error = item.get('error', 'Unknown error')
            # Truncate long errors
            if len(error) > 50:
                error = error[:47] + "..."
            table += f"| {item.get('category_id', 'N/A')} | {item.get('field_group_id', 'N/A')} | {item.get('name', 'N/A')} | {error} | {item.get('status_code', 'N/A')} |\n"

        return table

    def _generate_recommendations(self):
        """Generate recommendations based on results."""
        recommendations = []

        if not self.failed_specs:
            recommendations.append("✅ All specifications were created successfully!")
            recommendations.append("- No further action required")
        else:
            recommendations.append("⚠️ Some specifications failed to create:")
            recommendations.append(f"- Review the failed specifications in the CSV export")
            recommendations.append(f"- Check error messages for common patterns")
            recommendations.append(f"- Verify CategoryId and FieldGroupId values exist in VTEX")
            recommendations.append(f"- Fix errors and re-run with failed specifications")

        return "\n".join(recommendations)

    def generate_markdown_report(self, report_file):
        """Generate comprehensive markdown report.

        Args:
            report_file: Path to output markdown file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total = len(self.successful_specs) + len(self.failed_specs)
        success_count = len(self.successful_specs)
        failed_count = len(self.failed_specs)
        success_rate = (success_count / total * 100) if total > 0 else 0

        report = f"""# VTEX Specification Creation Report

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
*Generated by VTEX Specification Creator*
"""

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📄 Report generated: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Create VTEX specifications from specification groups JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create specifications
  python3 vtex_specification_create.py groups.json specs.json

  # Dry-run mode (test without creating)
  python3 vtex_specification_create.py groups.json specs.json --dry-run

  # Custom delay and timeout
  python3 vtex_specification_create.py groups.json specs.json --delay 2.0 --timeout 60

Groups JSON Format (from specification group creation):
  [
    {
      "response": {
        "Id": 168,
        "CategoryId": 118,
        "Name": "PUM_CAT"
      },
      "status_code": 200
    }
  ]

Specifications JSON Format:
  [
    {
      "Name": "VALOR UNIDAD DE MEDIDA",
      "FieldTypeId": 4,
      "IsFilter": false,
      "IsRequired": false,
      "IsOnProductDetails": true,
      "IsStockKeepingUnit": true,
      "IsActive": true,
      "IsTopMenuLinkActive": false,
      "IsSideMenuLinkActive": false
    }
  ]

Output Files:
  - YYYYMMDD_HHMMSS_specification_creation_successful.json (full API responses)
  - YYYYMMDD_HHMMSS_specification_creation_successful.csv (FieldId reference)
  - YYYYMMDD_HHMMSS_specification_creation_failed.json (error details)
  - YYYYMMDD_HHMMSS_specification_creation_failed.csv (errors for review)
  - YYYYMMDD_HHMMSS_specification_creation_REPORT.md (full report)
        '''
    )

    parser.add_argument('groups_json', help='JSON file with specification group creation responses')
    parser.add_argument('specs_json', help='JSON file with specification definitions')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--output-prefix', default='specification_creation',
                       help='Prefix for output files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulation mode: validate data without creating specifications')

    args = parser.parse_args()

    # Validate files exist
    if not os.path.exists(args.groups_json):
        print(f"Error: Groups JSON file not found - {args.groups_json}")
        sys.exit(1)

    if not os.path.exists(args.specs_json):
        print(f"Error: Specifications JSON file not found - {args.specs_json}")
        sys.exit(1)

    try:
        # Initialize creator
        creator = VTEXSpecificationCreator(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run
        )

        # Load groups and specifications
        groups = creator.load_specification_groups(args.groups_json)
        specifications = creator.load_specifications(args.specs_json)

        if not groups:
            print("No valid groups found in JSON file")
            sys.exit(1)

        if not specifications:
            print("No valid specifications found in JSON file")
            sys.exit(1)

        # Process all specifications
        creator.process_all_specifications(groups, specifications)

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
        print(f"✅ Successful:    {len(creator.successful_specs)}")
        print(f"❌ Failed:        {len(creator.failed_specs)}")
        print(f"{'='*70}\n")

        # Exit code based on results
        if creator.failed_specs:
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
