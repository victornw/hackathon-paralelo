# Busca rápida de pacote residencial — 07/11/2026

Nenhum dos achados abaixo foi enviado ao LLM ou incorporado ao conjunto de testes.
Não foi confirmado um pacote completo aprovado e vigente da Enel CE.

## Consulta INMETRO

O detalhe do registro 005485/2023 respondeu HTTP 200 por acesso programático,
sem autenticação/CAPTCHA nesse acesso. Situação: Ativo; modelo SG5.0RS-L.
Evidência técnica mínima, sem contatos pessoais: `inmetro-005485-2023.json`.
A linha incluída não explicita a tensão; linhas excluídas trazem descrições
anteriores, uma inclusive com unidade de potência inconsistente. Não aprovar
modelo/tensão com base apenas na situação da família ou em qualquer linha do histórico.

O formulário público usa GET em `Default.aspx`. Uma tentativa inicial com POST
não encontrou o registro. GET respondeu 200, mas o fluxo completo de localização
por marca/modelo e navegação dos resultados ainda não foi validado. O teste
positivo confirma viabilidade do detalhe por número conhecido, não uma API oficial.

Fonte: https://registro.inmetro.gov.br/consulta/detalhe.aspx?NumeroRegistro=005485%2F2023&pag=1

## Candidatos

1. Relatório residencial de Fortaleza, datado de 2015, Coelce, 5,2 kWp.
   https://pt.scribd.com/document/393250423/15-Projeto-Energia-Solar-Memorial-Descritivo-Em-PDF
   Leitura pública apresenta memorial e referências a diagramas. Há dados de cliente,
   endereço e localização; não usar antes de anonimizar texto, imagens e metadados.
   O texto menciona aprovação do proprietário, não comprova aprovação da distribuidora.
   Também diverge na quantidade de módulos por string (10 em uma seção, 9 em outra).
   Serve como candidato histórico/com erro, não como gabarito aprovado.
   PDF original ainda não obtido; não foi reconstruído o documento a partir do texto.

2. UFC: trabalho de homologação Enel CE (2022).
   https://repositorio.ufc.br/bitstream/riufc/78011/1/2022_tcc_vmsaraujo.pdf
   Localizado na busca; download direto e leitura via web falharam por timeout.
   Conteúdo integral e anexos não verificados.

3. SEDUC-CE: Apostila 17 — Projetos Fotovoltaicos.
   Resultado público aponta modelo de memorial residencial, sem dados de cliente
   preenchidos, mas é material didático, não caso aprovado. O download encontrado
   usa URL assinada expirada; a tentativa pela URL sem assinatura falhou.

4. IFRN: PDF de 95 páginas baixado em pasta temporária. Contém memorial e
   referências a unifilar, mas cita COSERN e não Enel. Não é o caso Enel CE buscado;
   aprovação da distribuidora não comprovada. Não foi enviado ao LLM.
   https://memoria.ifrn.edu.br/bitstream/handle/1044/3016/MATEUS-FINAL-PDF.pdf?isAllowed=y&sequence=1

## Antes de executar extração

Obter o arquivo original, delimitar páginas do caso, remover identificadores,
endereços/coordenadas, assinaturas/QRs e metadados; conferir também imagens e a
camada de texto. Guardar a fonte separada da versão anonimizada. Somente depois
usar o documento no agente. Dados técnicos e incoerências devem ser preservados.
