#!/usr/bin/env python3
"""Public search discovery. All search hits are leads, not verified auctions."""
import json, re, sys, time, hashlib, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

OUT=Path("data/verified.json")
PLACES=["Blachownia","Częstochowa","Kłobuck","Konopiska","Wręczyca Wielka","Poczesna","Myszków","Olsztyn śląskie","Kłomnice","Koniecpol","Herby","Lubliniec","Koziegłowy","Poraj","Mstów","Janów częstochowski","Przyrów","Rędziny","Kamienica Polska"]
QUERIES=[
 '"licytacja nieruchomości" "Częstochowa"',
 '"licytacja nieruchomości" "Kłobuck"',
 '"licytacja nieruchomości" "Blachownia"',
 '"syndyk" "nieruchomości" "Częstochowa"',
 '"przetarg" "nieruchomości" "Częstochowa"',
 '"przetarg" "nieruchomości" "Blachownia"',
 '"sprzedaż nieruchomości" "BIP" "Kłobuck"',
 '"sprzedaż nieruchomości" "BIP" "Lubliniec"',
 '"licytacja nieruchomości" "Myszków"',
 '"przetarg" "nieruchomości" "Konopiska"',
 '"licytacja" "Wręczyca Wielka" nieruchomość',
 '"licytacja" "Poczesna" nieruchomość',
 '"KOWR" "przetarg" "śląskie" nieruchomości',
 'site:licytacje.komornik.pl "Częstochowa" nieruchomości',
 'site:licytacje.komornik.pl "Kłobuck" nieruchomości',
 'site:listaprzetargow.pl "Częstochowa" licytacje',
 'site:licytor.pl "Częstochowa" nieruchomość',
 'site:krz.ms.gov.pl "Częstochowa" nieruchomość'
]
PROPERTY=re.compile(r"nieruchom|dzia[łl]k|lokal|mieszkan|dom\\b|grunt|licytac|przetarg|syndyk|komornik|zabudowan|budyn|kamienic|posesj|sprzeda[żz]",re.I)
LOCAL=re.compile(r"blachown|cz[eę]stochow|k[łl]obuck|konopisk|wr[eę]czyc|poczesn|myszk[oó]w|olsztyn|k[łl]omnic|koniecpol|herby|lubliniec|kozieg[łl]ow|poraj|mst[oó]w|przyr[oó]w|r[eę]dzin|kamienic[aey] polsk|jan[oó]w",re.I)
HEAD={"User-Agent":"Mozilla/5.0 (compatible; RadarOkazji/1.0; public search discovery)"}
def get_items(url):
 r=requests.get(url,headers=HEAD,timeout=(5,12))
 r.raise_for_status()
 root=ET.fromstring(r.content)
 for item in root.findall(".//item"):
  title=" ".join((item.findtext("title") or "").split())
  summary=re.sub(r"<[^>]+>"," ",item.findtext("description") or "")
  summary=" ".join(summary.split())[:500]
  link=(item.findtext("link") or "").strip()
  if title and link.startswith("https://") and PROPERTY.search(title+" "+summary) and LOCAL.search(title+" "+summary+" "+urllib.parse.unquote(link)):
   yield {"title":title[:180],"url":link,"description":"Trop z wyszukiwarki — wymaga sprawdzenia u źródła. "+summary[:250],"query":"Automatyczne wyszukiwanie — wymaga weryfikacji","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
def search(q):
 encoded=urllib.parse.quote(q)
 for url in ["https://www.bing.com/search?format=rss&q="+encoded, "https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"pl","gl":"PL","ceid":"PL:pl"})]:
  try:
   items=list(get_items(url))
   if items: return items
  except (requests.RequestException, ET.ParseError) as e: print("source unavailable",type(e).__name__,file=sys.stderr)
 return []
def main():
 data=json.loads(OUT.read_text(encoding="utf-8"))
 now=datetime.now(timezone.utc)
 original=data.get("offers",[])
 offers={o["url"]:o for o in original if o.get("verified_at")}
 discovered=0; worked=0
 for q in QUERIES:
  hits=search(q)
  if hits: worked+=1
  for o in hits:
   if o["url"] not in offers:
    offers[o["url"]]=o
    discovered+=1
  time.sleep(0.4)
 # Prevent stale unverified search hits from accumulating forever.
 cutoff=now-timedelta(days=35)
 final=[]
 for o in offers.values():
  if o.get("verified_at"):
   final.append(o)
  else:
   try:
    if datetime.fromisoformat(o.get("discovered_at",""))>=cutoff: final.append(o)
   except ValueError: pass
 data.update({"updated_at":now.isoformat(),"offers":final[:250],"status":f"Oferty oficjalnie sprawdzone i tropy z wyszukiwarek. Przeszukano {len(QUERIES)} zapytań; odpowiedzi z {worked}. Wyniki automatyczne wymagają weryfikacji. Nowych: {discovered}.","source_health":{"queries":len(QUERIES),"responding":worked,"new":discovered}})
 OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(data["status"],"Total",len(final))
if __name__=="__main__":main()
