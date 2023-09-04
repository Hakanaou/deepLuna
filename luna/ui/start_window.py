import os
import sys
import traceback
import tkinter as tk

from PIL import Image, ImageTk

from luna.constants import Constants
from luna.translation_db import TranslationDb
from luna.ui.information_window import InformationWindow
from luna.ui.translation_window import TranslationWindow


class StartWindow:

    def __init__(self):
        # Create the root TK window context
        self._root = tk.Tk()

        # Reference to active sub-windows
        self._warning = None
        self._translation_window_root = None

        # Configure UI basics
        self._root.title("Welcome to deepLuna")
        self._root.resizable(height=False, width=False)

        # Load logo
        frame_image = tk.Frame(self._root, borderwidth=5)
        basedir = os.path.join(os.path.dirname(__file__))
        icon = Image.open(os.path.join(basedir,  "../../icone.png")).resize((140, 140))
        self._icon_image = ImageTk.PhotoImage(icon)
        image = tk.Label(frame_image, image=self._icon_image)
        image.image = ImageTk.PhotoImage(icon)
        image.pack()
        frame_image.pack(side=tk.LEFT)

        # Create holder for buttons
        self._frame_buttons = tk.Frame(self._root, borderwidth=5)

        # Extract database from MRGs
        self._new_project_button = tk.Button(
            self._frame_buttons,
            text="Extract text",
            bg="#CFCFCF",
            width=28,
            command=self.btn_extract_database
        )
        self._new_project_button.grid(row=0,column=0,pady=2)

        # Open translation project
        self._open_project_button = tk.Button(
            self._frame_buttons,
            text="Open translation",
            bg="#CFCFCF",
            width=28,
            command=self.btn_open_main_window
        )
        self._open_project_button.grid(row=1,column=0,pady=2)

        # About
        self._about_button = tk.Button(
            self._frame_buttons,
            text="About",
            bg="#CFCFCF",
            width=28,
            command=self.btn_open_about
        )
        self._about_button.grid(row=2,column=0,pady=2)

        self._frame_buttons.pack(side=tk.LEFT)

    def mainloop(self):
        self._root.mainloop()

    def btn_open_main_window(self):
        self._translation_window_root = tk.Toplevel(self._root)
        self._translation_window_root.grab_set()
        try:
            TranslationWindow(self._translation_window_root)
        except Exception as e:
            # Destroy window
            self._translation_window_root.grab_release()
            self._translation_window_root.destroy()

            # Log to console
            sys.stderr.write(traceback.format_exc() + "\n")

            # Create error window
            self._warning = tk.Toplevel(self._root)
            self._warning.title("deepLuna")
            self._warning.resizable(height=False, width=False)
            self._warning.attributes("-topmost", True)
            self._warning.grab_set()

            # Set message
            warning_message = tk.Label(
                self._warning,
                text=f"Failed to open translation:\n{e}\n"
                     f"{traceback.format_exc()}",
                justify=tk.LEFT
            )
            warning_message.grid(row=0, column=0, padx=5, pady=5)

            # Button choices
            warning_button = tk.Button(
                self._warning,
                text="OK",
                command=self.btn_cancel_warning
            )
            warning_button.grid(row=1, column=0, pady=10)

    def btn_open_about(self):
        # Create / display the info window
        info_window_root = tk.Toplevel(self._root)
        info_window_root.grab_set()
        InformationWindow(info_window_root)

    def btn_extract_database(self):
        # If the DB is already extracted, prompt how to proceed
        if os.path.exists(Constants.DATABASE_PATH):
            # Create a new window root
            self._warning = tk.Toplevel(self._root)
            self._warning.title("deepLuna")
            self._warning.resizable(height=False, width=False)
            self._warning.attributes("-topmost", True)
            self._warning.grab_set()

            # Set message
            warning_message = tk.Label(
                self._warning,
                text="Existing database found. Do you wish to overwrite?"
            )
            warning_message.grid(row=0, column=0, pady=5, columnspan=2)

            # Button choices
            warning_button = tk.Button(
                self._warning,
                text="Cancel",
                command=self.btn_cancel_warning
            )
            warning_button.grid(row=1, column=0, pady=10)

            warning_button = tk.Button(
                self._warning,
                text="Overwrite",
                command=self.extract_database
            )
            warning_button.grid(row=1, column=1, pady=10)
            return

        # Attempt to extract the DB
        self.extract_database()

    def btn_cancel_warning(self):
        if self._warning:
            self._warning.grab_release()
            self._warning.destroy()
            self._warning = None

    def extract_database(self):
        # Kill any live prompts
        self.btn_cancel_warning()

        try:
            # Extract the database
            tl_db = TranslationDb.from_mrg(
                Constants.ALLSCR_MRG,
                Constants.SCRIPT_TEXT_MRG
            )

            # Cache it to file
            with open(Constants.DATABASE_PATH, 'wb+') as output:
                output.write(tl_db.as_json().encode('utf-8'))

            # Open the main window
            self.btn_open_main_window()
        except Exception as e:
            # Cancel any live dialogs
            self.btn_cancel_warning()

            # Log to console
            sys.stderr.write(traceback.format_exc() + "\n")

            # Create error window
            self._warning = tk.Toplevel(self._root)
            self._warning.title("deepLuna")
            self._warning.resizable(height=False, width=False)
            self._warning.attributes("-topmost", True)
            self._warning.grab_set()

            # Set message
            warning_message = tk.Label(
                self._warning,
                text=f"Failed to extract database:\n{e}\n"
                     f"{traceback.format_exc()}",
                justify=tk.LEFT
            )
            warning_message.grid(row=0, column=0, padx=5, pady=5)

            # Button choices
            warning_button = tk.Button(
                self._warning,
                text="OK",
                command=self.btn_cancel_warning
            )
            warning_button.grid(row=1, column=0, pady=10)
