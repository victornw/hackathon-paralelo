# Custo por processo de homologação residencial: dados, lacunas e protocolo de medição

Consulta: 07/11/2026. Rótulos: **VERIFIED** (abri a fonte), **REPORTED** (só vi em resultado de busca ou em
fonte secundária que não consegui abrir), **INFERRED** (conta ou hipótese minha). Câmbio usado nas conversões:
R$ 5,50/US$, suposição minha (INFERRED), sem fonte aberta; confirmar no dia.

## 0. Resumo executivo

- Não existe estimativa pública de **horas de trabalho** por homologação residencial. Só há **prazos corridos**
  (dias/semanas). Qualquer "economizamos N horas" precisa vir da nossa medição (seção 5).
- Custo de modelo por execução, a preços públicos de mercado: **~R$ 0,01 a R$ 0,04** (13k tokens). É desprezível
  perto de ART (R$ 108,39) e do tempo de revisão do engenheiro. O custo relevante é a **revisão humana**.
- Achado de risco: o plano flat de US$ 25 da Featherless (Chat) **proíbe agentes, tráfego de API de produção e
  automação em segundo plano**. O plano permitido para isso é o Developer (créditos por token, a partir de US$ 50/mês).
  Não dá para afirmar "custo por execução ~ zero porque é assinatura flat".
- Preço de mercado terceirizado: **R$ 450 a R$ 690** (residencial até 10 kWp), ART/TRT incluída só em parte dos casos.

## 1. Insumos de custo de mão de obra

### 1.1 Salário mínimo e piso
- Salário mínimo 2026 = **R$ 1.621,00**, vigente desde 01/01/2026, DOU de 24/12/2025. VERIFIED
  (Jovem Pan, abaixo). Número do decreto (12.797/2025): REPORTED (resultado de busca).
- Lei 4.950-A/66: piso = 6 SM para jornada de 6 h; 7,25 SM para 7 h; 8,5 SM para 8 h. Em R$ de 2026 isso daria
  9.726 / 11.752 / 13.778. VERIFIED só como tabela de cálculo do blog Engenharia 360 (13/01/2026, atualizado 21/01/2026);
  a conta é do blog, não de norma.
- **O piso em R$ é disputado.** Confea (03/08/2026): STF na ADPF 171 vedou a correção automática pelo SM; a FNE defende
  R$ 9.726 (6 h) e R$ 14.589 (8 h); atualização em debate (MP 1.334/2026 citada pela página). VERIFIED. Busca também aponta
  PL 5.346/2026 (piso ~R$ 14 mil a partir de 2027, ainda não é lei) e convenção SP de R$ 11.293,70: REPORTED.
  Conclusão: **não usar o piso como custo**; usar salário praticado (CAGED).

### 1.2 Salários praticados (CAGED via Salario.com.br, página atualizada em 05/11/2026, janela 10/2025 a 09/2026)
| Cargo | Média | Mediana | Faixa | n | Status |
|---|---|---|---|---|---|
| Engenheiro eletricista (CBO 2143-05), 42 h/sem | R$ 11.265 | R$ 11.799 | 9.103 a 16.817 | 5.235 | VERIFIED |
| Técnico de projeto eletrotécnico (CBO 3131-10), 43 h/sem | R$ 3.599 | R$ 3.219 | 2.746 a 5.452 (P25-P75: 2.480 a 4.000) | 2.532 | VERIFIED |
- Engenheiro, outras fontes (todas por busca): Glassdoor R$ 9.375; Novo CAGED via toexceed ~R$ 11.215 (out/2026);
  Catho R$ 6.800 sem data. REPORTED. Engenharia 360 (VERIFIED) dá média geral "Engenheiro" R$ 8.000 (Glassdoor/CAGED, jan/2026).
- Amostra CAGED = admissões/desligamentos CLT em 12 meses, não estoque de empregados nem PJ; tende a refletir salário de
  entrada. Salario.com.br tem página para "Técnico de operação eletrotécnica" com média R$ 3.300 (REPORTED).
