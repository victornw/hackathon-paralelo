import sys, pandas as pd
cols=['SigAgenteDistribuicao','NumProtocolo','DatPrzEnvio','DatSolicitacao','MdaPotencia','DscSubgrupoTarifario','DscFonteGeracao','DscStatusConexao','DscMotivoSituacao','DscSituacaoConexao']
df=pd.read_parquet(sys.argv[1],columns=cols)
df=df.sort_values('DatPrzEnvio',kind='stable').drop_duplicates(['SigAgenteDistribuicao','NumProtocolo'],keep='last')
r=df[(df.DscSubgrupoTarifario=='B1')&(df.MdaPotencia>0)&(df.MdaPotencia<=10)&(df.DscFonteGeracao=='UFV')&(pd.to_datetime(df.DatSolicitacao)>='2022-01-07')&(pd.to_datetime(df.DatSolicitacao)<='2023-01-07')]
for d,g in r.groupby('SigAgenteDistribuicao'):
    if len(g)<2000: continue
    neg=g[g.DscStatusConexao=='Pedidos Negados']
    inc=(neg.DscMotivoSituacao=='Documentação incompleta').sum(); doc=neg.DscMotivoSituacao.isin(['Documentação incompleta','Documentação incorreta']).sum()
    vist=g.DscSituacaoConexao.isin(['Vistoria não solicitada','Vistoria reprovada, aguardando nova solicitação']).sum()
    nap=(neg.DscMotivoSituacao=='Não aprovação nos prazos estabelecidos (art. 83, § 7º, I)').sum()
    print(f"{d:22} n={len(g):6d} doc_incompleta={inc:5d} ({inc/len(g)*100:5.2f}%) doc_total={doc} vistoria_parada={vist} ({vist/len(g)*100:4.1f}%) nao_aprovou_orc={nap}")
