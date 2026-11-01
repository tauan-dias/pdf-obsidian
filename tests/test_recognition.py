"""OCR contracts and fallbacks use synthetic documents and controllable children."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

import pymupdf
import pytest

from pdf_obsidian.converter import convert, ConversionCancelled
from pdf_obsidian.models import Block, Page, TextLine
from pdf_obsidian.recognition import ConversionOptions, RecognitionClient, resource_status, verify_resources, validate_response
from pdf_obsidian.recognition_merge import merge_recognition, table_markdown, formula_markdown


def test_table_uses_native_text_inside_cell_without_losing_punctuation():
    from pdf_obsidian.models import TextLine

    native = TextLine('Valor: 3.6', (10, 10, 90, 25), 11, 'Helvetica', 0, 22, 0)
    item = dict(rows=1, cols=2, cells=[
        dict(r0=0, r1=1, c0=0, c1=1, text='OCR incorreto', bbox=[0, 0, 100, 30]),
        dict(r0=0, r1=1, c0=1, c1=2, text='Outro valor', bbox=[100, 0, 200, 30])])
    assert '| Valor: 3.6 | Outro valor |' in table_markdown(item, [native])


@pytest.fixture
def resources(tmp_path, monkeypatch):
    root = tmp_path / 'ocr-resources'
    (root / 'environment/bin').mkdir(parents=True)
    (root / 'environment/bin/python').symlink_to(sys.executable)
    (root / 'model.bin').write_bytes(b'synthetic-model')
    manifest = dict(schema=1, versions={'synthetic': '1'}, files={'model.bin': sha256(b'synthetic-model').hexdigest()})
    monkeypatch.setattr('pdf_obsidian.recognition.trusted_model_hashes', lambda: dict(manifest['files']))
    (root / 'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setenv('PDF_OBSIDIAN_OCR_DIR', str(root))
    return root


def scanned_source(root, *, native=False, rotation=0, crop=False):
    root.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as raster:
        p = raster.new_page(width=300, height=400)
        p.insert_text((25, 80), 'Texto reconhecido', fontsize=18)
        image = p.get_pixmap(dpi=150, alpha=False).tobytes('png')
    source = root / 'scan.pdf'
    with pymupdf.open() as pdf:
        p = pdf.new_page(width=300, height=400)
        p.insert_image(p.rect, stream=image)
        if native:
            p.insert_text((25, 80), 'Texto nativo', fontsize=18)
        if crop:
            p.set_cropbox(pymupdf.Rect(10, 20, 290, 390))
        p.set_rotation(rotation)
        pdf.save(source)
    return source


def table(box=(0, 0, 100, 100)):
    return dict(kind='table', bbox=list(box), text='', rows=2, cols=2, cells=[
        dict(r0=r, r1=r+1, c0=c, c1=c+1, text=text)
        for r, c, text in ((0,0,'Item'),(0,1,'Valor'),(1,0,'Alfa'),(1,1,'10'))])


def test_resource_integrity_and_modes(resources):
    assert resource_status()[0]
    verify_resources(resources)
    (resources / 'model.bin').write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='corrompido'):
        verify_resources(resources)
    with pytest.raises(ValueError):
        ConversionOptions('force')


@pytest.mark.parametrize('manifest', [None, [], 'invalid', 42, {},
    {'schema': 1, 'files': {'model.bin': None}},
    {'schema': 1, 'files': {'model.bin': 'z' * 64}},
    {'schema': 1, 'files': {'../outside': '0' * 64}}])
def test_malformed_manifest_is_unavailable_without_crashing(resources, manifest):
    (resources / 'manifest.json').write_text(json.dumps(manifest))
    ready, message, data = resource_status(resources)
    assert not ready and not data
    assert 'preserva texto nativo e imagens' in message
    with pytest.raises(RuntimeError):
        verify_resources(resources)


def test_resource_status_rejects_external_model_link(resources, tmp_path):
    external = tmp_path / 'external-model'
    external.write_bytes((resources / 'model.bin').read_bytes())
    (resources / 'model.bin').unlink()
    (resources / 'model.bin').symlink_to(external)
    assert not resource_status(resources)[0]


def test_protocol_rejects_stale_and_out_of_page_output():
    data = dict(id='a', page=1, blocks=[dict(kind='text', bbox=[1, 1, 20, 20], text='ação')])
    assert validate_response(data, 'a', 1, 100, 100)
    with pytest.raises(ValueError, match='outra tarefa'):
        validate_response(data, 'b', 1, 100, 100)
    for box in ([1, 1, 1010, 20], [0, float('nan'), 20, 20], [20,20,1,1]):
        data['blocks'][0]['bbox'] = box
        with pytest.raises(ValueError):
            validate_response(data, 'a', 1, 100, 100)


def test_tables_formulas_and_safe_markup():
    assert '| Alfa | 10 |' in table_markdown(table())
    merged = dict(kind='table', bbox=[0,0,100,100], rows=2, cols=2, cells=[
        dict(r0=0,r1=1,c0=0,c1=2,text='<script>'), dict(r0=1,r1=2,c0=0,c1=1,text='A'),dict(r0=1,r1=2,c0=1,c1=2,text='B')])
    markup = table_markdown(merged)
    assert 'colspan="2"' in markup and '&lt;script&gt;' in markup
    merged['cells'].append(merged['cells'][0])
    assert table_markdown(merged) is None
    assert formula_markdown(r'\frac{x}{2}') == '$$\n\\frac{x}{2}\n$$'
    assert formula_markdown(r'\frac{x}{2') is None
    assert formula_markdown('<unk>') is None


def test_merge_preserves_native_and_only_adds_missing_regions():
    native_line = TextLine('Texto nativo', (0,0,100,15), 12,'Geist',0,12,0)
    original = Block('text','Texto nativo',1,native_line.bbox,12,lines=[native_line])
    page = Page(1,300,400,[original])
    decisions, warnings = [], []
    recognized = [dict(kind='text',bbox=[0,0,100,15],text='Texto nativo'),
                  dict(kind='text',bbox=[0,0,100,15],text='Texto errado'),
                  dict(kind='text',bbox=[0,50,150,65],text='Novo texto'),
                  dict(kind='text',bbox=[0,300,150,315],text='Fora da região')]
    assert merge_recognition(page, recognized, [original], [(0,0,200,200)], decisions, warnings) == 1
    assert original.text == 'Texto nativo'
    assert [b.text for b in page.blocks] == ['Texto nativo','Novo texto']
    assert any('diferente' in w.message for w in warnings)


@pytest.mark.parametrize('rotation', [0,90,180,270])
@pytest.mark.parametrize('crop', [False,True])
def test_converter_keeps_reference_image_and_visual_coordinates(resources, tmp_path, monkeypatch, rotation, crop):
    source = scanned_source(tmp_path / 'input', rotation=rotation, crop=crop)
    before = sha256(source.read_bytes()).hexdigest()
    def recognize(self, image, page, width, height, check, **kwargs):
        with pymupdf.open(image) as bitmap:
            assert bitmap[0].rect.width > 0
        return [dict(kind='text',bbox=[width*.1,height*.2,width*.8,height*.25],text='Texto por OCR')], .1
    monkeypatch.setattr(RecognitionClient, 'recognize', recognize)
    result = convert(source,tmp_path/'work')
    assert 'Texto por OCR' in result.markdown
    assert '![' in result.markdown and result.assets
    block = next(b for b in result.pages[0].blocks if b.text == 'Texto por OCR')
    width, height = result.pages[0].width, result.pages[0].height
    assert block.bbox == pytest.approx((width*.1,height*.2,width*.8,height*.25))
    assert sha256(source.read_bytes()).hexdigest() == before
    assert result.recognition['pages'][0]['status'] == 'recognized'
    assert result.recognition['pages'][0]['regions']
    assert result.recognition['image_policy'] == 'preserve'


def test_disabled_unavailable_and_engine_failure_fallback(tmp_path, resources, monkeypatch):
    source = scanned_source(tmp_path/'input')
    def unexpected(*args, **kwargs):
        raise AssertionError('OCR must not start')
    monkeypatch.setattr(RecognitionClient,'recognize',unexpected)
    result = convert(source,tmp_path/'off',options=ConversionOptions('off'))
    assert result.recognition['mode']=='off' and not result.recognition['pages']
    monkeypatch.setenv('PDF_OBSIDIAN_OCR_DIR',str(tmp_path/'absent'))
    result=convert(source,tmp_path/'missing')
    assert result.assets and result.recognition['pages'][0]['status']=='unavailable'
    monkeypatch.setenv('PDF_OBSIDIAN_OCR_DIR',str(resources))
    def broken(*args,**kwargs): raise RuntimeError('synthetic failure')
    monkeypatch.setattr(RecognitionClient,'recognize',broken)
    result=convert(source,tmp_path/'failed')
    assert result.assets and result.recognition['pages'][0]['status']=='failed'
    assert any('synthetic failure' in w.message for w in result.warnings)


def test_pure_digital_document_does_not_load_models(tmp_path,resources,monkeypatch):
    source=tmp_path/'native.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((30,80),'Only native text.',fontsize=12);pdf.save(source)
    monkeypatch.setattr(RecognitionClient,'start',lambda *a,**k:pytest.fail('Models loaded for native text'))
    result=convert(source,tmp_path/'work')
    assert 'Only native text.' in result.markdown and not result.recognition['pages']


def test_structured_output_survives_reconstruction_and_export(resources,tmp_path,monkeypatch):
    from pdf_obsidian.exporter import export_document,export_signature
    source=scanned_source(tmp_path/'input')
    def recognize(*args,**kwargs):
        return [table((20,100,220,200)),dict(kind='formula',bbox=[20,250,200,280],text=r'x^{2}=4')], .1
    monkeypatch.setattr(RecognitionClient,'recognize',recognize)
    result=convert(source,tmp_path/'work')
    assert '| Alfa | 10 |' in result.markdown and '$$\nx^{2}=4\n$$' in result.markdown
    vault=tmp_path/'vault';vault.mkdir()
    destination=export_document(result,vault)
    report=json.loads((destination/'conversao.json').read_text())
    assert report['recognition']==result.recognition
    assert (destination/'original.pdf').read_bytes()==source.read_bytes()
    assert all((destination/a.path).is_file() for a in result.assets)
    signature=export_signature(result)
    result.recognition=dict(result.recognition,mode='off')
    assert export_signature(result)!=signature


@pytest.mark.parametrize('failure',['timeout','cancel','stale','crash'])
def test_recognition_child_is_terminated_promptly(resources,tmp_path,monkeypatch,failure):
    script=tmp_path/'child.py'
    if failure in ('timeout','cancel'):
        script.write_text('import time;time.sleep(30)')
    elif failure=='stale':
        script.write_text('import json,sys,time\nr=json.loads(sys.stdin.readline());print(json.dumps(dict(id="old",page=1,blocks=[])),flush=True);time.sleep(30)')
    else:
        script.write_text('raise SystemExit(2)')
    real_popen=subprocess.Popen
    children=[]
    def launch(command,**kwargs):
        child=real_popen([sys.executable,str(script)],**kwargs);children.append(child);return child
    monkeypatch.setattr('pdf_obsidian.recognition.subprocess.Popen',launch)
    client=RecognitionClient(resources,tmp_path,timeout=.2)
    start=time.monotonic()
    def check():
        if failure=='cancel' and time.monotonic()-start>.08:raise ConversionCancelled()
    expected={'timeout':TimeoutError,'cancel':ConversionCancelled,'stale':ValueError,'crash':RuntimeError}[failure]
    with pytest.raises(expected):
        client.recognize(tmp_path/'unused.png',1,300,400,check)
    assert time.monotonic()-start<2
    assert children and children[0].poll() is not None
    assert client.process is None


def test_offline_model_bundle_can_be_verified_without_an_interpreter(resources):
    (resources/'environment/bin/python').unlink()
    assert not resource_status(resources)[0]
    assert verify_resources(resources,require_environment=False)['schema']==1


def test_memory_budget_terminates_child(resources,tmp_path,monkeypatch):
    script=tmp_path/'child-memory.py';script.write_text('import time;time.sleep(30)')
    real_popen=subprocess.Popen;children=[]
    def launch(command,**kwargs):
        child=real_popen([sys.executable,str(script)],**kwargs);children.append(child);return child
    monkeypatch.setattr('pdf_obsidian.recognition.subprocess.Popen',launch)
    client=RecognitionClient(resources,tmp_path,memory_limit=1)
    with pytest.raises(MemoryError,match='memória'):
        client.recognize(tmp_path/'unused.png',1,300,400,lambda:None)
    assert children[0].poll() is not None


def test_partial_table_native_text_is_preserved(tmp_path):
    line=TextLine('Não perder esta frase', (0,0,90,15), 12,'Geist',0,12,0)
    native=Block('text',line.text,1,line.bbox,12,lines=[line])
    page=Page(1,300,400,[native]);warnings=[]
    merge_recognition(page,[table()], [native],[(0,0,300,400)],[],warnings)
    assert native in page.blocks and native.text=='Não perder esta frase'
    assert not any(b.kind=='recognized_table' for b in page.blocks)
    assert any('conflita' in warning.message for warning in warnings)


def test_flat_raster_on_digital_page_keeps_image_without_loading_models(resources,tmp_path,monkeypatch):
    source=tmp_path/'flat.pdf'
    pix=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,100,30),False)
    pix.set_rect(pix.irect,(30,70,160))
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_text((40,80),'Native text.')
        page.insert_image(pymupdf.Rect(40,200,240,260),stream=pix.tobytes('png'));pdf.save(source)
    monkeypatch.setattr(RecognitionClient,'start',lambda *a,**k:pytest.fail('Flat image loaded OCR'))
    result=convert(source,tmp_path/'work')
    assert result.assets and '![' in result.markdown and not result.recognition['pages']


def test_rewritten_local_manifest_cannot_authorize_tampered_models(resources):
    model = resources / 'model.bin'
    model.write_bytes(b'tampered')
    path = resources / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['files']['model.bin'] = sha256(b'tampered').hexdigest()
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='modelos oficiais'):
        verify_resources(resources)


def test_ocr_child_receives_only_reduced_environment(resources, tmp_path, monkeypatch):
    monkeypatch.setenv('AUDIT_FAKE_SECRET', 'synthetic-only')
    monkeypatch.setenv('HF_TOKEN', 'synthetic-only')
    monkeypatch.setenv('PYTHONHOME', '/synthetic-invalid-home')
    script = tmp_path / 'environment_child.py'
    script.write_text('''
import json,os,sys
assert 'AUDIT_FAKE_SECRET' not in os.environ
assert 'HF_TOKEN' not in os.environ
assert 'PYTHONHOME' not in os.environ
assert os.environ['PYTHONNOUSERSITE']=='1'
r=json.loads(sys.stdin.readline())
print(json.dumps(dict(id=r['id'],page=r['page'],blocks=[])),flush=True)
''')
    real_popen = subprocess.Popen
    def launch(command, **kwargs):
        return real_popen([sys.executable, str(script)], **kwargs)
    monkeypatch.setattr('pdf_obsidian.recognition.subprocess.Popen', launch)
    client = RecognitionClient(resources, tmp_path)
    try:
        blocks, _ = client.recognize(tmp_path / 'unused.png', 1, 300, 400, lambda: None)
        assert blocks == []
    finally:
        client.close()
