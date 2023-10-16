import datetime as dt
import decimal as dec
import pathlib
from typing import TYPE_CHECKING, Iterator, Sequence

import pytz as tz
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal

from pynotas.models import Planilha
from pynotas.parser import (
    SEPARADORES_XP,
    get_next,
    get_next_text,
    get_text,
    montar_planilha,
    processar_dados,
    to_dec,
    to_dt,
)

if TYPE_CHECKING:
    from pynotas.models import LinhaPlanilha


def _dec_split(ds_texto: str, ds_indice: int) -> "dec.Decimal":
    return to_dec(ds_texto.split()[ds_indice])


def _dec_split_next(dsn_elementos: Iterator["LTTextBoxHorizontal"], dsn_indice: int) -> "dec.Decimal":
    dsn_texto = get_next_text(dsn_elementos)
    return to_dec(dsn_texto.split()[dsn_indice])


def _next_lista_decimal(nld_elementos: Iterator["LTTextBoxHorizontal"], nld_vezes: int = 1) -> list["dec.Decimal"]:
    nld_texto = get_next_text(nld_elementos, nld_vezes)
    return _lista_decimal(nld_texto)


def data_pregao(dp_elementos: Iterator["LTTextBoxHorizontal"]) -> dt.datetime:
    dp_texto = get_next_text(dp_elementos)
    return to_dt(dp_texto)


def _lista_decimal(ld_texto: str) -> list["dec.Decimal"]:
    return [to_dec(ld_decimal) for ld_decimal in ld_texto.split()]


def ativo(a_elementos: Iterator["LTTextBoxHorizontal"]) -> tuple[list[str], list[str]]:
    a_texto = get_next_text(a_elementos)  # Titulo
    if a_texto == "Valor Operação / Ajuste":
        a_texto = get_next_text(a_elementos)
    a_nomes = a_texto.split("\n")
    a_ativos = []
    a_tipos = []
    for a_nome in a_nomes:
        new_nome = a_nome
        if " CI" in a_texto:
            a_tipos.append("FII")
        else:
            a_tipos.append("Ação")
        for a_separador, a_indice in SEPARADORES_XP:
            new_nome = a_nome.split(a_separador)[a_indice]
        a_ativos.append(new_nome)
    return a_ativos, a_tipos


def quantidade(q_elementos: Iterator["LTTextBoxHorizontal"]) -> list[dec.Decimal]:
    q_texto = get_next_text(q_elementos, 2)
    while True:
        try:
            int(q_texto[0])
            return _lista_decimal(q_texto)
        except ValueError:
            q_texto = get_next_text(q_elementos)


def preco(p_elementos: Iterator["LTTextBoxHorizontal"]) -> list[dec.Decimal]:
    return _next_lista_decimal(p_elementos)


def total(t_elementos: Iterator["LTTextBoxHorizontal"]) -> list[dec.Decimal]:
    t_texto = get_next_text(t_elementos)
    while True:
        try:
            int(t_texto[4])
            return _lista_decimal(t_texto[4:].replace(" D", ""))
        except (ValueError, IndexError):
            t_texto = get_next_text(t_elementos)


def clearing(
    c_elementos: Iterator["LTTextBoxHorizontal"],
) -> tuple[dec.Decimal, dec.Decimal]:
    c_texto = get_next_text(c_elementos)
    return _dec_split(c_texto, 0), _dec_split(c_texto, 1)


def bolsa(b_elementos: Iterator["LTTextBoxHorizontal"]) -> dec.Decimal:
    return _dec_split_next(b_elementos, 2)


def liquido(l_elementos: Iterator["LTTextBoxHorizontal"]) -> dec.Decimal:
    return _dec_split_next(l_elementos, 1)


def read_xp(file_path: pathlib.Path) -> Sequence["LinhaPlanilha"]:

    data_nota = dt.datetime(1970, 1, 1, tzinfo=tz.utc)
    contador = 0

    ativos: list[str] = []
    tipos: list[str] = []
    quantidades: list[dec.Decimal] = []
    precos: list[dec.Decimal] = []
    totais: list[dec.Decimal] = []
    taxa_liquidacao = dec.Decimal(-1)
    taxa_emolumento = dec.Decimal(-1)
    nota_total_sem_taxa = dec.Decimal(-1)
    nota_total_com_taxa = dec.Decimal(-1)
    linhas_planilha: list["LinhaPlanilha"] = []

    for page_layout in extract_pages(file_path):
        try:
            elementos: Iterator["LTTextBoxHorizontal"] = iter(
                page_layout,  # type: ignore[arg-type]
            )
            while True:
                elemento = get_next(elementos)
                if isinstance(elemento, LTTextBoxHorizontal):
                    texto = get_text(elemento)
                    if texto == "Data pregão":
                        data_nota = data_pregao(elementos)
                    elif "C/V Tipo mercado" in texto:
                        contador = texto.count("C VISTA")  # Tipo mercado
                    elif texto == "Preço / Ajuste":
                        ativos, tipos = ativo(elementos)
                        quantidades = quantidade(elementos)  # Quantidade
                        precos = preco(elementos)  # Preco
                        totais = total(elementos)  # Total
                    elif (
                        "Taxa Operacional\nExecução\n"
                        "Taxa de Custódia\nImpostos\nI.R.R.F." in texto
                    ):
                        nota_total_sem_taxa, taxa_liquidacao = clearing(elementos)  # Clearing
                        taxa_emolumento = bolsa(elementos)  # Bolsa
                    elif "Total Custos / Despesas\nLíquido para " in texto:
                        nota_total_com_taxa = liquido(elementos)  # Liquido
        except StopIteration:
            planilha = Planilha(
                data_nota,
                contador,
                ativos,
                tipos,
                quantidades,
                precos,
                totais,
                taxa_liquidacao,
                taxa_emolumento,
                nota_total_sem_taxa,
                nota_total_com_taxa,
            )
            dados_processados = processar_dados(planilha)

        montar_planilha(planilha, dados_processados, linhas_planilha, "XP")
    return linhas_planilha
