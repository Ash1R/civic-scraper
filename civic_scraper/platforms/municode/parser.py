# asset_type function ie: find .pdf .docx etc.

import re
from datetime import datetime

import bs4

from civic_scraper.base.constants import SUPPORTED_ASSET_TYPES


class ParsingError(Exception):
    pass


class Parser:
    def __init__(self, html):
        self.html = html
        self.soup = bs4.BeautifulSoup(html, "html.parser")

    def parse(self):
        divs = self._get_rows()
        metadata = self._extract_asset_data(divs)
        return metadata

    def _get_rows(self):
        tr_tags = []
        all_rows = self.soup.find_all('tr')
        for r in all_rows:
            th_tags = r.find_all('th')
            if not th_tags:
                tr_tags.append(r)
        return tr_tags

    def _get_format(self, url):
        if "pdf" in url:
            return "application/pdf"
        if "html" in url:
            return "text/html"

        return "text/html"

    def _extract_asset_data(self, divs):

        metadata = []
        for row in divs:
            date = self._get_cell("Date", row).get_text()
            meeting = self._get_cell("Meeting", row).get_text()
            agendas = self._get_cell("Agenda", row).find_all("a")
            if len(agendas) > 0:
                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": agendas[0]["href"], "asset_type": "agenda", "format": self._get_format(agendas[0]["href"])})
                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": agendas[1]["href"], "asset_type": "agenda", "format": self._get_format(agendas[1]["href"])})

            agenda_packets = self._get_cell("Agenda Packet", row).find_all("a")
            if len(agenda_packets) > 0:

                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": agenda_packets[0]["href"], "asset_type": "agenda_packet", "format": self._get_format(agenda_packets[0]["href"])})
                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": agenda_packets[1]["href"], "asset_type": "agenda_packet", "format": self._get_format(agenda_packets[1]["href"])})
            if self._get_cell("Minutes", row).find("a"):
                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": self._get_cell("Minutes", row).find("a")['href'], "asset_type": "minutes", "format": self._get_format(self._get_cell("Minutes", row).find("a")['href'])})

            if self._get_cell("Video", row).find("a"):
                metadata.append({"date": date.strip(), "meeting": meeting.strip(),  "url": self._get_cell("Video", row).find("a")['href'], "asset_type": "video", "format": self._get_format(self._get_cell("Video", row).find("a")['href'])})
        print(metadata)
        return metadata

    def _get_cell(self, data_th, row):
        return row.find('td', {'data-th': data_th})
