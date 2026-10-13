"""Regression checks for associating upstream comments with enum members."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bindgen import enums, reference


class EnumDocumentationTests(unittest.TestCase):
    def test_comments_stay_with_members_and_preserve_numeric_collection(self):
        header = """
#define EVALUE(name) CVC5_KIND_##name
/** Description of the enum, not its first undocumented member. */
enum ENUM(Kind)
{
  EVALUE(UNDEFINED_KIND = -1),
  /**
   * Exponential function.
   *
   * - Arity: ``1``
   */
  EVALUE(EXPONENTIAL),
  /* Section boundary, not documentation. */
  /** Sine function. */
  EVALUE(SINE),
  EVALUE(UNDOCUMENTED),
};
"""
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'kind.h').write_text(header)
            with patch.object(enums, 'HEADERS', ['kind.h']):
                names = enums.collect(folder)
                docs = enums.documentation(folder)['Kind']
        self.assertEqual(names, [('Kind', 'CVC5_KIND_', [
            'UNDEFINED_KIND', 'EXPONENTIAL', 'SINE', 'UNDOCUMENTED'])])
        self.assertEqual(docs['UNDEFINED_KIND'], '')
        self.assertEqual(docs['UNDOCUMENTED'], '')
        self.assertEqual(docs['EXPONENTIAL'], 'Exponential function.\n\n- Arity: ``1``')
        self.assertEqual(docs['SINE'], 'Sine function.')

    def test_selected_summaries_use_the_existing_docstring_conversion(self):
        snap = {'enum_docs': {'Kind': {
            'SINE': 'Sine of ``x``.\n\nDetails not needed in the table.',
            'COSINE': 'Cosine function.',
        }}}
        table = reference.kinds_markdown(snap, ['COSINE', 'SINE'])
        self.assertLess(table.index('Kind.COSINE'), table.index('Kind.SINE'))
        self.assertIn('Sine of `x`.', table)
        self.assertNotIn('Details not needed', table)
        with self.assertRaises(KeyError):
            reference.kinds_markdown(snap, ['NOT_AN_UPSTREAM_KIND'])


if __name__ == '__main__':
    unittest.main()