- Estagiário de engenharia elétrica 2026: vagas de R$ 1.200 a R$ 1.233 (Belém, Unifor/abril) e programas grandes a
  partir de R$ 2.150 (Serasa). REPORTED (busca, não abri as vagas). Pesquisa Cia. de Estágios 2023: média R$ 2,6 mil. REPORTED.

### 1.3 Encargos (multiplicador sobre salário bruto)
- Razonet (publicado 19/08/2026, atualizado 31/08/2026), exemplo de R$ 3.000: **Simples ~1,72x** (R$ 5.159, com VR, VT, plano
  de saúde); **Lucro Presumido ~2,00x** (R$ 5.993). Faixa geral do texto 1,4x a 2,0x; sem benefícios ~1,4x a 1,5x. VERIFIED
  (os multiplicadores são conta feita sobre os exemplos do texto). Componentes: FGTS 8%, 13º 8,33%, férias 11,11%, CPP 20%,
  Sistema S 5,8%, RAT 1 a 3%. Outras fontes por busca: regra prática 1,7x a 2x. REPORTED.
- Estagiário: sem encargos trabalhistas CLT; custo = bolsa + auxílio transporte + seguro (Lei 11.788/08, jornada máx. 30 h/sem no
  superior; conhecimento meu, INFERRED, não abri a lei). O estágio da UFCG era de 40 h/sem (697 h): VERIFIED no PDF.

### 1.4 Custo/hora derivado (INFERRED, aritmética sobre os valores acima)
| Perfil | Base | Mult. | Horas/mês | R$/hora |
|---|---|---|---|---|
| Engenheiro (média CAGED 11.265) | 11.265 | 1,72 a 2,00 | 182 | **106 a 124** |
| Engenheiro (Glassdoor 9.375) | 9.375 | 1,72 | 182 | 89 |
| Técnico projeto (média 3.599) | 3.599 | 1,72 a 2,00 | 186 | **33 a 39** |
| Estagiário (R$ 1.200 a 2.150) | 1.200 a 2.150 | ~1,1 (transporte/seguro) | 130 a 173 | **8 a 17** |
Sugestão: no pitch mostrar **uma faixa** e a fórmula, não um único número. Usar R$ 106/h (engenheiro) e R$ 33/h (técnico) como centrais.

## 2. Horas de trabalho por homologação residencial

**Resultado: nenhuma fonte pública traz horas cronometradas.** Tudo abaixo é prazo corrido ou alegação.

| Dado | Fonte | Natureza | Status |
|---|---|---|---|
| Elaboração ~1 semana (UC monofásica), 1,5 a 2 semanas (trifásica); Illustrator; planilha Energisa; treinamento prévio de 4+2 semanas | Relatório de estágio UFCG 2024, Ecosol Engenharia, Itaporanga/PB, p. 25 do PDF (`data/pesquisa/ufcg-2024.pdf` no repo; li o texto extraído) | Prazo **corrido** de um estagiário em 40 h/sem, no começo da curva de aprendizado; **não são horas cronometradas**; 1 semana poderia ser 5 a 40 h | VERIFIED |
| Submissão à Energisa/PB + vistoria: 15 dias a 2 meses | mesmo relatório | prazo corrido, depende da distribuidora | VERIFIED |
| Solardesc: elaboração e submissão em 3 a 5 dias úteis após documentação completa; concessionária 15 a 30 dias | solardesc.com/homologacao | promessa comercial, prazo corrido | VERIFIED |
| Raio: protocolo em até 2 dias úteis após documentos completos; aprovação ~15 dias em média | raiosolucoes.com/homologacao | promessa comercial | VERIFIED |
| Treviso: projeto "pronto em até 5 dias"; Projetista Solar: envio em até 3 dias úteis, resposta 3 a 7 dias úteis | sites das empresas | promessa comercial | VERIFIED |
| Projeto elétrico 5 a 10 dias + ART 1 a 3 dias; projeto técnico 3 a 7 dias úteis; processo completo 30 a 90 dias | blogs (SolarMarket diz "até 90 dias"; E4 diz "34 dias úteis" teórico) | prazo corrido, genérico | VERIFIED (SolarMarket, E4); demais REPORTED |
| "Integradores gastam até 62% do tempo total de projetos em processos burocráticos e documentais", citando Greener | SolarZ (29/04/2026) | **Não localizei no PDF da Greener do repo** (o único "62%" no texto extraído é um gráfico de tarifa). Não usar. | REPORTED, tratar como não confirmado |
| Gargalo é documentação inconsistente (potência diferente entre formulário, memorial, unifilar, datasheet), que reinicia a contagem | SolarMarket (VERIFIED), SolarZ, Burtet (VERIFIED) | qualitativo, sem taxa | VERIFIED |
| Pendências: relato de integrador com ~15 projetos terceirizados, 14 recusas, pendências comunicadas com 7 a 8 dias de atraso | Reclame Aqui NR Solutions/DSA (19/11/2024), via `docs/pesquisa/validacao-comercial-homologacao.md` | anedota, sem auditoria; não abri (403 relatado no repo) | REPORTED |
| 3% do valor da venda é o custo médio da homologação (~R$ 450 sobre kit de R$ 15 mil) | SolarMarket | média alegada; os R$ 450 são cálculo do blog+meu | VERIFIED (3%); R$ 450 INFERRED |

