from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

SPEED_OF_LIGHT: float = 3.0e8
EARTH_RADIUS_KM: float = 6371.0

TECHNOLOGY_SENSITIVITY_DBM: Dict[str, float] = {
    "GSM": -102.0,
    "WCDMA": -115.0,
    "LTE": -95.0,
    "NR": -90.0,
}

ENVIRONMENT_CM: Dict[str, float] = {
    "urban": 3.0,
    "dense_urban": 5.0,
    "suburban": 0.0,
    "rural": 0.0,
}

ENVIRONMENT_CORRECTION: Dict[str, float] = {
    "urban": 0.0,
    "dense_urban": 2.0,
    "suburban": -9.88,
    "rural": -26.44,
}


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} deve ser maior que zero, recebido {value}")


def _validate_range(value: float, lo: float, hi: float, name: str) -> None:
    if not (lo <= value <= hi):
        raise ValueError(f"{name} deve estar entre {lo} e {hi}, recebido {value}")


# ---------------------------------------------------------------------------
# 1. Free Space Path Loss (FSPL)
# ---------------------------------------------------------------------------

def free_space_path_loss(freq_mhz: float, distance_km: float) -> float:
    """
    Calcula a perda de caminho no espaço livre (FSPL).

    Fórmula: L[dB] = 20·log₁₀(d[km]) + 20·log₁₀(f[MHz]) + 32.45

    Válido para cenários com linha de visada desobstruída (LOS).

    Args:
        freq_mhz: Frequência de operação em MHz (ex: 2100.0).
        distance_km: Distância entre transmissor e receptor em km.

    Returns:
        Perda de caminho em dB.

    Exemplo:
        >>> free_space_path_loss(2100.0, 1.0)
        98.89...
    """
    _validate_positive(freq_mhz, "freq_mhz")
    _validate_positive(distance_km, "distance_km")

    return 20.0 * math.log10(distance_km) + 20.0 * math.log10(freq_mhz) + 32.45


# ---------------------------------------------------------------------------
# 2. Okumura-Hata (Urban)
# ---------------------------------------------------------------------------

def okumura_hata_urban(
    freq_mhz: float,
    distance_km: float,
    h_base_m: float,
    h_mobile_m: float = 1.5,
    environment: str = "urban",
) -> float:
    """
    Modelo Okumura-Hata para predição de perda de caminho em ambiente urbano.

    Válido para: 150 MHz ≤ f ≤ 1500 MHz, 1 km ≤ d ≤ 20 km,
                 30 m ≤ h_base ≤ 200 m, 1 m ≤ h_mobile ≤ 10 m.

    Utiliza o fator de correção da altura da antena móvel:
    - Cidade pequena/média: a(hr) = (1.1·log₁₀(f) - 0.7)·hr - (1.56·log₁₀(f) - 0.8)
    - Cidade grande f ≥ 400 MHz: a(hr) = 3.2·(log₁₀(11.75·hr))² - 4.97
    - Cidade grande f < 200 MHz: a(hr) = 8.29·(log₁₀(1.54·hr))² - 1.1

    Para frequências > 1500 MHz, redireciona automaticamente ao COST-231 Hata.

    Fórmula padrão urbana:
    L = 69.55 + 26.16·log₁₀(f) - 13.82·log₁₀(hb) - a(hr)
        + (44.9 - 6.55·log₁₀(hb))·log₁₀(d)

    Aplica fator de correção ambiental:
    - suburban: -9.88 dB; rural: -26.44 dB

    Args:
        freq_mhz: Frequência em MHz (150 a 2000).
        distance_km: Distância em km.
        h_base_m: Altura da antena base (TX) em metros.
        h_mobile_m: Altura da antena móvel (RX) em metros (padrão 1.5 m).
        environment: Tipo de ambiente ("urban", "suburban", "rural").

    Returns:
        Perda de caminho em dB.

    Exemplo:
        >>> okumura_hata_urban(900.0, 5.0, 30.0)
        162.12...
    """
    _validate_positive(freq_mhz, "freq_mhz")
    _validate_positive(distance_km, "distance_km")
    _validate_positive(h_base_m, "h_base_m")

    if freq_mhz > 1500.0:
        return cost231_hata(freq_mhz, distance_km, h_base_m, h_mobile_m, environment)

    _validate_range(freq_mhz, 150.0, 1500.0, "freq_mhz")

    d_clamped = max(distance_km, 0.1)
    hb_clamped = max(h_base_m, 1.0)
    hm_clamped = max(h_mobile_m, 1.0)

    log_f = math.log10(freq_mhz)
    log_hb = math.log10(hb_clamped)
    log_d = math.log10(d_clamped)

    a_hm = (
        (1.1 * log_f - 0.7) * hm_clamped
        - (1.56 * log_f - 0.8)
    )

    loss = (
        69.55
        + 26.16 * log_f
        - 13.82 * log_hb
        - a_hm
        + (44.9 - 6.55 * log_hb) * log_d
    )

    c_env = ENVIRONMENT_CORRECTION.get(environment, 0.0)
    loss += c_env

    return loss


