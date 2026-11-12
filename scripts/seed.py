import json
import sys
from pathlib import Path
import httpx

root = Path(__file__).resolve().parent.parent
url = sys.argv[1].rstrip('/') if len(sys.argv)>1 else 'http://127.0.0.1:8000'
for item in json.loads((root/'sample_docs/manifest.json').read_text()):
    path=root/'sample_docs'/item['file']
    with path.open('rb') as f:
        response=httpx.post(url+'/api/documents',headers={'X-Tenant-Id':item['tenant']},files={'file':(path.name,f)},data={k:item[k] for k in ('title','version','valid_from','valid_to')},timeout=300)
    print(item['tenant'],path.name,response.status_code,response.text)
    response.raise_for_status()
