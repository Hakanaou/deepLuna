#!/usr/bin/env python3

### Import packages
import ast
import contextlib
import copy
import datetime
import functools
import os
import re
import requests
import shutil
import time

from PIL import ImageTk, Image
from math import floor

import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfile
from tkinter.ttk import *

import webbrowser

from pathlib import Path

from unpack_allsrc import *
from prep_tpl import *

from luna.scene_table import SceneTable
from luna.translation_table import (
    TranslationTable,
    TranslationTableEntry,
    MergedTranslationTableEntry
)

###Global variables and config.ini initialisation

searchResults = []
posSearch = 0
search_window_open = False
cs = [1]
n_trad = 0
n_trad_day = 0
table_day = []

#dayInfoTable

TRANSLATION_PLACEHOLDER = 'TRANSLATION'

if os.path.exists("config.ini"):
    config = open("config.ini","r+",encoding="utf-8")
    data = config.read()
    sdata = data.split("\n")
    dsdata = [elem.split('=') for elem in sdata]
    error = 0
    for parameter in dsdata:
        if parameter[0] == "translationApi":
            translationApi = parameter[1].split(",")
        elif parameter[0] == "translationLanguage":
            translationLanguage = parameter[1]
        elif parameter[0] == "blockTranslation":
            blockTranslation = False if parameter[1] == '0' else True
        elif parameter[0] == "swapText":
            swapText = False if parameter[1] == '0' else ast.literal_eval(parameter[1])
        else:
            error += 1
    if error > 0 :
        print("Invalid config.ini file. Making a backup of it an reinitialising the configuration...")
        config.seek(0)
        copy = config.read()
        config_copy = open("config.ini.BAK","w+")
        config_copy.write(copy)
        config_copy.close()
        config.close()

        config = open("config.ini","w+")
        translationApi = '0'
        config.write("translationApi=0\n")
        translationLanguage = 'EN'
        config.write("translationLanguage=EN\n")
        blockTranslation = False
        config.write("blockTranslation=0\n")
        swapText = False
        config.write("swapText=0")
        config.close()
    else:
        config.close()

else:
    print("File config.ini not found. Creation and reinitialisation of the file...")
    config = open("config.ini","w+")
    translationApi = '0'
    config.write("translationApi=0\n")
    translationLanguage = 'EN'
    config.write("translationLanguage=EN\n")
    blockTranslation = False
    config.write("blockTranslation=0\n")
    swapText = False
    config.write("swapText=0")
    config.close()


###General functions

def hexsum(a,b):
    return(hex(int(a,16)+int(b,16)))

#add_zeros : pour une 'chaine' hexa (str) de longueur p, rajoute 'len_max' - p zéros devant. Sortie : objet list
def add_zeros(chaine, len_max=8): # ne marche que pour les suites d'octets écrites en hexadecimal - len_max est par défaut à 8, soit un mot, on remplira donc de zéros jusqu'à avoir 8 caractères
    lenstr = len(chaine)
    if lenstr < len_max:
        listr = list(chaine)
        listr = ['0']*(len_max-lenstr) + listr
        return(''.join(listr))
    else:
        return(chaine)

def extract_by_line(scriptTextData,line,page,file,splitLine,choice):
    #scriptTextData corresponds to the opened and written script_text.mrg file
    if line > 0 and line < 43960:
        positionPointerOffsetStart = int(hexsum('0x58',hex((line-1)*4)),16)
        positionPointerOffsetEnd = int(hexsum('0x58',hex(line*4)),16)
        pointerValue = hexsum('2AF48',scriptTextData[positionPointerOffsetStart:positionPointerOffsetStart+4].hex())
        pointerValueNext = hexsum('2AF48',scriptTextData[positionPointerOffsetEnd:positionPointerOffsetEnd+4].hex())
        textLine = scriptTextData[int(pointerValue,16):int(pointerValueNext,16)-2].decode("utf-8")
        #Starting from the end, choice is 1 if line is a choice and 0 otherwise, the splitLine will be related to same-line-text, the file is the name of the heroine/day/text/scene file, the page is the page of the said file and the entry before will correspond to the presence (1) or not (0) of furigana in the text to translate
        return([pointerValue,textLine,'TRANSLATION',1 if re.search(r"\<.+?\|.+?\>",textLine) else 0,line,page,file,splitLine,choice])
        #The -2 comes from the fact that we have \x0D = \r and \x0A = \n at the end of each line of text. We suppress them so that not to show them to the translators (and avoid unnecessary confusion) and simply will replace them during the injection
    elif line == 43960:
        positionPointerOffsetStart = int(hexsum('0x58',hex((line-1)*4)),16)
        pointerValue = scriptTextData[positionPointerOffsetStart:positionPointerOffsetStart+4].hex()
        pointerValue = hexsum('2AF48',pointerValue)
        return([pointerValue,'','TRANSLATION',0,0,43960,'void',0,0])
    else:
        return(False)

def page_to_SpeLineInfo(pageList):

    newPageList = []
    contLine = False
    for line in pageList:
        lineSplit = orders_line(line)
        if len(lineSplit) == 2 and lineSplit[1] == 'n':
            newPageList.append([lineSplit[0],1,0])
            contLine = True
        else:
            if len(lineSplit) == 2 and lineSplit[1] == 's':
                newPageList.append([lineSplit[0],0,1])
            else:
                if contLine == True:
                    newPageList.append([lineSplit[0],1,0])
                    contLine = False
                else:
                    newPageList.append([lineSplit[0],0,0])
                    contLine = False

    return(newPageList)

def orders_line(string):
    splitStr = string.split('_')
    if splitStr[0] == 's' and len(splitStr) == 2:
        return([splitStr[1],splitStr[0]])
    else:
        return(splitStr)


def remove_ruby_text(line):
    # Ruby text consists of <bottom|top> text.
    # This function strips formatting characters and top text to get only
    # the baseline-level characters in a sentence.
    ret = ""
    processing_ruby = False
    seen_midline = False

    # Iterate each character in the line
    for c in line:

        # Is this the start of a ruby?
        if c == '<':
            # Sequential starts are likely an error in the input
            assert not processing_ruby, "Repeated ruby-start encountered in line '%s'" % line

            processing_ruby = True
            seen_midline = False
            continue

        # Is this a ruby midline?
        if c == '|':
            assert processing_ruby, "Encountered ruby-delimiter in non-ruby text for line '%s'" % line
            seen_midline = True
            continue

        # Is this a ruby end?
        if c == '>':
            assert processing_ruby, "Encountered ruby-end outside of ruby context for line '%s'" % line
            assert seen_midline, "Encountered ruby-end without ruby-delimiter for line '%s'" % line
            processing_ruby = False
            seen_midline = True
            continue

        # If this is a normal character, then append it to the output IFF
        # - We are outside a ruby context _or_
        # - We are indisde a ruby context but are before the midline
        if not processing_ruby or not seen_midline:
            ret = ret + c

    return ret


def unicode_aware_len(string):
    # Certain unicode codepoints render as double-width - account for that here
    # when calculating the length of a string
    DOUBLEWIDE_CHARS = set([u"―"])
    length = 0
    for c in string:
        if c in DOUBLEWIDE_CHARS:
            length += 2
        else:
            length += 1

    return length


def noruby_len(line):
    # Get the length of a line as if it did not contain any ruby text
    try:
        return unicode_aware_len(remove_ruby_text(line))
    except AssertionError as e:
        # There are non-conformant lines in the current script. Fail gracefully
        print(e)
        return unicode_aware_len(line)


def ruby_aware_split_words(line):
    # Split a line into words, but consider ruby groups to be a single word.
    ret = []
    acc = ""
    processing_ruby = False
    for c in line:
        # Begin ruby group?
        if c == '<':
            assert not processing_ruby, "Encountered repeated ruby-start in line '%s'" % line
            processing_ruby = True

        # End ruby group?
        if c == '>':
            assert processing_ruby, "Encountered ruby-end without ruby-start in line '%s'" % line
            processing_ruby = False

        # If we see a space and are _not_ inside a ruby group, copy the
        # accumulator to the output list and zero it out
        if c == ' ' and not processing_ruby:
            ret.append(acc)
            acc = ""
            continue

        # If this is not a space, or is a space but we are inside a ruby group,
        # append to current word accumulator.
        acc = acc + c

    # If the accumulator is non-empty, append to the return vector
    if acc:
        ret.append(acc)

    return ret


def add_linebreaks(line, length, start_cursor_pos=0):
    # If the line is already shorter than the desired length, just return
    if noruby_len(line) + start_cursor_pos < length:
        return(line)

    # Split the line into a list of words, where ruby groups as a single word
    splitLine = ruby_aware_split_words(line)

    # If the length of the longest element in the line is larger than our
    # allotted limit, we can't break this line
    if length < max([noruby_len(elem) for elem in splitLine]):
        return(line)

    # Actually break the line.
    i = 0
    listPos = []
    while i < len(splitLine):
        # Initialize the current length of the accumulated line
        # in the event that we are working on a glued sentence
        cumulLen = start_cursor_pos
        start_cursor_pos = 0
        while cumulLen <= length and i < len(splitLine):
            cumulLen += (noruby_len(splitLine[i])+1)
            if cumulLen <= length:
                i += 1
            elif cumulLen == length+1:
                i += 1
                listPos.append(i)
                break
            else:
                listPos.append(i)
                break

    for i in range(len(listPos)):
        splitLine.insert(listPos[i]+i, '\n')

    returnLine = ' '.join(splitLine)
    returnLine = re.sub(r"( \n )|( \n)", r"\n", returnLine)
    returnLine = returnLine[:-1] if returnLine[-1] == '\n' else returnLine
    return returnLine


#dayName: name of day file, scrTable: table of pointer (from allscr.mrg) (not file!), mainTable: main database (not file!)
def export_day(dayName, scrTable, mainTable):
    if not os.path.exists("export"):
        os.mkdir('export')

    # Get the list of text offsets for this scene
    offset_list = scrTable.offsets_for_scene(dayName)

    # Open the output file
    filename = dayName + ".txt"
    day_export = open(os.path.join('export', filename), "wb+")

    dayStr = ''

    for i in range(len(offset_list)):
        dayStr += ('<Page'+str(i+1)+'>\n')
        pageUpdated = page_to_SpeLineInfo(offset_list[i])

        for k in range(len(pageUpdated)):

            line_offset = int(orders_line(offset_list[i][k])[0]) + 1
            entry = mainTable.entry_for_text_offset(line_offset)
            extrLine = (
                entry.translated_text
                if entry.is_translated()
                else entry.jp_text
            )

            if pageUpdated[k][1] == 1:
                if k == len(pageUpdated)-1:
                    dayStr += (extrLine+'\n')
                elif pageUpdated[k+1][1] == 1:
                    dayStr += (extrLine+'#')
                else:
                    dayStr += (extrLine+'\n')
            elif pageUpdated[k][2] == 1:
                dayStr += 'C:>'+(extrLine+'\n')
            else:
                dayStr += (extrLine+'\n')

    day_export.write(dayStr[:-1].encode('utf-8'))
    day_export.close()


def export_all(scrTable, mainTable):

    print("Exporting whole database:")
    for day in scrTable:
        export_day(day[0], scrTable, mainTable)
        print(day[0]+".txt exported")
    print("Exporting done!")


