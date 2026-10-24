"""Offline-only recognition helper. Its stdout is a versioned JSON-lines channel."""
import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import socket
import signal
import re
import sys
import traceback


def block_network():
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise PermissionError('OCR é estritamente offline; conexão de rede bloqueada.')
        return original(sock, address)
    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise PermissionError('OCR é estritamente offline; conexão de rede bloqueada.')
        return original_ex(sock, address)
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex


class Engine:
    def __init__(self, root):
        import torch
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, TableFormerMode, OcrMode
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
        from docling.document_converter import DocumentConverter, ImageFormatOption
        torch.set_num_threads(2)
        options = PdfPipelineOptions(
            artifacts_path=root / 'models',
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=2),
            enable_remote_services=False, allow_external_plugins=False,
            do_ocr=True, do_table_structure=True, do_formula_enrichment=True,
            do_code_enrichment=False, do_picture_classification=False, do_picture_description=False,
            generate_parsed_pages=True, ocr_batch_size=1, layout_batch_size=1, table_batch_size=1,
            queue_max_size=1, document_timeout=175,
            ocr_options=RapidOcrOptions(lang=['latin'], backend='onnxruntime', mode=OcrMode.FULL_PAGE,
                                        text_score=.6, scale=1.0, print_verbose=False))
        options.table_structure_options.mode = TableFormerMode.FAST
        options.code_formula_options.model_spec.max_new_tokens = 1024
        self.converter = DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)})

    def recognize(self, request):
        result = self.converter.convert(Path(request['image']), raises_on_error=True)
        if not result.pages:
            raise ValueError('Motor OCR não retornou uma página.')
        page = result.pages[0]
        width, height = float(page.size.width), float(page.size.height)
        sx, sy = request['width'] / width, request['height'] / height
        def bbox(raw):
            box = raw.to_top_left_origin(height)
            output = [max(0., box.l * sx), max(0., box.t * sy),
                      min(request['width'], box.r * sx), min(request['height'], box.b * sy)]
            return output if output[2] > output[0] and output[3] > output[1] else None
        blocks = []
        if page.parsed_page:
            for cell in page.parsed_page.textline_cells:
                box = bbox(cell.rect.to_bounding_box())
                if box and cell.text.strip():
                    blocks.append(dict(kind='text', bbox=box, text=cell.text))
        for item, _level in result.document.iterate_items():
            if not getattr(item, 'prov', None):
                continue
            box = bbox(item.prov[0].bbox)
            if not box:
                continue
            label = str(item.label.value)
            if label == 'table':
                cells = []
                for cell in item.data.table_cells:
                    cells.append(dict(r0=cell.start_row_offset_idx, r1=cell.end_row_offset_idx,
                                      c0=cell.start_col_offset_idx, c1=cell.end_col_offset_idx,
                                      text=cell.text, bbox=bbox(cell.bbox) if cell.bbox else None))
                blocks.append(dict(kind='table', bbox=box, text='', rows=item.data.num_rows,
                                   cols=item.data.num_cols, cells=cells))
            elif label == 'formula':
                blocks.append(dict(kind='formula', bbox=box, text=item.text))
        # Layout classifiers sometimes label a short standalone equation as text.
        # Restrict supplementary formula recognition to explicit math lines or
        # formula regions already detected by the native converter.
        candidates = list(request.get('formula_regions', []))
        for block in blocks:
            if (block['kind'] == 'text' and re.search(r'[=∫∑√]', block['text'])
                    and not re.search(r'[A-Za-zÀ-ÿ]{4,}', block['text'])
                    and len(block['text']) < 300):
                candidates.append(block['bbox'])
        if candidates:
            from PIL import Image
            from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
            from docling.models.inference_engines.vlm import VlmEngineInput
            from docling.datamodel.base_models import InputFormat
            pipeline = self.converter._get_pipeline(InputFormat.IMAGE)
            formula_stage = next((model for model in pipeline.enrichment_pipe
                                  if isinstance(model, CodeFormulaVlmModel)), None)
            if formula_stage and formula_stage.engine:
                with Image.open(request['image']) as image:
                    for box in candidates:
                        def overlap(other):
                            area = max(1, (box[2]-box[0])*(box[3]-box[1]))
                            return max(0, min(box[2],other[2])-max(box[0],other[0])) * max(0, min(box[3],other[3])-max(box[1],other[1])) / area
                        if any(block['kind'] in ('formula', 'table') and overlap(block['bbox']) > .5 for block in blocks):
                            continue
                        xscale, yscale = image.width / request['width'], image.height / request['height']
                        crop = image.crop((max(0, int(box[0]*xscale)-8), max(0, int(box[1]*yscale)-8),
                                           min(image.width, int(box[2]*xscale)+8), min(image.height, int(box[3]*yscale)+8))).convert('RGB')
                        output = formula_stage.engine.predict_batch([VlmEngineInput(
                            image=crop, prompt='<formula>', temperature=0.0, max_new_tokens=512)])
                        text = formula_stage._post_process([output[0].text])[0]
                        if text.strip():
                            blocks.append(dict(kind='formula', bbox=list(box), text=text))
        return dict(id=request['id'], page=request['page'], blocks=blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    # A crashed/terminated PDF worker must not leave a multi-GB helper orphaned.
    if sys.platform.startswith('linux'):
        import ctypes
        parent_pid = os.getppid()
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'Não foi possível vincular o ciclo de vida do OCR ao worker.')
        if os.getppid() != parent_pid:
            return
    root = args.root.resolve()
    os.environ.update(HF_HOME=str(root / 'cache'), XDG_CACHE_HOME=str(root / 'cache'),
                      HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    block_network()
    protocol = sys.stdout
    engine = None
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if request.get("stop"):
                break
            with redirect_stdout(sys.stderr):
                if engine is None:
                    engine = Engine(root)
                response = engine.recognize(request)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            response = dict(id=request.get('id'), page=request.get('page'), error=str(exc))
        protocol.write(json.dumps(response, ensure_ascii=False) + '\n')
        protocol.flush()


if __name__ == '__main__':
    main()
