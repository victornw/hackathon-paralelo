"""Contratos de dados do agente de homologação solar.

Este arquivo é compartilhado entre os dois devs. Qualquer mudança aqui
deve ser avisada no chat e enviada num commit pequeno e isolado.

Persistência sugerida: uma tabela `processos(id, json)` com o Processo
serializado via `model_dump_json()`, e uma tabela `passos_trace` com PassoTrace.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Etapa(str, Enum):
    MONTAGEM = "montagem"
    EM_REVISAO = "em_revisao"
    PROTOCOLADO = "protocolado"
    PENDENCIA = "pendencia"
    ORCAMENTO_EMITIDO = "orcamento_emitido"  # 10 dias úteis para aprovar
    ORCAMENTO_APROVADO = "orcamento_aprovado"
    VISTORIA_SOLICITADA = "vistoria_solicitada"
    VISTORIA = "vistoria"
    MEDIDOR = "medidor"
    CONCLUIDO = "concluido"


class StatusRegra(str, Enum):
    APROVADA = "aprovada"
    REPROVADA = "reprovada"
    INCERTA = "incerta"  # faltou dado ou a regra exige julgamento
    NAO_VERIFICADA = "nao_verificada"  # fora da cobertura das regras


class Camada(str, Enum):
    FEDERAL = "federal"
    TECNICA = "tecnica"
    DISTRIBUIDORA = "distribuidora"


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------


class Fonte(BaseModel):
    """De onde veio um dado."""

    documento: str  # ex.: "conta_luz.pdf", "foto_padrao.jpg", "resposta_integrador"
    pagina: int | None = None
    trecho: str | None = None  # texto lido, para mostrar na tela de revisão


class CampoExtraido(BaseModel):
    """Um campo lido de um documento, com confiança."""

    valor: str | float | int | None
    confianca: float = Field(ge=0, le=1)
    fonte: Fonte | None = None

    @property
    def incerto(self) -> bool:
        return self.valor is None or self.confianca < 0.8


# Chaves esperadas em Processo.campos (vindas da conta de luz da Enel CE):
# "uc", "titular", "cpf_cnpj", "endereco", "cidade", "classe", "subgrupo" (ex.: "B1"),
# "tipo_ligacao" ("monofasico" | "bifasico" | "trifasico"),
# "tensao_atendimento_v" (monofásico na Enel CE: 220), "consumo_medio_kwh"


# ---------------------------------------------------------------------------
# Kit vendido e dados da visita
# ---------------------------------------------------------------------------


class Modulo(BaseModel):
    fabricante: str
    modelo: str
    potencia_wp: float
    voc_v: float
    isc_a: float
    vmp_v: float | None = None
    imp_a: float | None = None
    coef_temp_voc_pct_c: float | None = None  # ex.: -0.27 (%/°C)


class Inversor(BaseModel):
    fabricante: str
    modelo: str
    potencia_nominal_w: float
    potencia_max_cc_w: float
    tensao_max_cc_v: float
    mppt_min_v: float | None = None
    mppt_max_v: float | None = None
    num_mppt: int = 1
    corrente_max_entrada_a: float | None = None  # por MPPT
    corrente_max_saida_a: float
    tensao_saida_v: float = 220
    microinversor: bool = False
    certificado_inmetro: str | None = None  # número do registro, se houver


class StringFV(BaseModel):
    mppt: int  # 1, 2...
    modulos_em_serie: int
    sugerida: bool = False  # True quando o agente propôs e falta confirmar


class Kit(BaseModel):
    modulo: Modulo
    qtd_modulos: int
    inversor: Inversor
    strings: list[StringFV] = []

    @property
    def potencia_total_wp(self) -> float:
        return self.modulo.potencia_wp * self.qtd_modulos


class Carga(BaseModel):
    descricao: str  # ex.: "ar-condicionado 12.000 BTU"
    potencia_w: float
    quantidade: int = 1


class DadosVisita(BaseModel):
    """O que vem da visita técnica, da foto do padrão ou das respostas do integrador.

    Tudo opcional: o que faltar vira Pergunta, e a regra que depende do dado
    fica INCERTA.
    """

    disjuntor_padrao_a: CampoExtraido | None = None
    polos_padrao: CampoExtraido | None = None  # 1, 2 ou 3
    tipo_ramal: Literal["aereo", "subterraneo"] | None = None  # pedido no Portal GD
    latitude: float | None = None  # coordenadas do padrão, pedidas no Portal GD
    longitude: float | None = None
    distancia_inversor_quadro_m: float | None = None
    bitola_ca_mm2: float | None = None
    disjuntor_ca_a: float | None = None  # selecionado pela tabela
    relacao_cargas: list[Carga] = []


# ---------------------------------------------------------------------------
# Conferência e perguntas
# ---------------------------------------------------------------------------


class ResultadoRegra(BaseModel):
    regra_id: str  # "R01".."R05"
    descricao: str  # ex.: "Disjuntor CA entre corrente de projeto e capacidade do cabo"
    camada: Camada
    status: StatusRegra
    valores: dict[str, float | str] = {}  # ex.: {"corrente_saida_a": 52.8, "disjuntor_a": 50}
    mensagem: str  # ex.: "Corrente máxima de saída (52,8 A) acima do disjuntor de 50 A."
    fonte_norma: str  # ex.: "NBR 5410"
    a_validar: bool = False  # True para critérios ainda não validados por engenheiro


class Pergunta(BaseModel):
    id: str
    campo: str  # ex.: "relacao_cargas", "disjuntor_padrao_a"
    texto: str  # pergunta objetiva, em português
    destinatario: Literal["integrador", "engenheiro"] = "integrador"
    resposta: str | None = None
    respondida_em: datetime | None = None


# ---------------------------------------------------------------------------
# Documentos, portal e prazos
# ---------------------------------------------------------------------------


class DocumentoGerado(BaseModel):
    # solicitacao_orcamento = Anexo A da norma Enel; unifilar baseado no Anexo B;
    # memorial em PDF num formato nosso (a Enel não fornece modelo até 10 kW)
    tipo: Literal["solicitacao_orcamento", "memorial", "unifilar"]
    nome_arquivo: str
    caminho: str  # caminho local ou URL de download
    formato: Literal["pdf", "svg"]
    gerado_em: datetime


class EventoPortal(BaseModel):
    numero_solicitacao: str
    etapa: Etapa
    descricao: str
    data: date  # data no relógio simulado
    motivo_pendencia: str | None = None  # texto como a distribuidora escreveria
    categoria_pendencia: str | None = None  # preenchido pelo classificador
    correcao_proposta: str | None = None


class Prazo(BaseModel):
    # orcamento: 15 dias sem obras / 30 com obras (distribuidora, REN 1.000 art. 64)
    # aprovar_orcamento: 10 dias úteis (integrador, norma Enel 7.3.5, REN 1.000 art. 83)
    # devolver_contratos: 30 dias (integrador, REN 1.000 art. 83 § 7º III)
    # sanar_pendencia: 30 dias (integrador, Lei 14.300, artigo a confirmar)
    # vistoria_ligacao: 5 dias úteis (distribuidora, norma Enel Tabela 8)
    tipo: Literal[
        "orcamento", "aprovar_orcamento", "devolver_contratos", "sanar_pendencia", "vistoria_ligacao"
    ]
    inicio: date
    dias: int
    dias_uteis: bool = False
    vencimento: date
    conta_contra: Literal["integrador", "distribuidora"]
    fonte: str  # texto mostrado na interface, ex.: "Norma Enel 7.3.5; REN 1.000, art. 83"


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------


class PassoTrace(BaseModel):
    processo_id: str
    passo: str  # ex.: "extrair_conta", "conferir", "decidir_proximo_passo"
    decisao: str | None = None  # o que o agente decidiu, em uma frase
    tokens_entrada: int = 0
    tokens_saida: int = 0
    ms: int = 0
    custo_brl: float = 0.0
    erro: str | None = None
    em: datetime


# ---------------------------------------------------------------------------
# O processo
# ---------------------------------------------------------------------------


class Processo(BaseModel):
    id: str
    criado_em: datetime
    etapa: Etapa = Etapa.MONTAGEM
    distribuidora: str = "enel_ce"
    email_contato: str | None = None  # a consulta no Portal GD usa UC + e-mail + nº da solicitação

    campos: dict[str, CampoExtraido] = {}  # dados da conta de luz
    kit: Kit | None = None
    visita: DadosVisita = Field(default_factory=DadosVisita)

    regras: list[ResultadoRegra] = []
    perguntas: list[Pergunta] = []
    documentos: list[DocumentoGerado] = []

    revisado_por: str | None = None
    revisado_em: datetime | None = None

    numero_solicitacao: str | None = None
    eventos: list[EventoPortal] = []
    prazos: list[Prazo] = []

    simulacao: bool = True  # dados sintéticos; a interface mostra o selo