# Spec: Agente de Homologação de Energia Solar (v4.0)

Nov 7, 2026 · @Pedro Collet

## Visão geral

Um digital worker que conduz a homologação de GD solar residencial de ponta a ponta para o integrador: confere o kit vendido, completa e gera o projeto (formulário, memorial e unifilar), confere tudo contra a norma da distribuidora antes do envio, acompanha o processo no portal, responde pendências e vigia os prazos que dependem do integrador. O engenheiro revisa um projeto já conferido, em vez de montá-lo do zero, e assina.

**Tese central.** O tempo perdido na homologação não é só espera pela distribuidora. Montar o projeto leva de uma a duas semanas de trabalho técnico, pendências evitáveis fazem o processo voltar, e prazos do lado do integrador (aprovar orçamento, pedir vistoria) estouram por esquecimento. O agente elimina essa parte, que depende só do integrador.

**Foco.** Mercado residencial: UC monofásica (220 V), microgeração até 10 kW, Enel Ceará. O agente não dimensiona o sistema: o kit é escolhido na venda, e o agente confere esse arranjo, completa os dados do projeto e pergunta o que falta.

**O que mudou na v4.0 (pivot para a Enel CE).**

- A distribuidora da demo passou de Energisa PB para Enel CE. A norma da Enel (CNC-NDBR-DBR-18-0122-EDBR v05) é pública e legível; a NDU-013 da Energisa bloqueia download automatizado e o memorial dependia de uma planilha oficial que não encontramos.
- O memorial deixou de ser "planilha oficial por mapa de células". Para microgeração até 10 kW a Enel não exige aprovação prévia de projeto nem fornece modelo de memorial: ele vai junto do unifilar, em formato nosso.
- O unifilar parte do modelo oficial da norma (Anexo B, conexão à BT através de inversor).
- O portal simulado copia a estrutura do Portal GD real da Enel CE, que tem consulta aberta (UC, e-mail e número da solicitação). O mesmo portal atende a Enel RJ.
- Os evals da ANEEL foram refeitos: a Energisa PB não está no arquivo do Nordeste, e o motivo de recusa é uma de 18 categorias fixas, não texto livre.
- Sem ligações para integradores durante o hackathon; validação com integradores fica para depois do evento.

**Analogia.** É como o habite-se: a obra está pronta, mas ninguém mora até a prefeitura liberar. Só que, antes de pedir o habite-se, alguém ainda precisa montar a papelada da planta sem erro.

**Frase de pitch.** "O projeto chega na Enel conferido contra a norma, e nenhum prazo do integrador estoura."

## Problema e evidência

Quem sofre é o integrador pequeno e médio, em cada sistema vendido; o custo aparece em horas de trabalho técnico, em retrabalho por pendência e em meses de economia que o cliente final deixa de ter.

**O caminho da homologação.**

1. O integrador vende o sistema: a proposta comercial define o kit (módulos, inversor, potência), muitas vezes sem visita.
2. Depois da venda, a engenharia valida o projeto e faz a visita técnica, de onde saem padrão de entrada, distâncias e estado do quadro.
3. O responsável técnico elabora formulário, memorial e unifilar e protocola no Portal GD da distribuidora. É aqui que o agente entra.
4. A distribuidora analisa e emite o orçamento de conexão, ou aponta pendências.
5. O integrador aprova o orçamento no prazo e, com a instalação pronta, pede a vistoria.
6. A distribuidora vistoria e troca o medidor; só então o cliente economiza.

| Onde dói | Evidência | Fonte |
|---|---|---|
| Elaboração do projeto | ~1 semana por UC monofásica; 1,5 a 2 semanas por trifásica, feito por estagiário de engenharia com Illustrator e a planilha da distribuidora | Relatório UFCG 2024 (Energisa PB; usado como ordem de grandeza) |
| Tempo até gerar na Enel CE | Residencial até 10 kW: mediana de 34 dias da solicitação à injeção; 10% passam de 87 dias (2022–2023) | Base ANEEL de pedidos de conexão MMGD |
| Vistoria travando o processo | Residencial até 10 kW na Enel CE: 378 pedidos em "vistoria não solicitada" e 315 em "vistoria reprovada, aguardando nova solicitação", de 24.269 | Base ANEEL de pedidos de conexão MMGD |
| Pedidos perdidos por prazo do integrador | Enel CE, todos os segmentos: 94 orçamentos perderam a validade por não aprovação no prazo (art. 83, § 7º, I), que na Enel é de 10 dias úteis | Base ANEEL; norma Enel 7.3.5 |
| Recusas por documentação | Enel CE, todos os segmentos: 304 pedidos indeferidos por documentação incompleta (art. 71, II) | Base ANEEL de pedidos de conexão MMGD |
| Barreiras percebidas | 41% citam demora na troca do medidor, 40% atraso na aprovação e 31% reprovação sem justificativa plausível (pesquisa Greener, 2022) | Solfus |
| Dor atual em outras distribuidoras | Protesto na Neoenergia Brasília (jun/2026), atrasos na Equatorial Goiás (jul/2026), reprovações em massa na CPFL | Canal Solar |
| Motivo nº 1 de reprova (Cemig) | Divergência entre a coordenada informada e o endereço cadastrado | Cartilha Cemig 2025 |

