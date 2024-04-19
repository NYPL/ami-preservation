#!/usr/bin/env python3

import os
import requests


def move_cards(source_list_id, target_list_id):
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    
    # Get the correct target board ID from the target list
    url_get_list = f"https://api.trello.com/1/lists/{target_list_id}?key={api_key}&token={token}"
    list_response = requests.get(url_get_list)
    if list_response.status_code == 200:
        list_details = list_response.json()
        target_board_id = list_details['idBoard']  # This ensures you are using the correct board ID
        print(f"Target list details: {list_details}")
    else:
        print(f"Failed to fetch target list details: {list_response.text}")
        return

    url_get_cards = f"https://api.trello.com/1/lists/{source_list_id}/cards?key={api_key}&token={token}"
    cards_response = requests.get(url_get_cards)
    if cards_response.status_code != 200:
        print("Failed to fetch cards:", cards_response.status_code, cards_response.text)
        return

    cards = cards_response.json()
    print(f"Moving {len(cards)} cards from the source list to the target list.")

    for card in cards:
        url_move_card = f"https://api.trello.com/1/cards/{card['id']}"
        params = {
            'key': api_key,
            'token': token,
            'idList': target_list_id,
            'idBoard': target_board_id  # Use the correct board ID obtained from the list details
        }
        move_response = requests.put(url_move_card, params=params)
        if move_response.status_code != 200:
            print(f"Failed to move card {card['id']} to list {target_list_id} on board {target_board_id}: {move_response.text}")
        else:
            print(f"Card {card['id']} moved successfully to list {target_list_id} on board {target_board_id}.")

def main():
    source_list_id = os.getenv('TRELLO_QCQUEUE_LIST_ID')
    target_list_id = os.getenv('IN_HOUSE_QC_INBOX_LIST_ID')

    if not source_list_id or not target_list_id:
        print("Source or target list ID not set. Check environment variables.")
        return

    move_cards(source_list_id, target_list_id)

if __name__ == "__main__":
    main()
