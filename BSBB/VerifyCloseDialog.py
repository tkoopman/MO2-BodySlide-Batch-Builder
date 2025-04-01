# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

from abc import abstractmethod
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QWidget

class MyCloseEvent:
    @abstractmethod
    def closeEvent(self, closeEvent: QCloseEvent):
        pass

class VerifyCloseDialog(QDialog, QWidget):
    def __init__(self, parent: QWidget, myCloseEvent: MyCloseEvent) -> None:
        super().__init__(parent)
        self.__myCloseEvent = myCloseEvent

    def closeEvent(self, closeEvent: QCloseEvent):
        self.__myCloseEvent.closeEvent(closeEvent)