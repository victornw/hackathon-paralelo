# Agente com Vercel AI SDK

O agente usa `ToolLoopAgent` do AI SDK 7 em JavaScript/Node.js. As chamadas de
extração e redação usam `generateText`. O provider `@ai-sdk/openai-compatible`
aponta para o Featherless; não há necessidade de Vercel AI Gateway nem de hospedar
na Vercel. Versões exatas estão no `package-lock.json`.

## Executar

Requisitos: Node.js >=22, npm e Python >=3.11.

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --env-file .env
```

As variáveis de modelo/chave continuam sendo as do `.env.example`. A chave é
herdada pelo processo Node pelo ambiente; não é enviada em argumento de shell.
`MODELO_PRINCIPAL` ou `MODELO_DECISAO` habilita o agente quando há chave.
Sem modelo/chave, o modo local segue uma ordem determinística; isso não é uma
execução de agente com LLM. Falha do agente configurado é escalada e não troca
silenciosamente para o loop determinístico.

## Divisão de responsabilidades

- `agent/runtime.mjs`: ToolLoopAgent, provider, ferramentas, seleção dinâmica de
  `activeTools`, limite de passos, fallback de modelo e uso de tokens.
- `agent/worker.mjs`: protocolo JSON por stdin/stdout, privado ao processo pai.
- `app/core/ai_sdk.py`: inicia o worker e atende pedidos de estado/execução/uso.
- `app/core/orquestrador.py`: autoriza novamente cada ferramenta no estado atual;
  mantém persistência, hashes de entrada, tentativas de ferramenta e escalonamento.
- `app/core/llm.py`: mantém validação Pydantic, um reparo de JSON e fallback por
  papel; toda geração passa pelo AI SDK, sem o cliente OpenAI Python.

O SDK controla o loop com modelo. Ferramentas não recebem caminhos nem IDs livres:
o processo alvo fica preso ao contexto da ponte. A ponte só executa nomes
registrados e liberados pelas guardas, sequencialmente. A revisão humana segue
sob as regras já existentes. Esta migração não corrige as lacunas normativas
registradas em `status-dev-a.md`, cujo trabalho foi pausado pelo usuário.

O modelo precisa suportar tool calling. O SDK recebe apenas resumo do processo
para orquestrar; extração recebe o documento necessário. Cada ferramenta continua
com seu trace, e cada passo do modelo registra tokens em `modelo_agente_ai_sdk`.
O fallback consulta o estado persistido e não repete ferramentas concluídas.
O limite é de 30 execuções de ferramentas por rodada; cada modelo também tem
limite de 30 passos do SDK e 600 tokens máximos de saída por passo do agente.
A extração mantém o limite de tempo de 60 segundos por chamada. O worker tem
watchdog de comunicação de 90 segundos e é encerrado ao terminar a rodada.

## Verificação

```sh
npm test
npm run check
.venv/bin/ruff check app/core
.venv/bin/python -m pytest -q
```

Os testes usam o SDK real com provider HTTP simulado localmente. Exercitam o
loop, ferramentas liberadas, retomada, tokens, imagens, parada e a ponte
Python/Node. Não medem a compatibilidade real do modelo Featherless com tool
calling, sua latência ou qualidade; isso exige teste separado com tokens reais.

## Deploy

O runtime precisa de Node **e** Python. O runtime nativo Python do Render já
inclui Node e npm: Docker é opcional, não é requisito da migração.

Configuração recomendada para o serviço existente:

- Branch: `main`; Root Directory: raiz do repositório.
- Runtime: Python (manter o existente).
- Build Command: `pip install -r requirements.txt && npm ci --omit=dev`.
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Node fixado por `.node-version`; remover um `NODE_VERSION` antigo ou ajustá-lo
  para `22.22.0` (a variável tem precedência sobre o arquivo).
- Manter FEATHERLESS_API_KEY, MODELO_PRINCIPAL, MODELO_FALLBACK e MODELO_VISAO
  se houver modelo de visão compatível. Chaves continuam somente no ambiente.
- Manter os caminhos de dados e discos persistentes já configurados.

O `Dockerfile` continua disponível como alternativa. Não há servidor Node público
adicional: a API e a interface seguem no mesmo serviço, e o worker Node é iniciado
por execução. O build Docker ainda não foi validado localmente.

Referências de deploy: [runtimes nativos](https://render.com/docs/native-runtimes)
e [versão do Node](https://render.com/docs/node-version).

Fontes: [ToolLoopAgent](https://ai-sdk.dev/docs/reference/ai-sdk-core/tool-loop-agent)
e [provider compatível](https://ai-sdk.dev/providers/openai-compatible-providers).
