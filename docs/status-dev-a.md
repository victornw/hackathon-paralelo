# Auditoria do núcleo Dev A — 07/11/2026

Trabalho normativo pausado por solicitação do usuário para migrar o agente ao
Vercel AI SDK. A migração está descrita em [ai-sdk.md](ai-sdk.md).

Status: implementação parcial, ainda sem comprovação de conformidade normativa
do pacote gerado. Ter módulos e testes unitários não fecha uma etapa da spec.

## Evidências e lacunas

| Frente | Evidência atual | Falta para concluir |
|---|---|---|
| Fontes normativas | `app/core/regras.py` cita NBR 5410, norma Enel e Portaria INMETRO 140/2022; os documentos também citam outras normas | Matriz de requisitos aplicáveis ao recorte Enel CE até 10 kW, com versão, item, fonte verificável, implementação, teste e exclusões explícitas. O registro atual não possui seleção por distribuidora/data de vigência como a spec propõe |
| R01, documentos | Relê PDF/SVG e busca titular, UC, modelos, quantidade de módulos e disjuntor CA em alguns documentos | Cobrir os demais campos previstos na spec, inclusive potência e DPS; verificar valores associados aos campos e divergências, não apenas presença do valor esperado; ampliar testes com adulteração dos arquivos |
| R02, cabo/disjuntor | Compara corrente, disjuntor e capacidade de uma tabela fixa | Validar fonte e condições de aplicação da tabela; tratar premissas não confirmadas; distinguir disjuntor sugerido de confirmado. O código pode retornar APROVADA mesmo com tabela marcada a validar |
| R03, tensão | Calcula Voc a frio com temperatura mínima fixa de 10 °C | Confirmar premissa para a instalação e proveniência do coeficiente. O cálculo pode retornar APROVADA com premissa ainda a validar |
| R04, potência | Compara potência total dos módulos ao limite CC no objeto do processo | Comprovar a origem das especificações e a correspondência dos valores publicados nos documentos |
| R05, INMETRO | Verifica presença de uma string de registro, sem consultar validade | Comprovar registro/certificado do modelo e tensão; presença de número não significa certificação verificada |
| Documentos | Gera solicitação, memorial e unifilar de 1/2 MPPTs | Confrontar campos e conteúdo com exigências aplicáveis; identificar pendências obrigatórias; revisar desenhos e formato. O memorial imprime especificação de DPS como A INFORMAR e campos de ART/CREA em branco |
| Conta degradada | Caminho de visão implementado; testes de encaminhamento com LLM falso | Corpus de 10–20 contas e degradações com gabarito, execução real e métricas por campo, incerteza e erros confiantes. Não há esse eval no repositório |
| Datasheets reais | Extrator de PDF textual, com complemento por catálogo; testes sintéticos | PDFs oficiais de fabricantes com modelo/variante, URL, versão/página e gabarito; validar extração real e proveniência por especificação. O catálogo atual é explicitamente sintético, inclusive registros SIM-*; não usar como evidência de produto certificado |
| Fluxo e aprovação | Encadeamento e revisão humana implementados; regras reprovadas bloqueiam revisão/aprovação | Tornar explícito o tratamento de cada incerteza e premissa pendente; distinguir encaminhamento à revisão de conformidade comprovada; verificar bloqueios em execução completa |

R02–R05 operam sobre os dados estruturados. Não validam integralmente os
arquivos gerados. R06–R08 são explicitamente não verificadas, fora do MVP.

## Critério de conclusão

Uma etapa só deve ser reportada como concluída quando tiver entradas e saídas
definidas, fontes verificáveis, testes relevantes executados e limitações
explícitas. Teste com modelo real sobre documento sintético não é validação de
datasheet real. Referência impressa a uma norma não é comprovação de atendimento.

Na extração, dado ilegível ou sem evidência deve ficar incerto e gerar pedido de
confirmação; o objetivo não é prometer acerto absoluto. Na conferência, qualquer
exigência aplicável sem evidência deve ser identificada e resolvida ou escalada,
sem ser apresentada como verificada. Revisão humana não substitui verificações
que a spec atribui ao sistema.

## Ordem de fechamento

1. Fontes e matriz normativa/documental do recorte do MVP.
2. Dados reais de fabricantes e proveniência das especificações usadas.
3. Correção dos critérios de aprovação e conferência dos artefatos gerados.
4. Evals reais de extração textual e de imagens degradadas, com consumo por chamada.
5. Validação completa do fluxo e revisão técnica das premissas e documentos.

Não avançar em funcionalidades periféricas antes de fechar essas evidências.
