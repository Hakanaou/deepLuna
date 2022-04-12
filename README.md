# deepLuna
Extractor/Injector for Tsukihime Remake

## About
deepLuna is a Python script with a GUI interface that works as an extractor/injector for the text of the Tsukihime Remake game on Switch and possibly on PS4, while taking into account the whole internal structure of the script.

## Installation
You just need a regular Python distribution, for example the last one from https://www.python.org/downloads/, and then launch the script deepLuna.py using a Python IDE, for example IDLE that you get by default, or some other (Spyder, Pyzo, etc.).

For installing dependencies, it's recommended to use a python virtualenv.
To create a new virtualenv and install the dependencies necessary for deepLuna:

```bash
# Create a new virtual environment valled 'venv'
python3 -m virtualenv venv
# Activate the virtual enviroment, so that pip installs packages locally
. venv/bin/activate
# Install the necessary requirements
pip3 install -r requirements.txt
```

## Usage

### Preprocessing steps
1) Dump/Find the NSP Tsukihime Switch ROM as well as the relevant keys (prod.keys and title.keys)
2) Extract the NSP and the resulting (biggest) NCA file using for example hactool (https://github.com/SciresM/hactool)
3) In the romfs folder, copy the **script_text.mrg** and **allscr.mrg** files and paste them in the same folder as deepLuna.py.

### Extracting the text (first compulsory step)
After launching deepLuna, click on "Extract text" and wait until the extraction finishes.

**IMPORTANT NOTE:** This might take a bit of time, around a minute, and this is normal if you have the feeling that the graphical interface is lagging. The script is actually working at the command line level, so you can follow what is going on in the python console or in the console of the IDE you're using.

The main editor window should open. If the script complains (an error window will open), make sure that you placed both script files in the same folder as deepLuna and check that their respective names are "script_text.mrg" and "allscr.mrg" (these are the original names of the files).

### Editing the text
Once the first extraction has been done, when launching deepLuna simply click on "Open translation". This might also take some seconds.

The main editor window contains three main elements:
- On the left there is a tree view of the text files of the game, and it is the only active element at the beginning. This section is the organized by heroine and days ("Arcueid" and "Ciel"). The remaining three sections concern the bad end section "Teach Me, Ciel-sensei!", the part that is common to both Arcueid's and Ciel's route called "Common" and finally the section "Hidden text" that shows some text grabbed by the script that is not used ingame. The first thing you have to do is choose one of the scenes that appear as elements of the form "TEXT_WITH_UNDERSCORES_AND_NUMBERS", and then double-click on it. **IMPORTANT NOTE:** When clicking on one of the element, due to the structure of the script, you might have to wait a few seconds before the next content loads - this is perfectly normal.
- The second element from the left, a scrolling list, activates. It shows the content of the selected scene in the form "a : b" where a is the page and b is the line on the page a. Double-click on any element. You might also note at this point that the two fields above activated, and will show up the percentage of translation done on the selected scene as well as for the global file, computed both in real time. We will come back to them in the section below.
- Finally, you have the main editing part: a field that shows the original japanese selected line called "Original text", a field called "Translated text" below where you have to input your translation of the line above by replacing the word "TRANSLATION" that is there, a field called "Comments" for any comments related to translation and finally some buttons that will allow you to perform all the relevant actions.

**IMPORTANT NOTE:** When in some line you meet the pound/hashtag character "#", PLEASE do not delete it and leave as it is in the translation! This character symbolizes the fact that the line is shown ingame with a small break where the "#" is, and from a low-level perspective, symbolizes that the line is cut into two separate strings with altogether different pointers, so erasing it WILL break everything.

#### Commands
**Validate**: When you finish inputting the translation for a line, click on this button. The corresponding offset will become green to confirm the translation and the percentage of advancement of translation will update for the scene as well as for the total game.

**Save**: When you finish your translation, simply click on this button to save everything. **IMPORTANT NOTE:** This operation might also take a few seconds, this is also normal.

**Search**: Opens a window to search for some text in Japanese/Translated fields (comments are not included). Enter the text in the first field, and click on "Search". Move between the results with "Previous"/"Next". If you want to replace some text (works only for the translated text for obvious reasons), simply use the last field in the window and then click on "Replace"/"Replace all" (the number of results will update automatically). This allows you to search for text only in the selected scene, not in the whole game script.

### Injecting the text back
Easy as pie, simply click on the button "Insert" and wait a little bit (it might take up to ~20 seconds on some older computers). deepLuna will generate a new script file of the form "script_text_translatedDATETIME.mrg", with DATETIME being the date and time of insertion (to avoid overwriting files and keeping backups).
NOTE: The script inserts everytime the full translation.

### **NEW** Comment field

If you want to put a general comment related to translation/edition or anything to the same extent for any line of text, it is now possible to do some in the "Comments" field below "Translated text". Upon validating, your comment will be saved, and when exporting the day, it will appear on the same line after a `//` character. Imported text with such a character at then end of the line will also be counted as a comment.

### **NEW** Characters swapping

In certain languages, some special characters will take double space ingame, which makes them look out of place. In order to correct this, you can tinker font files so that to replace certain useless characters by your special characters. The idea is then to replace all your special characters by those useless characters when inserting the text, so that the modded font prints them as you special characters. To do that, simply check "Swap characters" below the buttons bar, and then insert.
In the new windows that opens, put on each line the replace and replacement characters separated by a comma, like `a,@`, which means that all "a" will be replaced by "@". Each line should contain only one pair of those! Once this is done, click on OK and wait like for usual insertion. You'll have to do this only once, deepLuna will then keep your replacement table saved. If you want for some reason to have the standard insertion, just uncheck "Swap characters".

### Exporting functions

Since the v2.0, deepLuna makes your life easier if you're working as a group on the translation, which is usually the case. How to keep everything up to date for all the people? Whenever you finish working on some scene, just press on "Export", and deepLuna will generate an update file in the update folder, in the same directory.
If you look inside, you will see that this is a simple text file with the same name as the scene you were working on, and if you open it, you'll realise that this is exactly the case - the exported file contains the whole scene in a very nice and readable way, with the original sentences where they were, and the freshly translated sentences where the japanese ones were supposed to be. It suffices now to send this file to your colleagues, and they will simply have to put it in the "update" folder. When they launch deepLuna the next time they want to use it, it will update itself and include the new file in its own database.

If you need for some reason to export your whole personal database, this is also doable - simply click on "Export all", and a new window will open, asking you for confirmation. Note that this operation might take up to 10 mn on some older computers.

On another note, this update function makes it possible to have an alternative use of deepLuna: simply export the scene file, then edit it directly with your favorite text editor, and finally share it with your teammates or use the "Insert" function to inject it in the script yourself.


### Additional comments

Feel free to raise an issue if something happens or if you wish to have some specific functionality, I'm always open to new possibilities and improvements! On another note, if you end up using this tool in some way or the other for your translation, please simply credit the script name itself, deepLuna, in some place or the other on your website/patched game/other.

This readme will get a more substantial update in the following days with screenshots and/or video tutorials.

### Acknoledgments

I am really thankful to Hintay for his wonderful tools at https://github.com/Hintay/PS-HuneX_Tools. I relied on them heavily (unpack_allsrc.py, prep_tpl.py and the mzx decompression script) and included a modified version of them in deepLuna to make it perfectly operational.