**Horas de pendência**: não há dado. Só o efeito calendário (a contagem reinicia; prazos de parecer 15 dias micro / 30 dias mini,
ou 34/49 dias segundo SolarZ citando REN 1.000/2021).

**Estimativa de ordem de grandeza (INFERRED, não é dado):** o preço de mercado de R$ 450 a R$ 690 equivale a ~4 a 6,5 h de
engenheiro (R$ 106/h) ou 14 a 21 h de técnico (R$ 33/h), antes de margem, imposto e ART/TRT. Isso sugere que o mercado
opera com algo entre poucas horas de engenheiro e ~2 dias de técnico por caso, mas é inferência sobre preço, não medição.
Uma semana de estagiário a 40 h x R$ 8 a 17 = R$ 320 a R$ 680 (INFERRED), coerente com o preço de mercado.

## 3. Tabela de preços terceirizados (residencial)

| Empresa | Preço | Inclui | Não inclui / ressalva | Prazo | Status |
|---|---|---|---|---|---|
| **Raio Soluções** | a partir de **R$ 450** (até 20 kWp); assinantes Raio Pro R$ 250 a R$ 400 | projeto e homologação, unifilar, **TRT**, pedido de vistoria após aprovação, acompanhamento no portal | ART: lista como arquivo baixável, sem dizer se está no preço; Equatorial/Energisa/Neoenergia DF | protocolo em 2 dias úteis; aprovação ~15 dias | VERIFIED |
| **Solardesc** | R$ 490 (1 a 3 kWp); **590** (3,1 a 5); **690** (5,1 a 10); 790 (10 a 15); 890 (15 a 20); 990+ (20 a 75) | engenheiro como RT por procuração; acompanha concessionária; agenda vistoria | página não cita ART/TRT, unifilar, memorial; garantia: aprovação em 30 dias ou devolve | 3 a 5 dias úteis + 15 a 30 dias | VERIFIED (avaliação mais recente na página: 24/06/2024) |
| **Meu Gerador** | R$ 469,42 cheio (12x sem juros); R$ 399,01 com 15% off (a página mostra também um valor Pix truncado, ~R$ 329; inconsistente) | ART por engenheiro eletricista, projeto, unifilar, submissão, acompanhamento **até troca para medidor bidirecional**, orientação de vistoria | **só para quem compra kit na Meu Gerador**; estorno integral se reprovação definitiva (>7,5 kW) | aprovação 10 a 30 dias | VERIFIED |
| **Turon Tecnologia** | ~R$ 650 (1 a 8 kWp); ~R$ 780 (8 a 10); ~R$ 910 (10 a 15); faixa geral R$ 700 a R$ 3.000 | "preparação dos documentos até a autorização"; lista ART como documento necessário | valores aproximados, tabela inconsistente com a faixa; sem data | não informa | VERIFIED |
| **Meubess (blog)** | homologação R$ 200 a R$ 2.500 total; **unifilar R$ 300 a 1.200**; memorial R$ 200 a 1.000; **ART R$ 150 a 450** | itemizado | estimativa de blog, internamente inconsistente, sem data | projeto 5 a 15 dias úteis | VERIFIED (a página; valores fracos) |
| TCJL (Cemig) | R$ 690 (5,01 a 10 kWp) | projeto de homologação | **ART/TRT NÃO inclusa**; página fora do ar quando abri | n/d | REPORTED (trecho de busca) |
| Vendedor no Mercado Livre | R$ 249 (até 2,99 kW) a R$ 499 (7 a 9,99 kW) | projeto | ART de R$ 99 **paga à parte** | n/d | REPORTED (trecho de busca) |
| GD Pro, SolarMarket/Techmax, Burtet, Treviso, Projetista Solar | sem preço publicado | acompanhamento por plataforma, correção de pendências, ART "quando aplicável" (Burtet) | só cotação | 3 a 5 dias | VERIFIED (ausência de preço) |

