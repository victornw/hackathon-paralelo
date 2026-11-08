# Medição do tempo de revisão humana

Objetivo: obter o número que sustenta o argumento central do pitch, quantos pacotes um engenheiro revisa por dia quando o agente monta e confere. A referência de mercado é a Tellar, com 14 engenheiros e cerca de 350 projetos por mês, pouco mais de 1 projeto por engenheiro por dia útil (pv magazine, 26/11/2024; conta nossa).

## O que medir

Tempo ativo de uma pessoa revisando um pacote gerado pelo agente, do momento em que abre a tela de revisão até decidir aprovar ou devolver. Não inclui o tempo do agente nem o tempo de espera da distribuidora.

Junto com o tempo, registrar se a pessoa encontrou os defeitos plantados. A referência de acerto é a lista de defeitos definida antes, não o conferidor do agente, para o número não ser circular.

## Casos

Usar 4 a 6 pacotes:

- os 3 processos gerados por `evals/processo_completo.py` a partir de `fixtures/contas/cliente_{1,2,3}`;
- 1 a 3 cópias com um defeito plantado cada, escolhido por quem não vai revisar, por exemplo: string com Voc acima da tensão máxima do inversor, disjuntor CA igual à corrente de saída, titular diferente entre a solicitação e o memorial, DPS ausente no unifilar.

Quem planta o defeito anota na planilha antes da revisão e não conta para o revisor.

## Procedimento

1. Abrir o processo na tela de revisão.
2. Iniciar o cronômetro.
3. Revisar como se fosse assinar: conferir regras, documentos e o que ficou incerto.
4. Decidir aprovar ou devolver, e anotar o motivo.
5. Parar o cronômetro e preencher uma linha em `evals/dados/medicao_revisao.csv`.

Se der, um segundo revisor repete os mesmos casos, para ver a variação entre pessoas.

## Como reportar

- Mediana e intervalo (menor e maior) do tempo por pacote, em minutos.
- Pacotes por dia útil, com 6 horas efetivas de revisão: 360 dividido pela mediana.
- Defeitos plantados encontrados e aprovações indevidas.
- Sempre dizer que os casos são sintéticos e que o revisor é da equipe.

Frase para o slide, preenchida com o número medido: "Com o agente montando e conferindo, a revisão levou N minutos por pacote (mediana de K casos sintéticos). Isso dá cerca de P pacotes por engenheiro por dia, contra pouco mais de 1 na referência de mercado."
