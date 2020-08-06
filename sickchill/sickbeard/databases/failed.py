from sickchill.sickbeard import db
from sickchill.sickbeard.common import Quality


# Add new migrations at the bottom of the list; subclass the previous migration.
class InitialSchema(db.SchemaUpgrade):
    def test(self):
        return self.has_table('db_version')

    def execute(self):
        queries = [
            ('CREATE TABLE failed (release TEXT, size NUMERIC, provider TEXT);',),
            ('CREATE TABLE history (date NUMERIC, size NUMERIC, release TEXT, provider TEXT, old_status NUMERIC DEFAULT 0, showid NUMERIC DEFAULT -1, season NUMERIC DEFAULT -1, episode NUMERIC DEFAULT -1);',),
            ('CREATE TABLE db_version (db_version INTEGER);',),
            ('INSERT INTO db_version (db_version) VALUES (1);',),
        ]
        for query in queries:
            if len(query) == 1:
                self.connection.action(query[0])
            else:
                self.connection.action(query[0], query[1:])


class SizeAndProvider(InitialSchema):
    def test(self):
        return self.has_column('failed', 'size') and self.has_column('failed', 'provider')

    def execute(self):
        self.add_column('failed', 'size', 'NUMERIC')
        self.add_column('failed', 'provider', 'TEXT', '')


class History(SizeAndProvider):
    """Snatch history that can't be modified by the user"""

    def test(self):
        return self.has_table('history')

    def execute(self):
        self.connection.action('CREATE TABLE history (date NUMERIC, ' +
                               'size NUMERIC, release TEXT, provider TEXT);')


class HistoryStatus(History):
    """Store episode status before snatch to revert to if necessary"""

    def test(self):
        return self.has_column('history', 'old_status')

    def execute(self):
        self.add_column('history', 'old_status', 'NUMERIC', Quality.NONE)
        self.add_column('history', 'showid', 'NUMERIC', '-1')
        self.add_column('history', 'season', 'NUMERIC', '-1')
        self.add_column('history', 'episode', 'NUMERIC', '-1')
