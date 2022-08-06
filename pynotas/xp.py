import datetime as dt
import decimal as dec
import pathlib
from typing import Iterator, Mapping, MutableMapping, Sequence

import pytz as tz
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal

from pynotas.parser import (
    _add2default,
    _dec_split,
    _dec_split_next,
    _lista_decimal,
    _next_lista_decimal,
)
from pynotas.utils import (
    SEPARADORES_XP,
    LinhaPlanilha,
    almost_equal,
    get_next,
    get_next_text,
    get_text,
)


def data_pregao(dp_elementos: Iterator["LTTextBoxHorizontal"]) -> dt.datetime:
    dp_texto = get_next_text(dp_elementos)
    ano, mes, dia = map(int, dp_texto.split("/")[::-1])
    return dt.datetime(ano, mes, dia, tzinfo=tz.utc)


def ativo(t_elementos: Iterator["LTTextBoxHorizontal"]) -> list[str]:
    t_texto = get_next_text(t_elementos)  # Titulo
    if t_texto == "Valor Operação / Ajuste":
        t_texto = get_next_text(t_elementos)
    t_nomes = t_texto.split("\n")
    t_ativos = []
    for t_nome in t_nomes:
        for t_separador, t_indice in SEPARADORES_XP:
            t_nome = t_nome.split(t_separador)[t_indice]
        t_ativos.append(t_nome)
    return t_ativos


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


def montar_dados_nota(
    mdn_ativos: list[str],
    mdn_quantidades: list[dec.Decimal],
    mdn_precos: list[dec.Decimal],
    mdn_totais: list[dec.Decimal],
) -> Mapping[str, Mapping[str, list[dec.Decimal]]]:
    mdn_dados_nota: MutableMapping[str, MutableMapping[str, list[dec.Decimal]]] = {}
    for mdn_indice_nota, mdn_nome_nota in enumerate(mdn_ativos):
        mdn_dic_nota = mdn_dados_nota.setdefault(mdn_nome_nota, {})
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


def read_xp(
    file_path: pathlib.Path,
) -> Sequence[LinhaPlanilha]:

    data_nota = dt.datetime(1970, 1, 1)
    contador = 0
    ativos: list[str] = []
    quantidades: list[dec.Decimal] = []
    precos: list[dec.Decimal] = []
    totais: list[dec.Decimal] = []
    taxa_liquidacao = dec.Decimal(-1)
    taxa_emolumento = dec.Decimal(-1)
    nota_total_sem_taxa = dec.Decimal(-1)
    nota_total_com_taxa = dec.Decimal(-1)
    planilha: list[LinhaPlanilha] = []

    for page_layout in extract_pages(file_path):
        try:
            elementos: Iterator["LTTextBoxHorizontal"] = iter(
                page_layout  # type: ignore[arg-type]
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
                        ativos = ativo(elementos)
                        quantidades = quantidade(elementos)  # Quantidade
                        precos = preco(elementos)  # Preco
                        totais = total(elementos)  # Total
                    elif (
                        "Taxa Operacional\nExecução\n"
                        "Taxa de Custódia\nImpostos\nI.R.R.F." in texto
                    ):
                        nota_total_sem_taxa, taxa_liquidacao = clearing(
                            elementos
                        )  # Clearing
                        taxa_emolumento = bolsa(elementos)  # Bolsa
                    elif "Total Custos / Despesas\nLíquido para " in texto:
                        nota_total_com_taxa = liquido(elementos)  # Liquido
        except StopIteration:
            if len(ativos) != contador:
                print(f"{len(ativos)=}, {contador=}")
                raise SystemError("len(ativos) != contador")
            dados_nota = montar_dados_nota(ativos, quantidades, precos, totais)
            dados_processados = montar_dados_processados(dados_nota)
            total_sem_taxa = sum(
                processado["total_sem_taxa"]
                for processado in dados_processados.values()
            )
            if total_sem_taxa != nota_total_sem_taxa:
                print(f"{total_sem_taxa=}, {nota_total_sem_taxa=}")
                raise SystemError("total_sem_taxa != nota_total_sem_taxa")
            total_taxa = taxa_liquidacao + taxa_emolumento
            total_com_taxa = total_sem_taxa + total_taxa
            if total_com_taxa != nota_total_com_taxa:
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
                if (
                    str(soma_parcial)[:-2]
                    != str(valores_processados["total_com_taxa"])[:-2]
                ):
                    # tira 2 casas de precisao pois estava dando erro
                    print(f"{soma_parcial=}, {valores_processados['total_com_taxa']=}")
                    raise SystemError(
                        "soma_parcial != valores_processados['total_com_taxa']"
                    )
                if (
                    taxa_ativo_unitario * valores_processados["quantidade"]
                    == valores_processados["preco_sem_taxa"]
                ):
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
                    tipo="FII",
                    local="Brasil",
                    corretora="XP",
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
