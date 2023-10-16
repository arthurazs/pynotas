import datetime as dt
import decimal as dec
import pathlib
from typing import TYPE_CHECKING, Iterator, Sequence

import pytz as tz
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal

from pynotas.models import Planilha, ProcessedDataType
from pynotas.parser import (
    SEPARADORES_NU,
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


def data_pregao(dp_texto: str) -> dt.datetime:
    dp_texto = dp_texto.split("\n")[1]
    return to_dt(dp_texto)


def ativo(a_elementos: Iterator["LTTextBoxHorizontal"], a_flag: int, a_texto: str) -> tuple[list[str], list[str]]:

    a_lista = []
    a_tipos = []
    a_contador = 0
    while True:
        if a_texto in ("FRACIONARIO", "D2S", "NOR", "VISTA"):
            a_texto = get_next_text(a_elementos)
            continue

        if " CI" in a_texto:
            a_tipos.append("FII")
        else:
            a_tipos.append("Ação")
        for a_separador, a_indice in SEPARADORES_NU:
            a_texto = a_texto.split(a_separador)[a_indice]
        a_lista.append(a_texto)

        a_contador += 1
        if a_contador == a_flag:
            return a_lista, a_tipos
        try:
            a_texto = get_next_text(a_elementos)
        except AttributeError:
            get_next(a_elementos)
            continue


def _add_dec2list_v2(adl_elementos: Iterator["LTTextBoxHorizontal"], adl_flag: int) -> tuple[
    list[dec.Decimal], list[dec.Decimal],
]:
    adl_lista1 = []
    adl_lista2 = []
    adl_contador = 0
    while True:
        adl_texto = get_next_text(adl_elementos)
        if " D" in adl_texto:
            adl_lista2.append(to_dec(adl_texto.replace(" D", "")))
        else:
            adl_lista1.append(to_dec(adl_texto))
        adl_contador += 1
        if adl_contador == (2 * adl_flag):
            return adl_lista1, adl_lista2


def _add_dec2list(
    adl_elementos: Iterator["LTTextBoxHorizontal"],
    adl_flag: int,
    adl_texto: str | None = None,
) -> list[dec.Decimal]:
    if adl_texto is None:
        adl_lista = []
        adl_contador = 0
    else:
        adl_lista = [to_dec(adl_texto.replace(" D", ""))]
        adl_contador = 1
    while True:
        if adl_contador == adl_flag:
            return adl_lista
        adl_texto = get_next_text(adl_elementos)
        # TODO @arthurazs: replace D apenas no total
        adl_lista.append(to_dec(adl_texto.replace(" D", "")))
        adl_contador += 1


def generico(g_elementos: Iterator["LTTextBoxHorizontal"], g_vezes: int = 1) -> "dec.Decimal":
    return abs(to_dec(get_next_text(g_elementos, g_vezes)))


def quantidade(
    q_elementos: Iterator["LTTextBoxHorizontal"],
    q_flag: int,
    q_texto: str | None = None,
) -> list[dec.Decimal]:
    return _add_dec2list(q_elementos, q_flag, q_texto)


def preco(p_elementos: Iterator["LTTextBoxHorizontal"], p_flag: int) -> list[dec.Decimal]:
    return _add_dec2list(p_elementos, p_flag)


def total(t_elementos: Iterator["LTTextBoxHorizontal"], t_flag: int) -> list[dec.Decimal]:
    return _add_dec2list(t_elementos, t_flag)


def preco_total(p_elementos: Iterator["LTTextBoxHorizontal"], p_flag: int) -> tuple[
    list[dec.Decimal], list[dec.Decimal],
]:
    return _add_dec2list_v2(p_elementos, p_flag)


def clearing(
    c_elementos: Iterator["LTTextBoxHorizontal"],
) -> tuple[dec.Decimal, dec.Decimal]:
    c_texto = get_next_text(c_elementos)
    while True:
        try:
            c_total = abs(to_dec(c_texto))
        except dec.InvalidOperation:
            c_texto = get_next_text(c_elementos)
        else:
            break
    c_texto = get_next_text(c_elementos)
    c_liquidacao = abs(to_dec(c_texto))
    return c_total, c_liquidacao


def bolsa(b_elementos: Iterator["LTTextBoxHorizontal"]) -> dec.Decimal:
    return abs(to_dec(get_next_text(b_elementos, 5)))


def liquido(l_elementos: Iterator["LTTextBoxHorizontal"]) -> dec.Decimal:
    return abs(to_dec(get_next_text(l_elementos).split()[0]))


def _alternative(
    a_elements: Iterator["LTTextBoxHorizontal"],
) -> tuple[list[str] | None, list[str], int, str]:
    a_list: list[str] = []
    a_types: list[str] = []
    a_counter = 0
    while True:
        a_text = get_next_text(a_elements)
        if a_text == "C":
            return None, [], 0, a_text
        if a_text in ("FRACIONARIO", "D2S", "NOR", "VISTA", "#"):
            continue
        try:
            dec.Decimal(a_text)
        except dec.InvalidOperation:
            if " CI" in a_text:
                a_types.append("FII")
            else:
                a_types.append("Ação")
            for a_separator, a_index in SEPARADORES_NU:
                a_text = a_text.split(a_separator)[a_index]
            a_list.append(a_text)

            a_counter += 1
        else:
            return a_list, a_types, a_counter, a_text


def read_nu(file_path: pathlib.Path) -> Sequence["LinhaPlanilha"]:  # noqa: C901, PLR0912, PLR0915

    versao: int | None = None
    data_nota = dt.datetime(1970, 1, 1, tzinfo=tz.utc)
    contador = 0
    contador_alt = 0
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
    dados_processados: ProcessedDataType = {}

    for page_layout in extract_pages(file_path):
        try:
            elementos: Iterator["LTTextBoxHorizontal"] = iter(
                page_layout,  # type: ignore[arg-type]
            )
            while True:
                elemento = get_next(elementos)
                if isinstance(elemento, LTTextBoxHorizontal):
                    texto = get_text(elemento)
                    if "Data Pregão" in texto:
                        data_nota = data_pregao(texto)
                    elif "C/VC/V" in texto:
                        texto = get_next_text(elementos)
                        while texto != "C":
                            texto = get_next_text(elementos)
                            if texto == "Valor/Ajuste D/CD/C\nValor/Ajuste":
                                auxiliar, tipos, contador_alt, texto = _alternative(elementos)
                                if auxiliar is None:
                                    break
                                ativos = auxiliar
                                quantidades = quantidade(elementos, contador_alt, texto)
                                precos, totais = preco_total(elementos, contador_alt)
                        while texto == "C":
                            contador += 1
                            texto = get_next_text(elementos)
                        if contador_alt == contador:
                            continue
                        ativos, tipos = ativo(elementos, contador, texto)

                        texto = get_next_text(elementos)
                        if texto == "Resumo dos Negócios\nResumo dos Negócios":
                            versao = 2  # NuInvest
                            while texto != "Outras":
                                texto = get_next_text(elementos)
                            quantidades = quantidade(elementos, contador)
                            precos, totais = preco_total(elementos, contador)
                            nota_total_sem_taxa = generico(elementos)
                            taxa_liquidacao = generico(elementos)
                            taxa_emolumento = generico(elementos, 5)
                        else:
                            versao = 1  # EasyInvest
                            quantidades = quantidade(elementos, contador, texto)
                            precos, totais = preco_total(elementos, contador)
                    elif contador_alt > 0:
                        if "Líquido para" in texto:
                            nota_total_com_taxa = liquido(elementos)  # Liquido
                            get_next(elementos)
                            nota_total_sem_taxa, taxa_liquidacao = clearing(elementos)  # Clearing
                            taxa_emolumento = bolsa(elementos)
                    elif texto == "Outras" and versao == 1:
                        nota_total_sem_taxa, taxa_liquidacao = clearing(elementos)  # Clearing
                        taxa_emolumento = bolsa(elementos)
                    elif "Líquido para" in texto:
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

        montar_planilha(planilha, dados_processados, linhas_planilha, "Nu")
    return linhas_planilha
