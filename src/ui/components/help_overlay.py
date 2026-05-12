"""Help overlay component for Hackflix."""

from src.qt import QEvent, QObject, Qt, Signal
from src.qt import QKeyEvent
from src.qt import QFrame, QLabel, QTextBrowser, QVBoxLayout, QWidget

from src.ui.styles import (
    BACKGROUND_COLOR,
    FONT_SIZE_BODY,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    scaled,
)

HELP_CONTENT_HTML = """
<h1>Instrukcja obslugi Hackflix</h1>
<p class="lead">Aplikacje obsluguje sie wylacznie klawiatura.</p>

<h2>Poruszanie sie po liscie</h2>
<table>
<tr><th>Klawisz</th><th>Dzialanie</th></tr>
<tr><td>Strzalki gora / dol</td><td>Wybor pozycji na liscie</td></tr>
<tr><td>Tab</td><td>Przelaczenie zakladki <b>Filmy / Seriale</b></td></tr>
<tr><td>Enter</td><td>Wejscie do wybranej pozycji</td></tr>
<tr><td>Esc</td><td>Powrot do poprzedniego widoku</td></tr>
<tr><td>H</td><td>Pokazanie tej pomocy</td></tr>
</table>

<h2>Aktualizacja listy filmow i seriali</h2>
<ol>
<li>Nacisnij klawisz <b>P</b>.</li>
<li>Na dole ekranu pojawi sie <b>Synchronizacja...</b>.</li>
<li>Poczekaj na komunikat <b>Synchronizacja zakonczona</b>.</li>
<li>Lista zostanie odswiezona.</li>
</ol>
<p class="note">Jesli nie ma internetu, w prawym dolnym rogu pojawi sie napis
<b>Rozlaczono</b>.</p>

<h2>Pobieranie filmu</h2>
<ol>
<li>Strzalkami wybierz film.</li>
<li>Nacisnij <b>Enter</b>, aby rozpoczac pobieranie.</li>
<li>Pasek postepu pokaze ile zostalo do pobrania.</li>
<li>Po zakonczeniu pobierania pozycja zmieni status na gotowa do ogladania.</li>
</ol>
<p class="note">Pobieranie dziala w tle, wiec mozna przegladac liste albo ogladac
inny film.</p>

<h2>Pobieranie odcinka serialu</h2>
<ol>
<li>Wybierz serial i nacisnij <b>Enter</b>.</li>
<li>Wybierz sezon i nacisnij <b>Enter</b>.</li>
<li>Wybierz odcinek i nacisnij <b>Enter</b>, aby rozpoczac pobieranie.</li>
<li>Nacisnij <b>Esc</b>, aby cofnac sie do listy sezonow lub seriali.</li>
</ol>

<h2>Ogladanie</h2>
<ol>
<li>Strzalkami wybierz pobrany film lub odcinek.</li>
<li>Nacisnij <b>Enter</b>, aby uruchomic odtwarzacz na caly ekran.</li>
</ol>

<h3>Sterowanie odtwarzaczem</h3>
<table>
<tr><th>Klawisz</th><th>Dzialanie</th></tr>
<tr><td>Spacja</td><td>Pauza / wznowienie</td></tr>
<tr><td>Strzalka w prawo</td><td>Przewin do przodu</td></tr>
<tr><td>Strzalka w lewo</td><td>Przewin do tylu</td></tr>
<tr><td>Strzalka w gore</td><td>Glosniej</td></tr>
<tr><td>Strzalka w dol</td><td>Ciszej</td></tr>
<tr><td>M</td><td>Wycisz / wlacz dzwiek</td></tr>
<tr><td>L</td><td>Przelacz sciezke dzwiekowa</td></tr>
<tr><td>Esc</td><td>Zakoncz ogladanie i wroc do listy</td></tr>
</table>

<h2>Szukanie filmu na liscie</h2>
<ol>
<li>Nacisnij klawisz <b>S</b>.</li>
<li>Wpisz fragment tytulu.</li>
<li>Nacisnij <b>Enter</b>, aby zawezic liste.</li>
<li>Nacisnij <b>X</b>, aby wyczyscic filtr i znow widziec wszystko.</li>
</ol>
<p class="note">Klawisz <b>Esc</b> zamyka okno wyszukiwania bez zmiany listy.</p>

<h2>Usuwanie pozycji</h2>
<ol>
<li>Strzalkami wybierz pozycje do usuniecia.</li>
<li>Nacisnij <b>D</b>.</li>
<li>Potwierdz <b>Enter</b> albo anuluj <b>Esc</b>.</li>
</ol>

<h2>Zamkniecie aplikacji</h2>
<p>Nacisnij <b>Ctrl + Q</b>.</p>

<h2>Komunikaty na dole ekranu</h2>
<ul>
<li><b>Polaczono / Rozlaczono</b> - stan polaczenia z internetem.</li>
<li><b>Synchronizacja...</b> - trwa pobieranie listy.</li>
<li><b>Ostatnia synchronizacja</b> - godzina ostatniej aktualizacji.</li>
<li><b>Blad synchronizacji</b> - nie udalo sie pobrac listy.</li>
</ul>
<p>Krotkie komunikaty w rogu ekranu informuja o postepie pobierania, bledach
lub zakonczonych operacjach. Nie wymagaja reakcji.</p>
"""