**Quanto custa cada mês parado.** Nos projetos residenciais de ~7 kWp do relatório da UFCG, com consumo de ~1.000 kWh/mês, a economia estimada era de ~R$ 720 por mês. O residencial típico da Enel CE tem 5 kW (mediana da base ANEEL), que gera ~650–750 kWh/mês no Ceará; a ordem de grandeza fica em algumas centenas de reais por mês. É dinheiro do cliente final; para o integrador, a dor vem pelo trabalho técnico e, quando o pagamento depende da homologação, pelo caixa.

**Ressalvas.** A "semana de elaboração" vem de um único relatório, com estagiário e Illustrator, e de outra distribuidora; integrador com software faz mais rápido. Na base da ANEEL, os pedidos residenciais até 10 kW da Enel CE não aparecem como negados; as recusas (466 no total) são de outros segmentos. O campo de motivo traz "não apresentação das informações pelo acessante (art. 89, I)" em quase todos os pedidos residenciais, mesmo conectados; o significado desse preenchimento ainda precisa ser entendido antes de virar argumento.

## Mercado, concorrência e why now

O volume de processos é grande e verificado; o valor em reais depende do preço por processo, que ainda é hipótese e sai da validação.

| Grandeza | Valor | Status | Fonte |
|---|---|---|---|
| Base instalada de GD solar | 4,321 milhões de conexões (abr/2026) | Verificado | Exame |
| Novas conexões 2024–2025 | Mais de 1,5 milhão (~750 mil/ano) | Verificado | Canal Solar |
| Novas conexões 2026 | 202 mil em jan–abr | Verificado; desacelerando | pv magazine |
| Ritmo anual 2026 | ~600 mil/ano | Projeção a partir de jan–abr | pv magazine |
| Pedidos na Enel CE | 35.030 pedidos únicos entre 07/01/2022 e 07/01/2023; 27.967 residenciais (B1), 86,8% deles até 10 kW | Verificado | Base ANEEL |
| Processos além de conexões novas | Ampliações e trocas de inversor exigem nova homologação | Verificado em caso real | Relatório UFCG 2024 |
| Payback residencial | 3 a 8 anos, mais comum 4 a 6 | Verificado (2026) | Estado de Minas |

**Conta de mercado (hipótese explícita).** Processos por ano × preço por processo. Com ~600 mil processos novos por ano, cada R$ 100 de preço por processo equivale a ~R$ 60 milhões por ano de mercado endereçável, antes de ampliações. O preço real sai das entrevistas (ver hipótese de preço).

**Como o integrador resolve hoje.**

| Alternativa | Como funciona | Onde o agente ganha |
|---|---|---|
| Fazer internamente | Engenheiro ou estagiário monta unifilar no Illustrator ou CAD e preenche os formulários da distribuidora à mão | Projeto conferido contra a norma antes do envio, em minutos |
| Empresa de projeto ou despachante (ex.: Spinatec) | Terceiriza unifilar, memorial, formulários e acompanhamento | Preço menor e prazo vigiado automaticamente |
| Software de projeto (SOLergo, Solarius PV) | Gera unifilar e relatórios a partir do sistema projetado | Confere contra a norma da distribuidora e conduz o processo depois do envio |
| Integradora em escala (EcoPower) | Central própria homologa para a rede de franquias | Cliente potencial do software, não concorrente |

**Why now.**

- Modelos com visão leem conta de luz e datasheet com confiabilidade que não existia há dois anos.
- A Lei 14.300 e a REN 1.000 criaram prazos rígidos dos dois lados do processo.
- As distribuidoras migraram o processo para portais digitais; na Enel CE e RJ o acompanhamento é aberto, sem login.
- A base de 4,3 milhões de sistemas gera ampliações e trocas de equipamento que voltam a exigir homologação.

**Por que ninguém resolveu.** Cada distribuidora tem norma, formulário e portal próprios, e a responsabilidade técnica exige engenheiro no circuito. Manter um repositório de regras por distribuidora é o trabalho difícil e o fosso do produto. Gerar documentos, sozinho, não é diferencial.

**Escala dentro da Enel.** A norma CNC-NDBR-DBR-18-0122 vale para Enel CE, RJ e SP, e o Portal GD com consulta aberta é o mesmo no Ceará e no Rio. Uma integração cobre duas distribuidoras; a norma, três.

## Cliente-alvo e modelo de negócio

O cliente é sempre o integrador residencial; como ele homologa hoje decide se compra o serviço completo ou o agente como software.

| Segmento | Como homologa hoje | O que compra | Quem assina a ART | Cobrança |
|---|---|---|---|---|
| Integrador que terceiriza | Paga empresa de projeto ou despachante | Serviço completo: o agente prepara e confere, engenheiros da startup revisam e assinam | Engenheiro da startup | Por processo, abaixo do terceiro atual |
| Integrador que faz internamente (ex.: Ecosol, no relatório UFCG) | Engenheiro supervisiona estagiário que monta o projeto | Agente como software: o engenheiro revisa o projeto conferido e assina | Engenheiro do integrador | Assinatura por volume |
| Integradora em escala (ex.: EcoPower) | Central de homologação própria | Software para reduzir a equipe de elaboração e revisão | Engenheiros internos | Contrato por volume (expansão) |