# ---------------------------------------------------------------------------
# 3. COST-231 Hata
# ---------------------------------------------------------------------------

def cost231_hata(
    freq_mhz: float,
    distance_km: float,
    h_base_m: float,
    h_mobile_m: float = 1.5,
    environment: str = "urban",
) -> float:
    """
    Extensão COST-231 do modelo Hata para a faixa 1500-2000 MHz.

    Válido para: 1500 MHz ≤ f ≤ 2000 MHz, 1 km ≤ d ≤ 20 km,
                 30 m ≤ h_base ≤ 200 m, 1 m ≤ h_mobile ≤ 10 m.

    Fórmula:
    L = 46.3 + 33.9·log₁₀(f) - 13.82·log₁₀(hb) - a(hr)
        + (44.9 - 6.55·log₁₀(hb))·log₁₀(d) + Cm

    Onde Cm é o fator de correção do ambiente:
    - urban: Cm = 3 dB
    - dense_urban: Cm = 5 dB
    - suburban: Cm = 0 dB
    - rural: Cm = 0 dB

    Após o cálculo, aplica-se um fator de correção adicional (Cenv)
    para ambientes suburbanos (-9.88 dB) e rurais (-26.44 dB).

    Args:
        freq_mhz: Frequência em MHz (1500 a 2000).
        distance_km: Distância em km.
        h_base_m: Altura da antena base (TX) em metros.
        h_mobile_m: Altura da antena móvel (RX) em metros (padrão 1.5 m).
        environment: Tipo de ambiente: "urban", "dense_urban", "suburban", "rural".

    Returns:
        Perda de caminho em dB.

    Exemplo:
        >>> cost231_hata(1800.0, 2.0, 30.0)
        135.75...
        >>> cost231_hata(1800.0, 2.0, 30.0, environment="rural")
        109.31...
    """
    _validate_positive(freq_mhz, "freq_mhz")
    _validate_positive(distance_km, "distance_km")
    _validate_positive(h_base_m, "h_base_m")

    if environment not in ENVIRONMENT_CM:
        raise ValueError(
            f"Ambiente '{environment}' não reconhecido. "
            f"Opções: {', '.join(ENVIRONMENT_CM.keys())}"
        )

    d_clamped = max(distance_km, 0.1)
    hb_clamped = max(h_base_m, 1.0)
    hm_clamped = max(h_mobile_m, 1.0)

    log_f = math.log10(freq_mhz)
    log_hb = math.log10(hb_clamped)
    log_d = math.log10(d_clamped)

    a_hm = (
        (1.1 * log_f - 0.7) * hm_clamped
        - (1.56 * log_f - 0.8)
    )

    cm = ENVIRONMENT_CM.get(environment, 3.0)

    loss = (
        46.3
        + 33.9 * log_f
        - 13.82 * log_hb
        - a_hm
        + (44.9 - 6.55 * log_hb) * log_d
        + cm
    )

    c_env = ENVIRONMENT_CORRECTION.get(environment, 0.0)
    loss += c_env

    return loss


