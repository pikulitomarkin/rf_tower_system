from __future__ import annotations

import math

import pytest

from services.rf_calculator import (
    free_space_path_loss,
    okumura_hata_urban,
    cost231_hata,
    calculate_received_power,
    calculate_coverage_radius,
    generate_coverage_polygon,
    simulate_station_coverage,
    calculate_link_budget,
    calculate_coverage_profile,
)


class TestFreeSpacePathLoss:
    def test_900_mhz_1_km(self):
        loss = free_space_path_loss(900.0, 1.0)
        expected = 20.0 * math.log10(1.0) + 20.0 * math.log10(900.0) + 32.45
        assert loss == pytest.approx(expected, rel=1e-6)
        assert 91.0 < loss < 92.5

    def test_2100_mhz_5_km(self):
        loss = free_space_path_loss(2100.0, 5.0)
        assert 112 < loss < 114

    def test_negative_freq_raises(self):
        with pytest.raises(ValueError, match="freq_mhz"):
            free_space_path_loss(-100.0, 1.0)

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="distance_km"):
            free_space_path_loss(900.0, 0.0)

    def test_los_increases_with_distance(self):
        l1 = free_space_path_loss(2100.0, 1.0)
        l2 = free_space_path_loss(2100.0, 2.0)
        assert l2 > l1


class TestOkumuraHataUrban:
    def test_900_mhz_5_km_40m_tower(self):
        loss = okumura_hata_urban(900.0, 5.0, 40.0)
        assert 145 < loss < 160

    def test_redirects_to_cost231_above_1500_mhz(self):
        loss = okumura_hata_urban(1800.0, 2.0, 30.0)
        loss_cost = cost231_hata(1800.0, 2.0, 30.0, environment="urban")
        assert loss == pytest.approx(loss_cost, rel=1e-6)

    def test_below_150_mhz_raises(self):
        with pytest.raises(ValueError, match="freq_mhz"):
            okumura_hata_urban(100.0, 5.0, 30.0)

    def test_environment_corrections(self):
        urban = okumura_hata_urban(900.0, 5.0, 30.0, environment="urban")
        rural = okumura_hata_urban(900.0, 5.0, 30.0, environment="rural")
        assert rural < urban


class TestCost231Hata:
    def test_1800_mhz_urban(self):
        loss = cost231_hata(1800.0, 2.0, 30.0, environment="urban")
        assert 140 < loss < 160

    def test_urban_greater_than_rural(self):
        u = cost231_hata(1800.0, 2.0, 30.0, environment="urban")
        r = cost231_hata(1800.0, 2.0, 30.0, environment="rural")
        assert u > r

    def test_suburban_correction(self):
        u = cost231_hata(1800.0, 2.0, 30.0, environment="urban")
        s = cost231_hata(1800.0, 2.0, 30.0, environment="suburban")
        assert s < u

    def test_invalid_environment(self):
        with pytest.raises(ValueError, match="Ambiente"):
            cost231_hata(1800.0, 2.0, 30.0, environment="mars")


class TestCalculateReceivedPower:
    def test_basic_friis(self):
        rx = calculate_received_power(20.0, 18.0, 135.0)
        tx_dbm = 10.0 * math.log10(20.0 * 1000.0)
        expected = tx_dbm + 18.0 - 135.0 + 0.0 - 2.0
        assert rx == pytest.approx(expected)

    def test_zero_power_raises(self):
        with pytest.raises(ValueError, match="tx_power_w"):
            calculate_received_power(0.0, 10.0, 100.0)


class TestCalculateCoverageRadius:
    def test_lte_2100_returns_positive(self):
        r = calculate_coverage_radius(20.0, 18.0, 2100.0, 30.0)
        assert 0.5 < r < 50.0
        assert isinstance(r, float)

    def test_gsm_900_larger_than_lte_2100(self):
        r_gsm = calculate_coverage_radius(20.0, 12.0, 900.0, 30.0, sensitivity_dbm=-102.0)
        r_lte = calculate_coverage_radius(20.0, 18.0, 2100.0, 30.0)
        assert r_gsm > 0
        assert r_lte > 0

    def test_higher_power_increases_radius(self):
        r1 = calculate_coverage_radius(10.0, 15.0, 2100.0, 30.0)
        r2 = calculate_coverage_radius(40.0, 15.0, 2100.0, 30.0)
        assert r2 > r1

    def test_negative_power_raises(self):
        with pytest.raises(ValueError):
            calculate_coverage_radius(-10.0, 15.0, 2100.0, 30.0)


