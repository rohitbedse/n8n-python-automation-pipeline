import json
from collections import Counter

with open(r'C:\n8n-project\scraper\output\swayam_courses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total courses: {len(data)}')
nc_counts = Counter(c.get('national_coordinator', '') for c in data)
print('National Coordinators:')
for k, v in sorted(nc_counts.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
prov_counts = Counter(c.get('provider', '') for c in data)
print()
print('Top Providers:')
for k, v in sorted(prov_counts.items(), key=lambda x: -x[1])[:20]:
    print(f'  {k}: {v}')
nptel = [c for c in data if c.get('national_coordinator') == 'NPTEL']
print()
print(f'NPTEL courses: {len(nptel)}')
if nptel:
    c = nptel[0]
    print(f'Sample NPTEL: {c.get("course_name")}, institute={c.get("institute")}, provider={c.get("provider")}')