# Created by GoriRed
# Version: 1.0
# License: CC-BY-NC
# https://github.com/tkoopman/MO2-BodySlide-Batch-Builder/

from .BSBBPlugin import BSBBPlugin
import mobase  # type: ignore

def createPlugin() -> mobase.IPluginTool:
    return BSBBPlugin()