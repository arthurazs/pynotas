import datetime as dt
import decimal as dec
import pathlib
from typing import Iterator, Mapping, MutableMapping, Sequence

import pytz as tz
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal

from pynotas.parser import _add2default, generico
from pynotas.utils import (
    SEPARADORES_NU,
    LinhaPlanilha,
    almost_equal,
    get_next,
    get_next_text,
    get_text,
    to_dec,
)


def data_pregao(dp_texto: str) -> dt.datetime:
    dp_texto = dp_texto.split("\n")[1]
    ano, mes, dia = map(int, dp_texto.split("/")[::-1])
    return dt.datetime(ano, mes, dia, tzinfo=tz.utc)


def ativo(
    a_elementos: Iterator["LTTextBoxHorizontal"], a_flag: int, a_texto: str
) -> tuple[list[str], list[str]]:

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


def _add_dec2list_v2(
    adl_elementos: Iterator["LTTextBoxHorizontal"], adl_flag: int
) -> tuple[list[dec.Decimal], list[dec.Decimal]]:
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
        # TODO replace D apenas no total
        adl_lista.append(to_dec(adl_texto.replace(" D", "")))
        adl_contador += 1


def quantidade(
    q_elementos: Iterator["LTTextBoxHorizontal"],
    q_flag: int,
    q_texto: str | None = None,
) -> list[dec.Decimal]:
    return _add_dec2list(q_elementos, q_flag, q_texto)


def preco(
    p_elementos: Iterator["LTTextBoxHorizontal"], p_flag: int
) -> list[dec.Decimal]:
    return _add_dec2list(p_elementos, p_flag)


def total(
    t_elementos: Iterator["LTTextBoxHorizontal"], t_flag: int
) -> list[dec.Decimal]:
    return _add_dec2list(t_elementos, t_flag)


def preco_total(
    p_elementos: Iterator["LTTextBoxHorizontal"], p_flag: int
) -> tuple[list[dec.Decimal], list[dec.Decimal]]:
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


def montar_dados_nota(
    mdn_ativos: list[str],
    mdn_tipos: list[str],
    mdn_quantidades: list[dec.Decimal],
    mdn_precos: list[dec.Decimal],
    mdn_totais: list[dec.Decimal],
) -> Mapping[str, Mapping[str, list[dec.Decimal]]]:
    mdn_dados_nota: MutableMapping[str, MutableMapping[str, list[dec.Decimal]]] = {}
    for mdn_indice_nota, mdn_nome_nota in enumerate(mdn_ativos):
        mdn_dic_nota = mdn_dados_nota.setdefault(mdn_nome_nota, {})
        mdn_dic_nota["tipo"] = mdn_tipos[mdn_indice_nota]  # type:ignore[assignment]
        _add2default(mdn_dic_nota, "quantidade", mdn_quantidades[mdn_indice_nota])
        _add2default(mdn_dic_nota, "preco_sem_taxa", mdn_precos[mdn_indice_nota])
        _add2default(mdn_dic_nota, "total_sem_taxa", mdn_totais[mdn_indice_nota])
    return mdn_dados_nota


def montar_dados_processados(
    mdp_dados_nota: Mapping[str, Mapping[str, list[dec.Decimal]]]
) -> Mapping[str, MutableMapping[str, dec.Decimal]]:
    mdp_dados_processados: MutableMapping[str, MutableMapping[str, dec.Decimal]] = {}
    for mdp_nome_nota, mdp_ativo_nota in mdp_dados_nota.items():
        mdp_dic_processado = mdp_dados_processados.setdefault(mdp_nome_nota, {})
        mdp_dic_processado["tipo"] = mdp_ativo_nota["tipo"]  # type:ignore[assignment]
        mdp_dic_processado["quantidade"] = sum(
            # type: ignore[assignment]
            mdp_ativo_nota["quantidade"]
        )
        mdp_total_processado = dec.Decimal(0)
        for mdp_indice, mdp_quantidade_nota in enumerate(mdp_ativo_nota["quantidade"]):
            mdp_total_processado += (
                mdp_quantidade_nota * mdp_ativo_nota["preco_sem_taxa"][mdp_indice]
            )
        if mdp_total_processado != sum(mdp_ativo_nota["total_sem_taxa"]):
            print(
                f"{mdp_nome_nota=}, {mdp_total_processado=}, "
                f"{sum(mdp_ativo_nota['total'])=}"
            )
            raise SystemError("mdp_total_processado != sum(mdp_ativo_nota['total'])")
        mdp_dic_processado["preco_sem_taxa"] = (
            mdp_total_processado / mdp_dic_processado["quantidade"]
        )
        mdp_dic_processado["total_sem_taxa"] = mdp_total_processado
    return mdp_dados_processados


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
            return a_list, a_types, a_counter, a_text
        except dec.InvalidOperation:
            if " CI" in a_text:
                a_types.append("FII")
            else:
                a_types.append("Ação")
            for a_separator, a_index in SEPARADORES_NU:
                a_text = a_text.split(a_separator)[a_index]
            a_list.append(a_text)

            a_counter += 1


