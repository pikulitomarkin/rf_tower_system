from __future__ import annotations

import io
import logging
import math
import os
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import simplekml
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_EARTH_RADIUS_M = 6_371_000.0

OPERADORA_COLORS: Dict[str, str] = {
    "CLARO": "#CC0000",
    "TELEFONICA": "#0000CC",
    "VIVO": "#0000CC",
    "TIM": "#CCCC00",
    "OI": "#FF6600",
}

TECNOLOGIA_LETTERS: Dict[str, str] = {
    "GSM": "G",
    "WCDMA": "W",
    "LTE": "L",
    "NR": "N",
}

ICON_SCALE_BY_TECH: Dict[str, float] = {
    "GSM": 0.9,
    "WCDMA": 1.0,
    "LTE": 1.2,
    "NR": 1.2,
}

ARROW_COLORS_KML: Dict[str, str] = {
    "GSM": "ff00ff00",
    "LTE": "ff0080ff",
    "NR": "ff800080",
    "WCDMA": "ffff0000",
}


def _resolve_operadora(nome: Optional[str]) -> str:
    if not nome:
        return "OUTROS"
    upper = nome.strip().upper()
    for keyword in OPERADORA_COLORS:
        if keyword in upper:
            return keyword
    return "OUTROS"


def _resolve_operadora_color(nome: Optional[str]) -> str:
    key = _resolve_operadora(nome)
    return OPERADORA_COLORS.get(key, "#666666")


def _resolve_tecnologia(raw: Optional[str]) -> str:
    if not raw:
        return "GSM"
    upper = str(raw).strip().upper()
    if upper in TECNOLOGIA_LETTERS:
        return upper
    return "GSM"


def _make_style_id(operadora: str, tecnologia: str) -> str:
    safe_op = operadora.replace(" ", "_").replace(".", "")
    return f"{safe_op}_{tecnologia}"


def _make_icon_filename(operadora: str, tecnologia: str) -> str:
    safe_op = operadora.replace(" ", "_").replace(".", "").lower()
    return f"icon_{safe_op}_{tecnologia.lower()}.png"


# ---------------------------------------------------------------------------
# 4 FUNÇÕES PRINCIPAIS
# ---------------------------------------------------------------------------


def create_colored_icon_png(color_hex: str, letter: str, size: int = 64) -> bytes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color_hex,
        outline="white",
        width=2,
    )

    text = letter[:1].upper()
    bbox = draw.textbbox((0, 0), text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 1
    draw.text((x, y), text, fill="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def calculate_endpoint(
    lat: float, lon: float, azimuth_deg: float, distance_m: float
) -> Tuple[float, float]:
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    az_rad = math.radians(azimuth_deg)
    angular_dist = distance_m / _EARTH_RADIUS_M

    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_dist)
        + math.cos(lat_rad) * math.sin(angular_dist) * math.cos(az_rad)
    )
    lon2_rad = lon_rad + math.atan2(
        math.sin(az_rad) * math.sin(angular_dist) * math.cos(lat_rad),
        math.cos(angular_dist) - math.sin(lat_rad) * math.sin(lat2_rad),
    )

    return (math.degrees(lat2_rad), math.degrees(lon2_rad))


def add_sector_arrows(
    folder: simplekml.Folder,
    station_id: str,
    sectors: List[Dict[str, Any]],
    base_lat: float,
    base_lon: float,
) -> None:
    arrow_distance_m = 300.0

    for i, sec in enumerate(sectors):
        az = sec.get("Azimute")
        if az is None or (isinstance(az, float) and math.isnan(az)):
            continue
        try:
            az_deg = float(az)
        except (ValueError, TypeError):
            continue

        end_lat, end_lon = calculate_endpoint(base_lat, base_lon, az_deg, arrow_distance_m)

        tech = _resolve_tecnologia(str(sec.get("Tecnologia", "")))
        line_color = ARROW_COLORS_KML.get(tech, "ffffffff")

        ls = folder.newlinestring(
            name=f"{station_id} - Setor {i + 1} ({az_deg:.0f}°)",
            coords=[(base_lon, base_lat), (end_lon, end_lat)],
        )
        ls.style.linestyle.color = line_color
        ls.style.linestyle.width = 2
        ls.altitudemode = simplekml.AltitudeMode.clamptoground
        ls.style.linestyle.color = line_color


