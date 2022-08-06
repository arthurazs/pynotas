import csv
import os
import pathlib
from typing import Callable, Mapping, Sequence, TypedDict

from pynotas.nu import read_nu
from pynotas.utils import CABECALHO, DECIMAL2STR, LinhaPlanilha, assert1page
from pynotas.xp import read_xp

OptionsType = TypedDict(
    "OptionsType",
    {"path": pathlib.Path, "code": Callable[[pathlib.Path], Sequence[LinhaPlanilha]]},
)

BASE_PATH = pathlib.Path("data")
OPTIONS: Mapping[str, OptionsType] = {
    "xp": {"path": BASE_PATH / "xp", "code": read_xp},
    "nu": {"path": BASE_PATH / "nu", "code": read_nu},
}


def run() -> None:

    for name, option in OPTIONS.items():

        path = option["path"]
        code = option["code"]

        print(f"\n{name} selecionado.")
        print("Lendo notas...")

        with open(path.parent / (name + ".csv"), "w") as csv_file:
            csv_writer = csv.DictWriter(csv_file, CABECALHO, dialect="unix")
            csv_writer.writeheader()
            for index, file_name in enumerate(sorted(os.listdir(path))):
                if file_name == ".gitkeep":
                    continue
                print(f"Lendo nota {index+1:02} {file_name}...", end=" ")
                file_path = path / file_name

                assert1page(file_path)
                linhas_planilha = code(file_path)
                print(f"Salvando nota {index+1:02}...", end=" ")
                for linha in linhas_planilha:
                    linha["data"] = str(linha["data"])[:-6]
                    # TODO change `linha` from TypedDict to MutableMapping
                    for header in DECIMAL2STR:
                        linha[header] = str(  # type: ignore[literal-required]
                            linha.get(header)
                        ).replace(".", ",")
                    csv_writer.writerow(linha)
                print("Salvo!")
        print("Fim.")


if __name__ == "__main__":
    run()
