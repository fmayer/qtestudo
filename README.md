# qtestudo
Graphical User Interface for the unittest framework. Formerly known as "qtest".
## Example
```python
from PyQt4 import QtGui
import qtestudo
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
window = qtestudo.QTestWindow()
window.show()
display = qtestudo.QTestRunner(window.result)
qtestudo.call_init(lambda: display.run(suite))
app.exec_()
```

qtestudo also has function mimicing unittest.main:
```python
import unittest
import qtestudo

class SomeTest(unittest.TestCase):
    def test_foo(self):
        " This is the description. "
        print 'You should see this in the UI'
        self.assertEquals(1, 2)

if __name__ == '__main__':
    qtestudo.main()
```

Additionally, if you run this file directly, you will be able to select
the TestCases you want to run using File->Open, then open files and
double click the TestCases you want to run, or press "Select All" to
select all. Run them using File->Run afterwards.
Please note that if you open new TestCases after having opened others the
same way before, only the new ones will be run.
Test that appear italics in the list have output which can be viewed in the
detailed view (double click). For tests with errors or failed tests the
traceback is shown in the detailed view too.
