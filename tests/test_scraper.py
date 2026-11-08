"""Regression tests for public property collectors. No network access."""
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from scripts import refresh

class FakeResponse:
    def __init__(self, html):
        self.text = html
    def raise_for_status(self):
        return None

OLX_HTML = """
<div data-cy="l-card">
  <a data-testid="card-title-link"
     aria-label="Dom na sprzedaż Blachownia"
     href="https://www.olx.pl/d/oferta/dom-blachownia-CID3-IDx1.html?tracking=foo">
     Dom na sprzedaż Blachownia
  </a>
  <p data-testid="ad-price">349 000 zł</p>
  <p data-testid="location-date">Blachownia - dzisiaj</p>
</div>
<div data-cy="l-card">
  <a data-testid="card-title-link" href="https://www.otodom.pl/pl/oferta/test-IDa123">Oferta z Otodom</a>
  <p data-testid="location-date">Częstochowa</p>
</div>
"""

class ScraperTest(unittest.TestCase):
    @patch("scripts.refresh.time.sleep")
    @patch("scripts.refresh.requests.get")
    def test_olx_accepts_own_offers_and_removes_tracking(self, get, sleep):
        get.return_value = FakeResponse(OLX_HTML)
        results = list(refresh.olx_listings())
        self.assertEqual(len(results), 18)
        self.assertTrue(all(x["url"] == "https://www.olx.pl/d/oferta/dom-blachownia-CID3-IDx1.html" for x in results))
        self.assertTrue(all(x["source"] == "OLX" for x in results))
        self.assertIn("349 000", results[0]["description"])
        self.assertEqual(get.call_count, 18)

    @patch("scripts.refresh.requests.get")
    def test_bip_excludes_results_and_rentals(self, get):
        today = datetime.now(timezone.utc).date().isoformat()
        get.return_value = FakeResponse(
            '<ul>'
            '<li><a href="https://blachownia.bip.net.pl/kategorie/175/artykuly/1-test">'
            'Ogłoszenie o przetargu na sprzedaż działki Blachownia</a>'
            '(Opublikowano: ' + today + ')</li>'
            '<li><a href="https://blachownia.bip.net.pl/kategorie/175/artykuly/2-test">'
            'Informacja o negatywnym wyniku przetargu na sprzedaż działki</a>'
            '(Opublikowano: ' + today + ')</li>'
            '<li><a href="https://blachownia.bip.net.pl/kategorie/175/artykuly/3-test">'
            'Przetarg na najem lokalu Blachownia</a>'
            '(Opublikowano: ' + today + ')</li>'
            '</ul>')
        results = list(refresh.bip_blachownia())
        self.assertEqual(len(results), 1)
        self.assertIn("Blachownia", results[0]["title"])

    def test_search_filters_by_locality(self):
        self.assertTrue(refresh.LOCAL.search("działka w Częstochowie"))
        self.assertFalse(refresh.LOCAL.search("nieruchomość Wrocław"))

if __name__ == "__main__":
    unittest.main()
