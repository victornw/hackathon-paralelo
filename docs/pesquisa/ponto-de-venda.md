# Onde vender o agente: tempo, custo e qualidade com dados

Estudo de 07/11/2026. Junta a base da ANEEL processada por nós e três pesquisas paralelas, cujos relatórios completos, com fontes e rótulos VERIFIED, REPORTED e INFERRED, estão em `anexos/`.

## Conclusão

O argumento que os dados sustentam não é "homologação mais rápida". É **"o pedido não volta e nenhum prazo do integrador estoura, com rastro de tudo"**, vendido como **serviço de homologação mais barato que o terceirizado de hoje**. O argumento de velocidade só se sustenta em duas formas mais estreitas: menos retrabalho por pedido negado e menos processos parados em etapas que dependem do integrador.

A migração para a Equatorial AL é viável e melhora o pitch, porque é lá que a dor documental aparece nos dados. A Enel CE tem zero pedidos residenciais negados na base.

## 1. Tempo: a parte que o agente faz não é o gargalo

Base ANEEL "Atendimento a pedidos de conexões MMGD", arquivo Nordeste, pedidos de 07/01/2022 a 07/01/2023, residencial B1 até 10 kW, um registro por protocolo. Script: `scripts/aneel/tempo_por_etapa.py`.

| Distribuidora | Pedidos | Protocolo → orçamento (mediana) | Orçamento → vistoria (mediana) | Total até injetar (mediana) |
|---|---|---|---|---|
| Enel CE | 22.853 | 9 dias | 20 | 32 |
| Equatorial AL | 11.773 | 8 | 27 | 38 |
| Equatorial MA | 14.614 | 101 | 27 | 122 |
| Neoenergia Coelba | 59.495 | 6 | 30 | 39 |
| Neoenergia Cosern | 17.939 | 5 | 16 | 22 |
| Neoenergia PE | 32.134 | 6 | 27 | 34 |

- A etapa da distribuidora costuma ficar abaixo de 10 dias. Quando ela estoura (Equatorial MA), o atraso é interno à distribuidora e o agente não o resolve.
- O trecho mais longo mistura obra física e a demora do integrador em pedir a vistoria; a base não separa os dois.
- Montar o projeto acontece antes do protocolo e a base não mede. Empresas especializadas anunciam 3 a 5 dias. Não existe dado público de horas de trabalho por projeto (anexo de custo, item 5).

## 2. Qualidade e prazos: onde a dor aparece nos dados

Mesma base. Script: `scripts/aneel/perdas_por_motivo.py`.

| Distribuidora | Negados por documentação incompleta ou incorreta | Parados em "vistoria não solicitada" ou "vistoria reprovada" | Negados por não aprovar o orçamento no prazo (art. 83, § 7º, I) |
|---|---|---|---|
| **Equatorial AL** | **1.754 (14,9%)** | **1.399 (11,9%)** | 0 |
| **Equatorial MA** | **1.508 (10,3%)** | 308 (2,1%) | 0 |
| Neoenergia Cosern | 1.068 (6,0%) | 289 (1,6%) | 0 |
| Equatorial PI | 662 (4,0%) | 144 (0,9%) | 0 |
| Neoenergia Coelba | 154 (0,3%) | 2 | **1.513 (2,5%)** |
| Neoenergia PE | 94 (0,3%) | 550 (1,7%) | 0 |
| Enel CE | 0 | 607 (2,7%) | 0 |
| **Nordeste, 178.090 pedidos** | **3,0%** | **1,9%** | |

Cuidados ao citar:

- São dados de 2022 a 2023, antes das revisões atuais das normas. Dizer "segundo a ANEEL, em 2022 e 2023", nunca "hoje".
- Pedido negado pode ter sido reenviado. O número mede retrabalho, não venda perdida.
- "Perda de validade: outros motivos" (6.484 na Equatorial PI) e "Outras não conformidades" (11.495 na Coelba) são categorias vagas. Não contam como prazo do integrador nem como erro documental.
- Em dez/2023, 54% do estoque nacional de pedidos estava em "vistoria não solicitada", segundo apresentação da ANEEL na Câmara (anexo tempo-em-dinheiro, REPORTED).

## 3. Custo: o que dá para provar e como

O que já está sustentado (anexo prova-de-custo):

