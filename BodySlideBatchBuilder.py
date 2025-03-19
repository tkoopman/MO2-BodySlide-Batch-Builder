# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# Requires: 
#  - MO2 of course
#  - BodySlide installed in MO2 under mods folder
#  - BodySlide Executable registered in MO2 as "BodySlide x64"
#
# Description:
#  - This plugin for MO2 will run BodySlide for up to 5 different groups, presets, and output mods.
#
# Installation:
#  - Place this file in the MO2/plugins/ folder.
#
# Settings:
#  - In MO2, go to the settings for this plugin and configure the builds you want to run.
#  - Default settings are for HIMBO and TNG using HIMBO Zero for OBody and 3BA using - Zeroed Sliders -.
#  - Default output mod is "Output - Bodyslide". 
#    Either make sure you have created this or changed in settings to the output mod name you want to use.
#  - When using clear output mod, the meshes folder will be deleted from output mod before running the build. 
#    If multiple builds going to same output mod, only the first build should clear the output mod.
#
# Notes:
#  - This plugin does modify the Config.xml file in the BodySlide mod folder. 
#  - It will create a backup of the Config.xml file before running the builds, and restore it back on completion.

import mobase  # type: ignore
import os
import logging
import shutil

from pathlib import PureWindowsPath
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLayout, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from xml.etree import ElementTree as et
from datetime import datetime

class QTextEditLogger(logging.Handler):
    def __init__(self):
        super().__init__()
        self.widget = QPlainTextEdit()
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)

class PrechecksWindow(QDialog):
    startAction = pyqtSignal()
    closeAction = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setWindowTitle("Batch BodySlide Builder")
        self.resize(600, 400)
        self.__layout = QVBoxLayout()
        self.__layout.layout = QLayout.SizeConstraint.SetMaximumSize
  
        logs = QTextEditLogger()
        self.__layout.addWidget(logs.widget)

        self.startButton = QPushButton("Build...")
        self.startButton.setEnabled(False)
        closeButton = QPushButton("Close")

        buttonHolder = QWidget()
        buttonLayout = QHBoxLayout(buttonHolder)

        buttonLayout.addWidget(self.startButton)
        buttonLayout.addWidget(closeButton)

        self.__layout.addWidget(buttonHolder)

        self.setLayout(self.__layout)

        self.startButton.clicked.connect(self.__startPressed)
        closeButton.clicked.connect(self.__closePressed)
  
        logging.getLogger().addHandler(logs)
        logging.getLogger().setLevel(logging.DEBUG)
        
        logging.info('Running Pre-checks...')

    def __closePressed(self) -> None:
        self.closeAction.emit()
        self.close()

    def __startPressed(self) -> None:
        self.startButton.setEnabled(False)
        self.startAction.emit()


