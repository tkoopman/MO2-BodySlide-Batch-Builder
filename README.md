This plugin for MO2 will run BodySlide for up to 5 different groups, presets, and output mods.

### Requires: 
  - MO2 of course
  - BodySlide installed in MO2 under mods folder
  - BodySlide Executable registered in MO2 as "BodySlide x64"

### Installation:
  - Place this file in the MO2/plugins/ folder.

### Settings:
  - In MO2, go to the settings for this plugin and configure the builds you want to run.
  - Default settings are for HIMBO and TNG using HIMBO Zero for OBody and 3BA using - Zeroed Sliders -.
  - Default output mod is "Output - Bodyslide". 
    Either make sure you have created this or changed in settings to the output mod name you want to use.
  - When using clear output mod, the meshes folder will be deleted from output mod before running the build. 
    If multiple builds going to same output mod, only the first build should clear the output mod.

### Notes:
  - This plugin does modify the Config.xml file in the BodySlide mod folder. 
  - It will create a backup of the Config.xml file before running the builds, and restore it back on completion.
