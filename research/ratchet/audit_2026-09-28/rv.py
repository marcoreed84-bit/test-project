import sys; sys.path.insert(0,'/home/user/test-project/research/ratchet')
import numpy as np, sim as S, report as R, validate as V, noise as N
ctx=S.build_ctx()
r2=R.load(R.RATCHET_BT2)
s2,_=S.simulate(ctx,S.V328)
V.compare(r2,s2,"Backtest_2 vs CORRECT v3.28 config (S.V328)")
# noise measured with correct config
def measure(ctx,cfg2):
    ent,slp=[],[]
    for path,p in [(R.RATCHET_BT1,S.BASELINE),(R.RATCHET_BT2,cfg2)]:
        real=R.load(path); simt,_=S.simulate(ctx,p)
        sk={N.key(t["entry_time"]):t for t in simt}
        for r in real:
            s=sk.get(N.key(r["entry_time"]))
            if s is not None and s["dir"]==r["side"]:
                ent.append(((r["entry"]-s["entry"])*r["side"],s["atr"]))
                if r["reason"]=="SL": slp.append(((r["exit"]-float(r["last_comment"][3:]))*r["side"],s["atr"]))
    ent,slp=np.array(ent),np.array(slp); return ent[:,0]/ent[:,1], slp[:,0]/slp[:,1]
for lab,cfg in [("SHIPPED(as in repo)",S.SHIPPED),("V328(correct)",S.V328)]:
    e,s=measure(ctx,cfg); print(lab,"ent n",len(e),"mean %.4f sd %.4f"%(e.mean(),e.std()),"slp n",len(s),"mean %.4f"%s.mean())
