#!/usr/bin/env python3
"""
AMI Collection Processor - Enhanced Version

A tool for fetching, processing, and reporting on AMI collection items
and their migration status from FileMaker databases.
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime, date

try:
    from fmrest import Server
except ImportError:
    logging.error("fmrest package not found. Install with: pip install python-fmrest")
    sys.exit(1)

# Set up enhanced styling
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Constants
DEFAULT_PAGE_SIZE = 100
MAX_COLUMN_WIDTH = 50
MIN_COLUMN_WIDTH = 8
EXCLUDED_FORMATS = frozenset([
    'box - record carton',
    'box (unspecified type)', 
    'box - vhs video',
    'box - document',
    'digital file',
    'digital directory',
    'box - card file',
    'box - flat',
    'film canister',
    'manuscript',
    'poster',
    'painting',
    'folder',
    '3-D object',
    'box - transfile',
    'tube',
    'painting'
    
])

# Color scheme for professional reports
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72', 
    'accent': '#F18F01',
    'success': '#C73E1D',
    'neutral': '#7F7F7F',
    'background': '#F5F5F5'
}


def sanitize_sheet_name(name: str) -> str:
    """
    Sanitize sheet name for Excel compatibility.
    Remove invalid Excel sheet chars: [ ] : * ? / \\
    """
    cleaned = re.sub(r"[\[\]\:\*\?/\\]", '_', name)
    return cleaned[:31] or 'Sheet'


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


class FileMakerConnectionError(Exception):
    """Raised when FileMaker connection fails."""
    pass


class Config:
    """Configuration management for FileMaker connection."""
    
    def __init__(self):
        self.server = os.getenv('FM_SERVER')
        self.database = os.getenv('FM_DATABASE')
        self.layout = os.getenv('FM_LAYOUT')
        self._validate()

    def _validate(self) -> None:
        """Validate that required environment variables are set."""
        missing_vars = []
        for var_name, value in [
            ('FM_SERVER', self.server),
            ('FM_DATABASE', self.database),
            ('FM_LAYOUT', self.layout)
        ]:
            if not value:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

    def __str__(self) -> str:
        return f"Config(server={self.server}, database={self.database}, layout={self.layout})"


class FileMakerClient:
    """Enhanced FileMaker client with better error handling and logging."""
    
    def __init__(self, config: Config):
        self.config = config
        self.fms: Optional[Server] = None
        self._connected = False

    def connect(self, username: str, password: str) -> bool:
        """
        Connect to FileMaker server with enhanced error handling.
        
        Args:
            username: FileMaker username
            password: FileMaker password
            
        Returns:
            bool: True if connection successful
            
        Raises:
            FileMakerConnectionError: If connection fails
        """
        try:
            url = f"https://{self.config.server}"
            logging.info(f"Connecting to FileMaker at {self.config.server}...")
            
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
            self._connected = True
            logging.info(f"Successfully connected to database '{self.config.database}' "
                        f"on layout '{self.config.layout}'")
            return True
            
        except Exception as e:
            logging.error(f"Failed to connect to FileMaker: {e}")
            raise FileMakerConnectionError(f"Connection failed: {e}") from e

    def find_all(self, query: Dict[str, Any], page_size: int = DEFAULT_PAGE_SIZE) -> List[Dict[str, Any]]:
        """
        Fetch all records matching query with pagination.
        
        Args:
            query: FileMaker query dictionary
            page_size: Records per page
            
        Returns:
            List of record dictionaries
            
        Raises:
            FileMakerConnectionError: If not connected or query fails
        """
        if not self._connected or not self.fms:
            raise FileMakerConnectionError("Not connected to FileMaker")

        offset = 1
        all_records: List[Dict[str, Any]] = []
        
        logging.info(f"Starting paginated fetch for query: {query}")
        
        while True:
            try:
                page = self.fms.find([query], offset=offset, limit=page_size)
                records = [record.to_dict() for record in page]
                logging.info(f"Fetched {len(records)} records (offset {offset})")
                logging.debug(f"Fetched {len(records)} records (offset {offset})")
                all_records.extend(records)
                
                # Break if we got fewer records than requested (last page)
                if len(records) < page_size:
                    break
                    
                offset += page_size
                
            except Exception as e:
                logging.error(f"Error fetching records at offset {offset}: {e}")
                raise FileMakerConnectionError(f"Query failed: {e}") from e

        logging.info(f"Total records fetched: {len(all_records)}")
        return all_records

    def disconnect(self) -> None:
        """Disconnect from FileMaker server."""
        if self.fms and self._connected:
            try:
                self.fms.logout()
                logging.info("Disconnected from FileMaker")
            except Exception as e:
                logging.warning(f"Error during disconnect: {e}")
            finally:
                self._connected = False


class CollectionProcessor:
    """Enhanced processor for AMI collection data with improved data handling."""
    
    def __init__(self, fm_client: FileMakerClient):
        self.fm = fm_client

    def fetch_items(self, collection_id: str) -> pd.DataFrame:
        """
        Fetch and process items for a given collection.
        
        Args:
            collection_id: Collection identifier
            
        Returns:
            DataFrame with processed collection items
        """
        logging.info(f"Fetching items for collection ID: {collection_id}")
        
        query = {'ref_collection_id': collection_id}
        records = self.fm.find_all(query)
        
        if not records:
            logging.warning(f"No records found for collection ID: {collection_id}")
            return pd.DataFrame()

        # Process records into structured data
        processed_rows = []
        for record in records:
            processed_rows.append({
                'AMI ID': self._clean_ami_id(record.get('ref_ami_id')),
                'Classmark': self._clean_string(record.get('OBJ_AMI_ITEMS_from_OBJECTS::id.classmark')),
                'Barcode': self._clean_string(record.get('id_barcode')),
                'Title': self._clean_string(record.get('id_label_text')),
                'Migration Status': self._clean_string(record.get('OBJECTS_MIGRATION_STATUS_active::migration_status')),
                'Format 1': self._clean_string(record.get('format_1')),
                'Format 2': self._clean_string(record.get('format_2')),
                'Format 3': self._clean_string(record.get('format_3')),
                'Box Name': self._clean_string(record.get('OBJECTS_parent_from_OBJECTS::name_d_calc')),
                'Box Barcode': self._clean_string(record.get('OBJECTS_parent_from_OBJECTS::id_barcode')),
                'Location': self._clean_string(record.get('ux_loc_active_d'))
            })
        
        df = pd.DataFrame(processed_rows)
        logging.info(f"Built DataFrame with {len(df)} rows and {len(df.columns)} columns")
        
        return df

    @staticmethod
    def _clean_string(value: Any) -> str:
        """Clean and normalize string values."""
        if value is None:
            return ''
        return str(value).strip()

    @staticmethod
    def _clean_ami_id(value: Any) -> Optional[int]:
        """Clean and convert AMI ID to integer."""
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None

    def apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply business logic filters to the DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df

        initial_count = len(df)
        
        # Filter 1: Exclude records with no barcode, unmigrated, and object inactive
        exclusion_mask = (
            (df['Barcode'] == '') &
            (df['Migration Status'] == 'Unmigrated') &
            (df['Location'] == 'Object inactive')
        )
        df = df[~exclusion_mask]
        excluded_inactive = exclusion_mask.sum()
        
        # Drop the Location column as it's no longer needed
        df = df.drop(columns=['Location'], errors='ignore')
        
        # Filter 2: Exclude unwanted formats
        format_mask = df['Format 1'].str.lower().isin(EXCLUDED_FORMATS)
        df = df[~format_mask]
        excluded_formats = format_mask.sum()
        
        logging.info(f"Applied filters: {initial_count} → {len(df)} records "
                    f"(excluded {excluded_inactive} inactive, {excluded_formats} unwanted formats)")
        
        return df

    def separate_digital_carriers(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Separate digital carriers from main dataset.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (main_df, digital_carriers_df)
        """
        if df.empty:
            return df, pd.DataFrame()

        digital_mask = df['Format 1'].str.lower() == 'digital carrier'
        df_digital = df[digital_mask].copy()
        df_main = df[~digital_mask].copy()
        
        logging.info(f"Separated digital carriers: {len(df_digital)} carriers, "
                    f"{len(df_main)} main records")
        
        return df_main, df_digital

    def sort_by_ami_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sort DataFrame by AMI ID with proper handling of non-numeric values."""
        if df.empty or 'AMI ID' not in df.columns:
            return df

        # Convert to numeric, invalid parsing will be NaN
        df = df.copy()
        df['AMI ID'] = pd.to_numeric(df['AMI ID'], errors='coerce')
        df = df.sort_values(by='AMI ID', na_position='last')
        
        logging.info("Sorted DataFrame by AMI ID")
        return df


class ReportGenerator:
    """Enhanced report generator with professional visualizations."""
    
    def __init__(self, collection_id: str):
        self.collection_id = collection_id
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def generate_excel(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                      output_file: str) -> None:
        """
        Generate Excel report with multiple sheets and formatting.
        
        Args:
            df_main: Main DataFrame
            df_digital: Digital carriers DataFrame  
            output_file: Output file path
        """
        logging.info(f"Generating Excel report: {output_file}")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Main sheet
            if not df_main.empty:
                df_main.to_excel(writer, sheet_name='All Records', index=False)
                logging.info(f"Wrote 'All Records' sheet with {len(df_main)} rows")
                
                # Create sheets by migration status
                self._create_status_sheets(df_main, writer)
            
            # Digital carriers sheet
            if not df_digital.empty:
                df_digital.to_excel(writer, sheet_name='Digital Carriers', index=False)
                logging.info(f"Wrote 'Digital Carriers' sheet with {len(df_digital)} rows")
            
            # Format all sheets
            self._format_excel_sheets(writer)

    def _create_status_sheets(self, df: pd.DataFrame, writer: pd.ExcelWriter) -> None:
        """Create separate sheets for each migration status."""
        status_values = df['Migration Status'].fillna('Unknown').unique()
        
        for status in status_values:
            # Create safe sheet name using the sanitization function
            safe_name = sanitize_sheet_name(str(status).strip() or 'Unknown')
            
            subset = df[df['Migration Status'] == status]
            if not subset.empty:
                subset.to_excel(writer, sheet_name=safe_name, index=False)
                logging.info(f"Wrote '{safe_name}' sheet with {len(subset)} rows")

    def _format_excel_sheets(self, writer: pd.ExcelWriter) -> None:
        """Apply formatting to Excel sheets."""
        for sheet_name, worksheet in writer.sheets.items():
            # Auto-adjust column widths using the original working method
            for col_cells in worksheet.columns:
                max_length = 0
                col_letter = col_cells[0].column_letter
                for cell in col_cells:
                    try:
                        length = len(str(cell.value)) if cell.value is not None else 0
                        if length > max_length:
                            max_length = length
                    except:
                        pass
                worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
            logging.info("Adjusted column widths on sheet '%s'", sheet_name)

    def generate_pdf_report(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                           output_file: str) -> None:
        """
        Generate streamlined PDF report with essential visualizations.
        
        Args:
            df_main: Main DataFrame
            df_digital: Digital carriers DataFrame
            output_file: Output PDF file path
        """
        logging.info(f"Generating PDF report: {output_file}")
        
        with PdfPages(output_file) as pdf:
            # Title page
            self._create_title_page(pdf)
            
            if not df_main.empty:
                # Summary statistics
                self._create_summary_page(df_main, df_digital, pdf)
                
                # Migration status analysis
                self._create_migration_status_chart(df_main, pdf)
                
                # Format analysis (streamlined)
                self._create_format_analysis_streamlined(df_main, pdf)

    def _create_title_page(self, pdf: PdfPages) -> None:
        """Create professional title page."""
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        
        # Add background color
        fig.patch.set_facecolor(COLORS['background'])
        
        # Title section
        ax.text(0.5, 0.75, 'AMI Collection Digitization Status Report', 
               ha='center', va='center', fontsize=28, fontweight='bold',
               color=COLORS['primary'])
        
        # Subtitle
        ax.text(0.5, 0.65, f'Collection ID: {self.collection_id}',
               ha='center', va='center', fontsize=18, 
               color=COLORS['secondary'])
        
        # Date
        ax.text(0.5, 0.55, f'Generated: {self.timestamp}',
               ha='center', va='center', fontsize=14,
               color=COLORS['neutral'])
        
        # Add decorative line
        line = plt.Line2D([0.2, 0.8], [0.45, 0.45], color=COLORS['accent'], linewidth=2)
        ax.add_line(line)
        
        # Footer
        ax.text(0.5, 0.1, 'New York Public Library\nAudio and Moving Image Preservation (AMIP)',
               ha='center', va='center', fontsize=10,
               color=COLORS['neutral'], style='italic')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_summary_page(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                            pdf: PdfPages) -> None:
        """Create summary statistics page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Collection Summary Statistics', fontsize=16, fontweight='bold')
        
        # Summary metrics
        total_items = len(df_main) + len(df_digital)
        ax1.axis('off')
        
        summary_text = f"""
        Total Items: {total_items:,}
        AMI Items: {len(df_main):,}
        Digital Carriers: {len(df_digital):,}
        
        Unique Formats: {df_main['Format 1'].nunique() if not df_main.empty else 0}
        Unique Boxes: {df_main['Box Name'].nunique() if not df_main.empty else 0}
        """
        
        ax1.text(0.1, 0.7, summary_text, fontsize=12, va='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS['background']))
        ax1.set_title('Overview', fontweight='bold')
        
        # Migration status pie chart (compact)
        if not df_main.empty and 'Migration Status' in df_main.columns:
            status_counts = df_main['Migration Status'].fillna('Unknown').value_counts()
            colors = sns.color_palette("husl", len(status_counts))
            
            ax2.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%',
                   colors=colors, startangle=90)
            ax2.set_title('Migration Status Distribution', fontweight='bold')
        else:
            ax2.text(0.5, 0.5, 'No Migration Status Data', ha='center', va='center')
            ax2.set_title('Migration Status', fontweight='bold')
        
        # Top formats
        if not df_main.empty:
            top_formats = df_main['Format 1'].value_counts().head(5)
            bars = ax3.barh(range(len(top_formats)), top_formats.values, 
                           color=sns.color_palette("viridis", len(top_formats)))
            ax3.set_yticks(range(len(top_formats)))
            ax3.set_yticklabels([f[:20] + '...' if len(f) > 20 else f 
                               for f in top_formats.index])
            ax3.set_xlabel('Count')
            ax3.set_title('Media Types', fontweight='bold')
            
            # Add value labels on bars
            for i, v in enumerate(top_formats.values):
                ax3.text(v + 0.1, i, str(v), va='center')
        else:
            ax3.text(0.5, 0.5, 'No Format Data', ha='center', va='center')
            ax3.set_title('Top Formats', fontweight='bold')
        
        # Items by box (if applicable)
        if not df_main.empty and df_main['Box Name'].notna().any():
            box_counts = df_main['Box Name'].value_counts().head(10)
            ax4.bar(range(len(box_counts)), box_counts.values,
                   color=sns.color_palette("plasma", len(box_counts)))
            ax4.set_xticks(range(len(box_counts)))
            ax4.set_xticklabels([f'Box {i+1}' for i in range(len(box_counts))],
                              rotation=45)
            ax4.set_ylabel('Item Count')
            ax4.set_title('Items per Box (Top 10)', fontweight='bold')
        else:
            ax4.text(0.5, 0.5, 'No Box Data', ha='center', va='center')
            ax4.set_title('Items per Box', fontweight='bold')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_migration_status_chart(self, df: pd.DataFrame, pdf: PdfPages) -> None:
        """Create detailed migration status analysis."""
        if df.empty or 'Migration Status' not in df.columns:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 6))
        fig.suptitle('Migration Status Analysis', fontsize=16, fontweight='bold')
        
        status_counts = df['Migration Status'].fillna('Unknown').value_counts()
        
        # Enhanced pie chart
        colors = sns.color_palette("Set3", len(status_counts))
        wedges, texts, autotexts = ax1.pie(status_counts.values, labels=status_counts.index,
                                          autopct='%1.1f%%', colors=colors, startangle=90,
                                          explode=[0.05] * len(status_counts))
        
        # Enhance text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax1.set_title('Migration Status Distribution', fontweight='bold', pad=20)
        
        # Bar chart with counts
        bars = ax2.bar(range(len(status_counts)), status_counts.values,
                      color=colors)
        ax2.set_xticks(range(len(status_counts)))
        ax2.set_xticklabels(status_counts.index, rotation=45, ha='right')
        ax2.set_ylabel('Count')
        ax2.set_title('Migration Status Counts', fontweight='bold')
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{int(height)}', ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_format_analysis_streamlined(self, df: pd.DataFrame, pdf: PdfPages) -> None:
        """Create streamlined format analysis without combinations heatmap."""
        if df.empty:
            return

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Format Analysis', fontsize=16, fontweight='bold')
        
        # Format 1 analysis
        if 'Format 1' in df.columns:
            fmt1_counts = df['Format 1'].value_counts().head(8)
            bars1 = ax1.bar(range(len(fmt1_counts)), fmt1_counts.values,
                           color=sns.color_palette("viridis", len(fmt1_counts)))
            ax1.set_xticks(range(len(fmt1_counts)))
            ax1.set_xticklabels([f[:15] + '...' if len(f) > 15 else f 
                               for f in fmt1_counts.index], rotation=45, ha='right')
            ax1.set_ylabel('Count')
            ax1.set_title('Primary Format Types', fontweight='bold')
            
            # Add value labels
            for bar in bars1:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{int(height)}', ha='center', va='bottom', fontsize=8)
        
        # Format 3 (most specific) analysis  
        if 'Format 3' in df.columns:
            fmt3_counts = df['Format 3'].fillna('Unknown').value_counts().head(10)
            ax2.barh(range(len(fmt3_counts)), fmt3_counts.values,
                    color=sns.color_palette("plasma", len(fmt3_counts)))
            ax2.set_yticks(range(len(fmt3_counts)))
            ax2.set_yticklabels([f[:20] + '...' if len(f) > 20 else f 
                               for f in fmt3_counts.index])
            ax2.set_xlabel('Count')
            ax2.set_title('Specific Format Types (Top 10)', fontweight='bold')
        
        # Format 2 analysis
        if 'Format 2' in df.columns:
            fmt2_counts = df['Format 2'].fillna('Unknown').value_counts().head(8)
            bars3 = ax3.bar(range(len(fmt2_counts)), fmt2_counts.values,
                           color=sns.color_palette("muted", len(fmt2_counts)))
            ax3.set_xticks(range(len(fmt2_counts)))
            ax3.set_xticklabels([f[:15] + '...' if len(f) > 15 else f 
                               for f in fmt2_counts.index], rotation=45, ha='right')
            ax3.set_ylabel('Count')
            ax3.set_title('Secondary Format Types', fontweight='bold')
            
            # Add value labels
            for bar in bars3:
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{int(height)}', ha='center', va='bottom', fontsize=8)
        
        # Stacked bar for migration status by format
        if 'Migration Status' in df.columns and 'Format 1' in df.columns:
            status_format = pd.crosstab(df['Format 1'], df['Migration Status'].fillna('Unknown'))
            status_format.head(8).plot(kind='bar', stacked=True, ax=ax4,
                                     colormap='Set3')
            ax4.set_title('Migration Status by Format', fontweight='bold')
            ax4.set_xlabel('Format 1')
            ax4.set_ylabel('Count')
            ax4.legend(title='Migration Status', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments with enhanced validation."""
    parser = argparse.ArgumentParser(
        description="AMI Collection Processor - Generate reports on AMI digitization status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -u username -p password -c COLL123
  %(prog)s -u username -p password -c COLL123 -o custom_report.xlsx --pdf --verbose
        """
    )
    
    parser.add_argument('-u', '--username', required=True,
                       help='FileMaker database username')
    parser.add_argument('-p', '--password', required=True,
                       help='FileMaker database password')
    parser.add_argument('-c', '--collection-id', required=True,
                       help='Collection ID to query')
    parser.add_argument('-o', '--output',
                       help='Excel output file (default: ~/Desktop/<collection-id>_Migration_Status.xlsx)')
    parser.add_argument('--pdf', action='store_true',
                       help='Generate PDF report alongside Excel file')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    
    return parser.parse_args()