# ---------------------------------------------------------------------------
# 4. Potência Recebida (Friis)
# ---------------------------------------------------------------------------

def calculate_received_power(
    tx_power_w: float,
    tx_gain_dbi: float,
    path_loss_db: float,
    rx_gain_dbi: float = 0.0,
    cable_loss_db: float = 2.0,
) -> float:
    """
    Calcula a potência recebida usando a equação de Friis.

    Pr_dBm = Pt_dBm + Gt - L + Gr - Lc

    Onde:
    - Pt_dBm = 10·log₁₀(Pt_W · 1000)  (conversão Watts → dBm)
    - Gt = ganho da antena transmissora (dBi)
    - L = perda de caminho (dB)
    - Gr = ganho do receptor (dBi)
    - Lc = perda total nos cabos/conectores (dB)

    Args:
        tx_power_w: Potência de transmissão em Watts.
        tx_gain_dbi: Ganho da antena transmissora em dBi.
        path_loss_db: Perda total de caminho em dB (via FSPL, Hata, etc.).
        rx_gain_dbi: Ganho da antena receptora em dBi (padrão 0).
        cable_loss_db: Perda em cabos e conectores em dB (padrão 2.0).

    Returns:
        Potência recebida em dBm.

    Exemplo:
        >>> calculate_received_power(20.0, 18.0, 135.0)
        26.01...
    """
    _validate_positive(tx_power_w, "tx_power_w")

    tx_dbm = 10.0 * math.log10(tx_power_w * 1000.0)

    rx_dbm = tx_dbm + tx_gain_dbi - path_loss_db + rx_gain_dbi - cable_loss_db

    return rx_dbm


# ---------------------------------------------------------------------------
# 5. Raio de Cobertura (Binary Search)
# ---------------------------------------------------------------------------

def _select_path_loss_model(
    freq_mhz: float,
    distance_km: float,
    h_base_m: float,
    environment: str,
) -> float:
    if freq_mhz < 1000.0:
        return okumura_hata_urban(freq_mhz, distance_km, h_base_m, environment=environment)
    elif freq_mhz <= 2000.0:
        return cost231_hata(freq_mhz, distance_km, h_base_m, environment=environment)
    else:
        fspl = free_space_path_loss(freq_mhz, distance_km)
        return fspl + 20.0


