import os
from datetime import datetime

from flask import request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

from routes import rf_bp
from services.rf_calculator import (
    calculate_link_budget,
    calculate_coverage_profile,
    calculate_coverage_radius,
    calculate_received_power,
    generate_coverage_polygon,
    simulate_station_coverage,
    free_space_path_loss,
    okumura_hata_urban,
    cost231_hata,
    TECHNOLOGY_SENSITIVITY_DBM,
)
from services.report_generator import generate_pdf_report, generate_docx_report
from services.excel_parser import parse_excel, group_by_station
from services.kmz_coverage_generator import generate_coverage_kmz


def _cleanup_file(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except OSError as e:
        current_app.logger.warning(f'Falha ao remover arquivo: {filepath}: {e}')


def _select_path_loss_model(freq_mhz, distance_km, h_base_m, environment):
    if freq_mhz < 1000.0:
        return okumura_hata_urban(freq_mhz, distance_km, h_base_m, environment=environment)
    elif freq_mhz <= 2000.0:
        return cost231_hata(freq_mhz, distance_km, h_base_m, environment=environment)
    else:
        return free_space_path_loss(freq_mhz, distance_km) + 20.0


def _model_name(freq_mhz):
    if freq_mhz < 1000.0:
        return "Okumura-Hata"
    elif freq_mhz <= 2000.0:
        return "COST-231 Hata"
    else:
        return "FSPL + Margem Urbana"


# ---------------------------------------------------------------------------
# POST /api/rf/calculate  (mantido para compatibilidade)
# ---------------------------------------------------------------------------

@rf_bp.route('/calculate', methods=['POST'])
def calculate_rf():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400

    required_fields = ['frequency_mhz', 'tx_power_dbm', 'tx_height_m', 'rx_height_m', 'distance_km']
    missing = [f for f in required_fields if f not in body]
    if missing:
        return jsonify({'success': False, 'error': 'missing_fields',
                        'message': f'Campos obrigatórios ausentes: {", ".join(missing)}'}), 400

    try:
        frequency_mhz = float(body['frequency_mhz'])
        tx_power_dbm = float(body['tx_power_dbm'])
        tx_height_m = float(body['tx_height_m'])
        rx_height_m = float(body['rx_height_m'])
        distance_km = float(body['distance_km'])
        environment = body.get('environment', 'urban')
        technology = body.get('technology', 'LTE')
        tx_gain_dbi = float(body.get('tx_gain_dbi', 0))
        rx_gain_dbi = float(body.get('rx_gain_dbi', 0))
        tx_loss_db = float(body.get('tx_loss_db', 0))
        rx_loss_db = float(body.get('rx_loss_db', 0))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': 'invalid_values',
                        'message': f'Valores numéricos inválidos: {str(e)}'}), 400

    if frequency_mhz <= 0 or distance_km <= 0:
        return jsonify({'success': False, 'error': 'invalid_range',
                        'message': 'Frequência e distância devem ser maiores que zero.'}), 400

    try:
        result = calculate_link_budget(
            frequency_mhz=frequency_mhz, tx_power_dbm=tx_power_dbm,
            tx_gain_dbi=tx_gain_dbi, tx_loss_db=tx_loss_db,
            rx_gain_dbi=rx_gain_dbi, rx_loss_db=rx_loss_db,
            tx_height_m=tx_height_m, rx_height_m=rx_height_m,
            distance_km=distance_km, environment=environment, technology=technology,
        )
        return jsonify({'success': True, 'data': result}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': 'calculation_error', 'message': str(e)}), 422
    except Exception as e:
        current_app.logger.error(f'Erro ao calcular RF: {e}', exc_info=True)
        return jsonify({'success': False, 'error': 'rf_calculation_error',
                        'message': 'Erro ao realizar o cálculo de propagação RF.'}), 500


# ---------------------------------------------------------------------------
# POST /api/rf/coverage  (mantido para compatibilidade)
# ---------------------------------------------------------------------------

@rf_bp.route('/coverage', methods=['POST'])
def calculate_coverage():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400

    required_fields = ['frequency_mhz', 'tx_power_dbm', 'tx_height_m', 'rx_height_m', 'max_distance_km']
    missing = [f for f in required_fields if f not in body]
    if missing:
        return jsonify({'success': False, 'error': 'missing_fields',
                        'message': f'Campos obrigatórios ausentes: {", ".join(missing)}'}), 400

    try:
        frequency_mhz = float(body['frequency_mhz'])
        tx_power_dbm = float(body['tx_power_dbm'])
        tx_height_m = float(body['tx_height_m'])
        rx_height_m = float(body['rx_height_m'])
        max_distance_km = float(body['max_distance_km'])
        step_km = float(body.get('step_km', 0.1))
        environment = body.get('environment', 'urban')
        technology = body.get('technology', 'LTE')
        tx_gain_dbi = float(body.get('tx_gain_dbi', 0))
        rx_gain_dbi = float(body.get('rx_gain_dbi', 0))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': 'invalid_values',
                        'message': f'Valores numéricos inválidos: {str(e)}'}), 400

    try:
        cov = calculate_coverage_profile(
            frequency_mhz=frequency_mhz, tx_power_dbm=tx_power_dbm,
            tx_gain_dbi=tx_gain_dbi, rx_gain_dbi=rx_gain_dbi,
            tx_height_m=tx_height_m, rx_height_m=rx_height_m,
            max_distance_km=max_distance_km, step_km=step_km,
            environment=environment, technology=technology,
        )
        return jsonify({'success': True, 'data': cov}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': 'calculation_error', 'message': str(e)}), 422
    except Exception as e:
        current_app.logger.error(f'Erro ao calcular cobertura: {e}', exc_info=True)
        return jsonify({'success': False, 'error': 'coverage_calculation_error',
                        'message': 'Erro ao calcular o perfil de cobertura.'}), 500


# ---------------------------------------------------------------------------
# POST /api/rf/simulate
# ---------------------------------------------------------------------------

@rf_bp.route('/simulate', methods=['POST'])
def simulate_rf():
    """
    Simula cobertura RF com parâmetros manuais.

    Recebe:
    { lat, lon, freq_mhz, power_watts, gain_dbi, height_m,
      azimuth_deg, beamwidth_deg, technology, environment,
      sensitivity_dbm (opcional) }

    Retorna:
    { radius_km, coverage_area_km2, path_loss_db, received_power_dbm,
      model_used, polygon_coords, ... }
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400

    required = ['lat', 'lon', 'freq_mhz', 'power_watts', 'gain_dbi', 'height_m',
                'azimuth_deg', 'beamwidth_deg', 'technology', 'environment']
    missing = [f for f in required if f not in body]
    if missing:
        return jsonify({'success': False, 'error': 'missing_fields',
                        'message': f'Campos obrigatórios ausentes: {", ".join(missing)}'}), 400

    try:
        lat = float(body['lat'])
        lon = float(body['lon'])
        freq_mhz = float(body['freq_mhz'])
        power_w = float(body['power_watts'])
        gain_dbi = float(body['gain_dbi'])
        height_m = float(body['height_m'])
        azimuth_deg = float(body['azimuth_deg'])
        beamwidth_deg = float(body['beamwidth_deg'])
        technology = str(body['technology']).upper()
        environment = str(body['environment']).lower()
        sensitivity_dbm = float(body.get('sensitivity_dbm',
                                          TECHNOLOGY_SENSITIVITY_DBM.get(technology, -95.0)))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': 'invalid_values',
                        'message': f'Valores numéricos inválidos: {str(e)}'}), 400

    if freq_mhz <= 0 or power_w <= 0 or height_m <= 0:
        return jsonify({'success': False, 'error': 'invalid_range',
                        'message': 'Frequência, potência e altura devem ser maiores que zero.'}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return jsonify({'success': False, 'error': 'invalid_coords',
                        'message': 'Coordenadas fora dos limites válidos.'}), 400

    try:
        radius_km = calculate_coverage_radius(
            tx_power_w=power_w, tx_gain_dbi=gain_dbi, freq_mhz=freq_mhz,
            h_base_m=height_m, sensitivity_dbm=sensitivity_dbm, environment=environment,
        )
        coverage_area_km2 = round(3.14159 * radius_km ** 2 * (beamwidth_deg / 360.0), 3)

        path_loss_db = round(_select_path_loss_model(
            freq_mhz, max(radius_km, 0.01), height_m, environment), 2)
        rx_dbm = round(calculate_received_power(power_w, gain_dbi, path_loss_db), 2)

        polygon = generate_coverage_polygon(
            lat, lon, azimuth_deg, beamwidth_deg, max(radius_km, 0.01)
        )

        current_app.logger.info(
            'Simulação RF: %s %sMHz Az=%d° R=%.2fkm', technology, freq_mhz, azimuth_deg, radius_km)

        return jsonify({
            'success': True,
            'data': {
                'radius_km': radius_km,
                'coverage_area_km2': coverage_area_km2,
                'path_loss_db': path_loss_db,
                'received_power_dbm': rx_dbm,
                'model_used': _model_name(freq_mhz),
                'polygon_coords': polygon,
                'frequency_mhz': freq_mhz,
                'technology': technology,
                'environment': environment,
                'sensitivity_dbm': sensitivity_dbm,
            }
        }), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': 'calculation_error', 'message': str(e)}), 422
    except Exception as e:
        current_app.logger.error(f'Erro na simulação RF: {e}', exc_info=True)
        return jsonify({'success': False, 'error': 'simulation_error',
                        'message': 'Erro ao simular a cobertura RF.'}), 500


# ---------------------------------------------------------------------------
# POST /api/rf/simulate-from-excel
# ---------------------------------------------------------------------------

@rf_bp.route('/simulate-from-excel', methods=['POST'])
def simulate_from_excel():
    """
    Recebe Excel ANATEL, simula cobertura de todas as torres/setores
    e retorna KMZ de cobertura para download.
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'no_file',
                        'message': 'Nenhum arquivo Excel foi enviado.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'empty_filename',
                        'message': 'Nome de arquivo vazio.'}), 400

    import uuid
    from werkzeug.utils import secure_filename

    excel_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                               f"{uuid.uuid4()}_{secure_filename(file.filename)}")
    file.save(excel_path)

    try:
        df = parse_excel(excel_path)
        stations_raw = group_by_station(df)

        stations_coverage = []
        for st_id, st_data in stations_raw.items():
            info = st_data['info']
            sectors = st_data['sectors']

            station_dict = {'info': {}, 'sectors': []}
            for key in ['Latitude', 'Longitude', 'AlturaAntena', 'EnderecoEstacao']:
                if key in info:
                    station_dict['info'][key] = info[key]

            for sec in sectors:
                station_dict['sectors'].append({
                    'Tecnologia': sec.get('Tecnologia', 'LTE'),
                    'FreqTxMHz': sec.get('FreqTxMHz', 2100.0),
                    'Azimute': sec.get('Azimute', 0),
                    'GanhoAntena': sec.get('GanhoAntena', 15.0),
                    'PotenciaTransmissorWatts': sec.get('PotenciaTransmissorWatts', 20.0),
                    'AnguloMeiaPotenciaAntena': sec.get('AnguloMeiaPotenciaAntena', 65.0),
                    'AlturaAntena': sec.get('AlturaAntena'),
                })

            try:
                sectors_sim = simulate_station_coverage(station_dict)
            except Exception as e:
                current_app.logger.warning('Falha ao simular estação %s: %s', st_id, e)
                continue

            stations_coverage.append({
                'station_id': str(st_id),
                'operadora': str(info.get('Torre Estação', info.get('operadora', ''))),
                'endereco': str(info.get('EnderecoEstacao', info.get('endereco', ''))),
                'lat': float(info.get('Latitude', info.get('latitude', 0))),
                'lon': float(info.get('Longitude', info.get('longitude', 0))),
                'altura_antena': float(info.get('AlturaAntena', info.get('altura_antena', 0))),
                'sectors': sectors_sim,
            })

        if not stations_coverage:
            return jsonify({'success': False, 'error': 'no_coverage',
                            'message': 'Nenhuma estação pôde ser simulada.'}), 422

        kmz_filename = f"simulacao_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz"
        kmz_path = os.path.join(current_app.config['UPLOAD_FOLDER'], kmz_filename)
        generate_coverage_kmz(stations_coverage=stations_coverage, output_path=kmz_path,
                              show_signal_levels=True, show_sector_arrows=False)

        current_app.logger.info('Simulação Excel: %d estações → KMZ', len(stations_coverage))
        return send_file(kmz_path,
                         mimetype='application/vnd.google-earth.kmz',
                         as_attachment=True,
                         download_name=kmz_filename)

    except ValueError as e:
        return jsonify({'success': False, 'error': 'simulation_error', 'message': str(e)}), 422
    except Exception as e:
        current_app.logger.error(f'Erro simulate-from-excel: {e}', exc_info=True)
        return jsonify({'success': False, 'error': 'simulation_error',
                        'message': 'Erro ao simular cobertura a partir do Excel.'}), 500
    finally:
        _cleanup_file(excel_path)


