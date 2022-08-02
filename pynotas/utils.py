import datetime as dt
import decimal as dec
import pathlib
from typing import TYPE_CHECKING, Any, Final, Iterator, Sequence, TypedDict, TypeVar

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1

if TYPE_CHECKING:
    from pdfminer.layout import LTTextBoxHorizontal

CodeReturnType = TypeVar("CodeReturnType", dt.datetime, str, dec.Decimal)

FLOATING_ERROR_PRECISION: Final[dec.Decimal] = dec.Decimal(1e-10)
DECIMAL2STR: Final[Sequence[str]] = (
    "quantidade",
    "taxa_ativo",
    "quantidade_final",
    "preco",
    "taxa_unitaria",
    "preco_medio",
    "preco_total",
    "taxa_total",
    "total_investido",
    "total_investido_em_real",
)
CABECALHO: Final[Sequence[str]] = (
    "data",
    "ativo",
    "tipo",
    "local",
    "corretora",
    *DECIMAL2STR,
)
SEPARADORES_XP: Sequence[tuple[str | None, int]] = (
    (" CI ER", 0),
    (" CI", 0),
    (None, -1),
)
SEPARADORES_NU: Sequence[tuple[str | None, int]] = (
    ("F ON", 0),
    ("F UNT", 0),
    ("F PN ", 0),
    (" PN ", 0),
    (" CI ER", 0),
    (" CI", 0),
    (None, -1),
)


class LinhaPlanilha(TypedDict):
    data: dt.datetime | str
    ativo: str
    tipo: str
    local: str
    corretora: str
    quantidade: dec.Decimal
    taxa_ativo: dec.Decimal
    quantidade_final: dec.Decimal
    preco: dec.Decimal
    taxa_unitaria: dec.Decimal
    preco_medio: dec.Decimal
    preco_total: dec.Decimal
    taxa_total: dec.Decimal
    total_investido: dec.Decimal
    total_investido_em_real: dec.Decimal


def eprint(*args: Any) -> None:
    print()
    for index, arg in enumerate(args):
        print(index, arg)
    exit()


def aprint(elements: Iterator["LTTextBoxHorizontal"]) -> None:
    print()
    while True:
        try:
            print(">>>", get_next_text(elements))
        except StopIteration:
            exit()


def almost_equal(a: dec.Decimal, b: dec.Decimal) -> bool:
    return abs(a - b) <= FLOATING_ERROR_PRECISION


def to_dec(t_number: str) -> dec.Decimal:
    return dec.Decimal(t_number.replace(".", "").replace(",", "."))


def get_next(
    gn_elements: Iterator["LTTextBoxHorizontal"], gn_times: int = 1
) -> "LTTextBoxHorizontal":
    for _ in range(gn_times - 1):
        next(gn_elements)
    return next(gn_elements)


def get_text(gt_element: "LTTextBoxHorizontal") -> str:
    return gt_element.get_text().strip()


def get_next_text(
    gnt_elements: Iterator["LTTextBoxHorizontal"], gnt_times: int = 1
) -> str:
    gnt_element = get_next(gnt_elements, gnt_times)
    return get_text(gnt_element)


def assert1page(file_path: pathlib.Path) -> None:
    with open(file_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        parser.set_document(doc)
        pages = resolve1(doc.catalog["Pages"])
        pages_count = pages.get("Count", 0)
        if pages_count != 1:
            raise NotImplementedError("Only works for PDFs with one page...")
