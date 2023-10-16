import csv
import logging
import os
import pathlib
import sys
from typing import Callable, Mapping, Sequence, TypedDict

from pynotas import read_avenue, read_nu, read_xp
from pynotas.models import LinhaPlanilha
from pynotas.utils import CABECALHO, assert1page

try:
    log_level = logging.INFO if sys.argv[1] == '-v' else logging.WARNING
except IndexError:
    log_level = logging.WARNING

logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

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

            logger.info("%s selecionado.", name)
            logger.info("Lendo notas...")

            with (path.parent / (name + ".csv")).open("w") as csv_file:
                csv_writer = csv.DictWriter(csv_file, CABECALHO, dialect="unix")
                csv_writer.writeheader()
                for index, file_name in enumerate(sorted(os.listdir(path))):
                    if file_name == ".gitkeep":
                        continue
                    logger.info("Lendo nota %02d %s...", index+1, file_name)
                    file_path = path / file_name

                    if name != "avenue":
                        assert1page(file_path)
                    linhas_planilha = code(file_path)
                    logger.info("Salvando nota %02d...", index+1)
                    for linha in linhas_planilha:
                        csv_writer.writerow(linha)
                        csv_all.writerow(linha)
                    logger.info("Salvo!")
            logger.info("Fim.")