class CleanerPlugin(mobase.IPluginTool):
    def __init__(self) -> None:
        super().__init__()
        self.__canceled = False

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self.__organizer = organizer
        return True

    def name(self) -> str:
        return "BatchBodySlideBuilder"

    def author(self) -> str:
        return "GoriRed"

    def displayName(self) -> str:
        return "BodySlide Batch Builder"

    def description(self) -> str:
        return f'Run BodySlide build for up to 5 times for different Groups, Preset, Output Mod combinations.'

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 1, 0)

    def isActive(self) -> mobase.MoVariant:
        return self.__organizer.pluginSetting(self.name(), "enabled")

    def tooltip(self) -> str:
        return "Run BodySlider Batch Builder"

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "Enable this plugin", True),
            mobase.PluginSetting("auto_start", "Auto start if no errors in pre-checks", True),
            mobase.PluginSetting("auto_close", "Auto close if no errors during build", False),
            mobase.PluginSetting("keep_backups", "Number of BodySlider Config.xml backups to keep in overwrites folder. Set to 0 to keep none unless process aborted.", 0),
            mobase.PluginSetting("warn_batch_build_override", "Display window in BodySlide to select which build to use when multiple for same mesh.", False),
   
            mobase.PluginSetting("build1_enabled",        "Build 1: Enabled",          True),
            mobase.PluginSetting("build1_output",         "Build 1: Output Mod",       "Output - Bodyslide"),
            mobase.PluginSetting("build1_output_clear",   "Build 1: Clear Output Mod", True),
            mobase.PluginSetting("build1_preset",         "Build 1: Preset",           "HIMBO Zero for OBody"),
            mobase.PluginSetting("build1_groups",         "Build 1: Groups",           "HIMBO, TNG"),
   
            mobase.PluginSetting("build2_enabled",        "Build 2: Enabled",          True),
            mobase.PluginSetting("build2_output",         "Build 2: Output Mod",       "Output - Bodyslide"),
            mobase.PluginSetting("build2_output_clear",   "Build 2: Clear Output Mod", False),
            mobase.PluginSetting("build2_preset",         "Build 2: Preset",           "- Zeroed Sliders -"),
            mobase.PluginSetting("build2_groups",         "Build 2: Groups",           "3BA"),
   
            mobase.PluginSetting("build3_enabled",        "Build 3: Enabled",          False),
            mobase.PluginSetting("build3_output",         "Build 3: Output Mod",       "Output - Bodyslide"),
            mobase.PluginSetting("build3_preset",         "Build 3: Preset",           ""),
            mobase.PluginSetting("build3_groups",         "Build 3: Groups",           ""),
            mobase.PluginSetting("build3_output_clear",   "Build 3: Clear Output Mod", False),
   
            mobase.PluginSetting("build4_enabled",        "Build 4: Enabled",          False),
            mobase.PluginSetting("build4_output",         "Build 4: Output Mod",       "Output - Bodyslide"),
            mobase.PluginSetting("build4_output_clear",   "Build 4: Clear Output Mod", False),
            mobase.PluginSetting("build4_preset",         "Build 4: Preset",           ""),
            mobase.PluginSetting("build4_groups",         "Build 4: Groups",           ""),
   
            mobase.PluginSetting("build5_enabled",        "Build 5: Enabled",          False),
            mobase.PluginSetting("build5_output",         "Build 5: Output Mod",       "Output - Bodyslide"),
            mobase.PluginSetting("build5_output_clear",   "Build 5: Clear Output Mod", False),
            mobase.PluginSetting("build5_preset",         "Build 5: Preset",           ""),
            mobase.PluginSetting("build5_groups",         "Build 5: Groups",           ""),
        ]

    def icon(self) -> QIcon:
        return QIcon()

    def setParentWidget(self, parent: QWidget) -> None:
        self.__parentWidget = parent

    def display(self) -> None:
        self.__canceled = False
        self.__dialog = PrechecksWindow(self.__parentWidget)

        hasEnabled = False
        hasError = False

        self.__bsXmlFile = self.__organizer.findFiles("CalienteTools/BodySlide", "Config.xml")[-1]
        if not self.__bsXmlFile:
            hasError = True
            logging.error("Unable to find BodySlide Config.xml. Make sure it is installed in MO2.")

        bsXML = et.parse(self.__bsXmlFile)
        if bsXML.find("TargetGame") is None:
            hasError = True
            logging.error("Run BodySlide manually first, to create config.")

        keep = self.__organizer.pluginSetting(self.name(), "keep_backups")
        if not isinstance(keep, int) or keep < 0:
            hasError = True
            logging.error("Keep backups must be a positive integer or zero.")

        for i in range(1, 6):
            if self.__organizer.pluginSetting(self.name(), f"build{i}_enabled"):
                hasEnabled = True
                output = self.__organizer.modList().getMod(self.__organizer.pluginSetting(self.name(), f"build{i}_output"))
                if not output:
                    hasError = True
                    logging.error(f"Build {i}: failed. Missing output mod {self.__organizer.pluginSetting(self.name(), f"build{i}_output")}")
                    continue

                logging.info(f"Build {i}: passed")
                if self.__organizer.pluginSetting(self.name(), f"build{i}_output_clear"):
                    logging.debug(f"    Output: {output.name()} - Meshes folder will be deleted prior to build!")
                else:
                    logging.debug(f"    Output: {output.name()}")

                logging.debug(f"    Preset: {self.__organizer.pluginSetting(self.name(), f'build{i}_preset')}")
                logging.debug(f"    Groups: {self.__organizer.pluginSetting(self.name(), f'build{i}_groups')}")
                logging.debug("")
            else:
                logging.info(f"Build {i}: disabled")

        self.__dialog.startAction.connect(self.__start)
        self.__dialog.closeAction.connect(self.__close)
        self.__dialog.open()
                        
        if (hasEnabled and not hasError):
            if self.__organizer.pluginSetting(self.name(), f"auto_start"):
                logging.info(f"Auto starting builds...")
                self.runBatches()
            else:
                self.__dialog.startButton.setEnabled(True)
        

    def __close(self) -> None:
        self.__canceled = True
        
    def __start(self) -> None:
        self.runBatches()

    def runBatches(self) -> None:
        # create backup of BodySlide config
        backup = f"{self.__organizer.overwritePath()}/CalienteTools/BodySlide/Config.xml.{datetime.now().strftime("%Y%m%d_%H%M%S")}"
        os.makedirs(os.path.dirname(backup), exist_ok=True) 
        shutil.copy(self.__bsXmlFile, backup)
        
        for i in range(1, 6):
            if self.__canceled:
                logging.info("canceled")
                break
            
            if self.__organizer.pluginSetting(self.name(), f"build{i}_enabled"):
                output = self.__organizer.modList().getMod(self.__organizer.pluginSetting(self.name(), f"build{i}_output"))
                if not output:
                    continue

                if self.__organizer.pluginSetting(self.name(), f"build{i}_output_clear"):
                    logging.info(f"Build {i}: Clearing output mod")
                    shutil.rmtree(f"{output.absolutePath()}/meshes", ignore_errors=True)

                
                logging.info(f"Build {i}: Running BodySlide...")
                
                bsXML = et.parse(backup)
                bsXML.find("OutputDataPath").text = PureWindowsPath(output.absolutePath()).__fspath__() + "\\"
                bsXML.find("WarnBatchBuildOverride").text = str(self.__organizer.pluginSetting(self.name(), "warn_batch_build_override")).lower()
                bsXML.write(self.__bsXmlFile)

                args = list([
                    f"--groupbuild=\"{self.__organizer.pluginSetting(self.name(), f'build{i}_groups')}\"",
                    f"--preset=\"{self.__organizer.pluginSetting(self.name(), f'build{i}_preset')}\"",
                    "--trimorphs",
                ])
                
                exe = self.__organizer.startApplication("BodySlide x64", args=args)
                if exe == mobase.INVALID_HANDLE_VALUE:
                    QMessageBox.critical(
                        self.__parentWidget,
                        "Failed to start BodySlide",
                        f'Make sure BodySlide is registered as an executable (Ctrl+E) with the name "BodySlide x64"',
                    )
                    return

                waitResult, exitCode = self.__organizer.waitForApplication(exe, False)
                if not waitResult:
                    logging.warning("canceled")
                    self.__canceled = True
                    break
                elif exitCode != 0:
                    logging.error(f"Exit Code: {exitCode}")
                    self.__canceled = True
                    break

        # Restore backup
        shutil.copy(backup, self.__bsXmlFile)

        # Delete old backups
        backups = sorted(
            [f for f in os.listdir(f"{self.__organizer.overwritePath()}/CalienteTools/BodySlide/") if f.startswith("Config.xml.")],
            key=lambda f: os.path.getctime(os.path.join(f"{self.__organizer.overwritePath()}/CalienteTools/BodySlide/", f))
        )

        keep = self.__organizer.pluginSetting(self.name(), "keep_backups")
        
        if keep > 0:
            keep = keep * -1
            backups = backups[:keep]

        for f in backups:
            logging.debug(f"Deleting backup: {f}")
            os.remove(os.path.join(f"{self.__organizer.overwritePath()}/CalienteTools/BodySlide/", f))

        # Delete empty folders
        delete_empty_folders(self.__organizer.overwritePath())

        logging.info("Finished")

        if not self.__canceled and self.__organizer.pluginSetting(self.name(), "auto_close"):
         	self.__dialog.close()

def delete_empty_folders(root) -> None:
    deleted = set()
    
    for current_dir, subdirs, files in os.walk(root, topdown=False):
        still_has_subdirs = False
        for subdir in subdirs:
            if os.path.join(current_dir, subdir) not in deleted:
                still_has_subdirs = True
                break
    
        if not any(files) and not still_has_subdirs:
            os.rmdir(current_dir)
            deleted.add(current_dir)

    return deleted


def createPlugin() -> mobase.IPluginTool:
    return CleanerPlugin()