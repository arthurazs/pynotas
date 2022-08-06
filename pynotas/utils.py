import datetime as dt
import decimal as dec
import pathlib
from typing import Any, Final, Sequence, TypedDict, TypeVar

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1

AnyNumber = TypeVar("AnyNumber", int, dec.Decimal)

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


def almost_equal(a: AnyNumber, b: AnyNumber) -> bool:
    return abs(a - b) <= FLOATING_ERROR_PRECISION


def assert_almost_equal(a: AnyNumber, b: AnyNumber, text: str = "") -> None:
    if not almost_equal(a, b):
        print(f"\n{a=}\n{b=}")
        raise SystemError(f"[{text}] a != b")


def assert1page(file_path: pathlib.Path) -> None:
    with open(file_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        parser.set_document(doc)
        pages = resolve1(doc.catalog["Pages"])
        pages_count = pages.get("Count", 0)
        if pages_count != 1:
            raise NotImplementedError("Only works for PDFs with one page...")


def _assert_data_found(
    data_nota: dt.datetime,
    contador: int,
    ativos: list[str],
    tipos: list[str],
    quantidades: list[dec.Decimal],
    precos: list[dec.Decimal],
    totais: list[dec.Decimal],
    taxa_liquidacao: dec.Decimal,
    taxa_emolumento: dec.Decimal,
    nota_total_sem_taxa: dec.Decimal,
    nota_total_com_taxa: dec.Decimal,
) -> None:

    if data_nota == dt.datetime(1970, 1, 1):
        raise SystemError("data_nota not found in PDF")
    if contador < 1:
        raise SystemError("no assets in PDF?")
    if len(ativos) == 0:
        raise SystemError("no assets in PDF?")
    if len(tipos) == 0:
        raise SystemError("no types in PDF?")
    if len(quantidades) == 0:
        raise SystemError("no quantities in PDF?")
    if len(precos) == 0:
        raise SystemError("no prices in PDF?")
    if len(totais) == 0:
        raise SystemError("no totals in PDF?")
    if taxa_liquidacao < 0:
        raise SystemError("no liquidation fee in PDF?")
    if taxa_emolumento < 0:
        raise SystemError("no emolument fee in PDF?")
    if nota_total_sem_taxa < 0:
        raise SystemError("no total without fee in PDF?")
    if nota_total_com_taxa < 0:
        raise SystemError("no total with fee in PDF?")
