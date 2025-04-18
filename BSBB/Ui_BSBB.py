# Form implementation generated from reading ui file 'UI\BSBB.ui'
#
# Created by: PyQt6 UI code generator 6.8.1
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_BSBB(object):
    def setupUi(self, BSBB):
        BSBB.setObjectName("BSBB")
        BSBB.resize(985, 501)
        self.verticalLayout = QtWidgets.QVBoxLayout(BSBB)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.setObjectName("mainLayout")
        self.topBarLayout = QtWidgets.QHBoxLayout()
        self.topBarLayout.setObjectName("topBarLayout")
        self.labelBatches = QtWidgets.QLabel(parent=BSBB)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.labelBatches.sizePolicy().hasHeightForWidth())
        self.labelBatches.setSizePolicy(sizePolicy)
        self.labelBatches.setObjectName("labelBatches")
        self.topBarLayout.addWidget(self.labelBatches)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.topBarLayout.addItem(spacerItem)
        self.addButton = QtWidgets.QPushButton(parent=BSBB)
        self.addButton.setMaximumSize(QtCore.QSize(30, 16777215))
        self.addButton.setAutoDefault(False)
        self.addButton.setObjectName("addButton")
        self.topBarLayout.addWidget(self.addButton)
        self.removeButton = QtWidgets.QPushButton(parent=BSBB)
        self.removeButton.setMaximumSize(QtCore.QSize(30, 16777215))
        self.removeButton.setAutoDefault(False)
        self.removeButton.setObjectName("removeButton")
        self.topBarLayout.addWidget(self.removeButton)
        self.mainLayout.addLayout(self.topBarLayout)
        self.buildsTable = QtWidgets.QTableWidget(parent=BSBB)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.buildsTable.sizePolicy().hasHeightForWidth())
        self.buildsTable.setSizePolicy(sizePolicy)
        self.buildsTable.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.buildsTable.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.buildsTable.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.buildsTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.buildsTable.setObjectName("buildsTable")
        self.buildsTable.setColumnCount(3)
        self.buildsTable.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.buildsTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.buildsTable.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.buildsTable.setHorizontalHeaderItem(2, item)
        self.buildsTable.horizontalHeader().setStretchLastSection(False)
        self.mainLayout.addWidget(self.buildsTable)
        self.horizontalLayout.addLayout(self.mainLayout)
        self.sideButtonsLayout = QtWidgets.QVBoxLayout()
        self.sideButtonsLayout.setObjectName("sideButtonsLayout")
        self.buildButton = QtWidgets.QPushButton(parent=BSBB)
        self.buildButton.setAutoDefault(False)
        self.buildButton.setDefault(True)
        self.buildButton.setObjectName("buildButton")
        self.sideButtonsLayout.addWidget(self.buildButton)
        self.validateButton = QtWidgets.QPushButton(parent=BSBB)
        self.validateButton.setAutoDefault(False)
        self.validateButton.setObjectName("validateButton")
        self.sideButtonsLayout.addWidget(self.validateButton)
        self.settingsButton = QtWidgets.QPushButton(parent=BSBB)
        self.settingsButton.setAutoDefault(False)
        self.settingsButton.setObjectName("settingsButton")
        self.sideButtonsLayout.addWidget(self.settingsButton)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.sideButtonsLayout.addItem(spacerItem1)
        self.upButton = QtWidgets.QPushButton(parent=BSBB)
        self.upButton.setAutoDefault(False)
        self.upButton.setObjectName("upButton")
        self.sideButtonsLayout.addWidget(self.upButton)
        self.downButton = QtWidgets.QPushButton(parent=BSBB)
        self.downButton.setAutoDefault(False)
        self.downButton.setObjectName("downButton")
        self.sideButtonsLayout.addWidget(self.downButton)
        spacerItem2 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.sideButtonsLayout.addItem(spacerItem2)
        self.applyButton = QtWidgets.QPushButton(parent=BSBB)
        self.applyButton.setEnabled(False)
        self.applyButton.setAutoDefault(False)
        self.applyButton.setObjectName("applyButton")
        self.sideButtonsLayout.addWidget(self.applyButton)
        self.cancelButton = QtWidgets.QPushButton(parent=BSBB)
        self.cancelButton.setAutoDefault(False)
        self.cancelButton.setObjectName("cancelButton")
        self.sideButtonsLayout.addWidget(self.cancelButton)
        self.horizontalLayout.addLayout(self.sideButtonsLayout)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.label = QtWidgets.QLabel(parent=BSBB)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)

        self.retranslateUi(BSBB)
        self.cancelButton.clicked.connect(BSBB.close) # type: ignore
        QtCore.QMetaObject.connectSlotsByName(BSBB)

    def retranslateUi(self, BSBB):
        _translate = QtCore.QCoreApplication.translate
        BSBB.setWindowTitle(_translate("BSBB", "BodySlide Batch Builder"))
        self.labelBatches.setText(_translate("BSBB", "Builds"))
        self.addButton.setToolTip(_translate("BSBB", "Add"))
        self.addButton.setWhatsThis(_translate("BSBB", "Create new build"))
        self.addButton.setText(_translate("BSBB", "+"))
        self.removeButton.setToolTip(_translate("BSBB", "Remove"))
        self.removeButton.setWhatsThis(_translate("BSBB", "Delete selected build"))
        self.removeButton.setText(_translate("BSBB", "-"))
        self.buildsTable.setWhatsThis(_translate("BSBB", "<html><head/><body><p>List of all builds you have. Double click any build to edit it.</p><p>Toggle checkbox to enable/disable build.</p></body></html>"))
        item = self.buildsTable.horizontalHeaderItem(0)
        item.setText(_translate("BSBB", "Output"))
        item = self.buildsTable.horizontalHeaderItem(1)
        item.setText(_translate("BSBB", "Preset"))
        item = self.buildsTable.horizontalHeaderItem(2)
        item.setText(_translate("BSBB", "Include #"))
        self.buildButton.setToolTip(_translate("BSBB", "Ctrl-Click to create BodySlide groups only"))
        self.buildButton.setWhatsThis(_translate("BSBB", "<html><head/><body><p>Runs all enabled builds in BodySlide. This will do the following things in this order:</p><ol style=\"margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-list-indent: 1;\"><li style=\" margin-top:12px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Validate all enabled builds.</li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Save config.</li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Generate BSBB BodySlide Groups based on enabled builds.</li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Delete contents of meshes folder in any enabled build\'s output mod.</li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Launch BodySlide for each build.</li></ol><p>Steps 4 &amp; 5 can be skipped by holding CTRL while clicking the button.<br/>Some parts of normal validation can be disabled in settings when running Build All.</p></body></html>"))
        self.buildButton.setText(_translate("BSBB", "Build All"))
        self.validateButton.setWhatsThis(_translate("BSBB", "<html><head/><body><p>Runs validation of all enabled builds</p></body></html>"))
        self.validateButton.setText(_translate("BSBB", "Validate All"))
        self.settingsButton.setText(_translate("BSBB", "Settings"))
        self.upButton.setWhatsThis(_translate("BSBB", "<html><head/><body><p>Change order that build are run in. Order only matters if multiple builds output to the same output mod and contain some overlapping meshes. Any overlaps will be overwritten by BodySlide on each build.</p></body></html>"))
        self.upButton.setText(_translate("BSBB", "Up"))
        self.downButton.setWhatsThis(_translate("BSBB", "<html><head/><body><p>Change order that build are run in. Order only matters if multiple builds output to the same output mod and contain some overlapping meshes. Any overlaps will be overwritten by BodySlide on each build.</p></body></html>"))
        self.downButton.setText(_translate("BSBB", "Down"))
        self.applyButton.setWhatsThis(_translate("BSBB", "Save any changes"))
        self.applyButton.setText(_translate("BSBB", "Apply"))
        self.cancelButton.setText(_translate("BSBB", "Cancel"))
        self.label.setText(_translate("BSBB", "Double click build to edit"))