def _build_description_html(
    station_id: str,
    endereco: str,
    operadora: str,
    sectors: List[Dict[str, Any]],
) -> str:
    rows_html: List[str] = []
    for sec in sectors:
        def _v(key: str, fmt: Optional[str] = None) -> str:
            val = sec.get(key)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return "N/D"
            try:
                if fmt:
                    return fmt.format(float(val))
                if isinstance(val, float):
                    return f"{val:.2f}"
                return str(val)
            except (ValueError, TypeError):
                return str(val)

        tech = str(sec.get("Tecnologia", "N/D"))
        rows_html.append(
            f"<tr>"
            f"<td>{tech}</td>"
            f"<td>{_v('FreqTxMHz', '{:.3f}')}</td>"
            f"<td>{_v('FreqRxMHz', '{:.3f}')}</td>"
            f"<td>{_v('Azimute')}</td>"
            f"<td>{_v('GanhoAntena', '{:.2f}')}</td>"
            f"<td>{_v('AlturaAntena', '{:.1f}')}</td>"
            f"<td>{_v('PotenciaTransmissorWatts', '{:.2f}')}</td>"
            f"<td>{_v('AnguloElevacao')}</td>"
            f"</tr>"
        )

    return (
        f'<![CDATA['
        f'<h3>#{station_id} &mdash; {endereco}</h3>'
        f'<p><b>Operadora:</b> {operadora}</p>'
        f'<table border="1" cellpadding="4" cellspacing="0" '
        f'style="border-collapse:collapse;font-size:12px;">'
        f'<tr style="background:#1a73e8;color:white;">'
        f'<th>Tecnologia</th><th>Freq Tx (MHz)</th><th>Freq Rx (MHz)</th>'
        f'<th>Azimute</th><th>Ganho (dBi)</th><th>Altura (m)</th>'
        f'<th>Potência (W)</th><th>Elevação</th>'
        f'</tr>'
        f'{"".join(rows_html)}'
        f'</table>'
        f']]>'
    )


def _normalize_kwargs(df: pd.DataFrame) -> pd.DataFrame:

    COLUMN_ALIASES: Dict[str, List[str]] = {
        "Torre Estação": ["operadora", "name", "Torre Estação"],
        "Numero Estacao": ["numero_estacao", "Numero Estacao"],
        "EnderecoEstacao": ["endereco", "EnderecoEstacao"],
        "SiglaUf": ["uf", "SiglaUf"],
        "DesignacaoEmissao": ["designacao_emissao", "DesignacaoEmissao"],
        "Tecnologia": ["technology", "Tecnologia"],
        "FreqTxMHz": ["freq_tx_mhz", "frequency_mhz", "FreqTxMHz"],
        "FreqRxMHz": ["freq_rx_mhz", "FreqRxMHz"],
        "Azimute": ["azimuth", "Azimute"],
        "GanhoAntena": ["antenna_gain_dbi", "GanhoAntena"],
        "FrenteCostaAntena": ["frente_costa_db", "FrenteCostaAntena"],
        "AnguloMeiaPotenciaAntena": ["beam_width_deg", "AnguloMeiaPotenciaAntena"],
        "AnguloElevacao": ["tilt", "AnguloElevacao"],
        "Polarizacao": ["polarizacao", "Polarizacao"],
        "AlturaAntena": ["tx_height_m", "AlturaAntena"],
        "CodEquipamentoTransmissor": ["cod_equipamento", "CodEquipamentoTransmissor"],
        "PotenciaTransmissorWatts": ["tx_power_watts", "PotenciaTransmissorWatts"],
        "Latitude": ["latitude", "lat", "Latitude"],
        "Longitude": ["longitude", "lon", "lon_gms", "Longitude"],
    }

    for target, aliases in COLUMN_ALIASES.items():
        if target in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                df[target] = df[alias]
                break

    return df


