import pytz as tz
import datetime as dt
import decimal as dec
import pathlib
from typing import Any, Final, Sequence, TYPE_CHECKING

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1
import sys

if TYPE_CHECKING:
    from pynotas.models import Planilha, AnyNumber

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
)
CABECALHO: Final[Sequence[str]] = (
    "data",
    "ativo",
    "tipo",
    "local",
    "corretora",
    *DECIMAL2STR,
)


def eprint(*args: Any) -> None:
    print()
    for index, arg in enumerate(args):
        print(index, arg)
    sys.exit()


def almost_equal(
    a: "AnyNumber", b: "AnyNumber", precision: dec.Decimal = FLOATING_ERROR_PRECISION
) -> bool:
    return abs(a - b) <= precision


def assert_almost_equal(
    a: "AnyNumber",
    b: "AnyNumber",
    text: str = "",
    precision: dec.Decimal = FLOATING_ERROR_PRECISION,
) -> None:
    if not almost_equal(a, b, precision):
        print(f"\n{a=}\n{b=}")
        msg = f"[{text}] a != b"
        raise SystemError(msg)


def assert1page(file_path: pathlib.Path) -> None:
    with file_path.open("rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        parser.set_document(doc)
        pages = resolve1(doc.catalog["Pages"])
        pages_count = pages.get("Count", 0)
        if pages_count != 1:
            msg = "Only works for PDFs with one page..."
            raise NotImplementedError(msg)


def _assert_data_found(planilha: "Planilha") -> None:  # noqa: C901

    if planilha.data_nota == dt.datetime(1970, 1, 1, tzinfo=tz.utc):
        msg = "data_nota not found in PDF"
        raise SystemError(msg)
    if planilha.contador < 1:
        msg = "no assets in PDF?"
        raise SystemError(msg)
    if len(planilha.ativos) == 0:
        msg = "no assets in PDF?"
        raise SystemError(msg)
    if len(planilha.tipos) == 0:
        msg = "no types in PDF?"
        raise SystemError(msg)
    if len(planilha.quantidades) == 0:
        msg = "no quantities in PDF?"
        raise SystemError(msg)
    if len(planilha.precos) == 0:
        msg = "no prices in PDF?"
        raise SystemError(msg)
    if len(planilha.totais) == 0:
        msg = "no totals in PDF?"
        raise SystemError(msg)
    if planilha.taxa_liquidacao < 0:
        msg = "no liquidation fee in PDF?"
        raise SystemError(msg)
    if planilha.taxa_emolumento < 0:
        msg = "no emolument fee in PDF?"
        raise SystemError(msg)
    if planilha.nota_total_sem_taxa < 0:
        msg = "no total without fee in PDF?"
        raise SystemError(msg)
    if planilha.nota_total_com_taxa < 0:
        msg = "no total with fee in PDF?"
        raise SystemError(msg)