| Dado | Valor | Fonte |
|---|---|---|
| Preço de tabela publicado, até 10 kWp (conferido em 08/11/2026) | Raio: a partir de R$ 450, TRT incluso; Solardesc: R$ 490 (1 a 3 kWp), R$ 590 (3,1 a 5), R$ 690 (5,1 a 10). Só essas duas vendem homologação a integradores; a Raio também é integradora e vende software, a Solardesc é empresa de engenharia e homologação | raiosolucoes.com/homologacao; solardesc.com/homologacao |
| Preço com assinatura | Raio: R$ 250 a 400 por homologação para assinantes | raiosolucoes.com/homologacao |
| Outras homologadoras | Spinatec a partir de R$ 459/projeto; Tellar R$ 2 mil por 5 projetos | ver seção 3b |
| Taxa de ART, contrato até R$ 15 mil | R$ 108,39 (16% a 24% do preço) | Tabela CREA-MT 2026 |
| Engenheiro eletricista | R$ 11.265/mês de média | Salario.com.br sobre CAGED, 05/11/2026 |
| Técnico de projeto eletrotécnico | R$ 3.599/mês de média | Salario.com.br sobre CAGED |
| Custo/hora com encargos (1,72x a 2,0x) | engenheiro R$ 106 a 124, técnico R$ 33 a 39 | INFERRED a partir dos dois acima |
| Custo de modelo por conta + kit | cerca de R$ 0,01 a 0,04 | Preço por token de modelos Qwen da mesma classe no OpenRouter (INFERRED) |

O que ainda não está sustentado: horas de trabalho poupadas. Só sai de medição nossa. Protocolo proposto para o hackathon:

1. 6 a 10 casos sintéticos com defeitos plantados e registrados antes (Voc acima do limite, disjuntor errado, titular divergente, documento faltando).
2. Braço humano: alguém monta e confere o pacote à mão, cronometrado. Braço agente: o agente monta e confere, e um revisor confere o resultado, também cronometrado.
3. Medir tempo ativo por pacote, defeitos encontrados de cada braço e aprovações falsas. A referência são os defeitos plantados, não o conferidor do agente, para o número não ser circular.
4. Reportar mediana e intervalo, e dizer que é sintético.

Frases que os dados sustentam hoje: "empresas que vendem homologação a integradores cobram de R$ 450 a R$ 690 por processo residencial até 10 kWp, e de R$ 250 a 400 em plano de assinatura"; "o custo de modelo por execução é de centavos". Frases que não sustentam: "de uma semana para minutos", "economizamos R$ N por processo" sem a medição, "substitui o engenheiro".

**Risco no Featherless:** o plano de assinatura fixa proíbe uso por agentes e API de produção; o plano permitido cobra por token e não publica a tarifa (anexo prova-de-custo, item 4). Confirmar o plano contratado antes de dizer "custo zero".

## 3b. As homologadoras: tamanho, preço e prazo

Levantamento de 08/11/2026. Relatório completo, com CNPJ e fontes, em `anexos/homologadoras.md`. Os números de Spinatec, GSH, Tellar e Techmax foram reabertos na fonte antes de entrar aqui. Faturamento de empresa fechada não é público: só a Tellar declarou receita à imprensa. Para as outras, o registro na Receita dá apenas o porte, que é um teto legal (ME até R$ 360 mil/ano, EPP até R$ 4,8 mi/ano), não o faturamento real. O porte não bate com o volume declarado (a Tellar é ME e declara R$ 3 mi), então não usar o porte como receita.

| Empresa | Tipo | Onde | Faturamento ou porte | Volume declarado | Preço por homologação | Prazo de preparo |
|---|---|---|---|---|---|---|
| **Tellar** | Engenharia só para integradores (B2B) | Sobral e Fortaleza (CE) | **R$ 3 mi em 2024**, meta de R$ 12 mi em 2025; cerca de R$ 200 mil/mês recorrente; **30 pessoas, 14 engenheiros** (pv magazine, 26/11/2024) | **cerca de 350 projetos/mês**; "+5 mil projetos" (2024), "+9Mil" (site hoje) | Pacote Prime: a partir de R$ 2 mil por 5 projetos (R$ 400 cada) | "média de sete dias para o projeto e dois dias para homologação" (pv magazine); "entre 5 e 7 dias" (site) |
| **Spinatec** | Homologação e CRM para integradores | Santana de Parnaíba (SP) | ME; capital R$ 23 mil; CNPJ aberto em 2024 | "mais de 6 mil homologações", "+90% de taxa de aprovação" | **a partir de R$ 459/projeto**; paga "somente após o parecer aprovado" | protocolo "em até 3 dias úteis" |
| **GSH Engenharia** | Homologação e média tensão | Bauru (SP) | ME; capital R$ 40 mil; fundada em 2017 | "mais de 17.000 projetos" | não publica | protocolo "em até 3 dias úteis" |
| **Techmax Solar** | Engenharia terceirizada para integradores | não informa | não confirmado (CNPJ candidato é EPP) | "9 mil projetos", "150MW", "600 empresas parceiras" | assinatura "R$250 /mês", tabela por potência não publicada | "Prazo Garantido de 15 Dias" (sem dizer se é preparo ou aprovação) |
| **Raio Soluções** | Integradora que também vende homologação e software | Senador Canedo (GO) | ME; capital R$ 2 mil | "+1.800" projetos (incluem instalação) | a partir de R$ 450 com TRT; assinantes R$ 250 a 400 | protocolo em 2 dias úteis |
| **Solardesc** | Engenharia e homologação, também atende cliente final | BH/Contagem (MG) | ME; capital R$ 100 mil | não informa | R$ 490 a 690 até 10 kWp | 3 a 5 dias úteis |
| Homolog Solar | Homologação, foco no Nordeste | PE (inferido pelo DDD) | CNPJ não localizado | "+4.000 projetos aprovados" | não publica | "até 15 dias" (aprovação) |

