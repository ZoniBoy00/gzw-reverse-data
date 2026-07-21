"""
Search for available UE5 PAK extraction tools/libraries.
"""
import urllib.request
import json

queries = [
    ('ue5-pak', 'python'),
    ('ue5-io-store', 'python'),
    ('unreal-pak-parser', 'python'),
    ('ue4pak', 'python'),
    ('uecast', 'ue5'),
    ('io-store', 'unreal'),
]

for query, extra in queries:
    url = f'https://api.github.com/search/repositories?q={query}+{extra}&sort=stars'
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github.v3+json'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if data['items']:
            print(f'\n=== {query}+{extra} ===')
            for item in data['items'][:3]:
                print(f'  {item["full_name"]}: ⭐{item["stargazers_count"]}')
                print(f'  {item["html_url"]}')
                desc = (item["description"] or "")[:120]
                if desc:
                    print(f'  {desc}')
        else:
            print(f'\n=== {query}+{extra} === (no results)')
    except Exception as e:
        print(f'\n=== {query}+{extra} === Error: {e}')
