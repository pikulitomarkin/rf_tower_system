from __future__ import annotations

import io
import logging
import math
import os
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import simplekml
from PIL import Image, ImageDraw, ImageFont

from services.kmz_generator import (
    OPERADORA_COLORS,
    TECNOLOGIA_LETTERS,
    create_colored_icon_png as _create_tower_icon,
    _resolve_operadora,
)

logger = logging.getLogger(__name__)

TECH_COLORS_RGB: Dict[str, str] = {
    "GSM": "#00CC00",
    "WCDMA": "#0055FF",
    "LTE": "#FF8800",
    "NR": "#8800FF",
}

TECH_COLORS_ABGR: Dict[str, str] = {
    "GSM": "ff00cc00",
    "WCDMA": "ffff5500",
    "LTE": "ff0088ff",
    "NR": "ffff0088",
}

FILL_ALPHA = 0x66
BORDER_ALPHA = 0xCC

SIGNAL_ZONES: List[Dict[str, Any]] = [
    {"label": "Excelente (> -75 dBm)", "threshold": -75.0, "color_rgb": "#00AA00", "color_abgr": "8800aa00"},
    {"label": "Bom (-85 a -75 dBm)",   "threshold": -85.0, "color_rgb": "#DDFF00", "color_abgr": "8800ffdd"},
    {"label": "Regular (-95 a -85 dBm)", "threshold": -95.0, "color_rgb": "#FFAA00", "color_abgr": "8800aaff"},
    {"label": "Fraco (> -105 dBm)",    "threshold": -105.0, "color_rgb": "#FF3333", "color_abgr": "663333ff"},
]

PATH_LOSS_EXPONENT = 35.0


def _hex_to_abgr(hex_color: str, alpha: int = 0xCC) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        r, g, b = "00", "00", "00"
    return f"{alpha:02x}{b}{g}{r}"


def _resolve_tech_color_abgr(technology: str) -> str:
    tech = str(technology).strip().upper()
    return TECH_COLORS_ABGR.get(tech, "ffffffff")


def _resolve_tech_color_rgb(technology: str) -> str:
    tech = str(technology).strip().upper()
    return TECH_COLORS_RGB.get(tech, "#CCCCCC")


# ---------------------------------------------------------------------------
# 4. export_to_kml_polygon
# ---------------------------------------------------------------------------


def export_to_kml_polygon(
    coords: List[Tuple[float, float]],
    name: str,
    description: str,
    color_abgr: str,
    fill: bool = True,
    altitude: float = 0.0,
    parent: Optional[simplekml.Folder] = None,
) -> simplekml.Polygon:
    """
    Cria um polígono KML com estilo customizado e opcionalmente adiciona
    a um folder pai.

    Converte coordenadas (lat, lon) para o formato KML (lon, lat, alt).
    Aplica cor de preenchimento semitransparente e borda sólida.

    Args:
        coords: Lista de tuplas (lat, lon) formando o anel externo.
        name: Nome do Placemark no KML.
        description: HTML/CData para o balloon.
        color_abgr: Cor no formato KML AABBGGRR (ex: "66ff8800" = laranja 40%).
        fill: Se True, preenche o polígono; se False, apenas contorno.
        altitude: Altitude (metros) para o modo clampToGround.
        parent: Folder KML onde adicionar o polígono. Se None, retorna solto.

    Returns:
        Objeto simplekml.Polygon.
    """
    kml_coords = [(lon, lat, altitude) for lat, lon in coords]

    if parent is not None:
        pol = parent.newpolygon(name=name)
    else:
        pol = simplekml.Polygon(name=name)

    pol.outerboundaryis = kml_coords
    pol.description = description
    pol.altitudemode = simplekml.AltitudeMode.clamptoground

    if fill:
        pol.style.polystyle.color = color_abgr
        pol.style.polystyle.fill = 1
        pol.style.polystyle.outline = 1
    else:
        pol.style.polystyle.color = simplekml.Color.changealphaint(0, color_abgr)
        pol.style.polystyle.fill = 0
        pol.style.polystyle.outline = 1

    pol.style.linestyle.color = color_abgr
    pol.style.linestyle.width = 1.5

    return pol


