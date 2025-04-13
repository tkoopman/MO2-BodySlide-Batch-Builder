# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

import logging
import os
from typing import Any
import mobase  # type: ignore
import xml.etree.ElementTree as ET

from abc import abstractmethod
from enum import Enum


# Defines the priority order for selecting slider sets when multiple exist for the same output.
# GROUP: Select the first slider set from the first group in the list that is exists in.
# BUILDSELECTION: Use BuildSelection.xml
# FIRST: Use the first slider set found for the output. Guaranteed to return a single match.
# If after all priority orders are checked and still multiple values, error will be raised.
# So if you want top prevent an error, make sure FIRST is the last in the list.
class PriorityOrder(Enum):
    INCLUDEORDER = 1
    BUILDSELECTION = 2
    FIRST = 3


class IncludeType(Enum):
    GROUP = 1
    SLIDERSET = 2
    SOURCE = 3
    CONTAINS = 4
    REGEX = 5


class IncludeUse(Enum):
    Exclude = 0b001
    Include = 0b010
    IncludeKeep = 0b110
    Keep = 0b100
    Remove = 0b101


class IncludeItem(object):

    def __init__(self, type: IncludeType, name: str, use: IncludeUse):
        self.type = type
        self.name = name
        self.use = use

    def typeAsStr(self) -> str:
        return includeTypeToStr(self.type)

    def useAsStr(self) -> str:
        return includeUseToStr(self.use)

    def isUsePriority(self) -> bool:
        return (self.use.value & 0b100) == 0b100

    def isUseAdd(self) -> bool:
        return (self.use.value & IncludeUse.Include.value) == IncludeUse.Include.value

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Item({self.type}, '{self.name}')"

    def __eq__(self, other:Any) -> bool:
        if isinstance(other, IncludeItem):
            return self.type == other.type and self.name.casefold(
            ) == other.name.casefold()

        if isinstance(other, str):
            return self.name.casefold() == other.casefold()

        return False

    def __hash__(self):
        return hash((self.type, self.name.casefold()))


class Output(object):

    @abstractmethod
    def __init__(self, output: str):
        self.output = output

    def getOutputPathorOverwrite(self, mo: mobase.IOrganizer) -> str:
        output = self.getOutputPath(mo)
        return mo.overwritePath() if output is None else output

    def getOutputPath(self, mo: mobase.IOrganizer) -> str | None:
        if self.output.casefold() == 'overwrite':
            return mo.overwritePath()

        mod = mo.modList().getMod(self.output)
        return None if mod is None else mod.absolutePath() # type: ignore

    def __eq__(self, other:Any) -> bool:
        if isinstance(other, Output):
            return self.output.casefold() == other.output.casefold()

        if isinstance(other, str):
            return self.output.casefold() == other.casefold()

        return False

    def __hash__(self):
        return hash(self.output.casefold())


class Build(Output):

    def __init__(self, enable: bool, output: str, preset: str,
                 include: list[IncludeItem]):
        super().__init__(output)
        self.enable: bool = enable
        self.preset: str = preset
        self.include: list[IncludeItem] = include

    def includeAsStr(self) -> str:
        result = list[str]()
        for include in self.include:
            match include.use:
                case IncludeUse.Exclude:
                    i = '!'
                case IncludeUse.Remove:
                    i = '-'
                case IncludeUse.Keep:
                    i = '+'
                case IncludeUse.IncludeKeep:
                    i = '++'
                case _:
                    i = ''
            i += include.name
            result.append(i)
        return ','.join(result)

    def clone(self) -> 'Build':
        return Build(self.enable, self.output, self.preset, list(self.include))

    def removeInclude(self, itemType: IncludeType, name: str) -> bool:
        for x in range(len(self.include)):
            include = self.include[x]
            if itemType == include.type and name == include.name:
                self.include.pop(x)
                return True
        return False

    def __eq__(self, other:Any) -> bool:
        if isinstance(other, Build):
            return self.output.casefold() == other.output.casefold(
            ) and self.enable == other.enable and self.preset == other.preset and len(
                self.include) == len(other.include) and all(
                    self.include[x] == other.include[x]
                    for x in range(len(self.include)))

        return False

    def __hash__(self):
        return hash((self.output.casefold(), self.preset, self.enable))


