# Evidências ampliadas da dor na homologação solar

**Avaliação comercial revisada:** para distinguir demora relatada, contratação de
homologadoras e disposição a pagar pelo nosso produto, consultar
[validação comercial da homologação](validacao-comercial-homologacao.md).
A ordem abaixo avalia contexto do problema; não é prova suficiente de compra ou
de redução do prazo final pelo agente.

Pesquisa de 07/11/2026. A pergunta é se o processo atual apresenta falhas e retrabalho
observados, além da possibilidade de executar tarefas mais depressa.

## Ordem de relevância para justificar o problema do produto

A dor considerada é o tempo e esforço até a conexão e o início da geração, inclusive
em pedidos aprovados. Documentação incompleta é uma das possíveis causas. Separar
duração total, atraso comprovado e tempo que a solução consegue reduzir.

1. **Fiscalização Arce / Enel CE:** fonte reguladora e distribuidora do produto.
   Em 2024, 1.444 reclamações MMGD e 353 casos analisados; comunicado relata
   atrasos de vistoria (34,4%), orçamento (26%) e análise/resposta (5%). Os
   percentuais da fiscalização não representam todos os pedidos e não devem ser
   somados. [Comunicado da Arce republicado pela ABAR](https://abar.org.br/arce-aplica-multa-de-r-194-milhoes-na-enel-ceara/).
2. **Duração na base ANEEL / Enel CE:** cálculo próprio, pedidos B1 até 10 kW,
   solicitações de 2022–início de 2023; 23.571 pares válidos solicitação/injeção,
   mediana 33 dias e percentil 90 de 86 dias. Quantifica duração observada no público
   próximo ao produto, sem medir quantos dias são excessivos ou evitáveis. Exclui
   datas ausentes/negativas e não estima a espera final dos pedidos ainda abertos.
   [Método e agregados](../evidencias/dor-aneel-enel-ce.json).
3. **Auditoria UFCG:** consequência concreta da demora, com 15 sistemas contratados
   por R$ 2,92 milhões sem operação após mais de dois anos no período auditado.
   Causas documentais, adequações físicas e restrição de rede; sistemas maiores que
   o recorte do produto. Não atribuir todo o período à documentação.
4. **Estudo Unisinos / RGE-CPFL:** proximidade do recorte até 10 kW e análise do
   mecanismo de retrabalho. Potencial proposto de melhoria não é redução operacional
   verificada nem resultado do nosso agente.
5. **Negativas ANEEL e cartilha CEMIG:** evidência de causas documentais e devoluções.
   A contagem de negativas não mede os dias acrescentados ao processo, e a análise
   de atrasos também precisa incluir pedidos conectados após correções.
6. **Oferta e métricas de empresas:** referências de esforço e valor econômico;
   horas e volumes comerciais autodeclarados têm menor força que dados regulatórios.
7. **Orçamento de Santa Cruz da Conceição:** evidencia custo previsto da etapa,
   sem medir demora ou desperdício. Tarumã e UFABC permanecem fontes complementares
   com as limitações descritas adiante.

Justificativa: há evidências de atrasos no atendimento, duração relevante até a
injeção e instalações que demoraram a operar. Preparação documental, reenvios e
acompanhamento são partes desse fluxo. A parcela de demora reduzida pelo produto
precisa de medição própria; cumprimento de obras, análise da distribuidora e
limitações da rede afetam o resultado mesmo com documentos corretos.

## 1. Pedidos negados por documentação: análise da base oficial ANEEL

Fonte: [Atendimento a pedidos MMGD](https://dadosabertos.aneel.gov.br/dataset/atendimento-mmgd-mini-e-micro-geracao-distribuida).
Cálculo próprio sobre o ZIP Nordeste, não uma estatística publicada pronta pela ANEEL.

| Estado / distribuidora | Pedidos solares B1 até 10 kW | Negados: documentação incompleta | Parcela do recorte |
|---|---:|---:|---:|
| Alagoas / Equatorial | 18.380 | 3.206 | 17,44% |
| Maranhão / Equatorial | 14.261 | 1.462 | 10,25% |
| Rio Grande do Norte / Cosern | 18.357 | 856 | 4,66% |
| Piauí / Equatorial | 16.024 | 545 | 3,40% |
| Sergipe / Energisa | 4.257 | 98 | 2,30% |

Nessas cinco distribuidoras: 6.167 pedidos com essa classificação em 71.279 pedidos
do recorte. A seleção não representa todos os estados nem o mercado nacional.

Método: leitura de 13.690.608 linhas; deduplicação por distribuidora e protocolo,
preservando a maior `DatPrzEnvio` e a última linha em empate. No recorte apresentado:
B1 residencial, fonte UFV, potência positiva até 10 kW e solicitação de 07/01/2022 a
07/01/2023, inclusivos. Contar documentação incompleta somente se o último status
é negado e o motivo declara documentação incompleta. Arquivo gerado em 28/10/2026;
para as cinco distribuidoras selecionadas, há referências de envio até 30/09/2026.

Interpretação: há falhas documentais efetivamente registradas em pedidos de sistemas
pequenos. A presença de um motivo explícito é evidência mais direta do que usar o
prazo total de conexão como medida de ineficiência.

Limites: último estado disponível, não taxa de rejeição na primeira tentativa nem
frequência de toda pendência histórica. Um projeto pode gerar mais de um protocolo.
Os dados são informados pelas distribuidoras; não auditamos os documentos de cada
pedido. Diferenças de preenchimento impedem tratar a comparação como ranking de
qualidade. Não é taxa nacional nem projeção para Enel CE. Não identifica ligação
monofásica. A base contém datas fora da coorte declarada e combinações anômalas de
distribuidora/UF; por isso aplicamos datas explícitas e selecionamos agentes cujo
campo UF corresponde integralmente ao estado apresentado. Não rotular outras não
conformidades ou inversão de fluxo como erro documental.

[Agregados, datas e hash do ZIP](../evidencias/dor-aneel-nordeste.json).
Reprodução: `python scripts/analisar_dor_nordeste.py data/pesquisa/nordeste.zip --saida docs/evidencias/dor-aneel-nordeste.json`.
O grupo `b1_solar_ate10kw` aplica todos os filtros acima; `b1_ate10kw` mantém o
recorte exploratório sem filtro de fonte/data. Nenhum identificador pessoal ou
protocolo é exportado.

## 2. Minas Gerais: a CEMIG identifica os erros que efetivamente geram reprovação

[Cartilha oficial — orientações para aprovação de microgeração](https://www.cemig.com.br/wp-content/uploads/2025/08/Cartilha-Orientacao-Responsaveis-Tecnicos-MICRO-GD.pdf),
9 páginas, original baixado. A distribuidora lista 13 motivos: ausência de anexos,
divergências de localização/endereço, potência e demanda inconsistentes e campos
incompletos, entre outros. Nas páginas 3–6 do PDF, descreve verificações entre
formulários, diagrama e cadastro; identifica divergência de coordenadas como o
principal motivo naquele documento. Isso sustenta a utilidade de conferir dados
entre documentos antes de protocolar, sem estimar quantos casos o agente evitaria.

Uma cartilha anterior indexada traz percentuais, mas seu original está indisponível
e existem versões diferentes. Esses percentuais **não foram usados**. A cartilha
consultada também não deve ser tratada como validação normativa da Enel CE.

## 3. Rio Grande do Sul: pesquisa acadêmica do processo da RGE/CPFL

Ingrid Kirsch, Unisinos, defesa em 02/12/2021:
[Análise e proposta de melhoria em sistema de aprovação de projetos de microgeração fotovoltaica](https://www.repositorio.jesuita.org.br/handle/UNISINOS/13018?show=full).
O estudo examina sistemas até 10 kW, com informações da equipe da distribuidora,
normas e organização das análises. Documenta retrabalho e propõe mudanças na
solicitação e conferência dos documentos. O resumo informa potencial de redução
de recusas de até 71,48%; não verificamos um antes/depois operacional que permita
usar esse percentual como resultado implantado ou promessa do nosso produto.

Acesso: metadados/resumo e trechos indexados do PDF; o download integral retornou
verificação de acesso. O trecho indexado da página 37 descreve reenvio de pedido
corrigido com nova análise das informações. É evidência qualitativa de um mecanismo
de retrabalho, sem extrapolação de horas ou taxa atual de rejeição.

## 4. Instalação em órgão público: auditoria da UFCG, Paraíba

[Relatório de auditoria 004/2024, original no portal oficial](https://www.gov.br/ufcg/pt-br/composicao/assessoramento/auditoria-interna/relatorios-de-auditoria/r0424-placas-fotovolticas.pdf/@@display-file/file),
28 páginas, baixado e lido. Período auditado: 04/01 a 28/06/2024.

Contrato 002/2021: 15 sistemas de 50 kWp, R$ 2.924.850,00, distribuídos entre
Campina Grande, Sumé e Sousa. A auditoria registra que não haviam entrado em
operação após mais de dois anos. Em Sousa, houve rejeição em junho de 2022 por
divergência das cargas informadas e cadastro, substituição de transformador e novo
pedido em dezembro, recusado em janeiro de 2023 por limitação na rede. Em Campina
Grande também houve incompatibilidade cadastral e adequações de subestação.

É uma consequência concreta de conexão mal resolvida, com equipamento instalado
sem produzir. Há causas documentais, físicas e de rede: **não atribuir os dois anos
nem o valor inteiro à documentação**. O investimento não é prejuízo definitivo nem
economia capturável pelo agente. As pendências de Campina Grande e Sumé haviam
sido sanadas ao fim do relatório, faltando reavaliação; não afirmar situação atual.
Pombal é outro sistema, com defeito de manutenção, fora desse conjunto de 15.

Localizadores: PDF p. 8 (contrato); pp. 18–22 (conexão); p. 27 (conclusão).

## 5. Empresas: oferta e métricas declaradas de um concorrente direto

[Reonic — serviço de homologação](https://reonic.com/pt-br/product/360h/grid-registration/)
anuncia serviço por R$ 399 até 37,5 kWp, 430 solicitações enviadas e até 12 horas
administrativas economizadas por projeto. Coleta de dados, diagramas, conferência
técnica, protocolo e acompanhamento são parte da oferta.

Isso dá evidência de oferta comercial para resolver a mesma tarefa e uma referência
de valor. Volume e horas são declarações da prestadora: não há método de medição
ou auditoria independente apresentados na página. Não usar as 12 horas como
baseline comprovado, nem preço anunciado como prova de pagamento por clientes.

A [WEG também descreve](https://www.weg.net/solar/blog/homologacao-de-energia-solar-como-evitar-falhas-e-atrasos-na-documentacao-com-a-distribuidora/)
retornos para reanálise, perda de prazos e impacto na margem por erros documentais.
É diagnóstico qualitativo da empresa, disponível no texto indexado; acesso direto
retornou 403. Não oferece amostra ou frequência mensurada.

## 6. São Paulo: custo público previsto e outros processos localizados

[Santa Cruz da Conceição, orçamento de 07/04/2025](https://santacruzdaconceicao.sp.gov.br/wp-content/uploads/2025/05/PLANILHA-ORCAMENTARIA-PLACAS.pdf):
Centro de Lazer do Trabalhador, sistema de 101,37 kWp. A rubrica 1.3 prevê
R$ 3.666,67 para homologação e comissionamento; total da obra R$ 590.550,00.
É orçamento, não pagamento comprovado, e inclui comissionamento físico. Sustenta
que há custo previsto para essa etapa, não prova desperdício.

[Tarumã, requerimento 05/2026](https://www.taruma.sp.leg.br/doc/materia/6865?imagedoc=1):
a Câmara solicita documentos sobre usina escolar alegadamente paga e sem operação,
incluindo protocolos e pareceres de conexão. Sem resposta do Executivo verificada,
permanece uma denúncia a esclarecer, não falha de homologação comprovada.

[UFABC, defesas do programa de Energia](https://sig.ufabc.edu.br/sigaa/public/programa/defesas.jsf?id=202&lc=pt_BR):
Juscelino Batista dos Santos, defesa em 30/05/2022, estudo dos aspectos
administrativos e jurídicos para implementar programas de P&D regulados pela ANEEL
em instituições públicas de ensino superior. Resumo descreve estudo de caso com
entrevistas e BPM sobre entraves documentais e impactos no início das atividades.
Trata de contratação institucional; não transferir seus resultados à homologação
residencial. Resumo consultado, sem resultado quantitativo validado.

## Alegação sustentada

Há pedidos reais de sistemas residenciais pequenos negados por documentação
incompleta em diferentes estados. Uma distribuidora publica os erros que geram
reprovação; universidade estuda o retrabalho do processo; auditoria registra sistemas
públicos sem autorização de operação. É sustentação da existência do problema.
Ainda falta medir qual fração dessas falhas nosso agente evita e o valor dessa
redução para o integrador da Enel CE.

[Manifesto de fontes baixadas e hashes](../evidencias/fontes-pesquisa-ampliada.json).
Originais em `data/pesquisa/` são ignorados pelo Git; somente agregados e pesquisa
são preparados para versionamento. Não houve alteração funcional no produto.