**Modelo para o pitch.** Liderar com o serviço completo ("fazemos o que uma empresa de projeto faz, com uma fração dos engenheiros") e apresentar o software como canal de expansão.

**Hipótese de preço.** O preço se ancora na alternativa, não no custo. Três âncoras:

- Quanto o integrador paga hoje a uma empresa de projeto ou despachante por processo (pesquisa pública durante o evento; confirmar com integradores depois).
- Quanto custa a semana de trabalho técnico de quem monta o projeto.
- O custo por execução do agente, medido no tracing.

Fala do pitch: "Hipótese de R$ X por processo, abaixo dos R$ Y que o integrador paga hoje a terceiros; nosso custo medido é R$ Z por execução." O estudo de custos completo fica para depois do evento.

**Custo por execução.** O agente precisa custar ordens de grandeza menos que uma semana de trabalho técnico. Medir tokens, tempo e custo por processo no tracing e mostrar a comparação no pitch.

**Responsabilidade técnica.** O agente prepara e confere; o engenheiro revisa de verdade e assume a ART. Assinar sem participação real é vedado pela Lei 5.194/66, então a tela de revisão é parte do produto: mostra o que foi gerado, qual regra foi checada e o que ficou incerto.

**Configuração inicial.** Dados do integrador (CNPJ, responsável técnico, procuração padrão), distribuidora atendida e catálogo dos kits mais vendidos, com datasheets.

## Como as distribuidoras funcionam

Nenhuma distribuidora pesquisada avisa status por e-mail: tudo fica no portal. A Enel CE e a Enel RJ têm consulta aberta só com dados do processo, sem login.

| Distribuidora | Canal de status | Acesso | Passo manual relevante | Fonte |
|---|---|---|---|---|
| Enel (Ceará e Rio) | Portal GD | Sem login: código da UC, e-mail e número da solicitação | Aprovar o orçamento em 10 dias úteis; pedir a vistoria pelos canais da distribuidora | Portal; norma Enel |
| Enel (São Paulo) | Processo pela NT 6.012; portal de acompanhamento não confirmado | — | — | NT 6.012 |
| Energisa (ex.: Paraíba) | Plataforma de projetos; ressalvas e cartas no portal | Login do projetista | Conexão GD na plataforma nova; vistoria ainda na antiga, só após "Aprovado" | Passo a passo |
| CPFL / RGE | Site de Projetos Particulares | Login do responsável técnico | RT pede a vistoria após aprovação | FAQ CPFL |
| Neoenergia (ex.: Coelba) | Portal de GD ou WhatsApp | Portal com cadastro | Nova vistoria pedida pelo portal | FAQ Coelba |

**O pacote que a Enel CE exige para microgeração até 10 kW** (norma CNC-NDBR-DBR-18-0122-EDBR v05, Tabela 10 e Anexo A):

| Documento | Conteúdo | O agente |
|---|---|---|
| Solicitação de orçamento de conexão (Anexo A) | UC, titular, endereço, carga instalada, fonte, potência, tipo de geração, dados do inversor (fabricante, modelo, quantidade, tensão e potência nominal), modalidade de compensação, declarações | Preenche a partir da conta de luz, do kit e da relação de cargas pedida ao integrador |
| ART do responsável técnico | Projeto e execução | Fica com o engenheiro; o agente só confere que existe |
| Certificado INMETRO do inversor | Portaria INMETRO 140/2022, obrigatória para inversores até 75 kW, para a tensão nominal de conexão | Confere e anexa a partir do catálogo |
| Dados de registro da central geradora | Conforme o site da ANEEL | Preenche a partir do kit |
| Diagrama unifilar e de blocos com memorial descritivo | Geração, proteção (inversor), medição e descrição da instalação; a norma não traz modelo de memorial | Preenche o template de unifilar baseado no Anexo B e gera o memorial em PDF num formato nosso |

Acima de 10 kW a Enel exige aprovação prévia de projeto e memorial; fica fora do MVP (e fora de UC monofásica, que na Enel CE vai até 10 kW).

**Dados técnicos da Enel CE úteis ao agente.**

- Tensão de atendimento: monofásica 220 V para potência disponibilizada até 10 kW (Tabela 4).
- Unifilar BT com inversor: medição → disjuntor → DPS → disjuntor → cargas e inversor (Anexo B, forma de conexão 1).
- DPS obrigatório nas instalações internas, conforme NBR 5410 e 5419 (7.6.1.6); AFCI recomendado (NBR 16690).
- Proteções de tensão, frequência e anti-ilhamento podem estar no próprio inversor; para microgeração, redundância é desnecessária (7.6.1.5).
- Ajustes de proteção do inversor aparecem como "a informar" para o Ceará no Anexo G.