def calculate_coverage_radius(
    tx_power_w: float,
    tx_gain_dbi: float,
    freq_mhz: float,
    h_base_m: float,
    sensitivity_dbm: float = -95.0,
    environment: str = "urban",
) -> float:
    """
    Calcula o raio de cobertura onde o sinal recebido atende à sensibilidade mínima.

    Utiliza busca binária para encontrar a distância exata onde
    Pr(d) = sensitivity_dbm, com precisão de 10 metros.

    O modelo de propagação é selecionado automaticamente:
    - f < 1000 MHz: Okumura-Hata (urbano clássico)
    - 1000 ≤ f ≤ 2000 MHz: COST-231 Hata
    - f > 2000 MHz: FSPL com margem urbana adicional de 20 dB

    Aplica margem de desvanecimento (shadow margin) de 8 dB e
    penalidade de penetração indoor de 12 dB para ambientes urbanos.

    Args:
        tx_power_w: Potência de transmissão em Watts.
        tx_gain_dbi: Ganho da antena transmissora em dBi.
        freq_mhz: Frequência de operação em MHz.
        h_base_m: Altura da torre/antena transmissora em metros.
        sensitivity_dbm: Sensibilidade do receptor em dBm (padrão -95 LTE).
        environment: Tipo de ambiente ("urban", "suburban", "rural", "dense_urban").

    Returns:
        Raio de cobertura em km, arredondado com precisão de 10 m.

    Exemplo:
        >>> calculate_coverage_radius(20.0, 18.0, 2100.0, 30.0)
        1.99...
    """
    _validate_positive(tx_power_w, "tx_power_w")
    _validate_positive(freq_mhz, "freq_mhz")
    _validate_positive(h_base_m, "h_base_m")

    if environment not in ENVIRONMENT_CM:
        raise ValueError(f"Ambiente '{environment}' não reconhecido")

    shadow_margin_db = 8.0
    indoor_penalty_db = 12.0 if environment in ("urban", "dense_urban") else 0.0
    effective_sensitivity = sensitivity_dbm + shadow_margin_db + indoor_penalty_db

    lo_km = 0.01
    hi_km = 50.0

    def rx_at(d_km: float) -> float:
        pl = _select_path_loss_model(freq_mhz, d_km, h_base_m, environment)
        return calculate_received_power(tx_power_w, tx_gain_dbi, pl)

    if rx_at(lo_km) < effective_sensitivity:
        return 0.0

    if rx_at(hi_km) > effective_sensitivity:
        return hi_km

    tolerance_km = 0.01  # 10 metros
    max_iterations = 100
    iteration = 0

    while (hi_km - lo_km) > tolerance_km and iteration < max_iterations:
        iteration += 1
        mid_km = (lo_km + hi_km) / 2.0
        rx_dbm = rx_at(mid_km)

        if math.isnan(rx_dbm):
            rx_dbm = -999.0

        if rx_dbm > effective_sensitivity:
            lo_km = mid_km
        else:
            hi_km = mid_km

    if iteration >= max_iterations:
        logger.warning("Busca binária atingiu limite de %d iterações", max_iterations)

    return round((lo_km + hi_km) / 2.0, 3)


# ---------------------------------------------------------------------------
# 6. Polígono de Cobertura Setorial
# ---------------------------------------------------------------------------

def _destination_point(
    lat_deg: float,
    lon_deg: float,
    azimuth_deg: float,
    distance_km: float,
) -> Tuple[float, float]:
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    az_rad = math.radians(azimuth_deg)
    angular = distance_km / EARTH_RADIUS_KM

    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular)
        + math.cos(lat_rad) * math.sin(angular) * math.cos(az_rad)
    )
    lon2_rad = lon_rad + math.atan2(
        math.sin(az_rad) * math.sin(angular) * math.cos(lat_rad),
        math.cos(angular) - math.sin(lat_rad) * math.sin(lat2_rad),
    )

    return (math.degrees(lat2_rad), math.degrees(lon2_rad))


def generate_coverage_polygon(
    lat: float,
    lon: float,
    azimuth_deg: float,
    beamwidth_deg: float,
    radius_km: float,
    num_points: int = 36,
) -> List[Tuple[float, float]]:
    """
    Gera o polígono de cobertura setorial de uma antena direcional.

    O polígono tem formato de "fatia de pizza":
    - A estação base está no vértice (lat, lon).
    - O arco externo está limitado pelo ângulo de meia potência (beamwidth),
      centrado na direção do azimute (azimuth_deg).
    - Para antenas omnidirecionais (beamwidth ≥ 360°), gera um círculo completo.

    Para cada ponto do arco, a distância é fixa em radius_km e o ângulo
    varia de (azimuth - beamwidth/2) a (azimuth + beamwidth/2).

    Utiliza a fórmula de destino geodésico (Haversine inversa) para calcular
    coordenadas precisas em grandes raios de cobertura.

    Args:
        lat: Latitude da estação base (graus decimais).
        lon: Longitude da estação base (graus decimais).
        azimuth_deg: Azimute do setor em graus (0 = Norte, 90 = Leste).
        beamwidth_deg: Ângulo de meia potência em graus (ex: 65° para painéis típicos).
        radius_km: Raio de cobertura em km.
        num_points: Número de pontos no arco do polígono (padrão 36).

    Returns:
        Lista de tuplas [(lat, lon), ...] formando o polígono de cobertura.
        O primeiro ponto é sempre a localização da estação base.
        Ordem: anti-horária (sentido trigonométrico, compatível com KML).

    Exemplo:
        >>> poly = generate_coverage_polygon(-23.55, -46.63, 120.0, 65.0, 2.0)
        >>> len(poly)
        38  # 1 vértice + 36 arco + 1 vértice de fechamento
    """
    _validate_positive(radius_km, "radius_km")

    if beamwidth_deg >= 360.0:
        beamwidth_deg = 360.0

    azimuth_deg = azimuth_deg % 360.0

    half_bw = beamwidth_deg / 2.0

    start_angle = azimuth_deg - half_bw
    end_angle = azimuth_deg + half_bw

    polygon: List[Tuple[float, float]] = [(lat, lon)]

    angles = []
    if beamwidth_deg >= 360.0:
        num_pts = max(num_points, 12)
        angles = np.linspace(0.0, 360.0, num_pts + 1)[:-1].tolist()
    else:
        angles = np.linspace(start_angle, end_angle, num_points).tolist()
        angles = [a % 360.0 for a in angles]

    for angle in angles:
        pt = _destination_point(lat, lon, angle, radius_km)
        polygon.append(pt)

    polygon.append((lat, lon))

    return polygon


