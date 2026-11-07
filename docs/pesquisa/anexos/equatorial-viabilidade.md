# Equatorial (AL e grupo) como distribuidora-alvo do MVP: pesquisa

Data da pesquisa: 07/11/2026. Escopo: microgeração <= 10 kW, BT, Grupo B.
Legenda: **VERIFIED** = li a fonte (PDF/página aberta); **REPORTED** = fonte secundária ou relato; **INFERRED** = dedução minha.

Observação de método: os sites `*.equatorialenergia.com.br` estão atrás de um WAF (Imperva/Incapsula). `curl` e o WebFetch recebem 302 em loop ou 403. Abrindo no navegador (preview), tudo carrega e todos os downloads retornam HTTP 200. Conclusão: é público para humanos, mas **não é baixável por script simples**. Isso importa para um agente (ver seção 5).

---

## 1. Norma técnica vigente

### 1.1 Identificação (VERIFIED)
- Código real: **NT.00020.EQTL** (não "NT.020"). Título: "Conexão de Micro e Minigeração Distribuída ao Sistema de Distribuição". Classificação "Público".
- **Rev. 07**: elaborada em 27/10/2026, homologada em **30/10/2026**, publicada no site em **04/11/2026** (três dias atrás). 94 páginas. Rótulo "DOCUMENTO NÃO CONTROLADO".
- **Rev. 06**: homologada em 26/12/2025 (elaboração 10/12/2025), 89 páginas. O site a mantém como "Revisão Anterior, válida até 03/03/2027".
- Vigência: a capa diz que a revisão passa a ser exigida "na íntegra após 120 dias ou mais" da publicação, conforme art. 20 da REN 1000. Logo a Rev. 07 é obrigatória a partir de cerca de 04/03/2027. Até lá valem as duas (VERIFIED nas capas; a conta dos 120 dias é INFERRED, mas bate com o "03/03/2027" do site).
- Histórico: Rev. 02 (09/09/2019) unificou a área de Alagoas; 03 (29/03/2022); 04 (24/03/2023, unificou NT.020 e NT.021 e incluiu a CELG-D/Goiás); 05 (12/11/2024); 06 (10/12/2025); 07 (27/10/2026). Ou seja, a norma muda quase todo ano (VERIFIED, tabela de controle de revisões).
- Rev. 06 -> 07 (VERIFIED por diff): a mudança relevante é a inclusão de sistemas de armazenamento (SAE) no unifilar, no diagrama de blocos e no memorial, mais um novo item 5.4. O restante da lista de documentos é igual.
- **Abrangência (VERIFIED, §1 e planilha Anexo I):** um único documento para todo o Grupo Equatorial: **AL, AP, GO, MA, PA, PI e RS (CEEE)**. O Anexo I lista as sedes regionais dos sete estados. Só muda o fuso UTM da planta e algumas notas (Nota 29: bifásico 380/220 V só em RS/GO; Nota 30: monofásico rural 127 V só em PA/AP/RS).

### 1.2 Disponibilidade pública (VERIFIED)
Página oficial AL: `https://al.equatorialenergia.com.br/institucional/leis-e-normas-tecnicas/normas-tecnicas/instalacao-de-padrao` (seção "NT.00020.EQTL"). Também espelhada em MA/PA/PI/CEEE.

| Arquivo | Formato | Download (via navegador) |
|---|---|---|
| NT.00020 Rev 07 | PDF com texto selecionável, 3,0 MB | 200 |
| Anexo I (Formulário de Solicitação de Orçamento, Grupo B) | **XLSX**, 612 KB | 200 |
| Anexo II (idem, Grupo A, micro/mini) | XLSX | listado |
| Anexo III (Modelo de Memorial Técnico Descritivo) | **PDF**, 411 KB | 200 |
| Anexo IV (Formulário de Troca de Padrão) | XLSX | listado |
| Anexo V (Termo de Aceite para dispensa da análise de inversão de fluxo, "Fast Track") | PDF, 50 KB | 200 |

