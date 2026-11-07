"""Assinaturas das funções que cruzam as duas fatias.

Cada dev implementa as suas e pode importar as do outro desde o primeiro
minuto: enquanto não estiverem prontas, elas levantam NotImplementedError
e a tela usa a fixture. Mudar uma assinatura aqui = avisar no chat.

Sugestão de onde mover cada função quando for implementada:
- Fatia 1 (Dev A): app/core/
- Fatia 2 (Dev B): app/docs/, app/portal_sim/, app/tracing/
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from app.schemas import (
    CampoExtraido,
    DadosVisita,
    DocumentoGerado,
    EventoPortal,
    Kit,
    Pergunta,
    Prazo,
    Processo,
    ResultadoRegra,
)

# ===========================================================================
# FATIA 1 — Dev A (antes do envio)
# ===========================================================================


def extrair_conta(arquivo: Path) -> dict[str, CampoExtraido]:
    """Lê a conta de luz (PDF ou imagem) e devolve os campos com confiança.

    Chaves: ver comentário em schemas.py (uc, titular, endereco, ...).
    Nunca inventa valor: campo ilegível volta com valor=None e confiança baixa.
    """
    raise NotImplementedError


def extrair_kit(arquivos: list[Path]) -> Kit:
    """Lê a proposta/kit e os datasheets e monta o Kit.

    Se a configuração de strings não vier, deixa `strings` vazio;
    quem propõe a configuração é verificar_arranjo.
    """
    raise NotImplementedError


def extrair_padrao(foto: Path) -> DadosVisita:
    """Lê a foto do padrão de entrada: disjuntor geral e número de polos."""
    raise NotImplementedError


def verificar_arranjo(kit: Kit, visita: DadosVisita) -> tuple[Kit, DadosVisita, list[ResultadoRegra]]:
    """Confere o kit vendido (R03, R04), propõe strings se faltarem
    (marcadas sugerida=True) e seleciona disjuntor CA e cabo por tabela.

    Devolve o kit e a visita atualizados e os resultados das regras.
    """
    raise NotImplementedError


def conferir(processo: Processo) -> list[ResultadoRegra]:
    """Aplica R01 a R05 sobre o processo completo (inclui coerência entre
    campos e documentos gerados). Sem dado suficiente -> INCERTA."""
    raise NotImplementedError


def perguntas_pendentes(processo: Processo) -> list[Pergunta]:
    """Lista o que falta para fechar o pacote (relação de cargas, disjuntor
    do padrão, bitola, configuração de strings...)."""
    raise NotImplementedError


def orquestrar(processo_id: str) -> Processo:
    """Recebe "homologar este sistema", decide o próximo passo, chama as
    ferramentas das duas fatias e registra cada decisão no trace."""
    raise NotImplementedError


# ===========================================================================
# FATIA 2 — Dev B (documentos e depois do envio)
# ===========================================================================


def gerar_documentos(processo: Processo) -> list[DocumentoGerado]:
    """Gera a solicitação de orçamento (Anexo A, PDF), o memorial descritivo
    (PDF, formato nosso) e o unifilar (template SVG baseado no Anexo B + PDF)."""
    raise NotImplementedError


def protocolar(processo: Processo) -> str:
    """Envia o formulário básico ao portal simulado (mesmos campos do Portal GD
    da Enel CE) e devolve o número da solicitação."""
    raise NotImplementedError


def consultar_status(uc: str, email: str, numero_solicitacao: str) -> list[EventoPortal]:
    """Consulta o portal simulado como no Portal GD real (UC, e-mail e número
    da solicitação) e devolve os eventos em ordem."""
    raise NotImplementedError


def avancar_tempo(dias: int) -> date:
    """Avança o relógio simulado e devolve a nova data."""
    raise NotImplementedError


def hoje() -> date:
    """Data atual no relógio simulado. Use sempre esta função, nunca date.today()."""
    raise NotImplementedError


def calcular_prazos(processo: Processo) -> list[Prazo]:
    """Calcula os prazos correndo a partir dos eventos do processo: 10 dias
    úteis para aprovar o orçamento, 30 dias para sanar pendência, 30 dias para
    devolver contratos, 15/30 dias do orçamento e 5 dias úteis da vistoria.
    Dias úteis consideram fins de semana e feriados."""
    raise NotImplementedError


def classificar_pendencia(texto: str) -> tuple[str, str]:
    """Classifica o motivo de pendência numa das categorias combinadas e
    devolve (categoria, correcao_proposta)."""
    raise NotImplementedError


def trace(nome_passo: str) -> Callable:
    """Decorador que grava um PassoTrace (tempo, tokens, custo, decisão, erro).

    Uso pelo Dev A:
        @trace("extrair_conta")
        def extrair_conta(...): ...

    Para registrar tokens e decisão de dentro da função, o Dev B pode expor
    um helper, por exemplo registrar_uso(tokens_entrada, tokens_saida, decisao).
    """
    raise NotImplementedError