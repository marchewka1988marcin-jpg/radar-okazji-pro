#!/usr/bin/env python3
"""Public search discovery. All search hits are leads, not verified auctions."""
import json, re, sys, time, hashlib, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup

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
 'site:krz.ms.gov.pl "Częstochowa" nieruchomość',
 'site:olx.pl/d/oferta/ nieruchomości Częstochowa sprzedaż',
 'site:otodom.pl/pl/oferta/ Częstochowa działka dom mieszkanie',
 'site:posrednik.pl/listings/ Częstochowa sprzedaż'
]
PROPERTY=re.compile(r"nieruchom|dzia[łl]k|lokal|mieszkan|dom\b|grunt|licytac|przetarg|syndyk|komornik|zabudowan|budyn|kamienic|posesj|sprzeda[żz]",re.I)
TRUSTED=re.compile(r"(?:olx\.pl|otodom\.pl|posrednik\.pl|licytacje\.komornik\.pl|listaprzetargow\.pl|licytor\.pl|adradar\.pl|aukcjeskarbowe\.pl|(?:^|\.)bip\.|(?:^|\.)gov\.pl|(?:^|\.)kowa?nr?\.gov\.pl)",re.I)
LOCAL=re.compile(r"blachown|cz[eę]stochow|k[łl]obuck|konopisk|wr[eę]czyc|poczesn|myszk[oó]w|olsztyn|k[łl]omnic|koniecpol|herby|lubliniec|kozieg[łl]ow|poraj|mst[oó]w|przyr[oó]w|r[eę]dzin|kamienic[aey] polsk|jan[oó]w",re.I)
HEAD={"User-Agent":"Mozilla/5.0 (compatible; RadarOkazji/1.0; public search discovery)"}
SOURCE_ERRORS=[]
def get_items(url):
 r=requests.get(url,headers=HEAD,timeout=(5,12))
 r.raise_for_status()
 root=ET.fromstring(r.content)
 for item in root.findall(".//item"):
  title=" ".join((item.findtext("title") or "").split())
  summary=re.sub(r"<[^>]+>"," ",item.findtext("description") or "")
  summary=" ".join(summary.split())[:500]
  link=(item.findtext("link") or "").strip()
  if title and link.startswith("https://") and TRUSTED.search(urllib.parse.urlparse(link).netloc) and PROPERTY.search(title+" "+summary) and LOCAL.search(title+" "+summary+" "+urllib.parse.unquote(link)):
   yield {"title":title[:180],"url":link,"description":"Trop z wyszukiwarki — wymaga sprawdzenia u źródła. "+summary[:250],"query":"Automatyczne wyszukiwanie — wymaga weryfikacji","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
def search(q):
 encoded=urllib.parse.quote(q)
 for url in ["https://www.bing.com/search?format=rss&q="+encoded, "https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"pl","gl":"PL","ceid":"PL:pl"})]:
  try:
   items=list(get_items(url))
   if items: return items
  except (requests.RequestException, ET.ParseError) as e: print("source unavailable",type(e).__name__,file=sys.stderr)
 return []
def official_notices():
 """Read public cards from the National Bailiffs Council website, no paywall."""
 for kind in ["obwieszczenia-o-licytacji","obwieszczenia-o-terminie-opisu-i-oszacowania"]:
  url="https://licytacje.komornik.pl/wyszukiwarka/"+kind
  try:
   r=requests.get(url,headers=HEAD,timeout=(5,18))
   if r.status_code==404: r=requests.get(url+"?page=1",headers=HEAD,timeout=(5,18))
   r.raise_for_status()
   soup=BeautifulSoup(r.text,"html.parser")
   for a in soup.select("a.notice[href]"):
    title=" ".join(a.stripped_strings)
    link=a.get("href","")
    if not link.startswith("https://licytacje.komornik.pl/"): continue
    if not LOCAL.search(title): continue
    stage="Licytacja" if kind=="obwieszczenia-o-licytacji" else "Opis i oszacowanie (przed licytacją)"
    yield {"title":stage+" — "+title[:150],"url":link,"description":"Oficjalny portal komorniczy. "+title[:350],"query":"Komornik — oficjalne obwieszczenie","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
  except requests.RequestException as exc:
   SOURCE_ERRORS.append("Portal komorniczy: "+str(exc)[:90])
   print("official source error",str(exc)[:120],file=sys.stderr)

def bailiff_office():
 """Official local bailiff's public auction list; excludes cars and finished sales."""
 url="https://www.czestochowa-komornik.com.pl/licytacje/"
 try:
  r=requests.get(url,headers=HEAD,timeout=(5,18));r.raise_for_status()
  soup=BeautifulSoup(r.text,"html.parser")
  for card in soup.select("article.b-auctions__item"):
   if card.get("data-type")!="nieruchomosc" or card.get("data-status")!="active": continue
   a=card.select_one('a[href*="licytacje.komornik.pl/licytacje/"]')
   if not a: continue
   title=" ".join(card.select_one(".b-auctions__title").stripped_strings) if card.select_one(".b-auctions__title") else ""
   if not title: title="Nieruchomość — licytacja komornicza"
   details=" ".join(card.stripped_strings)
   yield {"title":title[:180],"url":a["href"],"description":"Komornik Częstochowa · "+details[:380],"query":"Licytacja — kancelaria komornicza Częstochowa","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
 except requests.RequestException as exc:
  SOURCE_ERRORS.append("Kancelaria: "+str(exc)[:90])
  print("bailiff office error",str(exc)[:120],file=sys.stderr)

def posrednik_listings():
 """Public sale cards from Pośrednik Częstochowa, not rental or swaps."""
 url="https://posrednik.pl/nieruchomosci?sort=newest"
 try:
  r=requests.get(url,headers=HEAD,timeout=(5,18));r.raise_for_status()
  soup=BeautifulSoup(r.text,"html.parser")
  for card in soup.select("article.listing"):
   category=card.select_one(".listing-category-line")
   if not category or "Sprzedaż" not in category.get_text(" ",strip=True): continue
   a=card.select_one("a.listing-body-link[href]")
   title=card.select_one(".listing-title")
   price=card.select_one(".listing-price")
   meta=card.select_one(".listing-meta")
   if not a or not title: continue
   location=meta.get_text(" ",strip=True) if meta else ""
   if not LOCAL.search(location+" "+title.get_text(" ",strip=True)): continue
   if re.search(r"radomsko|zawiercie|katowice|sosnowiec|gliwice",location,re.I): continue
   link=urllib.parse.urljoin(url,a["href"])
   desc="Sprzedaż · "+(price.get_text(" ",strip=True) if price else "cena niepodana")+" · "+location
   yield {"title":title.get_text(" ",strip=True)[:180],"url":link,"description":desc[:380],"query":"Pośrednik — ogłoszenie sprzedaży","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
 except requests.RequestException as exc:
  SOURCE_ERRORS.append("Pośrednik: "+str(exc)[:90])
  print("posrednik error",str(exc)[:120],file=sys.stderr)

def otodom_listings():
 """Public Otodom sale results; no results reported if access is blocked."""
 urls=[
  "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/slaskie/czestochowa/czestochowa/czestochowa",
  "https://www.otodom.pl/pl/wyniki/sprzedaz/dom/slaskie/czestochowa/czestochowa/czestochowa",
  "https://www.otodom.pl/pl/wyniki/sprzedaz/dzialka/slaskie/czestochowa/czestochowa/czestochowa",
 ]
 seen=set()
 for url in urls:
  try:
   r=requests.get(url,headers={**HEAD,"Accept-Language":"pl-PL,pl;q=0.9"},timeout=(5,18));r.raise_for_status()
   soup=BeautifulSoup(r.text,"html.parser")
   for a in soup.select('a[href*="/pl/oferta/"]'):
    link=urllib.parse.urljoin("https://www.otodom.pl",a.get("href","")).split("?")[0]
    if link in seen or not re.match(r"^https://www\.otodom\.pl/pl/oferta/[^/?#]+-ID[a-zA-Z0-9]+$",link): continue
    seen.add(link)
    title=" ".join(a.stripped_strings)
    if len(title)<8:
     img=a.select_one("img[alt]")
     title=img.get("alt","") if img else ""
    if len(title)<8: continue
    card=a.find_parent("article") or a.parent
    details=" ".join(card.stripped_strings)[:500] if card else title
    if not LOCAL.search(details): continue
    yield {"title":title[:180],"url":link,"description":"Otodom · oferta sprzedaży · "+details[:300],"query":"Otodom — ogłoszenie sprzedaży","verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
  except requests.RequestException as exc:
   SOURCE_ERRORS.append("Otodom: "+str(exc)[:90])
   print("otodom unavailable",str(exc)[:140],file=sys.stderr)


def olx_listings():
 """Collect public sale cards from OLX (no account, captcha bypass or paid content).
 Each card must contain a direct OLX sale URL and a matching locality.
 """
 places=("blachownia","czestochowa","klobuck","konopiska","lubliniec","myszkow")
 kinds=("mieszkania","domy","dzialki")
 for place in places:
  for kind in kinds:
   url=f"https://www.olx.pl/nieruchomosci/{kind}/sprzedaz/{place}/"
   try:
    r=requests.get(url,headers={**HEAD,"Accept-Language":"pl-PL,pl;q=0.9"},timeout=(5,16))
    if getattr(r,"status_code",200) in (401,403,429):
     SOURCE_ERRORS.append("OLX: HTTP "+str(r.status_code)+" — automatyczny dostęp zablokowany")
     print("OLX access blocked: HTTP",r.status_code,file=sys.stderr)
     return
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    cards=soup.select('[data-cy="l-card"]')
    if not cards: print("OLX no public cards:",kind,place,file=sys.stderr)
    for card in cards:
     a=card.select_one('a[data-testid="card-title-link"]')
     if not a: continue
     link=urllib.parse.urljoin("https://www.olx.pl/",a.get("href",""))
     parts=urllib.parse.urlsplit(link)
     if parts.hostname not in ("www.olx.pl","olx.pl") or not parts.path.startswith("/d/oferta/") or not parts.path.endswith(".html"): continue
     link=urllib.parse.urlunsplit(("https","www.olx.pl",parts.path,"",""))
     title=" ".join((a.get("aria-label") or a.get_text(" ",strip=True)).split())
     loc_el=card.select_one('[data-testid="location-date"]')
     location=loc_el.get_text(" ",strip=True) if loc_el else ""
     if not title or not LOCAL.search(location): continue
     price_el=card.select_one('[data-testid="ad-price"]')
     price=price_el.get_text(" ",strip=True) if price_el else "cena do sprawdzenia"
     yield {"title":title[:180],"url":link,"description":f"Sprzedaż · {price} · {location}"[:380],
            "query":"OLX — ogłoszenie sprzedaży","source":"OLX","category":kind,
            "verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
   except requests.RequestException as exc:
    SOURCE_ERRORS.append("OLX: "+str(exc).split("for url:")[0][:70])
    print("OLX source unavailable:",kind,place,str(exc)[:110],file=sys.stderr)
   time.sleep(0.35)


def bip_blachownia():
 """Watch official municipal property-sale notices; skip results and rentals."""
 url="https://blachownia.bip.net.pl/kategorie/175-przetargi-na-zbycie-nieruchomosci-stanowiacych-wlasnosc-gminy-blachownia"
 try:
  r=requests.get(url,headers=HEAD,timeout=(5,16));r.raise_for_status()
  soup=BeautifulSoup(r.text,"html.parser")
  for li in soup.select("li"):
   a=li.select_one('a[href*="/artykuly/"]')
   if not a: continue
   title=" ".join(a.stripped_strings)
   low=title.lower()
   if not re.search(r"przetarg|sprzeda[żz]|zbyci",low): continue
   if re.search(r"wynik|negatywn|najem|dzier[żz]aw|u[żz]yczen|bezprzetarg",low): continue
   stamp=re.search(r"Opublikowano:\s*(20\d{2}-\d\d-\d\d)",li.get_text(" ",strip=True))
   published=stamp.group(1) if stamp else None
   if published:
    try:
     if datetime.fromisoformat(published).replace(tzinfo=timezone.utc)<datetime.now(timezone.utc)-timedelta(days=45): continue
    except ValueError: continue
   link=urllib.parse.urljoin(url,a.get("href",""))
   if urllib.parse.urlsplit(link).hostname!="blachownia.bip.net.pl":continue
   yield {"title":title[:180],"url":link,"description":"Oficjalny BIP Blachowni · sprzedaż nieruchomości · publikacja "+(published or "data nieznana"),
          "query":"BIP Blachownia — ogłoszenie przetargowe","source":"BIP Blachownia","verified_at":None,
          "discovered_at":datetime.now(timezone.utc).isoformat()}
 except requests.RequestException as exc:
  SOURCE_ERRORS.append("BIP Blachownia: "+str(exc)[:90])
  print("BIP Blachownia unavailable",str(exc)[:110],file=sys.stderr)


def gratka_listings():
 """Read sale cards with canonical source links from public Gratka category pages."""
 for place in ("blachownia","czestochowa","klobuck","konopiska","lubliniec","myszkow"):
  url="https://gratka.pl/nieruchomosci/"+place
  try:
   r=requests.get(url,headers={**HEAD,"Accept-Language":"pl-PL,pl;q=0.9"},timeout=(5,16))
   if getattr(r,"status_code",200) in (401,403,429):
    SOURCE_ERRORS.append("Gratka: HTTP "+str(r.status_code))
    return
   r.raise_for_status()
   soup=BeautifulSoup(r.text,"html.parser")
   for card in soup.select('[data-cy="card"]'):
    link_el=card.select_one("a.property-card__link[href]")
    title_el=card.select_one('[data-cy="propertyCardTitle"]')
    location_el=card.select_one('[data-cy="propertyCardLocation"]')
    price_el=card.select_one('[data-cy="propertyCardPrice"]')
    if not link_el or not title_el or not location_el: continue
    link=urllib.parse.urljoin(url,link_el.get("href","")).split("?")[0]
    parsed=urllib.parse.urlsplit(link)
    if parsed.hostname not in ("gratka.pl","www.gratka.pl") or not parsed.path.startswith("/nieruchomosci/") or "/oi/" not in parsed.path:continue
    title=title_el.get_text(" ",strip=True)
    location=location_el.get_text(" ",strip=True)
    if not title or not LOCAL.search(location): continue
    price=price_el.get_text(" ",strip=True) if price_el else "cena do sprawdzenia"
    slug=parsed.path.lower()
    category="mieszkania" if "mieszkanie-" in slug else "domy" if "dom-" in slug else "dzialki" if "dzialka-" in slug else ""
    yield {"title":title[:180],"url":link,"description":("Sprzedaż · "+price+" · "+location)[:380],
           "query":"Gratka — ogłoszenie sprzedaży","source":"Gratka","category":category,
           "verified_at":None,"discovered_at":datetime.now(timezone.utc).isoformat()}
  except requests.RequestException as exc:
   SOURCE_ERRORS.append("Gratka: "+str(exc)[:85])
   print("Gratka unavailable",place,str(exc)[:110],file=sys.stderr)
  time.sleep(0.3)

def main():
 data=json.loads(OUT.read_text(encoding="utf-8"))
 now=datetime.now(timezone.utc)
 original=data.get("offers",[])
 offers={o["url"]:o for o in original if o.get("url") and (o.get("verified_at") or o.get("discovered_at")) and not ("/hpr/pl/oferta/" in o["url"])}
 discovered=0; worked=0
 source_counts={"komornik_portal":0,"kancelaria_czestochowa":0,"posrednik":0,"otodom":0,"olx":0,"bip_blachownia":0,"gratka":0}
 for name,fn in [("komornik_portal",official_notices),("kancelaria_czestochowa",bailiff_office),("posrednik",posrednik_listings),("otodom",otodom_listings),("olx",olx_listings),("bip_blachownia",bip_blachownia),("gratka",gratka_listings)]:
  hits=list(fn())
  source_counts[name]=len(hits)
  for o in hits:
   if o["url"] not in offers: offers[o["url"]]=o; discovered+=1
   else:
    offers[o["url"]].update({k:v for k,v in o.items() if k not in ("verified_at","discovered_at")})
    offers[o["url"]]["last_seen_at"]=now.isoformat()
 for q in QUERIES:
  hits=search(q)
  if hits: worked+=1
  for o in hits:
   if o["url"] not in offers:
    offers[o["url"]]=o
    discovered+=1
   else:
    offers[o["url"]]["last_seen_at"]=now.isoformat()
  time.sleep(0.4)
 # Prevent stale unverified search hits from accumulating forever.
 cutoff=now-timedelta(days=14)
 final=[]
 for o in offers.values():
  if o.get("verified_at"):
   final.append(o)
  else:
   try:
    if datetime.fromisoformat(o.get("last_seen_at") or o.get("discovered_at",""))>=cutoff: final.append(o)
   except ValueError: pass
 final.sort(key=lambda x: (bool(x.get("verified_at")),x.get("last_seen_at") or x.get("discovered_at") or ""),reverse=True)
 data.update({"updated_at":now.isoformat(),"offers":final[:250],"status":f"Bezpośrednie źródła: komornik {source_counts['komornik_portal']}, kancelaria {source_counts['kancelaria_czestochowa']}, Pośrednik {source_counts['posrednik']}. Wyszukiwarki RSS z trafieniami: {worked}/{len(QUERIES)}. Otodom: {source_counts['otodom']}, OLX: {source_counts['olx']}, BIP: {source_counts['bip_blachownia']}, Gratka: {source_counts['gratka']}. Nowych: {discovered}. Weryfikuj u źródła.","source_health":{"queries":len(QUERIES),"responding":worked,"new":discovered,"direct_sources":source_counts,"scan_completed_at":now.isoformat(),"source_errors":sorted(set(SOURCE_ERRORS))[:12]}})
 OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(data["status"],"Total",len(final))
if __name__=="__main__":main()
