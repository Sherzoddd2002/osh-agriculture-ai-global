"""Download and import FAOSTAT Crops and livestock products bulk data.
Run from backend runtime: python -m app.sync_global_data
"""
from __future__ import annotations
import io, zipfile
from datetime import datetime, timezone
import httpx
import pandas as pd
import pycountry
from sqlalchemy import delete
from .db import SessionLocal, init_db
from .models import GlobalCropStatistic
from .services.global_crops import normalize_crop_code

URL="https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip"
def _country_iso3(m49):
    try:
        country=pycountry.countries.get(numeric=str(m49).zfill(3))
        return country.alpha_3 if country else None
    except Exception:
        return None
def _convert(value,unit,kind):
    if pd.isna(value):return None
    v=float(value);u=str(unit).lower().strip()
    if kind=="area":
        if "1000 ha" in u:return v*1000
        if u=="ha":return v
    if kind=="production":
        if "1000 t" in u:return v*1000
        if u in {"t","tonnes","tonne"}:return v
    if kind=="yield":
        if "hg/ha" in u:return v/10000
        if "kg/ha" in u:return v/1000
        if "t/ha" in u:return v
    return None
def main():
    init_db()
    print("Downloading official FAOSTAT bulk dataset...")
    with httpx.Client(timeout=180,follow_redirects=True) as client:
        response=client.get(URL);response.raise_for_status()
    archive=zipfile.ZipFile(io.BytesIO(response.content))
    csv_name=next((n for n in archive.namelist() if n.lower().endswith(".csv")),None)
    if not csv_name:raise RuntimeError("FAOSTAT ZIP ichida CSV topilmadi.")
    with archive.open(csv_name) as raw:
        df=pd.read_csv(raw,low_memory=False)
    required={"Area Code (M49)","Area","Item Code","Item","Element","Year","Unit","Value"}
    missing=required-set(df.columns)
    if missing:raise RuntimeError(f"FAOSTAT ustunlari yetishmaydi: {sorted(missing)}")
    df["crop_code"]=df["Item"].map(normalize_crop_code)
    df=df[df["crop_code"].isin({"WHEAT","MAIZE","RICE","BARLEY","SOYBEAN","COTTON","POTATO","SORGHUM"})].copy()
    element_map={
      "Area harvested":"area","Harvested area":"area",
      "Production":"production","Yield":"yield"
    }
    df["kind"]=df["Element"].map(element_map)
    df=df[df["kind"].notna()].copy()
    df["value_norm"]=df.apply(lambda r:_convert(r["Value"],r["Unit"],r["kind"]),axis=1)
    df=df[df["value_norm"].notna()]
    idx=["Area Code (M49)","Area","Item Code","Item","crop_code","Year"]
    pivot=df.pivot_table(index=idx,columns="kind",values="value_norm",aggfunc="last").reset_index()
    records=[]
    for _,r in pivot.iterrows():
        iso3=_country_iso3(r["Area Code (M49)"])
        if not iso3:continue
        area=r.get("area")
        production=r.get("production")
        yield_v=r.get("yield")
        if pd.isna(area):area=None
        if pd.isna(production):production=None
        if pd.isna(yield_v):yield_v=None
        if area is None and production is not None and yield_v and yield_v>0:area=production/yield_v
        if yield_v is None and area and production is not None:yield_v=production/area
        if yield_v is None and not (area and production is not None):continue
        records.append(GlobalCropStatistic(
          source_code="FAOSTAT_QCL",source_release="bulk-latest",
          area_m49=str(int(r["Area Code (M49)"])).zfill(3),country_iso3=iso3,
          area_name=str(r["Area"]),item_code=str(r["Item Code"]),
          crop_code=str(r["crop_code"]),crop_name=str(r["Item"]),
          year=int(r["Year"]),harvested_area_ha=float(area) if area else None,
          production_t=float(production) if production is not None else None,
          yield_t_ha=float(yield_v) if yield_v is not None else None,
          imported_at=datetime.now(timezone.utc)))
    if not records:raise RuntimeError("Mos FAOSTAT qatorlari topilmadi; unit/element mappingni tekshirish kerak.")
    with SessionLocal() as db:
        db.execute(delete(GlobalCropStatistic).where(GlobalCropStatistic.source_code=="FAOSTAT_QCL"))
        db.add_all(records);db.commit()
    print(f"Imported {len(records):,} crop-country-year rows from FAOSTAT.")
if __name__=="__main__":main()
