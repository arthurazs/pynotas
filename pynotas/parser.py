import datetime as dt
import decimal as dec
from typing import TYPE_CHECKING, Iterator, Mapping, MutableMapping, Sequence

import pytz as tz

if TYPE_CHECKING:
    from pdfminer.layout import LTTextBoxHorizontal

from pynotas.utils import (
    LinhaPlanilha,
    _assert_data_found,
    almost_equal,
    assert_almost_equal,
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
ProcessedDataType = Mapping[str, MutableMapping[str, dec.Decimal]]


def aprint(elements: Iterator["LTTextBoxHorizontal"]) -> None:
    print()
    while True:
        try:
            print(">>>", get_next_text(elements))
        except StopIteration:
            exit()
        except AttributeError:
            continue


def _add2default(
    gd_dict: MutableMapping[str, list[dec.Decimal]],
    gd_name: str,
    gd_value: dec.Decimal,
) -> None:
    gd_name_list = gd_dict.setdefault(gd_name, [])
    gd_name_list.append(gd_value)


def to_dt(t_text: str) -> dt.datetime:
    ano, mes, dia = map(int, t_text.split("/")[::-1])
    return dt.datetime(ano, mes, dia, tzinfo=tz.utc)


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
) -> ProcessedDataType:
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
            msg = "mdp_total_processado != sum(mdp_ativo_nota['total'])"
            raise SystemError(msg)
        mdp_dic_processado["preco_sem_taxa"] = (
            mdp_total_processado / mdp_dic_processado["quantidade"]
        )
        mdp_dic_processado["total_sem_taxa"] = mdp_total_processado
    return mdp_dados_processados


def pos_processamento(
    pp_dados_processados: ProcessedDataType,
    pp_total_sem_taxa: dec.Decimal,
    pp_total_taxa: dec.Decimal,
) -> None:
    pp_soma_final = dec.Decimal(0)
    for pp_valores_processados in pp_dados_processados.values():
        pp_porcentagem = pp_valores_processados["total_sem_taxa"] / pp_total_sem_taxa
        pp_taxa_ativo_total = pp_porcentagem * pp_total_taxa
        pp_taxa_ativo_unitario = (
            pp_taxa_ativo_total / pp_valores_processados["quantidade"]
        )
        pp_valores_processados["taxa_unitaria"] = pp_taxa_ativo_unitario
        pp_valores_processados["taxa_total"] = pp_taxa_ativo_total
        pp_valores_processados["preco_com_taxa"] = (
            pp_valores_processados["preco_sem_taxa"] + pp_taxa_ativo_unitario
        )
        pp_valores_processados["total_com_taxa"] = (
            pp_valores_processados["total_sem_taxa"] + pp_taxa_ativo_total
        )
        pp_soma_parcial = (
            pp_valores_processados["quantidade"]
            * pp_valores_processados["preco_com_taxa"]
        )
        assert_almost_equal(
            pp_soma_parcial, pp_valores_processados["total_com_taxa"], "parcial-taxa"
        )
        if almost_equal(
            pp_taxa_ativo_unitario * pp_valores_processados["quantidade"],
            pp_valores_processados["preco_sem_taxa"],
        ):
            # TODO pra que serve isso?
            print(
                f"{pp_taxa_ativo_unitario * pp_valores_processados['quantidade']=}, "
                f"{pp_valores_processados['preco_sem_taxa']=}"
            )
            msg = (
                "pp_taxa_ativo_unitario * pp_valores_processados['quantidade'] "
                "== pp_valores_processados['preco_sem_taxa']"
            )
            raise SystemError(msg)
        pp_soma_final += pp_soma_parcial


def processar_dados(
    pd_contador: int,
    pd_ativos: list[str],
    pd_tipos: list[str],
    pd_quantidades: list[dec.Decimal],
    pd_precos: list[dec.Decimal],
    pd_totais: list[dec.Decimal],
    pd_taxa_liquidacao: dec.Decimal,
    pd_taxa_emolumento: dec.Decimal,
    pd_nota_total_sem_taxa: dec.Decimal,
    pd_nota_total_com_taxa: dec.Decimal,
) -> ProcessedDataType:

    assert_almost_equal(len(pd_ativos), pd_contador, "contador")
    pd_dados_nota = montar_dados_nota(
        pd_ativos, pd_tipos, pd_quantidades, pd_precos, pd_totais
    )
    pd_dados_processados = montar_dados_processados(pd_dados_nota)
    pd_total_sem_taxa = sum(
        pd_processado["total_sem_taxa"]
        for pd_processado in pd_dados_processados.values()
    )
    assert_almost_equal(
        # type: ignore[type-var]
        pd_total_sem_taxa,
        pd_nota_total_sem_taxa,
        "nota-total",
    )
    pd_taxa_total = pd_taxa_liquidacao + pd_taxa_emolumento
    pd_total_com_taxa = pd_total_sem_taxa + pd_taxa_total
    assert_almost_equal(pd_total_com_taxa, pd_nota_total_com_taxa, "nota-total-taxa")
    pos_processamento(
        pd_dados_processados,
        pd_total_sem_taxa,  # type: ignore[arg-type]
        pd_taxa_total,
    )

    pd_soma_taxa_por_ativo = sum(
        pd_taxa_processados["taxa_total"]
        for pd_taxa_processados in pd_dados_processados.values()
    )
    assert_almost_equal(
        # type: ignore[type-var]
        pd_soma_taxa_por_ativo,
        pd_taxa_total,
        "taxa-total",
    )
    return pd_dados_processados


def _dec2str(value: dec.Decimal) -> str:
    return str(value).replace(",", "").replace(".", ",").strip("0")


def montar_planilha(
    mp_data_nota: dt.datetime,
    mp_contador: int,
    mp_ativos: list[str],
    mp_tipos: list[str],
    mp_quantidades: list[dec.Decimal],
    mp_precos: list[dec.Decimal],
    mp_totais: list[dec.Decimal],
    mp_taxa_liquidacao: dec.Decimal,
    mp_taxa_emolumento: dec.Decimal,
    mp_nota_total_sem_taxa: dec.Decimal,
    mp_nota_total_com_taxa: dec.Decimal,
    mp_dados_processados: ProcessedDataType,
    mp_planilha: list[LinhaPlanilha],
    mp_local: str,
) -> None:
    _assert_data_found(
        mp_data_nota,
        mp_contador,
        mp_ativos,
        mp_tipos,
        mp_quantidades,
        mp_precos,
        mp_totais,
        mp_taxa_liquidacao,
        mp_taxa_emolumento,
        mp_nota_total_sem_taxa,
        mp_nota_total_com_taxa,
    )

    for mp_nome, mp_dados in mp_dados_processados.items():
        mp_planilha.append(
            LinhaPlanilha(
                data=f"{mp_data_nota:%d/%m/%Y}",
                ativo=mp_nome,
                tipo=mp_dados["tipo"],  # type:ignore[typeddict-item]
                local="Brasil",
                corretora=mp_local,
                quantidade=_dec2str(mp_dados["quantidade"]),
                taxa_ativo="0",
                quantidade_final=_dec2str(mp_dados["quantidade"]),
                preco=_dec2str(mp_dados["preco_sem_taxa"]),
                taxa_unitaria=_dec2str(mp_dados["taxa_unitaria"]),
                preco_medio=_dec2str(mp_dados["preco_com_taxa"]),
                preco_total=_dec2str(mp_dados["total_sem_taxa"]),
                taxa_total=_dec2str(mp_dados["taxa_total"]),
                total_investido=_dec2str(mp_dados["total_com_taxa"]),
            )
        )
