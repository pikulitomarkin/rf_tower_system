# RF Tower System

**Sistema de Planejamento de Torres RF** — Ferramenta profissional para simulação de propagação de radiofrequência, cálculo de link budget, exportação KMZ para Google Earth e geração de relatórios técnicos.

---

## 📋 Índice

- [Descrição do Sistema](#descrição-do-sistema)
- [Instalação](#instalação)
- [Inicialização Rápida](#inicialização-rápida)
- [Módulo Excel → KMZ](#módulo-excel--kmz)
- [Módulo Simulação RF](#módulo-simulação-rf)
- [Estrutura do Excel Esperada](#estrutura-do-excel-esperada)
- [Modelos de Propagação](#modelos-de-propagacão)
- [API — Exemplos com curl](#api--exemplos-com-curl)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [FAQ](#faq)

---

## Descrição do Sistema

O **RF Tower System** é uma aplicação web Flask que oferece duas funcionalidades principais:

1. **Excel → KMZ**: Upload de planilhas ANATEL com dados de estações rádio-base e geração de arquivos KMZ navegáveis no Google Earth, com ícones coloridos por operadora e tecnologia, setas de azimute e tabelas de parâmetros.

2. **Simulação RF**: Cálculo de propagação de radiofrequência usando modelos **Okumura-Hata**, **COST-231 Hata** e **Free Space Path Loss (FSPL)**, com geração de polígonos de cobertura setorial, zonas de intensidade de sinal e relatórios em PDF/DOCX.

### Tecnologias suportadas

| Geração | Tecnologia | Bandas típicas |
|---|---|---|
| 2G | GSM | 850, 900, 1800, 1900 MHz |
| 3G | WCDMA / UMTS | 850, 900, 1700, 1900, 2100 MHz |
| 4G | LTE | 700, 850, 1800, 2100, 2600 MHz |
| 5G | NR | 700, 3500, 26000, 28000 MHz |

---

## Instalação

### Pré-requisitos

- Python **3.9+**
- pip (gerenciador de pacotes Python)

### Passo a passo

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd rf_tower_system

# 2. Crie um ambiente virtual (recomendado)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Instale as dependências
make install
# ou: pip install -r requirements.txt

# 4. Crie as pastas necessárias
mkdir -p uploads static/icons

# 5. Execute a aplicação
make run
# ou: python run.py
```

Acesse **http://localhost:5000** no navegador.

---

## Inicialização Rápida

```bash
# Ambiente de desenvolvimento com hot-reload
python run.py --debug --port 5000

# Ambiente de produção
python run.py --env production --host 0.0.0.0 --port 80

# Executar testes
make test
# ou: pytest tests/ -v

# Limpar arquivos temporários
make clean

# Verificar sintaxe de todos os arquivos
make lint
```

---

## Módulo Excel → KMZ

### Interface Web

1. Acesse http://localhost:5000
2. Na aba **Excel → KMZ**, faça o download do template Excel
3. Preencha a planilha com os dados das suas torres
4. Arraste o arquivo para a zona de upload
5. Clique em **Visualizar Dados** para conferir
6. Clique em **Gerar KMZ** e abra o arquivo no Google Earth

### Opções

- **Setas de Azimute**: exibe linhas de 300m indicando a direção de cada setor
- **Agrupamento**: estações são agrupadas por `Numero Estacao`

### API — Fluxo programático

```bash
# 1. Upload da planilha (retorna JSON com os dados processados)
curl -X POST http://localhost:5000/api/kmz/upload \
  -F "file=@planilha_anatel.xlsx"

# 2. Preview dos dados
curl -X POST http://localhost:5000/api/kmz/preview \
  -F "excel_file=@planilha_anatel.xlsx"

# 3. Gerar KMZ diretamente do Excel
curl -X POST http://localhost:5000/api/kmz/generate \
  -F "excel_file=@planilha_anatel.xlsx" \
  -F "show_sectors=true" \
  -o torres.kmz

# 4. Download do template Excel
curl -X GET http://localhost:5000/api/kmz/template \
  -o template_anatel.xlsx
```

---

## Módulo Simulação RF

### Interface Web

1. Na aba **Simulação RF**, preencha os parâmetros manuais:
   - Coordenadas (latitude, longitude)
   - Frequência (MHz), Potência (Watts), Ganho (dBi)
   - Altura da torre (m), Azimute (°), Beamwidth (°)
   - Tecnologia (GSM/WCDMA/LTE/NR), Ambiente (urbano/suburbano/rural)
2. Clique em **Simular Cobertura**
3. Visualize o raio calculado, área, path loss e potência recebida
4. Opcional: clique em **Gerar Relatório PDF**

### Simulação a partir de Excel

Na aba **Simulação RF**, há uma seção "Simular a Partir de Excel":
1. Faça upload de uma planilha ANATEL
2. Clique em **Simular do Excel e Baixar KMZ**
3. O sistema simula **todas** as estações do arquivo e gera um KMZ de cobertura com polígonos setoriais e zonas de intensidade de sinal

### API — Simulação manual

```bash
curl -X POST http://localhost:5000/api/rf/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -23.5505,
    "lon": -46.6333,
    "freq_mhz": 2100,
    "power_watts": 20,
    "gain_dbi": 18,
    "height_m": 35,
    "azimuth_deg": 0,
    "beamwidth_deg": 65,
    "technology": "LTE",
    "environment": "urban"
  }'
```

### API — Relatórios

```bash
# Gerar relatório PDF
curl -X POST http://localhost:5000/api/rf/report \
  -H "Content-Type: application/json" \
  -d '{"stations": [...], "format": "pdf"}' \
  -o relatorio.pdf

# Gerar relatório DOCX
curl -X POST http://localhost:5000/api/rf/report \
  -H "Content-Type: application/json" \
  -d '{"stations": [...], "format": "docx"}' \
  -o relatorio.docx
```

---

## Estrutura do Excel Esperada

A planilha deve conter **19 colunas** no formato ANATEL. Cada linha representa **um setor** de uma estação.

### Template

Faça download do template via interface web ou API: `GET /api/kmz/template`

### Colunas

| # | Coluna | Tipo | Descrição | Exemplo |
|---|---|---|---|---|
| 1 | `Torre Estação` | texto | Nome da operadora | `CLARO S.A.` |
| 2 | `Numero Estacao` | número | Código único da estação | `2083922` |
| 3 | `EnderecoEstacao` | texto | Endereço completo | `Av. Paulista, 1000` |
| 4 | `SiglaUf` | texto | Sigla do estado | `SP` |
| 5 | `DesignacaoEmissao` | texto | Designação de emissão | `5M00G7W` |
| 6 | `Tecnologia` | texto | `GSM`, `WCDMA`, `LTE` ou `NR` | `LTE` |
| 7 | `FreqTxMHz` | decimal | Frequência TX em MHz | `2640.0` |
| 8 | `FreqRxMHz` | decimal | Frequência RX em MHz | `2500.0` |
| 9 | `Azimute` | inteiro | Ângulo do setor (0=Norte) | `220` |
| 10 | `GanhoAntena` | decimal | Ganho em dBi | `17.9` |
| 11 | `FrenteCostaAntena` | decimal | Relação frente/costas dB | `25.0` |
| 12 | `AnguloMeiaPotenciaAntena` | decimal | Ângulo de meia potência | `65.0` |
| 13 | `AnguloElevacao` | inteiro | Tilt de elevação | `2` |
| 14 | `Polarizacao` | texto | Tipo de polarização | `X` |
| 15 | `AlturaAntena` | decimal | Altura em metros | `40.0` |
| 16 | `CodEquipamentoTransmissor` | texto | Código do equipamento TX | `TX-001` |
| 17 | `PotenciaTransmissorWatts` | decimal | Potência TX em Watts | `40.0` |
| 18 | `Latitude` | decimal | Latitude (graus decimais) | `-15.91993` |
| 19 | `Longitude` | decimal | Longitude (graus decimais) | `-47.96529` |

### Exemplo de dados

| Torre Estação | Numero Estacao | EnderecoEstacao | SiglaUf | DesignacaoEmissao | Tecnologia | FreqTxMHz | FreqRxMHz | Azimute | GanhoAntena | FrenteCostaAntena | AnguloMeiaPotenciaAntena | AnguloElevacao | Polarizacao | AlturaAntena | CodEquipamentoTransmissor | PotenciaTransmissorWatts | Latitude | Longitude |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CLARO S.A. | 2083922 | Rua A, 100 | SP | 5M00G7W | LTE | 2640 | 2500 | 220 | 17.9 | 25.0 | 65.0 | 2 | X | 40 | TX-001 | 40 | -15.91993 | -47.96529 |
| CLARO S.A. | 2083922 | Rua A, 100 | SP | 5M00G7W | LTE | 2640 | 2500 | 300 | 17.9 | 25.0 | 65.0 | 2 | X | 40 | TX-001 | 40 | -15.91993 | -47.96529 |

> **Nota**: Estações com o mesmo `Numero Estacao` são automaticamente agrupadas. Cada setor deve ter seu próprio `Azimute`.

---

## Modelos de Propagação

### 1. Free Space Path Loss (FSPL)

**Fórmula**: `L[dB] = 20·log₁₀(d_km) + 20·log₁₀(f_MHz) + 32.45`

- Válido para cenários com linha de visada (LOS) desobstruída
- Usado para frequências **acima de 2000 MHz** com margem urbana adicional de 20 dB
- Sem dependência de altura das antenas

### 2. Okumura-Hata (Urbano)

**Faixa**: 150 MHz ≤ f ≤ 1500 MHz, 1 km ≤ d ≤ 20 km

**Fórmula**:
```
L = 69.55 + 26.16·log₁₀(f) - 13.82·log₁₀(hb) - a(hr) + (44.9 - 6.55·log₁₀(hb))·log₁₀(d)
```

- `hb`: altura da antena base (30 a 200 m)
- `a(hr)`: fator de correção da antena móvel
- Correções ambientais: **suburban (-9.88 dB)**, **rural (-26.44 dB)**
- Para frequências > 1500 MHz, redireciona automaticamente ao COST-231 Hata

### 3. COST-231 Hata

**Faixa**: 1500 MHz ≤ f ≤ 2000 MHz

**Fórmula**:
```
L = 46.3 + 33.9·log₁₀(f) - 13.82·log₁₀(hb) - a(hr) + (44.9 - 6.55·log₁₀(hb))·log₁₀(d) + Cm + Cenv
```

- `Cm`: fator de correção metropolitano (**urban=3**, dense_urban=5, suburban/rural=0)
- `Cenv`: fator ambiental (**suburban=-9.88**, **rural=-26.44**)
- Extensão do modelo Hata validada para ambientes densos

### Seleção automática de modelo

| Faixa de frequência | Modelo |
|---|---|
| f < 1000 MHz | Okumura-Hata (urbano) |
| 1000 ≤ f ≤ 2000 MHz | COST-231 Hata |
| f > 2000 MHz | FSPL + 20 dB (margem urbana) |

### Sensibilidades por tecnologia

| Tecnologia | Sensibilidade típica |
|---|---|
| GSM | -102 dBm |
| WCDMA | -115 dBm |
| LTE | -95 dBm |
| NR (5G) | -90 dBm |

---

## API — Exemplos com curl

### KMZ

```bash
# Health check
curl http://localhost:5000/health

# Upload de planilha
curl -X POST http://localhost:5000/api/kmz/upload \
  -F "file=@planilha.xlsx"

# Preview
curl -X POST http://localhost:5000/api/kmz/preview \
  -F "excel_file=@planilha.xlsx"

# Gerar KMZ (Excel direto)
curl -X POST http://localhost:5000/api/kmz/generate \
  -F "excel_file=@planilha.xlsx" \
  -F "show_sectors=true" \
  -o torres.kmz

# Gerar KMZ de cobertura
curl -X POST http://localhost:5000/api/kmz/coverage \
  -H "Content-Type: application/json" \
  -d '{"stations": [...], "show_signal_levels": true}' \
  -o cobertura.kmz

# Baixar template Excel
curl -O http://localhost:5000/api/kmz/template
```

### RF

```bash
# Cálculo de link budget
curl -X POST http://localhost:5000/api/rf/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "frequency_mhz": 2100,
    "tx_power_dbm": 43,
    "tx_height_m": 30,
    "rx_height_m": 1.5,
    "distance_km": 1.0,
    "environment": "urban",
    "technology": "LTE",
    "tx_gain_dbi": 18
  }'

# Simulação de cobertura (parâmetros manuais)
curl -X POST http://localhost:5000/api/rf/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -23.55, "lon": -46.63,
    "freq_mhz": 2100, "power_watts": 20, "gain_dbi": 18,
    "height_m": 35, "azimuth_deg": 0, "beamwidth_deg": 65,
    "technology": "LTE", "environment": "urban"
  }'

# Simulação a partir de Excel (retorna KMZ de cobertura)
curl -X POST http://localhost:5000/api/rf/simulate-from-excel \
  -F "file=@planilha.xlsx" \
  -o cobertura_simulada.kmz

# Relatório PDF
curl -X POST http://localhost:5000/api/rf/report \
  -H "Content-Type: application/json" \
  -d '{"stations": [...], "format": "pdf", "title": "Relatório RF"}' \
  -o relatorio.pdf

# Relatório DOCX
curl -X POST http://localhost:5000/api/rf/report \
  -H "Content-Type: application/json" \
  -d '{"stations": [...], "format": "docx"}' \
  -o relatorio.docx

# Listar tecnologias suportadas
curl http://localhost:5000/api/rf/technologies
```

---

## Estrutura do Projeto

```
rf_tower_system/
├── run.py                          # Script de inicialização
├── app.py                          # Factory da aplicação Flask
├── config.py                       # Configurações por ambiente
├── Makefile                        # Comandos make (install, run, test, clean)
├── requirements.txt                # Dependências Python
├── README.md                       # Esta documentação
│
├── routes/
│   ├── __init__.py                 # Blueprints kmz_bp e rf_bp
│   ├── kmz_routes.py               # Rotas /api/kmz/*
│   └── rf_routes.py                # Rotas /api/rf/*
│
├── services/
│   ├── excel_parser.py             # Parser de planilhas ANATEL
│   ├── kmz_generator.py            # Gerador de KMZ (torres)
│   ├── kmz_coverage_generator.py   # Gerador de KMZ (cobertura RF)
│   ├── rf_calculator.py            # Modelos de propagação RF
│   └── report_generator.py         # Gerador de relatórios PDF/DOCX
│
├── templates/
│   └── index.html                  # Interface web (dark theme)
│
├── tests/
│   ├── __init__.py
│   ├── test_rf_calculator.py       # Testes unitários do rf_calculator
│   └── test_excel_parser.py        # Testes unitários do excel_parser
│
├── uploads/                        # Arquivos gerados (KMZ, PDF, DOCX)
└── static/icons/                   # Ícones estáticos
```

---

## FAQ

### 1. "Erro: Colunas obrigatórias não encontradas"

Verifique se sua planilha contém **exatamente** os 19 nomes de coluna listados na seção [Estrutura do Excel Esperada](#estrutura-do-excel-esperada). Os nomes são case-sensitive. Faça download do template para conferir.

### 2. "Nenhuma linha com coordenadas válidas para o Brasil"

O sistema filtra coordenadas fora dos limites do Brasil (Lat: -35° a 5°, Lon: -75° a -30°). Verifique se suas coordenadas estão em **graus decimais** (ex: -23.5505, não -23°33'02").

### 3. "Por que o raio de cobertura GSM é menor que o LTE?"

O modelo de propagação considera múltiplos fatores: frequência, potência, ganho da antena e sensibilidade do receptor. Frequências mais baixas (GSM 900 MHz) propagam melhor, mas se a potência e ganho forem menores e a sensibilidade mais exigente, o raio pode ser menor. Cada caso depende dos parâmetros específicos da estação.

### 4. "O KMZ não abre no Google Earth"

Certifique-se de que:
- O arquivo tem extensão `.kmz`
- O Google Earth está atualizado (versão 7.3+)
- O arquivo não está corrompido (verifique o tamanho — deve ser > 1 KB)

### 5. "Como gerar um relatório com várias estações?"

Envie a lista de estações no endpoint `/api/rf/report`:

```json
{
  "stations": [
    {"station_id": "1001", "operadora": "CLARO", "lat": -23.55, "lon": -46.63, "sectors": [...]},
    {"station_id": "2002", "operadora": "TIM", "lat": -23.58, "lon": -46.67, "sectors": [...]}
  ],
  "format": "pdf",
  "title": "Relatório de Cobertura — São Paulo"
}
```

### 6. "Posso usar CSV em vez de Excel?"

Sim! O sistema aceita arquivos `.csv` além de `.xlsx` e `.xls`. O formato das colunas deve ser o mesmo.

### 7. "O que é beamwidth (ângulo de meia potência)?"

É a abertura angular da antena onde o ganho cai 3 dB em relação ao pico. Antenas de painel típicas têm 65°. Antenas omnidirecionais têm 360°.

### 8. "Como funciona a busca binária do raio de cobertura?"

O algoritmo testa distâncias entre 10 m e 50 km, calculando a potência recebida em cada ponto médio. Aplica margem de desvanecimento (8 dB) e penalidade indoor (12 dB em ambientes urbanos). O processo converge com precisão de 10 metros.

### 9. "O servidor não inicia"

Verifique:
```bash
# Python 3.9+
python3 --version

# Dependências instaladas
pip list | grep -i flask

# Porta disponível
lsof -i :5000
```

### 10. "Como contribuir?"

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Execute os testes (`make test`)
4. Commit e push
5. Abra um Pull Request

---

## Licença

Este projeto é distribuído sob licença MIT.

---

**RF Tower System** — Desenvolvido para profissionais de telecomunicações e planejamento de redes móveis.