URLs base (AL): `https://al.equatorialenergia.com.br/wp-content/uploads/2026/11/NT.00020.EQTL-07-Conexao-de-Micro-e-Minigeracao-Distribuida-ao-Sistema-de-Distribuicao.pdf` e, no mesmo diretório, `Anexo-I-Formulario-de-Solicitacao-de-Orcamento-de-Microgeracao-Distribuida-Grupo-B.xlsx` e `NT.00020.EQTL-07-Anexo-III-Modelo-de-Memorial-Tecnico-Descritivo.pdf`.
Sem WAF-bypass, o download programático falha (curl: 302 em loop / 403). Obtive o PDF da Rev. 06 e da Rev. 07 pelo WebFetch (que salva o binário) e extraí o texto com `pdftotext`. O texto está legível. Não consegui ler o conteúdo interno do XLSX nem do Anexo III (só confirmei status 200 e tamanho). O conteúdo do Anexo I está reproduzido no corpo da norma (pág. 70) e li essa versão.

### 1.3 Terminologia (VERIFIED)
A norma segue a REN 1000/2021 (alterada pela REN 1059/2023): a etapa é **"Solicitação de Orçamento de Conexão"** (não mais "solicitação de acesso / parecer de acesso", embora o texto ainda use o termo antigo em alguns trechos, p.ex. §6.1.4.1 "reprovação da solicitação de acesso"). Etapas: orçamento estimado (opcional) -> aprovação prévia de projeto (se a norma de fornecimento exigir) -> solicitação de orçamento de conexão -> orçamento -> aprovação -> vistoria e ponto de conexão (§5.11).
**Atenção:** o limite de microgeração é **75 kW** (não 10 kW). O recorte "<= 10 kW" é nosso. Na Tabela 5 a carga/potência <= 10 kW em 220/127 V corresponde ao ponto de conexão monofásico.

### 1.4 Documentos exigidos (VERIFIED, §5.14.2 + Tabelas 3/4 + Anexo I, Rev. 07)
Entrega "através do site da CONCESSIONÁRIA" (§5.14). Regras de forma (§5.14.1): desenhos em CAD (AutoCAD 2007) ou PDF em escala; formulários em Excel ou PDF; demais em PDF; **documentos técnicos assinados e digitalizados pelo responsável técnico, no máximo 5 MB cada**; arquivos nomeados conforme o documento ("Memorial Técnico Descritivo", "Diagrama Unifilar", "Diagrama de Blocos"...).