O que isso mostra:

- **O mercado de homologação terceirizada existe e tem escala.** Quatro empresas declaram, somadas, dezenas de milhares de projetos. A Tellar, no Ceará, fatura milhões só com engenharia para integradores.
- **O preço por processo fica entre R$ 400 e R$ 690**, e cai para R$ 250 a 400 em assinatura. Esse é o teto contra o qual competimos.
- **O preparo já leva de 2 a 7 dias nas especializadas.** Confirma que velocidade de preparo não diferencia.
- **A unidade econômica da Tellar dá a referência de custo humano.** Com 14 engenheiros e cerca de 350 projetos por mês, são uns 25 projetos por engenheiro por mês, pouco mais de 1 por dia útil. A receita de cerca de R$ 200 mil por mês dá uns R$ 570 por projeto (INFERRED, conta nossa sobre números declarados). Se o agente deixa um engenheiro revisar e assinar vários projetos por dia, em vez de montar um, o custo por processo cai na mesma proporção. Esse é o argumento de "menos engenheiros por processo", e o número que falta é a nossa medição do tempo de revisão.

## 4. Outras formas de o tempo valer dinheiro

Do anexo tempo-em-dinheiro, em ordem de força da evidência:

1. **Rastro auditável em disputa.** Tribunais condenaram integrador quando a falha foi da etapa dele (TJRN 2025, R$ 5 mil; TJGO 2023, rescisão e R$ 136 mil) e afastaram a culpa quando o atraso foi da distribuidora (TJSC). Mostrar com datas quem atrasou tem valor direto.
2. **Prazos do integrador vigiados.** Coelba negou 1.513 pedidos residenciais por não aprovação do orçamento no prazo, e 1,9% dos pedidos do Nordeste ficaram parados em vistoria não solicitada ou reprovada.
3. **Caixa do integrador.** Na venda à vista, o integrador "antecipa tudo e só recebe na conclusão" (pv magazine, 27/08/2024). Não achamos regra pública de financiadora que libere dinheiro só após a homologação, então não usar esse argumento.
4. **Capacidade sem contratar.** O integrador típico vende 2 a 5 sistemas por mês e 37% terceirizam projeto e engenharia (Greener). O agente deixa um técnico atender mais processos.
5. **Cliente final.** Um sistema de 5 kWp no Ceará deixa de economizar cerca de R$ 400 a 600 por mês parado (INFERRED com tarifa B1 da Enel CE). Ninguém vende com esse argumento hoje; serve como contexto, não como promessa.

## 5. Migrar o MVP para a Equatorial AL?

Do anexo equatorial-viabilidade:

- **Norma pública:** NT.00020.EQTL, Rev. 07, publicada em 04/11/2026, texto legível. Vale para AL, AP, GO, MA, PA, PI e RS.
- **Templates oficiais:** Anexo I (formulário, XLSX) e Anexo III (memorial com fotos, PDF).
- **Lista de documentos (§ 5.14.2):** formulário; ART ou TRT de projeto e execução; unifilar com DPS CA e CC; diagrama de blocos; memorial; relatório de ensaio do inversor; INMETRO.
- **Prazo de checagem:** a distribuidora checa a documentação em 5 dias úteis e indefere listando as não conformidades.
- **Portal:** a Agência Virtual abre o pedido e o acompanha sem login, com UC e protocolo.
- **Riscos:** o site fica atrás de um WAF, então é preciso congelar uma cópia local da norma. A Rev. 07 tem 3 dias e convive com a Rev. 06 até 03/2027. Não achamos evidência recente (2024 a 2026) de recusa em AL.

**Recomendação:** migrar a demo para a Equatorial AL e manter a Enel CE como segunda distribuidora, para mostrar que o motor de regras troca de norma. O que muda:

- regras e exigências conforme a NT.00020;
- formulário do Anexo I em XLSX;
- memorial no modelo do Anexo III;
- portal simulado com indeferimento em 5 dias úteis.

O motor de regras, o orquestrador e a API ficam. Se não houver tempo para gerar os documentos da Equatorial, a alternativa mínima é aplicar as exigências e regras da NT.00020 e manter os documentos atuais, dizendo isso na demo.

## Fala de pitch que os dados permitem

"Segundo a ANEEL, em 2022 e 2023, 1 em cada 7 pedidos residenciais de geração solar em Alagoas voltou por documentação incompleta, e 1 em cada 8 ficou parado esperando a vistoria. Nosso agente monta o pacote conferido contra a norma da Equatorial, vigia os prazos do integrador e registra quem atrasou cada etapa. Empresas que vendem homologação a integradores cobram de R$ 450 a R$ 690 por processo residencial; nosso custo de modelo por processo é de centavos, e medimos o tempo de revisão humana em N minutos."

O N sai do protocolo de medição da seção 3.
