import argparse
import configparser
import re
import json

import lxml
import lxml.etree
import requests
from urllib.parse import unquote


def create_token() -> str:
    """
    request token string based on credentials
    write time and token to a file and return token
    """
    config = configparser.ConfigParser()
    config.read('credentials.ini')

    user = config.get('default', 'username')
    pw = config.get('default', 'password')
    tenant = config.get('default', 'tenant')

    # build the query string and get a new token
    TOKEN_BASE_URL = "https://nypl.preservica.com/api/accesstoken/login"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = f"username={user}&password={pw}&tenant={tenant}"
    response = requests.post(TOKEN_BASE_URL, headers=headers, data=payload)
    data = response.json()
    
    if not data["success"]:
        print(f"Invalid credentials. Please check your credentials.")

    return data["token"]

TOKEN = create_token()

SESSION = requests.Session()
SESSION.headers = {
    "Preservica-Access-Token": TOKEN,
    "Content-Type": "application/x-www-form-urlencoded",
    "charset": "UTF-8"
}

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch titles and ids for given AMI IDs.")

    def ami_id(value):
        """
        Custom type for AMI IDs, which must be six digits.
        """
        if not re.fullmatch(r"\d{6}", value):
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid six-digit AMI ID.")
        return value

    parser.add_argument(
        "--ids",
        type=ami_id,
        nargs="+",
        help="One or more six-digit AMI IDs",
        required=True
    )
    parser.add_argument(
        "-r",
        "--representation",
        type=str,
        choices=["access", "production", "preservation"],
        default="production",
        help="Representation specifier: access, production, or preservation"
    )

    return parser.parse_args()


def fetch_titles_and_ids(ami_ids):
    """
    Given a list of integers (ami_ids), query the API and return a list of (xip.title, id) tuples.
    """

    SEARCHURL = "https://nypl.preservica.com/api/content/search?"

    results = []
    for ami_id in ami_ids:
        data = {
            'q': json.dumps({'fields': [{'name': 'specObject.amiId', 'values': [str(ami_id)]},
                                        {'name': 'xip.identifier', 'values': ['ioCategory AMIMedia']}
                                        ]}),
            'start': 0,
            'max': '1',
            'metadata': ['xip.title', 'id', 'xip.identifier']
        }
        api_call = SESSION.post(SEARCHURL, data=data)

        try:
            metadata = api_call.json()['value']['metadata'][0]
            # metadata is a list of dicts, find xip.title and id
            title = next((item['value'] for item in metadata if item['name'] == 'xip.title'), None)
            obj_id = next((item['value'] for item in metadata if item['name'] == 'id'), None)
            results.append((title, obj_id))
        except (KeyError, IndexError, StopIteration):
            results.append((None, None))
    return results


def get_content_object_uuids(io_uuid, specifier="preservation_2"):
    """
    Given an information object UUID, fetch the representation and return a list of ContentObject UUIDs.
    """
    SESSION.headers.update({"Content-Type": "application/xml"})

    query = f"https://nypl.preservica.com/api/entity/information-objects/{io_uuid}/representations/{specifier}"
    io_call = SESSION.get(query)
    if io_call.status_code == 401:
        # Refresh token and retry once
        new_token = create_token()
        SESSION.headers["Preservica-Access-Token"] = new_token
        io_call = SESSION.get(query)
        if io_call.status_code == 401:
            raise Exception("Authentication failed after token refresh.")
    if io_call.status_code == 404 and specifier == "preservation_2":
        # If preservation_2 is not found, try preservation_1
        specifier = "preservation_1"
        query = f"https://nypl.preservica.com/api/entity/information-objects/{io_uuid}/representations/{specifier}"
        io_call = SESSION.get(query)
        if io_call.status_code == 404:
            raise Exception(f"No representation found for IO UUID {io_uuid} with specifier {specifier}.")

    io_tree = lxml.etree.fromstring(io_call.content)
    NSMAP = {'XIP': 'http://preservica.com/XIP/v8.0'}
    co_uuids = io_tree.xpath("//XIP:Representation/XIP:ContentObjects/XIP:ContentObject/text()", namespaces=NSMAP)
    return co_uuids


def download_bitstream(co_uuid):
    """
    Downloads the latest-active bitstream for the given ContentObject UUID.
    """
    co_query = f"https://nypl.preservica.com/api/entity/content-objects/{co_uuid}/generations/latest-active/bitstreams/1/content"
    co_call = SESSION.get(co_query, stream=True)
    if co_call.status_code == 401:
        # Refresh token and retry once
        new_token = create_token()
        SESSION.headers["Preservica-Access-Token"] = new_token
        co_call = SESSION.get(co_query, stream=True)
        if co_call.status_code == 401:
            raise Exception("Authentication failed after token refresh.")

    filesize = int(co_call.headers.get('Content-Length', None))
    if not filesize:
        filerange = co_call.headers.get('content-range', None)
        if not filerange:
            filesize = 1
        else:
            filesize = int(filerange.split('/')[-1])

    filename_parts = co_call.headers['Content-Disposition'].split('filename=')
    if len(filename_parts) > 1:
        filename = unquote(filename_parts[1].strip('"\''))

        total = 0
        with open(filename, 'wb') as f:
            for chunk in co_call.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)
                print(f"{100*total/filesize:.2f}% of {filesize} downloaded for {filename}", end='\r')



def main():
    args = parse_args()
    ami_ids = args.ids
    print(ami_ids)

    representations = {
        "access": "access_1",
        "production": "preservation_2",
        "preservation": "preservation_1"
    }

    # Fetch titles and IDs for the given AMI IDs
    results = fetch_titles_and_ids(ami_ids)

    # Print the results
    for title, obj_id in results:
        if title and obj_id:
            print(f"AMI: {title}, IO UUID: {obj_id}")
            # Get ContentObject UUIDs for the information object
            co_uuids = get_content_object_uuids(obj_id, specifier=representations[args.representation])
            for co_uuid in co_uuids:
                print(f"Downloading {args.representation} bitstream for ContentObject UUID: {co_uuid}")
                download_bitstream(co_uuid)
        else:
            print(f"No data found for AMI ID {title}")


if __name__ == "__main__":
    main()
