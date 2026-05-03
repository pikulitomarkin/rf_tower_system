from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from services.excel_parser import (
    parse_excel,
    group_by_station,
    get_icon_config,
    build_placemark_description,
    REQUIRED_COLUMNS,
    OPERADORA_COLORS,
)


ANATEL_COLUMNS = [
    "Torre Estação", "Numero Estacao", "EnderecoEstacao", "SiglaUf",
    "DesignacaoEmissao", "Tecnologia", "FreqTxMHz", "FreqRxMHz",
    "Azimute", "GanhoAntena", "FrenteCostaAntena", "AnguloMeiaPotenciaAntena",
    "AnguloElevacao", "Polarizacao", "AlturaAntena", "CodEquipamentoTransmissor",
    "PotenciaTransmissorWatts", "Latitude", "Longitude",
]


def _make_excel(rows):
    df = pd.DataFrame(rows, columns=ANATEL_COLUMNS)
    fp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(fp.name, index=False, engine="openpyxl")
    fp.close()
    return fp.name


def _remove(path):
    if path and os.path.exists(path):
        os.unlink(path)


class TestParseExcel:
    def test_basic_parse(self):
        path = _make_excel([
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             220, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             300, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
        ])
        try:
            df = parse_excel(path)
            assert len(df) == 2
            assert list(df.columns) == ANATEL_COLUMNS
            assert float(df.iloc[0]["FreqTxMHz"]) == 2640.0
        finally:
            _remove(path)

    def test_correct_types(self):
        path = _make_excel([
            ["CLARO S.A.", 2083922, "Rua A", "SP", "X", "LTE", 2640.0, 2500.0,
             220, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
        ])
        try:
            df = parse_excel(path)
            assert isinstance(float(df.iloc[0]["FreqTxMHz"]), float)
            assert isinstance(float(df.iloc[0]["GanhoAntena"]), float)
            assert isinstance(float(df.iloc[0]["Latitude"]), float)
            assert isinstance(df.iloc[0]["Tecnologia"], str)
        finally:
            _remove(path)

    def test_coordinates_outside_brazil_removed(self):
        path = _make_excel([
            ["CLARO S.A.", 1001, "Rua A", "SP", "X", "LTE", 2100.0, 1900.0,
             0, 18.0, 25.0, 65.0, 2, "X", 35.0, "TX", 20.0, 40.0, -73.0],  # New York
            ["TIM S.A.", 2002, "Rua B", "SP", "X", "NR", 3500.0, 3500.0,
             90, 20.0, 25.0, 65.0, 0, "X", 50.0, "TX", 40.0, -23.55, -46.63],  # São Paulo
        ])
        try:
            df = parse_excel(path)
            assert len(df) == 1
            assert df.iloc[0]["Torre Estação"] == "TIM S.A."
        finally:
            _remove(path)


class TestGroupByStation:
    def test_groups_multi_sector_station(self):
        path = _make_excel([
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             220, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             300, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             60, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
        ])
        try:
            df = parse_excel(path)
            stations = group_by_station(df)
            assert "2083922" in stations
            st = stations["2083922"]
            assert len(st["sectors"]) == 3
            assert st["info"]["Torre Estação"] == "CLARO S.A."
            assert st["info"]["Latitude"] == pytest.approx(-15.91993)
        finally:
            _remove(path)

    def test_groups_multiple_stations(self):
        path = _make_excel([
            ["CLARO S.A.", 1001, "Rua A", "SP", "X", "LTE", 2100.0, 1900.0,
             0, 18.0, 25.0, 65.0, 2, "X", 35.0, "TX", 20.0, -23.55, -46.63],
            ["TIM S.A.", 2002, "Rua B", "SP", "X", "NR", 3500.0, 3500.0,
             90, 20.0, 25.0, 65.0, 0, "X", 50.0, "TX", 40.0, -23.58, -46.67],
        ])
        try:
            df = parse_excel(path)
            stations = group_by_station(df)
            assert len(stations) == 2
            assert "1001" in stations
            assert "2002" in stations
        finally:
            _remove(path)


class TestGetIconConfig:
    def test_claro_is_red(self):
        config = get_icon_config("CLARO S.A.", "LTE")
        assert config["icon_color"] == "#CC0000"
        assert config["icon_name"] == "icon_lte"

    def test_telefonica_is_blue(self):
        config = get_icon_config("TELEFONICA BRASIL S.A.", "GSM")
        assert config["icon_color"] == "#0000CC"
        assert config["icon_name"] == "icon_gsm"

    def test_vivo_maps_to_telefonica_blue(self):
        config = get_icon_config("VIVO S.A.", "NR")
        assert config["icon_color"] == "#0000CC"

    def test_tim_is_yellow(self):
        config = get_icon_config("TIM S.A.", "LTE")
        assert config["icon_color"] == "#CCCC00"

    def test_oi_is_orange(self):
        config = get_icon_config("OI S.A.", "WCDMA")
        assert config["icon_color"] == "#FF6600"

    def test_unknown_operator_is_grey(self):
        config = get_icon_config("EMPRESA XYZ", "LTE")
        assert config["icon_color"] == "#666666"


class TestBuildPlacemarkDescription:
    def test_returns_html_string(self):
        path = _make_excel([
            ["CLARO S.A.", 2083922, "Rua A, 100", "SP", "5M00G7W", "LTE", 2640.0, 2500.0,
             220, 17.9, 25.0, 65.0, 2, "X", 40.0, "TX-001", 40.0, -15.91993, -47.96529],
        ])
        try:
            df = parse_excel(path)
            row = df.iloc[0]
            desc = build_placemark_description(row)
            assert isinstance(desc, str)
            assert "<b>Estação:</b>" in desc
            assert "2083922" in desc
            assert "CLARO" in desc
            assert "2640" in desc
        finally:
            _remove(path)
