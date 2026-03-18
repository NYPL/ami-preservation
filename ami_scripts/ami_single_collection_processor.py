#!/usr/bin/env python3
"""
AMI Collection Processor - Enhanced Version with AWS Validation

A tool for fetching, processing, and reporting on AMI collection items
and their migration status from FileMaker databases, with optional
S3 bucket validation for migrated assets.
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
from matplotlib.gridspec import GridSpec
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
EXCLUDED_FORMATS_RAW = [
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
    'painting',
    'custom enclosure - NYPL',
]

# Normalize to a case-insensitive set
EXCLUDED_FORMATS = frozenset(s.strip().casefold() for s in EXCLUDED_FORMATS_RAW)

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
    """Sanitize sheet name for Excel compatibility (max 31 chars)."""
    cleaned = re.sub(r"[\[\]\:\*\?/\\]", '_', name)
    if "Migration failed (will not retry)" in cleaned:
        return "Mig Fail (will not retry)"
    return cleaned[:31].strip() or 'Sheet'

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
        missing_vars = []
        for var_name, value in [
            ('FM_SERVER', self.server),
            ('FM_DATABASE', self.database),
            ('FM_LAYOUT', self.layout)
        ]:
            if not value:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def __str__(self) -> str:
        return f"Config(server={self.server}, database={self.database}, layout={self.layout})"


class AWSChecker:
    """Handles S3 bulk inventory building and dataframe augmentation."""
    def __init__(self, profile_name: Optional[str] = None):
        self.profile_name = profile_name
        self.bucket_name = 'ami-carnegie-servicecopies'
        self.s3_client = None
        self.inventory = defaultdict(list)

    def connect(self):
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound, TokenRetrievalError, SSOTokenLoadError
        except ImportError:
            logging.error("\n[ERROR] 'boto3' is required for the --check-aws flag.")
            logging.error("Install it by running: python3 -m pip install boto3\n")
            raise

        logging.info("Authenticating with AWS...")
        try:
            session = boto3.Session(profile_name=self.profile_name)
            sts = session.client('sts')
            sts.get_caller_identity() # Verify auth
            self.s3_client = session.client('s3')
            logging.info(f"AWS Authenticated. Profile: {session.profile_name}")
        except Exception as e:
            logging.error(f"AWS Authentication Failed: {e}")
            raise

    def build_inventory(self):
        """Pulls all keys from the bucket and maps 6-digit IDs to file lists."""
        logging.info(f"Building local S3 inventory from '{self.bucket_name}'. This may take a moment...")
        
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name)
        
        # Matches exactly 6 digits not surrounded by other digits
        id_pattern = re.compile(r'(?<!\d)(\d{6})(?!\d)')
        count = 0
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    count += 1
                    
                    # Find any 6-digit sequences in the filename
                    matches = id_pattern.findall(key)
                    for match in matches:
                        self.inventory[match].append(key)
                        
        logging.info(f"✅ S3 inventory built! Scanned {count:,} files and found {len(self.inventory):,} unique IDs.")

    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Injects S3 validation data into the dataframe for Migrated items."""
        if df.empty or 'AMI ID' not in df.columns or 'Migration Status' not in df.columns:
            return df
            
        df = df.copy()
        # Initialize columns
        df['S3 File Count'] = ''
        df['S3 Files'] = ''
        
        migrated_mask = df['Migration Status'].fillna('').str.strip().str.lower() == 'migrated'
        
        if not migrated_mask.any():
            return df

        # Apply mapping only to migrated items
        for idx, row in df[migrated_mask].iterrows():
            ami_id = row['AMI ID']
            if pd.isna(ami_id):
                continue
                
            # Ensure it's treated as a 6 digit string
            id_str = f"{int(ami_id):06d}"
            matched_files = self.inventory.get(id_str, [])
            
            df.at[idx, 'S3 File Count'] = len(matched_files)
            if matched_files:
                df.at[idx, 'S3 Files'] = ", ".join(matched_files)
                
        return df