# ---------------------------------------------------------------------------
# 2. add_signal_strength_overlay
# ---------------------------------------------------------------------------


def _compute_zone_radius(
    radius_km: float,
    boundary_rx_dbm: float,
    target_rx_dbm: float,
) -> float:
    if target_rx_dbm >= boundary_rx_dbm:
        return radius_km
    delta_db = boundary_rx_dbm - target_rx_dbm
    ratio = 10.0 ** (-delta_db / PATH_LOSS_EXPONENT)
    zone_radius = radius_km * ratio
    return max(zone_radius, 0.01)


def add_signal_strength_overlay(
    parent_folder: simplekml.Folder,
    sector_data: Dict[str, Any],
    base_lat: float,
    base_lon: float,
) -> None:
    """
    Cria polígonos concêntricos representando níveis de sinal dentro do setor.

    Para um setor com raio de cobertura R e potência recebida Pr no limite:
    - Zona 1 (> -75 dBm): verde sólido
    - Zona 2 (-85 a -75 dBm): amarelo
    - Zona 3 (-95 a -85 dBm): laranja
    - Zona 4 (-105 a -95 dBm): vermelho

    Cada zona é um polígono com raio proporcional, usando o mesmo formato
    setorial (mesmo azimute e beamwidth) do setor original.

    Args:
        parent_folder: Folder KML onde adicionar os polígonos de zona.
        sector_data: Dados do setor (azimuth, beamwidth_deg, radius_km, etc.).
        base_lat: Latitude da estação base.
        base_lon: Longitude da estação base.
    """
    from services.rf_calculator import generate_coverage_polygon

    azimuth = float(sector_data.get("azimuth", sector_data.get("Azimute", 0)))
    beamwidth = float(sector_data.get("beamwidth_deg", 65.0))
    radius_km = float(sector_data.get("radius_km", 1.0))
    rx_dbm = float(sector_data.get("received_power_dbm", -95.0))

    station_id = sector_data.get("station_id", "")
    tech = str(sector_data.get("technology", "LTE")).upper()

    for zone in SIGNAL_ZONES:
        z_radius = _compute_zone_radius(radius_km, rx_dbm, zone["threshold"])
        if z_radius <= 0.01:
            continue

        poly_coords = generate_coverage_polygon(
            base_lat, base_lon, azimuth, beamwidth, z_radius, num_points=24
        )

        zone_name = f"Sinal {zone['label'].split('(')[0].strip()} | {tech}"
        zone_desc = (
            f"<![CDATA["
            f"<p><b>Zona de Sinal:</b> {zone['label']}</p>"
            f"<p><b>Raio:</b> {z_radius:.2f} km</p>"
            f"<p><b>Setor Az:</b> {azimuth:.0f}°</p>"
            f"]]>"
        )

        kml_poly = export_to_kml_polygon(
            coords=poly_coords,
            name=zone_name,
            description=zone_desc,
            color_abgr=zone["color_abgr"],
            fill=True,
            parent=parent_folder,
        )


# ---------------------------------------------------------------------------
# 3. create_legend_screen_overlay
# ---------------------------------------------------------------------------