Pacote residencial típico (autoconsumo local, PF, UC nova ou existente):
1. **Formulário Anexo I** (XLSX, template oficial). Seções: dados da UC, responsável técnico (nome, título, registro, UF), características da microgeração (fonte, potência, modalidade de compensação, potência injetável, SAE), checklist de anexos, declarações.
2. **Documento de identificação do titular** (incisos I e II do art. 67 REN 1000). PJ: documento do representante + contrato/estatuto/ata.
3. **ART/TRT/documento de responsabilidade técnica**, de projeto e de execução. Se forem profissionais distintos, os dois documentos devem ir **juntos na solicitação, "não cabendo envio posterior"** (Nota 5).
4. **Diagrama unifilar**: gerador (P, V, I), inversor (P, V, I), SAE (se houver), quadro, cargas (P, V, I), proteções CA e CC (disjuntores, fusíveis, **DPS CA e CC**, aterramento), disjuntor geral (nº de polos e corrente), medidor, cabos (mm2), barramentos, transformador de isolamento se for o caso; "no caso de inversor mostrar todas as proteções contempladas no mesmo". Unidades obrigatórias: V, A, W/kW, mm2.
5. **Diagrama de blocos** (gerador, inversor, SAE, cargas, proteção, medidor).
6. **Memorial Técnico Descritivo** (modelo Anexo III): identificação da UC; ponto de conexão (tensão, condutores, disjuntor de entrada); **fotos** da caixa de medição (ou do futuro local) e do inversor; dimensionamento de gerador, inversor, disjuntores, DPS, condutores; aterramento; funções de proteção do inversor (27, 59, 81U, 81O, 25, anti-ilhamento etc.); características do gerador/inversor (V, A, W e VA, fator de potência, THD, eficiência); detalhes de montagem do padrão e do inversor com **placa de identificação a no máximo 1,80 m do piso** (não se aplica a microinversores, Nota 7); **planta de localização** com coordenadas (AL: UTM 24 ou 25, ou graus decimais), poste mais próximo, ramal e ponto de conexão. Planta e levantamento de carga só são obrigatórios em **ligação nova** (Notas 6 e 8).
7. **Relatório de ensaio em português** atestando conformidade dos conversores (inversores) à tensão de conexão (§5.14.2 g).
8. **Documento datado de propriedade ou posse do imóvel**: só para ligação nova de UC com microgeração ou aumento de potência disponibilizada (Anexo I item 13; Tabela 4).
9. **Procuração** quando houver terceiro. Inconsistência na própria norma: Anexo I diz "Procuração Autenticada", Tabela 4 diz "Procuração Registrada". Mais o documento de identificação do procurador.
10. Condicionais: lista de UCs beneficiárias (aba 2 do Anexo I; remoto/compartilhado); instrumento jurídico (múltiplas UCs); Formulário de Troca de Padrão (Anexo IV) se mudar fases/potência disponibilizada; manual do inversor/controlador de exportação se houver limitação de injeção ou Grid Zero; autorização de condomínio; licença ambiental em área protegida; dados de registro da central no site da ANEEL.
11. **Fast Track** (§5.16.8 c): autoconsumo local <= 7,5 kW dispensa a análise de inversão de fluxo; exige o **Anexo V assinado** na solicitação e proíbe compartilhar créditos com outra UC. Para um residencial <= 7,5 kW isso é decisivo: a opção errada gera "enquadramento indevido" (§5.16.12).
Removidos nas Revs. 05/06 (não exigir mais): relatório de comissionamento, cronograma/estágio do empreendimento, levantamento de carga e planta de situação para ligações existentes.

### 1.5 Requisitos técnicos (VERIFIED, §6.1 e Tabelas 5/7/8)
- **Inversor <= 75 kW: obrigatório registro INMETRO (Portaria 140/2022)**, "evidenciado na solicitação"; sem registro ocorre reprovação da solicitação e do ponto de conexão (§6.1.4.1). Acima de 75 kW: certificados NBR 16149/16150/IEC 62116 ou IEC 61727/IEEE 1547.
- Anti-ilhamento conforme ABNT NBR IEC 62116 e NBR 16149, sem retardo intencional. Não exige relé específico. Funções do inversor bastam em microgeração (redundância desnecessária, §6.1.7.1 b). Proibido "salto de vetor" (§6.1.7.2).
- Inversor em local de fácil acesso para a distribuidora, "imprescindível para aprovação" na vistoria (§6.1.1 c); equipamentos de padrão de entrada devem ser os homologados pela concessionária (§5.9.1 b).
- Potência de microgeração <= potência disponibilizada da UC (§6.1.5). Potência considerada = potência nominal de saída do inversor (ou potência máxima injetável, se limitada).
- **Monofásico (Tabela 5, 220/127 V):** carga da UC <= 10 kW -> ponto de conexão monofásico, microgeração <= 10 kW, conexão monofásica a 127 V. Em 380/220 V: <= 12 kW monofásico. Carga 10 a 15 kW -> bifásico, geração <= 15 kW. Inversores monofásicos podem ligar em sistemas monofásicos, bifásicos ou trifásicos (balanceando as fases). Inversores trifásicos só em sistema trifásico. Não se pode reduzir fases só por causa da GD (§6.1.2 c).
- Placa de advertência obrigatória (policarbonato anti-UV, §6.1.9). DSV só quando aplicável.

