# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

import logging
import re
import mobase  # type: ignore
import os
import sys
import xml.etree.ElementTree as ET

from collections.abc import Callable, Sequence

from BSBB import Config

class CaseInsensitive(str):
    def __eq__(self, other):
        if isinstance(other, str):
            return self.casefold() == other.casefold()

        return False

    def __hash__(self):
        return hash((self.casefold()))

class SliderGroupMember(object):

    def __init__(self, name: str, source: str):
        self.name = name
        self.sources = list[str]()
        if not isinstance(source, CaseInsensitive):
            source = CaseInsensitive(source)
        self.sources.append(source)

    def __eq__(self, other):
        if isinstance(other, SliderGroupMember):
            return self.name.casefold() == other.name.casefold()

        if isinstance(other, str):
            return self.name.casefold() == other.casefold()

        return False

    def __hash__(self):
        return hash ((self.name.casefold()))

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"SliderGroupMember('{self.name}', [ {', '.join([f"'{source}'" for source in self.sources])} ] )"

class SliderSet(Config.Output):

    def __init__(self, name: str, in_buildselection: bool, output: str, source: str):
        super().__init__(output)
        self.name = name
        self.in_buildselection = in_buildselection
        self.source = source
        self.groups = list[CaseInsensitive]()

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"SliderSetDetails('{self.name}', {self.in_buildselection}, '{self.output}', '{self.source}')"

    def __eq__(self, other):
        if isinstance(other, SliderSet):
            return super().__eq__(other) and self.name.casefold() == other.name.casefold()
        return False

    def __hash__(self):
        return hash((self.output.casefold(), self.name.casefold()))

    def isMember(self, group: str | list[str]) -> bool:
        if isinstance(group, str):
            group = [group]

        for check in self.groups:
            if check in group:
                return True

        return False

    def groupsAsStr(self, groupMembers: dict[CaseInsensitive, list[SliderGroupMember]] | None = None) -> str:
        if groupMembers is None:
            return ", ".join(self.groups)

        result = list[str]()
        for group in self.groups:
            if group == 'Unassigned':
                result.append(f"{group}")
            else:
                sources = ", ".join([source for group in groupMembers[group] if self.name == group.name for source in group.sources])
                result.append(f"{group} ({sources})")

        return ", ".join(result)

    # Matches filter
    def IsMatch(self, bs: 'BodySlide', *, include: Config.IncludeItem | None = None, matchType: Config.IncludeType | None = None, matchName: str | None = None) -> bool:
        if include:
            matchType = include.type
            matchName = include.name

        if matchType is None or matchName is None:
            raise ValueError("Must supply matchType and matchName, or include")

        
        match matchType:
            case Config.IncludeType.GROUP:
                return CaseInsensitive(matchName) in self.groups
            case Config.IncludeType.SLIDERSET:
                return matchName.casefold() == self.name.casefold()
            case Config.IncludeType.SOURCE:
                match matchName[-4:]:
                    case '.xml':
                        matchName = CaseInsensitive(matchName)
                        for group in self.groups:
                            # Have to check as we added Unassigned group
                            if group in bs.sliderGroups:
                                g = bs.sliderGroups[group]
                                for member in g:
                                    if member.name == self.name:
                                        if matchName in member.sources:
                                            return True

                        return False
                    case '.osp':
                        return self.source.casefold() == matchName.casefold()
                    case _:
                        return False
            case Config.IncludeType.CONTAINS:
                return matchName.casefold() in self.name.casefold()
            case Config.IncludeType.REGEX:
                return re.match(pattern=matchName, string=self.name) is not None