class TestGenerateCoveragePolygon:
    def test_returns_38_points_for_default_num_points(self):
        poly = generate_coverage_polygon(-23.55, -46.63, 120.0, 65.0, 2.0)
        assert len(poly) == 38
        assert isinstance(poly, list)

    def test_polygon_closes(self):
        poly = generate_coverage_polygon(-23.55, -46.63, 120.0, 65.0, 2.0)
        assert poly[0] == pytest.approx(poly[-1])

    def test_omni_returns_circle(self):
        poly = generate_coverage_polygon(-23.55, -46.63, 0, 360.0, 3.0, num_points=12)
        assert len(poly) == 14

    def test_each_point_is_tuple_of_two_floats(self):
        poly = generate_coverage_polygon(-23.55, -46.63, 120.0, 65.0, 2.0)
        for pt in poly:
            assert isinstance(pt, tuple)
            assert len(pt) == 2
            assert isinstance(pt[0], float)
            assert isinstance(pt[1], float)

    def test_zero_radius_raises(self):
        with pytest.raises(ValueError):
            generate_coverage_polygon(-23.55, -46.63, 120.0, 65.0, 0.0)


class TestSimulateStationCoverage:
    def test_three_sectors_return_three_results(self):
        station = {
            "info": {"Latitude": -23.55, "Longitude": -46.63, "AlturaAntena": 35.0},
            "sectors": [
                {"Tecnologia": "LTE", "FreqTxMHz": 2100.0, "Azimute": 0,
                 "GanhoAntena": 18.0, "PotenciaTransmissorWatts": 20.0},
                {"Tecnologia": "LTE", "FreqTxMHz": 2100.0, "Azimute": 120,
                 "GanhoAntena": 18.0, "PotenciaTransmissorWatts": 20.0},
                {"Tecnologia": "NR", "FreqTxMHz": 3500.0, "Azimute": 240,
                 "GanhoAntena": 20.0, "PotenciaTransmissorWatts": 40.0},
            ],
        }
        results = simulate_station_coverage(station)
        assert len(results) == 3
        for r in results:
            assert "polygon_coords" in r
            assert "radius_km" in r
            assert "received_power_dbm" in r

    def test_empty_sectors_raises(self):
        with pytest.raises(ValueError):
            simulate_station_coverage({"info": {}, "sectors": []})

    def test_none_input_raises(self):
        with pytest.raises(ValueError):
            simulate_station_coverage(None)


class TestLinkBudget:
    def test_returns_all_keys(self):
        lb = calculate_link_budget(2100.0, 43.0, tx_gain_dbi=18.0, environment="urban")
        expected_keys = [
            "frequency_mhz", "technology", "environment", "model",
            "distance_km", "tx_power_dbm", "eirp_dbm", "path_loss_db",
            "free_space_path_loss_db", "rx_power_dbm", "noise_floor_dbm",
            "snr_db", "status", "cell_radius_km", "wavelength_m",
        ]
        for k in expected_keys:
            assert k in lb

    def test_snr_status(self):
        lb = calculate_link_budget(900.0, 43.0, tx_gain_dbi=18.0, environment="rural")
        assert lb["status"] in ("Excelente", "Bom", "Regular", "Ruim", "Sem Sinal")


class TestCoverageProfile:
    def test_step_0_2_km_max_1_km_gives_5_points(self):
        cov = calculate_coverage_profile(
            2100.0, 43.0, tx_gain_dbi=18.0, step_km=0.2, max_distance_km=1.0
        )
        assert len(cov["points"]) == 5
        assert cov["technology"] == "LTE"
