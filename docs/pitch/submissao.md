# Texto da submissão (rascunho)

## Descrição do projeto

**Problema.** Para ligar um sistema solar residencial à rede, o integrador precisa montar e protocolar um pacote técnico na distribuidora: formulário, memorial descritivo, diagrama unifilar, certificados e responsabilidade técnica. Esse trabalho é feito à mão por engenheiros, processo por processo. Erro documental faz o pedido voltar: segundo a base de pedidos de conexão da ANEEL (2022–2023), 1 em cada 6 pedidos residenciais em Alagoas foi negado por documentação incompleta. Por isso, 37% dos integradores terceirizam projeto e engenharia (Greener, 2025), pagando de R$ 400 a R$ 690 por processo a homologadoras.

**Para quem.** Integradores de energia solar pequenos e médios, que vendem poucos sistemas por mês e não sustentam um engenheiro dedicado à homologação.

**Solução.** Uma homologadora operada por IA. O agente lê a conta de luz e a proposta do kit, pergunta só o que falta, gera o formulário, o memorial e o unifilar no padrão da norma da Enel, confere tudo contra a norma antes do envio e acompanha o processo depois do protocolo. Um engenheiro revisa e assina; o agente faz o resto. Com isso, cada engenheiro atende muito mais processos, e o serviço pode custar menos que o das homologadoras atuais.

**Como o agente funciona.**
- Extração: leitor determinístico para o layout da conta suportada e LLM com esquema fixo para propostas e outros layouts. A confiança de cada campo é calculada (cai quando o trecho citado não está no documento ou o formato não confere), nunca aceita do modelo.
- Pedido do que falta: uma tabela de exigências do pacote da Enel gera perguntas objetivas ao integrador e ao engenheiro.
- Conferência: regras em código determinístico com a fonte normativa de cada uma (norma Enel CNC-NDBR-DBR-18-0122, NBR 5410, Portaria INMETRO 140/2022). Dado ausente ou premissa não confirmada deixa a regra incerta e bloqueia a aprovação; documento com campo "A INFORMAR" também bloqueia.
- Decisão do próximo passo: o código lista os passos permitidos pelo estado do processo; com mais de uma opção, o LLM escolhe entre elas; com uma só, o passo roda sem chamar o modelo. Falha de ferramenta tenta de novo e, se persistir, vira pergunta ao engenheiro com o contexto, sem derrubar o processo.
- Depois do protocolo: portal simulado no formato do Portal GD da Enel, classificação de pendências por LLM com categorias fixas, correção, reenvio após nova revisão do engenheiro, e prazos do integrador vigiados com a fonte normativa.
- Rastro: cada passo grava decisão, tokens, tempo e custo, exibidos na linha do tempo do processo.

**Resultados medidos (dados sintéticos).**
- Classificação de pendências: 93,8% de acerto em 48 textos rotulados antes de rodar o modelo, contra 50% de uma linha de base por palavras-chave.
- Processo completo com o modelo real: cerca de 3 mil tokens e 30 a 40 segundos de LLM por processo, cerca de R$ 0,005 a preço de referência de mercado.
- [Tempo de revisão humana por pacote: preencher com a medição de `docs/medicao-revisao.md`.]

Os dados de clientes, contas e kits da demonstração são sintéticos.

## Ferramentas, modelos e APIs de terceiros

- **Modelos:** Qwen/Qwen3.8-27B (principal) e Qwen/Qwen3.8-Flash-Next (fallback), via API da Featherless.
- **Orquestração de LLM:** Vercel AI SDK (`ai`, `@ai-sdk/openai-compatible`) em Node.js, com zod.
- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLite, Jinja2, python-multipart.
- **Documentos:** fpdf2 (PDF) e pypdf (leitura de PDF).
- **Prazos:** biblioteca holidays (feriados).
- **Front:** HTMX.
- **Dados públicos:** ANEEL, dados abertos de pedidos de conexão MMGD; consulta pública de registros do INMETRO; normas técnicas da Enel.
- **Hospedagem:** Render.
- **Ferramentas de código com IA usadas no desenvolvimento:** Claude Code e Codex.

## Desafio Tako

Não se aplica: o projeto não responde ao desafio de RH.
