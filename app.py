"""Radar Okazji: live dataset from public GitHub, independent of Render deployments."""
import json, time, threading, requests
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
app=Flask(__name__,static_folder="static")
DATA_URL="https://raw.githubusercontent.com/marchewka1988marcin-jpg/radar-okazji-pro/main/data/verified.json"
cache={"value":None,"checked":0}
lock=threading.Lock()
def read_offers():
 with lock:
  if cache["value"] and time.monotonic()-cache["checked"]<15: return cache["value"]
  try:
   r=requests.get(DATA_URL,params={"_":int(time.time()//90)},timeout=(3,7),headers={"User-Agent":"RadarOkazji/1.0"})
   r.raise_for_status()
   data=r.json()
   if not isinstance(data.get("offers"),list): raise ValueError("Missing offers")
   cache.update({"value":data,"checked":time.monotonic()})
   return data
  except Exception as exc:
   if cache["value"]:
    return dict(cache["value"],status=cache["value"].get("status","")+" · Uwaga: odczyt danych chwilowo niedostępny.")
   local=json.loads(Path("data/verified.json").read_text(encoding="utf-8"))
   local["status"]=local.get("status","")+" · Dane zapasowe, aktualizacja GitHub chwilowo niedostępna."
   return local
@app.get("/")
def index(): return send_from_directory("static","index.html")
@app.get("/health")
def health():
 data=read_offers()
 return jsonify({"ok":True,"updated_at":data.get("updated_at"),"count":len(data.get("offers",[]))})
@app.get("/api/offers")
def offers():
 response=jsonify(read_offers())
 response.headers["Cache-Control"]="no-store, max-age=0"
 return response