def read_nu(file_path: pathlib.Path) -> Sequence[LinhaPlanilha]:
    versao: int | None = None
    data_nota = dt.datetime(1970, 1, 1)
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
    planilha: list[LinhaPlanilha] = []
    dados_processados: Mapping[str, MutableMapping[str, dec.Decimal]] = {}

    for page_layout in extract_pages(file_path):
        try:
            elementos: Iterator["LTTextBoxHorizontal"] = iter(
                page_layout  # type: ignore[arg-type]
            )
            while True:
                elemento = get_next(elementos)
                if isinstance(elemento, LTTextBoxHorizontal):
                    texto = get_text(elemento)
                    # while True:
                    #     texto = get_next_text(elementos)
                    #     print(">>>", texto)
                    if "Data Pregão" in texto:
                        data_nota = data_pregao(texto)
                    elif "C/VC/V" in texto:
                        texto = get_next_text(elementos)
                        # aprint(elementos)
                        while texto != "C":
                            texto = get_next_text(elementos)
                            if texto == "Valor/Ajuste D/CD/C\nValor/Ajuste":
                                auxiliar, tipos, contador_alt, texto = _alternative(
                                    elementos
                                )
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
                            nota_total_sem_taxa, taxa_liquidacao = clearing(
                                elementos
                            )  # Clearing
                            taxa_emolumento = bolsa(elementos)
                    elif texto == "Outras" and versao == 1:
                        nota_total_sem_taxa, taxa_liquidacao = clearing(
                            elementos
                        )  # Clearing
                        taxa_emolumento = bolsa(elementos)
                    elif "Líquido para" in texto:
                        nota_total_com_taxa = liquido(elementos)  # Liquido
        except StopIteration:
            if len(ativos) != contador:
                print(f"{len(ativos)=}, {contador=}")
                raise SystemError("len(ativos) != contador")
            dados_nota = montar_dados_nota(ativos, tipos, quantidades, precos, totais)
            dados_processados = montar_dados_processados(dados_nota)
            total_sem_taxa = sum(
                processado["total_sem_taxa"]
                for processado in dados_processados.values()
            )
            if not almost_equal(
                total_sem_taxa, nota_total_sem_taxa  # type:ignore[arg-type]
            ):
                raise SystemError("total_sem_taxa != nota_total_sem_taxa")
            total_taxa = taxa_liquidacao + taxa_emolumento
            total_com_taxa = total_sem_taxa + total_taxa
            if not almost_equal(total_com_taxa, nota_total_com_taxa):
                print(f"{total_com_taxa=}, {nota_total_com_taxa=}")
                raise SystemError("total_com_taxa != nota_total_com_taxa")
            soma_final = dec.Decimal(0)
            for valores_processados in dados_processados.values():
                porcentagem = valores_processados["total_sem_taxa"] / total_sem_taxa
                taxa_ativo_total = porcentagem * total_taxa
                taxa_ativo_unitario = (
                    taxa_ativo_total / valores_processados["quantidade"]
                )
                valores_processados["taxa_unitaria"] = taxa_ativo_unitario
                valores_processados["taxa_total"] = taxa_ativo_total
                valores_processados["preco_com_taxa"] = (
                    valores_processados["preco_sem_taxa"] + taxa_ativo_unitario
                )
                valores_processados["total_com_taxa"] = (
                    valores_processados["total_sem_taxa"] + taxa_ativo_total
                )
                soma_parcial = (
                    valores_processados["quantidade"]
                    * valores_processados["preco_com_taxa"]
                )
                if not almost_equal(
                    soma_parcial, valores_processados["total_com_taxa"]
                ):
                    print(f"{soma_parcial=}, {valores_processados['total_com_taxa']=}")
                    raise SystemError(
                        "soma_parcial != valores_processados['total_com_taxa']"
                    )
                if almost_equal(
                    taxa_ativo_unitario * valores_processados["quantidade"],
                    valores_processados["preco_sem_taxa"],
                ):
                    # TODO pra que serve isso?
                    print(
                        f"{taxa_ativo_unitario * valores_processados['quantidade']=}, "
                        f"{valores_processados['preco_sem_taxa']=}"
                    )
                    raise SystemError(
                        "taxa_ativo_unitario * valores_processados['quantidade'] "
                        "== valores_processados['preco_sem_taxa']"
                    )
                soma_final += soma_parcial

            soma_taxa_por_ativo = sum(
                taxa_processados["taxa_total"]
                for taxa_processados in dados_processados.values()
            )
            if not almost_equal(
                soma_taxa_por_ativo, total_taxa  # type:ignore[arg-type]
            ):
                print(f"{soma_taxa_por_ativo=}, {total_taxa=}")
                raise SystemError("soma_taxa_por_ativo != total_taxa")

        _assert_data_found(
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

        for nome, dados in dados_processados.items():
            planilha.append(
                LinhaPlanilha(
                    data=data_nota,
                    ativo=nome,
                    tipo=dados["tipo"],  # type:ignore[typeddict-item]
                    local="Brasil",
                    corretora="Nu",
                    quantidade=dados["quantidade"],
                    taxa_ativo=dec.Decimal(0),
                    quantidade_final=dados["quantidade"],
                    preco=dados["preco_sem_taxa"],
                    taxa_unitaria=dados["taxa_unitaria"],
                    preco_medio=dados["preco_com_taxa"],
                    preco_total=dados["total_sem_taxa"],
                    taxa_total=dados["taxa_total"],
                    total_investido=dados["total_com_taxa"],
                    total_investido_em_real=dados["total_com_taxa"],
                )
            )
    return planilha
