# -*- coding: us-ascii -*-

# qtest - unittest UI using PyQt
# Copyright (C) 2008 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
QTest is a graphical user interface to the unittest testing framework.
Below is a minimal working example for using it::

    from PyQt4 import QtGui
    import qtest
    import unittest
    import sys

    class ExampleTestCase(unittest.TestCase):
        def testDummy(self):
            self.assertEquals(2+2, 4)
        def testWillFail(self):
            self.assertEquals(2*2, 5)
        def testWillError(self):
            self.assertEquals(2+'2',5)
        
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.
                    loadTestsFromTestCase(ExampleTestCase))

    app = QtGui.QApplication(sys.argv)
    window = qtest.QTestWindow()
    window.show()
    display = qtest.QTestRunner(window.result)
    qtest.call_init(lambda: display.run(suite))
    app.exec_()

QTest also has function mimicing unittest.main::

    import unittest
    import qtest
    
    class SomeTest(unittest.TestCase):
        def test_foo(self):
            " This is the description. "
            print 'You should see this in the UI'
            self.assertEquals(1, 2)
    
    if __name__ == '__main__':
        qtest.main()

Additionally, if you run this file directly, you will be able to select
the TestCases you want to run using File->Open, then open files and
double click the TestCases you want to run, or press "Select All" to
select all. Run them using File->Run afterwards.

Please note that if you open new TestCases after having opened others the
same way before, only the new ones will be run.