### 1.6 Prazos regulatórios citados na norma (VERIFIED)
Orçamento de conexão em microgeração: 15 dias sem obras, 30 com obras. A distribuidora tem **5 dias úteis para verificar se a documentação está completa** e deve "indeferir a solicitação e comunicar as não conformidades" (§5.15.1.7), com protocolo obrigatório (§5.15.1.10). Aprovação tácita em 10 dias úteis se não houver participação financeira. Vistoria: até 5 dias úteis (< 2,3 kV); relatório em até 3 dias úteis. Reprovação na vistoria: sem nova solicitação em 120 dias, ou reprovação repetida pelo mesmo motivo, cancela o orçamento.
Este é o ponto mais valioso para o produto: o indeferimento por documentação tem janela de 5 dias úteis e a norma lista os itens exatos.

---

## 2. Como se submete e acompanha em Equatorial AL (VERIFIED, navegador, 07/11/2026)

- Canal: **Agência Virtual** (`https://agenciavirtual.equatorialenergia.com.br/`), tela "Geração distribuída" (`/GeracaoDistribuida/`). Texto: "canal para que você efetue diretamente a solicitação de orçamento de conexão... aprove o orçamento e solicite a vistoria/conexão". Dois botões: "Solicitar orçamento de conexão GD" e "Solicitar vistoria GD". Portal único para AL, AP, MA, PA, PI e RS (Goiás não aparece na lista de estados do formulário; REPORTED que GO usa e-mail gd.goias@equatorialenergia.com.br desde a desativação do SICAP em abril de 2025).
- O botão de GD está na seção "**Acesse sem fazer login**" da tela de entrada. O assistente tem 3 passos: "1. Selecionar tipo; 2. Preenchimento dos dados; 3. Anexo". O passo 1 pede tipo (micro até 75 kW / mini), estado, **CPF/CNPJ do titular e número da unidade consumidora**. Não submeti nada. Não sei se o passo 2 ou 3 exige login ou código (INFERRED: provavelmente identifica pelo CPF + UC).
- Aviso explícito no passo 1: **todas as faturas da unidade geradora devem estar quitadas; se houver fatura vencida, "sua solicitação será indeferida"**. Esta é uma causa de indeferimento não documental que o agente deve checar antes.
- Acompanhamento: `/solicitacao/AcompanharSolicitacoes` **funciona sem login**: informar estado, unidade consumidora e **protocolo**. Com login mostra todas as solicitações dos últimos 12 meses. O formulário de pesquisa só mostra status (não testei com protocolo real).
- Notificações por e-mail: **não verificado** para a Equatorial. O Anexo I tem opção de receber faturas/comunicações por e-mail (declaração opcional). Para a Neoenergia a notificação por e-mail a cada mudança de status está documentada (seção 4).
- Anexo no portal: tamanho máximo por arquivo 5 MB na norma. Reclamação em AL (REPORTED, ligação nova, não GD) cita rejeição por tamanho de arquivo.
- Páginas antigas de AL (`/sua-conta/mini-e-micro-geracao/...`, matérias de 2022) retornam 404 hoje: o fluxo migrou para a Agência Virtual. Isso invalida guias de terceiros de 2022 a 2024.
- Canais humanos: 0800 082 0196 (atendimento), 0800 082 8500 (grandes clientes). E-mail GD de AL citado em matéria de 2023: geracaodistribuida.alagoas@equatorialenergia.com.br (REPORTED, não revalidado).

---

## 3. Evidências recentes (2024-2026) de rejeições por documentação

### 3.1 Publicado pela empresa (VERIFIED)
- A **própria norma é a lista oficial de motivos**: itens obrigatórios em §5.14.2, nota de que a ausência de documento do RT distinto "não cabe envio posterior" (Nota 5), registro INMETRO "evidenciado na solicitação" sob pena de reprovação (§6.1.4.1), vistoria reprovada se o projeto não foi aprovado (§5.17 h).
- Portal: fatura vencida na unidade geradora leva ao indeferimento (aviso na Agência Virtual).
- Não encontrei **nenhum checklist de "erros comuns" ou "motivos de reprovação" publicado pela Equatorial** para GD (nem AL, nem MA/PI/PA). Um workshop com Crea/Aprel em AL (matéria da própria Equatorial, hoje 404) existiu, mas o conteúdo não está acessível.
- A única estatística de "pedido não efetivado por padrão incompleto" da Equatorial AL (cerca de 20%; falta de disjuntor, haste e conector de aterramento) é de **09/02/2021**, para **ligação nova, não GD** (VERIFIED na matéria do Painel Notícias; fora do período e fora do escopo, uso só como pista de padrão de entrada).

