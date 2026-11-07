# Síntese para o pitch: o que vender, com quais números e onde somos fracos

08/11/2026. Junta tudo o que foi levantado em `docs/pesquisa/` e `docs/evidencias/`. Cada número abaixo tem a fonte ao lado e foi conferido na origem ou recalculado por nós. Quando é conta nossa, está marcado.

## A tese em uma frase

**Somos uma homologadora operada por IA: o integrador pequeno manda conta e kit, recebe o pacote conferido contra a norma da distribuidora, e acompanha o processo com os prazos dele vigiados. Um engenheiro nosso revisa e assina; o agente faz o resto. Por isso cada engenheiro atende muito mais processos, e cobramos menos que as homologadoras de hoje.**

O que não vendemos: "homologação mais rápida" como promessa principal, e "sem engenheiro".

## 1. As evidências, por força

### Fortes (dado oficial ou regulador, conferido)

| Evidência | Número | Fonte |
|---|---|---|
| Pedidos residenciais negados por documentação incompleta, Equatorial AL | **16,3% a 17,4%** (1 em cada 6) | ANEEL, pedidos MMGD, B1 solar até 10 kW, 2022 a 2023; recontagem nossa em `scripts/aneel/recontagem_coorte.py` e a de `evidencias-outros-estados.md` |
| Mesma medida em outras distribuidoras | Equatorial MA 10,25%; Cosern 4,66%; Equatorial PI 3,40% | Mesma base, os dois cálculos batem |
| Pedidos negados porque o integrador não aprovou o orçamento no prazo, Coelba | **1.627** residenciais | Mesma base |
| Reclamações sobre atendimento a geração distribuída na Enel CE | 1.444 reclamações à ouvidoria em 2024; 353 casos analisados; a fiscalização relata "34,4% de atrasos nas vistorias" e "26% de falhas nos prazos de elaboração de orçamentos" (base dos percentuais não informada); multa de **R$ 19,4 mi** | Comunicado da Arce de 09/01/2025, republicado pela ABAR |
| Duração do processo, Enel CE residencial | mediana de 32 a 33 dias da solicitação à injeção; 10% passam de 84 a 86 dias | ANEEL, cálculo nosso e de `evidencias-da-dor.md` |
| Integradores que terceirizam projeto e engenharia | **37%** de 1.003 respostas | Greener, set/2025, pp. 32 e 35 |
| Requisitos da distribuidora em norma pública | Enel CNC-NDBR-DBR-18-0122 v05 e Equatorial NT.00020.EQTL Rev. 07 (7 estados) | Normas baixadas e lidas |

### Médias (declaração pública de empresa, conferida na página)

| Evidência | Número | Fonte |
|---|---|---|
| Uma homologadora B2B no Ceará faturou milhões | Tellar: **R$ 3 mi em 2024**, 30 pessoas, **14 engenheiros**, **cerca de 350 projetos/mês** | pv magazine, 26/11/2024 |
| Preço do serviço que já se compra | **R$ 400 a 690** por processo residencial (Tellar R$ 2 mil por 5; Spinatec R$ 459; Raio R$ 450; Solardesc R$ 490 a 690); **R$ 250 a 400** em assinatura (Raio) | Páginas das empresas |
| Escala do mercado de homologação terceirizada | GSH "+17.000 projetos"; Techmax "9 mil projetos", "600 empresas parceiras"; Spinatec "+6 mil homologações" | Páginas das empresas |
| Prazo de preparo das especializadas | 2 a 7 dias (Tellar: "sete dias para o projeto e dois dias para homologação") | pv magazine; páginas |
| Erro documental gera retorno, prazo perdido e margem menor | Cartilha da Cemig lista 13 motivos de reprovação; a WEG descreve retornos e perda de prazo | Cemig 2025; blog WEG |

### Fracas (usar só como contexto)

- Relatos individuais (Reclame Aqui, Goiás 2025, Fortaleza 2026): mostram o problema, não a frequência.
- Reonic diz economizar "até 12 horas administrativas por projeto": é promessa comercial, sem método.
- Auditoria da UFCG: 15 sistemas públicos de R$ 2,9 mi parados por mais de 2 anos. Mistura causas documentais, físicas e de rede.

## 2. Os argumentos que temos que usar

