import datetime as dt
import decimal as dec
import pathlib
from typing import Iterator, Sequence

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal

from pynotas.models import LinhaPlanilha, Sheet, TickerType
from pynotas.parser import _dec2str, get_next, get_next_text, get_text

stock = TickerType.stock
etf = TickerType.etf
reit = TickerType.reit

TICKER2TYPE = {
    "AMD": stock,
    "ARKX": etf,
    "NFLX": stock,
    "TSLA": stock,
    "ARKK": etf,
    "DOC": reit,
    "ACC": reit,
    "DIS": stock,
    "UPWK": stock,
    "QYLD": etf,
    "AMZN": stock,
    "T": stock,
    "EQIX": reit,
    "MA": stock,
    "IAU": etf,
    "BND": etf,
    "VXUS": etf,
    "VTI": etf,
    "BNDX": etf,
    "PG": stock,
    "GOOGL": stock,
    "IRM": reit,
    "PLD": reit,
    "WPC": reit,
    "NVDA": stock,
}


def get_next_decimal(gnd_elements: Iterator["LTTextBoxHorizontal"]) -> dec.Decimal:
    while True:
        gnd_text = get_next_text(gnd_elements)
        try:
            return dec.Decimal(gnd_text.replace(",", "").replace("$", ""))
        except dec.InvalidOperation:
            continue


def get_next_date(gnd_elements: Iterator["LTTextBoxHorizontal"], v2_flag: bool = True) -> dt.date:
    while True:
        gnd_text = get_next_text(gnd_elements)
        try:
            gnd_month, gnd_day, gnd_year = map(int, gnd_text.split("/"))
        except dec.InvalidOperation:
            continue
        else:
            if v2_flag:
                gnd_year += 2000
            return dt.date(gnd_year, gnd_month, gnd_day)


def get_b_s(fbs_elements: Iterator["LTTextBoxHorizontal"]) -> str:
    while True:
        fbs_text = get_next_text(fbs_elements).replace("Buy", "B").replace("Sell", "S")
        if fbs_text in ("B", "S"):
            return fbs_text


def get_ticker(gt_elements: Iterator["LTTextBoxHorizontal"]) -> str:
    while True:
        gt_text = get_next_text(gt_elements)
        if gt_text == "SYM" or " " in gt_text or ":" in gt_text:
            continue
        return gt_text


def get_data(gd_elements: Iterator["LTTextBoxHorizontal"], gd_flag: bool = False) -> tuple[
    dt.date,
    list[str],
    list[dec.Decimal],
    list[str],
    list[dec.Decimal],
    list[dec.Decimal],
]:
    gd_date = dt.date(1970, 1, 1)
    gd_actions: list[str] = []
    gd_quantities: list[dec.Decimal] = []
    gd_tickers: list[str] = []
    gd_prices: list[dec.Decimal] = []
    gd_totals: list[dec.Decimal] = []
    while True:
        try:
            gd_actions.append(get_b_s(gd_elements))
        except AttributeError:
            return gd_date, gd_actions, gd_quantities, gd_tickers, gd_prices, gd_totals
        if gd_flag:
            gd_date = get_next_date(gd_elements)
            gd_flag = False
        gd_quantities.append(get_next_decimal(gd_elements))
        gd_tickers.append(get_ticker(gd_elements))
        gd_prices.append(get_next_decimal(gd_elements))
        gd_totals.append(get_next_decimal(gd_elements))


def go2(g2_elements: Iterator["LTTextBoxHorizontal"], g2_value: str) -> None:
    while True:
        g2_text = get_next_text(g2_elements)
        if g2_text == g2_value:
            break


def get_data_v1(
    gdv1_elements: Iterator["LTTextBoxHorizontal"],
) -> tuple[
    int,
    list[str],
    list[str],
    list[dec.Decimal],
    list[dec.Decimal],
    list[dt.date],
    list[dec.Decimal],
]:
    gdv1_counter = 0
    gdv1_tickers: list[str] = []
    gdv1_actions: list[str] = []
    gdv1_quantities: list[dec.Decimal] = []
    gdv1_prices: list[dec.Decimal] = []
    gdv1_dates: list[dt.date] = []
    gdv1_totals: list[dec.Decimal] = []
    gdv1_flag = False
    while True:
        gdv1_text = get_next_text(gdv1_elements)

        if gdv1_text == "Capacity":
            gdv1_flag = True

        if gdv1_flag is True:
            gdv1_totals.append(get_next_decimal(gdv1_elements))
            get_next(gdv1_elements, 4)
            if len(gdv1_totals) == gdv1_counter:
                return (
                    gdv1_counter,
                    gdv1_tickers,
                    gdv1_actions,
                    gdv1_quantities,
                    gdv1_prices,
                    gdv1_dates,
                    gdv1_totals,
                )
        else:
            gdv1_tickers.append(gdv1_text)
            gdv1_actions.append(get_b_s(gdv1_elements))
            gdv1_quantities.append(get_next_decimal(gdv1_elements))
            gdv1_prices.append(get_next_decimal(gdv1_elements))
            gdv1_dates.append(get_next_date(gdv1_elements, v2_flag=False))
            gdv1_counter += 1
            go2(gdv1_elements, "Net Amount")


