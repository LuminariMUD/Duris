#!/usr/bin/env python3
"""Run the maintained importer against a disposable MariaDB schema, never game data."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]


class ImportFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'lib/information').mkdir(parents=True)
        (self.root / 'help').mkdir()
        self.script = self.root / 'scripts/import_help_to_prod.sh'
        self.script.write_text((ROOT / 'scripts/import_help_to_prod.sh').read_text())
        self.news = self.root / 'lib/information/news'
        self.news.write_text('new news')
        for name in ('help', 'motd', 'wizmotd', 'credits', 'faq', 'wizlist'):
            (self.root / ('lib/information/' + name)).write_text('new ' + name)
        self.index = self.root / 'lib/information/help_index'
        self.index.write_text('#\n"Alias"\na new alias entry\n')
        (self.root / 'help/duris_help_parsed.hlp').write_text(
            'Fresh\nFresh - Last Edited: 2026-09-11 by tester\na complete fresh page\n')
        self.env = dict(os.environ, DB_HOST='127.0.0.1', DB_PORT='1', DB_USER='test',
                        DB_PASSWD='unused', DB_NAME='news_preview_test', DB_SOCKET='')

    def run_import(self, *arguments, confirmation='yes\n'):
        return subprocess.run(['bash', str(self.script), *arguments], input=confirmation,
                              text=True, env=self.env, capture_output=True, timeout=30)


class NewsImportPreview(ImportFixture):
    def setUp(self):
        super().setUp()
        # Record even ignored connection attempts: dry-run must stay offline.
        commands = self.root / 'commands'
        commands.mkdir()
        self.connection_attempt = self.root / 'connection_attempt'
        self.env['IMPORT_TEST_CONNECTION_ATTEMPT'] = str(self.connection_attempt)
        for command in ('mysql', 'ssh'):
            stub = commands / command
            stub.write_text('#!/bin/sh\n: > "$IMPORT_TEST_CONNECTION_ATTEMPT"\nexit 99\n')
            stub.chmod(0o755)
        self.env['PATH'] = str(commands) + os.pathsep + self.env['PATH']

    def tearDown(self):
        self.assertFalse(self.connection_attempt.exists(), 'unexpected database connection')

    def test_news_only_dry_run_and_selected_database(self):
        (self.root / '.env').write_text('DB_NAME=selected_from_env\n')
        for connection in (('--local',), ('--remote', 'example.test', '--user', 'tester')):
            with self.subTest(connection=connection):
                result = self.run_import('--news-only', '--dry-run', *connection, confirmation='')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Database: selected_from_env', result.stdout)
                self.assertIn("Only lib/information/news -> mud_info.name = 'news'", result.stdout)
                self.assertIn('WOULD IMPORT: news (8 bytes)', result.stdout)
                self.assertEqual(result.stdout.count('WOULD IMPORT:'), 1)
                self.assertNotIn('Importing to pages', result.stdout)
                self.assertNotIn('Help Index Entries', result.stdout)
                self.assertNotIn('Parsed Help File', result.stdout)
                self.assertIn('Dry run complete', result.stdout)

    def test_invalid_news_and_clean_combination_fail_offline(self):
        for dry_run in ((), ('--dry-run',)):
            for flags in (('--news-only', '--clean'), ('--clean', '--news-only')):
                with self.subTest(flags=flags, dry_run=dry_run):
                    result = self.run_import(*flags, *dry_run)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('--news-only cannot be combined with --clean', result.stdout)
            for state in ('empty', 'missing'):
                with self.subTest(state=state, dry_run=dry_run):
                    self.news.write_bytes(b'')
                    if state == 'missing':
                        self.news.unlink()
                    result = self.run_import('--news-only', *dry_run)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('news file is empty' if state == 'empty' else 'news file not found',
                                  result.stdout)
                    self.assertNotIn('complete', result.stdout.lower())

    def test_declining_live_import_keeps_database_offline(self):
        result = self.run_import('--news-only', confirmation='no\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Aborted.', result.stdout)
        self.assertLess(result.stdout.index('Database: news_preview_test'),
                        result.stdout.index('Mode: LIVE'))


@unittest.skipUnless(os.environ.get('TEST_DB_HOST'), 'requires disposable TEST_DB_HOST')
class AtomicImport(ImportFixture):
    def setUp(self):
        super().setUp()
        self.schema = 'help_import_test_' + uuid.uuid4().hex[:12]
        password = os.environ.get('TEST_DB_PASSWORD', 'cache-test')
        self.env.update(MYSQL_PWD=password, DB_PASSWD=password,
                        DB_HOST=os.environ['TEST_DB_HOST'],
                        DB_PORT=os.environ.get('TEST_DB_PORT', '3306'),
                        DB_USER=os.environ.get('TEST_DB_USER', 'root'), DB_NAME=self.schema)
        self.mysql = ['mysql', '--protocol=tcp', '-h', self.env['DB_HOST'],
                      '-P', self.env['DB_PORT'], '-u', self.env['DB_USER'], '-N', '-B']
        self.query(f'CREATE DATABASE {self.schema} CHARACTER SET utf8mb4', False)
        self.addCleanup(self.query, f'DROP DATABASE {self.schema}', False)
        self.query("CREATE TABLE pages (title VARCHAR(255),text MEDIUMTEXT,category_id INT,"
                   "last_update DATETIME,last_update_by VARCHAR(255), CHECK(title<>'broken')) ENGINE=InnoDB;"
                   "CREATE TABLE mud_info (name VARCHAR(255) PRIMARY KEY,content MEDIUMTEXT) ENGINE=InnoDB;"
                   "INSERT INTO pages VALUES ('help','original',0,NOW(),'test'),('sentinel','old',0,NOW(),'test');"
                   "INSERT INTO mud_info VALUES ('news','original news'),('motd','website MOTD'),"
                   "('wizmotd','website wizard MOTD'),('credits','website credits'),('faq','website FAQ'),"
                   "('wizlist','website wizards'),('rules','website rules'),('custom','custom info');")

    def query(self, sql, database=True):
        return subprocess.run(self.mysql + ([self.schema] if database else []), input=sql,
                              text=True, env=self.env, capture_output=True, check=True).stdout.strip()

    def snapshot(self):
        return (self.query('SELECT name, HEX(content) FROM mud_info ORDER BY name'),
                self.query('SELECT * FROM pages ORDER BY title'))

    def test_planar_affinity_sources_publish_with_parsed_precedence(self):
        self.index.write_bytes((ROOT / 'lib/information/help_index').read_bytes())
        parsed = (self.root / 'help/duris_help_parsed.hlp')
        parsed.write_bytes((ROOT / 'help/duris_help_parsed.hlp').read_bytes())
        preview = self.run_import('--local', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        published = self.run_import('--local')
        self.assertEqual(published.returncode, 0, published.stdout + published.stderr)
        for element in ('Air', 'Water', 'Fire', 'Earth', 'Astral'):
            title = element + ' Affinity'
            with self.subTest(topic=title):
                self.assertEqual(self.query(f"SELECT COUNT(*) FROM pages WHERE title='{title}'"), '1')
                body = self.query(f"SELECT text FROM pages WHERE title='{title}'")
                for rule in ('level 51', 'remember', 'Groupmates, pets', 'VNUMs'):
                    self.assertIn(rule, body)
                self.assertIn('==See also==', body)  # Parsed source wins over index wrappers.
        self.assertIn('19826-19886', self.query("SELECT text FROM pages WHERE title='Planar Affinity'"))

    def test_news_only_preserves_bytes_and_other_content(self):
        pages = self.query('SELECT * FROM pages ORDER BY title')
        other_info = self.query("SELECT name, HEX(content) FROM mud_info WHERE name<>'news' ORDER BY name")
        # A bulk import would fail on this help entry; news must skip parsing it.
        self.index.write_text('#\n"broken"\nrejected test entry\n')
        samples = ((ROOT / 'lib/information/news').read_bytes(),
                   b'&+RNews&N\r\n\x1b[31mQuotes: \' " \\ % _\t\n'
                   b"'); DELETE FROM mud_info; --\nUTF-8: caf\xc3\xa9\n\n", b'x')
        for content in samples:
            with self.subTest(bytes=len(content)):
                self.news.write_bytes(content)
                result = self.run_import('--news-only')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(bytes.fromhex(self.query("SELECT HEX(content) FROM mud_info WHERE name='news'")),
                                 content)
                self.assertEqual(self.query('SELECT * FROM pages ORDER BY title'), pages)
                self.assertEqual(self.query("SELECT name, HEX(content) FROM mud_info WHERE name<>'news' ORDER BY name"),
                                 other_info)
                self.assertIn('Run plain page (no arguments)', result.stdout)
                self.assertNotIn('page help', result.stdout)

    def test_news_only_rolls_back_after_sql_error(self):
        before = self.snapshot()
        # Fail after REPLACE has deleted the old row and inserted the new one.
        self.query("CREATE TRIGGER reject_news AFTER INSERT ON mud_info FOR EACH ROW "
                   "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='news import rejected'")
        result = self.run_import('--news-only')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('news import rejected', result.stderr)
        self.assertIn('transaction rolled back', result.stdout)
        self.assertNotIn('Committed Atomically', result.stdout)
        self.assertNotIn('Run plain page', result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_news_only_does_not_require_pages(self):
        self.query('DROP TABLE pages')
        result = self.run_import('--news-only')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.query("SELECT content FROM mud_info WHERE name='news'"), 'new news')
        self.assertEqual(self.query('SHOW TABLES'), 'mud_info')

    def test_news_only_refuses_nontransactional_table(self):
        self.query('ALTER TABLE mud_info MODIFY name VARCHAR(128) NOT NULL, ENGINE=MyISAM')
        before = self.snapshot()
        result = self.run_import('--news-only')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires existing InnoDB', result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_rollback_and_consistent_publication(self):
        self.index.write_text('#\n"broken"\nrejected test entry\n')
        before = self.snapshot()
        failed = self.run_import('--clean', confirmation='yes\nyes\n')
        self.assertNotEqual(failed.returncode, 0, failed.stdout)
        self.assertEqual(self.snapshot(), before)

        self.index.write_text('#\n"Alias"\na new alias entry\n')
        self.query('CREATE TRIGGER slow_import BEFORE INSERT ON pages FOR EACH ROW SET @delay=SLEEP(0.4)')
        process = subprocess.Popen(['bash', str(self.script), '--clean'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        process.stdin.write('yes\nyes\n')
        process.stdin.close()
        snapshots = []
        deadline = time.monotonic() + 30
        try:
            while process.poll() is None:
                self.assertLess(time.monotonic(), deadline)
                snapshots.append(self.query('SELECT GROUP_CONCAT(title ORDER BY title) FROM pages'))
                time.sleep(0.03)
            self.assertEqual(process.returncode, 0, process.stderr.read())
            final = self.query('SELECT GROUP_CONCAT(title ORDER BY title) FROM pages')
            self.assertEqual(final, 'Alias,credits,faq,Fresh,help,wizlist')
            self.assertIn('help,sentinel', snapshots)
            self.assertTrue(set(snapshots) <= {'help,sentinel', final}, snapshots)
            self.assertEqual(self.query("SELECT content FROM mud_info WHERE name='news'"), 'new news')
            for name in ('credits', 'faq', 'wizlist'):
                self.assertEqual(self.query(f"SELECT content FROM mud_info WHERE name='{name}'"), 'new ' + name)
            self.assertIn('Run plain page (no arguments)', process.stdout.read())
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()
            process.stderr.close()
        # Refuse nontransactional destinations before staging deletes.
        self.query('DROP TRIGGER slow_import; '
                   'ALTER TABLE mud_info MODIFY name VARCHAR(128) NOT NULL, ENGINE=MyISAM')
        refused = self.run_import()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('requires existing InnoDB', refused.stdout)
        self.assertEqual(self.query('SELECT GROUP_CONCAT(title ORDER BY title) FROM pages'), final)


if __name__ == '__main__':
    unittest.main()
