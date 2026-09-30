import json

# Check mindler
with open(r'C:\n8n-project\scraper\output\mindler_career_library.json', 'r', encoding='utf-8') as f:
    m = json.load(f)
print(f'Mindler: {len(m)} records')
print(f'  Sample keys: {list(m[0].keys())}')

# Check swayam
with open(r'C:\n8n-project\scraper\output\swayam_courses.json', 'r', encoding='utf-8') as f:
    s = json.load(f)
print(f'SWAYAM: {len(s)} records')
print(f'  Sample keys: {list(s[0].keys())}')
print(f'  Has provider: {"provider" in s[0]}')
print(f'  Sample provider: {s[0].get("provider")}')
print(f'  Sample national_coordinator: {s[0].get("national_coordinator")}')
print(f'  Sample institute: {s[0].get("institute")}')
print(f'  Sample source: {s[0].get("source")}')