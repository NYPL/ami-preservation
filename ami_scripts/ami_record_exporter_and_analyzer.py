#!/usr/bin/env python3

import argparse
import csv
import os
import re
import pandas as pd
from fmrest import Server
from collections import defaultdict
from bookops_nypl_platform import PlatformSession, PlatformToken
import logging
import requests
from openpyxl.styles import Font
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class MigrationStatusSummary:
    """Data class to track migration status counts."""
    counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def add_status(self, status: str) -> None:
        """Add a migration status to the summary."""
        clean_status = status or 'Unknown'
        self.counts[clean_status] += 1
    
    def get_summary_string(self) -> str:
        """Get a formatted string representation of the migration status summary."""
        if not self.counts:
            return "0 items"
        
        total = sum(self.counts.values())
        status_parts = [f"{count} {status}" for status, count in sorted(self.counts.items())]
        return f"{total} total ({', '.join(status_parts)})"


@dataclass
class BoxSummary:
    """Data class to track box summary information."""
    box_barcode: str = 'No Barcode'
    spec_box_location: str = 'Not Specified'
    requested_migration_statuses: MigrationStatusSummary = field(default_factory=MigrationStatusSummary)
    remaining_migration_statuses: MigrationStatusSummary = field(default_factory=MigrationStatusSummary)
    formats: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    scsb_availabilities: Set[str] = field(default_factory=set)
    total_box_items: int = 0
    
    @property
    def total_requested_items(self) -> int:
        """Get total count of requested items."""
        return sum(self.requested_migration_statuses.counts.values())
    
    @property
    def total_remaining_items(self) -> int:
        """Get total count of remaining items."""
        return sum(self.remaining_migration_statuses.counts.values())


class Config:
    """Configuration class to handle environment variables and settings."""
    
    def __init__(self):
        self.server = os.getenv('FM_SERVER')
        self.database = os.getenv('FM_DATABASE')
        self.layout = os.getenv('FM_LAYOUT')
        self.client_id = os.getenv("OAUTH_CLIENT_ID")
        self.client_secret = os.getenv("OAUTH_CLIENT_SECRET")
        self.oauth_server = os.getenv("OAUTH_SERVER")
        self.scsb_api_key = os.getenv("SCSB_API_KEY")
        self.scsb_api_url = os.getenv("SCSB_API_URL")
        
        self._validate_required_env_vars()
    
    def _validate_required_env_vars(self) -> None:
        """Validate that required environment variables are set."""
        required_vars = [
            ('FM_SERVER', self.server),
            ('FM_DATABASE', self.database),
            ('FM_LAYOUT', self.layout),
            ('OAUTH_CLIENT_ID', self.client_id),
            ('OAUTH_CLIENT_SECRET', self.client_secret),
            ('OAUTH_SERVER', self.oauth_server),
            ('SCSB_API_KEY', self.scsb_api_key),
            ('SCSB_API_URL', self.scsb_api_url)
        ]
        
        missing_vars = [var_name for var_name, var_value in required_vars if not var_value]
        
        if missing_vars:
            logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            raise SystemExit(1)