1. **"Existe um mercado que já paga por isso."** São 37% dos integradores terceirizando engenharia, a Tellar faturou R$ 3 mi só com isso, e o preço é de R$ 400 a 690 por processo. É o argumento de viabilidade mais forte que temos, porque não depende de convencer ninguém de uma dor nova.
2. **"O gargalo das homologadoras é engenheiro."** A Tellar precisa de 14 engenheiros para cerca de 350 projetos por mês, uns 25 por engenheiro, pouco mais de 1 por dia útil (conta nossa sobre números declarados). Nosso agente monta e confere, e o engenheiro só revisa e assina. É daqui que sai o preço menor e a margem.
3. **"Pedido negado por documentação é comum onde a conferência falha."** 1 em cada 6 pedidos residenciais da Equatorial AL foi negado por documentação incompleta (ANEEL, 2022 e 2023). O agente confere contra a norma antes do envio e não deixa sair pacote com exigência sem evidência.
4. **"O integrador perde pedido por prazo dele."** A Coelba negou 1.627 pedidos residenciais por não aprovação do orçamento no prazo. O agente vigia esses prazos com a fonte normativa.
5. **"Rastro de quem atrasou."** A Arce multou a Enel CE em R$ 19,4 mi depois de 1.444 reclamações em 2024. Tribunais condenaram integradores quando a falha foi da etapa deles e os livraram quando foi da distribuidora. Cada passo do agente fica registrado com data e decisão.
6. **"Custo de IA por processo é de centavos."** Modelos Qwen da mesma classe custam de US$ 0,08 a 0,57 por milhão de tokens, e uma conta mais kit usa cerca de 13 mil tokens, o que dá centavos de real por execução (conta nossa). Medimos tokens e tempo de cada chamada no tracing.

## 3. Onde somos claramente mais fortes que o modelo atual

| Contra | Eles | Nós | Força da nossa vantagem |
|---|---|---|---|
| Homologadora humana (Tellar, Spinatec, GSH) | Engenheiro monta o projeto; ~1 projeto por engenheiro por dia; 2 a 7 dias de preparo | Agente monta e confere em minutos; engenheiro só revisa | **Alta**, mas o número de revisões por dia ainda precisa ser medido |
| Homologadora humana | Conferência depende da atenção de quem monta | Regras em código com item da norma; nada é dado como aprovado sem evidência | **Média.** Elas declaram "+90%" e "100%" de aprovação, sem auditoria |
| Software de template (GD Pro grátis, Homologa Plus) | Pessoa digita os dados; gera documentos | Lê a conta e o kit, pergunta o que falta, confere, acompanha o portal e os prazos | **Alta** em escopo; é o que separa agente de gerador de documento |
| Todos | Acompanhamento em plataforma | Prazos do integrador vigiados com fonte normativa e rastro auditável de cada passo | **Média.** Plataforma de acompanhamento já existe nas concorrentes |
| Todos | Cobram R$ 400 a 690 | Custo marginal de IA em centavos | **Potencial**; depende do tempo de revisão medido |

## 4. Onde está o valor e como capturar

- **Cliente:** o integrador pequeno, que vende 2 a 5 sistemas por mês (Greener) e não sustenta um engenheiro só para homologar.
- **Produto:** o serviço completo, com responsável técnico nosso assinando. Expansão: o mesmo motor como software para quem tem engenharia própria e para as próprias homologadoras.
- **Preço:** abaixo da faixa atual, com espaço entre R$ 250 e 400 por processo, perto do plano de assinatura da Raio. É hipótese até medirmos o custo da revisão.
- **Conta para o slide:** preço × processos. Com cerca de 600 mil conexões novas por ano e 37% de terceirização, um preço de R$ 300 dá a ordem de grandeza do mercado endereçável. A conta é nossa, e a taxa de terceirização mede engenharia em geral, não só homologação.

## 5. Falhas e riscos que não podemos esconder

