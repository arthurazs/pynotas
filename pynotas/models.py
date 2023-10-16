
from enum import Enum
import datetime as dt
from typing import NamedTuple, TypedDict, Mapping, MutableMapping, TypeVar
import decimal as dec

ProcessedDataType = Mapping[str, MutableMapping[str, dec.Decimal]]
AnyNumber = TypeVar("AnyNumber", int, dec.Decimal)


class LinhaPlanilha(TypedDict):
    data: str
    ativo: str
    tipo: str
    local: str
    corretora: str
    quantidade: str
    taxa_ativo: str
    quantidade_final: str
    preco: str
    taxa_unitaria: str
    preco_medio: str
    preco_total: str
    taxa_total: str
    total_investido: str


class Planilha(NamedTuple):
    data_nota: dt.datetime
    contador: int
    ativos: list[str]
    tipos: list[str]
    quantidades: list[dec.Decimal]
    precos: list[dec.Decimal]
    totais: list[dec.Decimal]
    taxa_liquidacao: dec.Decimal
    taxa_emolumento: dec.Decimal
    nota_total_sem_taxa: dec.Decimal
    nota_total_com_taxa: dec.Decimal


class TickerType(str, Enum):
    stock = "Stock"
    etf = "ETF"
    reit = "REIT"


class Sheet(NamedTuple):
    date: dt.date
    counter: int
    actions: list[str]
    tickers: list[str]
    types: list[TickerType]
    quantities: list[dec.Decimal]
    prices: list[dec.Decimal]
    totals: list[dec.Decimal]