Leitura: faixa observada **R$ 450 a R$ 690** para até 10 kWp com ART/TRT incluída em ~metade dos casos; sinal de que
ART/TRT é cobrada à parte em anúncios de entrada (Mercado Livre, TCJL). Preços anunciados não são vendas auditadas.

### 3.1 ART e TRT
- **ART 2026, Tabela A (obra ou serviço), CREA-MT, tabela de serviços e ART 2026 (PDF, jan/2026): R$ 108,39 para contrato até
  R$ 15.000,00; R$ 285,59 acima.** VERIFIED (extraí o texto do PDF). Um serviço de projeto/homologação residencial cai na primeira
  faixa. Registro de ART no CREA-PE de abril/2026 com R$ 108,39: REPORTED (busca). Cada CREA publica a sua tabela; o Confea só
  expôs a coluna de 2027 na página que abri (R$ 112,48 / R$ 296,35, Decisão Plenária 0684/2026): VERIFIED, não se aplica a 2026.
  ART de rotina (Tabela B) começa em R$ 2,10, mas não se aplica a projeto novo (INFERRED, ver CREA).
- ART como parcela do preço: 108,39 / 450 = **24%**; / 690 = **16%**; / 290 = 37% (INFERRED).
- TRT (técnico, CFT): valor 2026 **não encontrado**. E4 e JrSolar citam "~R$ 88 ART e ~R$ 55 TRT" (ambos sem data, valores defasados em
  relação a R$ 108,39): VERIFIED que dizem isso, REPORTED como preço vigente.
- Implicação para o pitch: **ART/TRT não é custo que o agente elimina.** Deve ficar numa linha fixa, igual nos dois braços.

## 4. Custo de IA por execução

### 4.1 Featherless
- Plano **Chat**: **US$ 25/mês** flat, 4 concurrent units, contexto 32K, tokens ilimitados, catálogo de 40 mil+ modelos. VERIFIED
  (featherless.ai/pricing e /docs/plans). **Uso "somente interativo, humano": não permitido coding agents, tráfego de API de produção,
  automação em segundo plano, revenda ou benchmarking.** VERIFIED (featherless.ai/pricing). Chat plan não pode ser base do número.
- Plano **Developer**: **a partir de US$ 50/mês em créditos, cobrado por token**; entrada e saída com preços distintos por modelo;
  100 concurrent units; contexto até 256K; só requisições bem-sucedidas são cobradas; créditos não expiram. **Pay-As-You-Go** idem, sem
  mensalidade mínima. VERIFIED. **Os preços por milhão de tokens não aparecem em /pricing, /docs/plans nem em /models** (a página de
  modelos que abri não listava Qwen3-32B nem preço): **não achei o preço Featherless por token**; precisa ser lido no painel logado.
- Unidades de concorrência: modelos <16B = 1 unidade; <35B = 2 (ex.: Qwen 32B); >=70B = 4; excesso retorna HTTP 429. VERIFIED
  (/docs/concurrency-limits). Com plano de 4 unidades: 2 requisições simultâneas de 32B, 1 de 72B.
