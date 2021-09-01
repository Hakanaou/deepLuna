# deepLuna
Injector/automatic translator (using deepL API) for Tsukihime Remake

## About
deepLuna, from "deepL", the machine translation service, and "Luna", the name of translation of the Roman Moon goddess, is a Python script with a GUI interface that works as an extractor/editor/translator/injector for the text of the remake of the Tsukihime game on Switch and possibly on PS4.

## Installation
You just need a regular Python distribution, for example the last one from https://www.python.org/downloads/, and then launch the script deepLuna.py using a Python IDE, for example IDLE that you get by default, or some other (Spyder, Pyzo, etc.).

## Usage

### Preprocessing steps
1) Dump/Find the NSP Tsukihime Switch ROM as well as the relevant keys (prod.keys and title.keys)
2) Extract the NSP and the resulting (biggest) NCA file using for example hactool (https://github.com/SciresM/hactool)
3) In the romfs folder, copy the script_text.mrg file and paste it in the same folder as deepLuna.py.

### Extracting the text (first compulsory step)
After launching deepLuna, click on "Extract text" and wait until the extraction finishes. The main editor window should open.

### Editing the text
Once the first extraction has been done, upon launching deepLuna simply click on "Open translation".

The main editor window contains on the left the scrolling list representing the offset of the line of text, and upon double-clicking on it, the line in japanese shows in the "Original text" (uneditable) field on the right, and you can put your translation in the "Translated text" field below (erase the word "TRANSLATION" contained in it). On the top of the window, you get the percentage of the translation done, computed in real time (see below).

#### Commands
"Validate": When you finish inputting the translation for a line, click on this button. The corresponding offset will become green to confirm the translation and the percentage of advancement of translation will update.

"Save": When you finish your translation, simply click on this button to save everything. IMPORTANT NOTE: If you don't click on this button before leaving, the program will lose all the new translated lines.

"Search": Opens a window to search for some text. Enter the text in the first field, and click on "Search". Move between the results with "Previous"/"Next". If you want to replace some text (works only for the translated text for obvious reasons), simply use the last field in the window and then click on "Replace"/"Replace all" (the number of results will update automatically).

### Translating the text
Select an offset or a range of offset (using Shift+double-click), then click on the "Translate" button in the main screen, a new window will open. The first time you execute the script, you'll have to configure three options:

a) "deepL API link": Input here your API link(s) from deepL. If you have several of them, just separate them by a comma. Currently works only for free deepL account (possible future update for a pro deepL API link). NOTE: If you copy/paste your link and it doesn't work, make sure that there is not an additional space character that was copied at the end of the link, this might happen.

b) "Language": Put the initials of the language into which you want to translate the script (e.g. EN for english, FR for french, etc.)

c) "Block translation": If you do keep the box unchecked, deepLuna will send each line separately to deepL for translation. If you check the box, deepLuna will glue all the lines from the selected range of offsets together, and send the whole block to deepL before splitting them again. From experience, the latter option might improve the quality of translation since you give more context to deepL.

IMPORTANT NOTE: The furigana are thrown away during translation at the moment since their structure prevent deepL from giving a consistent translation, and also because their meaning and positioning sometimes doesn't match at all the original word (Nasu writing style is really something...). Maybe I'll try to implement something to deal with this problem in the future, but for the moment it is as it is.

Now, it suffices to click on "OK" and wait until translation finishes. If something fails (too much deepL requests for example), the program will tell you and if you've chosen the line-by-line translation approach, will point you out the line where it stopped.

### Injecting the text back
Simply as hello, click on the button "Insert" and wait a litte bit (it might take up to ~20 seconds on some older computers). deepLuna will generate a new script file of the form "script_text_translatedDATETIME.mrg", with DATETIME being the date and time of insertion (to avoid overwriting files and keeping backups).
NOTE: The script inserts everytime the full translation.
