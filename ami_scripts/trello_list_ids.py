#!/usr/bin/env python3

import os
import requests

def fetch_trello_lists_and_members(board_id):
    # Fetch API key and token from environment variables
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')

    if not api_key or not token:
        print("API key or token is not set.")
        return

    # URL to fetch all lists on a board
    list_url = f"https://api.trello.com/1/boards/{board_id}/lists"
    member_url = f"https://api.trello.com/1/boards/{board_id}/members"

    # Parameters including the API key and token
    params = {
        'key': api_key,
        'token': token
    }

    # Make the HTTP request for lists
    list_response = requests.get(list_url, params=params)
    if list_response.status_code == 200:
        lists = list_response.json()
        # Print each list ID and name
        print("Lists on the Board:")
        for list in lists:
            print(f"List Name: {list['name']}, List ID: {list['id']}")
    else:
        print("Failed to fetch lists:", list_response.status_code)

    # Make the HTTP request for members
    member_response = requests.get(member_url, params=params)
    if member_response.status_code == 200:
        members = member_response.json()
        # Print each member ID and username
        print("\nMembers on the Board:")
        for member in members:
            print(f"Member Name: {member['fullName']}, Member Username: {member['username']}, Member ID: {member['id']}")
    else:
        print("Failed to fetch members:", member_response.status_code)

if __name__ == "__main__":
    board_id = input("Enter the Trello board ID: ")
    fetch_trello_lists_and_members(board_id)