**Portal GD da Enel CE (estrutura real, a imitar no simulado).** Fluxo em quatro passos: formulário básico, download da documentação, upload dos documentos e confirmação. O formulário básico pede código da UC, classe, titular, e-mail, endereço, CPF/CNPJ, telefone, fonte, potência instalada de geração, tipo de geração, quantidade de UCs com crédito, data de implantação, potência instalada da UC, nível de tensão, tipo de conexão, tensão de atendimento, corrente do disjuntor, tipo de ramal, subgrupo, modalidade, demanda e latitude/longitude. A consulta pede código da UC, e-mail e número da solicitação.

**Distribuidora da demo.** Enel Ceará, pela norma pública, pelo portal com consulta aberta e pelos dados da ANEEL. O portal é simulado na demo. Antes de automatizar qualquer consulta real, conferir os termos de uso e nunca criar solicitações falsas.

**Pré-requisitos antes de codar:** a norma da Enel (já baixada) e o modelo do Anexo B para o template do unifilar.

## Fluxo do digital worker

O agente recebe o objetivo "homologar este sistema" e conduz o processo sozinho; o humano aparece em dois pontos de responsabilidade legal (assinatura técnica e envio no portal) e nas exceções que o agente escala com contexto pronto.

1. **Receber e extrair.** O integrador manda a conta de luz, a proposta ou o kit vendido e os dados da visita técnica. O agente extrai UC, titular, classe, tipo de ligação e endereço; cada campo vem com grau de confiança.
2. **Pedir o que falta.** O agente compara o que recebeu com o que o pacote exige e pergunta de forma objetiva o que não está nos documentos: relação de cargas (declaração de carga instalada), disjuntor do padrão de entrada, distância até o quadro, bitola prevista, coordenadas do padrão, configuração de strings se não vier no kit.
3. **Conferir o kit vendido e completar o projeto.** O agente não escolhe equipamento. Confere o arranjo vendido pelos datasheets (tensão e potência de entrada do inversor), escolhe disjuntor e cabo por tabela a partir dos dados da visita e, se a configuração de strings não vier explicitada, propõe a configuração óbvia (uma string, ou dividida entre os 2 MPPTs) marcada como sugestão a confirmar.
4. **Gerar os documentos.** Solicitação de orçamento (Anexo A), memorial descritivo em PDF e unifilar a partir do template residencial correspondente.
5. **Conferir contra as regras.** Aplica R01 a R05 e marca cada uma como aprovada, reprovada ou incerta, com a fonte e os valores. Exemplo: "Corrente máxima de saída do inversor (52,8 A) acima do disjuntor de 50 A." O que as regras não cobrem aparece como "não verificado", nunca como aprovado.
6. **Escalar o que é incerto.** Campo ilegível ou regra que exige julgamento vira pergunta objetiva para o integrador ou para o engenheiro, nunca um chute.
7. **Revisão e assinatura.** O engenheiro vê o que foi gerado e conferido, contra qual item de norma, e o que ficou incerto ou sugerido; aprova e assina a ART. O integrador protocola no Portal GD e o número da solicitação volta para o agente.
8. **Acompanhar no portal.** Consulta o status do portal simulado (UC, e-mail e número da solicitação) e registra cada mudança de etapa com data.
9. **Responder pendências.** Classifica o motivo apontado, explica em linguagem simples, corrige o documento quando possível e vigia o prazo para sanar a pendência.
10. **Aprovar o orçamento e pedir a vistoria na hora.** Orçamento emitido gera o aviso com os 10 dias úteis contando; instalação pronta gera o pedido de vistoria com tudo pronto.
11. **Avisar o cliente final** a cada mudança de etapa (WhatsApp simulado na demo).

**Fase 2 (fora do MVP):** reclamação formal quando a distribuidora estoura o prazo regulatório, citando a REN 1.000 e o protocolo, aprovada com um toque. É registro e escalonamento, não promessa de acelerar a fila.

**Como o fluxo responde à régua de digital worker do Converge.**

| Critério do guia | Onde está no fluxo |
|---|---|
| Fecha o processo, não só um passo | Do envio da conta à troca do medidor |
| Trata a exceção de verdade | Pedido do que falta, estado "incerto" e escalonamento com contexto (passos 2, 5, 6 e 9) |
| Deixa rastro | Cada regra com fonte e valores; tracing de cada execução |
| Mostra o ganho | Projeto conferido em minutos; custo por execução medido |
| Autonomia com humano no loop | O agente decide o próximo passo; responsabilidade técnica e assinatura ficam com o engenheiro |

## Regras e prazos

O MVP confere cinco regras bem demonstradas (R01 a R05); as de distribuidora ficam para a fase 2.

As regras parecem divergir, mas são camadas diferentes; cada regra tem fonte e data de vigência.

| Camada | O que contém | Varia por |
|---|---|---|
| Federal | Lei 14.300, REN 1.000: processo, prazos, enquadramento | Só no tempo (novas resoluções) |
| Técnica geral | NBR 5410, NBR 16690, NBR 16149, exigências do INMETRO para inversores | Só no tempo |
| Distribuidora | Norma própria (CNC-NDBR-DBR-18-0122 na Enel), formulários, ajustes de proteção, portal | Distribuidora e versão da norma |

