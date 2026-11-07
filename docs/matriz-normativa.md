# Matriz de cobertura — Enel Ceará, residencial até 10 kW

Base: [fontes e versões](fontes/README.md). Esta é a matriz inicial da auditoria,
não um atestado de conformidade. Falta revisar integralmente as normas nacionais,
comprovar a aplicabilidade por projeto e implementar o checklist documental.
“Parcial” não significa aprovado. Cada pendência abaixo precisa de evidência.

| Exigência/critério | Fonte/item | Implementação atual | Evidência/teste e lacuna |
|---|---|---|---|
| Solicitação | Enel Anexo A, pp.42–43 | `docs/anexo_a.py` | `test_pdfs.py`; formato próprio, equivalência pendente |
| Responsabilidade técnica | Enel Tabela 10; A/3.1 | Ausente | Faltam recebimento e verificação |
| Comprovação do inversor | Enel 7.6.1.4; A/3.4 | R05 parcial | `test_regras.py`; resultado incerto sem comprovação de modelo/tensão |
| Dados da central | Enel A/3.5; ANEEL/MMGD | Ausente | Mapear formulário vigente |
| Unifilar/blocos/memorial | Enel Tabela 10, nota 2; A/3.3; Anexo B | Geradores parciais | `test_unifilar.py`, `test_pdfs.py`; conteúdo e topologia pendentes |
| DPS | Enel 7.6.1.6 | Texto/template | Sem especificação e verificação |
| Proteções do inversor | Enel 7.6.1.5 e Tabela 13 | Texto/template | Sem comprovação técnica |
| Compensação/rateio | Enel Tabela 10, nota 3; A/2.5,3.6 | Perguntas parciais | Aplicabilidade/lista pendentes |
| Instrumento jurídico | Enel Tabela 10, nota 5; A/3.7 | Ausente | Avaliar modalidade |
| Identificação/carga/imóvel | Enel A/1 | Perguntas parciais | Distinguir UC existente, nova e alteração |
| Declarações/assinatura | Enel A/4–5 | Texto e espaços | Sem validação documental |
| Coerência | Spec R01 | Busca parcial nos arquivos | `test_regras.py`; faltam potência, DPS e leitura vinculada aos rótulos |
| Cabo/disjuntor | Spec R02; NBR 5410 | Tabela provisória | Fronteiras testadas; premissas não validadas impedem aprovação |
| Voc/temperatura | Spec R03; datasheets | Temperatura fixa | Fronteiras testadas; premissa local/proveniência pendentes |
| Potência CC | Spec R04; datasheets | Comparação numérica | Falta comprovar origem dos limites |
| Condicionais especiais | Enel A/3.8–3.11 | Não implementado | Não presumir dispensa sem enquadramento |

## Política implementada nesta rodada

- Cálculo favorável sob critério `a_validar` resulta em INCERTA.
- Registro INMETRO preenchido sem verificação não resulta em APROVADA.
- R01–R05 precisam de resultado único, aprovado e sem `a_validar` para aprovação,
  protocolo e reenvio. R06–R08 permanecem fora do MVP; não são conformidade verificada.
- A API refaz a conferência sob a trava do processo antes de gravar aprovação;
  resultados antigos favoráveis não dispensam releitura e recálculo.
- Encaminhamento para revisão pode conter incertezas; o botão de aprovação não
  pode convertê-las silenciosamente em conformidade.

Testes: `test_aprovacao.py`, `test_regras.py`, `test_api.py`. O teste HTTP com
ferramentas reais agora comprova o bloqueio do pacote sintético. O teste das
transições posteriores do portal usa conferência explicitamente simulada.

## Próximos fechamentos necessários

1. Checklist executável de campos/anexos e condições do Anexo A; resolução com evidências.
2. Proveniência das especificações extraídas de datasheets oficiais.
3. Conferência de conteúdo dos arquivos, inclusive campos obrigatórios sem preenchimento.
4. Validação técnica das premissas em fonte autorizada e por engenheiro.
5. Evals de extração real/degradações e fluxo completo com consumo registrado.
