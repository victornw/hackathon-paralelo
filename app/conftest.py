"""Configuração comum dos testes: nenhum teste depende de rede externa."""

import pytest


@pytest.fixture(autouse=True)
def sem_consulta_externa(monkeypatch):
    # A R05 consulta o INMETRO; nos testes a consulta falha como site fora do ar.
    # Os testes da R05 simulam a página trocando r05_inmetro._baixar.
    monkeypatch.setenv("INMETRO_CONSULTA", "0")