**Regras do conferidor.**

| ID | Tipo | Regra | Fonte | Entrada |
|---|---|---|---|---|
| R01 | Coerência | O mesmo dado (titular, UC, disjuntor, DPS, potência, nº de módulos, modelo do inversor) é igual em solicitação, memorial e unifilar | Prática; erros recorrentes | MVP |
| R02 | Técnica | Disjuntor CA: corrente de projeto < corrente nominal do disjuntor < capacidade do cabo; sem bitola informada, fica incerta | NBR 5410 | MVP |
| R03 | Técnica | Módulos por string × Voc ≤ tensão máxima CC do inversor, com coeficiente de temperatura fixo marcado "a validar com engenheiro" | Datasheets | MVP |
| R04 | Técnica | Potência dos módulos ≤ potência máxima de entrada CC do inversor | Datasheets | MVP |
| R05 | Documental | Inversor até 75 kW com certificado INMETRO (Portaria 140/2022) para a tensão nominal de conexão | Norma Enel, Tabelas 10 e 11 | MVP |
| R06 | Distribuidora | Coordenada do padrão de entrada coerente com o endereço cadastrado | Cartilha Cemig 2025 | Fase 2: exige geocodificação e a fonte é da Cemig |
| R07 | Distribuidora | Tensão e tipo de ligação coerentes com a potência disponibilizada (monofásica 220 V até 10 kW) | Norma Enel, Tabela 4 | Fase 2 |
| R08 | Distribuidora | Ajustes de proteção do inversor conforme a tabela da distribuidora | Norma Enel, Anexo G ("a informar" para o Ceará) | Fase 2: valores não publicados para o Ceará |

**Prazos que o agente vigia.** Cada prazo aparece na interface com o artigo da norma.

| Etapa | Prazo | Conta contra | Fonte | Artigo |
|---|---|---|---|---|
| Orçamento de conexão (microgeração) | 15 dias sem obras; 30 dias com obras | Distribuidora | Norma Enel, Tabela 9 | REN 1.000, art. 64 |
| Aprovar o orçamento | 10 dias úteis da emissão, sob pena de perder a validade | Integrador | Norma Enel, 7.3.5 | REN 1.000, art. 83 |
| Devolver contratos assinados | 30 dias do recebimento | Integrador | Norma Enel, 7.3.6.4 | REN 1.000, art. 83, § 7º, III |
| Sanar pendência | Até 30 dias da notificação formal | Integrador | Lei 14.300 | A confirmar |
| Vistoria e ligação em BT | 5 dias úteis | Distribuidora | Norma Enel, Tabela 8 | REN 1.000 (a norma cita art. 64) |

## Arquitetura

Um agente orquestrador com ferramentas bem separadas: o LLM lê, decide o próximo passo e escreve; regras, cálculos e prazos ficam em código determinístico, porque errar uma regra de conexão é pior do que não ter a ferramenta.

| Ferramenta | Faz | Tipo |
|---|---|---|
| Extrator | Lê conta de luz, proposta/kit e datasheets; devolve campos com confiança | LLM com visão + esquema fixo |
| Verificador de arranjo | Confere o kit vendido pelos datasheets, escolhe disjuntor e cabo por tabela e sugere a configuração de strings quando ela não vier | Código determinístico (lookup, sem dimensionamento) |
| Gerador de documentos | Preenche a solicitação (Anexo A) e o memorial descritivo em PDF; preenche o unifilar a partir de 2 ou 3 templates SVG residenciais baseados no Anexo B (1 MPPT, 2 MPPTs, microinversor) e exporta PDF | Templates |
| Conferidor | Aplica o repositório de regras por camada, distribuidora e vigência | Código determinístico |
| Portal simulado + leitor | Imita o Portal GD da Enel CE (formulário básico, consulta por UC, e-mail e número da solicitação) e o fluxo de status (protocolado, pendência, orçamento emitido, vistoria, medidor) | Serviço web próprio |
| Classificador de pendência | Mapeia o texto do motivo de recusa para uma categoria e uma correção | LLM com categorias fixas |
| Relógio de prazos | Prazos da REN 1.000 e da norma Enel por processo, com dias úteis e botão de avançar o tempo | Código determinístico |
| Redator | Perguntas ao integrador, explicações e avisos ao cliente | LLM |
| Mensageiro | Chat de integrador e cliente final | Simulado no front |

**Repositório de regras.** Cada regra tem ID, camada, distribuidora (ou "todas"), fonte, data de início de vigência, campos usados e uma função de três estados. O agente pergunta "qual distribuidora e qual data?" e recebe o conjunto certo; o LLM nunca precisa saber a norma de cor.

**Estado de cada processo.** UC, distribuidora, kit, dados da visita, documentos gerados, resultado da conferência, etapa (montagem, em revisão, protocolado, pendência, orçamento emitido, orçamento aprovado, vistoria solicitada, vistoria, medidor, concluído), número da solicitação, datas de entrada em cada etapa e prazos correndo.