class Global(Output):

    def __init__(self, deleteMeshes: bool, priorities: list[PriorityOrder],
                 onBuildCheckConflicts: bool, onBuildCheckIgnored: bool,
                 autoClose: bool, showSources: bool, output: str):
        super().__init__(output)
        self.deleteMeshes = deleteMeshes
        self.priorities = priorities
        self.onBuildCheckConflicts = onBuildCheckConflicts
        self.onBuildCheckIgnored = onBuildCheckIgnored
        self.autoClose = autoClose
        self.showSources = showSources


def convertToBool(value:Any, *, default: bool = False) -> bool:
    return value.casefold() in ['true', 'yes', '1'] if isinstance(
        value, str) else default


def strToPriorities(value: str) -> list[PriorityOrder]:
    values = [v.strip() for v in value.split(",")]
    priorities = list[PriorityOrder]()
    for v in values:
        match v.casefold():
            case 'group':
                priorities.append(PriorityOrder.INCLUDEORDER)
            case 'includeorder':
                priorities.append(PriorityOrder.INCLUDEORDER)
            case 'buildselection':
                priorities.append(PriorityOrder.BUILDSELECTION)
            case 'first':
                priorities.append(PriorityOrder.FIRST)
            case _:
                raise BaseException(f"Unknown priority: {v}")

    return priorities


def includeTypeToStr(itemType: IncludeType) -> str:
    match itemType:
        case IncludeType.GROUP:
            return 'Group'
        case IncludeType.SLIDERSET:
            return 'Outfit or Body'
        case IncludeType.SOURCE:
            return 'Source'
        case IncludeType.CONTAINS:
            return 'Contains'
        case IncludeType.REGEX:
            return 'Regex'


def strToIncludeType(itemType: str | None) -> IncludeType:
    if not itemType:
        return IncludeType.SLIDERSET

    itemType = itemType.casefold()
    match itemType:
        case 'group':
            return IncludeType.GROUP
        case 'source':
            return IncludeType.SOURCE
        case 'contains':
            return IncludeType.CONTAINS
        case 'regex':
            return IncludeType.REGEX
        case _:
            return IncludeType.SLIDERSET

def includeUseToStr(itemUse: IncludeUse) -> str:
    match itemUse:
        case IncludeUse.Exclude:
            return 'Exclude'
        case IncludeUse.Include:
            return 'Include'
        case IncludeUse.IncludeKeep:
            return 'Include & Keep'
        case IncludeUse.Keep:
            return 'Keep'
        case IncludeUse.Remove:
            return 'Remove'

def strToIncludeUse(itemUse: str | None) -> IncludeUse:
    if not itemUse:
        return IncludeUse.IncludeKeep

    itemUse = itemUse.casefold()
    match itemUse:
        case 'exclude':
            return IncludeUse.Exclude
        case 'include':
            return IncludeUse.Include
        case 'keep':
            return IncludeUse.Keep
        case 'remove':
            return IncludeUse.Remove
        case _:
            return IncludeUse.IncludeKeep


