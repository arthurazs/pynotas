from typing import TYPE_CHECKING, Iterator, MutableMapping

from pynotas.utils import get_next_text, to_dec

if TYPE_CHECKING:
    import decimal as dec

    from pdfminer.layout import LTTextBoxHorizontal


def _lista_decimal(ld_texto: str) -> list["dec.Decimal"]:
    ld_lista = []
    for ld_decimal in ld_texto.split():
        ld_lista.append(to_dec(ld_decimal))
    return ld_lista


def _next_lista_decimal(
    nld_elementos: Iterator["LTTextBoxHorizontal"], nld_vezes: int = 1
) -> list["dec.Decimal"]:
    nld_texto = get_next_text(nld_elementos, nld_vezes)
    return _lista_decimal(nld_texto)


def _dec_split(ds_texto: str, ds_indice: int) -> "dec.Decimal":
    return to_dec(ds_texto.split()[ds_indice])


def _dec_split_next(
    dsn_elementos: Iterator["LTTextBoxHorizontal"], dsn_indice: int
) -> "dec.Decimal":
    dsn_texto = get_next_text(dsn_elementos)
    return to_dec(dsn_texto.split()[dsn_indice])


def generico(
    g_elementos: Iterator["LTTextBoxHorizontal"], g_vezes: int = 1
) -> "dec.Decimal":
    return abs(to_dec(get_next_text(g_elementos, g_vezes)))


def _add2default(
    gd_dict: MutableMapping[str, list["dec.Decimal"]],
    gd_name: str,
    gd_value: "dec.Decimal",
) -> None:
    gd_name_list = gd_dict.setdefault(gd_name, [])
    gd_name_list.append(gd_value)
