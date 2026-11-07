import os, requests
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory
app=Flask(__name__,static_folder="static")
QUERIES=["licytacje komornicze nieruchomości Blachownia Częstochowa","przetarg sprzedaż nieruchomości BIP Blachownia Częstochowa","syndyk nieruchomości Częstochowa licytacja","KOWR przetarg nieruchomości śląskie","site:listaprzetargow.pl Blachownia Częstochowa","site:licytor.pl Częstochowa nieruchomości"]
cache={"updated_at":None,"offers":[],"status":"Oczekiwanie na pierwsze pobranie"}
def fetch():
 key=os.getenv("FIRECRAWL_API_KEY")
 if not key: return {"updated_at":None,"offers":[],"status":"Brak klucza Firecrawl. Skonfiguruj FIRECRAWL_API_KEY na Render."}
 offers={}
 errors=[]
 for q in QUERIES:
  try:
   r=requests.post("https://api.firecrawl.dev/v1/search",headers={"Authorization":"Bearer "+key},json={"query":q,"limit":8},timeout=25)
   r.raise_for_status()
   payload=r.json().get("data",[])
   if isinstance(payload,dict): payload=payload.get("web",[])
   for item in payload:
    url=item.get("url","")
    if url.startswith("https://") and url not in offers:
     offers[url]={"title":item.get("title") or "Ogłoszenie nieruchomości","url":url,"description":(item.get("description") or "")[:500],"query":q}
  except Exception as exc: errors.append(str(exc)[:100])
 return {"updated_at":datetime.now(timezone.utc).isoformat(),"offers":list(offers.values()),"status":"Wyniki wyszukiwania wymagają sprawdzenia lokalizacji, dat i warunków u źródła.","errors":errors[:2]}
@app.get("/")
def index(): return send_from_directory("static","index.html")
@app.get("/health")
def health(): return jsonify({"ok":True,"firecrawl_configured":bool(os.getenv("FIRECRAWL_API_KEY"))})
@app.get("/api/offers")
def offers(): return jsonify(cache)
@app.post("/api/refresh")
def refresh():
 token=os.getenv("ADMIN_TOKEN")
 if not token or request.headers.get("X-Admin-Token")!=token: return jsonify({"error":"Unauthorized"}),401
 cache.update(fetch())
 return jsonify({"updated_at":cache["updated_at"],"count":len(cache["offers"])})
