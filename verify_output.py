import json
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\n8n-project\scraper\output\swayam_courses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total courses: {len(data)}')
providers = set(c.get('provider', '') for c in data)
print(f'Unique providers: {len(providers)}')

for c in data[:5]:
    name = c["course_name"][:50].encode('ascii', 'replace').decode('ascii')
    nc = c.get("national_coordinator", "")
    inst = c.get("institute", "")
    prov = c.get("provider", "")
    print(f'  {name} | NC: {nc} | Inst: {inst} | Provider: {prov}')

with_provider = sum(1 for c in data if c.get('provider'))
print(f'Courses with provider: {with_provider}/{len(data)}')

nptel = [c for c in data if c.get('national_coordinator') == 'NPTEL']
print(f'NPTEL courses: {len(nptel)}')
if nptel:
    c = nptel[0]
    name = c.get("course_name", "").encode('ascii', 'replace').decode('ascii')
    print(f'Sample NPTEL: {name} | Provider: {c.get("provider")}')

# Also check IGNOU and AICTE
for target in ['IGNOU', 'AICTE']:
    samples = [c for c in data if c.get('national_coordinator') == target]
    if samples:
        c = samples[0]
        name = c.get("course_name", "").encode('ascii', 'replace').decode('ascii')
        print(f'Sample {target}: {name} | Inst: {c.get("institute")} | Provider: {c.get("provider")}')