class APIClient:
    """Base class for API clients."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)


class PlatformAPIClient(APIClient):
    """Client for Platform API interactions."""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.session = None
    
    def connect(self) -> bool:
        """Create a platform session."""
        try:
            token = PlatformToken(
                self.config.client_id,
                self.config.client_secret,
                self.config.oauth_server
            )
            self.session = PlatformSession(authorization=token)
            self.logger.info("Successfully connected to the Platform API.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Platform API: {e}")
            return False
    
    def get_sierra_item(self, barcode: str) -> Dict[str, Any]:
        """Get Sierra item by barcode."""
        if not self.session:
            return {"error": "Platform session not established"}
        
        try:
            response = self.session.get_item_list(barcode=barcode)
            if response.status_code == 200 and response.json().get("data"):
                return response.json()
            else:
                return {"error": "Item barcode does not exist in Sierra database."}
        except Exception as e:
            self.logger.error(f"Error fetching item from Sierra: {e}")
            return {"error": str(e)}
    
    def extract_sierra_location(self, data: Dict[str, Any]) -> Tuple[str, str]:
        """Extract Sierra location from API response."""
        if "error" in data:
            return data["error"], data["error"]
        
        try:
            fixed_fields = data["data"][0]["fixedFields"]["79"]
            return fixed_fields["value"], fixed_fields["display"]
        except (KeyError, IndexError, TypeError):
            return "N/A", "N/A"


class SCSBAPIClient(APIClient):
    """Client for SCSB API interactions."""
    
    def get_availability(self, barcode: str) -> Dict[str, Any]:
        """Get SCSB availability for a barcode."""
        headers = {
            'accept': 'application/json',
            'api_key': self.config.scsb_api_key,
            'Content-Type': 'application/json'
        }
        payload = {"barcodes": [barcode]}
        
        try:
            response = requests.post(
                self.config.scsb_api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return [{"error": "Item barcode doesn't exist in SCSB database."}]
        except requests.RequestException as e:
            self.logger.error(f"SCSB API request failed: {e}")
            return [{"error": str(e)}]
    
    def extract_availability_status(self, json_response: List[Dict[str, Any]]) -> str:
        """Extract availability status from SCSB response."""
        if not json_response:
            self.logger.error("Empty JSON data received from SCSB.")
            return 'N/A'
        
        first_item = json_response[0]
        if "error" in first_item:
            return first_item["error"]
        
        return first_item.get('itemAvailabilityStatus', 'N/A')


class FileMakerClient(APIClient):
    """Client for FileMaker database interactions."""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.fms = None
    
    def connect(self, username: str, password: str) -> bool:
        """Connect to FileMaker database."""
        try:
            url = f"https://{self.config.server}"
            self.fms = Server(
                url,
                database=self.config.database,
                layout=self.config.layout,
                user=username,
                password=password,
                verify_ssl=True,
                api_version='v1'
            )
            self.fms.login()
            self.logger.info("Successfully connected to the FileMaker database.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Filemaker server: {e}")
            return False
    
    def find_records(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find records in FileMaker database."""
        if not self.fms:
            return []
        
        try:
            found_records = self.fms.find([query])
            return [record.to_dict() for record in found_records]
        except Exception as e:
            self.logger.error(f"Error finding records: {e}")
            return []
    
    def disconnect(self) -> None:
        """Disconnect from FileMaker database."""
        if self.fms:
            try:
                self.fms.logout()
                self.logger.info("Disconnected from FileMaker database.")
            except Exception as e:
                self.logger.error(f"Error disconnecting from FileMaker: {e}")


class FileProcessor:
    """Handles reading SPEC AMI IDs from input files."""
    
    @staticmethod
    def read_spec_ami_ids(file_path: str) -> List[str]:
        """Read SPEC AMI IDs from CSV or Excel file."""
        ids = []
        
        try:
            if file_path.endswith('.csv'):
                ids = FileProcessor._read_from_csv(file_path)
            elif file_path.endswith('.xlsx'):
                ids = FileProcessor._read_from_excel(file_path)
            else:
                logging.error(f"Unsupported file format: {file_path}")
                
        except Exception as e:
            logging.error(f"Failed to read input file: {e}")
            
        return ids
    
    @staticmethod
    def _read_from_csv(file_path: str) -> List[str]:
        """Read SPEC AMI IDs from CSV file."""
        ids = []
        
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            first_row = next(reader, None)
            
            if not first_row:
                return ids
            
            # Determine column index
            if any(not item.isdigit() for item in first_row):
                column_index = first_row.index('SPEC_AMI_ID') if 'SPEC_AMI_ID' in first_row else 0
            else:
                column_index = 0
                if re.match(r"^\d{6}$", first_row[0]):
                    ids.append(first_row[0])
            
            # Read remaining rows
            for row in reader:
                if len(row) > column_index and re.match(r"^\d{6}$", row[column_index]):
                    ids.append(row[column_index])
                    
        return ids
    
    @staticmethod
    def _read_from_excel(file_path: str) -> List[str]:
        """Read SPEC AMI IDs from Excel file."""
        ids = []
        
        df_dict = pd.read_excel(file_path, sheet_name=None)
        
        for sheet_name, sheet_df in df_dict.items():
            if 'SPEC_AMI_IDs' in sheet_name or re.search(r"spec_ami_ids", sheet_name, re.IGNORECASE):
                if 'SPEC_AMI_ID' in sheet_df.columns:
                    valid_ids = sheet_df['SPEC_AMI_ID'].dropna().astype(str).tolist()
                    ids.extend([id_val for id_val in valid_ids if re.match(r"^\d{6}$", id_val)])
                    
        return ids