def _build_legend_png() -> bytes:
    w, h = 280, 220
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, w - 1, h - 1], fill=(0, 0, 0, 180), outline=(255, 255, 255, 100))

    y = 16
    draw.text((12, y), "Legenda - Cobertura RF", fill="white")
    y += 26

    divider_y = y - 4
    draw.line([(8, divider_y), (w - 8, divider_y)], fill=(255, 255, 255, 80), width=1)

    tech_legend = [
        ("GSM", TECH_COLORS_RGB["GSM"], TECNOLOGIA_LETTERS.get("GSM", "G")),
        ("WCDMA", TECH_COLORS_RGB["WCDMA"], TECNOLOGIA_LETTERS.get("WCDMA", "W")),
        ("LTE", TECH_COLORS_RGB["LTE"], TECNOLOGIA_LETTERS.get("LTE", "L")),
        ("NR (5G)", TECH_COLORS_RGB["NR"], TECNOLOGIA_LETTERS.get("NR", "N")),
    ]

    for label, color, _ in tech_legend:
        color_rgb = tuple(int(color[i + 1 : i + 3], 16) for i in (0, 2, 4))
        draw.rectangle([12, y + 2, 32, y + 16], fill=color_rgb + (220,), outline="white")
        draw.text((40, y), label, fill="white")
        y += 22

    divider_y2 = y + 2
    draw.line([(8, divider_y2), (w - 8, divider_y2)], fill=(255, 255, 255, 80), width=1)
    y += 10

    draw.text((12, y), "Níveis de Sinal:", fill="white")
    y += 20

    signal_items = [
        ("Excelente (> -75 dBm)", "#00AA00"),
        ("Bom (-85 a -75)", "#DDFF00"),
        ("Regular (-95 a -85)", "#FFAA00"),
        ("Fraco (-105 a -95)", "#FF3333"),
    ]
    for label, color in signal_items:
        color_rgb = tuple(int(color[i + 1 : i + 3], 16) for i in (0, 2, 4))
        draw.rectangle([12, y + 2, 32, y + 16], fill=color_rgb + (200,), outline="white")
        draw.text((40, y), label, fill="white")
        y += 18

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_legend_screen_overlay(kml_doc: simplekml.Kml) -> None:
    """
    Adiciona um ScreenOverlay com a legenda das tecnologias e níveis de sinal.

    A legenda é gerada como PNG e embedada diretamente no KMZ.
    Posicionada no canto inferior esquerdo do Google Earth.

    Args:
        kml_doc: Documento KML raiz (simplekml.Kml) onde adicionar o overlay.
    """
    legend_png = _build_legend_png()

    screen = kml_doc.newscreenoverlay(name="Legenda de Cobertura RF")
    screen.icon.href = "files/legend_coverage.png"
    screen.overlayxy = simplekml.OverlayXY(x=0, y=1, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.screenxy = simplekml.ScreenXY(x=0.01, y=0.01, xunits=simplekml.Units.fraction, yunits=simplekml.Units.fraction)
    screen.size.x = 0
    screen.size.y = 0
    screen.size.xunits = simplekml.Units.fraction
    screen.size.yunits = simplekml.Units.fraction
    screen.visibility = 1

    return legend_png


# ---------------------------------------------------------------------------
# 1. generate_coverage_kmz
# ---------------------------------------------------------------------------


def generate_coverage_kmz(
    stations_coverage: List[Dict[str, Any]],
    output_path: str,
    show_labels: bool = True,
    show_signal_levels: bool = True,
    show_sector_arrows: bool = False,
) -> str:
    """
    Gera um arquivo KMZ com visualização da cobertura RF de estações no Google Earth.

    Estrutura do KML:
    - Folder "Torres": Placemarks das torres com ícones coloridos por operadora.
    - Folder "Cobertura RF":
        - Sub-pasta "GSM": polígonos verde claro semitransparentes
        - Sub-pasta "WCDMA": polígonos azul
        - Sub-pasta "LTE": polígonos laranja
        - Sub-pasta "NR": polígonos roxo
    - Folder "Zonas de Sinal" (opcional): camadas concêntricas de qualidade
    - ScreenOverlay: legenda no canto inferior esquerdo

    Args:
        stations_coverage: Lista de dicts com estrutura:
            {
                "station_id": str,
                "operadora": str,
                "endereco": str,
                "lat": float,
                "lon": float,
                "sectors": [
                    {
                        "azimuth": int,
                        "technology": str,
                        "freq_mhz": float,
                        "radius_km": float,
                        "beamwidth_deg": float,
                        "polygon_coords": [(lat, lon), ...],
                        "received_power_dbm": float,
                    }
                ]
            }
        output_path: Caminho completo para o arquivo KMZ de saída.
        show_labels: Exibe labels nos placemarks (padrão True).
        show_signal_levels: Adiciona zonas de sinal concêntricas (padrão True).
        show_sector_arrows: Adiciona setas de azimute (padrão False).

    Returns:
        Caminho do arquivo KMZ gerado.

    Exemplo:
        >>> stations = [{"station_id": "1001", "operadora": "CLARO S.A.",
        ...              "endereco": "Av. Paulista", "lat": -23.55, "lon": -46.63,
        ...              "sectors": [{"azimuth": 0, "technology": "LTE", "freq_mhz": 2100,
        ...                           "radius_km": 2.5, "polygon_coords": [...],
        ...                           "received_power_dbm": -75.0}]}]
        >>> path = generate_coverage_kmz(stations, "/tmp/cobertura.kmz")
    """
    if not stations_coverage:
        raise ValueError("stations_coverage está vazio ou é None")

    temp_dir = tempfile.mkdtemp(prefix="kmz_cov_")
    files_dir = os.path.join(temp_dir, "files")
    os.makedirs(files_dir, exist_ok=True)

    try:
        kml = simplekml.Kml(name="RF Coverage - Google Earth")

        legend_png_bytes = create_legend_screen_overlay(kml)
        legend_path = os.path.join(files_dir, "legend_coverage.png")
        with open(legend_path, "wb") as fh:
            fh.write(legend_png_bytes)

        towers_folder = kml.newfolder(name="Torres")
        coverage_folder = kml.newfolder(name="Cobertura RF")

        tech_folders: Dict[str, simplekml.Folder] = {}
        for tech in ["GSM", "WCDMA", "LTE", "NR"]:
            tech_folders[tech] = coverage_folder.newfolder(name=tech)

        signal_folder: Optional[simplekml.Folder] = None
        if show_signal_levels:
            signal_folder = kml.newfolder(name="Zonas de Sinal")

        generated_icons: set[str] = set()

        for station in stations_coverage:
            st_id = str(station.get("station_id", station.get("numero_estacao", "")))
            operadora = str(station.get("operadora", station.get("Torre Estação", "")))
            endereco = str(station.get("endereco", station.get("EnderecoEstacao", "")))
            lat = float(station.get("lat", station.get("latitude", 0)))
            lon = float(station.get("lon", station.get("longitude", 0)))
            altura = float(station.get("altura_antena", station.get("AlturaAntena", 0)))

            operadora_key = _resolve_operadora(operadora)
            color_hex = OPERADORA_COLORS.get(operadora_key, "#666666")
            icon_letter = "T"

            icon_filename = f"tower_{operadora_key.lower()}.png"
            if icon_filename not in generated_icons:
                icon_png = _create_tower_icon(color_hex, icon_letter)
                icon_path = os.path.join(files_dir, icon_filename)
                with open(icon_path, "wb") as fh:
                    fh.write(icon_png)
                generated_icons.add(icon_filename)

            pnt = towers_folder.newpoint(
                name=f"#{st_id} - {endereco[:40]}",
                coords=[(lon, lat, altura)],
            )
            pnt.style.iconstyle.icon.href = f"files/{icon_filename}"
            pnt.style.iconstyle.scale = 0.9
            pnt.style.labelstyle.scale = 0.8 if show_labels else 0.0
            pnt.altitudemode = simplekml.AltitudeMode.clamptoground
            pnt.description = (
                f"<![CDATA["
                f"<b>#{st_id} - {endereco}</b><br/>"
                f"<b>Operadora:</b> {operadora}<br/>"
                f"<b>Lat/Lon:</b> {lat:.6f}, {lon:.6f}<br/>"
                f"]]>"
            )

            sectors = station.get("sectors", [])
            for sec in sectors:
                tech = str(sec.get("technology", sec.get("Tecnologia", "LTE"))).upper()
                az = float(sec.get("azimuth", sec.get("Azimute", 0)))
                freq = float(sec.get("freq_mhz", sec.get("FreqTxMHz", 2100)))
                radius = float(sec.get("radius_km", 1.0))
                rx_dbm = float(sec.get("received_power_dbm", -95.0))
                beamwidth = float(sec.get("beamwidth_deg", 65.0))
                poly_coords = sec.get("polygon_coords", sec.get("polygon", []))

                if not poly_coords:
                    continue

                poly_name = (
                    f"#{st_id} | {tech} | {freq:.0f}MHz | "
                    f"Az:{az:.0f}° | R:{radius:.1f}km"
                )

                tx_power = sec.get("tx_power_watts", sec.get("PotenciaTransmissorWatts", "N/D"))
                ganho = sec.get("antenna_gain_dbi", sec.get("GanhoAntena", "N/D"))

                desc_parts = [
                    f"<b>Estação:</b> #{st_id}<br/>",
                    f"<b>Endereço:</b> {endereco}<br/>",
                    f"<b>Operadora:</b> {operadora}<br/>",
                    f"<b>Tecnologia:</b> {tech}<br/>",
                    f"<b>Frequência TX:</b> {freq:.3f} MHz<br/>",
                    f"<b>Azimute:</b> {az:.0f}°<br/>",
                    f"<b>Beamwidth:</b> {beamwidth:.1f}°<br/>",
                    f"<b>Raio de Cobertura:</b> {radius:.2f} km<br/>",
                    f"<b>Potência TX:</b> {tx_power} W<br/>",
                    f"<b>Ganho:</b> {ganho} dBi<br/>",
                    f"<b>Sinal recebido (borda):</b> {rx_dbm:.1f} dBm<br/>",
                ]
                poly_desc = f"<![CDATA[{' '.join(desc_parts)}]]>"

                color_abgr = _hex_to_abgr(
                    _resolve_tech_color_rgb(tech), alpha=FILL_ALPHA
                )

                tech_folder = tech_folders.get(tech)
                if tech_folder is None:
                    tech_folder = coverage_folder.newfolder(name=tech)
                    tech_folders[tech] = tech_folder

                export_to_kml_polygon(
                    coords=poly_coords,
                    name=poly_name,
                    description=poly_desc,
                    color_abgr=color_abgr,
                    fill=True,
                    altitude=50.0,
                    parent=tech_folder,
                )

                if show_signal_levels and signal_folder is not None:
                    sec_with_id = dict(sec)
                    sec_with_id["station_id"] = st_id
                    sec_with_id["azimuth"] = az
                    sec_with_id["beamwidth_deg"] = beamwidth
                    sec_with_id["radius_km"] = radius
                    sec_with_id["received_power_dbm"] = rx_dbm
                    sec_with_id["technology"] = tech

                    station_signal_folder = signal_folder.newfolder(
                        name=f"#{st_id} - {tech}"
                    )
                    add_signal_strength_overlay(
                        station_signal_folder, sec_with_id, lat, lon
                    )

                if show_sector_arrows:
                    from services.kmz_generator import calculate_endpoint

                    end_lat, end_lon = calculate_endpoint(lat, lon, az, 300.0)
                    ls = tech_folder.newlinestring(
                        name=f"#{st_id} Setor {az:.0f}°",
                        coords=[(lon, lat), (end_lon, end_lat)],
                    )
                    ls.style.linestyle.color = _hex_to_abgr(
                        _resolve_tech_color_rgb(tech), alpha=0xCC
                    )
                    ls.style.linestyle.width = 2

        kml_path = os.path.join(temp_dir, "doc.kml")
        kml.save(kml_path)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kmz.write(kml_path, "doc.kml")
            for fname in os.listdir(files_dir):
                fpath = os.path.join(files_dir, fname)
                kmz.write(fpath, f"files/{fname}")

        logger.info("KMZ de cobertura gerado: %s (%d estações)", output_path, len(stations_coverage))
        return output_path

    except Exception:
        logger.exception("Falha ao gerar KMZ de cobertura")
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