class FileMakerClient:
    """Enhanced FileMaker client with better error handling and logging."""
    def __init__(self, config: Config):
        self.config = config
        self.fms: Optional[Server] = None
        self._connected = False

    def connect(self, username: str, password: str) -> bool:
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
            logging.info(f"Successfully connected to database '{self.config.database}' on layout '{self.config.layout}'")
            return True
            
        except Exception as e:
            logging.error(f"Failed to connect to FileMaker: {e}")
            raise FileMakerConnectionError(f"Connection failed: {e}") from e

    def find_all(self, query: Dict[str, Any], page_size: int = DEFAULT_PAGE_SIZE,
                 portals: Optional[Dict[str, Dict[str, int]]] = None) -> List[Dict[str, Any]]:        
        if not self._connected or not self.fms:
            raise FileMakerConnectionError("Not connected to FileMaker")

        offset = 1
        all_records: List[Dict[str, Any]] = []

        logging.info(f"Starting paginated fetch for query: {query}")
        while True:
            try:
                page = self.fms.find(
                    [query],
                    offset=offset,
                    limit=page_size,
                    portals=portals
                )

                records: List[Dict[str, Any]] = []
                for rec in page:
                    d = rec.to_dict()
                    for key in list(d.keys()):
                        if key.startswith('portal_'):
                            fs = getattr(rec, key, None)
                            if fs is not None:
                                d[key] = [row.to_dict() for row in fs]
                    records.append(d)

                all_records.extend(records)

                if len(records) < page_size:
                    break
                offset += page_size

            except Exception as e:
                logging.error(f"Error fetching records at offset {offset}: {e}")
                raise FileMakerConnectionError(f"Query failed: {e}") from e

        logging.info(f"Total records fetched: {len(all_records)}")
        return all_records

    def disconnect(self) -> None:
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
        logging.info(f"Fetching items for collection ID: {collection_id}")
        
        query = {'ref_collection_id': collection_id}
        records = self.fm.find_all(query)
        
        if not records:
            logging.warning(f"No records found for collection ID: {collection_id}")
            return pd.DataFrame()

        processed_rows = []
        for record in records:
            portal_obj = record.get('portal_OBJ_ISSUES', [])
            portal_rows = [row.to_dict() for row in portal_obj] if portal_obj and not isinstance(portal_obj, list) else (portal_obj or [])

            row_data = {
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
                'Location': self._clean_string(record.get('ux_loc_active_d')),
                'Active': record.get('active'),
            }
            
            issues_data = self._extract_issues_as_columns(portal_rows)
            row_data.update(issues_data)
            processed_rows.append(row_data)
        
        df = pd.DataFrame(processed_rows)
        logging.info(f"Built DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return df

    @staticmethod
    def _clean_string(value: Any) -> str:
        if value is None: return ''
        return str(value).strip()

    @staticmethod
    def _clean_ami_id(value: Any) -> Optional[int]:
        if value is None: return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None

    def apply_filters(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if df.empty:
            return df, pd.DataFrame()

        inactive_mask = (df['Active'].astype(str) == '0')
        df_inactive = df[inactive_mask].copy()
        df_active = df[~inactive_mask].copy()

        format_mask = df_active['Format 1'].str.lower().isin(EXCLUDED_FORMATS)
        df_active = df_active[~format_mask]
        
        excluded_formats_count = format_mask.sum()

        logging.info(
            f"Filter Results:\n"
            f" - Shunted to Inactive Sheet: {len(df_inactive)}\n"
            f" - Active records kept: {len(df_active)}\n"
            f" - Active records excluded (format filter): {excluded_formats_count}"
        )

        df_active = df_active.drop(columns=['Active', 'Location'], errors='ignore')
        df_inactive = df_inactive.drop(columns=['Active'], errors='ignore')

        return df_active, df_inactive

    def separate_digital_carriers(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if df.empty:
            return df, pd.DataFrame()

        digital_mask = df['Format 1'].str.lower() == 'digital carrier'
        df_digital = df[digital_mask].copy()
        df_main = df[~digital_mask].copy()
        
        logging.info(f"Separated digital carriers: {len(df_digital)} carriers, {len(df_main)} main records")
        return df_main, df_digital

    def sort_by_ami_id(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'AMI ID' not in df.columns:
            return df

        df = df.copy()
        df['AMI ID'] = pd.to_numeric(df['AMI ID'], errors='coerce')
        df = df.sort_values(by='AMI ID', na_position='last')
        return df
    
    def _extract_issues_as_columns(self, portal_rows: list) -> Dict[str, Any]:
        if not portal_rows:
            return {'Issues (count)': 0}

        issues_data = {'Issues (count)': len(portal_rows)}
        for i, row in enumerate(portal_rows, 1):
            issues_data[f'Issue {i} Type'] = self._clean_string(row.get('OBJ_ISSUES::type'))
            issues_data[f'Issue {i}'] = self._clean_string(row.get('OBJ_ISSUES::issue'))
            issues_data[f'Issue {i} Notes'] = self._clean_string(row.get('OBJ_ISSUES::notes'))
            
        return issues_data


class ReportGenerator:
    """Enhanced report generator with professional visualizations."""
    def __init__(self, collection_id: str):
        self.collection_id = collection_id
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def generate_excel(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                        df_inactive: pd.DataFrame, output_file: str) -> None:
        logging.info(f"Generating Excel report: {output_file}")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            if not df_main.empty:
                df_main.to_excel(writer, sheet_name='All Records', index=False)
                self._create_status_sheets(df_main, writer)
            
            if not df_digital.empty:
                df_digital.to_excel(writer, sheet_name='Digital Carriers', index=False)

            if not df_inactive.empty:
                df_inactive.to_excel(writer, sheet_name='Inactive Records', index=False)
            
            self._format_excel_sheets(writer)

    def _create_status_sheets(self, df: pd.DataFrame, writer: pd.ExcelWriter) -> None:
        status_values = df['Migration Status'].fillna('Unknown').unique()
        for status in status_values:
            safe_name = sanitize_sheet_name(str(status).strip() or 'Unknown')
            subset = df[df['Migration Status'] == status]
            if not subset.empty:
                subset.to_excel(writer, sheet_name=safe_name, index=False)
                logging.info(f"Wrote '{safe_name}' sheet with {len(subset)} rows")

    def _format_excel_sheets(self, writer: pd.ExcelWriter) -> None:
        for sheet_name, worksheet in writer.sheets.items():
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

    def generate_pdf_report(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                           output_file: str) -> None:
        logging.info(f"Generating PDF report: {output_file}")
        
        with PdfPages(output_file) as pdf:
            self._create_title_page(pdf)
            if not df_main.empty:
                self._create_summary_page(df_main, df_digital, pdf)
                self._create_migration_status_chart(df_main, pdf)
                self._create_format_analysis_streamlined(df_main, pdf)

    def _create_title_page(self, pdf: PdfPages) -> None:
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        fig.patch.set_facecolor(COLORS['background'])
        
        ax.text(0.5, 0.75, 'AMI Collection\nDigitization Status Report', 
               ha='center', va='center', fontsize=28, fontweight='bold',
               color=COLORS['primary'])
        
        ax.text(0.5, 0.65, f'Collection ID: {self.collection_id}',
               ha='center', va='center', fontsize=18, 
               color=COLORS['secondary'])
        
        ax.text(0.5, 0.55, f'Generated: {self.timestamp}',
               ha='center', va='center', fontsize=14,
               color=COLORS['neutral'])
        
        line = plt.Line2D([0.2, 0.8], [0.45, 0.45], color=COLORS['accent'], linewidth=2)
        ax.add_line(line)
        
        ax.text(0.5, 0.1, 'New York Public Library\nAudio and Moving Image Preservation (AMIP)',
               ha='center', va='center', fontsize=10,
               color=COLORS['neutral'], style='italic')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_summary_page(self, df_main: pd.DataFrame, df_digital: pd.DataFrame, 
                            pdf: PdfPages) -> None:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Collection Summary Statistics', fontsize=18, fontweight='bold', y=0.96)
        
        total_items = len(df_main) + len(df_digital)
        ax1.axis('off')
        
        summary_text = f"""Total Items: {total_items:,}
    AMI Items: {len(df_main):,}
    Digital Carriers: {len(df_digital):,}

    Unique Formats: {df_main['Format 1'].nunique() if not df_main.empty else 0}
    Unique Boxes: {df_main['Box Name'].nunique() if not df_main.empty else 0}"""
        
        bbox_props = dict(
            boxstyle="round,pad=0.6", 
            facecolor=COLORS['background'],
            edgecolor=COLORS['primary'],
            linewidth=2,
            alpha=0.95
        )
        
        ax1.text(0.5, 0.45, summary_text, 
                fontsize=12, 
                ha='center', va='center',
                bbox=bbox_props,
                transform=ax1.transAxes,
                linespacing=1.6)
        ax1.set_title('Overview', fontweight='bold', fontsize=14, pad=20, y=0.95)
        
        if not df_main.empty and 'Migration Status' in df_main.columns:
            status_counts = df_main['Migration Status'].fillna('Unknown').value_counts()
            
            total_count = status_counts.sum()
            threshold = 0.03
            small_segments = status_counts[status_counts / total_count < threshold]
            large_segments = status_counts[status_counts / total_count >= threshold]
            
            if len(small_segments) > 0:
                combined_counts = large_segments.copy()
                if len(small_segments) > 1:
                    combined_counts['Other'] = small_segments.sum()
                else:
                    combined_counts = pd.concat([large_segments, small_segments])
            else:
                combined_counts = status_counts
            
            colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#7F7F7F', '#4CAF50', '#FF9800'][:len(combined_counts)]
            
            wedges, texts, autotexts = ax2.pie(
                combined_counts.values, 
                labels=combined_counts.index,
                autopct=lambda pct: f'{pct:.1f}%' if pct > 4 else '',
                colors=colors, 
                startangle=90,
                textprops={'fontsize': 10, 'fontweight': 'bold'},
                wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
            )
            
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(9)
            
            ax2.set_title('Migration Status Distribution', fontweight='bold', fontsize=14, pad=20, y=0.95)
        else:
            ax2.text(0.5, 0.5, 'No Migration Status Data', ha='center', va='center', fontsize=12)
            ax2.set_title('Migration Status Distribution', fontweight='bold', fontsize=14, pad=20, y=0.95)
        
        if not df_main.empty:
            top_formats = df_main['Format 1'].value_counts().head(6)
            colors_gradient = plt.cm.viridis(np.linspace(0.2, 0.8, len(top_formats)))
            
            bars = ax3.barh(range(len(top_formats)), top_formats.values, 
                        color=colors_gradient, 
                        edgecolor='white', linewidth=1)
            
            ax3.set_yticks(range(len(top_formats)))
            ax3.set_yticklabels([f[:25] + '…' if len(f) > 25 else f for f in top_formats.index], fontsize=10)
            ax3.set_xlabel('Count', fontweight='bold')
            ax3.set_title('Top Media Types', fontweight='bold', fontsize=14, pad=20, y=0.95)
            
            for i, v in enumerate(top_formats.values):
                ax3.text(v + max(top_formats.values) * 0.02, i, f'{v:,}', 
                        va='center', ha='left', fontsize=10, fontweight='bold')
            
            ax3.grid(axis='x', alpha=0.3, linestyle='--')
            ax3.set_axisbelow(True)
        else:
            ax3.text(0.5, 0.5, 'No Format Data', ha='center', va='center', fontsize=12)
            ax3.set_title('Top Media Types', fontweight='bold', fontsize=14, pad=20, y=0.95)
        
        ax4.axis('off')
        if not df_main.empty and 'Migration Status' in df_main.columns:
            status_counts = df_main['Migration Status'].fillna('Unknown').value_counts()
            
            table_data = []
            total = status_counts.sum()
            for status, count in status_counts.items():
                percentage = (count / total) * 100
                status_display = status[:18] + '…' if len(status) > 18 else status
                table_data.append([status_display, f'{count:,}', f'{percentage:.1f}%'])
            
            table = ax4.table(
                cellText=table_data,
                colLabels=['Migration Status', 'Count', '%'],
                cellLoc='left',
                loc='center',
                bbox=[0.05, 0.15, 0.9, 0.7]
            )
            
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2.2)
            
            header_color = COLORS['primary']
            alt_color1 = '#f8f9fa'
            alt_color2 = '#ffffff'
            
            for i in range(len(table_data) + 1):
                for j in range(3):
                    cell = table[(i, j)]
                    if i == 0:
                        cell.set_facecolor(header_color)
                        cell.set_text_props(weight='bold', color='white', size=11)
                        cell.set_height(0.08)
                    else:
                        cell.set_facecolor(alt_color1 if i % 2 == 0 else alt_color2)
                        cell.set_text_props(size=10)
                        if j == 1 or j == 2:
                            cell.set_text_props(weight='bold')
            
            ax4.set_title('Migration Status Summary', fontweight='bold', fontsize=14, pad=20, y=0.95)
        else:
            ax4.text(0.5, 0.5, 'No Migration Status Data', ha='center', va='center', fontsize=12)
            ax4.set_title('Migration Status Summary', fontweight='bold', fontsize=14, pad=20, y=0.95)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.90, hspace=0.4, wspace=0.35)
        pdf.savefig(fig, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close(fig)

    def _create_migration_status_chart(self, df: pd.DataFrame, pdf: PdfPages) -> None:
        if df.empty or 'Migration Status' not in df.columns:
            return

        fig, ax = plt.subplots(figsize=(11, 8.5))
        fig.suptitle('Migration Status Analysis', fontsize=22, fontweight='bold', y=0.95, x=0.6)
        
        status_counts = df['Migration Status'].fillna('Unknown').value_counts()
        
        status_colors = {
            'Migrated': '#2E7D32', 'Unmigrated': '#D32F2F', 'In Progress': '#F57F17',
            'Queued': '#1976D2', 'On Hold': '#7B1FA2', 'Unknown': '#616161',
            'Reviewed': '#00796B', 'Ready': '#388E3C', 'Will not migrate': '#FF5722'
        }
        
        colors = []
        fallback_colors = ['#424242', '#795548', '#607D8B', '#455A64', '#37474F']
        for i, status in enumerate(status_counts.index):
            if status in status_colors:
                colors.append(status_colors[status])
            else:
                colors.append(fallback_colors[i % len(fallback_colors)])
        
        bars = ax.barh(range(len(status_counts)), status_counts.values, 
                    color=colors, edgecolor='white', linewidth=1.5, alpha=0.9)
        
        ax.set_yticks(range(len(status_counts)))
        ax.set_yticklabels(status_counts.index, fontsize=13, fontweight='500')
        ax.set_xlabel('Number of Items', fontsize=15, fontweight='bold', labelpad=15)
        ax.set_title('Items by Migration Status', fontsize=18, fontweight='bold', pad=30)
        
        max_value = max(status_counts.values)
        for i, (bar, count) in enumerate(zip(bars, status_counts.values)):
            width = bar.get_width()
            percentage = (count / status_counts.sum()) * 100
            
            label_x = width + max_value * 0.015
            if width < max_value * 0.1:
                label_x = width + max_value * 0.02
                
            ax.text(label_x, bar.get_y() + bar.get_height()/2,
                    f'{count:,} ({percentage:.1f}%)', 
                    ha='left', va='center', fontweight='bold', fontsize=12)
        
        ax.grid(axis='x', alpha=0.4, linestyle='--', linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)
        
        total_text = f'Total Items: {status_counts.sum():,}'
        ax.text(0.98, 0.02, total_text, transform=ax.transAxes, 
                fontsize=14, fontweight='bold', ha='right',
                bbox=dict(boxstyle="round,pad=0.4", facecolor=COLORS['accent'], 
                        edgecolor='none', alpha=0.9))
        
        plt.subplots_adjust(left=0.28, right=0.96, top=0.85, bottom=0.12)
        pdf.savefig(fig, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close(fig)

    def _create_format_analysis_streamlined(self, df: pd.DataFrame, pdf: PdfPages) -> None:
        if df.empty:
            return

        fig = plt.figure(figsize=(11, 10))
        gs = GridSpec(2, 2, figure=fig, height_ratios=[1.4, 2.6], 
                    width_ratios=[1.0, 1.4], wspace=0.5, hspace=0.5)

        ax1 = fig.add_subplot(gs[0, 0])
        fmt1 = df['Format 1'].value_counts().head(8)
        
        colors1 = plt.cm.Blues(np.linspace(0.4, 0.9, len(fmt1)))
        
        bars1 = ax1.bar(range(len(fmt1)), fmt1.values, 
                        color=colors1, edgecolor='white', linewidth=1.2, alpha=0.9)
        
        ax1.set_xticks(range(len(fmt1)))
        ax1.set_xticklabels([f[:12] + '…' if len(f) > 12 else f for f in fmt1.index],
                            rotation=45, ha='right', fontsize=9)
        ax1.set_ylabel('Count', fontweight='bold', fontsize=11)
        ax1.set_title('Primary Format Types', fontweight='bold', fontsize=13, pad=15)
        
        for bar in bars1:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2, h + max(fmt1.values) * 0.02,
                    f'{int(h):,}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.set_axisbelow(True)

        ax2 = fig.add_subplot(gs[0, 1])
        fmt3 = df['Format 3'].fillna('Unknown').value_counts().head(10)
        
        colors2 = plt.cm.Oranges(np.linspace(0.4, 0.9, len(fmt3)))
        
        bars2 = ax2.barh(range(len(fmt3)), fmt3.values, 
                        color=colors2, edgecolor='white', linewidth=1.2, alpha=0.9)
        
        ax2.set_yticks(range(len(fmt3)))
        ax2.set_yticklabels([f[:28] + '…' if len(f) > 28 else f for f in fmt3.index], fontsize=10)
        ax2.set_xlabel('Count', fontweight='bold', fontsize=11)
        ax2.set_title('Specific Format Types (Top 10)', fontweight='bold', fontsize=13, pad=15)
        
        max_val = max(fmt3.values)
        for i, v in enumerate(fmt3.values):
            label_x = v + max_val * 0.015
            ax2.text(label_x, i, f'{v:,}', va='center', ha='left', fontsize=9, fontweight='bold')
        
        ax2.grid(axis='x', alpha=0.3, linestyle='--')
        ax2.set_axisbelow(True)
        ax2.set_xlim(0, max_val * 1.15)

        ax3 = fig.add_subplot(gs[1, :])
        top_formats = df['Format 1'].value_counts().head(12)
        filtered = df[df['Format 1'].isin(top_formats.index)]
        status_format = pd.crosstab(filtered['Format 1'], filtered['Migration Status'].fillna('Unknown'))

        status_colors_list = ['#2E7D32', '#D32F2F', '#F57F17', '#1976D2', '#7B1FA2', '#616161', '#00796B', '#388E3C']
        
        status_format.plot(kind='bar', stacked=True, ax=ax3, 
                        color=status_colors_list[:len(status_format.columns)],
                        edgecolor='white', linewidth=0.8, alpha=0.9)
        
        ax3.set_title('Migration Status by Format Type', fontweight='bold', fontsize=16, pad=20)
        ax3.set_xlabel('Format Type', fontweight='bold', fontsize=12, labelpad=10)
        ax3.set_ylabel('Number of Items', fontweight='bold', fontsize=12, labelpad=10)
        
        ax3.legend(title='Migration Status', bbox_to_anchor=(1.01, 1), loc='upper left',
                title_fontsize=11, fontsize=10, frameon=True, fancybox=True, shadow=True)
        
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=10)
        
        for container in ax3.containers:
            labels = [f'{v.get_height():.0f}' if v.get_height() > 5 else '' for v in container]
            ax3.bar_label(container, labels=labels, label_type='center', fontsize=8, fontweight='bold', color='white')
        
        ax3.grid(axis='y', alpha=0.3, linestyle='--')
        ax3.set_axisbelow(True)

        fig.suptitle('Format Analysis', fontsize=20, fontweight='bold', y=0.95)
        plt.subplots_adjust(top=0.88, bottom=0.15, left=0.08, right=0.85)

        pdf.savefig(fig, bbox_inches='tight', facecolor='white', edgecolor='none')
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
  # Using environment variables
  %(prog)s -c COLL123

  # Manually specifying credentials
  %(prog)s -u myuser -p mypass -c COLL123
  
  # Checking AWS S3 for Migrated files
  %(prog)s -c COLL123 --check-aws
        """
    )
    
    parser.add_argument('-u', '--username', help='FileMaker database username')
    parser.add_argument('-p', '--password', help='FileMaker database password')
    parser.add_argument('-c', '--collection-id', required=True, help='Collection ID to query')
    parser.add_argument('-o', '--output', help='Excel output file path')
    parser.add_argument('--pdf', action='store_true', help='Generate PDF report alongside Excel file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--check-aws', action='store_true', help='Check S3 for migrated files (Requires AWS credentials)')
    parser.add_argument('--aws-profile', help='AWS CLI profile to use (if using --check-aws)')
    
    return parser.parse_args()

def validate_output_path(output_path: str) -> Path:
    """Validate and create output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.touch(exist_ok=True)
        path.unlink()
    except PermissionError:
        raise PermissionError(f"Cannot write to {path}")
    return path

def main() -> int:
    """Main application entry point with comprehensive error handling."""
    try:
        args = parse_arguments()
        setup_logging(args.verbose)

        username = args.username or os.getenv('FM_DATABASE_USERNAME')
        password = args.password or os.getenv('FM_DATABASE_PASSWORD')
        
        if not username or not password:
            logging.error("Missing credentials. Please set FM_DATABASE_USERNAME/PASSWORD environment variables or use -u/-p flags.")
            return 1
        
        logging.info("Starting AMI Collection Processor")
        logging.info(f"Collection ID: {args.collection_id}")

        try:
            config = Config()
            logging.info(f"Configuration: {config}")
        except ConfigurationError as e:
            logging.error(f"Configuration error: {e}")
            return 1

        # Initialize AWS Checker Early (Fail fast if requested but unauthenticated)
        aws_checker = None
        if args.check_aws:
            aws_checker = AWSChecker(profile_name=args.aws_profile)
            try:
                aws_checker.connect()
                # Fetch the inventory NOW so it's ready when the dataframes are built
                aws_checker.build_inventory()
            except Exception as e:
                logging.error(f"Halting execution due to AWS error: {e}")
                return 1

        desktop_dir = Path.home() / "Desktop"

        if args.output:
            excel_file = Path(args.output)
        else:
            excel_file = desktop_dir / f"{args.collection_id}_Migration_Status.xlsx"
        excel_path = validate_output_path(str(excel_file))

        pdf_path = None
        if args.pdf:
            pdf_file = desktop_dir / f"{args.collection_id}_Migration_Status.pdf"
            pdf_path = validate_output_path(str(pdf_file))

        fm_client = FileMakerClient(config)

        try:
            fm_client.connect(username, password)
            processor = CollectionProcessor(fm_client)
            df = processor.fetch_items(args.collection_id)

            if df.empty:
                logging.warning("No data found for the specified collection ID")
                return 0

            df_active, df_inactive = processor.apply_filters(df)
            df_main, df_digital = processor.separate_digital_carriers(df_active)

            df_main = processor.sort_by_ami_id(df_main)
            df_digital = processor.sort_by_ami_id(df_digital)
            df_inactive = processor.sort_by_ami_id(df_inactive)

            # Apply AWS Validations to the DataFrames
            if aws_checker:
                logging.info("Applying S3 validations to DataFrames...")
                df_main = aws_checker.apply_to_dataframe(df_main)
                df_digital = aws_checker.apply_to_dataframe(df_digital)

            report_generator = ReportGenerator(args.collection_id)
            report_generator.generate_excel(df_main, df_digital, df_inactive, str(excel_path))
            logging.info(f"Excel report completed: {excel_path}")

            if args.pdf and pdf_path:
                report_generator.generate_pdf_report(df_main, df_digital, str(pdf_path))
                logging.info(f"PDF report completed: {pdf_path}")

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
    sys.exit(main())