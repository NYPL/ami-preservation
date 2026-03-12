#!/usr/bin/env python3

import os
import re
import requests
import csv
from datetime import datetime

# --- CONFIGURATION ---
# Set this to False if you want to see projects that are 100% in QC
HIDE_COMPLETED = True 

# ANSI Color Codes for terminal formatting
class Color:
    BOLD = '\033[1m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    DIM = '\033[2m'
    END = '\033[0m'

def get_trello_data(url, api_key, token):
    """Helper function to cleanly fetch data from Trello."""
    params = {'key': api_key, 'token': token}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"{Color.RED}Error fetching data: {response.status_code} - {response.text}{Color.END}")
        return None
    return response.json()

def main():
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    prod_board_id = os.getenv('NYPL_MPL_BOARD_ID')
    qc_board_id = os.getenv('MPS_QUALITY_CONTROL_BOARD_ID')

    if not all([api_key, token, prod_board_id, qc_board_id]):
        print(f"{Color.RED}Missing environment variables. Please check your .zshrc.{Color.END}")
        return

    print("Fetching Board Data... this takes a few seconds.\n")

    # Fetch Lists mapping
    prod_lists_data = get_trello_data(f"https://api.trello.com/1/boards/{prod_board_id}/lists", api_key, token)
    qc_lists_data = get_trello_data(f"https://api.trello.com/1/boards/{qc_board_id}/lists", api_key, token)
    
    prod_lists = {lst['id']: lst['name'] for lst in prod_lists_data} if prod_lists_data else {}
    qc_lists = {lst['id']: lst['name'] for lst in qc_lists_data} if qc_lists_data else {}

    # Fetch all Cards
    prod_cards = get_trello_data(f"https://api.trello.com/1/boards/{prod_board_id}/cards", api_key, token)
    qc_cards = get_trello_data(f"https://api.trello.com/1/boards/{qc_board_id}/cards", api_key, token)

    report_data = {}
    total_projects = 0
    total_active_cards = 0

    # Phase 1: Probe Production Board
    for card in prod_cards:
        match = re.match(r"(MDR\d+)", card['name'])
        if match:
            mdr = match.group(1)
            if mdr not in report_data:
                report_data[mdr] = {'Total': 0, 'Prod': {}, 'QC': {}}
                total_projects += 1

            list_name = prod_lists.get(card['idList'], "Unknown List")
            if list_name not in report_data[mdr]['Prod']:
                report_data[mdr]['Prod'][list_name] = []
            report_data[mdr]['Prod'][list_name].append(card['name'])
            
            report_data[mdr]['Total'] += 1
            total_active_cards += 1

    # Phase 2: Probe QC Board
    for card in qc_cards:
        match = re.match(r"(MDR\d+)", card['name'])
        if match:
            mdr = match.group(1)
            if mdr in report_data:
                list_name = qc_lists.get(card['idList'], "Unknown List")
                if list_name not in report_data[mdr]['QC']:
                    report_data[mdr]['QC'][list_name] = []
                report_data[mdr]['QC'][list_name].append(card['name'])
                
                report_data[mdr]['Total'] += 1
                total_active_cards += 1

    # --- FILTERING & PARTITIONING LOGIC ---
    single_card_projects = []
    multi_card_projects = []
    hidden_count = 0

    for mdr, data in report_data.items():
        total_qc = sum(len(cards) for cards in data['QC'].values())
        
        if HIDE_COMPLETED and total_qc == data['Total']:
            hidden_count += 1
            continue
            
        if data['Total'] == 1:
            single_card_projects.append((mdr, data))
        else:
            multi_card_projects.append((mdr, data))

    # --- SORTING LOGIC ---
    # Sort Single Projects alphabetically by MDR
    sorted_single = sorted(single_card_projects, key=lambda x: x[0])

    # Sort Multi Projects by Completion Percentage (Descending), then Total Cards
    def sort_by_completion(item):
        mdr, data = item
        total_qc = sum(len(cards) for cards in data['QC'].values())
        completion_ratio = total_qc / data['Total'] if data['Total'] > 0 else 0
        return (-completion_ratio, -data['Total'], mdr)

    sorted_multi = sorted(multi_card_projects, key=sort_by_completion)

    # --- HELPER FUNCTION FOR TERMINAL PRINTING ---
    def print_project_block(project_list):
        for mdr, data in project_list:
            total_qc = sum(len(cards) for cards in data['QC'].values())
            pct = int((total_qc / data['Total']) * 100)
            
            if pct >= 80:
                pct_color = Color.GREEN
            elif pct >= 30:
                pct_color = Color.YELLOW
            else:
                pct_color = Color.RED

            print(f"{Color.BOLD}Project {mdr}:{Color.END} [{pct_color}{pct}% in QC{Color.END}] - {data['Total']} Total Cards")
            
            if data['Prod']:
                print(f"  {Color.BLUE}[Production Board]{Color.END}")
                for list_name, cards in data['Prod'].items():
                    count = len(cards)
                    cards_str = ", ".join(cards)
                    
                    if "ON HOLD" in list_name.upper():
                        print(f"    {Color.RED}- {count} cards in '{list_name}' [{cards_str}]{Color.END}")
                    else:
                        print(f"    - {count} cards in '{list_name}' [{Color.DIM}{cards_str}{Color.END}]")
                    
            if data['QC']:
                print(f"  {Color.GREEN}[QC Board]{Color.END}")
                for list_name, cards in data['QC'].items():
                    count = len(cards)
                    cards_str = ", ".join(cards)
                    print(f"    - {count} cards in '{list_name}' [{Color.DIM}{cards_str}{Color.END}]")
                    
            print("-" * 40)

    # --- TERMINAL REPORT GENERATION ---
    if sorted_single:
        print(f"{Color.BOLD}=== SINGLE-CARD PROJECTS (ONE-OFFS) ==={Color.END}\n")
        print_project_block(sorted_single)

    if sorted_multi:
        print(f"{Color.BOLD}=== MULTI-BOX PROJECTS (RANKED BY % IN QC) ==={Color.END}\n")
        print_project_block(sorted_multi)

    # Print Summary
    active_display_count = total_projects - hidden_count
    print(f"\n{Color.BOLD}SUMMARY: {active_display_count} Active Projects Displayed ({len(sorted_single)} Single / {len(sorted_multi)} Multi) | {hidden_count} Completed Hidden | {total_active_cards} Total Cards{Color.END}")

    # --- CSV EXPORT GENERATION ---
    desktop_path = os.path.expanduser("~/Desktop")
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_filename = os.path.join(desktop_path, f"MDR_Active_Report_{date_str}.csv")

    # Combine lists so they print in the exact same order in the CSV
    final_export_list = sorted_single + sorted_multi

    try:
        with open(csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Project Type", "MDR Project", "Completion %", "Total Cards in Project", "Board", "List", "Card Count", "Card Names"])
            
            for mdr, data in final_export_list:
                total_qc = sum(len(cards) for cards in data['QC'].values())
                pct = int((total_qc / data['Total']) * 100)
                pct_str = f"{pct}%"
                proj_type = "Single-Card" if data['Total'] == 1 else "Multi-Card"

                # Write Prod Data
                for list_name, cards in data['Prod'].items():
                    count = len(cards)
                    cards_str = ", ".join(cards)
                    writer.writerow([proj_type, mdr, pct_str, data['Total'], "Production", list_name, count, cards_str])
                
                # Write QC Data
                for list_name, cards in data['QC'].items():
                    count = len(cards)
                    cards_str = ", ".join(cards)
                    writer.writerow([proj_type, mdr, pct_str, data['Total'], "QC", list_name, count, cards_str])
                    
        print(f"\n{Color.GREEN}✓ CSV Successfully saved to: {csv_filename}{Color.END}\n")
    except Exception as e:
        print(f"\n{Color.RED}✗ Failed to save CSV: {e}{Color.END}\n")

if __name__ == "__main__":
    main()