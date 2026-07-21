"""Report what was found in UTOC parsing."""
import json

with open(r'C:\Users\jonis\Desktop\AI Reverse Engineer\projects\GrayZoneWarfare\pak_data\exports\GZW-WindowsClient_utoc_parsed.json') as f:
    data = json.load(f)

all_strings = data.get('all_strings', [])
print(f'Total strings found: {len(all_strings)}')

# Categorize
categories = {
    'DataTables': [],
    'Items': [],
    'Weapons/Attachments': [],
    'Armor/Vests/Helmets': [],
    'Ammo': [],
    'Medical': [],
    'Keys/Keycards': [],
    'Quests/Tasks': [],
    'Loot': [],
    'NPC/AI': [],
    'Factions': [],
    'Skills/Progression': [],
    'Shops/Trading': [],
    'Storage/Inventory': [],
    'Maps/Locations': [],
    'UI/Screens': [],
    'Audio': [],
    'Animations': [],
    'Blueprints': [],
    'Materials/Textures': [],
    'Config/Data': [],
}

for s in all_strings:
    sl = s.lower()
    if 'datatable' in sl or 'dt_' in sl:
        categories['DataTables'].append(s)
    if 'item' in sl:
        categories['Items'].append(s)
    if 'weapon' in sl or 'attachment' in sl or 'mod' in sl or 'barrel' in sl or 'stock' in sl or 'magazine' in sl or 'scope' in sl:
        categories['Weapons/Attachments'].append(s)
    if 'armor' in sl or 'vest' in sl or 'helmet' in sl or 'glasses' in sl:
        categories['Armor/Vests/Helmets'].append(s)
    if 'ammo' in sl:
        categories['Ammo'].append(s)
    if 'medical' in sl or 'medkit' in sl or 'bandage' in sl or 'splint' in sl:
        categories['Medical'].append(s)
    if 'key' in sl or 'keycard' in sl:
        categories['Keys/Keycards'].append(s)
    if 'quest' in sl or 'task' in sl or 'mission' in sl:
        categories['Quests/Tasks'].append(s)
    if 'loot' in sl or 'pickup' in sl:
        categories['Loot'].append(s)
    if 'npc' in sl or 'ai_' in sl or 'enemy' in sl or 'bot' in sl:
        categories['NPC/AI'].append(s)
    if 'faction' in sl or 'rep_' in sl:
        categories['Factions'].append(s)
    if 'skill' in sl or 'progression' in sl or 'level' in sl or 'exp' in sl:
        categories['Skills/Progression'].append(s)
    if 'shop' in sl or 'trading' in sl or 'trader' in sl or 'vendor' in sl:
        categories['Shops/Trading'].append(s)
    if 'storage' in sl or 'inventory' in sl or 'stash' in sl:
        categories['Storage/Inventory'].append(s)
    if 'map' in sl or 'location' in sl or 'zone' in sl or 'level' in sl:
        categories['Maps/Locations'].append(s)
    if 'ui/' in sl or 'screen' in sl or 'widget' in sl or 'hud' in sl:
        categories['UI/Screens'].append(s)
    if '.wav' in sl or '.ogg' in sl or 'audio' in sl or 'sound' in sl:
        categories['Audio'].append(s)
    if '.json' in sl or '.csv' in sl or '.xml' in sl:
        categories['Config/Data'].append(s)

# Print report
for cat, items in categories.items():
    if items:
        items = sorted(set(items))
        print(f'\n{cat}: {len(items)}')
        for item in items[:10]:
            print(f'  {item}')
        if len(items) > 10:
            print(f'  ... and {len(items)-10} more')

# Total unique interesting items
all_interesting = set()
for items in categories.values():
    all_interesting.update(items)
print(f'\n\nTotal unique interesting paths: {len(all_interesting)}')
print(f'Total all strings: {len(all_strings)}')
