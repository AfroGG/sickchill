# coding=utf-8
# Author: Dustyn Gibson <miigotu@gmail.com>
# URL: https://sickrage.github.io
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage. If not, see <http://www.gnu.org/licenses/>.

import re
from requests.utils import dict_from_cookiejar
from urllib import urlencode

from sickbeard import logger, tvcache
from sickbeard.bs4_parser import BS4Parser

from sickrage.helper.exceptions import AuthException
from sickrage.helper.common import convert_size, try_int
from sickrage.providers.torrent.TorrentProvider import TorrentProvider


class MoreThanTVProvider(TorrentProvider):  # pylint: disable=too-many-instance-attributes

    def __init__(self):

        TorrentProvider.__init__(self, "MoreThanTV")

        self._uid = None
        self._hash = None
        self.username = None
        self.password = None
        self.ratio = None
        self.minseed = None
        self.minleech = None

        self.url = 'https://www.morethan.tv/'
        self.urls = {
            'login': self.url + 'login.php',
            'search': self.url + 'torrents.php',
        }

        self.proper_strings = ['PROPER', 'REPACK']

        self.cache = MoreThanTVCache(self, min_time=20)  # only poll MoreThanTV every 20 minutes max

    def _check_auth(self):

        if not self.username or not self.password:
            raise AuthException("Your authentication credentials for " + self.name + " are missing, check your config.")

        return True

    def login(self):
        if any(dict_from_cookiejar(self.session.cookies).values()):
            return True

        login_params = {
            'username': self.username,
            'password': self.password,
            'login': 'Log in',
            'keeplogged': '1'
        }

        response = self.get_url(self.urls['login'], post_data=login_params, timeout=30)
        if not response:
            logger.log(u"Unable to connect to provider", logger.WARNING)
            return False

        if re.search('Your username or password was incorrect.', response):
            logger.log(u"Invalid username or password. Check your settings", logger.WARNING)
            return False

        return True

    def search(self, search_strings, age=0, ep_obj=None):  # pylint: disable=too-many-branches, too-many-locals
        results = []
        if not self.login():
            return results

        search_params = {
            'tags_type': 1,
            'order_by': 'time',
            'order_way': 'desc',
            'action': 'basic',
            'searchsubmit': 1,
            'searchstr': ''
        }

        for mode in search_strings:
            items = []
            logger.log(u"Search Mode: %s" % mode, logger.DEBUG)
            for search_string in search_strings[mode]:
                if mode != 'RSS':
                    logger.log(u"Search string: %s " % search_string, logger.DEBUG)

                search_params['searchstr'] = search_string

                search_url = "%s?%s" % (self.urls['search'], urlencode(search_params))
                logger.log(u"Search URL: %s" % search_url, logger.DEBUG)

                # returns top 15 results by default, expandable in user profile to 100
                data = self.get_url(search_url)
                if not data:
                    continue

                with BS4Parser(data, 'html5lib') as html:
                    torrent_table = html.find('table', class_='torrent_table')
                    torrent_rows = torrent_table.find_all('tr') if torrent_table else []

                    # Continue only if one Release is found
                    if len(torrent_rows) < 2:
                        logger.log(u"Data returned from provider does not contain any torrents", logger.DEBUG)
                        continue

                    def process_column_header(td):
                        result = ''
                        if td.a and td.a.img:
                            result = td.a.img.get('title', td.a.get_text(strip=True))
                        if not result:
                            result = td.get_text(strip=True)
                        return result

                    labels = [process_column_header(label) for label in torrent_rows[0].find_all('td')]

                    # skip colheader
                    for result in torrent_rows[1:]:
                        try:
                            # skip if torrent has been nuked due to poor quality
                            if result.find('img', alt='Nuked'):
                                continue

                            title = result.find('a', title='View torrent').get_text(strip=True)
                            download_url = self.url + result.find('span', title='Download').parent['href']
                            if not all([title, download_url]):
                                continue

                            cells = result.find_all('td')
                            seeders = try_int(cells[labels.index('Seeders')].get_text(strip=True))
                            leechers = try_int(cells[labels.index('Leechers')].get_text(strip=True))
                            if seeders < self.minseed or leechers < self.minleech:
                                if mode != 'RSS':
                                    logger.log(u"Discarding torrent because it doesn't meet the minimum seeders or leechers: {0} (S:{1} L:{2})".format(title, seeders, leechers), logger.DEBUG)
                                continue

                            torrent_size = cells[labels.index('Size')].get_text(strip=True)
                            size = convert_size(torrent_size) or -1

                            item = title, download_url, size, seeders, leechers
                            if mode != 'RSS':
                                logger.log(u"Found result: %s " % title, logger.DEBUG)

                            items.append(item)
                        except StandardError:
                            continue

            # For each search mode sort all the items by seeders if available
            items.sort(key=lambda tup: tup[3], reverse=True)

            results += items

        return results

    def seed_ratio(self):
        return self.ratio


class MoreThanTVCache(tvcache.TVCache):
    def _getRSSData(self):
        search_strings = {'RSS': ['']}
        return {'entries': self.provider.search(search_strings)}

provider = MoreThanTVProvider()