class RecordProcessor:
    """Handles processing of FileMaker records and API calls."""
    
    def __init__(self, fm_client: FileMakerClient, platform_client: PlatformAPIClient, scsb_client: SCSBAPIClient):
        self.fm_client = fm_client
        self.platform_client = platform_client
        self.scsb_client = scsb_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_records(self, spec_ami_ids: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, BoxSummary]]:
        """Process all records and return details and box summary."""
        ami_id_details = []
        box_summary = defaultdict(BoxSummary)
        spec_ami_id_set = {str(i) for i in spec_ami_ids}
        
        for ami_id in sorted(spec_ami_ids):
            self.logger.info(f"Processing AMI ID: {ami_id}")
            
            records = self.fm_client.find_records({"ref_ami_id": ami_id})
            
            if not records:
                self.logger.warning(f"No records found for AMI ID: {ami_id}")
                continue
            
            for record in records:
                self._process_single_record(record, ami_id, spec_ami_id_set, ami_id_details, box_summary)
        
        return ami_id_details, dict(box_summary)
    
    def _process_single_record(self, record: Dict[str, Any], ami_id: str, spec_ami_id_set: Set[str], 
                              ami_id_details: List[Dict[str, Any]], box_summary: Dict[str, BoxSummary]) -> None:
        """Process a single FileMaker record."""
        box_barcode = record.get('OBJECTS_parent_from_OBJECTS::id_barcode')
        box_name = record.get('OBJECTS_parent_from_OBJECTS::name_d_calc', 'No Box')
        
        # Initialize box summary if needed
        if box_name not in box_summary:
            box_summary[box_name] = BoxSummary()
            box_summary[box_name].box_barcode = box_barcode or 'No Barcode'
            box_summary[box_name].spec_box_location = record.get('OBJECTS_parent_from_OBJECTS::ux_loc_active_d', 'Not Specified')
        
        if not box_barcode:
            self._handle_single_item(record, ami_id, ami_id_details, box_summary[box_name])
        else:
            self._handle_box_item(record, ami_id, box_barcode, box_name, spec_ami_id_set, ami_id_details, box_summary)
    
    def _handle_single_item(self, record: Dict[str, Any], ami_id: str, 
                           ami_id_details: List[Dict[str, Any]], box_summary: BoxSummary) -> None:
        """Handle items without a box barcode."""
        ami_barcode = record.get('id_barcode')
        
        if ami_barcode:
            self.logger.info(f"Handling single item in SCSB: {ami_barcode}")
            scsb_availability = self.scsb_client.extract_availability_status(
                self.scsb_client.get_availability(ami_barcode)
            )
        else:
            scsb_availability = 'No Barcode for Single Item'
        
        sierra_location_code, sierra_location_display = 'N/A', 'N/A'
        
        self._update_details_and_summary(
            record, ami_id, ami_barcode, sierra_location_code, sierra_location_display,
            ami_id_details, box_summary, scsb_availability
        )
    
    def _handle_box_item(self, record: Dict[str, Any], ami_id: str, box_barcode: str, box_name: str,
                        spec_ami_id_set: Set[str], ami_id_details: List[Dict[str, Any]], 
                        box_summary: Dict[str, BoxSummary]) -> None:
        """Handle items with a box barcode."""
        # Get all items in the box (only once per box)
        if box_summary[box_name].total_box_items == 0:
            box_records = self.fm_client.find_records({"OBJECTS_parent_from_OBJECTS::id_barcode": box_barcode})
            
            self.logger.info(f"Found {len(box_records)} items in box {box_name} with barcode {box_barcode}")
            
            # Update box summary with total items and migration statuses
            box_summary[box_name].total_box_items = len(box_records)
            
            # Process migration statuses for all items in the box
            for box_record in box_records:
                box_ami_id = str(box_record.get('ref_ami_id'))
                migration_status = box_record.get('OBJECTS_MIGRATION_STATUS_active::migration_status')
                
                if box_ami_id in spec_ami_id_set:
                    box_summary[box_name].requested_migration_statuses.add_status(migration_status)
                else:
                    box_summary[box_name].remaining_migration_statuses.add_status(migration_status)
        
        # Get Sierra and SCSB data (only once per box)
        if not box_summary[box_name].scsb_availabilities:
            platform_data = self.platform_client.get_sierra_item(box_barcode)
            sierra_location_code, sierra_location_display = self.platform_client.extract_sierra_location(platform_data)
            
            scsb_response = self.scsb_client.get_availability(box_barcode)
            scsb_availability = self.scsb_client.extract_availability_status(scsb_response)
            
            box_summary[box_name].scsb_availabilities.add(scsb_availability)
        else:
            sierra_location_code, sierra_location_display = 'N/A', 'N/A'
            scsb_availability = list(box_summary[box_name].scsb_availabilities)[0]
        
        self._update_details_and_summary(
            record, ami_id, box_barcode, sierra_location_code, sierra_location_display,
            ami_id_details, box_summary[box_name], scsb_availability
        )
    
    def _update_details_and_summary(self, record: Dict[str, Any], ami_id: str, barcode: Optional[str],
                                   sierra_location_code: str, sierra_location_display: str,
                                   ami_id_details: List[Dict[str, Any]], box_summary: BoxSummary,
                                   scsb_availability: str) -> None:
        """Update AMI ID details and box summary."""
        box_name = record.get('OBJECTS_parent_from_OBJECTS::name_d_calc', 'No Box')
        box_barcode = record.get('OBJECTS_parent_from_OBJECTS::id_barcode', 'No Barcode')
        
        ami_id_detail = {
            'AMI ID': ami_id,
            'Barcode': record.get('id_barcode'),
            'Format': self._get_item_format(record),
            'Migration Status': record.get('OBJECTS_MIGRATION_STATUS_active::migration_status'),
            'SPEC Item Location': record.get('ux_loc_active_d', ''),
            'Box Name': box_name,
            'Box Barcode': box_barcode,
            'Sierra Location Code': sierra_location_code,
            'Sierra Location Name': sierra_location_display,
            'SCSB Availability': scsb_availability
        }
        
        ami_id_details.append(ami_id_detail)
        
        # Update box summary formats for requested items only
        format_name = self._get_item_format(record)
        box_summary.formats[format_name] += 1
        
        # For single items, add the migration status to requested items
        if box_barcode == 'No Barcode':
            migration_status = record.get('OBJECTS_MIGRATION_STATUS_active::migration_status')
            box_summary.requested_migration_statuses.add_status(migration_status)
            box_summary.total_box_items = 1
    
    @staticmethod
    def _get_item_format(record: Dict[str, Any]) -> str:
        """Get item format from record data."""
        format_2 = record.get('format_2', '')
        format_3 = record.get('format_3', '')
        return format_3 if format_3 else format_2


