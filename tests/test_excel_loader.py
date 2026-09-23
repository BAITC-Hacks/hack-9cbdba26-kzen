"""Миниатюрные книги фиксируют реальные различия форматов двух поставщиков."""

from pathlib import Path

from openpyxl import Workbook

from app.infrastructure.storage.excel_loader import load_dataset


def _save(path: Path, rows: list[list], *, title: str = "Лист_1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def _common_files(root: Path, supplier_dir: str, code: str) -> Path:
    folder = root / supplier_dir
    _save(
        folder / "Динамика продаж_2025-2026.xlsx",
        [
            ["Дата", "Номер", "Документ", "Код", "Номенклатура", "Ед.", "Склад", "Количество"],
            ["01.01.2026 10:00:00", "INV-1", "", code, "Товар", "шт", "Алматы", 5],
            ["02.01.2026 10:00:00", "RET-1", "", code, "Товар", "шт", "Алматы", -1],
        ],
    )
    _save(folder / "Сезонность.xlsx", [["год", "янв"], [2026, 1]])
    return folder


def _build_iek(root: Path) -> None:
    folder = _common_files(root, "IEK", "IEK-1")
    _save(
        folder / "Ежемесячные продажи.xlsx",
        [
            ["Номенклатура", "Номенклатура.Код", "янв. 2024", "февр. 2024"],
            ["", "", "Количество", "Количество"],
            ["Кабель", "IEK-1", 10, 20],
        ],
    )
    _save(
        folder / "Ежемесячные остатки.xlsx",
        [
            ["Номенклатура", "Ед.", "Номенклатура.Код", "янв. 2024", "февр. 2024"],
            ["", "", "", "Количество", "Количество"],
            ["", "", "", "нач. остаток", "нач. остаток"],
            ["Кабель", "м", "IEK-1", None, 2],
        ],
    )
    _save(
        folder / "MOQ ИЭК.xlsx",
        [
            ["№", "Код 1с", "Артикул поставщика", "Наименование", "Мин. разр. к отгр."],
            [1, "IEK-1", "ART-I", "Кабель", 6],
        ],
    )
    _save(
        folder / "Путь ИЭК.xlsx",
        [
            [
                "Код 1с",
                "Артикул ИЭК",
                " Наименование",
                "ПП УТ-7848 от 7 сентября 2026\xa0г. (поступление до 01.10.2026)",
            ],
            ["IEK-1", "ART-I", "Кабель", 5],
        ],
    )


def _build_systeme(root: Path) -> None:
    folder = _common_files(root, "Systeme electric", "SE-1")
    _save(
        folder / "Ежемесячные продажи Systeme.xlsx",
        [
            ["Номенклатура", "Номенклатура.Код", "Артикул", "Кратность", "янв. 2024", "февр. 2024"],
            ["", "", "", "", "Количество", "Количество"],
            ["Розетка", "SE-1", "ART-S", 0, 3, 4],
        ],
    )
    _save(
        folder / "Ежемесячные остатки Systeme.xlsx",
        [
            ["№", "Номенклатура", "Номенклатура.Код", "Ед.изм", "янв. 2024", "февр. 2024"],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            [1, "Розетка", "SE-1", "шт", 12, 10],
        ],
    )
    _save(
        folder / "MOQ SystemElectric.xlsx",
        [
            ["№", "Номенклатура", "Номенклатура.Код", "Артикул", "Кратность"],
            [1, "Розетка", "SE-1", "ART-S", 4],
        ],
    )
    _save(
        folder / "Товар в пути_SystemElectric.xlsx",
        [
            ["", ""],
            [
                "№",
                "Артикул поставщика",
                "Код 1с",
                "Наименование",
                "Категория 2026",
                "Остаток",
                "Зарезервировано",
                "Свободный остаток",
                "СЭ в пути 24.09",
            ],
            [1, "ART-S", "SE-1", "Розетка", "A", 10, 3, 7, 4],
        ],
        title="TDSheet",
    )


def test_both_supplier_formats_are_normalized(tmp_path: Path):
    _build_iek(tmp_path)
    _build_systeme(tmp_path)

    loaded = load_dataset(tmp_path)
    iek = loaded.repository.get("IEK-1")
    systeme = loaded.repository.get("SE-1")

    assert iek is not None
    assert iek.unit == "м"
    assert iek.moq == 6
    assert iek.free_stock == 2
    assert iek.in_transit == 5
    assert len(iek.inbound) == 1
    assert iek.inbound[0].document == "УТ-7848"
    assert iek.inbound[0].eta.isoformat() == "2026-10-01"
    assert iek.inbound[0].quantity == 5
    assert iek.history[0].stockout

    assert systeme is not None
    assert systeme.moq == 4
    assert systeme.on_hand_stock == 10
    assert systeme.reserved_stock == 3
    assert systeme.free_stock == 7
    assert systeme.in_transit == 4
    assert systeme.inbound[0].eta is None
    assert loaded.report.metrics["normalized_skus"] == 2
