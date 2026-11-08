<p align="center">
  <img src="app/web/static/favicon.svg" alt="" width="96" height="96">
</p>

<h1 align="center">dia · gestão e homologação</h1>

<p align="center">
  Agente de IA que leva a homologação de energia solar residencial da conta de luz ao protocolo na distribuidora.<br>
  O agente monta e confere o pacote técnico; o engenheiro revisa, assina e protocola.
</p>

<p align="center">
  <a href="https://homosun.onrender.com"><b>Demo ao vivo</b></a> ·
  <a href="https://homosun.onrender.com/painel">Carteira</a> ·
  <a href="https://homosun.onrender.com/metricas">Métricas</a> ·
  <a href="https://homosun.onrender.com/portal-gd">Portal GD simulado</a>
</p>

> Projeto do **Converge Challenge powered by Tako** (Porto Digital, Recife, 7 e 8 de novembro de 2026).
> Todos os dados de clientes, contas e kits são sintéticos, e o portal da distribuidora é uma simulação.

---

## O problema

Para ligar um sistema solar residencial à rede, o integrador monta um pacote técnico (formulário de solicitação, memorial descritivo, diagrama unifilar, certificados) e protocola no portal da distribuidora. Hoje isso é trabalho manual, processo por processo:

- 1 em cada 6 pedidos residenciais em Alagoas foi negado por documentação incompleta (ANEEL, pedidos de conexão 2022 a 2023).
- 37% dos integradores terceirizam projeto e engenharia (Greener, 2025), pagando de R$ 400 a R$ 690 por processo a homologadoras.
- Depois do protocolo, prazos do lado do integrador (aprovar orçamento, pedir vistoria) estouram por esquecimento.

O dia entrega o pacote conferido, com engenheiro revisando e assinando, por **até R$ 350 por processo**.

## O que o dia faz