class ExcelExporter:
    """Handles exporting data to Excel files."""
    
    @staticmethod
    def export_to_excel(output_path: str, ami_id_details: List[Dict[str, Any]], box_summary: Dict[str, BoxSummary]) -> None:
        """Export all data to Excel file with multiple sheets."""
        details_df = pd.DataFrame(ami_id_details)
        overview_df, formats_df = ExcelExporter._prepare_summary_dataframes(box_summary)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            details_df.to_excel(writer, sheet_name='AMI ID Details', index=False)
            overview_df.to_excel(writer, sheet_name='Box Summary', index=False)
            formats_df.to_excel(writer, sheet_name='Format Counts', index=False)
            
            ExcelExporter._apply_formatting(writer)
            ExcelExporter._adjust_column_widths(writer)
        
        logging.info(f"Exported details to {output_path} with sheets: 'AMI ID Details', 'Box Summary', and 'Format Counts'.")
    
    @staticmethod
    def _prepare_summary_dataframes(box_summary: Dict[str, BoxSummary]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare summary DataFrames from box summary data."""
        overview = []
        formats = []
        
        for box_name, details in box_summary.items():
            # For the overview, we want to match the original format but with migration status details
            total_requested = details.total_requested_items
            total_remaining = details.total_remaining_items
            
            # Format the requested-items display
            if total_requested > 0:
                requested_display = f"{total_requested}"
                status_count = len(details.requested_migration_statuses.counts)

                if status_count == 1:
                    # exactly one migration status → show just the status name
                    status_name = next(iter(details.requested_migration_statuses.counts))
                    requested_display += f" ({status_name})"
                elif status_count > 1:
                    status_parts = [
                        f"{count} {status}"
                        for status, count in sorted(details.requested_migration_statuses.counts.items())
                    ]
                    requested_display += f" ({', '.join(status_parts)})"
            else:
                requested_display = "0"

            # Do the same for remaining_display
            if total_remaining > 0:
                remaining_display = f"{total_remaining}"
                status_count = len(details.remaining_migration_statuses.counts)

                if status_count == 1:
                    status_name = next(iter(details.remaining_migration_statuses.counts))
                    remaining_display += f" ({status_name})"
                elif status_count > 1:
                    status_parts = [
                        f"{count} {status}"
                        for status, count in sorted(details.remaining_migration_statuses.counts.items())
                    ]
                    remaining_display += f" ({', '.join(status_parts)})"
            else:
                remaining_display = "0"
            
            overview.append({
                'Box Name': box_name,
                'Box Barcode': details.box_barcode,
                'SPEC Box Location': details.spec_box_location,
                'Total Requested Items': requested_display,
                'Remaining Items in Box': remaining_display,
                'SCSB Availability': ', '.join(details.scsb_availabilities)
            })
            
            for format_name, count in details.formats.items():
                formats.append({
                    'Box Name': box_name,
                    'Format': format_name,
                    'Count': count
                })
        
        overview_df = pd.DataFrame(overview)
        formats_df = pd.DataFrame(formats)
        
        if not formats_df.empty:
            # Group and sort formats
            formats_df = formats_df.groupby(['Box Name', 'Format']).sum().reset_index()
            formats_df = formats_df.sort_values(by=['Box Name', 'Format'])
            
            # Add total row
            total_items = formats_df['Count'].sum()
            total_row = pd.DataFrame([{
                'Box Name': 'Total',
                'Format': '',
                'Count': total_items
            }])
            formats_df = pd.concat([formats_df, total_row], ignore_index=True)
        
        return overview_df, formats_df
    
    @staticmethod
    def _apply_formatting(writer: pd.ExcelWriter) -> None:
        """Apply formatting to Excel sheets."""
        if 'Format Counts' in writer.sheets:
            format_sheet = writer.sheets['Format Counts']
            
            # Apply bold formatting to total row
            for row in format_sheet.iter_rows(min_row=1, max_row=format_sheet.max_row, min_col=1, max_col=3):
                if row[0].value == 'Total':
                    for cell in row:
                        cell.font = Font(bold=True)
    
    @staticmethod
    def _adjust_column_widths(writer: pd.ExcelWriter) -> None:
        """Adjust column widths for all sheets."""
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter
                
                for cell in col:
                    try:
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column].width = adjusted_width


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process SPEC AMI IDs using FileMaker database and APIs."
    )
    parser.add_argument(
        '-u', '--username',
        required=True,
        help="Username for the FileMaker database"
    )
    parser.add_argument(
        '-p', '--password',
        required=True,
        help="Password for the FileMaker database"
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help="Path to input file containing SPEC AMI IDs"
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help="Path to output XLSX file for exported data"
    )
    return parser.parse_args()


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main() -> None:
    """Main application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        args = parse_arguments()
        config = Config()
        
        logger.info("Starting SPEC AMI processing...")
        
        # Initialize clients
        fm_client = FileMakerClient(config)
        platform_client = PlatformAPIClient(config)
        scsb_client = SCSBAPIClient(config)
        
        # Connect to services
        if not fm_client.connect(args.username, args.password):
            logger.error("Failed to connect to FileMaker database")
            return
        
        if not platform_client.connect():
            logger.error("Failed to connect to Platform API")
            return
        
        # Read input file
        spec_ami_ids = FileProcessor.read_spec_ami_ids(args.input)
        if not spec_ami_ids:
            logger.error("No valid SPEC AMI IDs found in input file")
            return
        
        logger.info(f"Found {len(spec_ami_ids)} SPEC AMI IDs to process")
        
        # Process records
        processor = RecordProcessor(fm_client, platform_client, scsb_client)
        ami_id_details, box_summary = processor.process_records(spec_ami_ids)
        
        # Export results
        ExcelExporter.export_to_excel(args.output, ami_id_details, box_summary)
        
        logger.info("Processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise
    finally:
        # Cleanup
        if 'fm_client' in locals():
            fm_client.disconnect()


if __name__ == "__main__":
    main()