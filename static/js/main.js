(function () {
    'use strict';

    var KMZModule = {

        sitesData: null,

        init: function () {
            var uploadForm = document.getElementById('uploadForm');
            var btnLoadSample = document.getElementById('btnLoadSample');
            var btnGenerateKMZ = document.getElementById('btnGenerateKMZ');
            var iconSize = document.getElementById('iconSize');
            var iconSizeLabel = document.getElementById('iconSizeLabel');

            if (uploadForm) {
                uploadForm.addEventListener('submit', this.handleUpload.bind(this));
            }
            if (btnLoadSample) {
                btnLoadSample.addEventListener('click', this.loadSample.bind(this));
            }
            if (btnGenerateKMZ) {
                btnGenerateKMZ.addEventListener('click', this.generateKMZ.bind(this));
            }
            if (iconSize && iconSizeLabel) {
                iconSize.addEventListener('input', function () {
                    iconSizeLabel.textContent = parseFloat(this.value).toFixed(1);
                });
            }
        },

        handleUpload: function (e) {
            e.preventDefault();
            var fileInput = document.getElementById('excelFile');
            var spinner = document.getElementById('uploadSpinner');

            if (!fileInput.files || !fileInput.files[0]) {
                showAlert('Selecione um arquivo para upload.', 'warning');
                return;
            }

            var file = fileInput.files[0];
            var formData = new FormData();
            formData.append('file', file);

            spinner.style.display = 'inline-block';
            showLoading('Processando planilha...');

            fetch('/api/kmz/upload', { method: 'POST', body: formData })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    hideLoading();
                    spinner.style.display = 'none';

                    if (!data.success) {
                        showAlert(data.message || 'Erro ao processar arquivo.', 'danger');
                        return;
                    }

                    KMZModule.sitesData = data.data.sites;
                    KMZModule.showPreview(data.data);
                    showAlert('Planilha processada com sucesso! ' + data.data.total_sites + ' sites encontrados.', 'success');
                })
                .catch(function (err) {
                    hideLoading();
                    spinner.style.display = 'none';
                    showAlert('Erro de conexão ao processar a planilha.', 'danger');
                });
        },

        loadSample: function () {
            var sampleSites = [
                { name: 'Torre Centro', latitude: -23.5505, longitude: -46.6333, technology: 'LTE', tx_power_dbm: 43, tx_height_m: 35, frequency_mhz: 2100, antenna_gain_dbi: 18, azimuth: 120, tilt: 2 },
                { name: 'Torre Paulista', latitude: -23.5614, longitude: -46.6560, technology: 'LTE', tx_power_dbm: 43, tx_height_m: 40, frequency_mhz: 1800, antenna_gain_dbi: 16, azimuth: 240, tilt: 4 },
                { name: 'Torre Morumbi', latitude: -23.6000, longitude: -46.7200, technology: 'NR', tx_power_dbm: 46, tx_height_m: 50, frequency_mhz: 3500, antenna_gain_dbi: 20, azimuth: 0, tilt: 2 },
                { name: 'Torre Itaim', latitude: -23.5850, longitude: -46.6780, technology: 'WCDMA', tx_power_dbm: 43, tx_height_m: 30, frequency_mhz: 2100, antenna_gain_dbi: 15, azimuth: 180, tilt: 3 },
                { name: 'Torre Santana', latitude: -23.5000, longitude: -46.6200, technology: 'GSM', tx_power_dbm: 43, tx_height_m: 25, frequency_mhz: 900, antenna_gain_dbi: 12, azimuth: 90, tilt: 5 },
            ];

            KMZModule.sitesData = sampleSites;

            fetch('/api/kmz/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sites: sampleSites })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        KMZModule.showPreviewTable(data.data);
                        showAlert('Dados de exemplo carregados! ' + data.data.total_sites + ' sites.', 'info');
                    }
                })
                .catch(function () {
                    KMZModule.showPreviewTable({
                        total_sites: sampleSites.length,
                        technologies: ['GSM', 'LTE', 'NR', 'WCDMA'],
                        site_list: sampleSites.map(function (s) {
                            return { name: s.name, lat: s.latitude, lon: s.longitude, technology: s.technology };
                        })
                    });
                });
        },

        showPreview: function (data) {
            document.getElementById('previewCard').style.display = 'block';
            document.getElementById('siteCount').textContent = data.total_sites + ' site(s)';
            this.showPreviewTable(data);
        },

        showPreviewTable: function (data) {
            var tbody = document.querySelector('#previewTable tbody');
            tbody.innerHTML = '';

            data.site_list.forEach(function (site, idx) {
                var tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid var(--border)';
                tr.innerHTML =
                    '<td style="padding: 0.4rem 0.5rem;">' + (site.name || 'N/A') + '</td>' +
                    '<td style="padding: 0.4rem 0.5rem;">' + (site.lat || 0).toFixed(6) + '</td>' +
                    '<td style="padding: 0.4rem 0.5rem;">' + (site.lon || 0).toFixed(6) + '</td>' +
                    '<td style="padding: 0.4rem 0.5rem;"><span style="padding: 0.15rem 0.5rem; background: var(--bg); border-radius: 12px; font-size: 0.8rem;">' + (site.technology || 'N/A') + '</span></td>';
                tbody.appendChild(tr);
            });

            document.getElementById('previewInfo').innerHTML =
                '<span style="margin-right: 1rem;"><strong>' + data.total_sites + '</strong> sites</span>' +
                '<span><strong>Tecnologias:</strong> ' + (data.technologies || []).join(', ') + '</span>';
        },

        generateKMZ: function () {
            if (!KMZModule.sitesData || KMZModule.sitesData.length === 0) {
                showAlert('Nenhum site disponível. Faça upload de uma planilha primeiro.', 'warning');
                return;
            }

            var body = {
                sites: KMZModule.sitesData,
                group_by: document.getElementById('groupBy').value,
                include_labels: document.getElementById('includeLabels').checked,
                icon_size: parseFloat(document.getElementById('iconSize').value)
            };

            showLoading('Gerando arquivo KMZ...');

            fetch('/api/kmz/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
                .then(function (response) {
                    if (!response.ok) {
                        return response.json().then(function (err) { throw err; });
                    }
                    return response.blob();
                })
                .then(function (blob) {
                    hideLoading();
                    var url = window.URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'torres_rf_' + new Date().toISOString().slice(0, 10) + '.kmz';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    showAlert('KMZ gerado com sucesso! Download iniciado.', 'success');
                })
                .catch(function (err) {
                    hideLoading();
                    showAlert(err.message || 'Erro ao gerar KMZ.', 'danger');
                });
        }
    };

    var RFModule = {

        linkBudgetData: null,
        coverageData: null,

        init: function () {
            var lbForm = document.getElementById('linkBudgetForm');
            var covForm = document.getElementById('coverageForm');
            var btnPDF = document.getElementById('btnDownloadPDF');
            var btnDOCX = document.getElementById('btnDownloadDOCX');

            if (lbForm) {
                lbForm.addEventListener('submit', this.handleLinkBudget.bind(this));
            }
            if (covForm) {
                covForm.addEventListener('submit', this.handleCoverage.bind(this));
            }
            if (btnPDF) {
                btnPDF.addEventListener('click', this.downloadPDF.bind(this));
            }
            if (btnDOCX) {
                btnDOCX.addEventListener('click', this.downloadDOCX.bind(this));
            }
        },

        handleLinkBudget: function (e) {
            e.preventDefault();

            var payload = {
                technology: document.getElementById('lbTech').value,
                environment: document.getElementById('lbEnv').value,
                frequency_mhz: parseFloat(document.getElementById('lbFreq').value),
                distance_km: parseFloat(document.getElementById('lbDist').value),
                tx_power_dbm: parseFloat(document.getElementById('lbTxPower').value),
                tx_height_m: parseFloat(document.getElementById('lbTxHeight').value),
                rx_height_m: parseFloat(document.getElementById('lbRxHeight').value),
                tx_gain_dbi: parseFloat(document.getElementById('lbTxGain').value),
                rx_gain_dbi: parseFloat(document.getElementById('lbRxGain').value),
                tx_loss_db: parseFloat(document.getElementById('lbTxLoss').value),
                rx_loss_db: 0
            };

            showLoading('Calculando Link Budget...');

            fetch('/api/rf/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    hideLoading();
                    if (!data.success) {
                        showAlert(data.message || 'Erro no cálculo.', 'danger');
                        return;
                    }
                    RFModule.linkBudgetData = data.data;
                    RFModule.showLinkBudget(data.data);
                })
                .catch(function () {
                    hideLoading();
                    showAlert('Erro de conexão.', 'danger');
                });
        },

        handleCoverage: function (e) {
            e.preventDefault();

            var payload = {
                technology: document.getElementById('covTech').value,
                environment: document.getElementById('covEnv').value,
                frequency_mhz: parseFloat(document.getElementById('covFreq').value),
                max_distance_km: parseFloat(document.getElementById('covMaxDist').value),
                tx_power_dbm: parseFloat(document.getElementById('covTxPower').value),
                tx_height_m: parseFloat(document.getElementById('covTxHeight').value),
                rx_height_m: 1.5,
                tx_gain_dbi: parseFloat(document.getElementById('covTxGain').value),
                rx_gain_dbi: 0,
                step_km: parseFloat(document.getElementById('covStep').value)
            };

            showLoading('Calculando perfil de cobertura...');

            fetch('/api/rf/coverage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    hideLoading();
                    if (!data.success) {
                        showAlert(data.message || 'Erro no cálculo.', 'danger');
                        return;
                    }
                    RFModule.coverageData = data.data;
                    RFModule.showCoverage(data.data);
                })
                .catch(function () {
                    hideLoading();
                    showAlert('Erro de conexão.', 'danger');
                });
        },

        showLinkBudget: function (data) {
            var card = document.getElementById('resultsCard');
            var title = document.getElementById('resultsTitle');
            var content = document.getElementById('resultsContent');

            card.style.display = 'block';
            title.textContent = '📊 Link Budget - ' + data.technology;

            var statusColor = data.status === 'Excelente' ? 'var(--success)' :
                              data.status === 'Bom' ? 'var(--primary)' :
                              data.status === 'Regular' ? 'var(--warning)' :
                              'var(--danger)';

            var rows = [
                ['Tecnologia', data.technology],
                ['Ambiente', data.environment],
                ['Modelo', data.model],
                ['Frequência (MHz)', data.frequency_mhz],
                ['Distância (km)', data.distance_km],
                ['Potência TX (dBm)', data.tx_power_dbm],
                ['EIRP (dBm)', data.eirp_dbm],
                ['Path Loss (dB)', data.path_loss_db],
                ['FSPL (dB)', data.free_space_path_loss_db],
                ['Potência RX (dBm)', data.rx_power_dbm],
                ['Noise Floor (dBm)', data.noise_floor_dbm],
                ['SNR (dB)', data.snr_db],
                ['Status', '<span style="color:' + statusColor + '; font-weight:600;">' + data.status + '</span>'],
            ];

            if (data.cell_radius_km !== null) {
                rows.push(['Raio da Célula (km)', data.cell_radius_km]);
            }

            var html = '<table style="width:100%; border-collapse:collapse; font-size:0.85rem;">';

            rows.forEach(function (row) {
                html += '<tr style="border-bottom:1px solid var(--border);">' +
                        '<td style="padding:0.5rem; font-weight:500; color:var(--text-light); width:200px;">' + row[0] + '</td>' +
                        '<td style="padding:0.5rem;">' + row[1] + '</td></tr>';
            });

            html += '</table>';
            content.innerHTML = html;
        },

        showCoverage: function (data) {
            var card = document.getElementById('resultsCard');
            var title = document.getElementById('resultsTitle');
            var content = document.getElementById('resultsContent');

            card.style.display = 'block';
            title.textContent = '📈 Perfil de Cobertura - ' + data.technology;

            var points = data.points || [];
            if (points.length === 0) {
                content.innerHTML = '<p style="color:var(--text-light);">Nenhum ponto de cobertura calculado.</p>';
                return;
            }

            var goodCount = points.filter(function (p) { return p.status === 'Excelente' || p.status === 'Bom'; }).length;

            var html = '<p style="color:var(--text-light); margin-bottom:1rem;">' +
                       data.technology + ' | ' + data.environment + ' | ' + data.frequency_mhz + ' MHz | ' +
                       points.length + ' pontos | <strong>' + goodCount + '</strong> com sinal bom/excelente</p>';

            html += '<div style="overflow-x:auto;"><table style="width:100%; border-collapse:collapse; font-size:0.8rem;">';
            html += '<thead><tr style="background:var(--bg);">' +
                    '<th style="padding:0.35rem 0.5rem; text-align:left; border-bottom:2px solid var(--border);">Dist (km)</th>' +
                    '<th style="padding:0.35rem 0.5rem; text-align:right; border-bottom:2px solid var(--border);">RX (dBm)</th>' +
                    '<th style="padding:0.35rem 0.5rem; text-align:right; border-bottom:2px solid var(--border);">Path Loss (dB)</th>' +
                    '<th style="padding:0.35rem 0.5rem; text-align:right; border-bottom:2px solid var(--border);">SNR (dB)</th>' +
                    '<th style="padding:0.35rem 0.5rem; text-align:center; border-bottom:2px solid var(--border);">Status</th>' +
                    '</tr></thead><tbody>';

            points.forEach(function (p) {
                var sc = p.status === 'Excelente' ? 'var(--success)' :
                         p.status === 'Bom' ? 'var(--primary)' :
                         p.status === 'Regular' ? 'var(--warning)' : 'var(--danger)';
                html += '<tr style="border-bottom:1px solid var(--border);">' +
                        '<td style="padding:0.3rem 0.5rem;">' + p.distance_km.toFixed(1) + '</td>' +
                        '<td style="padding:0.3rem 0.5rem; text-align:right;">' + p.rx_power_dbm.toFixed(1) + '</td>' +
                        '<td style="padding:0.3rem 0.5rem; text-align:right;">' + p.path_loss_db.toFixed(1) + '</td>' +
                        '<td style="padding:0.3rem 0.5rem; text-align:right;">' + p.snr_db.toFixed(1) + '</td>' +
                        '<td style="padding:0.3rem 0.5rem; text-align:center;"><span style="color:' + sc + '; font-weight:600; font-size:0.75rem;">' + p.status + '</span></td>' +
                        '</tr>';
            });

            html += '</tbody></table></div>';
            content.innerHTML = html;
        },

        downloadPDF: function () {
            var payload = {};
            if (RFModule.linkBudgetData) payload.link_budget = RFModule.linkBudgetData;
            if (RFModule.coverageData) payload.coverage = RFModule.coverageData;

            if (!payload.link_budget && !payload.coverage) {
                showAlert('Execute um cálculo primeiro.', 'warning');
                return;
            }

            showLoading('Gerando PDF...');

            fetch('/api/rf/report/pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (response) {
                    if (!response.ok) return response.json().then(function (e) { throw e; });
                    return response.blob();
                })
                .then(function (blob) {
                    hideLoading();
                    var url = window.URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'relatorio_rf.pdf';
                    document.body.appendChild(a); a.click(); document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    showAlert('PDF gerado com sucesso!', 'success');
                })
                .catch(function (err) {
                    hideLoading();
                    showAlert(err.message || 'Erro ao gerar PDF.', 'danger');
                });
        },

        downloadDOCX: function () {
            var payload = {};
            if (RFModule.linkBudgetData) payload.link_budget = RFModule.linkBudgetData;
            if (RFModule.coverageData) payload.coverage = RFModule.coverageData;

            if (!payload.link_budget && !payload.coverage) {
                showAlert('Execute um cálculo primeiro.', 'warning');
                return;
            }

            showLoading('Gerando DOCX...');

            fetch('/api/rf/report/docx', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (response) {
                    if (!response.ok) return response.json().then(function (e) { throw e; });
                    return response.blob();
                })
                .then(function (blob) {
                    hideLoading();
                    var url = window.URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'relatorio_rf.docx';
                    document.body.appendChild(a); a.click(); document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    showAlert('DOCX gerado com sucesso!', 'success');
                })
                .catch(function (err) {
                    hideLoading();
                    showAlert(err.message || 'Erro ao gerar DOCX.', 'danger');
                });
        }
    };

    if (document.getElementById('uploadForm') || document.getElementById('btnGenerateKMZ')) {
        KMZModule.init();
    }

    if (document.getElementById('linkBudgetForm') || document.getElementById('coverageForm')) {
        RFModule.init();
    }

})();
