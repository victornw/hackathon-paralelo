# Slides do Demo Day (rascunho)

Três minutos. Cada número tem a fonte no rodapé do slide. Os campos entre colchetes só entram quando forem medidos; sem medição, o slide usa a versão "sem número" indicada.

## 1. Problema

**Título:** Homologar energia solar ainda é trabalho de engenheiro, feito à mão, processo por processo.

- 1 em cada 6 pedidos residenciais de geração solar em Alagoas foi negado por documentação incompleta.
- Integradores pagam de R$ 400 a R$ 690 por processo para homologadoras fazerem esse trabalho.
- A maior delas no Ceará faturou R$ 3 milhões em 2024 com 14 engenheiros montando cerca de 350 projetos por mês.

Rodapé: ANEEL, pedidos de conexão MMGD 2022–2023, B1 solar até 10 kW (16,3% a 17,4%, Equatorial AL); preços publicados por Spinatec, Raio, Solardesc e Tellar; Tellar na pv magazine, 26/11/2024.

## 2. Para quem

**Título:** O integrador pequeno, que vende de 2 a 5 sistemas por mês e não sustenta um engenheiro só para homologar.

- 37% dos integradores já terceirizam projeto e engenharia.
- O mercado de homologação terceirizada já existe: GSH declara mais de 17 mil projetos, Techmax 9 mil, Spinatec 6 mil.

Rodapé: Greener, set/2025, 1.003 respostas; páginas das empresas.

## 3. Solução

**Título:** Uma homologadora operada por IA. O agente monta e confere; o engenheiro revisa e assina.

- Lê a conta de luz e a proposta do kit, e pergunta só o que falta.
- Gera formulário, memorial e unifilar no padrão da norma da Enel.
- Confere contra a norma antes do envio. O que não tem evidência fica incerto e bloqueia a aprovação.
- Depois do protocolo, acompanha o portal, classifica pendências e vigia os prazos do integrador.

## 4. Demo (ao vivo, 90 s)

Roteiro:
1. Conta e kit entram; o agente extrai os campos e pergunta o que falta.
2. A conferência mostra cada regra com o item da norma; o pacote com campo vazio não passa.
3. O engenheiro revisa, confirma as premissas e aprova; o pedido é protocolado no portal simulado.
4. Chega uma pendência; o agente classifica e propõe a correção; o engenheiro reaprova e o pedido é reenviado.
5. O agente avisa o prazo do integrador para aprovar o orçamento.
6. Fecha na linha do tempo, com tokens e custo de cada passo.

Usar os casos demo-01 e o caso 1 sintético. Não usar o caso 2 (microinversor, fora do MVP).

## 5. Por que funciona

**Título:** Regra crítica é código; o LLM lê, escolhe o próximo passo e escreve.

- Classificação de pendências: 93,8% de acerto, contra 50% de palavras-chave (48 textos sintéticos rotulados antes de rodar o modelo).
- Pacote com "A INFORMAR" ou regra sem evidência não é aprovado nem protocolado.
- Cada passo fica registrado com data, decisão, tokens e custo.

Rodapé: `evals/resultados_pendencias.md`; Qwen3.8-27B na Featherless.

## 6. Unidade econômica

**Título:** O mesmo engenheiro atende muito mais processos.

| | Homologadora atual | Nós |
|---|---|---|
| Trabalho do engenheiro | Monta o projeto | Revisa e assina |
| Projetos por engenheiro por dia | Pouco mais de 1 | [N, medido] |
| Custo de IA por processo | — | ~R$ 0,07 (cerca de 13 mil tokens) |
| Preço ao integrador | R$ 400 a 690 | até R$ 350 |

Versão sem medição: trocar "[N, medido]" por "medição de revisão em andamento" e não citar múltiplo.

Rodapé: Tellar (14 engenheiros, cerca de 350 projetos/mês, conta nossa); custo medido em processos completos com Qwen real, a preço de referência de mercado (US$ 0,14 e 0,57 por milhão de tokens) e PTAX de 06/11/2026.

## 7. Mercado e crescimento

- Cerca de 600 mil novas conexões solares por ano no Brasil.
- Começamos pela Enel (norma pública, vale para CE, RJ e SP; portal com consulta aberta no CE e no RJ).
- Próximas distribuidoras: Equatorial, com uma norma para 7 estados e a maior taxa de recusa documental entre as distribuidoras do Nordeste na base da ANEEL.
- Expansão: o mesmo motor como software para integradores com engenharia própria e para as próprias homologadoras.

## 8. Pedido

O que pedimos à banca e à Tako (preencher): por exemplo, conexão com integradores para piloto pago e com engenheiros para validar as regras.

## Falas que não usar

- "Homologação mais rápida" como promessa do processo inteiro. A distribuidora e a obra dominam o prazo.
- "Substitui o engenheiro". A lei exige participação real de quem assina.
- Qualquer número de recusa como se fosse de hoje. É ANEEL 2022–2023.
- Recusa documental na Enel CE. Na base, ela tem zero pedidos residenciais negados.