def get_types(gt_tickers: list[str]) -> list[TickerType]:
    gt_types = []
    for gt_ticker in gt_tickers:
        gt_types.append(TICKER2TYPE[gt_ticker])
    return gt_types


def _assert_list(
    al_data: list[str] | list[dec.Decimal] | list[TickerType],
    al_name: str,
    al_size: int,
) -> None:
    if len(al_data) == 0:
        msg = f"no {al_name} in PDF?"
        raise SystemError(msg)
    elif len(al_data) != al_size:
        msg = f"missing {al_name} in PDF...\nExpected {al_size}, got {len(al_data)}"
        raise SystemError(msg)


def assert_data_found(sheet: "Sheet") -> None:
    if sheet.date == dt.date(1970, 1, 1):
        msg = "no date in PDF?"
        raise SystemError(msg)
    for adf_data, adf_name in (
        (sheet.actions, "actions"),
        (sheet.tickers, "tickers"),
        (sheet.types, "types"),
        (sheet.quantities, "quantities"),
        (sheet.prices, "prices"),
        (sheet.totals, "totals"),
    ):
        _assert_list(adf_data, adf_name, sheet.counter)  # type: ignore[arg-type]


def build_sheet(sheet: "Sheet") -> list[LinhaPlanilha]:
    bs_list = []
    zero = "0"
    for bs_action, bs_ticker, bs_type, bs_quantity, bs_price, bs_total in zip(
        sheet.actions, sheet.tickers, sheet.types, sheet.quantities, sheet.prices, sheet.totals,
    ):
        if bs_action == "S":
            continue
        bs_list.append(
            LinhaPlanilha(
                data=f"{sheet.date:%d/%m/%Y}",
                ativo=bs_ticker,
                tipo=bs_type,
                local="Exterior",
                corretora="Avenue",
                quantidade=_dec2str(bs_quantity),
                taxa_ativo=zero,
                quantidade_final=_dec2str(bs_quantity),
                preco=_dec2str(bs_price),
                taxa_unitaria=zero,
                preco_medio=_dec2str(bs_price),
                preco_total=_dec2str(bs_total),
                taxa_total=zero,
                total_investido=_dec2str(bs_total),
            ),
        )
    return bs_list


def read_avenue(file_path: pathlib.Path) -> Sequence["LinhaPlanilha"]:  # noqa: C901, PLR0912, PLR0915

    counter = 0
    date = dt.date(1970, 1, 1)
    dates = []
    date_flag = True
    actions: list[str] = []
    tickers: list[str] = []
    types: list[TickerType] = []
    quantities: list[dec.Decimal] = []
    prices: list[dec.Decimal] = []
    totals: list[dec.Decimal] = []

    flag_v1, flag_v2 = False, False
    for page_layout in extract_pages(file_path):
        elements: Iterator["LTTextBoxHorizontal"] = iter(
            page_layout,  # type: ignore[arg-type]
        )
        try:
            while True:
                element = get_next(elements)
                if isinstance(element, LTTextBoxHorizontal):
                    text = get_text(element)
                    if (flag_v1 or flag_v2) is False:
                        if "Apex Clearing Corporation" in text:
                            flag_v2 = True
                            continue
                        elif "Confirmation Date  :  " in text:
                            flag_v1 = True
                    elif flag_v2:
                        if text == "B/S Trade Date Settle Date QTY":
                            (
                                temp_date,
                                temp_actions,
                                temp_quantities,
                                temp_tickers,
                                temp_prices,
                                temp_totals,
                            ) = get_data(elements, date_flag)
                            # TODO remove date_flag, read date of each line
                            if date_flag:
                                date = temp_date
                                date_flag = False
                            temp_types = get_types(temp_tickers)

                            counter += len(temp_actions)
                            actions += temp_actions
                            tickers += temp_tickers
                            types += temp_types
                            quantities += temp_quantities
                            prices += temp_prices
                            totals += temp_totals
                    else:
                        try:
                            (
                                temp_counter,
                                temp_tickers,
                                temp_actions,
                                temp_quantities,
                                temp_prices,
                                temp_dates,
                                temp_totals,
                            ) = get_data_v1(elements)

                            dates += temp_dates
                            temp_types = get_types(temp_tickers)

                            counter += len(temp_actions)
                            actions += temp_actions
                            tickers += temp_tickers
                            types += temp_types
                            quantities += temp_quantities
                            prices += temp_prices
                            totals += temp_totals
                        except AttributeError:
                            break
        except StopIteration:
            # TODO pegar total no fim do pdf e validar com o que foi lido
            continue

    if flag_v1:
        date = dates[0]
    sheet = Sheet(date, counter, actions, tickers, types, quantities, prices, totals)
    assert_data_found(sheet)
    return build_sheet(sheet)