def gen_day_subtable(dayName, scrTable, mainTable):
    # If we are loading the hidden text lines, just select all strings with
    # only the 'void' scene tag
    if dayName == "void":
        return [
            MergedTranslationTableEntry([entry])
            for entry in mainTable.hidden_text_lines()
        ]

    # Find the matching scr table entry for this scene
    page_offsets = scrTable.offsets_for_scene(dayName)

    subTable = []

    # For each page in this scene
    for page_idx in range(len(page_offsets)):
        offset_list = page_offsets[page_idx]

        # Convert each line reference on the page into a tuple encoding
        # control codes
        pageUpdated = page_to_SpeLineInfo(offset_list)

        # For each line on the page, iterate the entire main table(!)
        # and check if the line in the table has the same text offset.
        for line_idx in range(len(pageUpdated)):
            offset_raw = offset_list[line_idx]
            line_offset = int(orders_line(offset_raw)[0]) + 1
            entry = mainTable.entry_for_text_offset(line_offset)
            assert entry, "Failed to locate table entry for script offset '%s'" % line_offset
            subTable.append(entry)

    return correct_day_subtable(subTable)


def correct_day_subtable(subTable):
    # Given a list of entries for a day, group entries that are conjoined.
    newSubTable = []
    i = 0
    while i < len(subTable):
        # If there is nothing weird about this line, just add it and continue
        if subTable[i].is_glued == 0:
            newSubTable.append(MergedTranslationTableEntry([subTable[i]]))
            i += 1
            continue

        # If this is a merged line, then merge it with any subsequent lines
        # with the flag set
        j = i
        acc = []
        while j < len(subTable) and subTable[j].is_glued == 1:
            acc.append(subTable[j])
            j += 1
        newSubTable.append(MergedTranslationTableEntry(acc))

        i = j

    return newSubTable


def update_database():
    # If there is nothing to update, return None
    UPDATE_PATH = "update"
    if not os.path.exists(UPDATE_PATH):
        return None

    # Create a new copy of the translation / script tables
    translation_table = TranslationTable("table.txt")
    scr_table = SceneTable("table_scr.txt")

    # Load the original jp script text mrg
    jp_script_mrg = None
    with open("script_text.mrg", "rb") as script_jp:
        jp_script_mrg = script_jp.read()

    print("Updating the main database...")
    update_start = time.monotonic()
    traverse_updates(UPDATE_PATH, scr_table, translation_table, jp_script_mrg)
    update_elapsed = time.monotonic() - update_start
    print("Updating done in %.1f seconds" % update_elapsed)

    # Write the updated table back to file
    translation_table.serialize_to_file("table.txt")

    return translation_table


def traverse_updates(path, scr_table, translation_table, jp_script_mrg):
    for root, dirs, files in os.walk(path):
        for directory in dirs:
            # Recurse into subdirectories
            traverse_updates(
                os.path.join(root, directory), scr_table,
                translation_table, jp_script_mrg)

            # Remove directories after processing
            shutil.rmtree(os.path.join(root, directory))

        for filename in files:
            # Does this file map to a known scene?
            file_scene = filename.split('.')[0]
            if file_scene in scr_table.scene_names():
                # Ingest this file and mutate our translation table
                file_path = os.path.join(root, filename)
                new_txtfile_update_table(
                    file_path, scr_table, translation_table, jp_script_mrg)

                # Remove after processing
                os.remove(file_path)
                # print("Imported changes from '%s'" % file_path)


def new_txtfile_update_table(filename, scr_table, translation_table, jp_script_mrg):
    # Open scene file
    with open(filename, "r+", encoding="utf-8") as cleanTextFile:
        cleanText = cleanTextFile.read()

    # We eliminate choices indication and split the text into pages
    # And since we start by page 1, we eliminate the first element of the list
    cleanText = re.sub(r"C\:\>", r"", cleanText)
    cleanText = re.split(r"\<Page[0-9 ]+\>", cleanText)[1:]

    # We split the pages on newlines or special pound character, and remove
    # the '' remaining after regex splitting with \n and pound
    cleanText = [
        [line for line in re.split(r"\n|\#", page) if line]
        for page in cleanText
    ]

    # Get name of the scene from its path
    scene_name = os.path.basename(filename).split('.')[0]

    # Retrieve the offset list from the scr_table
    scene_offsets = scr_table.offsets_for_scene(scene_name)

    # Check whether we have the right number of pages in the scene
    if len(scene_offsets) != len(cleanText):
        print("Bad number of pages in '%s' (wanted %d, got %d)" % (
            filename, len(scene_offsets), len(cleanText)))
        return translation_table

    # Initialisation of local variables
    dayTable = []

    # We run through the pages of the day
    for i in range(len(scene_offsets)):

        # We get special formating for the pages, converting the
        # _n, _r_n or _s symbols to the corresponding elements of the
        # general table (translation_table)
        pageUpdated = page_to_SpeLineInfo(scene_offsets[i])

        # If number of lines on the page doesn't correspond, raise an error
        if len(pageUpdated) != len(cleanText[i]):
            print("Bad number of lines on '%s' page %d (wanted %d, got %d)" % (
                filename, i + 1, len(pageUpdated), len(cleanText[i])))
            return translation_table

        # We run through the lines of the pages - if they are identical to the
        # japanese, we change nothing, otherwise we add the translation
        for line in range(len(pageUpdated)):
            extrLine = extract_by_line(
                jp_script_mrg,
                int(pageUpdated[line][0]) + 1,
                i + 1,
                scene_name,
                pageUpdated[line][1],
                pageUpdated[line][2]
            )

            extrLine[2] = (
                extrLine[2]
                if cleanText[i][line] == extrLine[1]
                else cleanText[i][line]
            )
            dayTable.append(extrLine)

    # For each loaded string, update the matching translation in our db
    for import_entry in dayTable:
        db_entry = translation_table.entry_for_text_offset(import_entry[4])
        db_entry.translated_text = import_entry[2]
        translation_table.apply_update(MergedTranslationTableEntry([db_entry]))


def initial_full_extract():

    initDir = os.getcwd()

    #extracting script files
    unpackAllSrc()
    prepTpl()

    shutil.rmtree('allscr-unpacked')
    shutil.copy('script_text.mrg','allscr-decoded/')
    os.chdir('allscr-decoded/')

    #remove unneeded script files
    os.remove('ARCHIVE.tpl.txt')
    for p in Path(".").glob("JUMP*.tpl.txt"):
        p.unlink()
    os.remove('QACALL.tpl.txt')
    os.remove('STAFFROLL.tpl.txt')
    os.remove('START_SCRIPT.tpl.txt')
    os.remove('TEST_SCRIPT.tpl.txt')
    os.remove('00_01.tpl.txt')

    #extract the text in day files from script_text.mrg
    tableList = []
    scrFullInfo = []
    for filename in os.listdir(os.getcwd()):
        if filename.split('.')[1] == 'tpl':
            fileList, scrList = tplscript_to_txtfile(filename,True)
            print(filename.split('.')[0]+".txt extracted")
            tableList += fileList
            scrFullInfo.append(scrList)

    print("Initial extraction finished.\nSorting the database and adding missing text to it...")

    tableList = sorted(tableList, key = lambda x: int(x[0],16))

    os.remove('script_text.mrg')

    os.chdir(initDir)

    scrFullInfo.sort()

    #make the table standard (incorporating skipped pointers)
    old_table = extract_text("script_text.mrg","old_table.txt")

    tableList = complete_table(tableList,old_table)
    tableList = combine_elements_table(tableList)

    os.remove("old_table.txt")

    extractedText = open("table.txt",'w+',encoding="utf-8")
    extractedText.write('\n'.join([str(elem) for elem in tableList]))

    extractedScr = open("table_scr.txt",'w+',encoding="utf-8")
    extractedScr.write('\n'.join([str(elem) for elem in scrFullInfo]))

    shutil.rmtree('allscr-decoded')
    if not os.path.exists("update"):
        os.mkdir('update')

    print("Initialisation finished!")

    # Lazy - reload the files from disk to get them in the new format
    # instead of rewriting the import process right now
    reloaded_translation_table = TranslationTable('table.txt')
    reloaded_table_scr = SceneTable('table_scr.txt')

    return([reloaded_translation_table, reloaded_table_scr])


def complete_table(tab_new,tab_old):
    tab_new_hexa = [elem[0] for elem in tab_new]


    for i in range(len(tab_old)):
        if not tab_old[i][0] in tab_new_hexa:
            tab_new.append([tab_old[i][0],tab_old[i][1],tab_old[i][2],int(tab_old[i][3]),i+1,0,'void',0,0])

    tab_new = sorted(tab_new, key = lambda x: int(x[0],16))

    return(tab_new)

def combine_elements_table(tab_new):

    tab_comb_new = []

    i=0

    while i<len(tab_new):
        if i<len(tab_new)-1 and tab_new[i][0] == tab_new[i+1][0]:
            j=i+1
            fileNameList = [tab_new[i][6]]
            while tab_new[j][0] == tab_new[i][0]:
                fileNameList.append(tab_new[j][6])
                j += 1
            tab_comb_new.append([tab_new[i][0],tab_new[i][1],tab_new[i][2],tab_new[i][3],tab_new[i][4],tab_new[i][5],fileNameList,tab_new[i][7],tab_new[i][8]])
            i=j
        else:
            tab_comb_new.append([tab_new[i][0],tab_new[i][1],tab_new[i][2],tab_new[i][3],tab_new[i][4],tab_new[i][5],[tab_new[i][6]],tab_new[i][7],tab_new[i][8]])
            i += 1

    return(tab_comb_new)

