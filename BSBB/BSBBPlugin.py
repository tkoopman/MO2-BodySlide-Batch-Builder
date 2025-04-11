# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

import logging
from operator import methodcaller
import re
import shutil
import os
import subprocess
import sys
import mobase  # type: ignore

from pathlib import PureWindowsPath
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QByteArray, QItemSelectionModel, QSettings, Qt
from PyQt6.QtWidgets import QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMessageBox, QTableWidgetItem, QTreeWidgetItem, QWidget, QFileDialog

from BSBB import Config
from .BodySlide import MO2BodySlide, SliderSet, CaseInsensitive
from .Ui_BSBB import Ui_BSBB
from .Ui_EditBuild import Ui_EditBuild
from .Ui_Problems import Ui_Problems
from .Ui_Settings import Ui_Settings
from .VerifyCloseDialog import VerifyCloseDialog, MyCloseEvent

_UI_EDITBUILD_TREE_COL_ICON = 0
_UI_EDITBUILD_TREE_COL_NAME = 1
_UI_EDITBUILD_TREE_COL_TYPE = 2
_UI_EDITBUILD_TREE_COL_USE = 3


class BSBBPlugin(mobase.IPluginTool, MyCloseEvent):

    def __init__(self) -> None:
        super().__init__()
        self.__unsaved_changes = False
        self.__Source_Validator = re.compile(r'^[^\\\/]+\.(xml|osp)$', re.RegexFlag.IGNORECASE)

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self.__organizer = organizer
        return True

    def name(self) -> str:
        return "BSBB"

    def author(self) -> str:
        return "GoriRed"

    def displayName(self) -> str:
        return "BodySlide Batch Builder"

    def description(self) -> str:
        return f'Run BodySlide build for each configured build that includes different Groups, Preset, Output Mod combinations.'

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 1, 0)

    def isActive(self) -> mobase.MoVariant:
        return self.__organizer.pluginSetting(self.name(), "enabled")

    def tooltip(self) -> str:
        return "Run BodySlider Batch Builder"

    def settings(self) -> list[mobase.PluginSetting]:
        return [mobase.PluginSetting("enabled", "Enable this plugin", True)]

    def icon(self) -> QtGui.QIcon:
        return QtGui.QIcon()

    def setParentWidget(self, parent: QWidget) -> None:
        self.__parentWidget = parent

    #
    # General stuff
    #

    def __loadConfig(self):
        self.__unsaved_changes = False
        file_path = os.path.join(self.__organizer.getPluginDataPath(),
                                 'bsbb_config.xml')
        self.config, self.builds = Config.loadConfig(file_path)
        self.uiconfig = QSettings(os.path.join(self.__organizer.getPluginDataPath(), 'bsbb_config.ini'), QSettings.Format.IniFormat)

    def __saveConfig(self):
        file_path = os.path.join(self.__organizer.getPluginDataPath(),
                                 'bsbb_config.xml')
        Config.saveConfig(self.config, self.builds, file_path)
        
        self.__unsaved_changes = False
        self.Ui_BSBB.applyButton.setEnabled(False)

    def exportBodySlideSetDetails(self) -> None:
        fileName = QFileDialog.getSaveFileName(self.__parentWidget,
                                               "Export To",
                                               filter="Text Files (*.txt)")[0]
        if fileName == "":
            return

        with open(fileName, "w") as f:
            self.BodySlide.print_all_slider_set_details(file=f)

    def __comboboxMatchStyle(self, combobox: QComboBox):
        index = combobox.currentIndex()
        model = combobox.model()
        if not isinstance(model, QtGui.QStandardItemModel):
            raise AttributeError(type(model))

        fgColor = model.item(index).foreground().color().name()  # type: ignore
        style = ''

        if fgColor != '#000000':
            style += f"QComboBox {{color: {fgColor}}};"

        combobox.setStyleSheet(style) 

    def __validateBuilds(self, *,
                         build: Config.Build | None = None,
                         auto: bool = False,
                         checkConflicts: bool = True,
                         checkIgnored: bool = True) -> bool:
        force = build is not None
        builds = [build] if isinstance(build, Config.Build) else self.builds

        allConflicts = dict[Config.Build, dict[str, list[SliderSet]]]()
        meshOutputs = set[str]()
        missingOutputs = list[Config.Output]()
        
        xmlOutput = self.__organizer.modList().getMod(self.config.output)
        xmlOutputDisabled = None

        if not xmlOutput:
            missingOutputs.append(self.config)
        else:
            xmlOutputDisabled = not (xmlOutput.isOverwrite() or (mobase.ModState.ACTIVE.value & self.__organizer.modList().state(xmlOutput.name())) == mobase.ModState.ACTIVE.value) # type: ignore


        enabledBuilds = [build for build in builds if force or build.enable]

        if not enabledBuilds:
            self.__displayMessage(QMessageBox.Icon.Critical,
                                  title='Error',
                                  text='No enabled builds!')
            return False

        for build in enabledBuilds:
            if not self.__organizer.modList().getMod(build.output):
                missingOutputs.append(build)

            sliderSets = self.BodySlide.get_slider_sets_filtered_by_output(
                build.include, priorities=self.config.priorities)
            conflicts = dict[str, list[SliderSet]]()

            for output in sliderSets:
                meshOutputs.add(output)
                if checkConflicts and len(sliderSets[output]) > 1:
                    conflicts[output] = sliderSets[output]

            if len(conflicts) > 0:
                allConflicts[build] = conflicts

        setsByOutput = self.BodySlide.SliderSetsByOutput(
        ) if checkIgnored else None
        ignored = [
            output for output in setsByOutput.keys() if output not in meshOutputs
        ] if setsByOutput else None

        if not xmlOutputDisabled and len(missingOutputs) == 0 and len(allConflicts) == 0 and (not ignored or len(ignored) == 0):
            if not auto:
                self.__displayMessage(QMessageBox.Icon.Information,
                                      title='Builds validated' if len(builds)
                                      > 1 else 'Build validated',
                                      text='No problems found')
            return True

        # Display Problems Window

        self.Ui_Problems_Dialog = QDialog()
        self.Ui_Problems = Ui_Problems()
        self.Ui_Problems.setupUi(self.Ui_Problems_Dialog)
        
        if not auto:
            self.Ui_Problems.buttonBox.setStandardButtons(
                QDialogButtonBox.StandardButton.Close)

        tree = self.Ui_Problems.treeWidget
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # type: ignore
        tree.setColumnHidden(2, not self.config.showSources)

        # Hidden column for storing indexes
        tree.setColumnCount(4)
        tree.setColumnHidden(3, True)

        if xmlOutputDisabled:
            self.Ui_Problems.listWidget.addItem(f"Output mod set in settings must be enabled. Output mod defined: {self.config.output}")

        for missingOutput in set([output.output for output in missingOutputs]):
            self.Ui_Problems.listWidget.addItem(f"Missing output mod {missingOutput}")

        for build, conflicts in allConflicts.items():
            buildIndex = self.builds.index(build) if build in self.builds else -1
            conflictItem = QTreeWidgetItem(
                [build.preset, build.includeAsStr(), None, str(buildIndex)])
            tree.addTopLevelItem(conflictItem)
            conflictItem.setExpanded(True)
            for output, sliderSets in conflicts.items():
                outputItem = QTreeWidgetItem([f"{output} ({len(sliderSets)})"])
                conflictItem.addChild(outputItem)
                outputItem.setFirstColumnSpanned(True)
                for sliderSet in sliderSets:
                    nameItem = QTreeWidgetItem([
                        sliderSet.name, sliderSet.groupsAsStr(self.BodySlide.sliderGroups if self.config.showSources else None),
                        sliderSet.source
                    ])

                    nameItem.setCheckState(0, Qt.CheckState.Unchecked)

                    outputItem.addChild(nameItem)

        if setsByOutput and ignored and len(ignored) > 0:
            conflictItem = QTreeWidgetItem(['Ignored Slider Sets'])
            tree.addTopLevelItem(conflictItem)
            for output in ignored:
                sliderSets = setsByOutput[output]
                outputItem = QTreeWidgetItem([f"{output} ({len(sliderSets)})"])
                conflictItem.addChild(outputItem)
                outputItem.setFirstColumnSpanned(True)
                for sliderSet in sliderSets:
                    nameItem = QTreeWidgetItem([
                        sliderSet.name, ','.join(sliderSet.groups),
                        sliderSet.source
                    ])
                    outputItem.addChild(nameItem)

        self.Ui_Problems.treeWidget.itemChanged.connect(self.__Ui_Problems_ItemChanged)
        self.Ui_Problems.errors_GroupBox.setHidden(self.Ui_Problems.listWidget.count() == 0)
        self.Ui_Problems.conflicts_GroupBox.setHidden(self.Ui_Problems.treeWidget.topLevelItemCount() == 0)

        tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.Ui_Problems_Dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
        self.Ui_Problems.addButton.clicked.connect(self.__Ui_Problems_Add)

        result = self.Ui_Problems_Dialog.exec()

        if result == QDialog.DialogCode.Rejected:
            return False

        # Add checked to builds include list
        if result == 3:
            build = None
            for t in range(self.Ui_Problems.treeWidget.topLevelItemCount()):
                top = self.Ui_Problems.treeWidget.topLevelItem(t)
                if top:
                    if self.Ui_EditBuild is None:
                        buildIndex = top.text(3)
                        build = self.builds[int(buildIndex)]
                    for o in reversed(range(top.childCount())):
                        output = top.child(o)
                        if output:
                            for c in range(output.childCount()):
                                conflict = output.child(c)
                                if conflict:
                                    if conflict.checkState(0) == Qt.CheckState.Checked:
                                        if build: # Not None would mean not currently editing a build
                                            build.include.insert(0, Config.IncludeItem(Config.IncludeType.SLIDERSET, conflict.text(0), Config.IncludeUse.IncludeKeep))
                                        else:
                                            self.__Ui_EditBuild_MoveIncludeItemIn(sliderSet=conflict.text(0))

            if self.Ui_EditBuild is None:
                self.__Ui_BSBB_Populate()
                self.__Ui_BSBB_MadeChange()

        return True

    def __displayMessage(self,
                         icon: QMessageBox.Icon,
                         title: str,
                         text: str, *,
                         informativeText: str | None = None,
                         buttons: QMessageBox.StandardButton = QMessageBox.
                         StandardButton.Ok,
                         defaultButton: QMessageBox.
                         StandardButton = QMessageBox.StandardButton.Ok,
                         parent: QWidget | None = None) -> int:

        msgBox = QMessageBox(icon,
                             title,
                             text,
                             buttons=buttons,
                             parent=parent)
        msgBox.setInformativeText(informativeText)
        msgBox.setDefaultButton(defaultButton)
        return msgBox.exec()

    def __addOutputsToComboBox(self,
                               comboBox: QComboBox, *,
                               value: str | None = None,
                               createInvalid: bool = True,
                               defaultLast: bool = True):
        comboBox.addItems([
            mod for mod in self.__organizer.modList().allMods()
            if not mod.casefold().endswith('_separator')
        ])

        overwrite = QtGui.QStandardItem('Overwrite')
        overwrite.setForeground(QtGui.QColor('orange'))

        model = comboBox.model()
        if not isinstance(model, QtGui.QStandardItemModel):
            raise AttributeError(type(model))
        model.appendRow(overwrite)

        if value is None:
            selectIndex = (comboBox.count() - 1) if defaultLast else 0
        else:
            selectIndex = comboBox.findText(value, Qt.MatchFlag.MatchExactly)

            if selectIndex == -1 and createInvalid:
                selectIndex = comboBox.count()
                badItem = QtGui.QStandardItem(value)
                badItem.setForeground(QtGui.QColor('red'))
                model.appendRow(badItem)

        comboBox.setCurrentIndex(selectIndex)

    def __clearFolder(self, path: str, *, onlyFiles: bool = False):
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif not onlyFiles and os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    #
    # Problem Window Stuff
    #
    def __Ui_Problems_ItemChanged(self, item):
        if isinstance(item, QTreeWidgetItem):
            if item.checkState(0) == Qt.CheckState.Checked:
                self.Ui_Problems.addButton.setEnabled(True)
                parent = item.parent()
                if parent:
                    curItem = parent.indexOfChild(item)
                    for x in range(parent.childCount()):
                        if x != curItem:
                            parent.child(x).setCheckState(0, Qt.CheckState.Unchecked) # type: ignore
            else:
                self.Ui_Problems.addButton.setEnabled(self.__Ui_Problems_HasChecked())

    def __Ui_Problems_HasChecked(self) -> bool:
        for t in range(self.Ui_Problems.treeWidget.topLevelItemCount()):
            top = self.Ui_Problems.treeWidget.topLevelItem(t)
            if top:
                for o in range(top.childCount()):
                    output = top.child(o)
                    if output:
                        for c in range(output.childCount()):
                            conflict = output.child(c)
                            if conflict:
                                if conflict.checkState(0) == Qt.CheckState.Checked:
                                    return True
        return False

    def __Ui_Problems_Add(self):
        self.Ui_Problems_Dialog.done(3)

    #
    # Main BSB Window Related Stuff
    #
    def display(self) -> None:
        self.__EditBuild_Index = None
        self.Ui_EditBuild = None
        self.Ui_EditBuild_Dialog = None

        self.BodySlide = MO2BodySlide(self.__organizer)
        self.BodySlide.load_configs(exclude_slide_group_files=['BSBB_Groups.xml'])
        self.__loadConfig()

        self.Ui_BSBB_Dialog = VerifyCloseDialog(self.__parentWidget, self)
        self.Ui_BSBB = Ui_BSBB()
        self.Ui_BSBB.setupUi(self.Ui_BSBB_Dialog)
        self.__Ui_BSBB_Populate()

        header = self.Ui_BSBB.buildsTable.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # Buttons
        self.Ui_BSBB.addButton.clicked.connect(self.__Ui_BSBB_AddBuild)
        self.Ui_BSBB.removeButton.clicked.connect(self.__Ui_BSBB_DelBuild)
        self.Ui_BSBB.upButton.clicked.connect(self.__Ui_BSBB_MoveBuildUp)
        self.Ui_BSBB.downButton.clicked.connect(self.__Ui_BSBB_MoveBuildDown)
        self.Ui_BSBB.applyButton.clicked.connect(self.__saveConfig)
        self.Ui_BSBB.buildButton.clicked.connect(self.__Ui_BSBB_BuildAll)
        self.Ui_BSBB.validateButton.clicked.connect(self.__Ui_BSBB_ValidateAll)
        self.Ui_BSBB.settingsButton.clicked.connect(self.__Ui_Settings_Display)

        self.Ui_BSBB.buildsTable.doubleClicked.connect(self.__Ui_BSBB_EditBuild)
        self.Ui_BSBB.buildsTable.cellChanged.connect(self.__Ui_BSBB_ToggleBuild)

        self.Ui_BSBB_Dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
        self.Ui_BSBB_Dialog.show()

    def closeEvent(self, closeEvent: QtGui.QCloseEvent):
        if self.__unsaved_changes:
            ret = self.__displayMessage(
                QMessageBox.Icon.Warning,
                title='Save changes?',
                text="Config has been modified.",
                informativeText='Do you want to save your changes?',
                buttons=QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                defaultButton=QMessageBox.StandardButton.Save)

            if ret == QMessageBox.StandardButton.Cancel:
                closeEvent.ignore()
                return

            if ret == QMessageBox.StandardButton.Save:
                self.__saveConfig()

        closeEvent.accept()

    def __Ui_BSBB_MadeChange(self):
        self.__unsaved_changes = True
        self.Ui_BSBB.applyButton.setEnabled(True)

    def __Ui_BSBB_AddBuild(self) -> None:
        self.__Ui_EditBuild_Display()

    def __Ui_BSBB_ToggleBuild(self, row:int, col: int) -> None:
        self.__Ui_BSBB_MadeChange()
        self.builds[row].enable = self.Ui_BSBB.buildsTable.item(row, 0).checkState() == Qt.CheckState.Checked # type: ignore

    def __Ui_BSBB_EditBuild(self) -> None:
        sm = self.Ui_BSBB.buildsTable.selectionModel()
        if sm is None or not sm.hasSelection():
            return

        row = sm.selectedRows()[0].row()

        self.__Ui_EditBuild_Display(row, self.builds[row])

    def __Ui_BSBB_DelBuild(self) -> None:
        sm = self.Ui_BSBB.buildsTable.selectionModel()
        if sm is None or not sm.hasSelection():
            return

        row = sm.selectedRows()[0].row()
        self.builds.pop(row)

        self.__Ui_BSBB_Populate()
        self.__Ui_BSBB_MadeChange()

    def __Ui_BSBB_MoveBuild(self, up: bool):
        sm = self.Ui_BSBB.buildsTable.selectionModel()
        if sm is None or not sm.hasSelection():
            return

        row = sm.selectedRows()[0].row()
        if row == (0 if up else len(self.builds) - 1):
            return

        moveTo = row + (-1 if up else 1)

        self.builds.insert(moveTo, self.builds.pop(row))
        for editrow in [moveTo, row]:
            self.Ui_BSBB.buildsTable.setItem(
                editrow, 0, QTableWidgetItem(self.builds[editrow].preset))
            self.Ui_BSBB.buildsTable.setItem(
                editrow, 1,
                QTableWidgetItem(self.builds[editrow].includeAsStr()))

        index = self.Ui_BSBB.buildsTable.indexFromItem(
            self.Ui_BSBB.buildsTable.item(moveTo, 0))
        sm.select(
            index, QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        self.__Ui_BSBB_MadeChange()

    def __Ui_BSBB_MoveBuildUp(self) -> None:
        self.__Ui_BSBB_MoveBuild(True)

    def __Ui_BSBB_MoveBuildDown(self) -> None:
        self.__Ui_BSBB_MoveBuild(False)

    def __Ui_BSBB_ValidateAll(self) -> None:
        self.__validateBuilds()

    def __Ui_BSBB_BuildAll(self) -> None:
        self.__canceled = False
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        createGroupsOnly = modifiers == QtCore.Qt.KeyboardModifier.ControlModifier

        if not self.__validateBuilds(
                auto=True,
                checkConflicts=self.config.onBuildCheckConflicts,
                checkIgnored=self.config.onBuildCheckIgnored):
            logging.error('Problem validating builds. Stopping.')
            return

        self.__saveConfig()

        enabledBuilds = dict[str, Config.Build]()
        self.BodySlide.CreateFilePath = self.config.getOutputPathorOverwrite(self.__organizer)

        for x in range(len(self.builds)):
            build = self.builds[x]
            if not build.enable:
                continue

            buildName = f"BSBB Build {x+1}"
            enabledBuilds[buildName] = build
            
            meshesPath = f"{build.output}/meshes"
            
            if not createGroupsOnly:
                os.makedirs(meshesPath, exist_ok=True) # Failed attempt to fix BodySlide error creating folders on first build
            if not createGroupsOnly and self.config.deleteMeshes:
                logging.info(f"Clearing meshes from {build.output}")
                #shutil.rmtree(f"{build.output}/meshes", ignore_errors=True)
                self.__clearFolder(meshesPath) # Minor improvement to BodySlide error creating folders on first build

            try:
                sliderSets = self.BodySlide.get_silder_sets_filtered(
                    build.include, allowConflicts=True, priorities=self.config.priorities)
                self.BodySlide.create_slider_group(
                    'BSBB_Groups.xml', f"BSBB Build {x+1}",
                    [sliderSet.name for sliderSet in sliderSets])
                # Failed attempt to fix BodySlide error creating folders on first build
                #for sliderSet in sliderSets:
                #    os.makedirs(os.path.dirname(sliderSet.output), exist_ok=True)
            except ValueError:
                logging.error(repr(sys.exception()))
                return


        if createGroupsOnly:
            self.__displayMessage(QMessageBox.Icon.Information, "BodySlide Groups Created", "Created BodySlide groups for enabled builds.")
            return

        # Failed attempt to fix BodySlide error creating folders on first build
        # Maybe this would work if it waited for refresh but tried sleep after
        # Did also try executing a fake program just to force MO2 to load vfs
        # and refresh before real BodySlide run, but nope
        #self.__organizer.refresh(True)

        for buildName, build in enabledBuilds.items():
            if self.__canceled:
                break

            args = list([
                f"--groupbuild=\"{buildName}\"",
                f"--targetdir=\"{PureWindowsPath(build.getOutputPathorOverwrite(self.__organizer)).__fspath__().replace("\\", "\\\\")}\\\\\"", # Must have double back slashes else get a "Zero" error from BodySlide on launch
                f"--preset=\"{build.preset}\"",
                "--trimorphs",
            ])
            exe = self.__organizer.startApplication("BodySlide x64", args=args)
            if exe == mobase.INVALID_HANDLE_VALUE:
                
                self.__displayMessage(QMessageBox.Icon.Critical,
                                      title='Error running BodySlide',
                                      text='Make sure BodySlide is registered as an executable (Ctrl+E) with the name "BodySlide x64"')
                return

            waitResult, exitCode = self.__organizer.waitForApplication(exe, False)
            if not waitResult:
                logging.warning("BodySlide x64 execution canceled")
                return
            
            if exitCode != 0:
                logging.error(f"BodySlide x64 exit code: {exitCode}")
                self.__displayMessage(QMessageBox.Icon.Critical,
                                      title='Error running BodySlide',
                                      text=f"Error code {exitCode} returned by BodySlide x64")
                return

        if self.config.autoClose:
            self.Ui_BSBB_Dialog.close()

    def __Ui_BSBB_Populate(self):
        self.Ui_BSBB.buildsTable.clearContents()
        self.Ui_BSBB.buildsTable.setRowCount(len(self.builds))
        for row in range(len(self.builds)):
            i = QTableWidgetItem(self.builds[row].preset)
            i.setCheckState(Qt.CheckState.Checked if self.builds[row].enable else Qt.CheckState.Unchecked)
            self.Ui_BSBB.buildsTable.setItem(row, 0, i)
            self.Ui_BSBB.buildsTable.setItem(
                row, 1, QTableWidgetItem(self.builds[row].output))
            self.Ui_BSBB.buildsTable.setItem(
                row, 2, QTableWidgetItem(str(len(self.builds[row].include))))


    ###################################
    # Edit Build Window Related Stuff #
    ###################################

    # Outputs what to display in the use column and tool tip based Include Use
    # Want to change to display icon and tool tip if I ever get some icons made.
    def includeUseToUseColumn(self, itemUse: Config.IncludeUse) -> tuple[str, str | None]:
        match itemUse:
            case Config.IncludeUse.Exclude:
                return ('', None)
            case Config.IncludeUse.Include:
                return ('', None)
            case Config.IncludeUse.IncludeKeep:
                return ('++', 'Include + Keep matching alternatives')
            case Config.IncludeUse.Keep:
                return ('+', 'Keep matching alternatives')
            case Config.IncludeUse.Remove:
                return ('-', 'Remove matching alternatives')

    def __UI_EditBuild_UpdateInclude(self, *, addingNew: bool = False, setType: Config.IncludeType | str | None = None, setUse: Config.IncludeUse | str | None = None, setName: str | None = None, forceTop: bool = False, clearSelection: bool = True, select: bool = True ):
        if self.Ui_EditBuild is None:
            return

        tree = self.Ui_EditBuild.includeTree

        if addingNew:
            if setType is None or setUse is None or setName is None:
                raise ValueError('setType, setUse and setName cannot be None if addingNew is True')

            item = QTreeWidgetItem()
        else:
            items = tree.selectedItems()
            if len(items) != 1:
                raise ValueError('Must select exactly one item to edit')

            item = items[0]

        if isinstance(setType, str):
            Config.strToIncludeType(setType) # Will raise error if incorrect value
        if isinstance(setType, Config.IncludeType):
            setType = Config.includeTypeToStr(setType)

        if isinstance(setUse, str):
            Config.strToIncludeUse(setUse) # Will raise error if incorrect value
        if isinstance(setUse, Config.IncludeUse):
            setUse = Config.includeUseToStr(setUse)

        if setType:
            item.setText(_UI_EDITBUILD_TREE_COL_TYPE, setType)

        if setName and item.text(_UI_EDITBUILD_TREE_COL_NAME) != setName:
            item.setText(_UI_EDITBUILD_TREE_COL_NAME, setName)

        match Config.strToIncludeType(item.text(_UI_EDITBUILD_TREE_COL_TYPE)):
            case Config.IncludeType.GROUP:
                if CaseInsensitive(item.text(_UI_EDITBUILD_TREE_COL_NAME)) not in self.BodySlide.sliderGroups:
                    item.setForeground(_UI_EDITBUILD_TREE_COL_NAME, QtGui.QBrush(QtGui.QColor('red')))
                else:
                    item.setForeground(_UI_EDITBUILD_TREE_COL_NAME, QtGui.QBrush(Qt.BrushStyle.NoBrush))
            case Config.IncludeType.SLIDERSET:
                if item.text(_UI_EDITBUILD_TREE_COL_NAME) not in self.BodySlide.sliderSets:
                    item.setForeground(_UI_EDITBUILD_TREE_COL_NAME, QtGui.QBrush(QtGui.QColor('red')))
                else:
                    item.setForeground(_UI_EDITBUILD_TREE_COL_NAME, QtGui.QBrush(Qt.BrushStyle.NoBrush))
            case _:
                item.setForeground(_UI_EDITBUILD_TREE_COL_NAME, QtGui.QBrush(Qt.BrushStyle.NoBrush))
        

        if setUse and item.text(_UI_EDITBUILD_TREE_COL_USE) != setUse:
            item.setText(_UI_EDITBUILD_TREE_COL_USE, setUse)
            includeUse = Config.strToIncludeUse(setUse)
            parent = None
            insertAt = 0 if forceTop else -1
            sort = True
            useName, useToolTip = self.includeUseToUseColumn(includeUse)
            item.setText(_UI_EDITBUILD_TREE_COL_ICON, useName)
            item.setToolTip(_UI_EDITBUILD_TREE_COL_ICON, useToolTip)

            if includeUse == Config.IncludeUse.Exclude and item.parent() != tree.topLevelItem(0):
                parent = tree.topLevelItem(0)
            elif includeUse == Config.IncludeUse.Include and item.parent() != tree.topLevelItem(1):
                parent = tree.topLevelItem(1)
            elif item.parent() != tree.topLevelItem(2):
                parent = tree.topLevelItem(2)
                sort = False
                if addingNew and not forceTop:
                    selected = tree.selectedIndexes()
                    if selected:
                        selected = min(selected)
                        selected = tree.itemFromIndex(selected)
                        if selected:
                            selectedParent = selected.parent()
                            if selectedParent:
                                insertAt = selectedParent.indexOfChild(selected)


            if parent:
                currentParent = item.parent()
                if currentParent:
                    currentParent.removeChild(item)

                if insertAt == -1:
                    parent.addChild(item)
                else:
                    parent.insertChild(insertAt, item)

                if sort:
                    parent.sortChildren(_UI_EDITBUILD_TREE_COL_NAME, Qt.SortOrder.AscendingOrder)

                if clearSelection:
                    tree.clearSelection()

                if select:
                    item.setSelected(True)

        self.__Ui_EditBuild_HideUnused()

    def __Ui_EditBuild_HideUnused(self):
        if self.Ui_EditBuild is None:
            return
        
        tree = self.Ui_EditBuild.includeTree

        for x in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(x)
            if item:
                item.setHidden(item.childCount() == 0)


    def __Ui_EditBuild_Display(self,
                               index: int = -1,
                               build: Config.Build | None = None):
        if index >= 0 and build is None:
            raise ValueError('build cannot be None if index >= 0')

        self.__EditBuild_Index = index
        build = Config.Build(True, 'Output - BodySlide', '- Zeroed Sliders -', []) if build is None else build

        self.Ui_EditBuild_Dialog = QDialog(self.Ui_BSBB_Dialog)
        self.Ui_EditBuild = Ui_EditBuild()
        self.Ui_EditBuild.setupUi(self.Ui_EditBuild_Dialog)


        # Enabled CheckBox
        self.Ui_EditBuild.enabledCheckBox.setChecked(build.enable)

        # Output Mod ComboBox

        self.Ui_EditBuild.outputModComboBox.currentIndexChanged.connect(
            self.__Ui_EditBuild_OutputChange)
        self.__addOutputsToComboBox(self.Ui_EditBuild.outputModComboBox,
                                    value=build.output)

        # Preset ComboBox
        self.Ui_EditBuild.presetComboBox.addItems(self.BodySlide.presets)

        self.Ui_EditBuild.presetComboBox.currentIndexChanged.connect(
            self.__Ui_EditBuild_PresetChange)
        selectIndex = self.Ui_EditBuild.presetComboBox.findText(
            build.preset, Qt.MatchFlag.MatchExactly)

        if selectIndex == -1:
            if index == -1:
                selectIndex = 0
            else:
                selectIndex = self.Ui_EditBuild.presetComboBox.count()
                badItem = QtGui.QStandardItem(build.preset)
                badItem.setForeground(QtGui.QColor('red'))

                model = self.Ui_EditBuild.presetComboBox.model()
                if not isinstance(model, QtGui.QStandardItemModel):
                    raise AttributeError(type(model))
                model.appendRow(badItem)

        self.Ui_EditBuild.presetComboBox.setCurrentIndex(selectIndex)

        # Filters
        self.Ui_EditBuild.groupFilter.textChanged.connect(self.__Ui_EditBuild_GroupFilter)
        self.Ui_EditBuild.sliderSetFilter.textChanged.connect(self.__Ui_EditBuild_SliderSetFilter)

        # Include Tree
        tree = self.Ui_EditBuild.includeTree
        top = QTreeWidgetItem(['Exclude'])
        tree.addTopLevelItem(top)
        top.setFirstColumnSpanned(True)
        top.setForeground(0, QtGui.QBrush(QtGui.QColor('red')))
        top.font(0).setBold(True)
        top.setExpanded(True)
        
        top = QTreeWidgetItem(['Include Only'])
        tree.addTopLevelItem(top)
        top.setFirstColumnSpanned(True)
        top.setForeground(0, QtGui.QColor('green'))
        top.font(0).setBold(True)
        top.setExpanded(True)
        
        top = QTreeWidgetItem(['Ordered by Priority (Highest to Lowest)'])
        tree.addTopLevelItem(top)
        top.setFirstColumnSpanned(True)
        top.font(0).setBold(True)
        top.setForeground(0, QtGui.QColor('green'))
        top.setExpanded(True)

        tree.setColumnHidden(_UI_EDITBUILD_TREE_COL_TYPE, True)
        tree.setColumnHidden(_UI_EDITBUILD_TREE_COL_USE, True)
        tree.setColumnWidth(_UI_EDITBUILD_TREE_COL_ICON, 32)

        # Include Tree Items
        for include in build.include:
            self.__UI_EditBuild_UpdateInclude(addingNew=True, setType=include.type, setUse=include.use, setName=include.name, clearSelection=False, select=False)

        # Extra Groups List
        groups = [
            group for group in self.BodySlide.sliderGroups
            if group not in [include.name for include in build.include if include.type == Config.IncludeType.GROUP]
        ]
        self.Ui_EditBuild.groupList.addItems(groups)
        self.Ui_EditBuild.groupList.sortItems()

        # Preview SliderSets
        self.Ui_EditBuild.previewList.addItems([s for s in self.BodySlide.sliderSets])

        # Extra Outfits or Bodies List
        sliderSets = [
            sliderSet for sliderSet in self.BodySlide.sliderSets
            if sliderSet not in [include.name for include in build.include if include.type == Config.IncludeType.SLIDERSET]
        ]
        for sliderSet in sliderSets:
            groups = ', '.join(self.BodySlide.sliderSets[sliderSet].groups)
            li = QListWidgetItem(sliderSet)
            li.setToolTip(f"Member of {groups if groups else 'no groups'}")
            self.Ui_EditBuild.sliderSetList.addItem(li)
        self.Ui_EditBuild.sliderSetList.sortItems()
        self.__Ui_EditBuild_SliderSetFilter()

        # Buttons
        self.Ui_EditBuild.addButton.clicked.connect(
            self.__Ui_EditBuild_MoveIncludeItemIn)
        self.Ui_EditBuild.upButton.clicked.connect(
            self.__Ui_EditBuild_MoveIncludeUp)
        self.Ui_EditBuild.downButton.clicked.connect(
            self.__Ui_EditBuild_MoveIncludeDown)
        self.Ui_EditBuild.removeButton.clicked.connect(
            self.__Ui_EditBuild_MoveIncludeItemOut)
        self.Ui_EditBuild_Dialog.accepted.connect(self.__Ui_EditBuild_SaveUI)
        self.Ui_EditBuild_Dialog.rejected.connect(self.__Ui_EditBuild_SaveUI)
        self.Ui_EditBuild_Dialog.accepted.connect(self.__Ui_EditBuild_Accepted)
        self.Ui_EditBuild_Dialog.rejected.connect(self.__Ui_EditBuild_Rejected)
        self.Ui_EditBuild.validateButton.clicked.connect(self.__Ui_EditBuild_Validate)
        self.Ui_EditBuild.newButton.clicked.connect(self.__UI_EditBuild_AdvancedNewPressed)
        self.Ui_EditBuild.applyAdvancedButton.clicked.connect(self.__UI_EditBuild_AdvancedApplyPressed)

        # Double Clicks
        self.Ui_EditBuild.groupList.doubleClicked.connect(
            self.__Ui_EditBuild_MoveIncludeItemIn)
        self.Ui_EditBuild.sliderSetList.doubleClicked.connect(
            self.__Ui_EditBuild_MoveIncludeItemIn)
        self.Ui_EditBuild.includeTree.doubleClicked.connect(
            self.__Ui_EditBuild_MoveIncludeItemOut)

        # Other Events
        self.Ui_EditBuild.tabWidget.currentChanged.connect(self.__UI_EditBuild_TabChanged)
        self.Ui_EditBuild.includeTree.itemSelectionChanged.connect(self.__Ui_EditBuild_IncludeSelectionChanged)
        self.Ui_EditBuild.valueLineEdit.textChanged.connect(self.__UI_EditBuild_SetAdvancedStates)
        self.Ui_EditBuild.typeComboBox.currentIndexChanged.connect(self.__UI_EditBuild_SetAdvancedStates)
        self.__Ui_EditBuild_IncludeSelectionChanged()

        # Restore saved geometry
        self.__Ui_EditBuild_LoadUI()
        self.Ui_EditBuild_Dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint)
        
        self.Ui_EditBuild_Dialog.show()

    def __UI_EditBuild_ClearAdvanced(self):
        if not self.Ui_EditBuild:
            return

        self.Ui_EditBuild.valueLineEdit.setText('')
        self.Ui_EditBuild.typeComboBox.setCurrentIndex(0)
        self.Ui_EditBuild.useComboBox.setCurrentIndex(0)

        self.__UI_EditBuild_SetAdvancedStates()

    def __UI_EditBuild_SetAdvancedStates(self):
        if not self.Ui_EditBuild:
            return

        # These the only lines that can enable buttons. Everything else after should only disable if required
        self.Ui_EditBuild.newButton.setEnabled(True if self.Ui_EditBuild.valueLineEdit.text() else False)
        self.Ui_EditBuild.applyAdvancedButton.setEnabled(True if self.Ui_EditBuild.valueLineEdit.text() else False)
        self.Ui_EditBuild.previewList.clear()

        selection = self.Ui_EditBuild.includeTree.selectedItems()

        if len(selection) != 1:
            self.Ui_EditBuild.applyAdvancedButton.setEnabled(False)
        else:
            selection = selection[0]
            parent = selection.parent()

            if not parent:
                self.Ui_EditBuild.applyAdvancedButton.setEnabled(False)

        isValid = True
        ssType = Config.IncludeType.GROUP
        match self.Ui_EditBuild.typeComboBox.currentIndex():
            case 0: # Group
                ssType = Config.IncludeType.GROUP
                self.Ui_EditBuild.valueLabel.setText('Name')
                isValid = CaseInsensitive(self.Ui_EditBuild.valueLineEdit.text()) in self.BodySlide.sliderGroups or self.Ui_EditBuild.valueLineEdit.text().casefold() == 'unassigned'
            case 1: # Source
                ssType = Config.IncludeType.SOURCE
                self.Ui_EditBuild.valueLabel.setText('File')
                
                if self.__Source_Validator.match(self.Ui_EditBuild.valueLineEdit.text()) is None:
                    self.Ui_EditBuild.newButton.setEnabled(False)
                    self.Ui_EditBuild.applyAdvancedButton.setEnabled(False)
                    isValid = False
            case 2: # Slider Set
                ssType = Config.IncludeType.SLIDERSET
                self.Ui_EditBuild.valueLabel.setText('Name')
                isValid = self.Ui_EditBuild.valueLineEdit.text() in self.BodySlide.sliderSets
            case 3:
                ssType = Config.IncludeType.CONTAINS
                self.Ui_EditBuild.valueLabel.setText('Name')
            case 4:
                ssType = Config.IncludeType.REGEX
                self.Ui_EditBuild.valueLabel.setText('Regex')

                try:
                    re.compile(self.Ui_EditBuild.valueLineEdit.text())
                except re.error:
                    self.Ui_EditBuild.newButton.setEnabled(False)
                    self.Ui_EditBuild.applyAdvancedButton.setEnabled(False)
                    isValid = False
                    
        if isValid:
            self.Ui_EditBuild.valueLineEdit.setStyleSheet(None)
            self.Ui_EditBuild.previewList.addItems([s for s in self.BodySlide.GetMatchingSliderSets(Config.IncludeItem(ssType, self.Ui_EditBuild.valueLineEdit.text(), Config.IncludeUse.Include))])
            self.Ui_EditBuild.previewList.sortItems()
        else:
            self.Ui_EditBuild.valueLineEdit.setStyleSheet("color: red;")

    def __UI_EditBuild_AdvancedApplyPressed(self, add: bool = False):
        if not self.Ui_EditBuild:
            return

        match self.Ui_EditBuild.typeComboBox.currentIndex():
            case 0: # Group
                sType = Config.IncludeType.GROUP
            case 1: # Source
                sType = Config.IncludeType.SOURCE
            case 2: # Slider Set
                sType = Config.IncludeType.SLIDERSET
            case 3:
                sType = Config.IncludeType.CONTAINS
            case 4:
                sType = Config.IncludeType.REGEX

        match self.Ui_EditBuild.useComboBox.currentIndex():
            case 0: # Group
                sUse = Config.IncludeUse.IncludeKeep
            case 1: # Source
                sUse = Config.IncludeUse.Keep
            case 2: # Slider Set
                sUse = Config.IncludeUse.Remove
            case 3:
                sUse = Config.IncludeUse.Include
            case 4:
                sUse = Config.IncludeUse.Exclude
        
        self.__UI_EditBuild_UpdateInclude(addingNew=add, setType=sType, setUse=sUse, setName=self.Ui_EditBuild.valueLineEdit.text())
        self.__UI_EditBuild_SetAdvancedStates()

    def __UI_EditBuild_AdvancedNewPressed(self):
        self.__UI_EditBuild_AdvancedApplyPressed(True)

    def __UI_EditBuild_TabChanged(self, index: int):
        if self.Ui_EditBuild is None:
            return

        if index == 2:
            self.Ui_EditBuild.addButton.setEnabled(False)
            self.Ui_EditBuild.removeButton.setText('Remove')
        else:
            self.Ui_EditBuild.addButton.setEnabled(True)
            self.Ui_EditBuild.removeButton.setText('>>')

    def __Ui_EditBuild_IncludeSelectionChanged(self):
        if not self.Ui_EditBuild:
            return

        selection = self.Ui_EditBuild.includeTree.selectedItems()
        if len(selection) != 1:
            self.__UI_EditBuild_ClearAdvanced()
            return

        selection = selection[0]
        parent = selection.parent()
        if not parent:
            self.__UI_EditBuild_ClearAdvanced()
            match self.Ui_EditBuild.includeTree.indexOfTopLevelItem(selection):
                case 0:
                    self.Ui_EditBuild.useComboBox.setCurrentIndex(4)
                case 1:
                    self.Ui_EditBuild.useComboBox.setCurrentIndex(3)
            return

        sType = Config.strToIncludeType(selection.text(_UI_EDITBUILD_TREE_COL_TYPE))
        sUse = Config.strToIncludeUse(selection.text(_UI_EDITBUILD_TREE_COL_USE))
        self.Ui_EditBuild.valueLineEdit.setText(selection.text(_UI_EDITBUILD_TREE_COL_NAME))
        match sType:
            case Config.IncludeType.GROUP:
                self.Ui_EditBuild.typeComboBox.setCurrentIndex(0)
            case Config.IncludeType.SOURCE:
                self.Ui_EditBuild.typeComboBox.setCurrentIndex(1)
            case Config.IncludeType.SLIDERSET:
                self.Ui_EditBuild.typeComboBox.setCurrentIndex(2)
            case Config.IncludeType.CONTAINS:
                self.Ui_EditBuild.typeComboBox.setCurrentIndex(3)
            case Config.IncludeType.REGEX:
                self.Ui_EditBuild.typeComboBox.setCurrentIndex(4)

        match sUse:
            case Config.IncludeUse.IncludeKeep:
                self.Ui_EditBuild.useComboBox.setCurrentIndex(0)
            case Config.IncludeUse.Keep:
                self.Ui_EditBuild.useComboBox.setCurrentIndex(1)
            case Config.IncludeUse.Remove:
                self.Ui_EditBuild.useComboBox.setCurrentIndex(2)
            case Config.IncludeUse.Include:
                self.Ui_EditBuild.useComboBox.setCurrentIndex(3)
            case Config.IncludeUse.Exclude:
                self.Ui_EditBuild.useComboBox.setCurrentIndex(4)

        self.__UI_EditBuild_SetAdvancedStates()
        
    def __Ui_EditBuild_FilterList(self, targetList: QListWidget, filterText: str):
        if not filterText:
            for x in range(targetList.count()):
                targetList.item(x).setHidden(False) # type: ignore
            return

        filterText = filterText.casefold()
        for x in range(targetList.count()):
            item = targetList.item(x)
            item.setHidden(filterText not in item.text().casefold()) # type: ignore

    def __Ui_EditBuild_MoveIncludeItemIn(self, *, sliderSet: str | None = None):
        if self.Ui_EditBuild is None:
            return

        # If sliderSet we forcing it not to be a group, else based on current tab displayed
        isGroup = sliderSet is None and self.Ui_EditBuild.tabWidget.currentIndex() == 0
        isSliderSet = sliderSet is not None or self.Ui_EditBuild.tabWidget.currentIndex() == 1

        if (not isGroup and not isSliderSet):
            return

        fromList = self.Ui_EditBuild.groupList if isGroup else self.Ui_EditBuild.sliderSetList

        first = True
        if sliderSet is None:
            for index in sorted([index.row() for index in fromList.selectedIndexes()], reverse=True):
                li = fromList.takeItem(index)
                if li:
                    self.__UI_EditBuild_UpdateInclude(addingNew=True, setType=Config.IncludeType.GROUP if isGroup else Config.IncludeType.SLIDERSET, setUse=Config.includeUseToStr(Config.IncludeUse.IncludeKeep), setName=li.text(), clearSelection=first)
                    first=False
        else:
            for x in range(fromList.count()):
                li = fromList.item(x)
                if li and li.text() == sliderSet:
                    fromList.takeItem(x)
                    self.__UI_EditBuild_UpdateInclude(addingNew=True, setType=Config.IncludeType.SLIDERSET, setUse=Config.IncludeUse.Keep, setName=li.text(), forceTop=True, clearSelection=x==0)
                    break

        if isGroup:
            self.__Ui_EditBuild_SliderSetFilter()

    def __Ui_EditBuild_MoveIncludeItemOut(self):
        if self.Ui_EditBuild is None:
            return

        tree = self.Ui_EditBuild.includeTree
        addedGroup = False
        addedSliderSet = False
        for index in sorted([index for index in tree.selectedIndexes()], key=methodcaller('row'), reverse=True):
            include = tree.itemFromIndex(index)
            if include is None:
                continue
            if include.parent() is None:
                continue

            include.parent().removeChild(include) # type: ignore

            includeType = Config.strToIncludeType(include.text(_UI_EDITBUILD_TREE_COL_TYPE))

            match includeType:
                case Config.IncludeType.GROUP:
                    if include.text(_UI_EDITBUILD_TREE_COL_NAME) not in self.BodySlide.sliderGroups:
                        # We only add valid groups back to groups list
                        continue
                    addedGroup = True
                    li = QListWidgetItem(include.text(_UI_EDITBUILD_TREE_COL_NAME))
                    self.Ui_EditBuild.groupList.addItem(li)
                case Config.IncludeType.SLIDERSET:
                    if include.text(_UI_EDITBUILD_TREE_COL_NAME) not in self.BodySlide.sliderSets:
                        # We only add valid slider sets back to slider set list
                        continue
                    sliderSet = self.BodySlide.sliderSets[include.text(_UI_EDITBUILD_TREE_COL_NAME)]
                    addedSliderSet = True
                    li = QListWidgetItem(include.text(_UI_EDITBUILD_TREE_COL_NAME))
                    groups = ', '.join(sliderSet.groups)
                    li.setToolTip(f"Member of {groups if groups else 'no groups'}")
                    self.Ui_EditBuild.sliderSetList.addItem(li)

        if addedGroup:
            self.Ui_EditBuild.groupList.sortItems()
            self.__Ui_EditBuild_GroupFilter()
        if addedSliderSet:
            self.Ui_EditBuild.sliderSetList.sortItems()
        if addedGroup or addedSliderSet:
            # As slider sets may be filtering out included groups so need to reapply filter
            self.__Ui_EditBuild_SliderSetFilter()

    def __Ui_EditBuild_OutputChange(self):
        self.__comboboxMatchStyle(self.Ui_EditBuild.outputModComboBox) # type: ignore
        
    def __Ui_EditBuild_GroupFilter(self):
        self.__Ui_EditBuild_FilterList(self.Ui_EditBuild.groupList, self.Ui_EditBuild.groupFilter.text()) # type: ignore

    
    def __Ui_EditBuild_SliderSetFilter(self):
        if self.Ui_EditBuild is None:
            return

        filterText = self.Ui_EditBuild.sliderSetFilter.text()
        targetList = self.Ui_EditBuild.sliderSetList
        clearFilter = filterText == ''
        filterText = filterText.casefold()
        if self.Ui_EditBuild.autoFilterCheckBox.isChecked():
            currentGroups = [group.name for group in self.__Ui_EditBuild_GetBuild().include if group.type == Config.IncludeType.GROUP]
        else:
            currentGroups = False

        for x in range(targetList.count()):
            li = targetList.item(x)
            if li:
                if currentGroups and self.BodySlide.sliderSets[li.text()].isMember(currentGroups):
                    li.setHidden(True)
                elif clearFilter:
                    li.setHidden(False)
                else:
                    li.setHidden(filterText not in li.text().casefold())

    def __Ui_EditBuild_PresetChange(self):
        self.__comboboxMatchStyle(self.Ui_EditBuild.presetComboBox) # type: ignore          
        
    def __Ui_EditBuild_MoveTreeItemUpDown(self, up: bool):
        if not self.Ui_EditBuild:
            return

        target = self.Ui_EditBuild.includeTree
        moveBy = -1 if up else 1

        selection = sorted([index for index in target.selectedIndexes()], reverse=not up, key=methodcaller('row'))
        if len(selection) == 0:
            return

        # Make sure all selection is under Priority branch
        item = target.itemFromIndex(selection[0])
        priorityBranch = target.topLevelItem(2)
        if not (priorityBranch and item and item.parent() and item.parent() == priorityBranch):
            return
        
        # make sure not trying to move top item up or last item down
        i = priorityBranch.indexOfChild(item)
        if i == (0 if up else priorityBranch.childCount() - 1):
            return

        target.clearSelection()
        
        lastRow = -1
        for x in selection:
            if x.row() == lastRow:
                continue
            lastRow = x.row()

            item = target.itemFromIndex(x)
            if item:
                i = priorityBranch.indexOfChild(item)
                if i == (0 if up else priorityBranch.childCount() - 1):
                    return
                priorityBranch.removeChild(item)
                priorityBranch.insertChild(i + moveBy, item)
                item.setSelected(True)

    def __Ui_EditBuild_MoveIncludeUp(self):
        self.__Ui_EditBuild_MoveTreeItemUpDown(True)

    def __Ui_EditBuild_MoveIncludeDown(self):
        self.__Ui_EditBuild_MoveTreeItemUpDown(False)

    def __Ui_EditBuild_GetBuild(self) -> Config.Build:
        if self.Ui_EditBuild is None:
            return None # type: ignore

        enable = self.Ui_EditBuild.enabledCheckBox.isChecked()
        output = self.Ui_EditBuild.outputModComboBox.currentText()
        preset = self.Ui_EditBuild.presetComboBox.currentText()
        include = list[Config.IncludeItem]()

        top = self.Ui_EditBuild.includeTree.topLevelItem(0)
        if top:
            for x in range(top.childCount()): # type: ignore
                item = top.child(x)
                if item:
                    includeType = Config.strToIncludeType(item.text(_UI_EDITBUILD_TREE_COL_TYPE))
                    include.append(Config.IncludeItem(includeType, item.text(_UI_EDITBUILD_TREE_COL_NAME), Config.IncludeUse.Exclude))

        top = self.Ui_EditBuild.includeTree.topLevelItem(1)
        if top:
            for x in range(top.childCount()): # type: ignore
                item = top.child(x)
                if item:
                    includeType = Config.strToIncludeType(item.text(_UI_EDITBUILD_TREE_COL_TYPE))
                    include.append(Config.IncludeItem(includeType, item.text(_UI_EDITBUILD_TREE_COL_NAME), Config.IncludeUse.Include))

        top = self.Ui_EditBuild.includeTree.topLevelItem(2)
        if top:
            for x in range(top.childCount()): # type: ignore
                item = top.child(x)
                if item:
                    includeType = Config.strToIncludeType(item.text(_UI_EDITBUILD_TREE_COL_TYPE))
                    includeUse = Config.strToIncludeUse(item.text(_UI_EDITBUILD_TREE_COL_USE))
                    include.append(Config.IncludeItem(includeType, item.text(_UI_EDITBUILD_TREE_COL_NAME), includeUse))

        return Config.Build(enable, output, preset, include)

    def __Ui_EditBuild_Validate(self) -> None:
        build = self.__Ui_EditBuild_GetBuild()
        self.__validateBuilds(build=build, checkIgnored=False)

    def __Ui_EditBuild_Rejected(self) -> None:
        self.__EditBuild_Index = None
        self.Ui_EditBuild = None
        self.Ui_EditBuild_Dialog = None

    def __Ui_EditBuild_Accepted(self) -> None:
        build = self.__Ui_EditBuild_GetBuild()

        select = self.__EditBuild_Index
        if select is None:
            logging.error("Failed to update build")
            return

        if select == -1:
            select = len(self.builds)
            self.builds.append(build)
        else:
            self.builds[select] = build

        self.__Ui_BSBB_Populate()
        index = self.Ui_BSBB.buildsTable.indexFromItem(
            self.Ui_BSBB.buildsTable.item(select, 0))

        model = self.Ui_BSBB.buildsTable.selectionModel()
        if model is None:
            raise AttributeError
        model.select(
            index, QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        self.__Ui_BSBB_MadeChange()

        self.__EditBuild_Index = None
        self.Ui_EditBuild = None
        self.Ui_EditBuild_Dialog = None

    def __Ui_EditBuild_SaveUI(self):
        if not self.Ui_EditBuild_Dialog or not self.Ui_EditBuild:
            return

        self.uiconfig.setValue("EditBuild/Dialog", self.Ui_EditBuild_Dialog.saveGeometry())
        self.uiconfig.setValue("EditBuild/Splitter", self.Ui_EditBuild.splitter.saveState())

    def __Ui_EditBuild_LoadUI(self):
        if not self.Ui_EditBuild_Dialog or not self.Ui_EditBuild:
            return

        self.Ui_EditBuild_Dialog.restoreGeometry(self.uiconfig.value("EditBuild/Dialog", type=QByteArray))
        self.Ui_EditBuild.splitter.restoreState(self.uiconfig.value("EditBuild/Splitter", type=QByteArray))

    #
    # Settings window related stuff
    #
    def __Ui_Settings_Display(self):
        self.Ui_Settings_Dialog = QDialog()
        self.Ui_Settings = Ui_Settings()
        self.Ui_Settings.setupUi(self.Ui_Settings_Dialog)

        self.Ui_Settings_Dialog.accepted.connect(self.__Ui_Settings_Save)
        self.Ui_Settings.exportDataButton.clicked.connect(self.__Ui_Settings_ExportData)
        self.Ui_Settings.locateButton.clicked.connect(self.__Ui_Settings_Locate)

        # Populate current values
        self.Ui_Settings.deleteMeshesCheckBox.setChecked(
            self.config.deleteMeshes)

        match self.config.priorities:
            case [Config.PriorityOrder.BUILDSELECTION, Config.PriorityOrder.INCLUDEORDER]:
                priorty = 0
            case [Config.PriorityOrder.INCLUDEORDER, Config.PriorityOrder.BUILDSELECTION]:
                priorty = 1
            case [Config.PriorityOrder.INCLUDEORDER]:
                priorty = 2
            case _:
                logging.error(f"Unknown priority order: {self.config.priorities}. Defaulting value")
                priorty = 1

        self.Ui_Settings.priorityComboBox.setCurrentIndex(priorty)

        self.Ui_Settings.onBuildCheckConflictsCheckBox.setChecked(
            self.config.onBuildCheckConflicts)
        self.Ui_Settings.onBuildCheckIgnoredCheckBox.setChecked(
            self.config.onBuildCheckIgnored)
        self.Ui_Settings.autoCloseCheckBox.setChecked(self.config.autoClose)
        self.Ui_Settings.showSourcesCheckBox.setChecked(
            self.config.showSources)

        self.Ui_Settings.outputComboBox.currentIndexChanged.connect(
            self.__Ui_Settings_OutputChange)
        self.__addOutputsToComboBox(self.Ui_Settings.outputComboBox,
                                    value=self.config.output)

        self.Ui_Settings_Dialog.show()

    def __Ui_Settings_OutputChange(self):
        self.__comboboxMatchStyle(self.Ui_Settings.outputComboBox)

    def __Ui_Settings_Save(self):
        self.__Ui_BSBB_MadeChange()
        self.config.deleteMeshes = self.Ui_Settings.deleteMeshesCheckBox.isChecked(
        )

        match self.Ui_Settings.priorityComboBox.currentIndex():
            case 0:
                self.config.priorities = [Config.PriorityOrder.BUILDSELECTION, Config.PriorityOrder.INCLUDEORDER]
            case 1:
                self.config.priorities = [Config.PriorityOrder.INCLUDEORDER, Config.PriorityOrder.BUILDSELECTION]
            case 2:
                self.config.priorities = [Config.PriorityOrder.INCLUDEORDER]

        self.config.onBuildCheckConflicts = self.Ui_Settings.onBuildCheckConflictsCheckBox.isChecked(
        )
        self.config.onBuildCheckIgnored = self.Ui_Settings.onBuildCheckIgnoredCheckBox.isChecked(
        )
        self.config.autoClose = self.Ui_Settings.autoCloseCheckBox.isChecked()
        self.config.showSources = self.Ui_Settings.showSourcesCheckBox.isChecked(
        )
        self.config.output = self.Ui_Settings.outputComboBox.currentText()

    def __Ui_Settings_ExportData(self):
        fileName = QFileDialog.getSaveFileName(self.__parentWidget, "Export To", filter="Text Files (*.txt)")[0]
        if fileName == "":
            return

        with open(fileName, "w") as f:
            self.BodySlide.print_all_slider_set_details(file=f, include_sources=self.config.showSources)

    def __Ui_Settings_Locate(self):
        subprocess.Popen(f'explorer /select,"{PureWindowsPath(os.path.join(self.__organizer.getPluginDataPath(), 'BSBB_Config.xml')).__fspath__()}"')
