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
Below is a minimal example for using it::

    from PyQt4 import QtGui
    from qtest import QBGTestResult, QBGTestRunner
    
    app = QtGui.QApplication(sys.argv)
    result = QBGTestResult()
    result.show()
    suite = unittest.TestSuite(test_cases)
    display = QBGTestRunner(result)
    result = display.run(suite)
    app.exec_()
"""


import sys
import imp
import time
import inspect
import StringIO
import traceback

from multiprocessing import Queue, Process
from Queue import Empty

from PyQt4 import QtGui, QtCore
from unittest import TestResult, TestCase, TestSuite


class PseudoFile:
    def __init__(self):
        self.content = ''
    
    def write(self, data):
        self.content += data
    
    def clear(self):
        self.content = ''
    
    def flush(self):
        pass
    
    def writelines(self, lines):
        for line in lines:
            self.write(line)


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
        
        list_layout = QtGui.QHBoxLayout()
        list_layout.addWidget(self.testcases)
        list_layout.addWidget(self.selectedlist)
        
        buttons = QtGui.QDialogButtonBox()
        buttons.addButton(QtGui.QDialogButtonBox.Ok)
        buttons.addButton(QtGui.QDialogButtonBox.Cancel)
        
        self.connect(buttons, QtCore.SIGNAL('accepted()'), self,
                     QtCore.SLOT('accept()'))
        self.connect(buttons, QtCore.SIGNAL('rejected()'), self,
                     QtCore.SLOT('reject()'))
        
        main = QtGui.QVBoxLayout()
        main.addLayout(file_layout)
        main.addLayout(list_layout)
        main.addWidget(buttons)
        
        self.setLayout(main)
    
    def selectItem(self, item):
        # FIXME: This is supposed to move the item of the Qt list
        # from testcases to selectedlist and move the object from
        # objects to selected.
        indx = self.testcases.indexFromItem(item).row()
        self.testcases.removeItemWidget(item)
        self.selected.append(self.objects.pop(indx))
        self.selectedlist.addItem(item)
        self.selectedlist.scrollToBottom()
        self.testcases.scrollToBottom()
    
    def removeItem(self, item):
        # FIXME: This is supposed to move the item of the Qt list
        # from selectedlist to testcases and move the object from
        # selected to objects.
        indx = self.selectedlist.indexFromItem(item).row()
        self.selectedlist.removeItemWidget(item)
        self.objects.append(self.selected.pop(indx))
        self.testcases.addItem(item)
        self.selectedlist.scrollToBottom()
        self.testcases.scrollToBottom()
    
    def load(self):
        filename = QtGui.QFileDialog.getOpenFileNames(
            self, 'Open file', '.')
        files = map(str, list(filename))
        for f_name in files:
            mod = imp.load_source('mod', f_name)
            for n in dir(mod):
                obj = getattr(mod, n)
                if inspect.isclass(obj):
                    if issubclass(obj, TestCase):
                        item = QtGui.QListWidgetItem(
                            'TestCase: ' + obj.__name__
                        )
                        item.setToolTip(f_name)
                        self.testcases.addItem(item)
                        self.testcases.scrollToBottom()
                        self.objects.append(obj)
                    elif issubclass(obj, TestSuite):
                        item = QtGui.QListWidgetItem(
                            'TestSuite: ' + obj.__name__
                        )
                        item.setToolTip(f_name)
                        self.testcases.addItem(item)
                        self.testcases.scrollToBottom()
                        self.objects.append(obj)


class QTestView(QtGui.QWidget):
    def __init__(self, name, desc, outp, error):
        QtGui.QWidget.__init__(self)
        
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
        self.result = QTestResult()
        self.runner = QTestRunner(self.result)
        self.setCentralWidget(self.result)
        
        load = QtGui.QAction('&Open', self)
        load.setShortcut('Ctrl+O')
        load.setStatusTip('Load test cases')
        self.connect(load, QtCore.SIGNAL('triggered()'),
                     self.load_testcases)
        
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(load)
    
    def update_status(self, test):
        self.statusBar().showMessage('Running %s' % test)
    
    def load_testcases(self):
        selector = QTestLoader()
        if selector.exec_():
            self.cases = TestSuite([s() for s in selector.selected])
    

class QTestRunner:
    def __init__(self, result):
        self.result = result

    def run(self, test):
        "Run the given test case or test suite."
        self.result.setAmount(test.countTestCases() - 1)
        startTime = time.time()
        self.result.enter()
        test(self.result)
        self.result.done()
        stopTime = time.time()
        timeTaken = stopTime - startTime
        run = self.result.testsRun
        return self.result


class QTestResult(TestResult, QtGui.QWidget):
    def __init__(self, status=None, descriptions=True):
        TestResult.__init__(self)
        QtGui.QWidget.__init__(self)
        
        self.status = status
        self.descriptions = descriptions
        self.pseudo_file = PseudoFile()
                
        self.progress = QtGui.QProgressBar(self)
        
        self.success = QtGui.QListWidget(self)
        self.fail = QtGui.QListWidget(self)
        self.error = QtGui.QListWidget(self)
        
        self.success_data = []
        self.fail_data = []
        self.error_data = []
        
        self.views = []
        
        left = QtGui.QVBoxLayout()
        left.addWidget(self.progress)
        left.addWidget(QtGui.QLabel('Passed Tests:'))
        left.addWidget(self.success)
        
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
    
    def setAmount(self, amount):
        self.progress.setRange(0, amount)
    
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

    def getDescription(self, test):
        if self.descriptions:
            return test.shortDescription() or str(test)
        else:
            return str(test)

    def startTest(self, test):
        self.pseudo_file.clear()
        TestResult.startTest(self, test)
        self.progress.setValue(self.progress.value() + 1)
        if self.status is not None:
            self.status(str(test))

    def addSuccess(self, test):
        TestResult.addSuccess(self, test)
        item = QtGui.QListWidgetItem(str(test))
        if self.pseudo_file.content:
            item.setToolTip(self.pseudo_file.content)
        self.success_data.append(
            (str(test), test.shortDescription(), self.pseudo_file.content, '')
        )
        self.success.addItem(item)
        self.success.scrollToBottom()

    def addError(self, test, err):
        tb = ''.join(traceback.format_exception(*err))
        TestResult.addError(self, test, err)
        item = QtGui.QListWidgetItem(str(test))
        item.setToolTip(tb)
        self.error_data.append(
            (str(test), test.shortDescription(), self.pseudo_file.content, tb)
        )
        self.error.addItem(item)
        self.error.scrollToBottom()

    def addFailure(self, test, err):
        tb = ''.join(traceback.format_exception(*err))
        TestResult.addFailure(self, test, err)
        item = QtGui.QListWidgetItem(str(test))
        item.setToolTip(tb)
        self.fail_data.append(
            (str(test), test.shortDescription(), self.pseudo_file.content, tb)
        )
        self.fail.addItem(item)
        self.fail.scrollToBottom()
    
    def enter(self):
        sys.stdout = sys.stderr = PseudoFile()
    
    def done(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


class QBGTestResult(QTestResult):
    def __init__(self, status=None, descriptions=True):
        QTestResult.__init__(self, status, descriptions)
        self.translate = {
            'success': self.addSuccess,'failure': self.addFailure,
            'error': self.addError, 'start': self.startTest
        }
    
    def startTest(self, test_name, test_descr):
        self.progress.setValue(self.progress.value() + 1)
        if self.status is not None:
            self.status(test_name)
    
    def addSuccess(self, test_name, test_descr, outp):
        item = QtGui.QListWidgetItem(test_name)
        if outp:
            item.setToolTip(outp)
        self.success_data.append(
            (test_name, test_descr, outp, '')
        )
        self.success.addItem(item)
        self.success.scrollToBottom()
    
    def addFailure(self, test_name, test_descr, tb, outp):
        item = QtGui.QListWidgetItem(test_name)
        if outp:
            item.setToolTip(outp)
        self.fail_data.append(
            (test_name, test_descr, outp, tb)
        )
        self.fail.addItem(item)
        self.fail.scrollToBottom()
    
    def addError(self, test_name, test_descr, tb, outp):
        item = QtGui.QListWidgetItem(test_name)
        if outp:
            item.setToolTip(outp)
        self.error_data.append(
            (test_name, test_descr, outp, tb)
        )
        self.error.addItem(item)
        self.error.scrollToBottom()


class BGTestResult(TestResult):
    def __init__(self, queue, pseudo_file):
        TestResult.__init__(self)
        self.queue = queue
        self.pseudo_file = pseudo_file
    
    def setAmount(self, amount):
        self.queue.put(("amount", [amount]))
    
    def startTest(self, test):
        self.clearOutput()
        test_name = str(test)
        test_descr = test.shortDescription()
        self.queue.put(("start", [test_name, test_descr]))
    
    def addSuccess(self, test):
        test_name = str(test)
        test_descr = test.shortDescription()
        self.queue.put(("success", [test_name, test_descr, self.getOutput()]))
    
    def addError(self, test, err):
        test_name = str(test)
        test_descr = test.shortDescription()
        tb = ''.join(traceback.format_exception(*err))
        self.queue.put(("error", [test_name, test_descr, tb, self.getOutput()]))
    
    def addFailure(self, test, err):
        test_name = str(test)
        test_descr = test.shortDescription()
        tb = ''.join(traceback.format_exception(*err))
        self.queue.put(("failure", [test_name, test_descr, tb, self.getOutput()]))
    
    def getOutput(self):
        return self.pseudo_file.getvalue()
    
    def clearOutput(self):
        self.pseudo_file.truncate()


class QBGTestRunner:
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
        self.result.setAmount(test.countTestCases() - 1)
        self.proc = Process(target=self.bg_process, args=(test, self.q))
        self.proc.start()
        self.timer.start()
    
    def tick(self):
        c = True
        while c:
            try:
                data = self.q.get_nowait()
                if not data:
                    self.timer.stop()
                    self.done = True
                    c = False
                key, args = data
                self.result.translate[key](*args)
            except Empty:
                c = False
    
    @staticmethod
    def bg_process(suite, q):
        pseudo_file = StringIO.StringIO()
        sys.stdout = sys.stderr = pseudo_file
        result = BGTestResult(q, pseudo_file)
        suite(result)
        q.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    
    def stop(self):
        self.timer.stop()
        self.proc.terminate()


def main():
    app = QtGui.QApplication(sys.argv)
    test = QTestWindow()
    test.show()
    app.exec_()


if __name__ == "__main__":
    main()
