import importlib.util
from pathlib import Path
from pdf_obsidian.converter import convert


def test_shared_corpus(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "fixtures", Path(__file__).parents[1] / "tools" / "reading_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, source, tokens in module.generate(tmp_path):
        result = convert(source, tmp_path / (name + "-work"))
        positions = [result.markdown.index(token) for token in tokens]
        assert positions == sorted(positions), name
        assert all(result.markdown.count(token) == 1 for token in tokens), name
