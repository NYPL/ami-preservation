#!/usr/bin/env python3

import os
import requests

def create_card(api_key, token, list_id, card_name, card_desc=""):
    """Create a card in a specified Trello list"""
    url = "https://api.trello.com/1/cards"
    query = {
        'key': api_key,
        'token': token,
        'idList': list_id,
        'name': card_name,
        'desc': card_desc
    }
    response = requests.post(url, params=query)
    if response.status_code == 200:
        print(f"Card '{card_name}' created successfully!")
    else:
        print(f"Failed to create card. Status code: {response.status_code}, Response: {response.text}")

def main():
    # Load API credentials and list ID from environment variables
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    list_id = os.getenv('TRELLO_BENJAMIN_LIST_ID')

    if not api_key or not token or not list_id:
        print("Error: Missing Trello API credentials or list ID in environment variables.")
        return

    # Prompt user for card details
    card_name = input("What would you like to name the card? ").strip()
    if not card_name:
        print("Error: Card name cannot be empty.")
        return
    
    card_desc = input("Any description for the card? (Press Enter to skip): ").strip()

    # Create a new Trello card in the specified list
    create_card(api_key, token, list_id, card_name, card_desc)

if __name__ == "__main__":
    main()
