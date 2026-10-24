from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    size: float
    font: str
    flags: int
    baseline: float
    source_block: int
    direction: tuple[float, float] = (1, 0)
    role: str | None = None


@dataclass
class Block:
    kind: str
    text: str
    page: int
    bbox: tuple[float, float, float, float]
    size: float = 0
    asset: str | None = None
    lines: list[TextLine] = field(default_factory=list)
    role: str = "body"
    heading_level: int | None = None


@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Warning:
    page: int
    message: str


@dataclass
class AssetInfo:
    path: str
    origin: str
    role: str
    page: int
    bbox: tuple[float, float, float, float]
    page_size: tuple[float, float]
    source_digest: str | None = None
    generated_markdown: str | None = None


@dataclass
class FilteredImage:
    asset: str
    page: int
    bbox: tuple[float, float, float, float]
    reason: str
    signature: str


@dataclass
class ConversionResult:
    source: Path
    source_hash: str
    title: str
    markdown: str
    workspace: Path
    pages: list[Page]
    warnings: list[Warning]
    decisions: list[str] = field(default_factory=list)
    assets: list[AssetInfo] = field(default_factory=list)
    filtered_images: list[FilteredImage] = field(default_factory=list)
    recognition: dict | None = None