- Blog Featherless (04/03/2026) mostra versão anterior: Basic US$ 10 (2 req, até 15B), Premium US$ 25 (4 req), Scale US$ 75+; **sem tabela
  de preço por token de Qwen**. VERIFIED. As páginas de hoje mudaram: ao citar planos, usar as páginas de docs, não o blog.
- Hackathon: o código de resgate fornecido não substitui esse enquadramento. Declarar na submissão qual plano/termo foi usado (INFERRED).

### 4.2 Preço por token comparável, Qwen3-32B (OpenRouter, sem markup do provedor)
| Provedor | Entrada US$/M | Saída US$/M | Status |
|---|---|---|---|
| DeepInfra | 0,08 | 0,28 | VERIFIED (openrouter.ai/qwen/qwen3-32b) |
| Tenstorrent | 0,14 | 0,40 | VERIFIED |
| SiliconFlow | 0,14 | 0,57 | VERIFIED |
| Alibaba Qwen API | 0,10 | 0,44 | REPORTED (busca) |
A página não mostrava data; agregadores divergem em ±US$ 0,04 na saída. Ver preço no dia da demo.

### 4.3 Conta de custo por execução (INFERRED; 13k tokens medidos, divisão entrada/saída é suposta: 10k/3k)
- DeepInfra: 10k x 0,08 + 3k x 0,28 = **US$ 0,0016** (R$ 0,009).
- SiliconFlow: 10k x 0,14 + 3k x 0,57 = **US$ 0,0031** (R$ 0,017).
- Pior caso, 13k tudo a US$ 0,57: **US$ 0,0074** (R$ 0,041).
- **Defensável: "menos de R$ 0,05 de modelo por conta+kit, a preços públicos de Qwen3-32B em provedor aberto"**; para o fluxo completo
  (extração, regras, memorial, ciclo de pendências) vale **medir tokens do processo inteiro**: os 13k cobrem só conta+kit.
- Os 2 a 3 min são **latência**, não custo; entram só em "tempo até pacote pronto".
- Fixo: Developer US$ 50 (~R$ 275)/mês, a diluir por volume (100 processos/mês = R$ 2,75 cada) (INFERRED). Fórmula: custo_IA = tokens x preço +
  mensalidade/volume + Langfuse/hospedagem.

## 5. Protocolo de medição para o hackathon

**Objetivo:** estimar custo por processo **aceito** (pacote correto, assinável) nos dois braços, com qualidade igual ou melhor.
**Não medimos:** espera da distribuidora, aprovação, conexão, venda. Só trabalho técnico sob nosso controle.

### 5.1 Desenho
1. **Casos sintéticos**: 12 a 20 (mínimo viável no fim de semana: 8 + 1 de aquecimento por braço), estratificados: monofásico/trifásico, 3 a 10 kWp,
   com **defeitos semeados** (potência divergente entre documentos, disjuntor subdimensionado, string acima do Voc, INMETRO ausente,
   dado de titular errado). Lista de defeitos **fixada e commitada antes** de rodar (hash do commit = pré-registro).
2. **Braço A, baseline humano:** técnico ou engenheiro (não o autor do agente) faz o mesmo pacote com as ferramentas que o mercado usa
   (planilha da distribuidora, editor de desenho, Word/PDF). Mesmas entradas brutas (fatura, ficha do kit, datasheets).
3. **Braço B, agente + revisão:** agente gera pacote; engenheiro revisa, corrige, aprova. Revisor ≠ autor do código do agente.
4. **Cruzado:** cada humano faz casos diferentes em cada braço, ordem alternada (quadrado latino simples) para neutralizar aprendizado e fadiga.
   Nunca o mesmo caso nos dois braços para o mesmo humano.
5. **Segundo avaliador cego** pontua os dois pacotes contra checklist (campos do Anexo A, coerência entre documentos, regras da norma) e
   conta defeitos semeados achados/perdidos e falsas aprovações.

### 5.2 O que medir (planilha CSV por caso, versionada no repo)
- **Tempo ativo** por etapa, cronometrado (pausa para interrupção): leitura de fatura/kit, preenchimento do Anexo A, unifilar, memorial,
  conferência, correção de pendência, montagem do protocolo (mock). Registrar também tempo **corrido** só para mostrar a diferença.