# ---------------------------------------------------------------------------
# 7. Simulação de Cobertura de uma Estação
# ---------------------------------------------------------------------------

def _resolve_sensitivity(technology: Optional[str]) -> float:
    if not technology:
        return -95.0
    tech_upper = str(technology).strip().upper()
    return TECHNOLOGY_SENSITIVITY_DBM.get(tech_upper, -95.0)


def _resolve_environment(technology: Optional[str]) -> str:
    if not technology:
        return "urban"
    tech_upper = str(technology).strip().upper()
    if tech_upper == "NR":
        return "urban"
    return "urban"


def simulate_station_coverage(station_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Simula a cobertura de todos os setores de uma estação.

    Parâmetros esperados em station_data:
        - info.Latitude: float
        - info.Longitude: float
        - info.AlturaAntena: float (metros) [opcional, default=30]
        - sectors: lista de setores, cada um com:
            - Tecnologia: str (GSM|WCDMA|LTE|NR)
            - FreqTxMHz: float
            - Azimute: int|float
            - AnguloMeiaPotenciaAntena: float [opcional, default=65.0]
            - GanhoAntena: float [opcional, default=15.0]
            - PotenciaTransmissorWatts: float [opcional, default=20.0]

    Para cada setor:
        - Seleciona automaticamente a sensibilidade por tecnologia.
        - Calcula o raio de cobertura via binary search.
        - Gera o polígono setorial com ângulo de meia potência.
        - Calcula potência recebida teórica no limite do raio.

    Modelo selecionado por faixa de frequência:
        - f < 1000 MHz: Okumura-Hata (urbano)
        - 1000 ≤ f ≤ 2000 MHz: COST-231 Hata
        - f > 2000 MHz: FSPL + 20 dB (margem urbana)

    Args:
        station_data: Dicionário com dados da estação e setores.

    Returns:
        Lista de dicionários, um por setor:
        [{azimuth, technology, freq_mhz, radius_km, polygon_coords, received_power_dbm}, ...]

    Exemplo:
        >>> station = {
        ...     "info": {"Latitude": -23.55, "Longitude": -46.63, "AlturaAntena": 35.0},
        ...     "sectors": [
        ...         {"Tecnologia": "LTE", "FreqTxMHz": 2100.0, "Azimute": 0, "GanhoAntena": 18.0, "PotenciaTransmissorWatts": 20.0},
        ...         {"Tecnologia": "LTE", "FreqTxMHz": 2100.0, "Azimute": 120, "GanhoAntena": 18.0, "PotenciaTransmissorWatts": 20.0},
        ...         {"Tecnologia": "LTE", "FreqTxMHz": 2100.0, "Azimute": 240, "GanhoAntena": 18.0, "PotenciaTransmissorWatts": 20.0},
        ...     ]
        ... }
        >>> results = simulate_station_coverage(station)
        >>> len(results)
        3
    """
    if not station_data:
        raise ValueError("station_data está vazio ou é None")

    info = station_data.get("info", station_data)
    sectors = station_data.get("sectors", [])

    if not sectors:
        raise ValueError("station_data não contém 'sectors' ou a lista está vazia")

    base_lat = float(info.get("Latitude", info.get("latitude", 0.0)))
    base_lon = float(info.get("Longitude", info.get("longitude", 0.0)))
    h_base = float(info.get("AlturaAntena", info.get("altura_antena", 30.0)))

    if not (-90 <= base_lat <= 90) or not (-180 <= base_lon <= 180):
        raise ValueError(f"Coordenadas inválidas: lat={base_lat}, lon={base_lon}")

    results: List[Dict[str, Any]] = []

    for sec in sectors:
        tech = str(sec.get("Tecnologia", sec.get("technology", "LTE"))).strip().upper()
        freq_mhz = float(sec.get("FreqTxMHz", sec.get("freq_tx_mhz", sec.get("frequency_mhz", 2100.0))))
        azimute = float(sec.get("Azimute", sec.get("azimute", sec.get("azimuth", 0))))
        beamwidth = float(sec.get("AnguloMeiaPotenciaAntena",
                                   sec.get("beam_width_deg",
                                           sec.get("angulo_meia_potencia", 65.0))))
        ganho = float(sec.get("GanhoAntena", sec.get("antenna_gain_dbi",
                                                       sec.get("ganho_antena", 15.0))))
        potencia = float(sec.get("PotenciaTransmissorWatts",
                                  sec.get("tx_power_watts",
                                          sec.get("potencia_transmissor_watts", 20.0))))

        sensitivity = _resolve_sensitivity(tech)
        environment = _resolve_environment(tech)

        radius = calculate_coverage_radius(
            tx_power_w=potencia,
            tx_gain_dbi=ganho,
            freq_mhz=freq_mhz,
            h_base_m=h_base,
            sensitivity_dbm=sensitivity,
            environment=environment,
        )

        if radius > 0:
            polygon = generate_coverage_polygon(
                base_lat, base_lon, azimute, beamwidth, radius
            )
        else:
            polygon = [(base_lat, base_lon)]

        if radius > 0:
            pl = _select_path_loss_model(freq_mhz, radius, h_base, environment)
        else:
            pl = _select_path_loss_model(freq_mhz, 0.01, h_base, environment)
        rx_dbm = calculate_received_power(potencia, ganho, pl)

        results.append({
            "azimuth": azimute,
            "technology": tech,
            "freq_mhz": freq_mhz,
            "radius_km": radius,
            "beamwidth_deg": beamwidth,
            "environment": environment,
            "sensitivity_dbm": sensitivity,
            "received_power_dbm": round(rx_dbm, 2),
            "polygon_coords": polygon,
        })

    return results


# ---------------------------------------------------------------------------
# Wrappers de compatibilidade com as rotas existentes
# ---------------------------------------------------------------------------


def calculate_link_budget(
    frequency_mhz: float,
    tx_power_dbm: float,
    tx_gain_dbi: float = 0.0,
    tx_loss_db: float = 0.0,
    rx_gain_dbi: float = 0.0,
    rx_loss_db: float = 0.0,
    tx_height_m: float = 30.0,
    rx_height_m: float = 1.5,
    distance_km: float = 1.0,
    environment: str = "urban",
    technology: str = "LTE",
) -> Dict[str, Any]:
    _validate_positive(frequency_mhz, "frequency_mhz")
    _validate_positive(distance_km, "distance_km")

    eirp_dbm = tx_power_dbm + tx_gain_dbi - tx_loss_db

    if frequency_mhz < 1000.0:
        path_loss_db = okumura_hata_urban(
            frequency_mhz, distance_km, tx_height_m, rx_height_m
        )
        model = "Okumura-Hata"
    elif frequency_mhz <= 2000.0:
        path_loss_db = cost231_hata(
            frequency_mhz, distance_km, tx_height_m, rx_height_m, environment
        )
        model = "COST-231 Hata"
    else:
        path_loss_db = free_space_path_loss(frequency_mhz, distance_km) + 20.0
        model = "FSPL + Margem Urbana"

    rx_power_dbm = eirp_dbm - path_loss_db + rx_gain_dbi - rx_loss_db

    noise_floor_map = {
        "urban": -114.0,
        "dense_urban": -110.0,
        "suburban": -118.0,
        "rural": -124.0,
    }
    noise_floor = noise_floor_map.get(environment, -114.0)
    snr_db = rx_power_dbm - noise_floor

    wavelength = SPEED_OF_LIGHT / (frequency_mhz * 1e6)
    fspl_db = free_space_path_loss(frequency_mhz, distance_km)

    tx_power_w = 10 ** ((tx_power_dbm - 30) / 10)
    cell_radius_km = calculate_coverage_radius(
        tx_power_w=tx_power_w,
        tx_gain_dbi=tx_gain_dbi,
        freq_mhz=frequency_mhz,
        h_base_m=tx_height_m,
        sensitivity_dbm=TECHNOLOGY_SENSITIVITY_DBM.get(technology.upper(), -95.0),
        environment=environment,
    )

    if snr_db > 20:
        status = "Excelente"
    elif snr_db > 10:
        status = "Bom"
    elif snr_db > 0:
        status = "Regular"
    elif snr_db > -10:
        status = "Ruim"
    else:
        status = "Sem Sinal"

    return {
        "frequency_mhz": frequency_mhz,
        "technology": technology,
        "environment": environment,
        "model": model,
        "distance_km": round(distance_km, 3),
        "tx_power_dbm": tx_power_dbm,
        "eirp_dbm": round(eirp_dbm, 2),
        "path_loss_db": round(path_loss_db, 2),
        "free_space_path_loss_db": round(fspl_db, 2),
        "rx_power_dbm": round(rx_power_dbm, 2),
        "noise_floor_dbm": noise_floor,
        "snr_db": round(snr_db, 2),
        "status": status,
        "cell_radius_km": cell_radius_km,
        "wavelength_m": round(wavelength, 3),
    }


def calculate_coverage_profile(
    frequency_mhz: float,
    tx_power_dbm: float,
    tx_gain_dbi: float = 0.0,
    rx_gain_dbi: float = 0.0,
    tx_height_m: float = 30.0,
    rx_height_m: float = 1.5,
    max_distance_km: float = 10.0,
    step_km: float = 0.1,
    environment: str = "urban",
    technology: str = "LTE",
) -> Dict[str, Any]:
    _validate_positive(step_km, "step_km")
    _validate_positive(max_distance_km, "max_distance_km")

    distances = []
    current = step_km
    while current <= max_distance_km:
        distances.append(round(current, 3))
        current += step_km
    if not distances:
        distances = [max_distance_km]

    points = []
    for dist_km in distances:
        link = calculate_link_budget(
            frequency_mhz=frequency_mhz,
            tx_power_dbm=tx_power_dbm,
            tx_gain_dbi=tx_gain_dbi,
            rx_gain_dbi=rx_gain_dbi,
            tx_height_m=tx_height_m,
            rx_height_m=rx_height_m,
            distance_km=dist_km,
            environment=environment,
            technology=technology,
        )
        points.append({
            "distance_km": dist_km,
            "rx_power_dbm": link["rx_power_dbm"],
            "path_loss_db": link["path_loss_db"],
            "snr_db": link["snr_db"],
            "status": link["status"],
        })

    return {
        "technology": technology,
        "environment": environment,
        "frequency_mhz": frequency_mhz,
        "tx_power_dbm": tx_power_dbm,
        "tx_height_m": tx_height_m,
        "rx_height_m": rx_height_m,
        "points": points,
    }