def test_function(tplScript):
    tpl = open(tplScript,"r+",encoding="utf-8")
    tplData = tpl.read()
    tplData = re.sub(r"\~\_(ZZ|ZY|W|R|S|F|G|V|C|T|M|N|A|J|I|X|E)[A-Za-z0-9\(\)\,\.\-\_\`\:\#\+]+?\~", r"",tplData)
    tplData = re.sub(r"\~\_PGST\((\-1|10000)\)\~\n",r"",tplData)
    tplData = re.sub(r"\~\n{2,}",r"~\n",tplData)
    tplData = re.sub(r"\)\n{2,}",r")\n",tplData)
    tplData = re.sub(r"\n\n\~",r"~",tplData)
    tplData = re.sub(r"\n\~\~",r"",tplData)
    tplData = re.sub(r"\~\_PGST\([0-9]+?\)\~",r"P",tplData)
    tplData = re.sub(r"(\<[0-9]+?\>\_(ZM[0-9A-Za-z]+?|MSAD)\((\@[cr1-9]*)*\$)|(\))", r"",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\@k\@e\)", r"", tplData)
    tplData = re.sub(r"([0-9]+)\_r\$([0-9]+\_?n?)", r"\1_r_n\n\2",tplData)
    tplData = re.sub(r"\@x\@r", r"@x",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_SELR\([0-9]+?\;\/\$",r"s_",tplData)
    tplData = re.sub(r"(P\n)+",r"P\n",tplData)
    tplData = re.sub(r"P\nP",r"P",tplData)
    tplData = re.sub(r"\nP\ns\_",r"\ns_",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    tplData = re.sub(r"\;\/1\n",r"\n",tplData)
    tplData = re.sub(r"\n\~\n",r"\n",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_ZM[0-9A-Za-z]+?\(\@x\$", r"@x",tplData)
    tplData = re.sub(r"(\@k\@e)?\n\@x", r"_n\n", tplData)
    tplData = re.sub(r"\@k\@e\ns\_",r"\ns_",tplData)
    tplData = re.sub(r"\@k\@e",r"",tplData)
    tplData = re.sub(r"\n\<[0-9]+?\>\_MSAD\(\_?n?\n", r"\n", tplData)
    tplData = re.sub(r"(\n){2,}",r"\n",tplData)

    txt = open("debug.txt","w+",encoding="utf-8")
    txt.write(str(tplScript.split('.')[0])+"\n"+tplData)
    #txt.write(tplData)
    txt.close()

def tplscript_to_txtfile(tplScript,niceText=False):

    tpl = open(tplScript,"r+",encoding="utf-8")
    tplData = tpl.read()
    tplData = re.sub(r"\~\_(ZZ|ZY|W|R|S|F|G|V|C|T|M|N|A|J|I|X|E)[A-Za-z0-9\(\)\,\.\-\_\`\:\#\+]+?\~", r"",tplData)
    tplData = re.sub(r"\~\_PGST\((\-1|10000)\)\~\n",r"",tplData)
    tplData = re.sub(r"\~\n{2,}",r"~\n",tplData)
    tplData = re.sub(r"\)\n{2,}",r")\n",tplData)
    tplData = re.sub(r"\n\n\~",r"~",tplData)
    tplData = re.sub(r"\n\~\~",r"",tplData)
    tplData = re.sub(r"\~\_PGST\([0-9]+?\)\~",r"P",tplData)
    tplData = re.sub(r"(\<[0-9]+?\>\_(ZM[0-9A-Za-z]+?|MSAD)\((\@[cr1-9]*)*\$)|(\))", r"",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\@k\@e\)", r"", tplData)
    tplData = re.sub(r"([0-9]+)\_r\$([0-9]+\_?n?)", r"\1_r_n\n\2",tplData)
    tplData = re.sub(r"\@x\@r", r"@x",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_SELR\([0-9]+?\;\/\$",r"s_",tplData)
    tplData = re.sub(r"(P\n)+",r"P\n",tplData)
    tplData = re.sub(r"P\nP",r"P",tplData)
    tplData = re.sub(r"\nP\ns\_",r"\ns_",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    tplData = re.sub(r"\;\/1\n",r"\n",tplData)
    tplData = re.sub(r"\n\~\n",r"\n",tplData)
    tplData = re.sub(r"\<[0-9]+?\>\_ZM[0-9A-Za-z]+?\(\@x\$", r"@x",tplData)
    tplData = re.sub(r"(\@k\@e)?\n\@x", r"_n\n", tplData)
    tplData = re.sub(r"\@k\@e\ns\_",r"\ns_",tplData)
    tplData = re.sub(r"\@k\@e",r"",tplData)
    tplData = re.sub(r"\n\<[0-9]+?\>\_MSAD\(\_?n?\n", r"\n", tplData)

    # tplData = re.sub(r"\~\_PGST\((\-1|10000)\)\~\n",r"",tplData)
    # tplData = re.sub(r"\~\n{2,}",r"~\n",tplData)
    # tplData = re.sub(r"\)\n{2,}",r")\n",tplData)
    # tplData = re.sub(r"\n\n\~",r"~",tplData)
    # tplData = re.sub(r"\n\~\~",r"",tplData)
    # tplData = re.sub(r"\~\_PGST\([0-9]+?\)\~",r"P",tplData)
    # tplData = re.sub(r"(\<[0-9]+?\>\_(ZM[0-9A-Za-z]+?|MSAD)\((\@[a-z1-9]*)*\$)|(\))", r"",tplData)
    # tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    # tplData = re.sub(r"\<[0-9]+?\>\_SELR\([0-9]+?\;\/\$",r"s_",tplData)
    # tplData = re.sub(r"\@k\@e\n",r"\n",tplData)
    # tplData = re.sub(r"\@k\@e",r"",tplData)
    # tplData = re.sub(r"(P\n)+",r"P\n",tplData)
    # tplData = re.sub(r"P\nP",r"P",tplData)
    # tplData = re.sub(r"\nP\ns\_",r"\ns_",tplData)
    # tplData = re.sub(r"\<[0-9]+?\>\_MSAD\(\n",r"",tplData)
    # tplData = re.sub(r"\;\/1\n",r"\n",tplData)
    # tplData = re.sub(r"\n\~\n",r"\n",tplData)

    tplData = re.sub(r"(\n){2,}",r"\n",tplData)

    lineInformation = tplData.split('P')
    if lineInformation[-1] != '' and lineInformation[-1] != '\n':
        if lineInformation[0] == '' or lineInformation[0] == '\n':
            lineInformation = lineInformation[1:]
    else:
        if lineInformation[0] == '' or lineInformation[0] == '\n':
            lineInformation = lineInformation[1:-1]
        else:
            lineInformation = lineInformation[:-1]

    seen = {}
    lineInformation = [[seen.setdefault(x, x) for x in (page.split('\n')[1:-1] if page.split('\n')[-1] == '' else page.split('\n')[1:]) if x not in seen] for page in lineInformation]

    txt = open("debug.txt","w+",encoding="utf-8")
    txt.write(str(tplScript.split('.')[0])+"\n"+tplData)
    #txt.write(tplData)
    txt.close()

    scrInfo = [tplScript.split('.')[0],lineInformation]

    script_jp = open("script_text.mrg","rb")
    dataScriptJP = script_jp.read()

    if niceText:
        niceTextFile = open(tplScript.split('.')[0]+".txt", "w+", encoding="utf-8")
        strNiceText = ''

    listText = []
    pageNum = 1

    for i in range(len(lineInformation)):

        if niceText:
            strNiceText += ('<Page'+str(i+1)+'>\n')

        pageUpdated = page_to_SpeLineInfo(lineInformation[i])

        for l in range(len(pageUpdated)):
            extrLine = extract_by_line(dataScriptJP,int(pageUpdated[l][0])+1,i+1,tplScript.split('.')[0],pageUpdated[l][1],pageUpdated[l][2])
            listText.append(extrLine)
            if niceText:
                if pageUpdated[l][1] == 1:
                    if l == len(pageUpdated)-1:
                        strNiceText += (extrLine[1]+'\n')
                    elif pageUpdated[l+1][1] == 1:
                        strNiceText += (extrLine[1]+'#')
                    else:
                        strNiceText += (extrLine[1]+'\n')
                elif pageUpdated[l][2] == 1:
                    strNiceText += 'C:>'+(extrLine[1]+'\n')
                else:
                    strNiceText += (extrLine[1]+'\n')


    if niceText:
        niceTextFile.write(strNiceText[:-1])
        niceTextFile.close()

    tpl.close()

    return([listText,scrInfo])


def extract_text(scriptFile, outputFile):

    script = open(scriptFile, 'rb')
    extractedText = open(outputFile, 'w+', encoding="utf-8")

    data = script.read()

    extractedTable = []
    offset = '0x2AF48'

    pointerWord = b'\x00\x00\x00\x00'
    nextPointerWord = b'\x00\x00\x00A'
    positionText =  offset
    positionPointer = '0x58'

    while nextPointerWord != b'\xFF\xFF\xFF\xFF':

        textPointer = hexsum(pointerWord.hex(),offset)
        textStr = data[int(positionText,16):int(hexsum(offset,nextPointerWord.hex()),16)-2]
        textStr = textStr.decode('utf-8')
        newLine = [textPointer,textStr,'TRANSLATION',1 if re.search(r"\<.+?\|.+?\>",textStr) else 0]

        extractedTable.append(newLine)

        extractedText.write(str(newLine))

        positionPointer = hexsum(positionPointer,'0x4')
        positionText = hexsum(offset,nextPointerWord.hex())
        pointerWord = nextPointerWord
        nextPointerWord = data[int(hexsum(positionPointer,'0x4'),16):int(hexsum(positionPointer,'0x8'),16)]

        if nextPointerWord != b'\xFF\xFF\xFF\xFF':
            extractedText.write('\n')

    extractedText.close()
    script.close()

    return(extractedTable)

def read_table(tableName):
    table_file = open(tableName, 'r', encoding="utf-8")

    data = table_file.read()
    data = data.split('\n')
    data = [ast.literal_eval(elem) for elem in data]

    table_file.close()

    return(data)

def swap_characters_line(line,rep_list):

    if rep_list:
        #print(rep_list)
        for rep in rep_list:
            #print(rep)
            line = re.sub(rep[0],rep[1],line)
        return(line)
    else:
        return(line)


def insert_translation(scriptFile, translation_table_filename, scriptFileTranslated, swap=False):

    print("Starting script injection...")

    scriptJP = open(scriptFile, 'rb')
    scriptTL = open(scriptFileTranslated, 'wb')

    dataJPFile = scriptJP.read()

    # Read in the translation table again
    translation_table = TranslationTable(translation_table_filename)

    startJPFile = dataJPFile[0:int('58', 16)]
    endJPFile = dataJPFile[int('36B89F', 16):]

    bytesNewPointers = b'\x00\x00\x00\x00'
    totalLenText = '00000000'
    bytesListTLText = b''

    # Track cursor position for breaking conjoined lines
    cursor_position = 0

    # Iterate the lines in the translation table, in order of their offset
    string_offsets = sorted(translation_table.string_offsets())

    # Track whether the previously emitted line was a glued line
    last_line_was_glued = False

    # What is the last page for the previous entry?
    last_page_number = -1

    for offset in string_offsets:
        entry = translation_table.entry_for_text_offset(offset)
        assert type(entry.jp_mrg_offset) == str

        # Delete the trailing comment if there is one
        entry.translated_text = entry.translated_text.split('//')[0]

        # If this line isn't glued, or is the first glued line of a set,
        # reset any tracked cursor position
        # Hidden text should be ignored, since it does not affect the
        # render state of the lines
        # QA lines are excepted from this, since we handle those differently
        if not entry.is_hidden() and not entry.scene_list[0][:2] == 'QA':
            # Reset cursor position
            # - This line isn't glued
            # - It is glued, but it's the first line in a glue group
            # - It's glued, but it's the first line on a new page
            if not entry.is_glued \
                    or not last_line_was_glued \
                    or entry.page_number != last_page_number:
                cursor_position = 0

        line_to_inject = None
        if not entry.is_translated():
            # For untranslated strings, put the original JP text back in
            charswapped_line = swap_characters_line(entry.jp_text, swap)
            line_to_inject = charswapped_line.encode("utf-8") + b'\x0D\x0A'
        elif entry.scene_list[0][:2] == 'QA':
            # Replace any custom character sets
            charswapped_line = \
                swap_characters_line(entry.translated_text, swap)

            # If this is a fresh page, reset the cursor position
            # Otherwise, we treat _all_ QA lines as glued
            if entry.page_number != last_page_number:
                cursor_position = 0

            # Insert linebreaks. We don't break on character counting, but based
            # on control codes in the script. %{@n}
            broken_line = ""
            has_pct = False  # Did we see a % that might open a cc
            in_cc = False  # Are we inside a control code segment
            for c in charswapped_line:
                # Handle control mode entry / exit
                if c == '%':
                    has_pct = True
                    continue
                if has_pct and c == '{':
                    in_cc = True
                    has_pct = False
                    continue
                if in_cc and c == '}':
                    in_cc = False
                    continue

                # Non-control mode: just append character to output buffer
                if not in_cc:
                    broken_line += c
                    continue

                # CC mode: handle characters
                if c == 'n':
                    broken_line += "\n"
                    continue

                assert False, f"Unknown control code '{c}'"

            # New cursor position is length of final line of broken line
            did_break_line = len(broken_line.split('\n')) > 1
            final_broken_line = broken_line.split('\n')[-1]
            if did_break_line:
                cursor_position = noruby_len(final_broken_line)
            else:
                cursor_position += noruby_len(final_broken_line)

            # print(
            #     f"{offset}: Last line: {final_broken_line} "
            #     f"New cursor position: {cursor_position}")

            # Encode and add trailing \r\n\
            line_to_inject = broken_line.encode("utf-8") + b'\x0D\x0A'

        else:  # Normal case
            # Replace any custom character sets
            charswapped_line = \
                    swap_characters_line(entry.translated_text, swap)

            # Insert linebreaks
            broken_line = add_linebreaks(
                charswapped_line, 55, start_cursor_pos=cursor_position)

            # print(
            #     f"{offset}: Start cursor pos {cursor_position}, "
            #     f"broken line: {broken_line}")

            # Update cursor position with the length of the final line
            # If the broken line is only a single line, increment cursor pos
            # If it is _multiple_ lines, then we only count the len of the
            # final line
            did_break_line = len(broken_line.split('\n')) > 1
            final_broken_line = broken_line.split('\n')[-1]
            if did_break_line:
                cursor_position = noruby_len(final_broken_line)
            else:
                cursor_position += noruby_len(final_broken_line)
                cursor_position = cursor_position % 55

            # print(
            #     f"{offset}: Last line: {final_broken_line} "
            #     f"New cursor position: {cursor_position}")

            # Encode and add trailing \r\n\
            line_to_inject = broken_line.encode("utf-8") + b'\x0D\x0A'

        # Encode this line into our text data and add an offset indirection
        bytesListTLText += line_to_inject
        totalLenText = add_zeros(
            hexsum(totalLenText, hex(len(line_to_inject)))[2:])
        bytesNewPointers += bytes.fromhex(totalLenText)

        # Update tracking state
        last_line_was_glued = entry.is_glued
        last_page_number = entry.page_number

    bytesListTLText = bytesListTLText[:-2]
    bytesNewPointers = bytesNewPointers[:-4] + bytesNewPointers[-8:-4] + 12*b'\xFF'

    totalNewFile = startJPFile + bytesNewPointers + bytesListTLText + endJPFile

    scriptTL.write(totalNewFile)

    scriptJP.close()
    scriptTL.close()

    print("Script injection done!")


def names_organize(listNames):
    arcList = []
    cielList = []
    teachMeList = [('QA_0'+str(i) if i<10 else 'QA_'+str(i)) for i in range(1,26)]
    common = ['00_00','00_02']

    for i in range(1,16):
        i_dayArc = []
        i_dayCiel = []

        for scene in listNames:
            splitScene = scene.split('_')
            if i != 15 and splitScene[0] != 'QA' and int(splitScene[0]) == i and splitScene[2][:2] == 'AR':
                i_dayArc.append(scene)
            elif splitScene[0] != 'QA' and int(splitScene[0]) == i and (splitScene[2][:2] == 'CI' or splitScene[3][:2] == 'CI'):
                i_dayCiel.append(scene)

        if i != 15:
            arcList.append(i_dayArc)
        cielList.append(i_dayCiel)

    return([arcList,cielList,teachMeList,common])

#Harphield extraction function for the UI .DAT file
def extract_sysmes():
    sysmes = open('SYSMES_TEXT.DAT', 'rb')

    data = sysmes.read()

    count_offset = '0x4'

    int_pos = int(count_offset, 16)
    string_count = int.from_bytes(data[int_pos:int_pos + 4], byteorder='little')

    print('Found', string_count, 'strings')

    header_offset = '0x18'

    # first we read the header with the string offsets
    positions = []
    first_position = int(header_offset, 16)
    i = first_position
    while i < first_position + string_count * 8:
        positions.append(int.from_bytes(data[i:i + 8], byteorder='little'))
        i += 8

    # then we read the strings on those positions

    output = open('sysmes_text.txt', 'w+', encoding="utf-8")

    for position in positions:
        int_pos = position

        values = []
        texts = []

        value = data[int_pos]

        while value != 0:
            values.append(value)
            int_pos += 1
            value = data[int_pos]

        text = bytearray(values).decode('utf-8')
        texts.append(text)
        print(hex(position) + ': ' + text)
        output.write(text + "\n")


    sysmes.close()
    output.close()

#Harphield injection function for the UI .DAT file
def rebuild_sysmes():
    # the original sysmes here
    sysmes = open('SYSMES_TEXT.DAT', 'rb')
    old_data = sysmes.read()

    # the translated texts here
    translation = open('sysmes_text.txt', 'rb')
    translations = translation.read().splitlines()

    # output of new sysmes here
    new_sysmes = open('SYSMES_TEXT_NEW.DAT', 'wb')

    count_offset = '0x4'
    int_pos = int(count_offset, 16)
    string_count = int.from_bytes(old_data[int_pos:int_pos + 4], byteorder='little')

    if len(translations) != string_count:
        raise SystemExit('Wrong number of strings in translation file!')

    header_offset = '0x18'
    footer_offset = '0x184DA'
    strings_offset = '0x2ED8'

    # prepare header and footer
    # we will prepend our new data with this
    header_data = old_data[0:int(header_offset, 16)]
    # we will append our new data with this
    footer_data = old_data[int(footer_offset, 16):len(old_data)]

    # write header
    new_sysmes.write(header_data)
    # write string positions
    first_position = int(header_offset, 16)
    pos = first_position
    i = 0
    strings_position = int(strings_offset, 16)
    while pos < first_position + string_count * 8:
        new_sysmes.write(strings_position.to_bytes(8, byteorder='little'))
        pos += 8
        strings_position += len(translations[i]) + 1    # +1 because there will be a 00 byte after each string
        i += 1

    # write strings
    for t in translations:
        new_sysmes.write(t)
        new_sysmes.write(bytes([0x00]))

    # write footer
    new_sysmes.write(footer_data)

    sysmes.close()
    translation.close()
    new_sysmes.close()


###GUI Interface


class StartWindow:

    def __init__(self,welcome):
        self.welcome = welcome
        welcome.title("Welcome to deepLuna")
        welcome.resizable(height=False, width=False)
        self.frame_image = tk.Frame(welcome, borderwidth=5)
        self.icone = Image.open("icone.png")
        self.icone = self.icone.resize((140, 140))
        self.picture = ImageTk.PhotoImage(self.icone)
        self.imag = tk.Label(self.frame_image, image=self.picture)
        self.imag.image = ImageTk.PhotoImage(self.icone)
        self.imag.pack()
        self.frame_image.pack(side=tk.LEFT)

        self.frame_buttons = tk.Frame(welcome, borderwidth=5)

        self.new_project_button = tk.Button(self.frame_buttons, text="Extract text", bg="#CFCFCF", width=28, command=self.function_extract)
        self.new_project_button.grid(row=0,column=0,pady=2)
        self.open_project_button = tk.Button(self.frame_buttons, text="Open translation", bg="#CFCFCF", width=28, command=self.open_main_window)
        self.open_project_button.grid(row=1,column=0,pady=2)
        self.open_project_button = tk.Button(self.frame_buttons, text="About", bg="#CFCFCF", width=28, command=self.open_about)
        self.open_project_button.grid(row=2,column=0,pady=2)

        self.frame_buttons.pack(side=tk.LEFT)

    def open_about(self):
        self.info_window = tk.Toplevel(self.welcome)

        #self.info_window.attributes("-topmost", True)
        self.info_window.grab_set()

        self.info = Informations(self.info_window)

    def function_extract(self):
        if os.path.exists("table.txt") and os.path.exists("table_scr.txt"):
            self.warning = tk.Toplevel(self.welcome)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False, width=False)
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="WARNING: You have already extracted the text")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Continue", command = self.function_reextract)
            self.warning_button.grid(row=1,column=0,pady=10)
        else:
            if os.path.exists("script_text.mrg") and os.path.exists("allscr.mrg"):
                self.table_jp, self.table_scr = initial_full_extract()

                self.translation_window = tk.Toplevel(self.welcome)

                #self.translation_window.attributes("-topmost", True)
                self.translation_window.grab_set()

                self.analysis = MainWindow(self.translation_window, self.table_jp, self.table_scr)
            else:
                if os.path.exists("script_text.mrg") and not os.path.exists("allscr.mrg"):
                    self.add_files = "allscr.mrg"
                elif not os.path.exists("script_text.mrg") and os.path.exists("allscr.mrg"):
                    self.add_files = "script_text.mrg"
                else:
                    self.add_files = "script_text.mrg and allscr.mrg"

                self.warning = tk.Toplevel(self.welcome)
                self.warning.title("deepLuna")
                self.warning.resizable(height=False, width=False)
                #self.warning.attributes("-topmost", True)
                self.warning.grab_set()

                self.warning_message = tk.Label(self.warning, text="ERROR: Please add "+self.add_files+" in the folder!")
                self.warning_message.grid(row=0,column=0,pady=5)

                self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                self.warning_button.grid(row=1,column=0,pady=10)


    def function_reextract(self):
        self.warning.grab_release()
        self.warning.destroy()
        self.welcome.grab_set()

        if os.path.exists("script_text.mrg") and os.path.exists("allscr.mrg"):
            self.table_jp, self.table_scr = initial_full_extract()

            self.translation_window = tk.Toplevel(self.welcome)

            #self.translation_window.attributes("-topmost", True)
            self.translation_window.grab_set()

            self.analysis = MainWindow(self.translation_window, self.table_jp, self.table_scr)
        else:
            if os.path.exists("script_text.mrg") and not os.path.exists("allscr.mrg"):
                self.add_files = "allscr.mrg"
            elif not os.path.exists("script_text.mrg") and os.path.exists("allscr.mrg"):
                self.add_files = "script_text.mrg"
            else:
                self.add_files = "script_text.mrg and allscr.mrg"

            self.warning = tk.Toplevel(self.welcome)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False, width=False)
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="ERROR: Please add "+self.add_files+" in the folder!")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
            self.warning_button.grid(row=1,column=0,pady=10)


    def open_main_window(self):
        if os.path.exists("table.txt") and os.path.exists("table_scr.txt"):
            self.table_jp = update_database()
            print("Loading the database...")
            self.table_scr = SceneTable("table_scr.txt")
            print("Loading done!")
            self.translation_window = tk.Toplevel(self.welcome)

            #self.translation_window.attributes("-topmost", True)
            try:
                self.translation_window.grab_set()
            except Exception as e:
                print(e)

            self.analysis = MainWindow(self.translation_window, self.table_jp, self.table_scr)
        else:
            self.warning = tk.Toplevel(self.welcome)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False, width=False)
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="ERROR: Extract the game text first!")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
            self.warning_button.grid(row=1,column=0,pady=10)


    def pushed(self,sub_win):
        sub_win.grab_release()
        sub_win.destroy()
        self.welcome.grab_set()


class Informations:
    def __init__(self,information):
        self.informations = information

        information.title("deepLuna — About")
        information.geometry("400x150")
        information.resizable(height=False, width=False)

        self.nom = tk.Label(information, text ="deepLuna v3.1.2 — 18/10/2021\nDeveloped by Hakanaou and R.Schlaikjer\n", justify=tk.CENTER, borderwidth=10)
        self.nom.pack()

        self.explanations = tk.Button(information, text="deepLuna GitHub", command=self.callback)
        self.explanations.pack()

    def callback(self):
        webbrowser.open_new("https://github.com/Hakanaou/deepLuna")


class MainWindow:

    def __init__(self,dl_editor,table, table_scr):

        global cs
        global translationApi
        global translationLanguage
        global blockTranslation
        global swapText
        global table_day

        self.dl_editor = dl_editor

        self.table_file = table
        self.table_scr_file = table_scr

        dl_editor.resizable(height=False, width=False)
        dl_editor.title("deepLuna — Editor")

        self.s = Style()
        self.s.theme_use('clam')
        self.s.configure("blue.Horizontal.TProgressbar", foreground='green', background='green')
        self.s.configure("smallFont.Treeview", font='TkDefaultFont 11', rowheight=24)
        self.s.configure("smallFont.Treeview.Heading", font='TkDefaultFont 11')

        self.name_day = tk.StringVar()
        self.name_day.set('No day loaded ')

        self.frame_infos = tk.Frame(dl_editor, borderwidth=20)

        self.frame_local_tl = tk.Frame(self.frame_infos, borderwidth=10)

        self.label_prct_trad_day = tk.Label(self.frame_local_tl, textvariable=self.name_day)
        self.label_prct_trad_day.grid(row=0, column=0)

        self.prct_trad_day = tk.Text(self.frame_local_tl, width=6, height=1, borderwidth=5, highlightbackground="#A8A8A8")
        self.prct_trad_day.bind("<Key>", lambda e: self.ctrlEvent(e))
        self.prct_trad_day.grid(row=0, column=1)

        self.frame_local_tl.grid(row=0, column=0, padx=10)

        self.frame_tl = tk.Frame(self.frame_infos, borderwidth=10)

        self.label_prct_trad = tk.Label(self.frame_tl, text="Translated text: ")
        self.label_prct_trad.grid(row=0, column=0)

        self.prct_trad = tk.Text(self.frame_tl, width=6, height=1, borderwidth=5, highlightbackground="#A8A8A8")
        self.prct_trad.bind("<Key>", lambda e: self.ctrlEvent(e))
        self.prct_trad.grid(row=0, column=1)

        self.frame_tl.grid(row=0, column=1, padx=10)

        self.frame_infos.grid(row=1, column=1)

        self.frame_edition = tk.Frame(dl_editor, borderwidth=1)

        self.frame_tree = tk.Frame(self.frame_edition, borderwidth=20)

        self.tree = Treeview(self.frame_tree, height=21, style="smallFont.Treeview")
        self.tree.column('#0', anchor='w', width=320)
        self.tree.heading('#0', text='Game text', anchor='center')

        self.table_scr = SceneTable("table_scr.txt")
        self.nameDaysList = self.table_scr.scene_names()

        self.clusDayData = names_organize(self.nameDaysList)

        self.num = 0
        self.tree.insert('', tk.END, text='Arcueid', iid=self.num, open=False)
        self.num += 1

        for self.i in range(14):
            self.tree.insert('', tk.END, text='Day '+str(self.i+1), iid=self.num+self.i, open=False)
            self.tree.move(self.num+self.i, 0, self.i)
            for self.j in range(len(self.clusDayData[0][self.i])):
                self.tree.insert('', tk.END, text=self.clusDayData[0][self.i][self.j], iid=self.num+self.i+self.j+1, open=False)
                self.tree.move(self.num+self.i+self.j+1,self.num+self.i,self.j)
            self.num = self.num + len(self.clusDayData[0][self.i])
        self.num = self.num + 14

        self.tree.insert('', tk.END, text='Ciel', iid=self.num, open=False)
        self.cielNum = self.num
        self.num += 1

        for self.i in range(15):
            self.tree.insert('', tk.END, text='Day '+str(self.i+1), iid=self.num+self.i, open=False)
            self.tree.move(self.num+self.i, self.cielNum, self.i)
            for self.j in range(len(self.clusDayData[1][self.i])):
                self.tree.insert('', tk.END, text=self.clusDayData[1][self.i][self.j], iid=self.num+self.i+self.j+1, open=False)
                self.tree.move(self.num+self.i+self.j+1,self.num+self.i,self.j)
            self.num = self.num + len(self.clusDayData[1][self.i])
        self.num = self.num + 15

        self.tree.insert('', tk.END, text='Teach Me, Ciel-sensei!', iid=self.num, open=False)
        self.senseiNum = self.num
        self.num += 1

        for self.i in range(25):
            self.tree.insert('', tk.END, text=self.clusDayData[2][self.i], iid=self.num+self.i, open=False)
            self.tree.move(self.num+self.i, self.senseiNum, self.i)
        self.num = self.num + 25

        self.tree.insert('', tk.END, text='Common', iid=self.num, open=False)
        self.commonNum = self.num
        self.num += 1

        for self.i in range(2):
            self.tree.insert('', tk.END, text=self.clusDayData[3][self.i], iid=self.num+self.i, open=False)
            self.tree.move(self.num+self.i, self.commonNum, self.i)
        self.num = self.num + 2

        self.tree.insert('', tk.END, text='Hidden text', iid=self.num, open=False)
        self.hiddenText = self.num
        self.num += 1

        self.tree.bind('<Double-Button-1>', lambda e: self.selectItem(e))

        self.tree.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')

        self.frame_tree.pack(side=tk.LEFT)


        self.frame_choix = tk.Frame(self.frame_edition, borderwidth=20)

        self.label_offsets = tk.Label(self.frame_choix, text="Original text offsets:")
        self.label_offsets.pack()

        self.listbox_offsets = tk.Listbox(self.frame_choix, height=32, width=18, exportselection=False, selectmode=tk.EXTENDED)
        self.listbox_offsets.bind('<Button-1>', self.show_text)
        self.listbox_offsets.bind('<Return>', self.show_text)
        self.listbox_offsets.pack(side = tk.LEFT, fill = tk.BOTH)
        self.scrollbar_offsets = tk.Scrollbar(self.frame_choix)
        self.scrollbar_offsets.pack(side = tk.RIGHT, fill = tk.BOTH)

        self.listbox_offsets.config(yscrollcommand = self.scrollbar_offsets.set)
        self.scrollbar_offsets.config(command = self.listbox_offsets.yview)

        self.frame_choix.pack(side=tk.LEFT)

        self.frame_texte = tk.Frame(self.frame_edition, borderwidth=20)

        self.labels_txt_orig = tk.Label(self.frame_texte, text="Original text:")
        self.labels_txt_orig.grid(row=1,column=1)

        self.text_orig = tk.Text(self.frame_texte, width=60, height=10, borderwidth=5, highlightbackground="#A8A8A8")
        self.text_orig.config(state=tk.DISABLED)
        self.text_orig.grid(row=2,column=1)

        self.labels_txt_trad = tk.Label(self.frame_texte, text="Translated text:")
        self.labels_txt_trad.grid(row=3,column=1)

        self.text_trad = tk.Text(self.frame_texte, width=60, height=10, borderwidth=5, highlightbackground="#A8A8A8")
        self.text_trad.grid(row=4,column=1)

        self.labels_txt_comment = tk.Label(self.frame_texte, text="Comments:")
        self.labels_txt_comment.grid(row=5,column=1)

        self.text_comment = tk.Text(self.frame_texte, width=60, height=2, borderwidth=5, highlightbackground="#A8A8A8")
        self.text_comment.grid(row=6,column=1)

        self.frame_buttons = tk.Frame(self.frame_texte, borderwidth=10)

        self.button_save_line = tk.Button(self.frame_buttons, text="Validate", command=self.validate_line)
        self.button_save_line.grid(row=1, column=1,padx=2)

        self.button_save_file = tk.Button(self.frame_buttons, text="Save", command=self.save_translation_table)
        self.button_save_file.grid(row=1, column=2,padx=2)

        self.button_translate_file = tk.Button(self.frame_buttons, text="Translate", command=self.translate_game_window)
        self.button_translate_file.grid(row=1, column=3,padx=2)

        self.button_insert_translation = tk.Button(self.frame_buttons, text="Insert", command=self.function_insert_translation)
        self.button_insert_translation.grid(row=1, column=4,padx=2)

        self.button_search_text = tk.Button(self.frame_buttons, text="Search", command=self.search_text_window)
        self.button_search_text.grid(row=1, column=5,padx=2)

        self.button_export_page = tk.Button(self.frame_buttons, text="Export page", command=self.export_page)
        self.button_export_page.grid(row=1, column=6,padx=2)

        self.button_export_all = tk.Button(self.frame_buttons, text="Export all", command=self.export_all_pages_window)
        self.button_export_all.grid(row=1, column=7,padx=2)

        self.frame_buttons.grid(row=7,column=1)

        self.frame_options = tk.Frame(self.frame_texte, borderwidth=10)

        self.text_swapText = tk.Label(self.frame_options, text="Swap text")
        self.text_swapText.grid(row=0,column=0)

        self.var_swapText = tk.BooleanVar()
        self.var_swapText.set(False)

        self.option_swapText = tk.Checkbutton(self.frame_options, variable=self.var_swapText, onvalue=True, offvalue=False)
        self.option_swapText.grid(row=0,column=1)

        self.frame_options.grid(row=8,column=1)

        self.frame_texte.pack(side=tk.LEFT)

        self.frame_edition.grid(row=2, column=1)

        self.dl_editor.protocol("WM_DELETE_WINDOW", self.closing_main_window)

        self.show_text(None)
        self.load_percentage()

    @contextlib.contextmanager
    def editable_orig_text(self):
        self.text_orig.config(state=tk.NORMAL)
        try:
            yield None
        finally:
            self.text_orig.config(state=tk.DISABLED)

    def load_percentage(self):
        percent_translated = self.table_file.translated_percent()
        self.prct_trad.delete("1.0", tk.END)
        self.prct_trad.insert("1.0", "%.1f%%" % percent_translated)

    def closing_main_window(self):

        self.warning = tk.Toplevel(self.dl_editor)
        self.warning.title("deepLuna")
        self.warning.resizable(height=False, width=False)
        self.warning.attributes("-topmost", True)
        self.warning.grab_set()

        self.warning_message = tk.Label(self.warning, text="WARNING: Do you want to close without saving?")
        self.warning_message.grid(row=0,column=0,pady=5)

        self.frame_quit_buttons = tk.Frame(self.warning, borderwidth=2)

        self.quit_and_save_button = tk.Button(self.frame_quit_buttons, text="Save and Quit", width = 15, command = self.save_and_quit)
        self.quit_and_save_button.grid(row=0,column=0,padx=5,pady=10)
        self.quit_button = tk.Button(self.frame_quit_buttons, text="Quit", width = 15, command = self.quit_editor)
        self.quit_button.grid(row=0,column=1,padx=5,pady=10)

        self.frame_quit_buttons.grid(row=1, column=0, pady=5)


    def save_and_quit(self):

        self.save_translation_table()

        self.warning.grab_release()
        self.warning.destroy()
        self.dl_editor.destroy()

    def quit_editor(self):

        self.warning.grab_release()
        self.warning.destroy()
        self.dl_editor.destroy()


    def export_page(self):

        global table_day

        if table_day != []:
            if table_day[0].scene_list[0] != 'void':
                export_day(table_day[0].scene_list[0],self.table_scr_file,self.table_file)
                self.warning = tk.Toplevel(self.dl_editor)
                self.warning.title("deepLuna")
                self.warning.resizable(height=False, width=False)
                self.warning.attributes("-topmost", True)
                self.warning.grab_set()

                self.warning_message = tk.Label(self.warning, text="Scene "+table_day[0].scene_list[0]+" exported successfully!")
                self.warning_message.grid(row=0,column=0,pady=5)

                self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                self.warning_button.grid(row=1,column=0,pady=10)
            else:
                self.warning = tk.Toplevel(self.dl_editor)
                self.warning.title("deepLuna")
                self.warning.resizable(height=False, width=False)
                self.warning.attributes("-topmost", True)
                self.warning.grab_set()

                self.warning_message = tk.Label(self.warning, text="These lines cannot be exported by nature.")
                self.warning_message.grid(row=0,column=0,pady=5)

                self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                self.warning_button.grid(row=1,column=0,pady=10)
        else:
            self.warning = tk.Toplevel(self.dl_editor)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False,width=False)
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="Select some day first.")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
            self.warning_button.grid(row=1,column=0,pady=10)


    def export_all_pages_window(self):

        self.export_all_window = tk.Toplevel(self.dl_editor)
        self.export_all_window.resizable(height=False,width=False)
        self.export_all_window.title("deepLuna — Full export")
        self.export_all_window.grab_set()
        self.expected_time_exp = tk.StringVar()
        self.expected_time_exp.set('0:00:00')

        self.frame_question = tk.Frame(self.export_all_window, borderwidth=2)

        self.question_message = tk.Label(self.frame_question, text="Do you want to export all the text files?\nThis might take some time.")
        self.question_message.grid(row=0,column=0,pady=5)

        self.button_ok = tk.Button(self.frame_question,text="OK", bg="#CFCFCF", width=10, command=self.export_all_pages)
        self.button_ok.grid(row=0,column=1,pady=10)

        self.frame_question.grid(row=0, column=0, padx=5, pady=5)

        self.progress_export = Progressbar(self.export_all_window, style="blue.Horizontal.TProgressbar", orient = tk.HORIZONTAL, length = 300, mode = 'determinate')
        self.progress_export.grid(row=1,column=0,padx=20,pady=20)

        self.time_frame_exp = tk.Frame(self.export_all_window, borderwidth=10)

        self.remaining_time_text_exp = tk.Label(self.time_frame_exp, text="Estimated remaining time: ")
        self.remaining_time_text_exp.grid(row=0,column=0,pady=10)

        self.remaining_time_exp = tk.Label(self.time_frame_exp, textvariable=self.expected_time_exp)
        self.remaining_time_exp.grid(row=0,column=1,pady=10)

        self.time_frame_exp.grid(row=2,column=0,pady=10)


    def export_all_pages(self):
        # Save the translation table
        self.save_translation_table()

        # Get the total number of scenes to export
        scene_names = self.table_scr_file.scene_names()
        len_export = len(scene_names)

        print("Exporting whole database:")
        start_export = time.time()
        for i in range(len_export):
            # Export that day
            export_day(scene_names[i], self.table_scr_file, self.table_file)
            # Update the progress indicator
            self.progress_export["value"] = floor((i+1)/len_export*100)
            # Estimated completion
            new_time_exp = datetime.timedelta(seconds=time.time()-start_export)
            accum_lines_exp = i+1
            remain_time_exp = (len_export+1-i)*new_time_exp/accum_lines_exp
            self.expected_time_exp.set(str(remain_time_exp).split('.')[0])
            root.update()
            print(f"{scene_names[i]}.txt exported")

        print("Exporting done!")

        self.export_all_window.destroy()
        root.update()
        self.warning = tk.Toplevel(self.dl_editor)
        self.warning.title("deepLuna")
        self.warning.resizable(height=False, width=False)
        self.warning.attributes("-topmost", True)
        self.warning.grab_set()

        self.warning_message = tk.Label(self.warning, text="Text exported successfully!")
        self.warning_message.grid(row=0,column=0,pady=5)

        self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
        self.warning_button.grid(row=1,column=0,pady=10)


    def selectItem(self,event):

        self.curItem = self.tree.focus()
        if (self.tree.item(self.curItem)["text"][:3] != "Day" and self.tree.item(self.curItem)["text"][:3] != "Arc" and self.tree.item(self.curItem)["text"][:3] != "Cie" and self.tree.item(self.curItem)["text"][:3] != "Tea" and self.tree.item(self.curItem)["text"][:3] != "Com" and self.tree.item(self.curItem)["text"] != '' and self.tree.item(self.curItem)["text"][:3] != "Hid"):
            self.open_day(self.tree.item(self.curItem)["text"])
            root.update()
        else:
            if self.tree.item(self.curItem)["text"][:3] == "Hid":
                self.open_day("void")
                root.update()

    def function_insert_translation(self):

        global swapText

        if self.var_swapText.get():
            if swapText:
                self.save_translation_table()
                insert_translation("script_text.mrg","table.txt","script_text_translated"+time.strftime('%Y%m%d-%H%M%S')+".mrg",swapText)

                self.warning = tk.Toplevel(self.dl_editor)
                self.warning.title("deepLuna")
                self.warning.resizable(height=False, width=False)
                self.warning.attributes("-topmost", True)
                self.warning.grab_set()

                self.warning_message = tk.Label(self.warning, text="Text inserted successfully!")
                self.warning_message.grid(row=0,column=0,pady=5)

                self.warning_button = tk.Button(self.warning, text="Close", command = lambda : self.pushed(self.warning))
                self.warning_button.grid(row=1,column=0,pady=10)

            else:
                self.swap_table_window()


        else:
            self.save_translation_table()

            insert_translation("script_text.mrg","table.txt","script_text_translated"+time.strftime('%Y%m%d-%H%M%S')+".mrg")

            self.warning = tk.Toplevel(self.dl_editor)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False, width=False)
            self.warning.attributes("-topmost", True)
            try:
                self.warning.grab_set()
            except Exception as e:
                print(e)

            self.warning_message = tk.Label(self.warning, text="Text inserted successfully!")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Close", command = lambda : self.pushed(self.warning))
            self.warning_button.grid(row=1,column=0,pady=10)


    def swap_table_window(self):

        global swapText

        self.swap_window = tk.Toplevel(self.dl_editor)
        self.swap_window.resizable(height=False, width=False)
        self.swap_window.title("deepLuna — Create swap table")
        self.swap_window.grab_set()

        self.label_swap = tk.Label(self.swap_window, text="Enter the character pairs to be swapped:")
        self.label_swap.grid(row=0,column=0)

        self.swap_text_zone = tk.Text(self.swap_window, width=20, height=25, borderwidth=5, highlightbackground="#A8A8A8")
        self.swap_text_zone.grid(row=1,column=0)

        self.swap_frame_buttons = tk.Frame(self.swap_window, borderwidth=10)

        self.swap_ok_button = tk.Button(self.swap_frame_buttons, text="OK", command=self.get_swap_table)
        self.swap_ok_button.grid(row=0,column=0)

        self.swap_warning_button = tk.Button(self.swap_frame_buttons, text="Cancel", command = lambda : self.pushed(self.swap_window))
        self.swap_warning_button.grid(row=0,column=1,pady=10)

        self.swap_frame_buttons.grid(row=2,column=0)

    def get_swap_table(self):

        global swapText

        self.save_translation_table()

        self.get_swap_text = self.swap_text_zone.get("1.0", tk.END)
        if self.get_swap_text == '':
            swapText = False
        else:
            #print(self.get_swap_text)
            self.get_swap_text = self.get_swap_text.strip("\n")
            #print(self.get_swap_text)
            swapText = [pair.split(",") for pair in self.get_swap_text.split("\n")]
            with open("config.ini", "r+", encoding="utf-8") as self.r_config:
                self.data_config = self.r_config.read()
            self.data_config = self.data_config.replace("swapText=0","swapText="+str(swapText))
            with open("config.ini", "w+", encoding="utf-8") as self.w_config:
                self.w_config.write(self.data_config)

            insert_translation("script_text.mrg","table.txt","script_text_translated"+time.strftime('%Y%m%d-%H%M%S')+".mrg",swapText)

            self.warning = tk.Toplevel(self.dl_editor)
            self.warning.title("deepLuna")
            self.warning.resizable(height=False, width=False)
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="Text inserted successfully!")
            self.warning_message.grid(row=0,column=0,pady=5)

            self.warning_button = tk.Button(self.warning, text="Close", command = lambda : self.pushed(self.warning))
            self.warning_button.grid(row=1,column=0,pady=10)

        self.pushed(self.swap_window)


    def pushed(self,sub_win):
        sub_win.grab_release()
        sub_win.destroy()

    def align_page(self,page,length):
        return('0'*(length-len(page))+page)

    def open_day(self,table_day_name):
        global table_day
        print("Loading the selected day...")
        if table_day_name != False:
            table_day = gen_day_subtable(table_day_name,self.table_scr_file,self.table_file)
        if table_day != []:
            self.listbox_offsets.delete(0,tk.END)
            with self.editable_orig_text():
                self.text_orig.delete("1.0", tk.END)
                self.text_trad.delete("1.0", tk.END)
            global n_trad_day
            n_trad_day = 0
            self.len_table_day = len(table_day)
            for self.i in range(self.len_table_day):
                self.listbox_offsets.insert(
                    self.i,
                    self.align_page(
                        str(table_day[self.i].page_number),
                        len(str(table_day[-1].page_number))
                    ) + " : " + table_day[self.i].offset_label()
                )

                if table_day[self.i].is_translated():
                    # Green for translated and inserted
                    self.listbox_offsets.itemconfig(self.i, bg='#BCECC8')
                    n_trad_day = n_trad_day + 1

            self.prct_trad_day.delete("1.0", tk.END)
            self.prct_trad_day.insert("1.0", str(round(n_trad_day*100/len(table_day),1))+"%")
            self.name_day.set(str(table_day[0].scene_list[0])+": ")
        else:
            print("This day is empty.")
        print("Day loaded!")

    def open_table(self):
        self.listbox_offsets.delete(0,tk.END)
        with self.editable_orig_text():
            self.text_orig.delete("1.0", tk.END)
            self.text_trad.delete("1.0", tk.END)
        self.csv = open('table.txt', "r+", encoding='utf-8')
        self.csv.close()
        global n_trad
        n_trad = 0
        for i in range(len(self.table_file)):
            if self.table_file[i][3] == 1:
                self.listbox_offsets.insert(i, str(i+1)+": "+self.table_file[i][0]+' *')
            else:
                self.listbox_offsets.insert(i, str(i+1)+": "+self.table_file[i][0])
            if self.table_file[i][2] != "TRANSLATION":
                self.listbox_offsets.itemconfig(i, bg='#BCECC8') #green for translated and inserted
                n_trad = n_trad + 1

        self.prct_trad.delete("1.0",tk.END)
        self.prct_trad.insert("1.0", str(round(n_trad*100/len(self.table_file),1))+"%")

    def show_text(self,event):
        global cs
        global table_day
        cs = self.listbox_offsets.curselection()
        if cs == ():
            cs = (0,)
        else:
            for offset in cs:
                with self.editable_orig_text():
                    self.text_orig.delete("1.0", tk.END)
                    self.text_trad.delete("1.0", tk.END)
                    self.text_comment.delete("1.0", tk.END)
                    self.text_orig.insert("1.0", table_day[offset].jp_text)
                    split_translation = table_day[offset].translated_text.split('//')
                    self.text_trad.insert("1.0", split_translation[0])
                    if len(split_translation) == 2:
                        self.text_comment.insert("1.0", split_translation[1])


    def ctrlEvent(self,event):
        if(12==event.state and event.keysym=='c') or (8==event.state and event.keysym=='c') or event.char=='\uf700' or event.char=='\uf701' or event.char=='\uf702' or event.char=='\uf703':
            return
        else:
            return "break"

    def validate_line(self):

        global search_window_open
        global posSearch
        global searchResults
        global n_trad
        global n_trad_day
        global table_day

        # Load the entry that we are validating
        entry_offset = self.listbox_offsets.curselection()[0]
        entry = table_day[entry_offset]

        # Load input translation text / comment from UI
        self.line = self.text_trad.get("1.0", tk.END).strip('\n')
        self.comment = self.text_comment.get("1.0", tk.END).strip('\n')

        # If the translation and comment are valid, conjoin them
        if self.comment and self.line != TRANSLATION_PLACEHOLDER:
            self.line = self.line + '//' + self.comment

        # If the translation input is the raw 'TRANSLATION' placeholder,
        # _clear_ the translation on this entry
        if self.line == TRANSLATION_PLACEHOLDER:
            entry.clear_translation()
            # Clear highlight for line
            self.listbox_offsets.itemconfig(entry_offset, bg='#FFFFFF')
        else:
            # If the input translation text valid, check if it fits
            split_line = self.line.split('#')

            # If the numbers are wrong, highlight red and crash operation
            if len(entry.offset_list) != len(split_line):
                self.listbox_offsets.itemconfig(entry_offset, bg='#ECBDBC')
                assert False, "Line count mismatch - expected %d, got %d" % (
                    len(entry.offset_list), len(split_line))

            # Apply the translation string to the merged entry
            entry.set_translation(split_line)

            # Mark this entry as green
            self.listbox_offsets.itemconfig(entry_offset, bg='#BCECC8')

        # Apply the changes in this translation entry back to the master table
        self.table_file.apply_update(entry)

        # Regenerate the translation percentages for the day / overall
        self.load_percentage()  # Global
        day_translated_count = functools.reduce(
            lambda acc, entry: acc + 1 if entry.is_translated() else acc,
            table_day, 0)
        day_translated_percent = \
            float(day_translated_count) * 100.0 / len(table_day)
        self.prct_trad_day.delete("1.0", tk.END)
        self.prct_trad_day.insert("1.0", "%.1f%%" % day_translated_percent)

        if search_window_open and len(searchResults) > 0:
            try:
                self.search_text()
            except IndexError:
                posSearch = posSearch-1
                self.search_text()


    def save_translation_table(self):
        global search_window_open
        global posSearch
        global searchResults
        global table_day

        print("Saving file, please wait...")
        self.table_file.serialize_to_file("table.txt")
        print("Database saved!")

    def search_text_window(self):

        global searchResults
        global search_window_open
        global posSearch
        global table_day

        if not search_window_open:
            search_window_open = True

            self.search_window = tk.Toplevel(self.dl_editor)
            self.search_window.resizable(height=False, width=False)
            self.search_window.title("deepLuna — Search")
            #self.search_window.attributes("-topmost", True)
            self.search_window.grab_set()

            self.search_frame = tk.Frame(self.search_window,borderwidth=10)

            self.search_field = tk.Text(self.search_frame, width=30, height=1, borderwidth=5, highlightbackground="#A8A8A8")
            self.search_field.grid(row=0,column=0,padx=5,pady=10)

            self.search_button = tk.Button(self.search_frame, text="Search", command=self.search_text)
            self.search_button.grid(row=0,column=1,padx=5,pady=10)

            self.search_frame.grid(row=0,column=0,pady=10)

            self.result_frame = tk.Frame(self.search_window,borderwidth=10)

            self.result_field = tk.Text(self.result_frame, width=15, height=1, borderwidth=5, highlightbackground="#A8A8A8")
            self.result_field.bind("<Key>", lambda e: self.ctrlEvent(e))
            self.result_field.grid(row=0,column=0,padx=5,pady=10)

            self.prev_button = tk.Button(self.result_frame, text="Previous", state=tk.DISABLED, command=self.prev_text)
            self.prev_button.grid(row=0,column=1,padx=5,pady=10)

            self.next_button = tk.Button(self.result_frame, text="Next", state=tk.DISABLED, command=self.next_text)
            self.next_button.grid(row=0,column=2,padx=5,pady=10)

            self.result_frame.grid(row=1,column=0,pady=10)

            self.replace_frame = tk.Frame(self.search_window,borderwidth=10)

            self.replace_field = tk.Text(self.replace_frame, width=25, height=1, borderwidth=5, highlightbackground="#A8A8A8")
            self.replace_field.grid(row=0,column=0,padx=5,pady=10)

            self.replace_button = tk.Button(self.replace_frame, text="Replace", state=tk.DISABLED, command=self.replace_text)
            self.replace_button.grid(row=0,column=1,padx=5,pady=10)

            self.all_replace_button = tk.Button(self.replace_frame, text="Replace all", state=tk.DISABLED, command=self.all_replace_text)
            self.all_replace_button.grid(row=0,column=2,padx=5,pady=10)

            self.replace_frame.grid(row=2,column=0,pady=10)

            self.search_window.protocol("WM_DELETE_WINDOW", self.closing_search_window)

    def closing_search_window(self):

        global search_window_open
        global searchResults
        global posSearch

        self.search_window.grab_release()
        self.search_window.destroy()
        self.dl_editor.grab_set()
        search_window_open = False
        searchResults = []
        posSearch = 0

    def replace_text(self):

        global searchResults
        global posSearch
        global table_day

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]
        self.replacement_text = self.replace_field.get("1.0",tk.END)[:-1]

        self.pos_text = table_day.index(searchResults[posSearch])

        if self.txt_to_search in table_day[self.pos_text][2]:
            table_day[self.pos_text][2] = table_day[self.pos_text][2].replace(self.txt_to_search,self.replacement_text)

        if len(searchResults) == 1:
            self.listbox_offsets.selection_clear(0, tk.END)
            self.listbox_offsets.see(self.pos_text)
            self.listbox_offsets.select_set(self.pos_text)
            self.listbox_offsets.activate(self.pos_text)
            with self.editable_orig_text():
                self.text_orig.delete("1.0", tk.END)
                self.text_trad.delete("1.0", tk.END)
                self.text_orig.insert("1.0", table_day[self.pos_text][1])
                self.text_trad.insert("1.0", table_day[self.pos_text][2])
            posSearch = 0

        self.search_text()

    def all_replace_text(self):

        global searchResults
        global posSearch
        global table_day

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]
        self.replacement_text = self.replace_field.get("1.0",tk.END)[:-1]

        for self.j in range(len(searchResults)):
            self.pos_text = table_day.index(searchResults[self.j])

            if self.txt_to_search in table_day[self.pos_text][2]:
                table_day[self.pos_text][2] = table_day[self.pos_text][2].replace(self.txt_to_search,self.replacement_text)


        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        with self.editable_orig_text():
            self.text_orig.delete("1.0", tk.END)
            self.text_trad.delete("1.0", tk.END)
            self.text_orig.insert("1.0", table_day[self.pos_text][1])
            self.text_trad.insert("1.0", table_day[self.pos_text][2])

        posSearch = 0

        self.search_text()

        self.search_text()



    def search_text(self):

        global searchResults
        global posSearch
        global table_day

        searchResults = []

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]

        for self.k in range(len(table_day)):
            if (self.txt_to_search in table_day[self.k][1]) or (self.txt_to_search in table_day[self.k][2]):
                searchResults.append(table_day[self.k])

        self.result_field.delete("1.0",tk.END)
        self.result_field.insert("1.0", str(len(searchResults))+(" résultat" if len(searchResults) == 1 else " résultats"))


        if len(searchResults)>0:
            try:
                self.pos_text = table_day.index(searchResults[posSearch])
            except IndexError:
                posSearch -= 1
                self.pos_text = table_day.index(searchResults[posSearch])
            self.listbox_offsets.selection_clear(0, tk.END)
            self.listbox_offsets.see(self.pos_text)
            self.listbox_offsets.select_set(self.pos_text)
            self.listbox_offsets.activate(self.pos_text)
            with self.editable_orig_text():
                self.text_orig.delete("1.0", tk.END)
                self.text_trad.delete("1.0", tk.END)
                self.text_orig.insert("1.0", table_day[self.pos_text][1])
                self.text_trad.insert("1.0", table_day[self.pos_text][2])

        if len(searchResults) == 0 or len(searchResults) == 1:
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
        else:
            self.prev_button.config(state=tk.DISABLED if posSearch==0 else tk.NORMAL)
            self.next_button.config(state=tk.NORMAL if posSearch<len(searchResults)-1 else tk.DISABLED)

        self.replace_button.config(state=tk.DISABLED if len(searchResults)==0 else tk.NORMAL)
        self.all_replace_button.config(state=tk.DISABLED if len(searchResults)==0 else tk.NORMAL)

    def next_text(self):

        global searchResults
        global posSearch
        global table_day

        posSearch = posSearch+1
        self.pos_text = table_day.index(searchResults[posSearch])

        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        with self.editable_orig_text():
            self.text_orig.delete("1.0", tk.END)
            self.text_trad.delete("1.0", tk.END)
            self.text_orig.insert("1.0", table_day[self.pos_text][1])
            self.text_trad.insert("1.0", table_day[self.pos_text][2])

        if posSearch == len(searchResults)-1:
            self.next_button.config(state=tk.DISABLED)
            self.prev_button.config(state=tk.NORMAL)
        else:
            self.next_button.config(state=tk.NORMAL)
            self.prev_button.config(state=tk.NORMAL)

    def prev_text(self):

        global searchResults
        global posSearch
        global table_day

        posSearch = posSearch-1
        self.pos_text = table_day.index(searchResults[posSearch])

        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        with self.editable_orig_text():
            self.text_orig.delete("1.0", tk.END)
            self.text_trad.delete("1.0", tk.END)
            self.text_orig.insert("1.0", table_day[self.pos_text][1])
            self.text_trad.insert("1.0", table_day[self.pos_text][2])

        if posSearch == 0:
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.NORMAL)
        else:
            self.prev_button.config(state=tk.NORMAL)
            self.next_button.config(state=tk.NORMAL)


    def translate_game_window(self):

        global cs
        global translationApi
        global translationLanguage
        global blockTranslation
        global table_day

        self.test_cs = self.listbox_offsets.curselection()
        if len (self.test_cs)>0:
            cs = self.test_cs

        self.translation = tk.Toplevel(self.dl_editor)
        self.translation.resizable(height=False,width=False)
        self.translation.title("deepLuna — Translation")
        #self.translation.attributes("-topmost", True)
        self.translation.grab_set()
        self.expected_time = tk.StringVar()
        self.expected_time.set('0:00:00')


        self.set_translation_frame = tk.Frame(self.translation, borderwidth=10)

        self.deepl_api_message = tk.Label(self.set_translation_frame, text="deepL API link:")
        self.deepl_api_message.grid(row=0,column=0,pady=10)

        self.deepl_api = tk.Text(self.set_translation_frame, width=15, height=1, borderwidth=5, highlightbackground="#A8A8A8")
        self.deepl_api.insert("1.0", ','.join(translationApi))
        self.deepl_api.grid(row=0, column=1, pady=10)

        self.lang_message = tk.Label(self.set_translation_frame, text="Language:")
        self.lang_message.grid(row=1,column=0,pady=10)

        self.lang = tk.Text(self.set_translation_frame, width=15, height=1, borderwidth=5, highlightbackground="#A8A8A8")
        self.lang.insert("1.0", translationLanguage)
        self.lang.grid(row=1, column=1, pady=10)

        self.block_tl_message = tk.Label(self.set_translation_frame, text="Block translation:")
        self.block_tl_message.grid(row=2,column=0)

        self.var_block_tl = tk.BooleanVar()
        self.var_block_tl.set(blockTranslation)

        self.graph_advanced_options = tk.Checkbutton(self.set_translation_frame, variable=self.var_block_tl, onvalue=True, offvalue=False)
        self.graph_advanced_options.grid(row=2,column=1)

        self.message = tk.Label(
            self.set_translation_frame,
            text=(
                "Translate starting from the line " +
                str(table_day[cs[0]].offset_label()) + " until line " +
                str(table_day[cs[-1]].offset_label()) + "?"
                if len(cs) > 1
                else "Translate the line " +
                str(table_day[cs[0]].offset_label()) + "?"
            )
        )
        self.message.grid(row=3,column=0,pady=10)

        self.launch_butten = tk.Button(self.set_translation_frame, text="OK", command = self.translate_game)
        self.launch_butten.grid(row=3,column=1,padx=10,pady=10)

        self.set_translation_frame.grid(row=0,column=0,pady=10)

        self.progress_translate = Progressbar(self.translation, style="blue.Horizontal.TProgressbar", orient = tk.HORIZONTAL, length = 300, mode = 'determinate')
        self.progress_translate.grid(row=1,column=0,padx=20,pady=20)

        self.time_frame = tk.Frame(self.translation, borderwidth=10)

        self.remaining_time_text = tk.Label(self.time_frame, text="Estimated remaining time: ")
        self.remaining_time_text.grid(row=0,column=0,pady=10)

        self.remaining_time = tk.Label(self.time_frame, textvariable=self.expected_time)
        self.remaining_time.grid(row=0,column=1,pady=10)

        self.time_frame.grid(row=2,column=0,pady=10)

        self.translation.protocol("WM_DELETE_WINDOW", self.closing_translation_window)

    def closing_translation_window(self):

        self.s.theme_use('default')
        self.translation.grab_release()
        self.translation.destroy()
        self.dl_editor.grab_set()


    def translate_game(self):

        global cs
        global translationApi
        global translationLanguage #'EN' for english/'FR' for french
        global blockTranslation
        global table_day

        self.save_cs = cs

        self.intern_translationApi = self.deepl_api.get("1.0", tk.END)[:-1]
        self.intern_translationLanguage = self.lang.get("1.0", tk.END)[:-1]

        if len(self.intern_translationApi) > 10:

            config = open("config.ini","w+")
            config.write("translationApi="+self.intern_translationApi+"\n")
            translationApi = self.intern_translationApi.split(',')
            config.write("translationLanguage="+self.intern_translationLanguage+"\n")
            translationLanguage = self.intern_translationLanguage
            config.write("blockTranslation="+("1" if self.var_block_tl.get() else "0"))
            blockTranslation = self.var_block_tl.get()
            config.close()

            self.error = False
            self.progress_translate["value"] = 0
            self.progress_translate["maximum"] = 1000
            self.len_translation = cs[-1]-cs[0]+1

            self.len_translationApi = len(translationApi)
            self.finished_var = False
            self.j = 0

            if not blockTranslation:
                #DeepL line-by-line translation
                print("\nAutomatic translation of the game with deepL (line-by-line):")
                self.start = time.time()
                while (self.j < self.len_translationApi and not self.finished_var):
                    #print(cs)
                    for self.i in range(cs[0],cs[-1]+1):
                        try:
                            self.translated_text = requests.post(url='https://api-free.deepl.com/v2/translate', data={'auth_key':translationApi[self.j],'target_lang':translationLanguage,'text':table_day[self.i][1] if table_day[self.i][3] == 0 else re.sub(r"(\<)|(\|.+?\>)", r"",table_day[self.i][1])})
                            self.translated_text = self.translated_text.json()["translations"][0]["text"]
                            print("\n*** Line n°"+str(self.i+1)+" ***")
                            print("JP: "+str(table_day[self.i][1]))
                        except:
                            cs = cs[(self.i-cs[0]):]
                            if self.j < self.len_translationApi - 1:
                                print("Encountered error. Trying to use next API link...")
                            else:
                                print("Encountered error. Stopping the translation...")
                            break
                        #table_day[self.i][2] = self.translated_text

                        if type(table_day[self.i][0]) == str:
                            table_day[self.i][2] = self.translated_text
                            print(translationLanguage+": "+table_day[self.i][2])
                        else:
                            table_day[self.i][2] = self.translated_text
                            self.translated_text = self.translated_text.split('#')

                            if len(self.translated_text) > len(table_day[self.i][0]):
                                self.translated_text = self.translated_text[:len(table_day[self.i][0])]
                                table_day[self.i][2] = '#'.join(self.translated_text)
                            else:
                                if len(self.translated_text) < len(table_day[self.i][0]):
                                    for self.erlen in range(len(table_day[self.i][0])-len(self.translated_text)):
                                        self.translated_text.append("ERROR")
                                    table_day[self.i][2] = '#'.join(self.translated_text)


                            for self.l in range(len(table_day[self.i][0])):
                                for self.k in range(len(self.table_file)):
                                    if self.table_file[self.k][0] == table_day[self.i][0][self.l]:
                                        self.table_file[self.k] = [self.table_file[self.k][0],self.table_file[self.k][1],self.translated_text[self.l],self.table_file[self.k][3],self.table_file[self.k][4],self.table_file[self.k][5],self.table_file[self.k][6],self.table_file[self.k][7],self.table_file[self.k][8]]
                            print(translationLanguage+": "+table_day[self.i][2])

                        self.progress_translate["value"] = floor((self.i-cs[0]+1)/self.len_translation*1000)
                        self.new_time = datetime.timedelta(seconds=time.time()-self.start)
                        self.accum_lines = self.i-cs[0]+1
                        self.remain_time = (cs[-1]+1-self.i)*self.new_time/self.accum_lines
                        self.expected_time.set(str(self.remain_time).split('.')[0])
                        root.update()


                    if self.i < cs[-1] or (len(cs) == 1 and cs == self.save_cs and table_day[cs[0]][2] == 'TRANSLATION'):
                        self.j += 1
                        self.error = True
                    else:
                        self.finished_var = True
                        self.error = False


                if not self.error:
                    self.save_translation_table()
                    self.translation.destroy()
                    self.open_day(False)
                    self.listbox_offsets.see(self.save_cs[-1])
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.resizable(height=False, width=False)
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="Text translated successfully!")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

                else:
                    self.save_translation_table()
                    self.translation.destroy()
                    self.open_day(False)
                    self.listbox_offsets.see(self.i)
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.resizable(height=False, width=False)
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="ERROR: Text translated only partially. Please start again from the line "+str(table_day[self.i][4]))
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

            else:
                #DeepL block translation
                print("\nAutomatic translation of the game with deepL (block)")
                self.start = time.time()
                while (self.j < self.len_translationApi and not self.finished_var):
                    self.block_text = '\n'.join([re.sub(r"(\<)|(\|.+?\>)", r"", elem[1]) for elem in table_day[cs[0]:cs[-1]+1]])
                    try:
                        self.translated_text = requests.post(url='https://api-free.deepl.com/v2/translate', data={'auth_key':translationApi[self.j],'target_lang':translationLanguage,'text':self.block_text})
                        self.translated_text = self.translated_text.json()["translations"][0]["text"]
                        self.translated_text = self.translated_text.split('\n')
                        for self.k in range(cs[0],cs[-1]+1):
                            #table_day[self.k][2] = self.translated_text[self.k-cs[0]]

                            if type(table_day[self.k][0]) == str:
                                table_day[self.k][2] = self.translated_text[self.k-cs[0]]
                            else:
                                table_day[self.k][2] = self.translated_text[self.k-cs[0]]
                                self.translated_text[self.k-cs[0]] = self.translated_text[self.k-cs[0]].split('#')

                                if len(self.translated_text[self.k-cs[0]]) > len(table_day[self.k][0]):
                                    self.translated_text[self.k-cs[0]] = self.translated_text[self.k-cs[0]][:len(table_day[self.k][0])]
                                    table_day[self.k][2] = '#'.join(self.translated_text[self.k-cs[0]])
                                else:
                                    if len(self.translated_text[self.k-cs[0]]) < len(table_day[self.k][0]):
                                        for self.erlen in range(len(table_day[self.k][0])-len(self.translated_text[self.k-cs[0]])):
                                            self.translated_text[self.k-cs[0]].append("ERROR")
                                        table_day[self.k][2] = '#'.join(self.translated_text[self.k-cs[0]])

                                for self.l in range(len(table_day[self.k][0])):
                                    for self.m in range(len(self.table_file)):
                                        if self.table_file[self.m][0] == table_day[self.k][0][self.l]:
                                            self.table_file[self.m] = [self.table_file[self.m][0],self.table_file[self.m][1],self.translated_text[self.k-cs[0]][self.l],self.table_file[self.m][3],self.table_file[self.m][4],self.table_file[self.m][5],self.table_file[self.m][6],self.table_file[self.m][7],self.table_file[self.m][8]]

                            print("\n*** Line n°"+str(self.k+1)+" ***")
                            print("JP: "+str(table_day[self.k][1]))
                            print(translationLanguage+": "+table_day[self.k][2])
                            self.progress_translate["value"] = floor((self.k-cs[0]+1)/self.len_translation*1000)
                            #self.save_translation_table()
                            self.new_time = datetime.timedelta(seconds=time.time()-self.start)
                            self.accum_lines = self.k-cs[0]+1
                            self.remain_time = (cs[-1]+1-self.k)*self.new_time/self.accum_lines
                            self.expected_time.set(str(self.remain_time).split('.')[0])
                            root.update()
                        self.finished_var = True
                        self.error = False
                    except:
                        self.j += 1
                        self.finished_var = False
                        self.error = True
                        if self.j < self.len_translationApi - 1:
                            print("Encountered error. Trying to use next API link...")
                        else:
                            print("Encountered error. Stopping the translation...")

                if not self.error:
                    self.save_translation_table()
                    self.translation.destroy()
                    self.open_day(False)
                    self.listbox_offsets.see(self.save_cs[-1])
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.resizable(height=False, width=False)
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="Text translated successfully!")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

                else:
                    self.save_translation_table()
                    self.translation.destroy()
                    self.open_day(False)
                    self.listbox_offsets.see(self.save_cs[0])
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.resizable(height=False, width=False)
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="ERROR: Text couldn\'t be translated. Use another API link or do the translation manually.")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)


if __name__ == '__main__':
    root = tk.Tk()
    deepLuna = StartWindow(root)
    root.mainloop()