### 3.2 Reguladores e fiscalização
- Não achei fiscalização da ARSAL ou da ANEEL sobre GD na Equatorial AL em 2024-2026 (a busca da ARSAL só retornou resoluções gerais e fiscalização de atendimento em Delmiro Gouveia). Ausência de resultado, não prova de ausência.
- Referência comparável (REPORTED, Cenário Energia, 24/07/2026): ANEEL multou a **Neoenergia Coelba em R$ 82,7 milhões** por GD: indeferimentos indevidos de solicitações de acesso, atraso sistemático em orçamentos de conexão, falta de comunicação e dados obrigatórios ausentes nos pareceres. Indica que a ANEEL está fiscalizando justamente indeferimentos e prazos. É um tailwind para um produto que contesta indeferimentos com base normativa. Fonte secundária, período fiscalizado não informado.
- Os números da ANEEL que vocês já têm (AL 14,9%) são de 2022-2023, anteriores a REN 1000 (em 2023 o regime foi reformulado) e a Rev. 04+ da norma. Não achei série atualizada por motivo.

### 3.3 Anedotas / Reclame Aqui (REPORTED; li as páginas)
| Data | Distribuidora | Padrão |
|---|---|---|
| 09/11/2023 | Equatorial AL | Projetista: erro "Nonce já utilizado" no envio pelo site de GD; orientaram enviar por e-mail; protocolo de análise saiu quase 1 mês depois. Erros semelhantes relatados em PA e MA. |
| 10/06/2025 | Equatorial GO | Após desativar o SICAP (abril/2025), análise por e-mail; projetista relata reprovas sucessivas com motivos diferentes a cada envio, às vezes aprovação e reprovação do mesmo projeto no mesmo dia; sem transparência do andamento. |
| 09/07/2025 | Equatorial GO | Reprova porque "potência de geração informada > potência disponibilizada" (NT00020); o integrador diz que o próprio formulário validava. A empresa confirmou o motivo na resposta. |
| 03/09/2025 | Equatorial GO | 4 reprovas por um protocolo de troca de padrão antigo e cancelado, sem relação com a GD. |
| 08/03/2023 | Equatorial MA | Minigeração: reprovas por memorial descritivo, datasheet, unifilar sem P/V/I, disjuntor do inversor, dados do ponto de entrega, fotos, cálculo de proteção. (Fora do período e fora do escopo, mas é o **mesmo vocabulário do §5.14.2**.) |
| 01/11/2021 | Equatorial AL (Piaçabuçu) | Reprova por "adequar ramal conforme NT001", sem explicar o item; faltava DPS. Antigo. |
Padrões recorrentes (INFERRED a partir de poucos casos): (a) reprovas por itens que **estão na lista da norma** (unifilar sem P/V/I, memorial, DPS, disjuntor, fotos); (b) **incoerência entre potência de geração, disjuntor e potência disponibilizada**; (c) **pendências cadastrais cruzadas** da UC (protocolos antigos, faturas); (d) **motivo de reprovação vago**; (e) falhas do canal de envio. Nenhum dado de AL em 2024-2026 que sustente 14,9% como taxa atual. Reputação geral Equatorial AL no RA (REPORTED, resultado de busca): nota ~6,7, "Regular".

---

## 4. Neoenergia Cosern (RN), checagem rápida (itens 1 e 2)

