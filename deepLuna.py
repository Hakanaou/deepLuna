###Import packages
try:
    import tkinter as tk
except ImportError:
    install("tkinter")
    import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfile
from tkinter.ttk import *
import webbrowser
try:
    import subprocess
except ImportError:
    install("subprocess")
    import subprocess
from math import floor
import time
try:
    from PIL import ImageTk, Image
except ImportError:
    install("Pillow")
    from PIL import ImageTk, Image
import random
import sys
import requests
import json
import time
import datetime
import ast
import re
import os

###Global variables and config.ini initialisation

searchResults = []
posSearch = 0
search_window_open = False
cs = [1]
n_trad = 0

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
        config.write("blockTranslation=0")
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
    config.write("blockTranslation=0")
    config.close()


###Basic functions

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

def extract_text(scriptFile,outputFile):

    script = open(scriptFile, 'rb')
    extractedText = open(outputFile,'w+',encoding="utf-8")

    data = script.read()

    extractedTable = []
    offset = '0x2AF48'

    pointerWord = b'\x00\x00\x00\x00'
    nextPointerWord = b'\x00\x00\x00A'
    positionText =  offset
    positionPointer = '0x58'

    furiganaFlag = 0

    while nextPointerWord != b'\xFF\xFF\xFF\xFF':

        #print(pointerWord)
        #print(nextPointerWord)
        #print(positionText)
        #print(positionPointer)

        textPointer = hexsum(pointerWord.hex(),offset)
        textStr = data[int(positionText,16):int(hexsum(offset,nextPointerWord.hex()),16)-2]
        textStr = textStr.decode('utf-8')
        newLine = [textPointer,textStr,'TRANSLATION',1 if re.search(r"\<.+?\|.+?\>",textStr) else 0]

        extractedTable.append(newLine)
        #print(newLine)

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


def insert_translation(scriptFile,translatedText,scriptFileTranslated):

    scriptJP = open(scriptFile, 'rb')
    scriptTL = open(scriptFileTranslated, 'wb')
    translatedTextFile = open(translatedText, 'r', encoding="utf-8")

    dataJPFile = scriptJP.read()

    dataTLFile = translatedTextFile.read()
    dataTLFile = dataTLFile.split('\n')
    dataTLFile = [ast.literal_eval(elem) for elem in dataTLFile]

    startJPFile = dataJPFile[0:int('58',16)]
    endJPFile = dataJPFile[int('36B89F',16):]

    bytesNewPointers = b'\x00\x00\x00\x00'
    totalLenText = '00000000'
    bytesListTLText = b''

    #bytesListTest = dataJPFile[:int('2AF48',16)]

    #print(len(bytesListTest))

    for line in dataTLFile:

        newLine = line[1].encode("utf-8")+b'\x0D\x0A' if line[2] == 'TRANSLATION' else line[2].encode("utf-8")+b'\x0D\x0A'
        bytesListTLText += newLine
        totalLenText = add_zeros(hexsum(totalLenText,hex(len(newLine)))[2:])
        #print(totalLenText)
        bytesNewPointers += bytes.fromhex(totalLenText)

    bytesListTLText = bytesListTLText[:-2]
    bytesNewPointers = bytesNewPointers[:-4] + bytesNewPointers[-8:-4] + 12*b'\xFF'

    #print(len(startJPFile + bytesNewPointers))

    totalNewFile = startJPFile + bytesNewPointers + bytesListTLText + endJPFile

    scriptTL.write(totalNewFile)


        #listPointers.append(bytes.fromhex(hexsum(line[0],'-0x2AF48')[2:]))

    scriptJP.close()
    scriptTL.close()
    translatedTextFile.close()


###GUI Interface


