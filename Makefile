.PHONY: install run test clean lint

PYTHON := python3
PIP := pip3
PYTEST := pytest
APP := run.py
TEST_DIR := tests

install:
	$(PIP) install -r requirements.txt
	@echo "[OK] Dependências instaladas."

run:
	$(PYTHON) $(APP)

test:
	$(PYTEST) $(TEST_DIR)/ -v

test-rf:
	$(PYTEST) $(TEST_DIR)/test_rf_calculator.py -v

test-excel:
	$(PYTEST) $(TEST_DIR)/test_excel_parser.py -v

clean:
	@rm -rf uploads/*.xlsx uploads/*.kmz uploads/*.pdf uploads/*.docx 2>/dev/null || true
	@rm -rf __pycache__ services/__pycache__ routes/__pycache__ tests/__pycache__ 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "[OK] Arquivos temporários removidos."

lint:
	@echo "Verificando sintaxe Python..."
	$(PYTHON) -m py_compile $(APP) || exit 1
	$(PYTHON) -m py_compile app.py || exit 1
	$(PYTHON) -m py_compile services/rf_calculator.py || exit 1
	$(PYTHON) -m py_compile services/kmz_generator.py || exit 1
	$(PYTHON) -m py_compile services/kmz_coverage_generator.py || exit 1
	$(PYTHON) -m py_compile services/report_generator.py || exit 1
	$(PYTHON) -m py_compile services/excel_parser.py || exit 1
	$(PYTHON) -m py_compile routes/kmz_routes.py || exit 1
	$(PYTHON) -m py_compile routes/rf_routes.py || exit 1
	@echo "[OK] Todos os arquivos compilam sem erros."
