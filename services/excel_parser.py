from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

REQUIRED_COLUMNS: List[str] = [
    "Torre Estação", "Numero Estacao", "EnderecoEstacao", "SiglaUf",
    "DesignacaoEmissao", "Tecnologia", "FreqTxMHz", "FreqRxMHz",
    "Azimute", "GanhoAntena", "FrenteCostaAntena", "AnguloMeiaPotenciaAntena",
    "AnguloElevacao", "Polarizacao", "AlturaAntena", "CodEquipamentoTransmissor",
    "PotenciaTransmissorWatts", "Latitude", "Longitude",
]

FLOAT_COLUMNS: List[str] = [
    "FreqTxMHz", "FreqRxMHz", "GanhoAntena", "FrenteCostaAntena",
    "AnguloMeiaPotenciaAntena", "AlturaAntena", "PotenciaTransmissorWatts",
    "Latitude", "Longitude",
]

INT_COLUMNS: List[str] = ["Azimute", "AnguloElevacao"]

STR_COLUMNS: List[str] = [
    "Torre Estação", "Numero Estacao", "EnderecoEstacao", "SiglaUf",
    "DesignacaoEmissao", "Tecnologia", "Polarizacao", "CodEquipamentoTransmissor",
]

OPERADORA_COLORS: Dict[str, str] = {
    "CLARO": "#CC0000",
    "TELEFONICA": "#0000CC",
    "VIVO": "#0000CC",
    "TIM": "#CCCC00",
    "OI": "#FF6600",
}

TECNOLOGIA_ICONS: Dict[str, str] = {
    "GSM": "icon_gsm",
    "WCDMA": "icon_wcdma",
    "LTE": "icon_lte",
    "NR": "icon_5g",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    raw_mapping: Dict[str, str] = {}
    normalized_cols: List[str] = []

    for col in df.columns:
        cleaned = str(col).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        raw_mapping[col] = cleaned
        normalized_cols.append(cleaned)

    df.columns = normalized_cols

    missing = [c for c in REQUIRED_COLUMNS if c not in normalized_cols]
    if missing:
        raise ValueError(
            f"Colunas obrigatórias não encontradas: {', '.join(missing)}. "
            f"Colunas detectadas: {', '.join(normalized_cols)}"
        )

    return df[REQUIRED_COLUMNS]


def _convert_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in INT_COLUMNS:
        if col in df.columns:
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            df[col] = numeric_series.astype("Int64")

    for col in STR_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "NaN": None, "None": None, "": None})

    return df


def _fill_rx_frequency(df: pd.DataFrame) -> pd.DataFrame:
    null_rx = df["FreqRxMHz"].isna()
    before = null_rx.sum()
    if before > 0:
        df.loc[null_rx, "FreqRxMHz"] = df.loc[null_rx, "FreqTxMHz"]
    return df


def _validate_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    lat_invalid = ~df["Latitude"].between(-35.0, 5.0)
    lon_invalid = ~df["Longitude"].between(-75.0, -30.0)

    lat_nan = df["Latitude"].isna()
    lon_nan = df["Longitude"].isna()

    invalid = lat_invalid | lon_invalid | lat_nan | lon_nan
    removed = invalid.sum()

    if removed > 0:
        df = df.loc[~invalid].copy()

    if df.empty:
        raise ValueError(
            "Nenhuma linha com coordenadas válidas para o Brasil "
            "(Lat: -35 a 5, Lon: -75 a -30)."
        )

    return df