def validate_output_path(output_path: str) -> Path:
    """Validate and create output path."""
    path = Path(output_path)
    
    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if we can write to the location
    try:
        path.touch(exist_ok=True)
        path.unlink()  # Remove the test file
    except PermissionError:
        raise PermissionError(f"Cannot write to {path}")
    
    return path


def main() -> int:
    """Main application entry point with comprehensive error handling."""
    try:
        args = parse_arguments()
        setup_logging(args.verbose)

        logging.info("Starting AMI Collection Processor")
        logging.info(f"Collection ID: {args.collection_id}")

        # Initialize configuration
        try:
            config = Config()
            logging.info(f"Configuration: {config}")
        except ConfigurationError as e:
            logging.error(f"Configuration error: {e}")
            return 1

        # Determine default save directory (Desktop)
        desktop_dir = Path.home() / "Desktop"

        # Excel output: user override or ~/Desktop/<ID>_Migration_Status.xlsx
        if args.output:
            excel_file = Path(args.output)
        else:
            excel_file = desktop_dir / f"{args.collection_id}_Migration_Status.xlsx"
        excel_path = validate_output_path(str(excel_file))

        # PDF output: only if requested, saved as ~/Desktop/<ID>_Migration_Status.pdf
        pdf_path = None
        if args.pdf:
            pdf_file = desktop_dir / f"{args.collection_id}_Migration_Status.pdf"
            pdf_path = validate_output_path(str(pdf_file))

        # Initialize FileMaker client
        fm_client = FileMakerClient(config)

        try:
            # Connect to FileMaker
            fm_client.connect(args.username, args.password)

            # Fetch and process items
            processor = CollectionProcessor(fm_client)
            df = processor.fetch_items(args.collection_id)

            if df.empty:
                logging.warning("No data found for the specified collection ID")
                return 0

            # Apply filters, separate carriers, sort
            df = processor.apply_filters(df)
            df_main, df_digital = processor.separate_digital_carriers(df)
            df_main = processor.sort_by_ami_id(df_main)

            # Generate reports
            report_generator = ReportGenerator(args.collection_id)

            # Excel report
            report_generator.generate_excel(df_main, df_digital, str(excel_path))
            logging.info(f"Excel report completed: {excel_path}")

            # PDF report (if requested)
            if args.pdf and pdf_path:
                report_generator.generate_pdf_report(df_main, df_digital, str(pdf_path))
                logging.info(f"PDF report completed: {pdf_path}")

            # Final summary
            total_items = len(df_main) + len(df_digital)
            logging.info(f"Processing complete: {total_items} total items processed")
            logging.info(f"Main records: {len(df_main)}, Digital carriers: {len(df_digital)}")

        except FileMakerConnectionError as e:
            logging.error(f"FileMaker error: {e}")
            return 1

        finally:
            fm_client.disconnect()

    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
        return 130

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    logging.info("AMI Collection Processor completed successfully")
    return 0


if __name__ == '__main__':
    import sys
    from pathlib import Path

    sys.exit(main())
