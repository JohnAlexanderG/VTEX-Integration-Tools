#!/usr/bin/env python3
"""
vtex_groups_by_category.py

Consulta grupos de especificación por categoryId en VTEX.

Lee un CSV con categoryId, consulta la API por cada categoryId y genera un CSV
consolidado con los grupos de especificación encontrados.

Features:
- Rate limiting con delay configurable entre requests
- Exponential backoff para errores de rate limit (429)
- Dry-run mode para testing sin consultas reales
- Reintentos automáticos para errores de servidor
- Exportación de resultados a JSON y CSV
- Generación de reportes markdown detallados

Usage:
    python3 vtex_groups_by_category.py input.csv
    python3 vtex_groups_by_category.py input.csv --dry-run
    python3 vtex_groups_by_category.py input.csv --delay 0.5 --timeout 60

CSV de entrada:
    - Ideal: columna llamada "categoryId"
    - Alternativa: si no hay header, toma la primera columna

Environment Variables (.env):
    X-VTEX-API-AppKey=your_app_key
    X-VTEX-API-AppToken=your_app_token
    VTEX_ACCOUNT_NAME=your_account
    VTEX_ENVIRONMENT=vtexcommercestable

Output Files:
    - TIMESTAMP_groups_by_category_results.json (full API responses)
    - TIMESTAMP_groups_by_category_results.csv (consolidated groups)
    - TIMESTAMP_groups_by_category_errors.json (error details)
    - TIMESTAMP_groups_by_category_errors.csv (errors for manual review)
    - TIMESTAMP_groups_by_category_REPORT.md (comprehensive report)
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
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

# Default configuration
DEFAULT_DELAY = 0.1
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5


class VTEXGroupsByCategory:
    """Fetches VTEX specification groups by category ID."""

    def __init__(self, delay=DEFAULT_DELAY, timeout=DEFAULT_TIMEOUT, dry_run=False):
        """Initialize the groups fetcher.

        Args:
            delay: Delay between requests in seconds (default: 0.1)
            timeout: Request timeout in seconds (default: 30)
            dry_run: If True, simulate without making real API calls (default: False)
        """
        self.delay = delay
        self.timeout = timeout
        self.dry_run = dry_run

        # Validate credentials
        self.validate_credentials()

        # Setup session with authentication headers
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'X-VTEX-API-AppKey': VTEX_APP_KEY,
            'X-VTEX-API-AppToken': VTEX_APP_TOKEN
        })

        # Build API endpoint URL
        self.base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"

        # Tracking lists
        self.successful_results = []
        self.failed_results = []
        self.total_processed = 0
        self.total_groups_found = 0

        # Statistics
        self.start_time = None
        self.categories_with_groups = 0
        self.categories_without_groups = 0

        print(f"🔧 Base URL: {self.base_url}")
        print(f"⏱️  Delay: {self.delay}s between requests")
        print(f"🕐 Timeout: {self.timeout}s per request")
        if self.dry_run:
            print("🧪 DRY-RUN MODE: No API calls will be made")

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

    def read_category_ids(self, input_path: str) -> List[str]:
        """Lee categoryId desde CSV de forma robusta.

        Soporta delimitadores comunes (',', ';', '\\t', '|') y archivos con o sin header.
        - Si existe header "categoryId" (case-insensitive), usa esa columna.
        - Si no, usa la primera columna.

        Devuelve una lista única preservando orden.
        """

        def _is_plausible_delim(d: str) -> bool:
            return isinstance(d, str) and len(d) == 1 and d not in ("\n", "\r")

        def _try_parse_with_delim(delim: str) -> List[str]:
            ids_local: List[str] = []
            seen_local = set()

            with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
                sample = f.read(8192)
                f.seek(0)

                first_line = ""
                for line in sample.splitlines():
                    if line.strip():
                        first_line = line
                        break
                has_header_guess = "categoryid" in first_line.lower()

                reader = csv.reader(f, delimiter=delim)

                if has_header_guess:
                    dict_reader = csv.DictReader(f, delimiter=delim)
                    if not dict_reader.fieldnames:
                        return []
                    field_map = {name.lower().strip(): name for name in dict_reader.fieldnames if name}
                    if "categoryid" in field_map:
                        key = field_map["categoryid"]
                        for row in dict_reader:
                            val = (row.get(key) or "").strip()
                            if val and val not in seen_local:
                                ids_local.append(val)
                                seen_local.add(val)
                    else:
                        first_key = dict_reader.fieldnames[0]
                        for row in dict_reader:
                            val = (row.get(first_key) or "").strip()
                            if val and val not in seen_local:
                                ids_local.append(val)
                                seen_local.add(val)
                else:
                    for row in reader:
                        if not row:
                            continue
                        val = (row[0] or "").strip()
                        if val and val not in seen_local:
                            ids_local.append(val)
                            seen_local.add(val)

            return ids_local

        # 1) Intentar Sniffer de forma segura
        try:
            with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
                sample = f.read(8192)
            sniff = csv.Sniffer()
            dialect = sniff.sniff(sample, delimiters=[",", ";", "\t", "|"])
            delim = getattr(dialect, "delimiter", ",")
            if _is_plausible_delim(delim):
                ids = _try_parse_with_delim(delim)
                if ids:
                    return ids
        except Exception:
            pass

        # 2) Fallbacks por delimitadores comunes
        for delim in [";", ",", "\t", "|"]:
            try:
                ids = _try_parse_with_delim(delim)
                if ids:
                    return ids
            except Exception:
                continue

        # 3) Último recurso: leer por líneas
        ids: List[str] = []
        seen = set()
        with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if "categoryid" in s.lower():
                    continue
                for d in (";", ",", "\t", "|"):
                    if d in s:
                        s = s.split(d, 1)[0].strip()
                        break
                val = s.strip().strip('"').strip("'")
                if val and val not in seen:
                    ids.append(val)
                    seen.add(val)

        return ids

    def _safe_get(self, d: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
        """Safely get value from dict trying multiple keys."""
        for k in keys:
            if k in d:
                return d[k]
        return default

    def fetch_groups_for_category(
        self,
        category_id: str,
        retry_count: int = 0
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str], int]:
        """Fetch specification groups for a category.

        Args:
            category_id: The VTEX category ID
            retry_count: Current retry count (for exponential backoff)

        Returns:
            Tuple of (data, error, status_code)
        """
        # Apply rate limiting (except on retries)
        if self.total_processed > 0 and retry_count == 0:
            time.sleep(self.delay)

        # Dry-run mode
        if self.dry_run:
            simulated_groups = [
                {
                    'Id': f"SIMULATED-{category_id}-1",
                    'Name': f"Simulated Group for {category_id}",
                    'CategoryId': int(category_id) if category_id.isdigit() else category_id,
                    'IsActive': True,
                    'Position': 1
                }
            ]
            return simulated_groups, None, 200

        url = f"{self.base_url}/api/catalog_system/pvt/specification/groupbycategory/{category_id}"

        try:
            resp = self.session.get(url, timeout=self.timeout)
            status = resp.status_code

            if 200 <= status < 300:
                try:
                    data = resp.json()
                except Exception:
                    return None, f"Response is not JSON. Body: {resp.text[:500]}", status

                if not isinstance(data, list):
                    return [data], None, status
                return data, None, status

            # Rate limit - retry with exponential backoff
            if status == 429 and retry_count < MAX_RETRIES:
                wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                print(f"  ⚠️  Rate limit. Waiting {wait_time:.1f}s... (retry {retry_count+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.fetch_groups_for_category(category_id, retry_count + 1)

            # Server error - retry
            if 500 <= status <= 599 and retry_count < MAX_RETRIES:
                wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                print(f"  ⚠️  Server error {status}. Waiting {wait_time:.1f}s... (retry {retry_count+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.fetch_groups_for_category(category_id, retry_count + 1)

            return None, f"HTTP {status}. Body: {resp.text[:500]}", status

        except requests.exceptions.Timeout:
            return None, f"Request timeout after {self.timeout}s", 0
        except requests.exceptions.RequestException as e:
            return None, f"Request error: {str(e)}", 0

    def process_category(self, category_id: str) -> None:
        """Process a single category ID.

        Args:
            category_id: The category ID to process
        """
        data, error, status = self.fetch_groups_for_category(category_id)

        if data is None:
            # Error case
            self.failed_results.append({
                'categoryId': category_id,
                'error': error or "Unknown error",
                'statusCode': status,
                'timestamp': datetime.now().isoformat()
            })
            print(f"  ❌ Error: {error}")
        elif len(data) == 0:
            # Category with no groups
            self.successful_results.append({
                'categoryId': category_id,
                'groups': [],
                'groupCount': 0,
                'statusCode': status,
                'timestamp': datetime.now().isoformat()
            })
            self.categories_without_groups += 1
            print(f"  ⏭️  No groups found")
        else:
            # Success with groups
            groups_data = []
            for g in data:
                group_id = self._safe_get(g, ["Id", "id", "GroupId", "groupId"], "")
                group_name = self._safe_get(g, ["Name", "name"], "")
                is_active = self._safe_get(g, ["IsActive", "isActive", "Active", "active"], "")
                position = self._safe_get(g, ["Position", "position"], "")

                groups_data.append({
                    'groupId': group_id,
                    'groupName': group_name,
                    'isActive': is_active,
                    'position': position,
                    'rawGroupJson': g
                })

            self.successful_results.append({
                'categoryId': category_id,
                'groups': groups_data,
                'groupCount': len(groups_data),
                'statusCode': status,
                'timestamp': datetime.now().isoformat()
            })
            self.categories_with_groups += 1
            self.total_groups_found += len(groups_data)
            print(f"  ✅ Found {len(groups_data)} group(s)")

        self.total_processed += 1

    def process_all_categories(self, category_ids: List[str]) -> None:
        """Process all category IDs.

        Args:
            category_ids: List of category IDs to process
        """
        total = len(category_ids)
        print(f"\n{'='*70}")
        print(f"Processing {total} categories...")
        print(f"{'='*70}\n")

        self.start_time = time.time()

        for i, category_id in enumerate(category_ids, 1):
            print(f"[{i}/{total}] categoryId={category_id}")
            self.process_category(category_id)

            # Progress report every 50 items
            if i % 50 == 0:
                elapsed = time.time() - self.start_time
                avg_time = elapsed / i
                remaining = (total - i) * avg_time
                print(f"\n📊 Progress: {i}/{total}")
                print(f"   Groups found: {self.total_groups_found}")
                print(f"   With groups: {self.categories_with_groups}, Without: {self.categories_without_groups}")
                print(f"   Errors: {len(self.failed_results)}")
                print(f"⏱️  Elapsed: {elapsed:.1f}s, Estimated remaining: {remaining:.1f}s\n")

        duration = time.time() - self.start_time
        print(f"\n{'='*70}")
        print(f"✅ Processing complete!")
        print(f"⏱️  Total duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        print(f"{'='*70}\n")

    def export_results(self, output_prefix: str = "groups_by_category") -> None:
        """Export results to JSON and CSV files.

        Args:
            output_prefix: Prefix for output filenames
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export successful results to JSON
        if self.successful_results:
            results_json = f"{timestamp}_{output_prefix}_results.json"
            with open(results_json, 'w', encoding='utf-8') as f:
                json.dump(self.successful_results, f, ensure_ascii=False, indent=2)
            print(f"✅ Results exported to: {results_json}")

            # Export consolidated CSV
            results_csv = f"{timestamp}_{output_prefix}_results.csv"
            fieldnames = [
                "categoryId",
                "groupId",
                "groupName",
                "isActive",
                "position",
                "statusCode",
                "rawGroupJson"
            ]
            with open(results_csv, 'w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                for result in self.successful_results:
                    category_id = result['categoryId']
                    status_code = result['statusCode']
                    if result['groups']:
                        for g in result['groups']:
                            w.writerow({
                                'categoryId': category_id,
                                'groupId': g['groupId'],
                                'groupName': g['groupName'],
                                'isActive': g['isActive'],
                                'position': g['position'],
                                'statusCode': status_code,
                                'rawGroupJson': json.dumps(g['rawGroupJson'], ensure_ascii=False)
                            })
                    else:
                        w.writerow({
                            'categoryId': category_id,
                            'groupId': '',
                            'groupName': '',
                            'isActive': '',
                            'position': '',
                            'statusCode': status_code,
                            'rawGroupJson': '[]'
                        })
            print(f"✅ CSV exported to: {results_csv}")

        # Export errors
        if self.failed_results:
            errors_json = f"{timestamp}_{output_prefix}_errors.json"
            with open(errors_json, 'w', encoding='utf-8') as f:
                json.dump(self.failed_results, f, ensure_ascii=False, indent=2)
            print(f"❌ Errors exported to: {errors_json}")

            errors_csv = f"{timestamp}_{output_prefix}_errors.csv"
            with open(errors_csv, 'w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['categoryId', 'error', 'statusCode', 'timestamp'])
                w.writeheader()
                for err in self.failed_results:
                    w.writerow({
                        'categoryId': err['categoryId'],
                        'error': err['error'],
                        'statusCode': err['statusCode'],
                        'timestamp': err['timestamp']
                    })
            print(f"❌ Errors CSV exported to: {errors_csv}")

    def _format_results_table(self, limit: int = 20) -> str:
        """Format results as markdown table."""
        if not self.successful_results:
            return "_No results_"

        table = "| CategoryId | Groups Found | Group Names |\n"
        table += "|------------|--------------|-------------|\n"

        count = 0
        for result in self.successful_results:
            if count >= limit:
                break
            group_names = ", ".join([g['groupName'] for g in result['groups'][:3]])
            if len(result['groups']) > 3:
                group_names += f" (+{len(result['groups']) - 3} more)"
            table += f"| {result['categoryId']} | {result['groupCount']} | {group_names or '-'} |\n"
            count += 1

        if len(self.successful_results) > limit:
            table += f"\n_... and {len(self.successful_results) - limit} more categories_\n"

        return table

    def _format_errors_table(self) -> str:
        """Format errors as markdown table."""
        if not self.failed_results:
            return "_No errors_"

        table = "| CategoryId | Error | Status Code |\n"
        table += "|------------|-------|-------------|\n"

        for err in self.failed_results:
            error_msg = err['error']
            if len(error_msg) > 50:
                error_msg = error_msg[:47] + "..."
            table += f"| {err['categoryId']} | {error_msg} | {err['statusCode']} |\n"

        return table

    def _generate_recommendations(self) -> str:
        """Generate recommendations based on results."""
        recommendations = []

        if not self.failed_results:
            recommendations.append("✅ All categories were queried successfully!")
        else:
            recommendations.append(f"⚠️ {len(self.failed_results)} categories failed to query:")
            recommendations.append("- Review the errors CSV export")
            recommendations.append("- Verify CategoryId values are valid")
            recommendations.append("- Check API rate limits and retry if needed")

        if self.categories_without_groups > 0:
            recommendations.append(f"\n📝 {self.categories_without_groups} categories have no specification groups")

        return "\n".join(recommendations)

    def generate_markdown_report(self, report_file: str) -> None:
        """Generate comprehensive markdown report.

        Args:
            report_file: Path to output markdown file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration = time.time() - self.start_time if self.start_time else 0

        total_categories = len(self.successful_results) + len(self.failed_results)
        success_rate = (len(self.successful_results) / total_categories * 100) if total_categories > 0 else 0

        report = f"""# VTEX Specification Groups by Category Report

**Generated:** {timestamp}
**VTEX Account:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}
**Mode:** {'DRY-RUN (Simulation)' if self.dry_run else 'Production'}
**Duration:** {duration:.1f}s ({duration/60:.1f} minutes)

## Summary

| Metric | Value |
|--------|-------|
| **Total Categories Processed** | {total_categories} |
| **✅ Successful Queries** | {len(self.successful_results)} ({success_rate:.1f}%) |
| **❌ Failed Queries** | {len(self.failed_results)} ({100-success_rate:.1f}%) |
| **📦 Total Groups Found** | {self.total_groups_found} |
| **Categories with Groups** | {self.categories_with_groups} |
| **Categories without Groups** | {self.categories_without_groups} |
| **⏱️ Delay between requests** | {self.delay}s |
| **⏱️ Timeout per request** | {self.timeout}s |

## Results by Category

{self._format_results_table()}

## Errors

{self._format_errors_table()}

## Recommendations

{self._generate_recommendations()}

---
*Generated by VTEX Groups by Category Fetcher*
"""

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"📄 Report generated: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Fetch VTEX specification groups by category from CSV file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Fetch groups for categories
  python3 vtex_groups_by_category.py categories.csv

  # Dry-run mode (test without API calls)
  python3 vtex_groups_by_category.py categories.csv --dry-run

  # Custom delay and timeout
  python3 vtex_groups_by_category.py categories.csv --delay 0.5 --timeout 60

CSV Format:
  categoryId
  1309
  1310
  1311

  Or without header (first column is used):
  1309
  1310
  1311

Output Files:
  - YYYYMMDD_HHMMSS_groups_by_category_results.json (full API responses)
  - YYYYMMDD_HHMMSS_groups_by_category_results.csv (consolidated groups)
  - YYYYMMDD_HHMMSS_groups_by_category_errors.json (error details)
  - YYYYMMDD_HHMMSS_groups_by_category_errors.csv (errors for review)
  - YYYYMMDD_HHMMSS_groups_by_category_REPORT.md (full report)
        '''
    )

    parser.add_argument('input_csv', help='CSV file with categoryId column')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                       help=f'Delay between requests in seconds (default: {DEFAULT_DELAY})')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                       help=f'Request timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--output-prefix', default='groups_by_category',
                       help='Prefix for output files (default: groups_by_category)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulation mode: validate data without making API calls')

    args = parser.parse_args()

    # Validate CSV file exists
    if not os.path.exists(args.input_csv):
        print(f"❌ Error: CSV file not found - {args.input_csv}")
        sys.exit(1)

    try:
        # Initialize fetcher
        fetcher = VTEXGroupsByCategory(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run
        )

        # Load category IDs from CSV
        print(f"\n📂 Loading categories from: {args.input_csv}")
        category_ids = fetcher.read_category_ids(args.input_csv)

        if not category_ids:
            print("❌ No categoryId values found in CSV file")
            sys.exit(1)

        print(f"✅ Loaded {len(category_ids)} unique category IDs")

        # Process all categories
        fetcher.process_all_categories(category_ids)

        # Export results
        fetcher.export_results(args.output_prefix)

        # Generate report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{timestamp}_{args.output_prefix}_REPORT.md"
        fetcher.generate_markdown_report(report_file)

        # Final statistics
        print(f"\n{'='*70}")
        print(f"FINAL STATISTICS")
        print(f"{'='*70}")
        print(f"Total processed:      {fetcher.total_processed}")
        print(f"✅ Successful:        {len(fetcher.successful_results)}")
        print(f"❌ Failed:            {len(fetcher.failed_results)}")
        print(f"📦 Total groups:      {fetcher.total_groups_found}")
        print(f"   With groups:       {fetcher.categories_with_groups}")
        print(f"   Without groups:    {fetcher.categories_without_groups}")
        print(f"{'='*70}\n")

        # Exit code based on results
        if fetcher.failed_results:
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
