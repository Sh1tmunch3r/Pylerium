import unittest
import ast
import test_dynamic_builders as builders
from test_orchestration import APP
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest


class EditorTests(unittest.TestCase):
    setUp=builders.BuilderTests.setUp
    tearDown=builders.BuilderTests.tearDown
    def test_templates_in_focus_and_window_controls(self):
        from editor_templates import WORKSHOP_TEMPLATES
        for code in WORKSHOP_TEMPLATES.values():ast.parse(code)
        self.w.show();self.w.navigate('WORKSHOP');APP.processEvents()
        card=self.w.code_card;card.editor.clear()
        card.open_focus();APP.processEvents()
        self.assertIs(card.toolbar.parentWidget(),card.dialog)
        card.template_picker.setCurrentText('Main entry point');card.insert_template()
        ast.parse(card.editor.toPlainText())
        card.editor.undo();self.assertEqual(card.editor.toPlainText(),'')
        card.dialog.close();APP.processEvents()
        self.assertIs(card.toolbar.parentWidget(),card)
        self.w.code.setFocus();QTest.keyClick(self.w.code,Qt.Key.Key_F11);APP.processEvents()
        self.assertTrue(self.w.isFullScreen())
        QTest.keyClick(self.w.code,Qt.Key.Key_F11);APP.processEvents()
        self.assertFalse(self.w.isFullScreen())
        plugin=self.w.plugin_builder
        plugin.editor_card.open_focus();APP.processEvents()
        plugin.new_from_card('Custom UI page')
        self.assertIn("ctx.add_page",plugin.editor.toPlainText())
        plugin.editor_card.dialog.close();plugin.dirty=False
    # Reuse workspace setup/cleanup while exercising shared editor behavior.
    def test_focus_preserves_document_and_undo_for_both_editors(self):
        for card in (self.w.code_card,self.w.plugin_builder.editor_card):
            editor=card.editor
            editor.setPlainText('original')
            cursor=editor.textCursor();cursor.movePosition(cursor.MoveOperation.End);editor.setTextCursor(cursor)
            document=editor.document()
            card.open_focus();APP.processEvents()
            self.assertIs(editor.document(),document)
            QTest.keyClicks(editor,' value')
            card.dialog.close();APP.processEvents()
            self.assertIsNone(card.dialog)
            self.assertIs(editor.document(),document)
            self.assertEqual(editor.toPlainText(),'original value')
            editor.undo();self.assertEqual(editor.toPlainText(),'original')
        self.w.plugin_builder.dirty=False

    def test_completions_accept_and_suppress_comments(self):
        self.w.show();self.w.navigate('WORKSHOP');APP.processEvents()
        editor=self.w.code;editor.clear();editor.setFocus()
        QTest.keyClicks(editor,'pri');editor.suggest(manual=True);APP.processEvents()
        self.assertTrue(editor.completer.popup().isVisible())
        QTest.keyClick(editor,Qt.Key.Key_Tab)
        self.assertEqual(editor.toPlainText(),'print')
        editor.setPlainText('# pri');cursor=editor.textCursor();cursor.movePosition(cursor.MoveOperation.End);editor.setTextCursor(cursor)
        editor.suggest(manual=True);self.assertFalse(editor.completer.popup().isVisible())
        editor.setPlainText('"pri');cursor=editor.textCursor();cursor.movePosition(cursor.MoveOperation.End);editor.setTextCursor(cursor)
        editor.suggest(manual=True);self.assertFalse(editor.completer.popup().isVisible())
        editor.suggestions_enabled=False;editor.setPlainText('pri');editor.suggest(manual=True)
        self.assertFalse(editor.completer.popup().isVisible())


if __name__=='__main__':unittest.main(verbosity=2)