### 4.1 Norma (VERIFIED)
- **DIS-NOR-031 Rev. 02**, "Conexão de Microgeradores ao Sistema de Distribuição", aprovada em 16/05/2025 (alterações em 30/04/2025), 41 páginas. Documento unificado para **Coelba, Pernambuco, Cosern, Elektro e Brasília**. Público, baixável por `curl` sem WAF (HTTP 200, PDF com texto): `https://www.neoenergia.com/documents/d/rn/dis-nor-031?download=true` (listada em `https://www.neoenergia.com/web/rn/normas-tecnicas`). Minigeração é outra norma (DIS-NOR-033); armazenamento DIS-NOR-082.
- Conteúdo: **não traz lista fechada de documentos nem templates**. Requisitos de projeto: ART ou TRT "preenchida, autenticada e quitada" com atividades de projeto e execução, e a potência de geração deve coincidir com a soma dos módulos ou dos inversores; ausência é "motivo impeditivo para energização" (§7.3). Inversor certificado INMETRO ou na lista de homologados; não aceitar inversor monofásico em sistema trifásico (§7.7.1); anti-ilhamento (§7.7.3, NBR IEC 62116); potência máxima pela corrente por fase vs. disjuntor geral (§7.6.4-7.6.5) e desequilíbrio entre fases <= 63 A (§7.6.6). Anexos só para Grid Zero/LPI (termos de responsabilidade técnica, SCRPI).
- Os documentos do pedido estão no portal (REPORTED por busca: formulário, memorial, layout, diagramas, ART). A lista oficial atual e os templates não são públicos fora do portal: **INFERRED**, não consegui vê-los.

### 4.2 Portal (VERIFIED)
- "Portal GD Acessante" Cosern: `https://gdneoenergiacosern.neoenergia.com/login.jsf`: **exige login + captcha**, com "Cadastrar novo usuário". Não há consulta pública de status.
- Página institucional (`https://www.neoenergia.com/geracao-distribuida`): pedido "exclusivamente online", **"receber notificações por e-mail a cada mudança de status"**, tela de consulta, download de parecer e contratos. Ferramenta pública "Simulação de disponibilidade de conexão". Prazos conforme REN 1000 (5 dias úteis para checar documentos, 15/30 dias de orçamento).
- Dados ANEEL do usuário: Cosern 6,0% de indeferimentos (2022-2023). Sem dados recentes.

---

## 5. Veredicto

### 5.1 Migrar para Equatorial AL é viável hoje?
**Sim, com ressalvas, e é mais forte como "motor de regras" do que como simulação de portal.**
- Norma pública e legível (PDF com texto), com lista exaustiva de documentos, conteúdo mínimo do unifilar e do memorial, regras de proteção e de ligação (Tabela 5). VERIFIED.
- Templates oficiais existem e são públicos (XLSX Anexo I, PDF Anexo III, PDF Anexo V). VERIFIED.
- Portal tem um fluxo público e simples (3 passos, sem login para iniciar; consulta de status por UC + protocolo sem login). VERIFIED. Isso é **mais fácil de simular fielmente** que o Cosern (login + captcha) e é comparável ao modelo da Enel CE.
- A mesma norma cobre sete estados: ganho de escala narrativo (um motor, 7 distribuidoras) e dá resposta ao critério "viabilidade como startup".
- Há dor real documentada: lista longa de documentos, norma que muda quase anualmente (Rev. 07 saiu há 3 dias), exigências cruzadas (potência x disjuntor x potência disponibilizada), motivos de reprovação vagos relatados, ANEEL multando indeferimentos indevidos (Coelba).

