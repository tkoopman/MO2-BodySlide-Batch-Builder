# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

import logging
import os
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
    GROUP = 1
    BUILDSELECTION = 2
    FIRST = 3


class ItemType(Enum):
    GROUP = 1
    SLIDERSET = 2
    MESH = 3
    SOURCE = 4


class Item(object):

    def __init__(self, type: ItemType, name: str):
        self.type = type
        self.name = name

    def typeAsStr(self) -> str:
        return itemTypeToStr(self.type)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Item({self.type}, '{self.name}')"

    def __eq__(self, other) -> bool:
        if isinstance(other, Item):
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
        return None if mod is None else mod.absolutePath()

    def __eq__(self, other):
        if isinstance(other, Output):
            return self.output.casefold() == other.output.casefold()

        if isinstance(other, str):
            return self.output.casefold() == other.casefold()

        return False

    def __hash__(self):
        return hash(self.output.casefold())


class Build(Output):

    def __init__(self, enable: bool, output: str, preset: str,
                 include: list[Item]):
        super().__init__(output)
        self.enable: bool = enable
        self.preset: str = preset
        self.include: list[Item] = include

    def includeAsStr(self) -> str:
        return ','.join([include.name for include in self.include])

    def clone(self) -> 'Build':
        return Build(self.enable, self.output, self.preset, list(self.include))

    def removeInclude(self, itemType: ItemType, name: str) -> bool:
        for x in range(len(self.include)):
            item = self.include[x]
            if itemType == item.type and name == item.name:
                self.include.pop(x)
                return True
        return False

    def __eq__(self, other):
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


def convertToBool(value, *, default: bool = False) -> bool:
    return value.casefold() in ['true', 'yes', '1'] if isinstance(
        value, str) else default


def convertToPriorities(value: str) -> list[PriorityOrder]:
    values = [v.strip() for v in value.split(",")]
    priorities = list[PriorityOrder]()
    for v in values:
        match v.casefold():
            case 'group':
                priorities.append(PriorityOrder.GROUP)
            case 'buildselection':
                priorities.append(PriorityOrder.BUILDSELECTION)
            case 'first':
                priorities.append(PriorityOrder.FIRST)

    return priorities


def itemTypeToStr(itemType: ItemType) -> str:
    match itemType:
        case ItemType.GROUP:
            return 'Group'
        case ItemType.SLIDERSET:
            return 'Outfit or Body'
        case ItemType.MESH:
            return 'Mesh'
        case ItemType.SOURCE:
            return 'Source'


def strToItemType(itemType: str) -> ItemType:
    itemType = itemType.casefold()
    match itemType:
        case 'group':
            return ItemType.GROUP
        case 'outfit or body':
            return ItemType.SLIDERSET
        case 'mesh':
            return ItemType.MESH
        case 'source':
            return ItemType.SOURCE
        case 'src':
            return ItemType.SOURCE
        case _:
            if 'outfit' in itemType or 'body' in itemType:
                return ItemType.SLIDERSET

            raise ValueError(f"Invalid item type: {itemType}")


def loadConfig(file_path: str) -> tuple[Global, list[Build]]:
    builds = list[Build]()
    config = Global(
        deleteMeshes=False,
        priorities=[PriorityOrder.GROUP, PriorityOrder.BUILDSELECTION],
        onBuildCheckConflicts=True,
        onBuildCheckIgnored=False,
        autoClose=True,
        showSources=False,
        output='Output - BodySlide')

    if not os.path.exists(file_path):
        # Create default builds
        builds.append(
            Build(True, 'Output - BodySlide', 'HIMBO Zero for OBody',
                  [Item(ItemType.GROUP, 'HIMBO'),
                   Item(ItemType.GROUP, 'TNG')]))
        builds.append(
            Build(True, 'Output - BodySlide', '- Zeroed Sliders -', [
                Item(ItemType.GROUP, '3BA'),
                Item(ItemType.GROUP, '3BBB'),
                Item(ItemType.GROUP, 'CBBE')
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
                    config.priorities = convertToPriorities(value)
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
        include = list[Item]()
        for item in build.findall('Include'):
            itemType = item.get('type')
            name = item.get('name')

            if not isinstance(name, str) or not isinstance(itemType, str):
                raise ValueError('Error reading in build from bsbb_config.xml')

            include.append(Item(strToItemType(itemType), name))

        if not isinstance(output, str) or not isinstance(preset, str):
            raise ValueError('Error reading in build from bsbb_config.xml')

        builds.append(Build(enable, output, preset, include))

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
            e = ET.Element('Include',
                           type=itemTypeToStr(include.type),
                           name=include.name)
            build_element.append(e)

        root.append(build_element)

    ET.indent(tree, '    ')
    tree.write(file_path, encoding='UTF-8', xml_declaration=True)