class HelpOverlay(QFrame):
    """Modal help overlay displaying keyboard instructions."""

    help_closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the help overlay."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the help overlay layout and styling."""
        self.setObjectName("HelpOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setStyleSheet(f"""
            QFrame#HelpOverlay {{
                background-color: {SURFACE_COLOR};
                border: 1px solid {SECONDARY_COLOR};
                border-radius: 8px;
            }}
            QFrame#HelpOverlay QLabel {{
                background-color: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(scaled(28), scaled(24), scaled(28), scaled(20))
        layout.setSpacing(scaled(14))

        self._title_label = QLabel(self.tr("Help"))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_LARGE}px;
            font-weight: bold;
            color: {TEXT_PRIMARY};
        """)
        layout.addWidget(self._title_label)

        self._content_browser = QTextBrowser()
        self._content_browser.setObjectName("HelpContent")
        self._content_browser.setOpenExternalLinks(False)
        self._content_browser.setHtml(self._styled_help_html())
        self._content_browser.installEventFilter(self)
        self._content_browser.setStyleSheet(f"""
            QTextBrowser#HelpContent {{
                background-color: {BACKGROUND_COLOR};
                border: 1px solid {SECONDARY_COLOR};
                border-radius: 4px;
                padding: {scaled(14)}px;
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY}px;
            }}
        """)
        layout.addWidget(self._content_browser)

        self._hint_label = QLabel(self.tr("Press Esc to close"))
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_SMALL}px;
            color: {TEXT_SECONDARY};
        """)
        layout.addWidget(self._hint_label)

        self.hide()

    def _styled_help_html(self) -> str:
        """Return the embedded help content with local visual styles."""
        return f"""
        <style>
            body {{
                color: {TEXT_PRIMARY};
                font-family: Segoe UI, Roboto, Ubuntu, sans-serif;
                font-size: {FONT_SIZE_BODY}px;
                line-height: 1.45;
            }}
            h1 {{
                color: {PRIMARY_COLOR};
                font-size: {scaled(30)}px;
                margin: 0 0 {scaled(10)}px 0;
            }}
            h2 {{
                color: {TEXT_PRIMARY};
                font-size: {scaled(24)}px;
                margin: {scaled(24)}px 0 {scaled(8)}px 0;
            }}
            h3 {{
                color: {TEXT_PRIMARY};
                font-size: {scaled(21)}px;
                margin: {scaled(18)}px 0 {scaled(8)}px 0;
            }}
            p, li {{
                margin-bottom: {scaled(8)}px;
            }}
            .lead {{
                color: {TEXT_SECONDARY};
                font-size: {scaled(21)}px;
            }}
            .note {{
                color: {TEXT_SECONDARY};
                border-left: {scaled(4)}px solid {PRIMARY_COLOR};
                padding-left: {scaled(12)}px;
            }}
            table {{
                border-collapse: collapse;
                margin: {scaled(8)}px 0 {scaled(16)}px 0;
                width: 100%;
            }}
            th {{
                color: {TEXT_PRIMARY};
                background-color: {SECONDARY_COLOR};
                padding: {scaled(8)}px;
                text-align: left;
            }}
            td {{
                border-bottom: 1px solid {SECONDARY_COLOR};
                padding: {scaled(8)}px;
            }}
            b {{
                color: {PRIMARY_COLOR};
                font-weight: 700;
            }}
        </style>
        {HELP_CONTENT_HTML}
        """

    def eventFilter(
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:  # type: ignore[invalid-method-override]
        """Close help when Escape is pressed inside the content browser."""
        if watched == self._content_browser and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._close_help()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[invalid-method-override]
        """Close help on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self._close_help()
            event.accept()
            return
        super().keyPressEvent(event)

    def _close_help(self) -> None:
        """Emit close signal and hide this overlay."""
        self.help_closed.emit()
        self.hide()

    def show_help(self) -> None:
        """Show and position the help overlay."""
        scroll_bar = self._content_browser.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.setValue(0)
        self.show()
        self._content_browser.setFocus()
        self._center_in_parent()

    def _center_in_parent(self) -> None:
        """Center and size the overlay within its parent widget."""
        parent = self.parent()
        if not isinstance(parent, QWidget):
            return

        parent_rect = parent.rect()
        width = min(scaled(820), max(scaled(560), parent_rect.width() - scaled(96)))
        height = min(scaled(720), max(scaled(420), parent_rect.height() - scaled(96)))
        self.setFixedSize(width, height)
        x = (parent_rect.width() - self.width()) // 2
        y = (parent_rect.height() - self.height()) // 2
        self.move(x, y)