**Confiabilidade.** Ferramenta que falha não derruba o processo: o agente registra, tenta de novo e, se persistir, escala com o contexto. Instrução ambígua vira pergunta, não suposição.

**Tracing e custo.** Toda execução grava tokens, tempo, custo e decisão por passo numa tabela do SQLite, exibida como timeline do processo. Langfuse só se plugar em 15 minutos.

**Stack.** Python com FastAPI, modelo com visão, SQLite, portal simulado como rota própria, front simples com painel da carteira, tela de revisão e timeline. PDF gerado com biblioteca em Python puro, para não depender de bibliotecas de sistema no deploy.

## Avaliação

Cada eval responde "isso funciona em algo que não controlamos?"; por isso o peso fica na extração de imagens degradadas, na cobertura das categorias reais de recusa da ANEEL e na classificação de pendências contra uma linha de base.

| Componente | Dados | O que mede | Cuidado |
|---|---|---|---|
| Extração | 10 a 20 contas sintéticas no layout da Enel CE, com gabarito gerado junto, renderizadas também como imagens degradadas (baixa resolução, rotação, desfoque, corte, sombra) | Acerto por campo, % de campos marcados como incertos e erros confiantes (campo errado com confiança alta) | A métrica principal é erros confiantes; a meta é zero |
| Conferência: falso positivo | Projetos sintéticos corretos, montados com kits reais de mercado e validados à mão | Alarmes indevidos em projetos corretos | Não temos projetos aprovados reais da Enel CE; apresentar como controle |
| Conferência: detecção | Variações desses projetos com erro injetado dentro dos documentos (PDF da solicitação, memorial), não no dado estruturado; casos de fronteira (Voc 1% abaixo e acima do limite, disjuntor igual à corrente) | Erros pegos de ponta a ponta (extração + conferência), por tipo | Apresentar como teste de regressão das regras, não como taxa de detecção |
| Cobertura | Categorias de motivo da base ANEEL de pedidos de conexão MMGD, filtrada na Enel CE | Quais categorias de recusa e de prazo o agente previne (documentação incompleta, perda de prazo de aprovação, vistoria não solicitada) | São 18 categorias fixas, não texto livre; categorias sem cobertura aparecem como "não verificado" |
| Resposta a pendência | 40 a 50 textos de pendência sintéticos, escritos a partir das categorias da ANEEL e das cartilhas de reprovação (Cemig, Neoenergia), rotulados em 6 a 8 categorias antes de rodar o modelo | Acerto de categoria contra uma linha de base (palavras-chave ou categoria mais comum) | Textos sintéticos; dizer isso no pitch |
| Custo e latência | 5 execuções completas do processo | Média de tokens, tempo e custo em reais por processo | — |

Prazos não são eval: são testes unitários com datas, fins de semana e feriados.

**A base da ANEEL.** O conjunto "Atendimento a pedidos de conexões MMGD — pós Lei 14300" traz os pedidos de 07/01/2022 a 07/01/2023 por distribuidora, com datas, situação, status e motivo (categoria fixa). O arquivo do Nordeste tem um registro por pedido e por mês de envio: deduplicar por `NumProtocolo` mantendo o envio mais recente. A sigla é `Enel CE`. A Energisa PB não aparece no arquivo do Nordeste.

**Entrega.** Um script `evals/run.py` gera uma tabela em markdown que vira o slide de números.

**Como apresentar no pitch.** "O agente previne X das categorias de recusa e de prazo que a ANEEL registra na Enel CE; zero erros confiantes na extração; Y% de acerto na classificação de pendências, contra Z% da linha de base; nenhum alarme falso nos projetos de controle." Nunca afirmar que o agente achou erros em processos reais.

## Hackathon: escopo, plano e demo

Com dois devs, o MVP faz o núcleo muito bem (conta e kit entram, projeto sai conferido, engenheiro revisa) e mostra o depois do envio num único caminho roteirizado, tudo acessível num link.

| Parte | Status na demo |
|---|---|
| Extração da conta, do kit e dos datasheets | Núcleo, real |
| Verificação do arranjo e seleção de disjuntor e cabo por tabela | Núcleo, real, UC monofásica residencial |
| Geração da solicitação (Anexo A), memorial e unifilar por template | Núcleo, real |
| Conferência R01 a R05 | Núcleo, real |
| Tela de revisão do engenheiro | Núcleo, real |
| Timeline do processo com tracing e custo | Núcleo, real |
| Portal simulado no formato do Portal GD da Enel CE: protocolado → pendência → correção → orçamento emitido | Roteirizado, um caminho |
| Prazos (aprovação do orçamento em 10 dias úteis, pendência, vistoria) com botão de avançar o tempo | Roteirizado |
| Chat com integrador e cliente final | Painel simples no front |
| Evals (extração, cobertura ANEEL, pendências, controles) | Real, com números no pitch |
| Reclamação formal, leitura do portal real, R06 a R08, ampliações, trifásico, acima de 10 kW | Fora |

**Divisão do time.**

- **Dev A (backend do núcleo):** extração, verificador de arranjo, conferidor, geração de documentos e templates.
- **Dev B (front e dados):** painel da carteira, tela de revisão, portal simulado e timeline; no sábado à noite, base da ANEEL e evals.
- **Os dois:** pitch no domingo de manhã. Os dois precisam ter commits desde sábado às 10h.