class StartWindow:

    def __init__(self,welcome):
        self.welcome = welcome
        welcome.title("Welcome to deepLuna")
        welcome.resizable(height=False, width=False)
        self.frame_image = tk.Frame(welcome, borderwidth=5)
        #self.icone = tk.PhotoImage(file="icone.gif")
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
        #self.info_window.iconbitmap("AteliELF.ico")
        #self.welcome.withdraw()

        self.info_window.attributes("-topmost", True)
        self.info_window.grab_set()

        self.info = Informations(self.info_window)

    def function_extract(self):
        if os.path.exists("script_text.mrg"):
            self.table_jp = extract_text("script_text.mrg","table.txt")

            self.translation_window = tk.Toplevel(self.welcome)

            self.translation_window.attributes("-topmost", True)
            self.translation_window.grab_set()

            self.analysis = MainWindow(self.translation_window, self.table_jp)

    def open_main_window(self):
        try:
            self.table_jp = read_table("table.txt")
            self.translation_window = tk.Toplevel(self.welcome)

            self.translation_window.attributes("-topmost", True)
            self.translation_window.grab_set()

            self.analysis = MainWindow(self.translation_window, self.table_jp)

        except:
            self.warning = tk.Toplevel(self.welcome)
            #self.warning.iconbitmap("AteliELF.ico")
            self.warning.title("deepLuna")
            self.warning.attributes("-topmost", True)
            self.warning.grab_set()

            self.warning_message = tk.Label(self.warning, text="WARNING: Table file not found. Extract first the text of the game.")
            self.warning_message.grid(row=0,column=0,pady=5)



class Informations:
    def __init__(self,information):
        self.informations = information

        information.title("deepLuna — About")
        information.geometry("400x150")
        information.resizable(height=False, width=False)

        self.nom = tk.Label(information, text ="deepLuna version 1 — 1/9/2021\nDevelopped by Tsukihimates\n", justify=tk.CENTER, borderwidth=10)
        self.nom.pack()

        self.explanations = tk.Button(information, text="https://github.com/Hakanaou/deepLuna", command=self.callback)
        self.explanations.pack()

    def callback(self):
        webbrowser.open_new("https://github.com/Hakanaou/deepLuna")