Test that appear italics in the list have output which can be viewed in the
detailed view(double click). For tests with errors or failed tests the
traceback is shown in the detailed view too.
"""


import os
import sys
import imp
import time
import types
import inspect
import StringIO
import traceback

from multiprocessing import Queue, Process
from Queue import Empty

from PyQt4 import QtGui, QtCore
from unittest import TestResult, TestCase, TestSuite, TestProgram, TestLoader

COLORED_PROGRESS = True

BLUE_COLOR = '#6699FF'
RED_COLOR = '#ff471a'
GREEN_COLOR = '#b3ff66'

timers = []

def call_init(fun):
    timer = QtCore.QTimer()
    def func():
        fun()
        timers.remove(timer)
    timer.singleShot(0, func)
    timers.append(timer)


class QExceptionDialog(QtGui.QDialog):
    def __init__(self, msg, title=None):
        QtGui.QDialog.__init__(self)
        
        buttons = QtGui.QDialogButtonBox()
        buttons.addButton(QtGui.QDialogButtonBox.Ok)
        
        self.connect(buttons, QtCore.SIGNAL('accepted()'), self,
                     QtCore.SLOT('accept()'))
        
        main = QtGui.QVBoxLayout()
        if title is not None:
            main.addWidget(QtGui.QLabel(title))
        entry = QtGui.QTextEdit(msg)
        entry.setReadOnly(True)
        main.addWidget(entry)
        main.addWidget(buttons)
        
        self.setLayout(main)


class QTestLoader(QtGui.QDialog):
    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.setModal(True)
        
        self.objects = []
        self.selected = []
        
        self.file_line = QtGui.QLineEdit()
        self.file_button = QtGui.QPushButton("Open...")
        
        self.connect(self.file_button, QtCore.SIGNAL('clicked()'), self.load)
        
        self.testcases = QtGui.QListWidget()
        self.selectedlist = QtGui.QListWidget()
        
        self.connect(
            self.testcases,
            QtCore.SIGNAL("itemDoubleClicked ( QListWidgetItem * )"),
            self.selectItem
        )
        self.connect(
            self.selectedlist,
            QtCore.SIGNAL("itemDoubleClicked ( QListWidgetItem * )"),
            self.removeItem
        )
        
        file_layout = QtGui.QHBoxLayout()
        file_layout.addWidget(self.file_line, 5)
        file_layout.addWidget(self.file_button, 1)
        
        first_col = QtGui.QVBoxLayout()
        first_col.addWidget(QtGui.QLabel('Available:'))
        first_col.addWidget(self.testcases)
        
        sec_col = QtGui.QVBoxLayout()
        sec_col.addWidget(QtGui.QLabel('Selected:'))
        sec_col.addWidget(self.selectedlist)
        
        list_layout = QtGui.QHBoxLayout()        
        list_layout.addLayout(first_col)
        list_layout.addLayout(sec_col)
        
        select_all = QtGui.QPushButton('Select All')
        
        self.connect(select_all, QtCore.SIGNAL('clicked()'),
                     self.selectAll)
        
        buttons = QtGui.QDialogButtonBox()
        buttons.addButton(QtGui.QDialogButtonBox.Ok)
        buttons.addButton(QtGui.QDialogButtonBox.Cancel)
        
        self.connect(buttons, QtCore.SIGNAL('accepted()'), self,
                     QtCore.SLOT('accept()'))
        self.connect(buttons, QtCore.SIGNAL('rejected()'), self,
                     QtCore.SLOT('reject()'))
        
        button_lay = QtGui.QHBoxLayout()
        button_lay.addWidget(select_all)
        button_lay.addWidget(buttons)
        
        main = QtGui.QVBoxLayout()
        main.addLayout(file_layout)
        main.addLayout(list_layout)
        main.addLayout(button_lay)
        
        self.setLayout(main)
    
    def selectAll(self):
        items = []
        for i in xrange(self.testcases.count()):
            items.append(self.testcases.item(0))
            self.selected.append(self.objects.pop(0))
            self.testcases.takeItem(0)
        for item in items:
            self.selectedlist.addItem(item)
    
    def selectItem(self, item):
        indx = self.testcases.indexFromItem(item).row()
        self.testcases.takeItem(indx)
        self.selected.append(self.objects.pop(indx))
        self.selectedlist.addItem(item)
        self.selectedlist.scrollToBottom()
        self.testcases.scrollToBottom()
    
    def removeItem(self, item):
        indx = self.selectedlist.indexFromItem(item).row()
        self.selectedlist.takeItem(indx)
        self.objects.append(self.selected.pop(indx))
        self.testcases.addItem(item)
        self.selectedlist.scrollToBottom()
        self.testcases.scrollToBottom()
    
    def load(self):
        filename = QtGui.QFileDialog.getOpenFileNames(
            self, 'Open file', '.', "Python Source (*.py)")
        files = map(str, list(filename))
        for f_name in files:
            mod_name = os.path.splitext(os.path.split(f_name)[1])[0]
            try:
                mod = imp.load_source(mod_name, f_name)
            except:
                tb = ''.join(traceback.format_exception(*sys.exc_info()))
                msg = QExceptionDialog(
                    tb, 'An exception occured while importing the module'
                )
                msg.exec_()
                continue
            for n in dir(mod):
                obj = getattr(mod, n)
                if inspect.isclass(obj):
                    if issubclass(obj, TestCase):
                        item = QtGui.QListWidgetItem(obj.__name__)
                        item.setToolTip(f_name)
                        self.testcases.addItem(item)
                        self.testcases.scrollToBottom()
                        self.objects.append(obj)


class QTestView(QtGui.QWidget):
    def __init__(self, name, desc, outp, error):
        QtGui.QWidget.__init__(self)
        
        self.setWindowTitle("QTest - %s" % name)
        
        self.name = QtGui.QLineEdit(name)
        self.name.setReadOnly(True)
        
        self.desc = QtGui.QLineEdit(desc)
        self.name.setReadOnly(True)
        
        self.outp = QtGui.QTextEdit(self)
        for line in outp.splitlines():
            self.outp.append(line)
        self.outp.setReadOnly(True)
        
        self.error = QtGui.QTextEdit(error, self)
        for line in error.splitlines():
            self.error.append(line)
        self.error.setReadOnly(True)        
        
        first_line = QtGui.QHBoxLayout()
        second_line = QtGui.QHBoxLayout()
        
        first_line.addWidget(QtGui.QLabel('Name:'))
        first_line.addWidget(self.name)
        second_line.addWidget(QtGui.QLabel('Description:'))
        second_line.addWidget(self.desc)
        
        main = QtGui.QVBoxLayout()
        main.addLayout(first_line)
        main.addLayout(second_line)
        main.addWidget(QtGui.QLabel(''))
        main.addWidget(QtGui.QLabel('Test Output:'))
        main.addWidget(self.outp)
        main.addWidget(QtGui.QLabel('Traceback:'))
        main.addWidget(self.error)
    
        self.setLayout(main)


class QTestWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        self.setWindowTitle("QTest")
        
        self.cases = []
        self.result = QTestResult(self.updateStatus, self.indicateSuccess,
                                  self.indicateFailure, self.reset)
        self.runner = QTestRunner(self.result)
        self.setCentralWidget(self.result)
        
        load = QtGui.QAction('&Open', self)
        load.setShortcut('Ctrl+O')
        load.setStatusTip('Load test cases')
        self.connect(load, QtCore.SIGNAL('triggered()'),
                     self.loadTestCases)
        
        run = QtGui.QAction('&Run', self)
        run.setStatusTip('Run test cases')
        self.connect(run, QtCore.SIGNAL('triggered()'),
                     self.runTestCases)
        
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(load)
        file_menu.addAction(run)
        self.statusBar().showMessage('')
    
    def reset(self):
        self.statusBar().showMessage('')
        self.statusBar().setStyleSheet('')
    
    def indicateSuccess(self):
        # self.colorStatusBar('#B2FF7F')
        total = self.result.n_success
        self.statusBar().showMessage("Ran %d tests. OK" % total)
    
    def indicateFailure(self):
        # self.colorStatusBar('#FFB2B2')
        res = self.result
        total = res.n_success + res.n_fail + res.n_error
        self.statusBar().showMessage(
            "Ran %d tests. %d failed, %d errors." % 
            (total, res.n_fail, res.n_error)
        )
    
    def colorStatusBar(self, color):
        self.statusBar().setStyleSheet("QStatusBar {\n"
         "background: %s;\n"
         "}" % color)
    
    def updateStatus(self, test):
        self.statusBar().showMessage(test)
    
    def loadTestCases(self):
        loader = TestLoader()
        selector = QTestLoader()
        if selector.exec_():
            self.cases[:] = []
            for case in selector.selected:
                self.cases.extend(loader.loadTestsFromTestCase(case))
    
    def runTestCases(self):
        if not self.cases:
            self.statusBar().showMessage('No TestCases selected.')
        else:
            suite = TestSuite(self.cases)
            self.runner.run(suite)


class QTestResult(QtGui.QWidget, TestResult):
    def __init__(self, status=None, on_success=None, on_failure=None,
                 reset=None):
        TestResult.__init__(self)
        QtGui.QWidget.__init__(self)
        
        self.status = status
        self.on_success = on_success
        self.on_failure = on_failure
        self.reset = reset
        
        self.progress = QtGui.QProgressBar(self)
        if COLORED_PROGRESS:
            self.setProgressColor(BLUE_COLOR)
        
        self.success = QtGui.QListWidget(self)
        self.fail = QtGui.QListWidget(self)
        self.error = QtGui.QListWidget(self)
        
        self.success_data = []
        self.fail_data = []
        self.error_data = []
        
        self.views = []
        
        self.n_success = 0
        self.n_fail = 0
        self.n_error = 0
        
        left = QtGui.QVBoxLayout()
        left.addWidget(QtGui.QLabel('Passed Tests:'))
        left.addWidget(self.success)
        left.addWidget(self.progress)
        
        right = QtGui.QVBoxLayout()
        right.addWidget(QtGui.QLabel('Tests with Errors:'))
        right.addWidget(self.error)
        right.addWidget(QtGui.QLabel('Failed Tests:'))
        right.addWidget(self.fail)
        
        main = QtGui.QHBoxLayout()
        main.addLayout(left)
        main.addLayout(right)
        
        self.setLayout(main)
        
        self.connect(
            self.success,
            QtCore.SIGNAL("itemDoubleClicked ( QListWidgetItem * )"),
            self.successItemDoubleClicked
        )
        self.connect(
            self.fail,
            QtCore.SIGNAL("itemDoubleClicked ( QListWidgetItem * )"),
            self.failureItemDoubleClicked
        )
        self.connect(
            self.error,
            QtCore.SIGNAL("itemDoubleClicked ( QListWidgetItem * )"),
            self.errorItemDoubleClicked
        )
        
        self.translate = {
            'success': self.addSuccess,'failure': self.addFailure,
            'error': self.addError, 'start': self.startTest,
        }
    
    def setProgressColor(self, color):
        self.progress.setStyleSheet(""" QProgressBar {
     border: 2px solid grey;
     border-radius: 5px;
     text-align: center;
 }