- Braço B: **tempo de máquina** (cronômetro do agente), **tempo de revisão humana** (leitura, edições, nº de edições, nº de campos
  corrigidos), tokens entrada/saída e custo por chamada (Langfuse), nº de reexecuções.
- Qualidade: defeitos semeados detectados (recall), falsas aprovações (meta zero), campos errados no pacote final, retrabalho necessário.
- Custo: horas x R$/h (seção 1.4, mostrando técnico e engenheiro), mais IA, mais ART/TRT constante (R$ 108,39) nos dois braços.
- Para a pendência: casos com uma "carta de pendência" simulada; medir tempo humano para ler, corrigir e reenviar nos dois braços.

### 5.3 Como evitar alegações circulares
- Não usar o conferidor do agente como verdade: a verdade são os **defeitos semeados** e o checklist do avaliador cego.
- Não contar economia de tempo se qualidade do braço B < braço A. Reportar **custo por pacote aceito**: (horas de produção + retrabalho) / pacotes aceitos.
- Medir se o revisor **detecta defeitos plantados no pacote do agente** (viés de automação). Se o recall cair, o ganho de tempo é aparente.
- Humano do baseline com experiência equivalente à do revisor; reportar sensibilidade com estagiário/técnico/engenheiro.
- Reportar **mediana e intervalo**, n pequeno, sem teste de significância; dizer "n=12, sintético, um avaliador". Publicar CSV bruto e export do Langfuse.
- Não projetar sintético para real: fatura, procuração e pendência reais são mais sujas. Dizer isso na tela.
- Preço de mercado (R$ 450 a 690) é **âncora externa**, não custo: preço inclui margem, imposto, risco de ART e espera.

### 5.4 Fórmulas do slide
- custo_humano = horas_ativas x R$/h (técnico 33 a 39; engenheiro 106 a 124) + ART/TRT.
- custo_agente = horas_revisão x R$/h_engenheiro + R$ IA (~0,01 a 0,05) + mensalidade/volume + ART/TRT.
- economia por processo = custo_humano(A) - custo_agente(B), **com os números medidos**. Ex. ilustrativo (hipótese, não dado): 4 h de técnico
  (R$ 132 a 156) vs 20 min de engenheiro (R$ 35 a 41) + R$ 0,05 = economia de ~R$ 95 a 115. **Não usar esse exemplo no pitch.**

## 6. Frases de pitch

**Sustentadas hoje (fonte aberta):**
1. "Terceirizar a homologação residencial custa de R$ 450 a R$ 690 por projeto até 10 kWp, e a ART sozinha é R$ 108,39 (tabela CREA 2026)."
2. "Um relatório de estágio da UFCG, de 2024, descreve cerca de uma semana de elaboração por projeto monofásico, sem cronometragem."
3. "Um engenheiro eletricista custa, em média, R$ 11,3 mil por mês de salário CAGED (≈ R$ 106 a 124 por hora com encargos); um técnico, R$ 3,6 mil (≈ R$ 33 a 39 por hora)."
4. "Nossa execução de conta + kit usa cerca de 13 mil tokens; a preços públicos de Qwen3-32B isso é menos de R$ 0,05."
5. "O custo do modelo é irrelevante; o que importa é o tempo do engenheiro que revisa e assina, e é isso que vamos medir."

**Sustentadas só depois da medição (preencher com número do CSV):**
6. "Em N casos sintéticos, o pacote ficou pronto para revisão em X min de máquina; a revisão do engenheiro levou Y min contra Z min do baseline humano, com W% dos defeitos semeados detectados."

**Não sustentadas (evitar):**
- "Reduzimos uma semana para minutos/segundos": a semana é prazo corrido de estagiário; minutos são só a parte de máquina.
- "Custo por execução ~R$ 0 porque é assinatura flat": o plano flat proíbe agentes/produção; custo real é por token + mensalidade.
- "Economizamos R$ N por homologação" sem baseline cronometrado; ou usando preço de mercado como se fosse custo.
- "62% do tempo é burocracia": não confirmado na fonte primária.
- "Aprovamos em X dias" ou "reduzimos o prazo de conexão": depende da distribuidora, fora do nosso controle.
- "Substitui o engenheiro/ART": a ART/TRT e a decisão técnica continuam humanas, e a ART é custo fixo.
- Qualquer taxa de rejeição/pendência de mercado: só há anedota e texto qualitativo.