# ---------------------------------------------------------------------------
# POST /api/rf/report  -- unificado: { stations, format: "pdf"|"docx", title }
# ---------------------------------------------------------------------------

@rf_bp.route('/report', methods=['POST'])
def generate_report():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400

    stations_data = body.get('stations', [])
    report_format = str(body.get('format', 'pdf')).lower()
    title = body.get('title', 'Relatório de Cobertura RF')

    if report_format not in ('pdf', 'docx'):
        return jsonify({'success': False, 'error': 'invalid_format',
                        'message': 'Formato deve ser "pdf" ou "docx".'}), 400

    if not stations_data:
        return jsonify({'success': False, 'error': 'missing_data',
                        'message': 'Forneça uma lista de "stations".'}), 400

    report_path = None
    try:
        ext = 'pdf' if report_format == 'pdf' else 'docx'
        mime = 'application/pdf' if ext == 'pdf' else \
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        output_fn = f"relatorio_rf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        report_path = os.path.join(current_app.config['UPLOAD_FOLDER'], output_fn)

        if report_format == 'pdf':
            generate_pdf_report(stations_data=stations_data, output_path=report_path, title=title)
        else:
            generate_docx_report(stations_data=stations_data, output_path=report_path, title=title)

        current_app.logger.info('Relatório %s gerado: %s', ext.upper(), output_fn)
        return send_file(report_path, mimetype=mime, as_attachment=True, download_name=output_fn)

    except ValueError as e:
        return jsonify({'success': False, 'error': 'report_error', 'message': str(e)}), 422
    except Exception as e:
        current_app.logger.error(f'Erro ao gerar relatório: {e}', exc_info=True)
        return jsonify({'success': False, 'error': 'report_generation_error',
                        'message': 'Erro ao gerar o relatório.'}), 500


