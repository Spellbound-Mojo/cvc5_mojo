"""Search must include tutorial and landing pages, and CSS assets must exist."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from check_docs import audit_site, search_location


class SiteAudit(unittest.TestCase):
    def test_directory_urls(self):
        for page, url in [('index.md', ''), ('tutorials/index.md', 'tutorials/'),
                          ('tutorials/terms.md', 'tutorials/terms/')]:
            self.assertEqual(search_location(Path(page)), url)

    def test_missing_tutorial_and_css_font_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); site = root / 'site'; content = root / 'content'
            (site / 'search').mkdir(parents=True); content.mkdir()
            (content / 'tutorial.md').write_text('# A tutorial\n')
            (site / 'index.html').write_text('<h1 id="main">Title</h1>')
            index = site / 'search/search_index.json'
            index.write_text(json.dumps({'docs': []}))
            with self.assertRaisesRegex(AssertionError, 'Unindexed documentation page'):
                audit_site(site, content=content)
            index.write_text(json.dumps({'docs': [{'location': 'tutorial/'}]}))
            (site / 'style.css').write_text('body { src: url("font.woff2") }')
            with self.assertRaisesRegex(AssertionError, 'Missing CSS asset'):
                audit_site(site, content=content)
            (site / 'font.woff2').write_bytes(b'font')
            self.assertEqual(audit_site(site, content=content)['search_documents'], 1)


if __name__ == '__main__':
    unittest.main()
