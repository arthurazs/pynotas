import csv
import os
import pathlib
from typing import Callable, Mapping, Sequence, TypedDict

from pynotas import read_avenue, read_nu, read_xp
from pynotas.utils import CABECALHO, assert1page
from pynotas.models import LinhaPlanilha

OptionsType = TypedDict(
    "OptionsType",
    {"path": pathlib.Path, "code": Callable[[pathlib.Path], Sequence[LinhaPlanilha]]},
)

BASE_PATH = pathlib.Path("data")
OPTIONS: Mapping[str, OptionsType] = {
    "xp": {"path": BASE_PATH / "xp", "code": read_xp},
    "nu": {"path": BASE_PATH / "nu", "code": read_nu},
    "avenue": {"path": BASE_PATH / "avenue", "code": read_avenue},
}


def cli() -> None:

    with (BASE_PATH / "all.csv").open("w") as all_file:
        csv_all = csv.DictWriter(all_file, CABECALHO, dialect="unix")
        csv_all.writeheader()

        for name, option in OPTIONS.items():

            path = option["path"]
            code = option["code"]

            print(f"\n{name} selecionado.")
            print("Lendo notas...")

            with (path.parent / (name + ".csv")).open("w") as csv_file:
                csv_writer = csv.DictWriter(csv_file, CABECALHO, dialect="unix")
                csv_writer.writeheader()
                for index, file_name in enumerate(sorted(os.listdir(path))):
                    if file_name == ".gitkeep":
                        continue
                    print(f"Lendo nota {index+1:02} {file_name}...", end=" ")
                    file_path = path / file_name

                    if name != "avenue":
                        assert1page(file_path)
                    linhas_planilha = code(file_path)
                    print(f"Salvando nota {index+1:02}...", end=" ")
                    for linha in linhas_planilha:
                        csv_writer.writerow(linha)
                        csv_all.writerow(linha)
                    print("Salvo!")
            print("Fim.")