def generate_tower_kmz(
    data: Union[pd.DataFrame, List[Dict[str, Any]]],
    output_path: str,
    show_sectors: bool = False,
) -> str:
    if isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        raise TypeError(
            "data deve ser um pd.DataFrame ou uma lista de dicionários, "
            f"recebido {type(data).__name__}"
        )

    if df.empty:
        raise ValueError("Nenhum dado disponível para gerar o KMZ.")

    df = _normalize_kwargs(df)

    required = {"Numero Estacao", "Latitude", "Longitude", "Torre Estação", "EnderecoEstacao"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Colunas obrigatórias ausentes no DataFrame: {', '.join(sorted(missing))}"
        )

    temp_dir = tempfile.mkdtemp(prefix="kmz_")
    files_dir = os.path.join(temp_dir, "files")
    os.makedirs(files_dir, exist_ok=True)

    try:
        kml = simplekml.Kml(name="RF Tower System - ANATEL")

        generated_icons: set[str] = set()

        for station_id, group in df.groupby("Numero Estacao"):
            station_id_str = str(station_id)

            first = group.iloc[0]
            lat = float(first["Latitude"])
            lon = float(first["Longitude"])
            operadora_raw = str(first.get("Torre Estação", ""))
            endereco = str(first.get("EnderecoEstacao", ""))
            altura = float(first["AlturaAntena"]) if not pd.isna(first.get("AlturaAntena")) else 0.0

            operadora_key = _resolve_operadora(operadora_raw)
            operadora_color = _resolve_operadora_color(operadora_raw)

            sectors: List[Dict[str, Any]] = []
            for _, row in group.iterrows():
                sectors.append({
                    "Tecnologia": row.get("Tecnologia"),
                    "FreqTxMHz": row.get("FreqTxMHz"),
                    "FreqRxMHz": row.get("FreqRxMHz"),
                    "Azimute": row.get("Azimute"),
                    "GanhoAntena": row.get("GanhoAntena"),
                    "AlturaAntena": row.get("AlturaAntena"),
                    "PotenciaTransmissorWatts": row.get("PotenciaTransmissorWatts"),
                    "AnguloElevacao": row.get("AnguloElevacao"),
                    "FrenteCostaAntena": row.get("FrenteCostaAntena"),
                    "AnguloMeiaPotenciaAntena": row.get("AnguloMeiaPotenciaAntena"),
                    "Polarizacao": row.get("Polarizacao"),
                })

            technologies_in_tower: set[str] = set()
            for sec in sectors:
                tech = _resolve_tecnologia(str(sec.get("Tecnologia", "")))
                technologies_in_tower.add(tech)

            tech_primary = sorted(technologies_in_tower)[0] if technologies_in_tower else "GSM"

            icon_filename = _make_icon_filename(operadora_key, tech_primary)
            if icon_filename not in generated_icons:
                icon_png = create_colored_icon_png(
                    operadora_color,
                    TECNOLOGIA_LETTERS.get(tech_primary, "?"),
                )
                icon_path = os.path.join(files_dir, icon_filename)
                with open(icon_path, "wb") as fh:
                    fh.write(icon_png)
                generated_icons.add(icon_filename)

            op_folder: simplekml.Folder = _get_or_create_folder(kml, operadora_key)
            tech_folder: simplekml.Folder = _get_or_create_folder(op_folder, tech_primary)

            placemark_name = f"#{station_id_str} - {endereco}"
            pnt = tech_folder.newpoint(name=placemark_name, coords=[(lon, lat, altura)])
            pnt.style.iconstyle.icon.href = f"files/{icon_filename}"
            pnt.style.iconstyle.scale = ICON_SCALE_BY_TECH.get(tech_primary, 1.0)
            pnt.style.labelstyle.scale = 0.8
            pnt.description = _build_description_html(
                station_id_str, endereco, operadora_raw, sectors
            )
            pnt.altitudemode = simplekml.AltitudeMode.clamptoground

            if show_sectors and sectors:
                arrows_folder_name = f"Setores_{station_id_str}"
                arrows_folder: simplekml.Folder = tech_folder.newfolder(name=arrows_folder_name)
                add_sector_arrows(arrows_folder, station_id_str, sectors, lat, lon)

        kml_path = os.path.join(temp_dir, "doc.kml")
        kml.save(kml_path)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kmz.write(kml_path, "doc.kml")
            for fname in os.listdir(files_dir):
                fpath = os.path.join(files_dir, fname)
                kmz.write(fpath, f"files/{fname}")

        logger.info("KMZ gerado com sucesso: %s", output_path)
        return output_path

    except Exception:
        logger.exception("Falha ao gerar KMZ")
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _get_or_create_folder(parent, name: str) -> simplekml.Folder:
    candidate = getattr(parent, "folders", {})
    if callable(candidate):
        candidate = candidate()
    if isinstance(candidate, dict):
        for folder in candidate.values():
            if hasattr(folder, "name") and folder.name == name:
                return folder
    return parent.newfolder(name=name)
