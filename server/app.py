"""Symulowane portale ogłoszeniowe (OLX i Otodom) dla testów scrapera.

Uruchomienie:  python -m server --port 8080 --scenario normal

Scenariusze (--scenario) celowo psują działanie, żeby sprawdzić reakcję scrapera:
  normal          prawidłowe odpowiedzi
  empty           brak ofert na każdej stronie
  layout_change   zmieniony HTML: scraper nie znajduje kart ani danych
  no_state        OLX bez stanu __PRERENDERED_STATE__ (tylko HTML)
  rate_limit      co trzecie żądanie dostaje 429 z Retry-After
  server_error    strona 2 każdego listingu zwraca 500
"""
import argparse
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import olx, otodom
from .data import build_offers

SCENARIOS = ("normal", "empty", "layout_change", "no_state", "rate_limit", "server_error")
OLX_PREFIX = "/nieruchomosci/mieszkania/sprzedaz/"
OTODOM_PATH = "/pl/wyniki/sprzedaz/mieszkanie,rynek-wtorny/cala-polska"
OLX_PRICE_FROM = "search[filter_float_price:from]"
OLX_PRICE_TO = "search[filter_float_price:to]"

logger = logging.getLogger("portal-mock")


class PortalServer(ThreadingHTTPServer):
	def __init__(self, address, scenario: str):
		super().__init__(address, PortalHandler)
		self.scenario = scenario
		self.offers = sorted(build_offers(), key=lambda o: o.created_at, reverse=True)
		self._lock = threading.Lock()
		self._requests = 0

	def throttle_now(self) -> bool:
		with self._lock:
			self._requests += 1
			return self.scenario == "rate_limit" and self._requests % 3 == 0


class PortalHandler(BaseHTTPRequestHandler):
	server: PortalServer

	def do_GET(self):
		url = urlparse(self.path)
		query = parse_qs(url.query)

		if url.path == "/health":
			return self._send(200, "text/plain; charset=utf-8", "ok")

		if self.server.throttle_now():
			return self._send(429, "text/plain; charset=utf-8", "Too Many Requests",
			                  headers={"Retry-After": "1"})

		page = _page(query)
		if self.server.scenario == "server_error" and page == 2:
			return self._send(500, "text/plain; charset=utf-8", "Internal Server Error")

		if url.path.startswith(OLX_PREFIX):
			province = url.path[len(OLX_PREFIX):].strip("/")
			body = self._olx(province, query, page)
			return self._send(200, "text/html; charset=utf-8", body)

		if url.path == OTODOM_PATH:
			limit = otodom.parse_limit((query.get("limit") or [None])[0])
			offers = [] if self.server.scenario == "empty" else self.server.offers
			body = otodom.render_results(offers, page, limit, self.server.scenario)
			return self._send(200, "text/html; charset=utf-8", body)

		return self._send(404, "text/plain; charset=utf-8", "Not Found")

	def _olx(self, province: str, query: dict, page: int) -> str:
		offers = [o for o in self.server.offers
		          if (not province or o.region_slug == province)]
		price_from = _int((query.get(OLX_PRICE_FROM) or [None])[0], 0)
		price_to = _int((query.get(OLX_PRICE_TO) or [None])[0], 10**9)
		offers = [o for o in offers if price_from <= o.price <= price_to]
		if self.server.scenario == "empty":
			offers = []
		return olx.render_listing(offers, page, len(offers), self.server.scenario)

	def _send(self, status: int, content_type: str, body: str, headers: dict | None = None):
		payload = body.encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(payload)))
		for name, value in (headers or {}).items():
			self.send_header(name, value)
		self.end_headers()
		self.wfile.write(payload)

	def log_message(self, format, *args):
		logger.debug("%s - %s", self.address_string(), format % args)


def _page(query: dict) -> int:
	return _int((query.get("page") or [None])[0], 1)


def _int(value, default: int) -> int:
	try:
		return int(value) if value is not None else default
	except ValueError:
		return default


def main(argv=None) -> None:
	parser = argparse.ArgumentParser(description="Symulowane portale OLX i Otodom")
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=8080)
	parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
	args = parser.parse_args(argv)
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
	server = PortalServer((args.host, args.port), args.scenario)
	logger.info("Portal mock on http://%s:%s (scenario=%s)", args.host, args.port, args.scenario)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	finally:
		server.server_close()