### 5.2 O que muda nos entregáveis
**Regras (rules):**
- Trocar a base normativa para NT.00020.EQTL Rev. 07 (e manter a Rev. 06 como alternativa até 03/03/2027; o diff é só SAE, então uma flag basta).
- Terminologia: "orçamento de conexão" em vez de "solicitação de acesso/parecer".
- Regras determinísticas novas a checar antes de enviar: ART/TRT de projeto e de execução juntos (Nota 5); registro INMETRO do inversor evidenciado; unifilar com P/V/I do gerador, inversor e cargas, DPS CA e CC, disjuntor geral (polos e A), cabos em mm2; memorial no modelo do Anexo III com **fotos** da caixa de medição e do inversor; placa do inversor a <= 1,80 m (exceto microinversor); planta com coordenadas UTM 24/25 ou graus decimais (só ligação nova); geração <= potência disponibilizada (conferir com disjuntor, tensão e fator de fases); Tabela 5 (fases x potência x tensão); arquivo <= 5 MB, PDF/Excel/CAD, nomes padronizados; posse/propriedade só para ligação nova; procuração (ambiguidade "autenticada" x "registrada"); **fatura da UC em dia**; Fast Track <= 7,5 kW exige Anexo V assinado e proíbe compartilhar créditos; Grid Zero exige manual do controlador.
- Remover da lista (Enel CE ou Rev. antigas): comissionamento, cronograma, levantamento de carga/planta para UC existente.
**Documentos (templates):**
- Preencher o **XLSX Anexo I** (precisa de geração de XLSX, não só PDF) e gerar o **memorial no formato do Anexo III** (PDF; obter e ler o template: ainda não li o conteúdo). Anexo V quando Fast Track. Unifilar e diagrama de blocos separados.
**Simulação do portal:**
- Reproduzir o assistente de 3 passos da Agência Virtual: tipo (micro/mini), estado, CPF/CNPJ do titular, UC; dados; anexos. Mais a tela "Acompanhar solicitações" (estado, UC, protocolo -> status). Mock de indeferimento em 5 dias úteis com lista de não conformidades, e mock do aviso de fatura vencida.
- Prazos do agente: 5 dias úteis (checagem documental), 15/30 dias (orçamento), 10 dias úteis (aprovação tácita), 5 dias úteis (vistoria), 3 dias úteis (relatório), 120 dias (nova vistoria).

### 5.3 Riscos
1. **WAF Imperva**: nem `curl` nem fetch simples baixam a norma ou os anexos. O agente real não pode "puxar a norma ao vivo" sem navegador; para a demo, **congelar uma cópia local da Rev. 07 e dos anexos**, citando URL, versão e data. Sem automação do portal real (e não deveríamos automatizar o envio real, de qualquer forma, por regra do hackathon: dados sintéticos).
2. **Norma recém-publicada (04/11/2026), "documento não controlado" e com dualidade 06/07 até 03/03/2027**: risco de um jurado apontar a versão errada. Mitigação: exibir versão e data na UI e testar contra as duas.
3. **Evidência recente de AL é fraca**: sem dado oficial de indeferimentos 2024-2026; os 14,9% da ANEEL são de 2022-2023, anteriores às Revs. 04 a 07 e a REN 1000. Os relatos recentes de reprova são de **Goiás** (que usa e-mail, não portal). Não afirmar "14,9% hoje" no pitch: dizer "ANEEL 2022-2023".
4. **Parte das reprovas relatadas parece arbitrária** (motivos vagos, protocolo cancelado, validação do formulário ignorada): um verificador documental determinístico não resolve isso. O que ajuda é *prevenir* o que é da lista e *documentar* a contestação com a cláusula. Evitar prometer "aprovação garantida".
5. **XLSX e Anexo III não lidos por dentro**: preciso abrir os arquivos (no navegador) antes de implementar o gerador; o conteúdo do Anexo I está só como reprodução em PDF.
6. **Dependência de sistema interno**: "Service Request", "NIS", "Parceiro de Negócios" (Anexo IV) mostram backend SAP; sem acesso a login real não dá para validar o passo 2 e 3 do assistente nem o conteúdo de e-mails de notificação.
7. **Escopo de pesos iguais**: Enel CE tem 0% de indeferimento, o que enfraquece a dor. Equatorial dá uma dor mais plausível, mas a dor que o jurado vê é o "agente que prepara e checa", a segurança de decisão ainda é humana (alinhado ao CLAUDE.md do projeto).
**Recomendação (opinião, INFERRED):** migrar o motor de regras e os documentos para Equatorial AL/NT.00020 Rev. 07, mantendo Enel CE como segunda distribuidora ("mesmo motor, outra norma") para demonstrar portabilidade. Cosern só como terceira opção: norma pública, mas sem templates nem checklist públicos e portal com login + captcha.

