"""Radar Okazji: live dataset from public GitHub, independent of Render deployments."""
import json, time, threading, requests, html
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, Response
app=Flask(__name__,static_folder="static")
DATA_URL="https://raw.githubusercontent.com/marchewka1988marcin-jpg/radar-okazji-pro/main/data/verified.json"
cache={"value":None,"checked":0,"last_error":None,"source":"unknown"}
lock=threading.Lock()
def read_offers():
 with lock:
  if cache["value"] and time.monotonic()-cache["checked"]<15: return cache["value"]
  try:
   r=requests.get(DATA_URL,params={"_":int(time.time()//90)},timeout=(3,7),headers={"User-Agent":"RadarOkazji/1.0"})
   r.raise_for_status()
   data=r.json()
   if not isinstance(data.get("offers"),list): raise ValueError("Missing offers")
   cache.update({"value":data,"checked":time.monotonic(),"last_error":None,"source":"github_raw"})
   return data
  except Exception as exc:
   cache["last_error"]=str(exc)[:240]
   print("GITHUB DATA ERROR:",repr(exc),flush=True)
   if cache["value"]:
    return dict(cache["value"],status=cache["value"].get("status","")+" · Uwaga: odczyt danych chwilowo niedostępny.")
   local=json.loads(Path("data/verified.json").read_text(encoding="utf-8"))
   local["status"]=local.get("status","")+" · Dane zapasowe, aktualizacja GitHub chwilowo niedostępna."
   return local
@app.get("/")
def index():
 """Render actual offer cards on the server so the page works even if iOS blocks JS."""
 data=read_offers()
 template=Path("static/index.html").read_text(encoding="utf-8")
 cards=[]
 for offer in data.get("offers",[])[:250]:
  title=html.escape(str(offer.get("title") or "Ogłoszenie"))
  description=html.escape(str(offer.get("description") or ""))
  source=html.escape(str(offer.get("query") or ""))
  url=str(offer.get("url") or "")
  if not url.startswith(("https://","http://")): continue
  cards.append(f'<article class="card offer"><h3>{title}</h3><p class="muted">{description}</p><div class="small muted">{source}</div><a href="{html.escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">Otwórz źródło ↗</a></article>')
 template=template.replace('<section id="results"></section>','<section id="results">'+''.join(cards)+'</section>')
 template=template.replace('id="count">0 wyników','id="count">'+str(len(cards))+' wyników')
 template=template.replace('id="status" class="muted">Sprawdzam połączenie…','id="status" class="muted">Dane: '+html.escape(str(data.get("updated_at") or ""))+' · '+html.escape(str(data.get("status") or "")))
 return Response(template,mimetype="text/html",headers={"Cache-Control":"no-store, max-age=0"})

@app.get("/health")
def health():
 data=read_offers()
 return jsonify({"ok":True,"updated_at":data.get("updated_at"),"count":len(data.get("offers",[])),"source":cache["source"],"error":cache["last_error"]})
@app.get("/api/offers")
def offers():
 response=jsonify(read_offers())
 response.headers["Cache-Control"]="no-store, max-age=0"
 return response