# ---------------------------------------------------------------------------
# POST /api/rf/report/pdf  (legado — redireciona para /report)
# ---------------------------------------------------------------------------

@rf_bp.route('/report/pdf', methods=['POST'])
def generate_pdf_report_route():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400
    body['format'] = 'pdf'
    return generate_report()


# ---------------------------------------------------------------------------
# POST /api/rf/report/docx  (legado — redireciona para /report)
# ---------------------------------------------------------------------------

@rf_bp.route('/report/docx', methods=['POST'])
def generate_docx_report_route():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'success': False, 'error': 'missing_body',
                        'message': 'O corpo da requisição está vazio.'}), 400
    body['format'] = 'docx'
    return generate_report()


# ---------------------------------------------------------------------------
# GET /api/rf/technologies
# ---------------------------------------------------------------------------

@rf_bp.route('/technologies', methods=['GET'])
def list_technologies():
    technologies = [
        {'id': 'gsm', 'name': 'GSM',
         'frequency_bands': ['850 MHz', '900 MHz', '1800 MHz', '1900 MHz'],
         'max_power_dbm': 43, 'bandwidth': '200 kHz'},
        {'id': 'wcdma', 'name': 'WCDMA / UMTS',
         'frequency_bands': ['850 MHz', '900 MHz', '1700 MHz', '1900 MHz', '2100 MHz'],
         'max_power_dbm': 43, 'bandwidth': '5 MHz'},
        {'id': 'lte', 'name': 'LTE',
         'frequency_bands': ['700 MHz', '850 MHz', '1800 MHz', '2100 MHz', '2600 MHz'],
         'max_power_dbm': 46, 'bandwidth': '1.4 MHz - 20 MHz'},
        {'id': 'nr', 'name': 'NR (5G)',
         'frequency_bands': ['700 MHz', '3.5 GHz', '26 GHz', '28 GHz'],
         'max_power_dbm': 46, 'bandwidth': '5 MHz - 100 MHz'},
    ]
    return jsonify({'success': True, 'data': technologies}), 200
