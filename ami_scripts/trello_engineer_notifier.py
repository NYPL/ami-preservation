#!/usr/bin/env python3

import os
import argparse
import requests

# Set up the argument parser
parser = argparse.ArgumentParser(description="Move a Trello card to an engineer's specific list and notify them")
parser.add_argument('-c', '--card', required=True, help='Card ID to be moved')
parser.add_argument('-e', '--engineer', required=True, help='Engineer name to determine the list the card will be moved to')
args = parser.parse_args()


def get_trello_username(engineer_name):
    """Return the Trello username based on the engineer's name from environment variables."""
    env_var_name = f'TRELLO_{engineer_name.upper()}_USERNAME'
    member_username = os.getenv(env_var_name)
    if not member_username:
        print(f"No Trello username found for {engineer_name}")
    return member_username


def get_list_id(engineer_name):
    """Fetch the list ID from environment variables based on the engineer's name."""
    env_var_name = f'TRELLO_{engineer_name.upper()}_LIST_ID'
    list_id = os.getenv(env_var_name)
    if not list_id:
        print(f"No list ID found for engineer: {engineer_name}")
    return list_id

def get_card_id_by_name(board_id, card_name):
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    url = f"https://api.trello.com/1/boards/{board_id}/cards?key={api_key}&token={token}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch cards, status code: {response.status_code}")
        print("Response text:", response.text)
        return None

    cards = response.json()
    for card in cards:
        if card['name'].strip().lower() == card_name.strip().lower():
            print(f"Found card: {card['name']} with ID: {card['id']}")
            return card['id']
    
    print(f"No card found with the name: {card_name}")
    return None

def move_card(card_id, list_id, position='bottom'):
    """Move the specified card to the given list ID and set its position."""
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {
        'key': api_key,
        'token': token,
        'idList': list_id,
        'pos': position  # Adding the position parameter to control card placement
    }
    response = requests.put(url, params=params)

    try:
        response.raise_for_status()  # This will raise an exception for HTTP error codes
        return response.json()  # Attempt to return JSON if possible
    except requests.exceptions.HTTPError as e:
        # Print out more information on HTTP errors
        print(f"HTTP Error: {e}")
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
    except ValueError as e:
        # Handle cases where JSON decoding fails
        print(f"JSON Decode Error: {e}")
        print(f"Response Text: {response.text}")
        return None  # Return None if JSON decoding fails

    return None  # General fallback in case of other unexpected issues


def assign_member(card_id, engineer_name):
    """Add a comment to the card to notify the engineer by Trello username."""
    member_username = get_trello_username(engineer_name)
    if not member_username:
        print(f"No Trello username found for {engineer_name}")
        return None

    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    url = f"https://api.trello.com/1/cards/{card_id}/actions/comments"
    comment_text = f"@{member_username} you have been assigned to this card."
    query = {
        'key': api_key,
        'token': token,
        'text': comment_text
    }
    response = requests.post(url, params=query)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
    except ValueError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Response Text: {response.text}")
        return None
    return None



def main():
    card_name = args.card  # Assumes the argument is the card name, not the ID.
    board_id = os.getenv('TRELLO_BOARD_ID')
    if not board_id:
        print("Board ID is not set in the environment variables.")
        return

    card_id = get_card_id_by_name(board_id, card_name)
    if not card_id:
        print(f"Unable to find card '{card_name}' on board '{board_id}'. Exiting.")
        return

    list_id = get_list_id(args.engineer)
    if list_id and card_id:
        result = move_card(card_id, list_id, 'bottom')  # Move the card and position it at the bottom
        if result and 'id' in result:
            print(f"Card successfully moved to {args.engineer}'s list.")
            # Notify the engineer by adding a comment to the card
            notification_result = assign_member(card_id, args.engineer)
            if 'id' in notification_result:
                print("Engineer notified successfully.")
            else:
                print("Failed to notify the engineer.")
        else:
            print("Failed to move the card: ", result)
    else:
        print("Operation aborted due to missing list ID or card ID.")


if __name__ == "__main__":
    main()