QProgressBar::chunk {
     background-color: %s;
     width: 1px;
}""" % color)
    
    def setAmount(self, amount):
        self.progress.setValue(0)
        self.progress.setMaximum(amount)
        self.progress.setMinimum(0)
    
    def successItemDoubleClicked(self, item):
        indx = self.success.indexFromItem(item).row()
        view = QTestView(*self.success_data[indx])
        view.show()
        self.views.append(view)

    def errorItemDoubleClicked(self, item):
        indx = self.error.indexFromItem(item).row()
        view = QTestView(*self.error_data[indx])
        view.show()
        self.views.append(view)

    def failureItemDoubleClicked(self, item):
        indx = self.fail.indexFromItem(item).row()
        view = QTestView(*self.fail_data[indx])
        view.show()
        self.views.append(view)
    
    def startTest(self, test_name, test_descr):
        self.progress.setValue(self.progress.value() + 1)
        if self.status is not None:
            self.status('Running Test %s.' % test_name)
    
    def addSuccess(self, test_name, test_descr, outp):
        self.n_success += 1
        item = QtGui.QListWidgetItem(test_name)
        if test_descr:
            item.setToolTip(test_descr)
        self.success_data.append(
            (test_name, test_descr, outp, '')
        )
        font = QtGui.QFont()
        if outp:
            font.setItalic(True)
        item.setFont(font)
        self.success.addItem(item)
        self.success.scrollToBottom()
    
    def addFailure(self, test_name, test_descr, tb, outp):
        self.n_fail += 1
        item = QtGui.QListWidgetItem(test_name)
        if test_descr:
            item.setToolTip(test_descr)
        self.fail_data.append(
            (test_name, test_descr, outp, tb)
        )
        font = QtGui.QFont()
        if outp:
            font.setItalic(True)
        item.setFont(font)
        self.fail.addItem(item)
        self.fail.scrollToBottom()
    
    def addError(self, test_name, test_descr, tb, outp):
        self.n_error = 0
        item = QtGui.QListWidgetItem(test_name)
        if test_descr:
            item.setToolTip(test_descr)
        self.error_data.append(
            (test_name, test_descr, outp, tb)
        )
        font = QtGui.QFont()
        if outp:
            font.setItalic(True)
        item.setFont(font)
        self.error.addItem(item)
        self.error.scrollToBottom()
    
    def enter(self):
        if self.reset is not None:
            self.reset()
        
        if COLORED_PROGRESS:
            self.setProgressColor(BLUE_COLOR)
        self.success.clear()
        self.fail.clear()
        self.error.clear()
        
        self.success_data[:] = []
        self.fail_data[:] = []
        self.error_data[:] = []
        
        self.n_success = 0
        self.n_fail = 0
        self.n_error = 0
    
    def done(self):
        ok = not (self.n_error or self.n_fail)
        if ok:
            if COLORED_PROGRESS:
                self.setProgressColor(GREEN_COLOR)
            if self.on_success is not None:
                self.on_success()
        else:
            if COLORED_PROGRESS:
                self.setProgressColor(RED_COLOR)
            if self.on_failure is not None:
                self.on_failure()
    


class BGTestResult(TestResult):
    def __init__(self, queue, pseudo_file):
        TestResult.__init__(self)
        self.queue = queue
        self.pseudo_file = pseudo_file
    
    def startTest(self, test):
        self.clearOutput()
        test_name = str(test)
        test_descr = test.shortDescription()
        self.queue.put(("start", [test_name, test_descr]))
    
    def addSuccess(self, test):
        test_name = str(test)
        test_descr = test.shortDescription()
        self.queue.put(
            ("success", [test_name, test_descr, self.getOutput()])
        )
    
    def addError(self, test, err):
        test_name = str(test)
        test_descr = test.shortDescription()
        tb = ''.join(traceback.format_exception(*err))
        self.queue.put(
            ("error", [test_name, test_descr, tb, self.getOutput()])
        )
    
    def addFailure(self, test, err):
        test_name = str(test)
        test_descr = test.shortDescription()
        tb = ''.join(traceback.format_exception(*err))
        self.queue.put(
            ("failure", [test_name, test_descr, tb, self.getOutput()])
        )
    
    def getOutput(self):
        return self.pseudo_file.getvalue()
    
    def clearOutput(self):
        self.pseudo_file.truncate()


class QTestRunner:
    def __init__(self, result):
        self.result = result
        self.done = False
        self.timer = QtCore.QTimer()
        self.timer.connect(self.timer, 
                   QtCore.SIGNAL('timeout()'),
                   self.tick
                   )
        self.timer.setInterval(500)
    
    def run(self, test):
        self.done = False
        self.q = Queue()
        self.result.setAmount(test.countTestCases())
        self.result.enter()
        self.proc = Process(target=self.bgProcess, args=(test, self.q))
        self.proc.start()
        self.timer.start()
    
    def tick(self):
        c = True
        while c:
            try:
                data = self.q.get_nowait()
                if not data or data == 'END':
                    self.timer.stop()
                    self.done = True
                    self.result.done()
                    c = False
                else:
                    key, args = data
                    self.result.translate[key](*args)
            except Empty:
                c = False
    
    @staticmethod
    def bgProcess(suite, q):
        pseudo_file = StringIO.StringIO()
        sys.stdout = sys.stderr = pseudo_file
        result = BGTestResult(q, pseudo_file)
        suite(result)
        q.put('END')
        q.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    
    def stop(self):
        self.timer.stop()
        self.proc.terminate()


class QTestProgram(TestProgram):
    def runTests(self):
        if isinstance(self.testRunner, (type, types.ClassType)):
            try:
                testRunner = self.testRunner(verbosity=self.verbosity)
            except TypeError:
                # didn't accept the verbosity argument
                testRunner = self.testRunner()
        else:
            # it is assumed to be a TestRunner instance
            testRunner = self.testRunner
        testRunner.run(self.test)


def main():
    app = QtGui.QApplication(sys.argv)
    win = QTestWindow()
    result = win.result
    runner = QTestRunner(result)
    win.show()
    call_init(lambda: QTestProgram(testRunner=runner))
    app.exec_()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    win = QTestWindow()
    win.show()
    app.exec_()
