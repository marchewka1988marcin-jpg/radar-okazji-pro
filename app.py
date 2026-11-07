import os, requests, threading, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlencode
from flask import Flask, jsonify, request, send_from_directory
app=Flask(__name__,static_folder="static")
QUERIES=[
 'licytacja nieruchomości Częstochowa Blachownia',
 'przetarg sprzedaż nieruchomości Blachownia Częstochowa',
 'syndyk nieruchomość Częstochowa Kłobuck',
 'KOWR przetarg nieruchomości śląskie Częstochowa',
 'komornik licytacja nieruchomości Częstochowa Myszków',
 'BIP sprzedaż działki Konopiska Wręczyca Wielka']
cache={"updated_at":None,"offers":[],"status":"Trwa przygotowanie pierwszego wyszukiwania"}
lock=threading.Lock()
def fetch():
 offers={}
 errors=[]
 for q in QUERIES[:4]:
  try:
   params=urlencode({"q":q+" when:30d","hl":"pl","gl":"PL","ceid":"PL:pl"})
   r=requests.get("https://news.google.com/rss/search?"+params,headers={"User-Agent":"Mozilla/5.0 RadarOkazji/1.0"},timeout=(3,5))
   r.raise_for_status()
   root=ET.fromstring(r.content)
   for item in root.findall(".//item"):
    title=(item.findtext("title") or "").strip()
    url=(item.findtext("link") or "").strip()
    date=(item.findtext("pubDate") or "").strip()
    if url.startswith("https://") and url not in offers:
     offers[url]={"title":title,"url":url,"description":"Wynik z publicznego indeksu wiadomości; sprawdź ogłoszenie u źródła. "+date,"query":q}
  except Exception as exc: errors.append(str(exc)[:120])
 return {"updated_at":datetime.now(timezone.utc).isoformat(),"offers":list(offers.values()),"status":("Znaleziono publiczne wyniki; zweryfikuj lokalizację i aktualność u źródła." if offers else ("Nie udało się pobrać wyników z publicznego RSS." if errors else "Publiczne źródło RSS nie zwróciło wyników.")),"errors":errors[:3]}
def update():
 with lock:
  cache["status"]="Trwa pobieranie danych z publicznych źródeł"
  try: cache.update(fetch())
  except Exception as exc: cache.update({"updated_at":datetime.now(timezone.utc).isoformat(),"offers":[],"status":"Błąd pobierania: "+str(exc)[:100]})
def background():
 while True:
  update()
  time.sleep(21600)
threading.Thread(target=background,daemon=True).start()
@app.get("/")
def index(): return send_from_directory("static","index.html")
@app.get("/health")
def health(): return jsonify({"ok":True,"updated_at":cache["updated_at"],"count":len(cache["offers"])})
@app.get("/api/offers")
def offers(): return jsonify(cache)
@app.post("/api/refresh")
def refresh():
 token=os.getenv("ADMIN_TOKEN")
 if not token or request.headers.get("X-Admin-Token")!=token: return jsonify({"error":"Unauthorized"}),401
 update()
 return jsonify({"updated_at":cache["updated_at"],"count":len(cache["offers"])})
