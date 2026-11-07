import sys, pandas as pd
cols=['SigAgenteDistribuicao','NumProtocolo','DatPrzEnvio','DatSolicitacao','DatOrcamentoConexao','DatVistoria','DatInj','MdaPotencia','DscSubgrupoTarifario','DscStatusConexao','DscSituacaoConexao','DscNecessidadeObras']
df=pd.read_parquet(sys.argv[1],columns=cols)
df=df.sort_values('DatPrzEnvio').drop_duplicates('NumProtocolo',keep='last')
for c in ['DatSolicitacao','DatOrcamentoConexao','DatVistoria','DatInj']: df[c]=pd.to_datetime(df[c],errors='coerce')
r=df[(df.MdaPotencia<=10)&(df.DscSubgrupoTarifario=='B1')].copy()
r['a_sol_orc']=(r.DatOrcamentoConexao-r.DatSolicitacao).dt.days
r['b_orc_vis']=(r.DatVistoria-r.DatOrcamentoConexao).dt.days
r['c_vis_inj']=(r.DatInj-r.DatVistoria).dt.days
r['tot']=(r.DatInj-r.DatSolicitacao).dt.days
def q(s): s=s.dropna(); s=s[s>=0]; return f"n={len(s)} mediana={s.median():.0f} p75={s.quantile(.75):.0f} p90={s.quantile(.9):.0f}"
print(f"{'dist':22} {'pedidos':>8} | sol->orc (distrib.) | orc->vistoria (integrador+obra) | vist->inj | total")
for d,g in r.groupby('SigAgenteDistribuicao'):
    if len(g)<2000: continue
    a=g.a_sol_orc.dropna(); a=a[a>=0]
    neg=(g.DscStatusConexao=='Pedidos Negados').mean()*100
    print(f"{d:22} {len(g):8d} | {q(g.a_sol_orc)} | {q(g.b_orc_vis)} | {q(g.c_vis_inj)} | {q(g.tot)} | orc>15d {(a>15).mean()*100:.0f}% | negados {neg:.1f}%")
