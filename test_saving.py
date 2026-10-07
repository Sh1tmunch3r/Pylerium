import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QMessageBox
import test_dynamic_builders as builders
from file_saving import write_text_atomic


class SavingTests(unittest.TestCase):
    setUp=builders.BuilderTests.setUp
    tearDown=builders.BuilderTests.tearDown

    def test_existing_plugin_copy_replace_cancel(self):
        builder=self.w.plugin_builder
        builder.new_plugin();builder.ident.setText('same');builder.name.setText('Same')
        builder.editor.setPlainText('def register(ctx):\n    pass\n')
        self.assertTrue(builder.save())
        original=(builder.folder/'plugin.py')
        for answer in (QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.No,QMessageBox.StandardButton.Yes):
            builder.dirty=False;builder.new_plugin();builder.ident.setText('same');builder.name.setText('Same')
            builder.editor.setPlainText('def register(ctx):\n    ctx.log("changed")\n')
            with patch('plugin_builder.QMessageBox.question',return_value=answer):
                result=builder.save()
            if answer==QMessageBox.StandardButton.Cancel:
                self.assertFalse(result);self.assertNotIn('changed',original.read_text())
            elif answer==QMessageBox.StandardButton.No:
                self.assertTrue(result);self.assertEqual(builder.ident.text(),'same_2')
                self.assertNotIn('changed',original.read_text())
            else:
                self.assertTrue(result);self.assertIn('changed',original.read_text())

    def test_atomic_replacement_failure_preserves_original(self):
        path=Path(self.temp.name)/'existing.py'
        path.write_text('original')
        with patch('file_saving.os.replace',side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):write_text_atomic(path,'replacement')
        self.assertEqual(path.read_text(),'original')
        self.assertEqual(list(path.parent.glob('.existing.py.*.tmp')),[])
        write_text_atomic(path,'replacement');self.assertEqual(path.read_text(),'replacement')


if __name__=='__main__':unittest.main()