| Bloco | Foco |
|---|---|
| Sáb 10h–13h | Repositório criado no evento; esqueleto ponta a ponta: conta entra, campos saem, interface mostra |
| Sáb 13h–17h | Verificador de arranjo, regras e conferidor; tracing ligado; deploy do esqueleto; domínio e e-mail configurados (DNS leva horas) |
| Sáb 17h–19h | Contas sintéticas da Enel CE, catálogo de kits e datasheets; pesquisa pública das âncoras de preço |
| Sáb noite | Templates do unifilar, solicitação e memorial; tela de revisão; portal simulado; base da ANEEL e textos de pendência |
| Dom 8h30–11h | Evals rodando, relógio de prazos, pendência e vistoria; landing page |
| Dom 11h–13h | Código congelado, vídeo, slides, submissão |
| Dom 13h–16h | Ensaios do pitch de 3 minutos |

**Roteiro de 3 minutos.**

1. Problema em uma frase e o dado da semana de trabalho técnico por projeto.
2. Painel da carteira com vários processos por etapa.
3. Integrador manda conta e kit; o agente pede a relação de cargas que falta, confere o arranjo, gera o projeto e aponta uma incompatibilidade antes do envio.
4. Engenheiro revisa o projeto conferido, vê o que ficou incerto e assina; número da solicitação entra.
5. Portal mostra pendência; o agente classifica, corrige e reenvia dentro do prazo.
6. Orçamento emitido: aviso dos 10 dias úteis e pedido de vistoria prontos no mesmo minuto, cliente final avisado.
7. Números: cobertura ANEEL, evals, custo por processo vs. trabalho manual, preço, mercado e pedido.

**Checklist de submissão (até dom 13h).**

- [ ] Descrição: problema, para quem, solução e como o agente funciona
- [ ] Vídeo de demonstração
- [ ] Link navegável e testável, com 2 ou 3 casos prontos para os jurados
- [ ] Slides do Demo Day
- [ ] Ferramentas, modelos e APIs declarados
- [ ] Site em domínio próprio e e-mail no mesmo domínio (condição para os créditos AWS)
- [ ] Time de 2 a 4 pessoas com histórico de commits a partir de sábado às 10h

## Fases, riscos e validação

O agente começa conferindo, gerando e lendo portais; só passa a protocolar quando a conferência provou que não erra regra.

| Fase | O agente faz | O humano faz | Gate para avançar |
|---|---|---|---|
| 1. MVP e hackathon | Confere o kit, gera e confere o projeto, acompanha o portal (leitura), responde pendências, vigia prazos | Revisa, assina a ART e envia no portal | Integradores pagando; conferência sem erro de regra validada por engenheiro |
| 2. Protocolo assistido | Lê o Portal GD real da Enel CE e RJ; protocola e pede vistoria; regras R06 a R08; reclamação formal por atraso | Revisa e assina antes de cada envio | Taxa alta de envios aprovados sem correção humana |
| 3. Escala | Cobre Enel SP, outras distribuidoras e trifásico; software para centrais de homologação | Aprova exceções | Volume que justifique cada nova integração |

| Risco | Mitigação |
|---|---|
| Regra técnica errada | Engenheiro valida as regras; regras em código, com fonte e vigência; evals com controles e casos de fronteira |
| Jurado questionar o dimensionamento | O agente não dimensiona: confere o kit vendido e seleciona proteções por tabela; sugestões aparecem marcadas a confirmar |
| Eval parecer circular | Erro injetado dentro do documento, casos de fronteira e métricas com dado real (categorias ANEEL da Enel CE) |
| Sem projetos aprovados reais da Enel CE | Projetos de controle sintéticos validados à mão; buscar projetos reais com integradores do Ceará depois do evento |
| Gerar documentos já é commodity | Pitch lidera com conferência contra a norma e condução do processo depois do envio |
| Dados da visita não chegam | O agente pergunta o que falta; regra sem dado fica incerta, nunca aprovada |
| Dor fraca na distribuidora escolhida | Promessa centrada no tempo do integrador (elaboração e prazos), que existe mesmo com distribuidora rápida; na Enel CE os residenciais quase não são negados, então o argumento é tempo e prazo, não recusa |
| Portal sem consulta aberta ou instável | Na Enel CE e RJ a consulta é aberta; leitura real só na fase 2, com termos de uso conferidos |
| Assinatura soar como acobertamento | Revisão real na tela de revisão; engenheiro assume a responsabilidade técnica |
| Mercado de GD desacelerando | Ampliações, trocas de inversor e base instalada seguem gerando processos |
| Dados pessoais na conta de luz | Dados sintéticos na demo; em produção, mínimo necessário e consentimento do titular |

**Validação pendente.**

