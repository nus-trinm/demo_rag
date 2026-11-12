import io
import math

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path/'test.db'))
    monkeypatch.setattr(main, 'RETRIEVAL_MIN_SCORE', 0.5)
    def fake_embed(texts):
        vectors=[]
        for text in texts:
            t=text.lower(); v=[0.0,0.0,0.0,0.0]
            if any(x in t for x in ('remote','home')): v[0]=1
            if any(x in t for x in ('leave','vacation')): v[1]=1
            if any(x in t for x in ('travel','receipt')): v[2]=1
            if not any(v): v[3]=1
            vectors.append(v)
        return vectors
    monkeypatch.setattr(main,'embed',fake_embed)
    def fake_chat(prompt):
        import re, json
        chunk_id=int(re.search(r'\[chunk:(\d+)\]',prompt.split('Excerpts:\n', 1)[1]).group(1))
        return json.dumps({'answer':'Up to three days per week.','citation_ids':[chunk_id]})
    monkeypatch.setattr(main,'llm_chat',fake_chat)
    with TestClient(main.app) as c: yield c


def docx_bytes(*paragraphs):
    d=Document()
    for p in paragraphs: d.add_paragraph(p)
    b=io.BytesIO(); d.save(b); return b.getvalue()


def upload(client, tenant='acme', title='Remote', version='1', start='2025-01-01', end='2099-12-31', content='Remote work is allowed three days weekly.', filename='policy.docx', raw=None):
    return client.post('/api/documents',headers={'X-Tenant-Id':tenant},data={'title':title,'version':version,'valid_from':start,'valid_to':end},files={'file':(filename,raw if raw is not None else docx_bytes(content))})


def test_retrieval_scope_version_and_citations(client):
    old=upload(client,version='old',start='2020-01-01',end='2099-12-31',content='Remote work one day weekly.').json()['id']
    current=upload(client,version='new',start='2025-01-01',content='Remote work three days weekly.').json()['id']
    other=upload(client,tenant='northstar',content='Remote work five days weekly.').json()['id']
    leave=upload(client,title='Leave',content='Annual leave is 18 days.').json()['id']
    h={'X-Tenant-Id':'acme'}
    payload={'question':'How many days can I work from home?', 'document_ids':[old,current,other,leave]}
    result=client.post('/api/search',headers=h,json=payload).json()['chunks']
    assert result[0]['document_id']==current
    assert all(c['document_id'] not in (old,other) for c in result)
    answer=client.post('/api/ask',headers=h,json=payload).json()
    assert answer['status']=='answered' and answer['citations'][0]['id'] in {c['id'] for c in answer['chunks']}
    only_leave=client.post('/api/ask',headers=h,json={**payload,'document_ids':[leave]}).json()
    assert only_leave['status']=='not_enough_information' and all(c['document_id']==leave for c in only_leave['chunks'])
    missing=client.post('/api/ask',headers=h,json={'question':'What is the cafeteria menu?', 'document_ids':[current]}).json()
    assert missing['status']=='not_enough_information' and not missing['citations']
    assert client.get(f'/api/documents/{other}/chunks',headers=h).status_code==404
    assert client.delete(f'/api/documents/{other}',headers=h).status_code==404
    assert client.get('/api/documents',headers={'X-Tenant-Id':'northstar'}).json()[0]['id']==other
    with main.connect() as db:
        assert db.execute('select valid_to from documents where id=?',(old,)).fetchone()[0]=='2024-12-31'
        assert db.execute('select count(*) from query_logs').fetchone()[0]==3


def test_upload_validation_pdf_and_cascade(client):
    assert upload(client,filename='no.txt',raw=b'text').status_code==400
    assert client.post('/api/documents',headers={'X-Tenant-Id':'a'},files={'file':('x.docx',docx_bytes('x'))},data={'title':'T','version':'1'}).status_code==422
    stream=io.BytesIO(); pdf=canvas.Canvas(stream); pdf.drawString(40,800,'Business travel receipts within 30 days.'); pdf.save()
    response=upload(client,title='Travel',filename='policy.pdf',raw=stream.getvalue())
    assert response.status_code==201
    doc_id=response.json()['id']; h={'X-Tenant-Id':'acme'}
    chunks=client.get(f'/api/documents/{doc_id}/chunks',headers=h).json()
    assert {x['strategy'] for x in chunks}=={'semantic','structure'}
    assert client.delete(f'/api/documents/{doc_id}',headers=h).status_code==204
    with main.connect() as db: assert db.execute('select count(*) from chunks').fetchone()[0]==0


