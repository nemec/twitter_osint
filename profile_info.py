from datetime import datetime
import pathlib
import time
import sys
import csv
import re

import requests


from config import (
    cookie_header, auth_header,
    sleep_after_rate_limit_seconds,
    delay_between_requests_seconds,
    username_file)


URL_FMT = 'https://api.twitter.com/graphql/4S2ihIKfF3xhp-ENxvUAfQ/UserByScreenName?variables={{"screen_name":"{username}","withHighlightedLabel":true}}'

RATE_LIMIT_SENTINEL = object()

def parse_cookies(cookie_header: str):
    for item in re.split(';\s?', cookie_header):
        if not item:
            continue

        key, sep, val = item.partition('=')
        if not val:
            print(f'Error parsing cookie "{item}"')
            continue
        yield (key, val)


def request_username_data(s, csrf, username):
    resp = s.get(URL_FMT.format(username=username), headers={
            'Authorization': auth_header.strip(),
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0',
            'x-csrf-token': csrf
        })
        
    if resp.status_code == 200:
        j = resp.json()
        created_at = j['data']['user']['legacy']['created_at']
        created_at_iso = None
        try:
            created_at_iso = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
        except ValueError:
            pass
        return {
            'username': username,
            'userid': j['data']['user']['rest_id'],
            'created_at': created_at,
            'created_at_iso': created_at_iso.strftime('%Y-%m-%dT%H:%M:%S+00:00Z'),
            'desc': 'Success'
        }
    elif resp.status_code == 429:
        return RATE_LIMIT_SENTINEL
    else:
        return {
            'username': username,
            'userid': None,
            'created_at': None,
            'created_at_iso': None,
            'desc': f'Error requesting API data. Status code {resp.status_code}'
        }


def main(username_f: pathlib.Path, delay_between_requests_seconds: float, sleep_after_rate_limit_seconds: float):
    with open(username_f, 'r') as f:
        usernames = (u.strip() for u in f.readlines())

    s = requests.Session()
    for key, val in parse_cookies(cookie_header.strip()):
        s.cookies.set(key, val, domain='api.twitter.com')

    csrf = s.cookies.get('ct0')

    writer = csv.DictWriter(sys.stdout,
        fieldnames=['username', 'userid', 'created_at', 'created_at_iso', 'desc'])
    writer.writeheader()

    for username in usernames:
        retries = 3
        while retries > 0:

            try:
                username_data = request_username_data(s, csrf, username)
                if username_data is RATE_LIMIT_SENTINEL:
                    time.sleep(sleep_after_rate_limit_seconds)
                    retries -= 1
                    continue
            except Exception as e:
                username_data = {
                    'username': username,
                    'userid': None,
                    'created_at': None,
                    'created_at_iso': None,
                    'desc': str(e)
                }

            writer.writerow(username_data)

            if usernames:
                time.sleep(delay_between_requests_seconds)
            break
            

if __name__ == '__main__':
    username_f = pathlib.Path(username_file)
    if not username_f.is_file():
        print(f'Username file input {username_f} does not exist')
    main(
        username_f,
        delay_between_requests_seconds,
        sleep_after_rate_limit_seconds)