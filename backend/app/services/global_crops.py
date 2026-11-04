"""FAOSTAT-based global crop forecast baseline."""
from collections import defaultdict
from statistics import median
import re, unicodedata
import numpy as np
from sklearn.linear_model import Ridge
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import GlobalCropStatistic
ALIASES={"WHEAT":{"wheat","wheat grain"},"MAIZE":{"maize","corn"},"RICE":{"rice","paddy rice"},"BARLEY":{"barley"},"SOYBEAN":{"soybean","soybeans"},"COTTON":{"cotton","cotton lint"},"POTATO":{"potato","potatoes"},"SORGHUM":{"sorghum"}}
def normalize_crop_code(value):
 s=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().lower()
 s=re.sub(r"[^a-z0-9]+"," ",s).strip()
 for code,names in ALIASES.items():
  if s==code.lower() or s in names:return code
 return s.upper().replace(" ","_")[:64] or "UNKNOWN"
def _series(rows):
 d=defaultdict(lambda:[0.,0.,0.,0.])
 for r in rows:
  a=r.harvested_area_ha or 0
  if a<=0:continue
  x=d[r.year];x[0]+=a
  if r.production_t is not None and r.production_t>=0:x[1]+=r.production_t
  if r.yield_t_ha is not None and r.yield_t_ha>=0:x[2]+=r.yield_t_ha*a;x[3]+=a
 out=[]
 for y,(a,p,ya,yw) in sorted(d.items()):
  v=p/a if p>0 else (ya/yw if yw else None)
  if v is not None and np.isfinite(v) and 0<=v<=30:out.append({"year":y,"yield_t_ha":v})
 return out
def _fit(s,target):
 if len(s)<8:raise ValueError(f"Kamida 8 yillik qator kerak; mavjud: {len(s)}.")
 vals=[x["yield_t_ha"] for x in s];X=[];Y=[]
 for i in range(3,len(s)):
  w=np.asarray(vals[i-3:i]);X.append([s[i]["year"],vals[i-1],w.mean(),w.std()]);Y.append(vals[i])
 errors=[];base=[]
 for i in range(3,len(Y)):
  m=Ridge(alpha=2).fit(np.asarray(X[:i]),np.asarray(Y[:i]))
  errors.append(abs(Y[i]-max(0,float(m.predict(np.asarray([X[i]]))[0]))));base.append(abs(Y[i]-Y[i-1]))
 mae=float(np.mean(errors));base_mae=float(np.mean(base))
 latest=np.asarray(vals[-3:]);m=Ridge(alpha=2).fit(np.asarray(X),np.asarray(Y))
 pred=max(0,float(m.predict(np.asarray([[target,vals[-1],latest.mean(),latest.std()]]))[0]))
 return {"predicted_yield_t_ha":pred,"oof_mae_t_ha":mae,"persistence_oof_mae_t_ha":base_mae,"beats_persistence":mae<base_mae,"oof_rows":len(errors),"lower_approx_t_ha":max(0,pred-1.96*mae),"upper_approx_t_ha":pred+1.96*mae,"training_years":len(s),"last_observed_year":s[-1]["year"]}
def forecast_global_crop_yield(db:Session,country_iso3:str,crop_code:str,target_year:int):
 crop=normalize_crop_code(crop_code)
 rows=db.scalars(select(GlobalCropStatistic).where(GlobalCropStatistic.crop_code==crop).order_by(GlobalCropStatistic.year)).all()
 if not rows:raise ValueError(f"{crop}: FAOSTAT global bazasi yuklanmagan.")
 glob=_series(rows);local=_series([r for r in rows if r.country_iso3==country_iso3.upper()])
 if len(local)>=8:result=_fit(local,target_year);kind="COUNTRY_NATIONAL_TREND";factor=1.
 else:
  result=_fit(glob,target_year);byyear={x["year"]:x["yield_t_ha"] for x in glob}
  ratios=[x["yield_t_ha"]/byyear[x["year"]] for x in local if x["year"] in byyear and byyear[x["year"]]>0]
  factor=min(2.5,max(.4,float(median(ratios[-5:])))) if len(ratios)>=3 else 1.
  for k in ("predicted_yield_t_ha","lower_approx_t_ha","upper_approx_t_ha"):result[k]*=factor
  kind="COUNTRY_ADJUSTED_GLOBAL_TREND" if len(ratios)>=3 else "GLOBAL_CROP_TREND_PROXY"
 return {**result,"crop_code":crop,"country_iso3":country_iso3.upper(),"target_year":target_year,"prediction_type":kind,"country_observed_years":len(local),"global_observed_years":len(glob),"country_adjustment_factor":factor,"source":"FAOSTAT QCL","source_url":"https://www.fao.org/faostat/en/#data/QCL","spatial_scope":"NATIONAL_OR_GLOBAL_PROXY","limitations":"Bu tuman/dala kuzatuvi emas. FAOSTAT milliy trendiga asoslangan baseline; raster iqlim/tuproq bilan kalibrlash hali ulanmagan. Interval OOF xatosidan olingan taxminiy diapazon."}