def loadConfig(file_path: str) -> tuple[Global, list[Build]]:
    builds = list[Build]()
    config = Global(
        deleteMeshes=False,
        priorities=[PriorityOrder.INCLUDEORDER, PriorityOrder.BUILDSELECTION],
        onBuildCheckConflicts=True,
        onBuildCheckIgnored=False,
        autoClose=True,
        showSources=False,
        output='Output - BodySlide')

    if not os.path.exists(file_path):
        # Create default builds
        builds.append(
            Build(True, 'Output - BodySlide', 'HIMBO Zero for OBody',
                  [IncludeItem(IncludeType.GROUP, 'HIMBO', IncludeUse.IncludeKeep),
                   IncludeItem(IncludeType.GROUP, 'TNG', IncludeUse.IncludeKeep)]))
        builds.append(
            Build(True, 'Output - BodySlide', '- Zeroed Sliders -', [
                IncludeItem(IncludeType.GROUP, '3BA', IncludeUse.IncludeKeep),
                IncludeItem(IncludeType.GROUP, '3BBB', IncludeUse.IncludeKeep),
                IncludeItem(IncludeType.GROUP, 'CBBE', IncludeUse.IncludeKeep)
            ]))
        return config, builds

    tree = ET.parse(file_path)
    root = tree.getroot()

    e = root.find('Global')
    if isinstance(e, ET.Element):
        for setting in e.findall('Setting'):
            name = setting.get('name')
            value = str(setting.get('value'))
            match name:
                case "deleteMeshes":
                    config.deleteMeshes = convertToBool(value)
                case "priorities":
                    config.priorities = strToPriorities(value)
                case "onBuildCheckConflicts":
                    config.onBuildCheckConflicts = convertToBool(value)
                case "onBuildCheckIgnored":
                    config.onBuildCheckIgnored = convertToBool(value)
                case "autoClose":
                    config.autoClose = convertToBool(value)
                case "showSources":
                    config.showSources = convertToBool(value)
                case "output":
                    config.output = value
                case _:
                    logging.warning(
                        f"Unknown setting found in config: {name}. Will be removed on next save."
                    )

    for build in root.findall('Build'):
        enable = convertToBool(build.get('enable'))
        output = build.get('output')
        preset = build.get('preset')
        includes = list[IncludeItem]()
        for include in build.findall('Include'):
            includeType = strToIncludeType(include.get('type'))
            name = include.get('name')
            includeUse = strToIncludeUse(include.get('use'))

            if not isinstance(name, str):
                raise ValueError('Error reading in build from bsbb_config.xml')

            includes.append(IncludeItem(includeType, name, includeUse))

        if not isinstance(output, str) or not isinstance(preset, str):
            raise ValueError('Error reading in build from bsbb_config.xml')

        builds.append(Build(enable, output, preset, includes))

    return config, builds


def saveConfig(globalConfig: Global, builds: list[Build], file_path: str):
    root = ET.Element('Config')
    tree = ET.ElementTree(root)

    config = ET.Element('Global')
    config.append(
        ET.Element('Setting',
                   name='deleteMeshes',
                   value=str(globalConfig.deleteMeshes)))
    config.append(
        ET.Element('Setting',
                   name='priorities',
                   value=', '.join([p.name for p in globalConfig.priorities])))
    config.append(
        ET.Element('Setting',
                   name='onBuildCheckConflicts',
                   value=str(globalConfig.onBuildCheckConflicts)))
    config.append(
        ET.Element('Setting',
                   name='onBuildCheckIgnored',
                   value=str(globalConfig.onBuildCheckIgnored)))
    config.append(
        ET.Element('Setting',
                   name='autoClose',
                   value=str(globalConfig.autoClose)))
    config.append(
        ET.Element('Setting',
                   name='showSources',
                   value=str(globalConfig.showSources)))
    config.append(
        ET.Element('Setting', name='output', value=globalConfig.output))

    root.append(config)

    for build in builds:
        build_element = ET.Element('Build',
                                   enable=str(build.enable),
                                   output=build.output,
                                   preset=build.preset)
        for include in build.include:
            if include.type == IncludeType.SLIDERSET and include.use == IncludeUse.IncludeKeep:
                e = ET.Element('Include',
                               name=include.name)
            elif include.type == IncludeType.SLIDERSET:
                e = ET.Element('Include',
                               name=include.name,
                               use=includeUseToStr(include.use))
            elif include.use == IncludeUse.IncludeKeep:
                e = ET.Element('Include',
                               name=include.name,
                               type=includeTypeToStr(include.type))
            else:
                e = ET.Element('Include',
                               name=include.name,
                               type=includeTypeToStr(include.type),
                               use=includeUseToStr(include.use))

            build_element.append(e)

        root.append(build_element)

    ET.indent(tree, '    ')
    tree.write(file_path, encoding='UTF-8', xml_declaration=True)