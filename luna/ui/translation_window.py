import os
import contextlib

from functools import cmp_to_key

import tkinter as tk
from tkinter.ttk import (
    Style,
    Treeview,
)

from luna.constants import Constants
from luna.readable_exporter import ReadableExporter
from luna.translation_db import TranslationDb


class TranslationWindow:

    # Constants for TK event masks
    TKSTATE_SHIFT = 0x0001
    TKSTATE_CAPS = 0x0002
    TKSTATE_CTRL = 0x0004
    TKSTATE_L_ALT = 0x0008

    def __init__(self, root):
        # Cache TK root
        self._root = root

        # Reference for warning dialog handles
        self._warning = None

        # Try and load the translation DB from file
        self._translation_db = TranslationDb.from_file(
            Constants.DATABASE_PATH)

        # Configure UI
        self._root.resizable(height=False, width=False)
        self._root.title("deepLuna — Editor")

        # Configure style vars
        self.load_style()

        # Translation percentage UI
        self.init_translation_percent_ui()

        # Container for editing zone
        # Used by scene selector tree, line selector, tl line view
        self.frame_editing = tk.Frame(self._root, borderwidth=1)

        # Scene selector tree
        self.init_scene_selector_tree()

        # Line selector
        self.init_line_selector()

        # Selected line orig/tl/comments
        self.init_tl_line_view()

        # Hook close function to prompt save
        self._root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Init total translated percent field
        self.load_percentage()

    def load_percentage(self):
        percent_translated = self._translation_db.translated_percent()
        self.percent_translated_global.delete("1.0", tk.END)
        self.percent_translated_global.insert(
            "1.0", "%.1f%%" % percent_translated)

    def on_close(self):
        # Prompt to save the DB
        self._warning = tk.Toplevel(self._root)
        self._warning.title("deepLuna")
        self._warning.resizable(height=False, width=False)
        self._warning.attributes("-topmost", True)
        self._warning.grab_set()

        # Warning text
        warning_message = tk.Label(
            self._warning,
            text="WARNING: Do you want to close without saving?"
        )
        warning_message.grid(row=0, column=0, pady=5)

        # Buttons
        self.frame_quit_buttons = tk.Frame(self._warning, borderwidth=2)
        quit_and_save_button = tk.Button(
            self.frame_quit_buttons,
            text="Save and Quit",
            width=15,
            command=self.save_and_quit
        )
        quit_and_save_button.grid(row=0, column=0, padx=5, pady=10)
        quit_button = tk.Button(
            self.frame_quit_buttons,
            text="Quit",
            width=15,
            command=self.quit_editor
        )
        quit_button.grid(row=0, column=1, padx=5, pady=10)
        self.frame_quit_buttons.grid(row=1, column=0, pady=5)

    def save_and_quit(self):
        # Save DB
        with open(Constants.DATABASE_PATH, 'wb+') as output:
            output.write(self._translation_db.as_json().encode('utf-8'))

        # Exit
        self.quit_editor()

    def close_warning(self):
        if self._warning:
            self._warning.grab_release()
            self._warning.destroy()
            self._warning = None

    def quit_editor(self):
        self.close_warning()
        self._root.destroy()

    def init_tl_line_view(self):
        self.text_frame = tk.Frame(self.frame_editing, borderwidth=20)

        # Original JP text field
        self.labels_txt_orig = tk.Label(
            self.text_frame, text="Original text:")
        self.labels_txt_orig.grid(row=1, column=1)
        self.text_orig = tk.Text(
            self.text_frame,
            width=60,
            height=10,
            borderwidth=5,
            highlightbackground="#A8A8A8"
        )
        self.text_orig.config(state=tk.DISABLED)
        self.text_orig.grid(row=2, column=1)

        # Translated text field
        self.labels_txt_trad = tk.Label(
            self.text_frame, text="Translated text:")
        self.labels_txt_trad.grid(row=3, column=1)
        self.text_translated = tk.Text(
            self.text_frame,
            width=60,
            height=10,
            borderwidth=5,
            highlightbackground="#A8A8A8"
        )
        self.text_translated.grid(row=4, column=1)

        # Comments field
        self.labels_txt_comment = tk.Label(
            self.text_frame, text="Comments:")
        self.labels_txt_comment.grid(row=5, column=1)
        self.text_comment = tk.Text(
            self.text_frame,
            width=60,
            height=2,
            borderwidth=5,
            highlightbackground="#A8A8A8"
        )
        self.text_comment.grid(row=6, column=1)

        # Text buttons
        self.frame_buttons = tk.Frame(self.text_frame, borderwidth=10)

        # Update current line
        self.button_save_line = tk.Button(
            self.frame_buttons,
            text="Update Line",
            command=self.save_line
        )
        self.button_save_line.grid(row=1, column=1, padx=2)

        # Save DB
        self.button_save_file = tk.Button(
            self.frame_buttons,
            text="Save DB",
            command=self.save_translation_table
        )
        self.button_save_file.grid(row=1, column=2, padx=2)

        # Translate line using DeepL
        self.button_translate_file = tk.Button(
            self.frame_buttons,
            text="Translate",
            command=self.translate_game_window
        )
        self.button_translate_file.grid(row=1, column=3, padx=2)

        # Pack new script_text mrg
        self.button_insert_translation = tk.Button(
            self.frame_buttons,
            text="Insert",
            command=self.insert_translation
        )
        self.button_insert_translation.grid(row=1, column=4, padx=2)

        # Search window
        self.button_search_text = tk.Button(
            self.frame_buttons,
            text="Search",
            command=self.search_text_window
        )
        self.button_search_text.grid(row=1, column=5, padx=2)

        # Export selected scene
        self.button_export_page = tk.Button(
            self.frame_buttons,
            text="Export scene",
            command=self.export_page
        )
        self.button_export_page.grid(row=1, column=6, padx=2)

        # Export _all_ scenes
        self.button_export_all = tk.Button(
            self.frame_buttons,
            text="Export all",
            command=self.export_all_pages_window
        )
        self.button_export_all.grid(row=1, column=7, padx=2)

        # Pack button region
        self.frame_buttons.grid(row=7, column=1)

        # Toggle options frame
        self.frame_options = tk.Frame(self.text_frame, borderwidth=10)

        # Should the text be charswapped for non-EN languages?
        self.text_swapText = tk.Label(self.frame_options, text="Swap text")
        self.text_swapText.grid(row=0, column=0)

        self.var_swapText = tk.BooleanVar()
        self.var_swapText.set(False)

        self.option_swapText = tk.Checkbutton(
            self.frame_options,
            variable=self.var_swapText,
            onvalue=True,
            offvalue=False
        )
        self.option_swapText.grid(row=0, column=1)

        # Pack all containers
        self.frame_options.grid(row=8, column=1)
        self.text_frame.pack(side=tk.LEFT)
        self.frame_editing.grid(row=2, column=1)

    def save_line(self):
        # Get the selected line indexes
        # (multiple selection possible, but ignored)
        selected_indexes = self.listbox_offsets.curselection()
        if not selected_indexes:
            return

        # Check the active scene is valid
        selected_scene = self.scene_tree.focus()
        if selected_scene not in self._translation_db.scene_names():
            return

        # Get the line info for the selected offset
        scene_lines = self._translation_db.lines_for_scene(selected_scene)
        selected_line = scene_lines[selected_indexes[0]]

        # Extract the new tl/comment
        new_tl = self.text_translated.get("1.0", tk.END).strip("\n")
        new_comment = self.text_comment.get("1.0", tk.END).strip("\n")

        # Write them back to the translation DB
        self._translation_db.set_translation_and_comment_for_hash(
            selected_line.jp_hash,
            new_tl,
            new_comment
        )

    def save_translation_table(self):
        # Write out the translation DB to file
        with open(Constants.DATABASE_PATH, 'wb+') as output:
            output.write(self._translation_db.as_json().encode('utf-8'))

    def translate_game_window(self):
        print("Translate game window")

    def insert_translation(self):
        print("Insert tl")

    def search_text_window(self):
        print("Search text")

    def export_page(self):
        # Check the active scene is valid
        selected_scene = self.scene_tree.focus()
        if selected_scene not in self._translation_db.scene_names():
            return

        # Ensure the export dir exists
        try:
            os.makedirs(Constants.EXPORT_DIRECTORY)
        except FileExistsError:
            pass

        # Export
        output_filename = os.path.join(
            Constants.EXPORT_DIRECTORY, f"{selected_scene}.txt")
        with open(output_filename, "wb+") as output_file:
            output_file.write(
                ReadableExporter.export_text(
                    self._translation_db, selected_scene
                ).encode('utf-8')
            )

    def export_all_pages_window(self):
        # Ensure the export dir exists
        try:
            os.makedirs(Constants.EXPORT_DIRECTORY)
        except FileExistsError:
            pass

        for scene in self._translation_db.scene_names():
            output_filename = os.path.join(
                Constants.EXPORT_DIRECTORY, f"{scene}.txt")
            with open(output_filename, "wb+") as output_file:
                output_file.write(
                    ReadableExporter.export_text(
                        self._translation_db, scene
                    ).encode('utf-8')
                )

    def init_line_selector(self):
        self.line_selector_frame = tk.Frame(self.frame_editing, borderwidth=20)

        # Header label
        self.label_offsets = tk.Label(
            self.line_selector_frame,
            text="Original text offsets:")
        self.label_offsets.pack()

        # Listbox containing list of page: text offset
        self.listbox_offsets = tk.Listbox(
            self.line_selector_frame,
            height=32,
            width=18,
            exportselection=False,
            selectmode=tk.EXTENDED
        )
        self.listbox_offsets.bind('<Button-1>', self.load_translation_line)
        self.listbox_offsets.bind('<Return>', self.load_translation_line)
        self.listbox_offsets.pack(side=tk.LEFT, fill=tk.BOTH)
        self.scrollbar_offsets = tk.Scrollbar(self.line_selector_frame)
        self.scrollbar_offsets.pack(side=tk.RIGHT, fill=tk.BOTH)

        self.listbox_offsets.config(yscrollcommand=self.scrollbar_offsets.set)
        self.scrollbar_offsets.config(command=self.listbox_offsets.yview)

        self.line_selector_frame.pack(side=tk.LEFT)

    @staticmethod
    def compare_scenes(in_a, in_b):
        """
        Compare function for scene names that sorts integer fragments properly.
        """
        def decimal_extract(val):
            ret = []
            is_chr = True
            acc = ""
            for c in val:
                if '0' <= c and c <= '9':
                    # If there was a character acc, append it
                    if is_chr and acc:
                        ret.append(acc)
                        acc = ""

                    # Now in non-char acc mode
                    is_chr = False
                    acc += c
                else:
                    # If there was a non-char acc, apend it
                    if not is_chr and acc:
                        ret.append(int(acc))
                        acc = ""

                    # Now in char mode
                    is_chr = True
                    acc += c

            # Handle trailing acc value
            if acc:
                ret.append(acc if is_chr else int(acc))

            return ret

        scene_a = decimal_extract(in_a)
        scene_b = decimal_extract(in_b)

        i = 0
        for i in range(max(len(scene_a), len(scene_b))):
            # Longer is greater
            if i >= len(scene_a):
                return -1
            if i >= len(scene_b):
                return 1

            # If the types match, direct compare
            val_a = scene_a[i]
            val_b = scene_b[i]
            if type(val_a) is type(val_b):
                if val_a < val_b:
                    return -1
                if val_a > val_b:
                    return 1
            else:
                # If the types don't match, compare on the lex order of
                # type names
                type_a_name = str(type(val_a))
                type_b_name = str(type(val_b))
                if type_a_name < type_b_name:
                    return -1
                if type_a_name > type_b_name:
                    return 1

        # If we get all the way here, they are equal
        return 0

    def init_scene_selector_tree(self):
        self.frame_tree = tk.Frame(self.frame_editing, borderwidth=20)
        self.scene_tree = Treeview(
            self.frame_tree,
            height=21,
            style="smallFont.Treeview"
        )
        self.scene_tree.column('#0', anchor='w', width=320)
        self.scene_tree.heading('#0', text='Game text', anchor='center')

        # Add all of the scene names to the treeview
        scene_names = self._translation_db.scene_names()
        ciel_scenes = [name for name in scene_names if '_CIEL' in name]
        arc_scenes = [name for name in scene_names if '_ARC' in name]
        qa_scenes = [name for name in scene_names if 'QA' in name]
        misc_scenes = [
            name for name in scene_names
            if name not in set(ciel_scenes + arc_scenes + qa_scenes)]

        # Create top level categories
        categories = [
            ('Arcueid', 'arc'),
            ('Ciel', 'ciel'),
            ('QA', 'qa'),
            ('Misc', 'misc'),
        ]
        for category_name, category_id in categories:
            self.scene_tree.insert(
                '',
                tk.END,
                text=category_name,
                iid=category_id,
                open=False
            )

        # Helper fun to add arc/ciel scenes, which are by-day
        def insert_day_scene_tree(root, scene_names):
            # Create day holders
            day_names = sorted(list(set([
                v.split('_')[0] for v in scene_names])))
            for day in day_names:
                self.scene_tree.insert(
                    root,
                    tk.END,
                    text=f"Day {day}",
                    iid=f"{root}_{day}",
                    open=False
                )

            # Add arc scenes to appropriate days
            sorted_scenes = sorted(
                scene_names, key=cmp_to_key(self.compare_scenes))
            for scene in sorted_scenes:
                scene_day = scene.split('_')[0]
                self.scene_tree.insert(
                    f"{root}_{scene_day}",
                    tk.END,
                    text=scene,
                    iid=scene,
                    open=False
                )

        insert_day_scene_tree('arc', arc_scenes)
        insert_day_scene_tree('ciel', ciel_scenes)

        # Helper fun to insert the non-day scenes
        def insert_non_day_scene_tree(root, scene_names):
            sorted_scenes = sorted(
                scene_names, key=cmp_to_key(self.compare_scenes))
            for scene in sorted_scenes:
                self.scene_tree.insert(
                    root,
                    tk.END,
                    text=scene,
                    iid=scene,
                    open=False
                )

        insert_non_day_scene_tree('qa', qa_scenes)
        insert_non_day_scene_tree('misc', misc_scenes)

        # Double-click scenes to load
        self.scene_tree.bind('<Double-Button-1>', self.load_scene)

        self.scene_tree.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.frame_tree.pack(side=tk.LEFT)

    def load_scene(self, _event):
        # Get the selected scene id
        scene = self.scene_tree.focus()

        # If this isn't a real scene (e.g. a day header), do nothing
        if scene not in self._translation_db.scene_names():
            return

        # Clear old data from offsets list
        self.listbox_offsets.delete(0, tk.END)

        # Add new entries for each translation offset
        scene_lines = self._translation_db.lines_for_scene(scene)
        idx = 0
        translated_count = 0
        for line in scene_lines:
            modifiers = []
            if line.has_ruby:
                modifiers.append('*')
            if line.is_glued:
                modifiers.append('+')
            if line.is_choice:
                modifiers.append('?')
            self.listbox_offsets.insert(
                idx,
                "%03d: %05d %s" % (
                    line.page_number,
                    line.offset,
                    ''.join(modifiers)
                )
            )
            tl_info = self._translation_db.tl_line_with_hash(line.jp_hash)
            if tl_info.en_text:
                self.listbox_offsets.itemconfig(idx, bg='#BCECC8')
                translated_count += 1
            idx += 1

        # Update current day translated percent
        self.percent_translated_day.delete("1.0", tk.END)
        self.percent_translated_day.insert(
            "1.0",
            str(round(translated_count*100/min(idx, 1), 1))+"%")
        self._name_day.set(scene + ": ")

    def load_translation_line(self, _event):
        # Get the selected line indexes
        # (multiple selection possible, but ignored)
        selected_indexes = self.listbox_offsets.curselection()
        if not selected_indexes:
            return

        # Check the active scene is valid
        selected_scene = self.scene_tree.focus()
        if selected_scene not in self._translation_db.scene_names():
            return

        # Load the relevant line info from the scene
        scene_lines = self._translation_db.lines_for_scene(selected_scene)
        selected_line = scene_lines[selected_indexes[0]]

        # Get the translation data for this JP hash
        tl_info = self._translation_db.tl_line_with_hash(selected_line.jp_hash)

        # Update the text fields
        with self.editable_orig_text():
            self.text_orig.delete("1.0", tk.END)
            self.text_translated.delete("1.0", tk.END)
            self.text_comment.delete("1.0", tk.END)

            self.text_orig.insert("1.0", tl_info.jp_text)
            self.text_translated.insert("1.0", tl_info.en_text or "")
            self.text_comment.insert("1.0", tl_info.comment or "")

    @contextlib.contextmanager
    def editable_orig_text(self):
        self.text_orig.config(state=tk.NORMAL)
        try:
            yield None
        finally:
            self.text_orig.config(state=tk.DISABLED)

    def init_translation_percent_ui(self):
        # Name of currently loaded day
        self._name_day = tk.StringVar()
        self._name_day.set('No day loaded ')

        # UI containers
        self.frame_info = tk.Frame(self._root, borderwidth=20)
        self.frame_local_tl = tk.Frame(self.frame_info, borderwidth=10)
        self.frame_global_tl = tk.Frame(self.frame_info, borderwidth=10)

        # Label showing the translation percentage for the loaded day
        self.label_percent_translated_day = tk.Label(
            self.frame_local_tl,
            textvariable=self._name_day
        )
        self.label_percent_translated_day.grid(row=0, column=0)

        # Counter box with the translation percentage for the loaded day
        self.percent_translated_day = tk.Text(
            self.frame_local_tl,
            width=6,
            height=1,
            borderwidth=5,
            highlightbackground="#A8A8A8"
        )
        self.percent_translated_day.bind("<Key>", self.on_keyevent)
        self.percent_translated_day.grid(row=0, column=1)

        # Pack the local TL percentage area
        self.frame_local_tl.grid(row=0, column=0, padx=10)

        # Global tl stats label
        self.label_percent_translated_global = tk.Label(
            self.frame_global_tl,
            text="Translated text: "
        )
        self.label_percent_translated_global.grid(row=0, column=0)

        # Global tl stats counter
        self.percent_translated_global = tk.Text(
            self.frame_global_tl,
            width=6,
            height=1,
            borderwidth=5,
            highlightbackground="#A8A8A8"
        )
        self.percent_translated_global.bind("<Key>", self.on_keyevent)
        self.percent_translated_global.grid(row=0, column=1)
        self.frame_global_tl.grid(row=0, column=1, padx=10)

        # Pack top info frame
        self.frame_info.grid(row=1, column=1)

    def load_style(self):
        self._style = Style()
        self._style.theme_use('clam')
        self._style.configure(
            "blue.Horizontal.TProgressbar",
            foreground='green',
            background='green'
        )
        self._style.configure(
            "smallFont.Treeview",
            font='TkDefaultFont 11',
            rowheight=24
        )
        self._style.configure(
            "smallFont.Treeview.Heading",
            font='TkDefaultFont 11'
        )

    def on_keyevent(self, event):
        # Ctrl-C exits
        if event.state == self.TKSTATE_CTRL and event.keysym == 'c':
            return None

        # Alt-c exits
        if event.state == self.TKSTATE_L_ALT and event.keysym == 'c':
            return None

        # No clue what these are for, Haka.
        if event.char in ['\uf700', '\uf701', '\uf701', '\uf701']:
            return None

        return "break"