- [x] Norma técnica da Enel CE com documentação exigida, formulário e modelo de unifilar (CNC-NDBR-DBR-18-0122-EDBR v05)
- [x] Baixar a base de pedidos de conexão da ANEEL (Nordeste) e filtrar a Enel CE
- [ ] Contar as categorias de motivo e situação da Enel CE para a métrica de cobertura e entender o preenchimento de "art. 89, I" nos pedidos conectados
- [ ] Escrever e rotular 40 a 50 textos de pendência em 6 a 8 categorias
- [ ] Validar R02 a R05 e o coeficiente de temperatura da R03 com um engenheiro (mentores do evento)
- [ ] Confirmar o artigo do prazo de 30 dias para sanar pendência na Lei 14.300
- [ ] Depois do evento, perguntar a integradores do Ceará: quem monta o projeto, quanto tempo leva, que software usa, quantas vezes volta da Enel, quanto pagam hoje por processo a terceiros, e quem define strings e proteções e em que momento

**Critério de desistência.** Se integradores disserem que o projeto sai em minutos com o software atual e quase nunca volta com pendência, pivotar para a etapa que eles apontarem como dolorosa, mantendo o mesmo cliente e a mesma estrutura de agente.

## Integradores em João Pessoa

Contatos levantados na v3.1, quando a demo era na Energisa PB. Não há ligações durante o hackathon; servem para validação depois do evento e para a expansão à Energisa.

| Integrador | Bairro | Telefone | Por que contatar |
|---|---|---|---|
| FCG Energia Solar | Planalto da Boa Esperança | (83) 99851-5428 | Liderada por engenheiro; candidato a validar regras |
| Megga Sun | Treze de Maio | (83) 3024-4889 | Maior volume de avaliações; cuida do envio à Energisa |
| PB Energia Solar | Manaíra | (83) 99177-2095 | Porte médio |
| Synergy Energia Engenharia | Estados | (83) 99114-9635 | Residencial e comercial |
| Solar Investe | Brisamar | (83) 99419-5878 | Relatos de demora para dar entrada na Energisa |
| Paraíba Solar | Tambauzinho | (83) 98680-0340 | Porte pequeno a médio |
| Eletroserv Energia Solar | Manaíra | (83) 98725-3494 | Porte pequeno a médio |
| ENOVAR Engenharia e Energia | Portal do Sol | (83) 99194-5120 | Engenharia |

## Fontes

**Mercado e dor**

- Geração distribuída supera 4,3 milhões (Exame)
- GD deve crescer 15% em 2026, projeta ABGD (Canal Solar)
- Energia solar em casa vale a pena? (Estado de Minas)
- 32 GW de pedidos negados na GD (pv magazine)
- Barreiras na GD, pesquisa Greener (Solfus)
- Protesto na Neoenergia Brasília, 2026 (Canal Solar)
- Atrasos na Equatorial Goiás, 2026 (Canal Solar)
- Fast Track e inversão de fluxo na CPFL (Canal Solar)

**Processo, normas e regras**

- Lei 14.300/2022 (Câmara)
- CNC-NDBR-DBR-18-0122-EDBR v05: Conexão de Micro e Minigeração Distribuída ao Sistema Elétrico da Enel Grids Brasil (https://www.eneldistribuicao.com.br/rj/documentos/CNC-NDBR-DBR-18-0122-EDBR%20Conex%C3%A3o%20de%20Micro%20e%20Minigera%C3%A7%C3%A3o%20Distribu%C3%ADda%20ao%20Sistema%20El%C3%A9trico%20da%20Enel%20Grids%20Brasil.pdf)
- Portal GD Enel CE (https://www.eneldistribuicao.com.br/PortalGD/ENELCE/Acessante) e Enel RJ (https://www.eneldistribuicao.com.br/PortalGD/ENELRJ/Acessante)
- NT 6.012 Enel SP (https://www.enel.com.br/content/dam/enel-br/one-hub-brasil---2018/sp/padroes-normas-tecnicas-espec/NT%206.012-5.pdf)
- NDU-013 v9.0 (Energisa)
- Passo a passo da plataforma de projetos (Energisa)
- Cartilha de reprovações micro GD (Cemig, 2025)
- Como evitar reprovações (Neoenergia)
- FAQ de geração distribuída (CPFL)
- FAQ MMGD (Neoenergia Coelba)

**Venda e projeto (kit definido na venda, engenharia valida depois)**

- Proposta comercial com etapa de validação pela engenharia (SolarMarket)
- Guia de profissionais especialistas (ABSOLAR)

**Dados para avaliação**

- Atendimento a pedidos de conexões MMGD, pós Lei 14300 (ANEEL, https://dadosabertos.aneel.gov.br/dataset/atendimento-mmgd-mini-e-micro-geracao-distribuida)
- Dicionário de dados dos pedidos de conexão (ANEEL)
- Grupo Geração Distribuída nos dados abertos (ANEEL)
- Relatório de estágio com 6 projetos aprovados na Energisa PB (UFCG, 2024)
- Normalização dos dados técnicos de GD da ANEEL (GitHub)

**Concorrência**

- EcoPower na ABF Franchising Expo (Portal do Franchising)
- Vaga de estágio Spinatec (Poli-USP)
- Documentos automáticos no SOLergo (Canal Solar)
- Solarius PV (ACCA)