1. **Velocidade não nos diferencia de forma provada.** O tempo até a ligação é dominado pela distribuidora e pela obra. A Tellar já prepara em 7 dias. Nunca dizer "de uma semana para minutos" como ganho do processo inteiro.
2. **A Enel CE, nossa distribuidora atual, tem zero pedidos residenciais negados na base.** O argumento de qualidade não se aplica a ela. Ou migramos a demo para a Equatorial AL, ou o pitch fala da Enel CE só como prova técnica e usa a Equatorial como dado de mercado.
3. **Os dados de recusa são de 2022 e 2023**, antes das revisões atuais das normas. Sempre dizer o período.
4. **O custo por processo não está medido.** Sem o tempo de revisão humana, "mais barato" é hipótese.
5. **O plano de assinatura fixa do Featherless proíbe uso por agentes e API de produção.** O plano permitido cobra por token, e a tarifa não é pública. Confirmar o plano contratado antes de falar em custo.
6. **O conferidor ainda não fecha conformidade.** R02, R03 e R05 dependem de premissas a validar por engenheiro, e o memorial ainda sai com campos "A INFORMAR" (ver `docs/status-dev-a.md` e `docs/matriz-normativa.md`). Testar antes da demo se o caminho completo até o protocolo funciona com os casos prontos.
7. **O catálogo de equipamentos é sintético**, exceto o inversor real usado na demo. Não dizer que temos base de datasheets reais.
8. **Não falamos com nenhum integrador.** Toda a evidência de compra é indireta: mercado existente, preços e uma empresa que fatura com isso.
9. **Concorrência direta forte e local.** A Tellar está em Fortaleza, tem 500 integradores clientes e fala em plataforma própria. A Reonic anuncia R$ 399 com automação.
10. **A assinatura é humana.** O modelo de serviço exige engenheiro ou técnico nosso com responsabilidade técnica; isso é custo fixo e risco legal.

## 6. Perguntas difíceis que a banca pode fazer

| Pergunta | Resposta honesta |
|---|---|
| "Por que o integrador trocaria a homologadora atual?" | Preço menor com o mesmo serviço e responsável técnico, conferência registrada contra a norma e prazos dele vigiados. Ainda não validamos com clientes; é o primeiro passo depois do evento. |
| "A Tellar já faz isso." | Faz com 14 engenheiros montando projeto. Nosso agente monta, e o engenheiro revisa. Com o mesmo time, atendemos mais processos; é aí que está a margem. |
| "Quanto tempo vocês economizam?" | Responder com o número medido de revisão por pacote, contra pouco mais de 1 projeto por engenheiro por dia na referência da Tellar. Não responder em dias de processo. |
| "E se o agente errar?" | Regra crítica é código determinístico com item da norma. O que falta evidência fica incerto e bloqueia aprovação. O engenheiro assina só depois de revisar. |
| "Vocês substituem o engenheiro?" | Não. A lei exige participação real de quem assina. Reduzimos as horas dele por processo. |
| "Por que a Enel CE se lá não há recusa?" | Responder conforme a decisão sobre a migração: ou mostramos a Equatorial AL, ou dizemos que a Enel CE prova a troca de norma e a Equatorial é o mercado inicial. |

## 7. O que fazer até a submissão para fechar os buracos

1. **Medir o tempo de revisão** em 3 a 5 casos prontos: o agente gera, uma pessoa revisa até estar pronto para assinar, com cronômetro. Isso transforma os argumentos 2 e 6 em número.
2. **Decidir a distribuidora da demo** com o Pedro: migrar para a Equatorial AL ou manter a Enel CE com a Equatorial como dado de mercado.
3. **Confirmar o plano do Featherless** e o custo por token, para o número de custo por execução.
4. **Mandar mensagem para 3 a 5 integradores e homologadoras** com 3 perguntas: se terceirizam, quanto pagam e se pagariam R$ X pelo pacote conferido com acompanhamento. Qualquer resposta vira slide.
5. **Rodar o caminho completo da demo** com os casos prontos, até o protocolo, e garantir que nenhuma regra a validar trava a apresentação sem explicação.

## 8. Roteiro de 3 minutos sugerido

1. **Problema (20 s):** "1 em cada 6 pedidos residenciais de geração solar em Alagoas foi negado por documentação incompleta (ANEEL). Integradores pagam de R$ 400 a 690 por processo para homologadoras resolverem isso, e a maior delas no Ceará fatura R$ 3 milhões por ano com 14 engenheiros montando projetos."
2. **Solução (20 s):** homologadora operada por IA, com engenheiro que revisa e assina.
3. **Demo (90 s):** a conta e o kit entram; o agente pergunta o que falta e pega um erro que geraria recusa, mostrando o item da norma; o engenheiro revisa e aprova; o pedido é protocolado; chega uma pendência, que o agente classifica e corrige; o agente lembra o prazo do integrador. Fechar com a linha do tempo, com tokens e custo por passo.
4. **Números (30 s):** tempo de revisão medido contra ~1 projeto por engenheiro por dia; custo de IA em centavos; preço-alvo; mercado.
5. **Pedido (20 s):** o que queremos dos jurados e da Tako.