def parse_excel(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    except Exception as exc:
        raise ValueError(f"Não foi possível ler o arquivo '{file_path}': {exc}")

    if df.empty:
        raise ValueError("A planilha está vazia (0 linhas de dados).")

    df = _normalize_columns(df)
    df = _convert_types(df)
    df = _fill_rx_frequency(df)
    df = _validate_coordinates(df)

    return df


def group_by_station(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}

    if "Numero Estacao" not in df.columns:
        raise KeyError("Coluna 'Numero Estacao' não encontrada no DataFrame.")

    sector_fields = [
        "Azimute",
        "Tecnologia",
        "FreqTxMHz",
        "GanhoAntena",
        "AlturaAntena",
        "PotenciaTransmissorWatts",
        "AnguloMeiaPotenciaAntena",
        "AnguloElevacao",
        "FrenteCostaAntena",
        "Polarizacao",
    ]

    station_fields = [
        "Torre Estação",
        "Numero Estacao",
        "EnderecoEstacao",
        "SiglaUf",
        "DesignacaoEmissao",
        "Latitude",
        "Longitude",
        "AlturaAntena",
        "CodEquipamentoTransmissor",
    ]

    stations: Dict[str, Any] = {}

    for station_id, group in df.groupby("Numero Estacao"):
        station_id_str = str(station_id)
        first = group.iloc[0]

        info: Dict[str, Any] = {}
        for field in station_fields:
            if field in group.columns:
                val = first[field]
                if isinstance(val, float) and pd.notna(val):
                    info[field] = float(val)
                elif isinstance(val, (pd.Int64Dtype, int)) and pd.notna(val):
                    info[field] = int(val)
                elif pd.isna(val):
                    info[field] = None
                else:
                    info[field] = str(val)

        sectors: List[Dict[str, Any]] = []
        for _, row in group.iterrows():
            sector: Dict[str, Any] = {}
            for field in sector_fields:
                if field in group.columns:
                    val = row[field]
                    if isinstance(val, float) and pd.notna(val):
                        sector[field] = float(val)
                    elif isinstance(val, (int, pd.Int64Dtype)) and pd.notna(val):
                        sector[field] = int(val)
                    elif pd.isna(val):
                        sector[field] = None
                    else:
                        sector[field] = str(val)
            sectors.append(sector)

        stations[station_id_str] = {"info": info, "sectors": sectors}

    return stations


def get_icon_config(operadora: str, tecnologia: str) -> Dict[str, Any]:
    operadora_upper = operadora.strip().upper() if operadora else ""
    tecnologia_upper = tecnologia.strip().upper() if tecnologia else ""

    color = "#666666"
    for keyword, hex_color in OPERADORA_COLORS.items():
        if keyword in operadora_upper:
            color = hex_color
            break

    scale = 1.0
    if "TIM" in operadora_upper:
        scale = 1.1
    elif "OI" in operadora_upper:
        scale = 0.95

    icon_name = TECNOLOGIA_ICONS.get(tecnologia_upper, "icon_gsm")

    return {"icon_color": color, "icon_name": icon_name, "scale": scale}


def build_placemark_description(row: pd.Series) -> str:
    def _val(key: str, fmt: Optional[str] = None) -> str:
        val = row.get(key)
        if pd.isna(val):
            return "N/D"
        if fmt:
            try:
                return fmt.format(float(val))
            except (ValueError, TypeError):
                pass
        return str(val)

    lines: List[str] = []
    lines.append(f"<b>Estação:</b> {_val('Torre Estação')}<br/>")
    lines.append(f"<b>Número:</b> {_val('Numero Estacao')}<br/>")
    lines.append(f"<b>Endereço:</b> {_val('EnderecoEstacao')}<br/>")
    lines.append(f"<b>UF:</b> {_val('SiglaUf')}<br/>")
    lines.append(f"<b>Designação de Emissão:</b> {_val('DesignacaoEmissao')}<br/>")
    lines.append(f"<b>Tecnologia:</b> {_val('Tecnologia')}<br/>")
    lines.append(f"<b>Freq. Tx:</b> {_val('FreqTxMHz', '{:.3f}')} MHz<br/>")
    lines.append(f"<b>Freq. Rx:</b> {_val('FreqRxMHz', '{:.3f}')} MHz<br/>")
    lines.append(f"<b>Azimute:</b> {_val('Azimute')}°<br/>")
    lines.append(f"<b>Ganho da Antena:</b> {_val('GanhoAntena', '{:.2f}')} dBi<br/>")
    lines.append(f"<b>Frente/Costas:</b> {_val('FrenteCostaAntena', '{:.2f}')} dB<br/>")
    lines.append(f"<b>Ângulo Meia Potência:</b> {_val('AnguloMeiaPotenciaAntena', '{:.1f}')}°<br/>")
    lines.append(f"<b>Ângulo de Elevação:</b> {_val('AnguloElevacao')}°<br/>")
    lines.append(f"<b>Polarização:</b> {_val('Polarizacao')}<br/>")
    lines.append(f"<b>Altura da Antena:</b> {_val('AlturaAntena', '{:.1f}')} m<br/>")
    lines.append(f"<b>Cód. Equipamento TX:</b> {_val('CodEquipamentoTransmissor')}<br/>")
    lines.append(f"<b>Potência TX:</b> {_val('PotenciaTransmissorWatts', '{:.2f}')} W<br/>")
    lines.append(f"<b>Coordenadas:</b> {_val('Latitude', '{:.6f}')}, {_val('Longitude', '{:.6f}')}<br/>")

    return "".join(lines)