---

## Fontes realmente abertas
- https://al.equatorialenergia.com.br/institucional/leis-e-normas-tecnicas/normas-tecnicas/instalacao-de-padrao (navegador; tabela Rev 07/06 e links)
- https://ma.equatorialenergia.com.br/institucional/leis-e-normas-tecnicas/normas-tecnicas/instalacao-de-padrao e https://pa.equatorialenergia.com.br/institucional/leis-e-normas-tecnicas/normas-tecnicas/instalacao-de-padrao (via WebFetch; mesma tabela)
- https://ma.equatorialenergia.com.br/wp-content/uploads/2026/11/NT.00020.EQTL-07-Conexao-de-Micro-e-Minigeracao-Distribuida-ao-Sistema-de-Distribuicao.pdf (PDF baixado, texto extraído)
- https://ma.equatorialenergia.com.br/wp-content/uploads/2025/12/NT.00020.EQTL-06-Conexao-de-Micro-e-Minigeracao-Distribuida-ao-Sistema-de-Distribuicao.pdf (idem)
- https://al.equatorialenergia.com.br/wp-content/uploads/2026/11/ (Anexos I, III, V: status 200 e tamanho; conteúdo não lido)
- https://agenciavirtual.equatorialenergia.com.br/Login/ , /GeracaoDistribuida/?sc= , /solicitacao/AcompanharSolicitacoes?sc= (navegador)
- https://ceee.equatorialenergia.com.br/micro-e-minigeracao (WebFetch; fluxo CEEE por e-mail)
- https://www.cadaminuto.com.br/noticia/2022/03/21/equatorial-explica-passo-a-passo-para-solicitacao-e-instalacao-de-energia-solar-confira (2022)
- https://www.vorbe.com.br/artigos/ligacao-nova-geracao-gd-goias/ (06/08/2024; secundária)
- https://painelnoticias.com.br/geral/184916/20-dos-pedidos-de-ligacao-de-energia-sao-reprovados-por-padrao-incompleto (09/02/2021)
- Reclame Aqui (navegador): https://www.reclameaqui.com.br/companhia-de-energia-eletrica-alagoas/problemas-no-site_gGkxbModTd6xZSpE/ ; .../prazo-vencido-para-envio-do-parecer-de-acesso-para-projeto-de-microgeracao_aUf21ug5s96EuieO/ ; https://www.reclameaqui.com.br/equatorial-goias/equatorial-reprova-indevidamente-solicitacao-de-parecer-de-acesso_gHDtyoIUj0fz67Sm/ ; .../equatorial-goias-impede-aprovacao-de-projeto-de-energia-solar-por-motivo-infundado_ETMlY8KGNyUwBKCq/ ; .../dificuldade-na-aprovacao-de-projetos-apos-desativacao-do-sicap_dkSaISe8oKyM5n8U/ ; https://www.reclameaqui.com.br/cemar-ma/reprovas-sem-sentido-solicitacao-de-acesso-de-minigeracao_j8PPOUoIbSqn349E/
- https://cenarioenergia.com.br/2026/07/24/aneel-aplica-multa-recorde-de-r-827-mi-a-neoenergia-coelba-por-falhas-na-gd/ (24/07/2026)
- https://www.neoenergia.com/web/rn/normas-tecnicas ; https://www.neoenergia.com/documents/d/rn/dis-nor-031?download=true ; https://www.neoenergia.com/geracao-distribuida ; https://gdneoenergiacosern.neoenergia.com/login.jsf

Tentadas e **não** abertas (WAF/404): páginas antigas de GD de AL e PI, matéria do workshop Crea/Aprel de AL, página de minutas da CEEE (NT 04/2024), cartilha GD da CEEE. Resultados de busca (WebSearch) usados apenas como pistas, não como fonte.
