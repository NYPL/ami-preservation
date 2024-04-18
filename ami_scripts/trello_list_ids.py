#!/usr/bin/env python3

import os
import requests

def fetch_trello_lists(board_id):
    # Fetch API key and token from environment variables
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')

    if not api_key or not token:
        print("API key or token is not set.")
        return

    # URL to fetch all lists on a board
    url = f"https://api.trello.com/1/boards/{board_id}/lists"

    # Parameters including the API key and token
    params = {
        'key': api_key,
        'token': token
    }

    # Make the HTTP request
    response = requests.get(url, params=params)
    if response.status_code == 200:
        lists = response.json()

        # Print each list ID and name
        for list in lists:
            print(f"List Name: {list['name']}, List ID: {list['id']}")
    else:
        print("Failed to fetch data:", response.status_code)

if __name__ == "__main__":
    board_id = input("Enter the Trello board ID: ")
    fetch_trello_lists(board_id)
