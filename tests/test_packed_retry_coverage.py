import unittest

from scripts.v14_continue_audit import retry_fields


class PackedRetryCoverageTest(unittest.TestCase):
    def test_each_scheduler_task_covers_all_its_registered_fields(self):
        rows=[dict(field='a',array_task_index='0'),dict(field='b',array_task_index='0'),
              dict(field='c',array_task_index='1')]
        self.assertEqual(retry_fields(rows,0),[dict(id='a'),dict(id='b')])
        self.assertEqual(retry_fields(rows,1),[dict(id='c')])
        with self.assertRaises(ValueError):retry_fields(rows,2)

    def test_original_single_field_retry_mapping_is_preserved(self):
        self.assertEqual(retry_fields([dict(field='a'),dict(field='b')],1),[dict(id='b')])


if __name__=='__main__':unittest.main()
