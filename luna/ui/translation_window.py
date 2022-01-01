from luna.constants import Constants
from luna.translation_db import TranslationDb


class TranslationWindow:

    def __init__(self, root):
        # Cache TK root
        self._root = root

        # Try and load the translation DB from file
        self._translation_db = TranslationDb.from_file(
            Constants.DATABASE_PATH)
