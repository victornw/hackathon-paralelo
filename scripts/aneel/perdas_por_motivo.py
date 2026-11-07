import sys, pandas as pd
cols=['SigAgenteDistribuicao','NumProtocolo','DatPrzEnvio','MdaPotencia','DscSubgrupoTarifario','DscStatusConexao','DscMotivoSituacao','DscSituacaoConexao']
df=pd.read_parquet(sys.argv[1],columns=cols).sort_values('DatPrzEnvio').drop_duplicates('NumProtocolo',keep='last')
r=df[(df.MdaPotencia<=10)&(df.DscSubgrupoTarifario=='B1')]
PRAZO_MOT=['Não aprovação nos prazos estabelecidos (art. 83, § 7º, I)','Não devolução dos contratos assinados no prazo (art. 83, § 7º, III)','Perda de validade: outros motivos;Caso o Orçamento tenha sido cancelado']
DOC_MOT=['Documentação incompleta','Documentação incorreta']
VIST=['Vistoria não solicitada','Vistoria reprovada, aguardando nova solicitação']
linhas=[]
for d,g in r.groupby('SigAgenteDistribuicao'):
    if len(g)<2000: continue
    neg=g[g.DscStatusConexao=='Pedidos Negados']
    prazo=neg.DscMotivoSituacao.isin(PRAZO_MOT).sum(); doc=neg.DscMotivoSituacao.isin(DOC_MOT).sum()
    vist=g.DscSituacaoConexao.isin(VIST).sum(); desist=neg.DscMotivoSituacao.str.startswith('Desistência',na=False).sum()
    linhas.append((d,len(g),doc,prazo,desist,vist))
    print(f"{d:22} n={len(g):6d} | doc {doc:5d} ({doc/len(g)*100:4.1f}%) | prazo do integrador {prazo:5d} ({prazo/len(g)*100:4.1f}%) | desistência {desist:4d} | vistoria parada {vist:4d} ({vist/len(g)*100:3.1f}%)")
t=pd.DataFrame(linhas,columns=['d','n','doc','prazo','desist','vist']).sum(numeric_only=True)
print(f"TOTAL n={t.n} | doc {t.doc} ({t.doc/t.n*100:.1f}%) | prazo {t.prazo} ({t.prazo/t.n*100:.1f}%) | vistoria parada {t.vist} ({t.vist/t.n*100:.1f}%) | doc+prazo+vist {(t.doc+t.prazo+t.vist)/t.n*100:.1f}%")
