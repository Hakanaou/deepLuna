import webbrowser
import tkinter as tk


class InformationWindow:

    def __init__(self, root):
        self._root = root

        self._root.title("deepLuna — About")
        self._root.geometry("400x150")
        self._root.resizable(height=False, width=False)

        # Add about text
        tk.Label(
            self._root,
            text=(
                "deepLuna v3.1.2 — 18/10/2021\n"
                "Developed by Hakanaou and R.Schlaikjer\n"
            ),
            justify=tk.CENTER,
            borderwidth=10
        ).pack()

        self.explanations = tk.Button(
            self._root,
            text="deepLuna GitHub",
            command=self.btn_open_github
        )
        self.explanations.pack()

    @staticmethod
    def btn_open_github():
        webbrowser.open_new("https://github.com/Hakanaou/deepLuna")
