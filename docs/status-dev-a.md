# Auditoria do núcleo Dev A — 07/11/2026

Trabalho normativo retomado após a migração para o Vercel AI SDK.
Matriz inicial e política de bloqueios em [matriz-normativa.md](matriz-normativa.md).

Status: implementação parcial, ainda sem comprovação de conformidade normativa
do pacote gerado. Ter módulos e testes unitários não fecha uma etapa da spec.

## Evidências e lacunas

| Frente | Evidência atual | Falta para concluir |
|---|---|---|
| Fontes normativas | `app/core/regras.py` cita NBR 5410, norma Enel e Portaria INMETRO 140/2022; os documentos também citam outras normas | Matriz inicial criada em matriz-normativa.md; falta fechar todos os requisitos aplicáveis com evidência e testes. O registro atual não possui seleção por distribuidora/data de vigência como a spec propõe |
| R01, documentos | Relê PDF/SVG e busca titular, UC, modelos, quantidade de módulos e disjuntor CA em alguns documentos | Cobrir os demais campos previstos na spec, inclusive potência e DPS; verificar valores associados aos campos e divergências, não apenas presença do valor esperado; ampliar testes com adulteração dos arquivos |
| R02, cabo/disjuntor | Compara corrente, disjuntor e capacidade de uma tabela fixa | Validar fonte e condições de aplicação da tabela; tratar premissas não confirmadas; distinguir disjuntor sugerido de confirmado. Agora retorna INCERTA enquanto a tabela estiver marcada a validar |
| R03, tensão | Calcula Voc a frio com temperatura mínima fixa de 10 °C | Confirmar premissa para a instalação e proveniência do coeficiente. Agora retorna INCERTA com premissa ainda a validar |
| R04, potência | Compara potência total dos módulos ao limite CC no objeto do processo | Comprovar a origem das especificações e a correspondência dos valores publicados nos documentos |
| R05, INMETRO | Retorna INCERTA mesmo com número preenchido, sem consultar validade | Comprovar registro/certificado do modelo e tensão; presença de número não significa certificação verificada |
| Documentos | Gera solicitação, memorial e unifilar de 1/2 MPPTs | Confrontar campos e conteúdo com exigências aplicáveis; identificar pendências obrigatórias; revisar desenhos e formato. O memorial imprime especificação de DPS como A INFORMAR e campos de ART/CREA em branco |
| Conta degradada | Caminho de visão implementado; testes de encaminhamento com LLM falso | Corpus de 10–20 contas e degradações com gabarito, execução real e métricas por campo, incerteza e erros confiantes. Não há esse eval no repositório |
| Datasheets reais | Extrator de PDF textual, com complemento por catálogo; testes sintéticos | PDFs oficiais de fabricantes com modelo/variante, URL, versão/página e gabarito; validar extração real e proveniência por especificação. O catálogo atual é explicitamente sintético, inclusive registros SIM-*; não usar como evidência de produto certificado |
| Fluxo e aprovação | Encadeamento e revisão humana implementados; regras obrigatórias ausentes, duplicadas, incertas ou a validar bloqueiam aprovação/protocolo/reenvio | Tornar explícito o tratamento de cada incerteza e premissa pendente; distinguir encaminhamento à revisão de conformidade comprovada; verificar bloqueios em execução completa |

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


## Rodada retomada

A política de bloqueios das R01–R05 foi implementada em `app/core/aprovacao.py`
e aplicada à aprovação HTTP, ao protocolo e ao reenvio. A API refaz a conferência
antes de aceitar uma aprovação que tenha resultados prévios favoráveis.
Os testes reais do pacote sintético comprovam que ele fica bloqueado, enquanto
os testes de transições posteriores usam conferência explicitamente simulada.

Consequência operacional: como as premissas R02/R03 e a comprovação R05 ainda
não foram fechadas, os pacotes atuais podem ir para revisão, mas não podem ser
aprovados/protocolados pelo fluxo real. Não foi criado um botão de ignorar essas
pendências. Implementar evidência e sua resolução é trabalho seguinte, junto
com o checklist documental; não existe garantia integral de conformidade ainda.