class BodySlide:
    def __init__(self, body_slide_dir: str, *, get_file: Callable[[str|None, str, bool], str] | None = None, get_files: Callable[[str, str], list[str]|Sequence[str]] | None = None):
        if get_file is None:
            self.get_file = self.__get_file
        else:
            self.get_file = get_file

        if get_files is None:
            self.get_files = self.__get_files
        else:
            self.get_files = get_files

        self._body_slide_dir = body_slide_dir

    def load_configs(self, *, exclude_slide_group_files: list[str] = []):
        self.presets = self._read_slider_presets()
        self.sliderGroups = self._read_slider_groups(exclude_slide_group_files=exclude_slide_group_files)
        self.sliderSets = self._read_slider_sets()
        self.__populate_slider_set_groups()

    def __get_file(self, folder: str | None, filename: str, create: bool) -> str:
        path = self._body_slide_dir if folder is None else os.path.join(self._body_slide_dir, folder)
        return os.path.join(path, filename)

    def __get_files(self, folder: str, extension: str) -> list[str]:
        path = os.path.join(self._body_slide_dir, folder)
        return [os.path.join(path, filename) for filename in os.listdir(path) if filename.endswith(f".{extension}")]

    def _read_slider_presets(self) -> list[str]:
        presets = list[str]()

        for file_path in self.get_files('SliderPresets', 'xml'):
            tree = ET.parse(file_path)
            root = tree.getroot()
            for preset in root.findall('Preset'):
                name = str(preset.get('name'))
                presets.append(name)

        return presets

    # Read all slider groups from the BodySlide config directory.
    def _read_slider_groups(self, *, exclude_slide_group_files: list[str]) -> dict[CaseInsensitive, list[SliderGroupMember]]:
        group_members = dict[CaseInsensitive, list[SliderGroupMember]]()

        for file_path in self.get_files('SliderGroups', 'xml'):
            filename = os.path.basename(file_path)
            if filename not in exclude_slide_group_files:
                tree = ET.parse(file_path)
                root = tree.getroot()
                for group in root.findall('Group'):
                    group_name = CaseInsensitive(group.get('name'))
                    members = [SliderGroupMember(str(member.get('name')), filename) for member in group.findall('Member')]
                    if group_name not in group_members:
                        group_members[group_name] = members
                    else:
                        for member in members:
                            if member not in group_members[group_name]:
                                group_members[group_name].append(member)
                            else:
                                group_members[group_name][group_members[group_name].index(member)].sources.append(CaseInsensitive(filename))

        return group_members

    def _read_buildselection_xml(self) -> dict[str, str]:
        file_path = self.get_file(None, 'BuildSelection.xml', False)
        output = dict[str, str]()

        if not os.path.exists(file_path):
            return output

        tree = ET.parse(file_path)
        root = tree.getroot()
        for bs in root.findall('OutputChoice'):
            path = bs.get('path')
            choice = bs.get('choice')
            if not (isinstance(path, str) and isinstance(choice, str)):
                logging.warning('Error reading output choice')
                break

            output[path.casefold()] = choice

        return output

    # Read all slider sets from the BodySlide config directory.
    def _read_slider_sets(self) -> dict[str, SliderSet]:
        buildselection = self._read_buildselection_xml()
        slider_sets = {}
        for file_path in self.get_files('SliderSets', 'osp'):
            filename = os.path.basename(file_path)
            tree = ET.parse(file_path)
            root = tree.getroot()
            for slider_set in root.findall('SliderSet'):
                source_file = filename
                name = slider_set.get('name')
                output_path = slider_set.find('OutputPath')
                output_file = slider_set.find('OutputFile')
                if not isinstance(name, str) or not isinstance(output_path, ET.Element) or not isinstance(output_file, ET.Element) or not isinstance(output_path.text, str) or not isinstance(output_file.text, str):
                    logging.warning(f"Error reading SliderSet in {filename}")
                else:
                    output = os.path.join(output_path.text, output_file.text)
                    in_buildselection = output.casefold() in buildselection and buildselection[output.casefold()] == name

                    slider_sets[name] = SliderSet(name, in_buildselection, output, source_file)

        return slider_sets

    def __populate_slider_set_groups(self, *, add_unassigned_group = True):
        for group in self.sliderGroups:
            for member in self.sliderGroups[group]:
                if member.name in self.sliderSets:
                    self.sliderSets[member.name].groups.append(group)

        if add_unassigned_group:
            for slider_set in self.sliderSets.values():
                if len(slider_set.groups) == 0:
                    slider_set.groups.append(CaseInsensitive("Unassigned"))

    # Get all slider sets that are members of the specified groups.
    def GetMatchingSliderSets(self, includes: list[Config.IncludeItem] | Config.IncludeItem) -> dict[str, SliderSet]:
        output_sets = dict[str, SliderSet]()
        single = False
        if isinstance(includes, Config.IncludeItem):
            single = True
            includes = [includes]

        excludes = list[str]()
        if not single:
            for exclude in [exclude for exclude in includes if exclude.use == Config.IncludeUse.Exclude]:
                for name, ss in self.sliderSets.items():
                    if name not in excludes and ss.IsMatch(self, include=exclude):
                        excludes.append(name)

        for include in [include for include in includes if include.isUseAdd()]:
            for name, ss in self.sliderSets.items():
                if name not in excludes and ss.IsMatch(self, include=include):
                    output_sets[CaseInsensitive(name)] = ss

        return output_sets

    def SliderSetsByOutput(self, slider_sets: dict[str, SliderSet] | None = None) -> dict[str, list[SliderSet]]:
        output_groups = {}
        slider_sets = self.sliderSets if slider_sets is None else slider_sets
        for slider_set in slider_sets.values():
            if slider_set.output.casefold() not in output_groups:
                output_groups[slider_set.output.casefold()] = [slider_set]
            else:
                output_groups[slider_set.output.casefold()].append(slider_set)
        return output_groups

    # Reduce slider sets to only ones that appear in the first group in the list.
    # output_sets: list of sets for a single output path.
    def __priority_include_order_single(self, output_sets:list[SliderSet], include: Config.IncludeItem) -> list[SliderSet]:
        if len(output_sets) <= 1:
            return output_sets
            
        workingList = [ss for ss in output_sets if ss.IsMatch(self, include=include)]

        return workingList if workingList else output_sets


    def __priority_include_order(self, output_sets:list[SliderSet], includes: list[Config.IncludeItem]) -> list[SliderSet]:
        if len(output_sets) <= 1:
            return output_sets

        workingList = output_sets
        for include in [i for i in includes if i.isUsePriority()]:
            workingList = self.__priority_include_order_single(workingList, include)

            if len(workingList) == 1:
                return workingList

        return workingList

    # Reduce slider sets to only ones that appear BuildSelection.xml unless no sets exist in that file.
    # output_sets: list of sets for a single output path.
    def __priority_buildselection(self, output_sets:list[SliderSet]) -> list[SliderSet]:
        valid_sets = list[SliderSet]()
        for slider_set in output_sets:
            if slider_set.in_buildselection:
                valid_sets.append(slider_set)

        if len(valid_sets) == 0:
            return output_sets

        return valid_sets

    def get_silder_sets_filtered(self, groups: list[Config.IncludeItem], *, priorities: list[Config.PriorityOrder] = [Config.PriorityOrder.INCLUDEORDER, Config.PriorityOrder.BUILDSELECTION], allowConflicts: bool = False) -> list[SliderSet]:
        slider_sets_by_output = self.get_slider_sets_filtered_by_output(groups, priorities=priorities)

        # Check for any outputs with multiple slider sets still
        if not allowConflicts:
            foundMultiple = False
            for output in slider_sets_by_output:
                if len(slider_sets_by_output[output]) > 1:
                    foundMultiple = True
                    print(f"Multiple slider sets found for output: {output}")
                    for slider_set in slider_sets_by_output[output]:
                        print(f"   {slider_set.name} ({slider_set.groups})")

            if foundMultiple:
                raise ValueError("Multiple slider sets found for the same output. Unable to resolve.")

        return [sliderSet
                  for sliderSets in slider_sets_by_output.values()
                  for sliderSet in sliderSets
            ]

    def get_slider_sets_filtered_by_output(self, include: list[Config.IncludeItem], *, priorities: list[Config.PriorityOrder] = [Config.PriorityOrder.INCLUDEORDER, Config.PriorityOrder.BUILDSELECTION]) -> dict[str, list[SliderSet]]:
        slider_sets_by_output = self.SliderSetsByOutput(self.GetMatchingSliderSets(include))

        for priority in priorities:
            if priority == Config.PriorityOrder.INCLUDEORDER:
                for output in slider_sets_by_output:
                    if len(slider_sets_by_output[output]) > 1:
                        slider_sets_by_output[output] = self.__priority_include_order(slider_sets_by_output[output], include)

            elif priority == Config.PriorityOrder.BUILDSELECTION:
                for output in slider_sets_by_output:
                    if len(slider_sets_by_output[output]) > 1:
                        slider_sets_by_output[output] = self.__priority_buildselection(slider_sets_by_output[output])

            elif priority == Config.PriorityOrder.FIRST:
                for output in slider_sets_by_output:
                    slider_sets_by_output[output] = [slider_sets_by_output[output][0]]

        return slider_sets_by_output


    def create_slider_group(self, filename: str, name: str, members: list[str]):
        filename = self.get_file('SliderGroups', filename, True)

        if os.path.exists(filename):
            tree = ET.parse(filename)
            root = tree.getroot()
            # Remove existing group if it exists
            for group in root.findall('Group'):
                if group.get('name') == name:
                    root.remove(group)
                    break
        else:
            root = ET.Element('SliderGroups')
            tree = ET.ElementTree(root)

        group_element = ET.Element('Group', name=name)
        for member in sorted(members):
            member_element = ET.Element('Member', name=member)
            group_element.append(member_element)

        root.append(group_element)
        ET.indent(tree, '    ')
        tree.write(filename, encoding='UTF-8', xml_declaration=True)

    def __sort_by_output_then_name(self, e:SliderSet):
        return (e.output, e.name)

    def print_all_slider_set_details(self, *, include_sources = False, file=sys.stdout, sep = ' | ', group_sep = ', '):
        if include_sources:
            print("Output", "Name", "Source", "Groups [Group Sources]", file=file, sep=sep)
        else:
            print("Output", "Name", "Groups", file=file, sep=sep)

        for slider_set in sorted(self.sliderSets.values(), key=self.__sort_by_output_then_name):
            if not include_sources:
                print(slider_set.output, slider_set.name, group_sep.join(slider_set.groups), file=file, sep=sep)
                continue

            groups = list[str]()
            for group in slider_set.groups:
                if group == 'Unassigned':
                    groups.append(group)
                else:
                    memberships = self.sliderGroups[group]
                    sources = [member.sources for member in memberships if member.name == slider_set.name][0]
                    groups.append(f"{group} {sources}")

            print(slider_set.output, slider_set.name, slider_set.source, group_sep.join(groups), file=file, sep=sep)

class MO2BodySlide(BodySlide):
    
    def __init__(self, organizer: mobase.IOrganizer, *, body_slide_dir: str = 'CalienteTools/BodySlide'):
        super().__init__(body_slide_dir, get_file=self.__get_file, get_files=self.__get_files)
        self.__organizer = organizer
        self.CreateFilePath = organizer.overwritePath()

    def __get_file(self, folder: str | None, filename: str, create: bool) -> str:
        path = self._body_slide_dir if folder is None else f"{self._body_slide_dir}/{folder}"
        files = self.__organizer.findFiles(self._body_slide_dir, filename)
        if files:
            return files[-1]

        if not create:
            raise FileNotFoundError(f"Unable to find {filename}")

        path = os.path.join(self.CreateFilePath, path)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)

        return os.path.join(path, filename)


    def __get_files(self, folder: str, extension: str) -> Sequence[str]:
        path = f"{self._body_slide_dir}/{folder}"
        return self.__organizer.findFiles(path, f"*.{extension}")