## 7. Lacunas a fechar
- Preço por token Featherless do modelo usado (painel logado) e termos de uso para o enquadramento no hackathon.
- Valor TRT/CFT 2026 e tabela ART do CREA-PE/CE (onde o caso real roda); a do MT é referência.
- Horas reais: só a nossa medição ou entrevista com 3 a 5 projetistas ("quantas horas ativas, última vez").
- Split entrada/saída dos 13k tokens (Langfuse) e tokens do processo completo, incluindo pendências.

## Fontes abertas (WebFetch/leitura local)
- https://www.salario.com.br/profissao/engenheiro-eletricista-cbo-214305/ (atualizada 05/11/2026)
- https://www.salario.com.br/profissao/tecnico-de-projeto-eletrotecnico-cbo-313110/ (05/11/2026)
- https://engenharia360.com/os-salarios-dos-engenheiros-em-2026/ (13/01/2026)
- https://www.confea.org.br/piso-salarial-da-engenharia-confea-aumenta-acoes-judiciais (03/08/2026)
- https://jovempan.com.br/economia/macroeconomia/lula-publica-decreto-que-aumenta-salario-minimo-para-r-1-621-em-2026/
- https://razonet.com.br/contabilidade-digital/quanto-custa-um-empregado-clt-em-2026-para-a-empresa (19/08/2026)
- https://www.crea-mt.org.br/portal/wp-content/uploads/2026/01/TABELA-DE-SERVICOS-E-ART-2026.pdf (texto extraído)
- https://www.confea.org.br/profissional/taxas ; https://portal.crea-sc.org.br/anuidades-servicos-multas-e-arts-tem-valores-definidos-para-2026/ (sem tabela 2026)
- https://reonic.com/pt-br/blog/como-emitir-art-energia-solar/ (14/09/2026, sem valores)
- https://raiosolucoes.com/homologacao ; https://solardesc.com/homologacao/ ;
  https://www.meugerador.com.br/products/homologacao-energia-solar-fotovoltaico-de-8-a-10kwp ;
  https://turontecnologia.com.br/blog/quanto-custa-para-homologar-energia-solar/ ; https://blog.meubess.com.br/quanto-custa-para-homologar-energia-solar/ ;
  https://jrsolar.com.br/valor-para-homologar-sistema-fotovoltaico/ ; https://grupoe4.com.br/quanto-custa-para-homologar-energia-solar/ (17/07/2025) ;
  https://burtetengenharia.com.br/servicos/homologacao/ ; https://trevisoengenharia.com/fotovoltaico/ ; https://projetistasolar.eng.br/
- https://www.solarmarket.com.br/blog/terceirizar-homologacao-ou-engenharia-interna ; https://www.solarmarket.com.br/blog/homologacao-energia-solar ;
  https://solarz.com.br/documentacao-projetos-solares-guia-completo/ (29/04/2026)
- https://featherless.ai/pricing ; https://featherless.ai/docs/plans ; https://featherless.ai/docs/concurrency-limits ; https://featherless.ai/docs/faq ;
  https://featherless.ai/blog/llm-api-pricing-comparison-2026-complete-guide-inference-costs (04/03/2026) ; https://featherless.ai/models
- https://openrouter.ai/qwen/qwen3-32b
- Locais: `/Users/victor/programming/hackathon-paralelo/data/pesquisa/ufcg-2024.pdf`, `.../greener-2025-setembro.txt`,
  `.../docs/pesquisa/validacao-comercial-homologacao.md`
- Não abertas (só trecho de busca, REPORTED): tcjlcomercioservicos.com.br (loja fora do ar), listagem Mercado Livre, Workana (403), meutudo.com.br,
  toexceed.com.br, numerando.com.br, engehall.com.br, Unifor/O Liberal (estágio), PL 5.346/2026, openrouter agregadores.