def test_invalid_model_citation_fails_closed(client, monkeypatch):
    doc=upload(client).json()['id']
    monkeypatch.setattr(main,'llm_chat',lambda *args: '{"answer":"Made up", "citation_ids":[99999]}')
    result=client.post('/api/ask',headers={'X-Tenant-Id':'acme'},json={'question':'work from home','document_ids':[doc]})
    assert result.status_code==502 and 'citation' in result.json()['detail']


def test_model_citation_with_chunk_prefix(client, monkeypatch):
    import json
    doc=upload(client).json()['id']
    chunks=client.get(f'/api/documents/{doc}/chunks',headers={'X-Tenant-Id':'acme'}).json()
    chunk_id=next(c['id'] for c in chunks if c['strategy']=='semantic')
    monkeypatch.setattr(main,'llm_chat',lambda prompt: json.dumps({'answer':'Three days.', 'citation_ids':[f'chunk:{chunk_id}']}))
    result=client.post('/api/ask',headers={'X-Tenant-Id':'acme'},json={'question':'work from home','document_ids':[doc]})
    assert result.status_code==200
    assert result.json()['status']=='answered' and result.json()['citations'][0]['id']==chunk_id


def test_lower_scoring_supporting_chunk_is_available_to_llm(client, monkeypatch):
    import json
    chunks = [
        {'id': 1, 'score': 0.6, 'content': 'Protect confidential information.'},
        {'id': 2, 'score': 0.22, 'content': 'Remote work requires manager approval.'},
    ]
    monkeypatch.setattr(main, 'retrieve', lambda *args: chunks)
    def chat(prompt):
        assert '[chunk:2] Remote work requires manager approval.' in prompt
        return json.dumps({'answer':'Manager approval is required.', 'citation_ids':[2]})
    monkeypatch.setattr(main, 'llm_chat', chat)
    response=client.post('/api/ask',headers={'X-Tenant-Id':'acme'},json={'question':'Who approves remote work?', 'document_ids':[1]})
    assert response.status_code == 200
    assert response.json()['citations'][0]['id'] == 2


def test_semantic_chunking_and_scope_before_topk(client):
    a=upload(client,content='Remote work three days. Annual leave eighteen days.').json()['id']
    b=upload(client,tenant='northstar',content='Remote work five days.').json()['id']
    h={'X-Tenant-Id':'acme'}
    chunks=client.get(f'/api/documents/{a}/chunks',headers=h).json()
    assert len([c for c in chunks if c['strategy']=='semantic'])==2
    assert len([c for c in chunks if c['strategy']=='structure'])==1
    result=client.post('/api/search',headers=h,json={'question':'remote work','document_ids':[a,b],'top_k':1}).json()['chunks']
    assert len(result)==1 and result[0]['document_id']==a


def test_llm_api_request_and_errors(monkeypatch):
    import httpx
    monkeypatch.setenv('LLM_API_KEY', 'test-key')
    monkeypatch.setattr(main, 'LLM_BASE_URL', 'https://example.test/v1')
    seen = {}
    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        request = httpx.Request('POST', url)
        return httpx.Response(200, request=request, json={'choices':[{'message':{'content':'{"answer":"ok","citation_ids":[1]}'}}]})
    monkeypatch.setattr(main.httpx, 'post', post)
    assert '"answer":"ok"' in main.llm_chat('Return JSON')
    assert seen['url'] == 'https://example.test/v1/chat/completions'
    assert seen['json']['model'] == 'qwen-3.7-flash'
    assert seen['headers']['Authorization'] == 'Bearer test-key'
    assert seen['json']['response_format'] == {'type':'json_object'}
    monkeypatch.delenv('LLM_API_KEY')
    with pytest.raises(main.HTTPException) as error:
        main.llm_chat('Return JSON')
    assert error.value.status_code == 503