class MainWindow:

    def __init__(self,dl_editor,table):

        global cs
        global translationApi
        global translationLanguage #'EN' for english/'FR' for french
        global blockTranslation

        self.dl_editor = dl_editor

        self.table_file = table

        dl_editor.resizable(height=False, width=False)
        dl_editor.title("deepLuna — Editor")

        self.frame_infos = tk.Frame(dl_editor, borderwidth=20)

        self.label_prct_trad = tk.Label(self.frame_infos, text="Translated text: ")
        self.label_prct_trad.grid(row=1, column=0)

        self.prct_trad = tk.Text(self.frame_infos, width=6, height=1, borderwidth=5, highlightbackground="#A8A8A8")
        self.prct_trad.bind("<Key>", lambda e: self.ctrlEvent(e))
        self.prct_trad.grid(row=1, column=5)

        self.frame_infos.grid(row=1, column=1)

        self.frame_edition = tk.Frame(dl_editor, borderwidth=1)


        self.frame_choix = tk.Frame(self.frame_edition, borderwidth=20)

        self.label_offsets = tk.Label(self.frame_choix, text="Original text offsets:")
        self.label_offsets.pack()

        self.listbox_offsets = tk.Listbox(self.frame_choix, height=21, width=18, exportselection=False, selectmode=tk.EXTENDED)
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
        self.text_orig.bind("<Key>", lambda e: self.ctrlEvent(e))
        self.text_orig.grid(row=2,column=1)

        self.labels_txt_trad = tk.Label(self.frame_texte, text="Translated text:")
        self.labels_txt_trad.grid(row=3,column=1)

        self.text_trad = tk.Text(self.frame_texte, width=60, height=10, borderwidth=5, highlightbackground="#A8A8A8")
        self.text_trad.grid(row=4,column=1)

        self.frame_buttons = tk.Frame(self.frame_texte, borderwidth=10)

        self.button_save_line = tk.Button(self.frame_buttons, text="Validate", command=self.valider_ligne)
        self.button_save_line.grid(row=1, column=1,padx=2)

        self.button_save_file = tk.Button(self.frame_buttons, text="Save", command=self.enregistrer_fichier)
        self.button_save_file.grid(row=1, column=2,padx=2)

        self.button_translate_file = tk.Button(self.frame_buttons, text="Translate", command=self.translate_game_window)
        self.button_translate_file.grid(row=1, column=3,padx=2)

        self.button_insert_translation = tk.Button(self.frame_buttons, text="Insert", command=self.function_insert_translation)
        self.button_insert_translation.grid(row=1, column=4,padx=2)

        self.button_search_text = tk.Button(self.frame_buttons, text="Search", command=self.search_text_window)
        self.button_search_text.grid(row=1, column=5,padx=2)

        self.frame_buttons.grid(row=5,column=1)

        self.frame_texte.pack(side=tk.LEFT)

        self.frame_edition.grid(row=2, column=1)

        self.open_table()
        self.show_text(None)


    def function_insert_translation(self):

        self.enregistrer_fichier()

        insert_translation("script_text.mrg","table.txt","script_text_translated"+time.strftime('%Y%m%d-%H%M%S')+".mrg")

        self.warning = tk.Toplevel(self.dl_editor)
        self.warning.title("deepLuna")
        self.warning.attributes("-topmost", True)
        self.warning.grab_set()

        self.warning_message = tk.Label(self.warning, text="Text inserted successfully!")
        self.warning_message.grid(row=0,column=0,pady=5)

        self.warning_button = tk.Button(self.warning, text="Close", command = lambda : self.pushed(self.warning))
        self.warning_button.grid(row=1,column=0,pady=10)

    def pushed(self,sub_win):
        sub_win.grab_release()
        sub_win.destroy()

    def open_table(self):
        self.listbox_offsets.delete(0,tk.END)
        self.text_orig.delete("1.0",tk.END)
        self.text_trad.delete("1.0",tk.END)
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
        cs = self.listbox_offsets.curselection()
        if cs == ():
            cs = (0,)
        else:
            for offset in cs:
                self.text_orig.delete("1.0",tk.END)
                self.text_trad.delete("1.0",tk.END)
                self.text_orig.insert("1.0", self.table_file[offset][1])
                self.text_trad.insert("1.0", self.table_file[offset][2])


    def ctrlEvent(self,event):
        if(12==event.state and event.keysym=='c') or (8==event.state and event.keysym=='c') or event.char=='\uf700' or event.char=='\uf701' or event.char=='\uf702' or event.char=='\uf703':
            return
        else:
            return "break"

    def valider_ligne(self):

        global search_window_open
        global posSearch
        global searchResults
        global n_trad

        cs=self.listbox_offsets.curselection()

        self.table_file[cs[0]][2] = self.text_trad.get("1.0", tk.END)
        if self.table_file[cs[0]][2][-1] == "\n":
            self.table_file[cs[0]][2] = self.table_file[cs[0]][2][:-1]
        if self.table_file[cs[0]][2] != "TRANSLATION":
            self.listbox_offsets.itemconfig(cs[0], bg='#BCECC8') #green for translated and inserted
            n_trad = n_trad + 1
            self.prct_trad.delete("1.0",tk.END)
            self.prct_trad.insert("1.0", str(round(n_trad*100/len(self.table_file),1))+"%")
        else:
            self.listbox_offsets.itemconfig(cs[0], bg='#FFFFFF')
            if n_trad > 0:
                n_trad = n_trad - 1
                self.prct_trad.delete("1.0",tk.END)
                self.prct_trad.insert("1.0", str(round(n_trad*100/len(self.table_file),1))+"%")

        if search_window_open and len(searchResults)>0:
            try:
                self.search_text()
            except IndexError:
                posSearch = posSearch-1
                self.search_text()


    def enregistrer_fichier(self):

        global search_window_open
        global posSearch
        global searchResults

        tableFile = open("table.txt","w",encoding="utf-8")
        tableFile.write("\n".join([str(elem) for elem in self.table_file]))
        tableFile.close()

    def search_text_window(self):

        global searchResults
        global search_window_open
        global posSearch

        if not search_window_open:
            search_window_open = True

            self.search_window = tk.Toplevel(self.dl_editor)
            #self.search_window.iconbitmap("AteliELF.ico")
            self.search_window.resizable(height=False, width=False)
            self.search_window.title("deepLuna — Search")
            self.search_window.attributes("-topmost", True)
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

            #self.search_results = tk.Text(self.search_window, width=25, height=1, borderwidth=5, highlightbackground="#A8A8A8")

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

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]
        self.replacement_text = self.replace_field.get("1.0",tk.END)[:-1]

        #posSearch = 0
        #print("posSearch (avant) = "+str(posSearch))

        self.pos_text = self.table_file.index(searchResults[posSearch])

        #print("\n")

        #print(self.pos_text)
        #print(self.txt_to_search in self.table_file[self.pos_text][3])

        if self.txt_to_search in self.table_file[self.pos_text][2]:
            #print(self.table_file[self.pos_text][3])
            self.table_file[self.pos_text][2] = self.table_file[self.pos_text][2].replace(self.txt_to_search,self.replacement_text)
            #print(self.table_file[self.pos_text][3])

        if len(searchResults) == 1:
            self.listbox_offsets.selection_clear(0, tk.END)
            self.listbox_offsets.see(self.pos_text)
            self.listbox_offsets.select_set(self.pos_text)
            self.listbox_offsets.activate(self.pos_text)
            self.text_orig.delete("1.0",tk.END)
            self.text_trad.delete("1.0",tk.END)
            self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
            self.text_trad.insert("1.0", self.table_file[self.pos_text][2])
            posSearch = 0
        #
        # print("posSearch (après) = "+str(posSearch))

        # if posSearch==len(searchResults):
        #     posSearch -= 1
        # if posSearch<0:
        #     posSearch = 0

        self.search_text()

    def all_replace_text(self):

        global searchResults
        global posSearch

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]
        self.replacement_text = self.replace_field.get("1.0",tk.END)[:-1]

        for self.j in range(len(searchResults)):
            self.pos_text = self.table_file.index(searchResults[self.j])

            if self.txt_to_search in self.table_file[self.pos_text][2]:
                #print(self.table_file[self.pos_text][3])
                self.table_file[self.pos_text][2] = self.table_file[self.pos_text][2].replace(self.txt_to_search,self.replacement_text)
                #print(self.table_file[self.pos_text][3])


        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        self.text_orig.delete("1.0",tk.END)
        self.text_trad.delete("1.0",tk.END)
        self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
        self.text_trad.insert("1.0", self.table_file[self.pos_text][2])

        posSearch = 0

        self.search_text()

        #     if self.txt_to_search in self.table_file[self.j][3]:
        #         print(self.table_file[self.pos_text][3])
        #         self.table_file[self.j][3] = self.table_file[self.j][3].replace(self.txt_to_search,self.replacement_text)
        #
        # self.pos_text = self.table_file.index(searchResults[posSearch])
        #
        # self.listbox_offsets.selection_clear(0, tk.END)
        # self.listbox_offsets.see(self.pos_text)
        # self.listbox_offsets.select_set(self.pos_text)
        # self.listbox_offsets.activate(self.pos_text)
        # self.text_orig.delete("1.0",tk.END)
        # self.text_trad.delete("1.0",tk.END)
        # self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
        # self.text_trad.insert("1.0", self.table_file[self.pos_text][3])

        self.search_text()



    def search_text(self):

        global searchResults
        global posSearch

        searchResults = []

        self.txt_to_search = self.search_field.get("1.0",tk.END)[:-1]

        #print(self.txt_to_search)

        for self.k in range(len(self.table_file)):

            # if self.k<10:
            #     print("Eng : ",self.table_file[self.k][1])
            #     print(self.txt_to_search in self.table_file[self.k][1])
            #     print("Fr : ",self.table_file[self.k][3])
            #     print(self.txt_to_search in self.table_file[self.k][3])

            if (self.txt_to_search in self.table_file[self.k][1]) or (self.txt_to_search in self.table_file[self.k][2]):
                #print('True.')
                searchResults.append(self.table_file[self.k])

        #print(searchResults)

        self.result_field.delete("1.0",tk.END)
        self.result_field.insert("1.0", str(len(searchResults))+(" résultat" if len(searchResults) == 1 else " résultats"))

        #print("posSearch = ",posSearch)


        if len(searchResults)>0:
            try:
                self.pos_text = self.table_file.index(searchResults[posSearch])
            except IndexError:
                posSearch -= 1
                self.pos_text = self.table_file.index(searchResults[posSearch])
            self.listbox_offsets.selection_clear(0, tk.END)
            self.listbox_offsets.see(self.pos_text)
            self.listbox_offsets.select_set(self.pos_text)
            self.listbox_offsets.activate(self.pos_text)
            self.text_orig.delete("1.0",tk.END)
            self.text_trad.delete("1.0",tk.END)
            self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
            self.text_trad.insert("1.0", self.table_file[self.pos_text][2])

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

        posSearch = posSearch+1
        #print("posSearch = ",posSearch)
        #print("searchResults[posSearch] = ",searchResults[posSearch])
        self.pos_text = self.table_file.index(searchResults[posSearch])

        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        self.text_orig.delete("1.0",tk.END)
        self.text_trad.delete("1.0",tk.END)
        self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
        self.text_trad.insert("1.0", self.table_file[self.pos_text][2])

        if posSearch == len(searchResults)-1:
            self.next_button.config(state=tk.DISABLED)
            self.prev_button.config(state=tk.NORMAL)
        else:
            self.next_button.config(state=tk.NORMAL)
            self.prev_button.config(state=tk.NORMAL)

    def prev_text(self):

        global searchResults
        global posSearch

        posSearch = posSearch-1
        #print("posSearch = ",posSearch)
        #print("searchResults[posSearch] = ",searchResults[posSearch])
        self.pos_text = self.table_file.index(searchResults[posSearch])

        self.listbox_offsets.selection_clear(0, tk.END)
        self.listbox_offsets.see(self.pos_text)
        self.listbox_offsets.select_set(self.pos_text)
        self.listbox_offsets.activate(self.pos_text)
        self.text_orig.delete("1.0",tk.END)
        self.text_trad.delete("1.0",tk.END)
        self.text_orig.insert("1.0", self.table_file[self.pos_text][1])
        self.text_trad.insert("1.0", self.table_file[self.pos_text][2])

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

        self.test_cs = self.listbox_offsets.curselection()
        if len (self.test_cs)>0:
            cs = self.test_cs
        #cs=self.listbox_offsets.curselection()

        self.translation = tk.Toplevel(self.dl_editor)
        self.translation.title("deepLuna — Translation")
        self.translation.attributes("-topmost", True)
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
        #print(blockTranslation)
        self.var_block_tl.set(blockTranslation)
        #print(self.var_block_tl)

        self.graph_advanced_options = tk.Checkbutton(self.set_translation_frame, variable=self.var_block_tl, onvalue=True, offvalue=False)
        self.graph_advanced_options.grid(row=2,column=1)

        self.message = tk.Label(self.set_translation_frame, text="Translate starting from the offset  "+str(self.table_file[cs[0]][0])+" until "+str(self.table_file[cs[-1]][0])+"?" if len(cs)>1 else "Translate at the offset "+str(self.table_file[cs[0]][0])+"?")
        self.message.grid(row=3,column=0,pady=10)

        self.launch_butten = tk.Button(self.set_translation_frame, text="OK", command = self.translate_game)
        self.launch_butten.grid(row=3,column=1,padx=10,pady=10)

        self.set_translation_frame.grid(row=0,column=0,pady=10)

        self.s = Style()
        self.s.theme_use('clam')
        self.s.configure("blue.Horizontal.TProgressbar", foreground='green', background='green')

        self.progress_translate = Progressbar(self.translation, style="blue.Horizontal.TProgressbar", orient = tk.HORIZONTAL, length = 300, mode = 'determinate')
        #self.progress_extract = Progressbar(project_options, orient = tk.HORIZONTAL, length = 100, mode = 'determinate')
        self.progress_translate.grid(row=1,column=0,padx=20,pady=20)

        self.time_frame = tk.Frame(self.translation, borderwidth=10)

        self.remaining_time_text = tk.Label(self.time_frame, text="Estimated remaining time: ")
        self.remaining_time_text.grid(row=0,column=0,pady=10)

        self.remaining_time = tk.Label(self.time_frame, textvariable=self.expected_time)
        self.remaining_time.grid(row=0,column=1,pady=10)

        self.time_frame.grid(row=2,column=0,pady=10)

        self.translation.protocol("WM_DELETE_WINDOW", self.closing_translation_window)

    def closing_translation_window(self):

        #global search_window_open
        #global searchResults
        #global posSearch

        self.translation.grab_release()
        self.translation.destroy()
        self.dl_editor.grab_set()
        #search_window_open = False
        #searchResults = []
        #posSearch = 0


    def translate_game(self):

        global cs
        global translationApi
        global translationLanguage #'EN' for english/'FR' for french
        global blockTranslation

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
                    #print(translationApi[self.j])
                    #print(translationLanguage)
                    for self.i in range(cs[0],cs[-1]+1):
                        print("\n*** Line n°"+str(self.i+1)+" ***")
                        print("JP: "+str(self.table_file[self.i][1]))
                        try:
                            self.translated_text = requests.post(url='https://api-free.deepl.com/v2/translate', data={'auth_key':translationApi[self.j],'target_lang':translationLanguage,'text':self.table_file[self.i][1] if self.table_file[self.i][3] == 0 else re.sub(r"(\<)|(\|.+?\>)", r"",self.table_file[self.i][1])})
                            self.translated_text = self.translated_text.json()["translations"][0]["text"]
                            #print(self.translated_text)
                        except:
                            # self.error = True
                            # break
                            cs = cs[self.i:]
                            break
                        self.table_file[self.i][2] = self.translated_text
                        print(translationLanguage+": "+self.translated_text)
                        self.progress_translate["value"] = floor((self.i-cs[0])/self.len_translation*1000)
                        self.enregistrer_fichier()
                        self.new_time = datetime.timedelta(seconds=time.time()-self.start)
                        self.accum_lines = self.i-cs[0]+1
                        self.remain_time = (cs[-1]+1-self.i)*self.new_time/self.accum_lines
                        self.expected_time.set(str(self.remain_time).split('.')[0])
                        root.update()

                    if self.i < cs[-1]:
                        self.j += 1
                        self.error = True
                    else:
                        self.finished_var = True
                        self.error = False


                if not self.error:
                    self.enregistrer_fichier()
                    self.translation.destroy()
                    self.open_table()
                    self.listbox_offsets.see(self.i)
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="Text translated successfully!")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

                else:
                    self.enregistrer_fichier()
                    self.translation.destroy()
                    self.open_table()
                    self.listbox_offsets.see(self.i)
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="ERROR: Text couldn\'t be translated. Use another API link or do the translation manually.")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

            else:
                #DeepL block translation
                print("\nAutomatic translation of the game with deepL (block)")
                self.start = time.time()
                while (self.j < self.len_translationApi and not self.finished_var):
                    self.block_text = '\n'.join([re.sub(r"(\<)|(\|.+?\>)", r"", elem[1]) for elem in self.table_file[cs[0]:cs[-1]+1]])
                    try:
                    #print(self.block_text)
                        self.translated_text = requests.post(url='https://api-free.deepl.com/v2/translate', data={'auth_key':translationApi[self.j],'target_lang':translationLanguage,'text':self.block_text})
                        #print(self.translated_text.json())
                        self.translated_text = self.translated_text.json()["translations"][0]["text"]
                        #print(self.translated_text)
                        self.translated_text = self.translated_text.split('\n')
                        for self.k in range(cs[0],cs[-1]+1):
                            self.table_file[self.k][2] = self.translated_text[self.k-cs[0]]
                            print("\n*** Line n°"+str(self.k+1)+" ***")
                            print("JP: "+str(self.table_file[self.k][1]))
                            print(translationLanguage+": "+self.table_file[self.k][2])
                            self.progress_translate["value"] = floor((self.k-cs[0])/self.len_translation*1000)
                            self.enregistrer_fichier()
                            self.new_time = datetime.timedelta(seconds=time.time()-self.start)
                            self.accum_lines = self.k-cs[0]+1
                            self.remain_time = (cs[-1]+1-self.k)*self.new_time/self.accum_lines
                            self.expected_time.set(str(self.remain_time).split('.')[0])
                            root.update()
                            #print(self.translated_text)
                        self.finished_var = True
                        self.error = False
                    except:
                        self.j += 1
                        self.finished_var = False
                        self.error = True

                if not self.error:
                    self.enregistrer_fichier()
                    self.translation.destroy()
                    self.open_table()
                    self.listbox_offsets.see(cs[-1])
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="Text translated successfully!")
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

                else:
                    self.enregistrer_fichier()
                    self.translation.destroy()
                    self.open_table()
                    self.listbox_offsets.see(cs[0])
                    root.update()
                    self.warning = tk.Toplevel(self.dl_editor)
                    self.warning.title("deepLuna")
                    self.warning.attributes("-topmost", True)
                    self.warning.grab_set()

                    self.warning_message = tk.Label(self.warning, text="ERROR: Text translated only partially. Please start again from the offset "+str(self.table_file[self.i][0]))
                    self.warning_message.grid(row=0,column=0,pady=5)

                    self.warning_button = tk.Button(self.warning, text="Back", command = lambda : self.pushed(self.warning))
                    self.warning_button.grid(row=1,column=0,pady=10)

root = tk.Tk()
deepLuna = StartWindow(root)
root.mainloop()