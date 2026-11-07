"""Classificador de pendência: categorias fixas + correção proposta.

Duas implementações:
- classificar_por_palavras: linha de base determinística (palavras-chave), usada
  no eval como comparação e como fallback quando o LLM falha ou não está configurado.
- classificar_pendencia: o contrato. Usa o LLM quando houver um configurado
  (a ligar quando o provedor for definido); sem LLM, cai na linha de base.

Categorias escritas a partir das categorias de motivo da base ANEEL e das
cartilhas de reprovação (Cemig 2025, Neoenergia).
"""

from __future__ import annotations

import re
import unicodedata

from app.tracing import registrar_uso, trace

CATEGORIAS: dict[str, dict] = {
    "unifilar_inconsistente": {
        "descricao": "Diagrama unifilar incompleto ou divergente da norma",
        "correcao": "Corrigir o diagrama unifilar (incluir a proteção ou o elemento apontado, "
        "conforme Anexo B da norma Enel) e reenviar.",
        "palavras": [
            "unifilar",
            "diagrama",
            "dps",
            "surto",
            "seccionadora",
            "aterramento",
        ],
    },
    "dados_divergentes": {
        "descricao": "Dado divergente entre documentos ou com o cadastro",
        "correcao": "Alinhar o dado divergente (titular, UC, potência, quantidade de módulos ou "
        "modelo do inversor) em solicitação, memorial e unifilar e reenviar.",
        "palavras": [
            "diverg",
            "inconsist",
            "nao confere",
            "difere",
            "titular",
            "potencia",
        ],
    },
    "documentacao_incompleta": {
        "descricao": "Documento obrigatório ausente ou ilegível",
        "correcao": "Anexar o documento ausente ou legível (procuração, documento do titular, "
        "relação de cargas) e reenviar.",
        "palavras": [
            "ausente",
            "falta",
            "nao apresent",
            "ilegivel",
            "procuracao",
            "anexar",
        ],
    },
    "art_irregular": {
        "descricao": "ART ausente, sem quitação ou com atividade incompatível",
        "correcao": "Pedir ao responsável técnico a ART correta (projeto e execução, quitada) e "
        "reenviar; mudança só documental mantém a ART.",
        "palavras": [
            "art ",
            "art,",
            "art.",
            "anotacao de responsabilidade",
            "crea",
            "quitacao",
        ],
    },
    "inversor_certificacao": {
        "descricao": "Inversor sem certificado INMETRO válido para a tensão de conexão",
        "correcao": "Anexar o certificado INMETRO do inversor (Portaria 140/2022) para 220 V ou "
        "trocar por modelo certificado.",
        "palavras": ["inmetro", "certificado", "certificacao", "portaria 140"],
    },
    "localizacao": {
        "descricao": "Coordenada ou endereço do padrão divergente",
        "correcao": "Conferir as coordenadas do padrão de entrada no local e corrigir o "
        "endereço/coordenada no formulário.",
        "palavras": ["coordenad", "latitude", "longitude", "localizacao", "endereco"],
    },
    "padrao_entrada": {
        "descricao": "Padrão de entrada ou disjuntor fora da norma",
        "correcao": "Adequar o padrão de entrada ou o disjuntor à norma de fornecimento da Enel e "
        "enviar foto atualizada.",
        "palavras": ["padrao de entrada", "disjuntor", "caixa de medicao", "ramal"],
    },
    "outros": {
        "descricao": "Motivo não coberto pelas categorias",
        "correcao": "Encaminhar ao engenheiro: motivo fora das categorias conhecidas.",
        "palavras": [],
    },
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()) + " "


def classificar_por_palavras(texto: str) -> str:
    """Categoria com mais palavras-chave; empate segue a ordem de CATEGORIAS."""
    t = _normalizar(texto)
    melhor, pontos = "outros", 0
    for nome, cat in CATEGORIAS.items():
        n = sum(t.count(p) for p in cat["palavras"])
        if n > pontos:
            melhor, pontos = nome, n
    return melhor


def correcao(categoria: str) -> str:
    return CATEGORIAS[categoria]["correcao"]


@trace("classificar_pendencia")
def classificar_pendencia(texto: str) -> tuple[str, str]:
    """Classifica o motivo de pendência e devolve (categoria, correcao_proposta)."""
    categoria = classificar_por_palavras(texto)
    registrar_uso(decisao=f"Pendência classificada como {categoria} (palavras-chave).")
    return categoria, correcao(categoria)