1. **Lê os documentos.** A conta de luz é lida por rótulos e conferida pela IA, campo a campo. A proposta traz o kit (módulos, inversor, strings) e a ficha da visita técnica.
2. **Pergunta só o que falta.** As exigências do pacote viram perguntas objetivas ao integrador e ao engenheiro. Divergência ou dúvida de leitura também vira pergunta, nunca chute.
3. **Gera o pacote.** Solicitação de orçamento (Anexo A da Enel), memorial descritivo e diagrama unifilar (a partir do Anexo B), em PDF.
4. **Confere contra a norma.** Regras em código, cada uma com a fonte normativa (ver [Conferência normativa](#conferência-normativa)). Regra incerta ou reprovada bloqueia a aprovação.
5. **Espera o engenheiro.** Ele baixa o pacote, assina fora do dia (certificado ICP-Brasil ou gov.br), emite a ART, aprova e protocola no portal. Na demo há um botão de protocolo simulado.
6. **Acompanha o portal.** Consulta o status, classifica pendências da distribuidora, prepara a correção, reenvia depois de nova aprovação e vigia os prazos, avisando integrador e cliente final.

O agente escolhe o próximo passo entre os que as guardas do estado liberam (Vercel AI SDK com um modelo Qwen). O modelo nunca decide se uma regra passa nem se um passo pode rodar. Cada passo grava decisão, tokens, tempo e custo, e isso aparece na timeline de cada processo.

**Quem decide continua sendo uma pessoa:** o engenheiro confirma premissas que a norma não fecha sozinha, revisa o pacote, assina a responsabilidade técnica e autoriza cada reenvio.

## Conferência normativa

As regras ficam em [`app/core/regras.py`](app/core/regras.py) e [`app/core/parecer/`](app/core/parecer). Os valores das normas (tabelas, limites, fatores) estão escritos no código de cada regra, com a fonte citada no resultado que o engenheiro vê na revisão.

| Regra | O que confere | Fonte | Situação |
|---|---|---|---|
| R00 | Potência do inversor dentro da potência disponibilizada pelo disjuntor do padrão | Norma Enel CNC-NDBR-DBR-18-0122 v05, 7.2.4 e tabela CNC-OMBR-MAT-18-0124 | Implementada |
| R01 | Coerência dos dados entre solicitação, memorial e unifilar | Prática (erros recorrentes) | Implementada |
| R02 | Disjuntor CA entre a corrente do inversor e a capacidade do cabo; queda de tensão | NBR 5410 (Tabela 36, fatores de temperatura e agrupamento) | Implementada, com premissas declaradas |
| R03 | Tensão das strings no frio, corrente e janela do MPPT | Datasheets do módulo e do inversor | Implementada |
| R04 | Potência dos módulos ≤ potência máxima CC do inversor | Datasheets | Implementada |
| R05 | Inversor com registro INMETRO ativo para 220 V | Norma Enel 7.6.1.4, Tabelas 10 e 11; Portarias INMETRO 140/2022 e 515/2023 | Implementada: consulta o INMETRO; sem resposta, o engenheiro confirma |

Onde estão as normas:

- **Norma da Enel:** cópia local em [`docs/fontes/enel-0122-v05.pdf`](docs/fontes/enel-0122-v05.pdf), com versão, URL oficial e hash em [`docs/fontes/README.md`](docs/fontes/README.md).
- **NBR 5410 e demais NBRs:** não há cópia no repositório (são normas pagas). Só as tabelas usadas estão transcritas em [`app/core/parecer/r02_cabo.py`](app/core/parecer/r02_cabo.py), e o que ainda falta revisar item a item está em [`docs/matriz-normativa.md`](docs/matriz-normativa.md).
- **INMETRO:** consultado ao vivo pelo número do registro; os registros já conferidos à mão ficam em [`app/core/parecer/inmetro_verificados.json`](app/core/parecer/inmetro_verificados.json).
- **Cobertura e lacunas:** [`docs/matriz-normativa.md`](docs/matriz-normativa.md) e [`docs/parecer-regras.md`](docs/parecer-regras.md). A conferência é uma ajuda ao engenheiro, não um atestado de conformidade.

## Medido com o modelo real

| | Resultado | Como foi medido |
|---|---|---|
| Classificação de pendências da distribuidora | 93,8% de acerto (palavras-chave: 50%) | 48 textos sintéticos rotulados antes de rodar o modelo, [`evals/resultados_pendencias.md`](evals/resultados_pendencias.md) |
| Processo completo, da conta ao protocolo | 6 de 6 concluídos; 8 chamadas, ~13 mil tokens e ~90 s de máquina por processo | exemplos 1 e 3, 3 repetições cada, pelo fluxo do produto, [`evals/resultados_processo_completo.md`](evals/resultados_processo_completo.md) |
| Custo de IA por processo | ~R$ 0,07 | preço publicado da Featherless para o Qwen3.8-27B (US$ 0,40 e 3,00 por milhão de tokens), PTAX de 06/11/2026 |

A página [Métricas](https://homosun.onrender.com/metricas) mostra esses números e os da carteira ao vivo. O custo usa o preço publicado da Featherless para o modelo principal.

## Como testar a demo

1. Abra **Novo processo** e escolha um exemplo. A página mostra a conta e a proposta que vão para o agente; clique em **Começar**.
2. Acompanhe os passos do agente ao vivo. As perguntas que sobrarem chegam pré-preenchidas: clique em **Responder**.
3. Em **Revisar e assinar**, confira as regras, confirme a R05 se for pedido, baixe o pacote, aprove e use **Protocolar automaticamente (simulação)**.
4. Avance o relógio simulado no topo da página (ou em **Operador**) para ver o portal andar: orçamento, pendência, vistoria, ligação. O agente avisa o integrador e o cliente final no chat.

**Operador** faz o papel da distribuidora e reinicia a demonstração com os quatro casos prontos.

## Rodar localmente

Requisitos: Python 3.11+, Node 22+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
npm ci                      # Vercel AI SDK usado pelo agente
cp .env.example .env        # preencha FEATHERLESS_API_KEY e MODELO_PRINCIPAL
set -a; . ./.env; set +a
.venv/bin/uvicorn app.main:app --reload
```

Abra http://localhost:8000. Sem chave de IA o app funciona com o leitor por rótulos e a ordem de passos determinística; a leitura da proposta e a classificação de pendências precisam do modelo.

Testes e evals:

```bash
.venv/bin/pytest -q                                              # suíte completa, sem rede
npm test                                                         # agente (Node)
.venv/bin/python -m evals.pendencias                             # classificação de pendências (LLM real)
.venv/bin/python -m evals.processo_completo --casos 1 3 --repeticoes 3
```

### Variáveis de ambiente

| Variável | Para quê |
|---|---|
| `FEATHERLESS_API_KEY`, `FEATHERLESS_BASE_URL` | Acesso ao modelo (API compatível com a OpenAI) |
| `MODELO_PRINCIPAL`, `MODELO_FALLBACK` | Modelo de todos os papéis e o reserva quando ele falha |
| `MODELO_EXTRACAO`, `MODELO_VISAO`, `MODELO_DECISAO`, `MODELO_REDACAO`, `MODELO_PENDENCIA` | Opcionais: um modelo por papel. Leitura de imagem só roda com `MODELO_VISAO` |
| `DB_PATH`, `DOCS_DIR`, `UPLOADS_DIR` | Banco SQLite local, PDFs gerados e arquivos enviados |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Opcionais: cópia do banco no Turso, para sobreviver a reinícios do servidor |
| `LLM_PRECO_ENTRADA_USD_MTOK`, `LLM_PRECO_SAIDA_USD_MTOK`, `USD_BRL` | Preço por milhão de tokens e câmbio usados no custo de cada passo |
| `RELOGIO_INICIO`, `FERIADOS_UF` | Data inicial do relógio simulado e feriados estaduais nos prazos em dias úteis |

## Arquitetura

```
app/
  core/          orquestrador do agente, leitura de documentos, perguntas, regras e aprovação
  core/parecer/  regras R00, R02, R03 e R05 com os casos do parecer do engenheiro
  docs/          geração do Anexo A, memorial e unifilar em PDF
  portal_sim/    Portal GD simulado, relógio, prazos, pendências e mensagens
  tracing/       rastro de cada passo (decisão, tokens, tempo, custo) e prompts versionados
  web/           telas (FastAPI + Jinja): carteira, processo, revisão, chat, métricas
agent/           runtime do agente em Node (Vercel AI SDK)
evals/           avaliações com o modelo real e os resultados
fixtures/        contas, propostas e casos sintéticos
docs/            fontes normativas, matriz de cobertura, evidências e material do pitch
```

- **Backend:** Python, FastAPI, Jinja2, Pydantic; PDFs com fpdf2 e leitura com pypdf.
- **Agente:** guardas determinísticas por passo; o Vercel AI SDK (`ai`, `@ai-sdk/openai-compatible`) escolhe a ordem entre os passos liberados.
- **Dados:** SQLite local, com cópia opcional no Turso (libSQL).
- **Deploy:** Docker no Render. `GET /saude` mostra o commit publicado e se a IA está configurada.

## Ferramentas, modelos e APIs de terceiros

- **Featherless** (API compatível com a OpenAI) com **Qwen/Qwen3.8-27B** e fallback **Qwen/Qwen3.8-Flash-Next**
- **Vercel AI SDK** (`ai`, `@ai-sdk/openai-compatible`, `zod`)
- **INMETRO**, consulta pública de registro de equipamentos
- **Turso** (libSQL) para persistência; **Render** para hospedagem
- Bibliotecas Python: FastAPI, Uvicorn, Jinja2, Pydantic, fpdf2, pypdf, holidays, libsql
- Dados públicos da **ANEEL** (pedidos de conexão) para a evidência do problema e os evals de pendência
- Desenvolvido com apoio de assistentes de código (Claude Code)

## Limitações

- Distribuidora coberta: Enel Ceará, residencial, monofásico, até 10 kW. O portal é simulado; não há integração com o portal real.
- A assinatura digital e a ART são feitas fora do dia, pelo engenheiro.
- As NBRs não foram revisadas item a item (ver a matriz normativa).
