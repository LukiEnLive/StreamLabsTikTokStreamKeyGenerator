import glob
import os
import platform
import re
import sys
import json
import threading
import traceback
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QFrame,
)
from PySide6.QtCore import (
    Signal,
    QTimer,
    Qt,
    QEvent,
    QPoint,
)
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
)
from Stream import Stream
from TokenRetriever import TokenRetriever
from Updater import VersionChecker
from packaging import version
from _version import __version__


class StreamApp(QMainWindow):
    update_ui = Signal()
    _token_ready = Signal(str)
    _token_error = Signal(str)
    _restore_local_btn = Signal()
    _restore_online_btn = Signal()
    _stream_start_ready = Signal(str, str)
    _stream_start_error = Signal(str)
    _stream_end_ready = Signal(bool)
    _stream_end_error = Signal(str)
    _game_search_ready = Signal(list, str)
    _game_search_error = Signal(str)
    _game_mask_ready = Signal(str, str)
    _account_refresh_ready = Signal(dict)
    _account_refresh_error = Signal(str)

    def __init__(self):
        super().__init__()
        self.stream = None
        self.game_mask_id = ""

        self._game_searching = False
        self._ignore_next_game_search = False
        self._game_categories = {}

        self.dark_mode = True

        self.init_ui()
        self.apply_styles()

        self._game_search_timer = QTimer(self)
        self._game_search_timer.setSingleShot(True)
        self._game_search_timer.setInterval(300)
        self._game_search_timer.timeout.connect(self._start_game_search)

        self.update_ui.connect(self.handle_ui_update)
        self._token_ready.connect(self._apply_token)
        self._token_error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self._restore_local_btn.connect(self._do_restore_local_btn)
        self._restore_online_btn.connect(self._do_restore_online_btn)
        self._stream_start_ready.connect(self._handle_stream_started)
        self._stream_start_error.connect(self._handle_stream_start_error)
        self._stream_end_ready.connect(self._handle_stream_ended)
        self._stream_end_error.connect(self._handle_stream_end_error)
        self._game_search_ready.connect(self._handle_game_search_results)
        self._game_search_error.connect(self._handle_game_search_error)
        self._game_mask_ready.connect(self._handle_game_mask_ready)
        self._account_refresh_ready.connect(self._handle_account_refresh)
        self._account_refresh_error.connect(self._handle_account_refresh_error)

        self.load_config()

        icon_path = Path(__file__).resolve().parent / "assets" / "LukiEnLive.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        QTimer.singleShot(3000, self.check_updates_on_startup)

    def init_ui(self):
        self.setWindowTitle("LukiEnLive - StreamLabs TikTok Stream Key Generator")
        self.setMinimumSize(650, 570)
        self.resize(700, 600)
        main_widget = QWidget()
        main_widget.setObjectName("MainWidget")
        self.setCentralWidget(main_widget)
        self.main_widget = main_widget
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(7)
        main_widget.setLayout(main_layout)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(10)
        icon_path = Path(__file__).resolve().parent / "assets" / "LukiEnLive.ico"
        if icon_path.exists():
            logo_label = QLabel()
            logo_label.setPixmap(QIcon(str(icon_path)).pixmap(52, 52))
            logo_label.setFixedSize(52, 52)
            header_layout.addWidget(logo_label)
        # Brand
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(1)
        brand_label = QLabel("LukiEnLive")
        brand_label.setObjectName("BrandLabel")
        subtitle_label = QLabel("TikTok LIVE • Streamlabs")
        subtitle_label.setObjectName("SubtitleLabel")
        header_text_layout.addWidget(brand_label)
        header_text_layout.addWidget(subtitle_label)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        # Version + update button
        version_layout = QHBoxLayout()
        version_layout.setSpacing(8)
        self.update_btn = QPushButton("Check for Updates")
        self.update_btn.setFixedHeight(30)
        self.update_btn.clicked.connect(self.check_for_updates)
        version_layout.addWidget(self.update_btn)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignVCenter)
        version_layout.addWidget(version_label)
        self.version_label = version_label
        # Theme button
        self.theme_btn = QPushButton("☀  Light mode")
        self.theme_btn.setFixedHeight(30)
        self.theme_btn.clicked.connect(self.toggle_theme)
        version_layout.addWidget(self.theme_btn)
        header_layout.addLayout(version_layout)
        main_layout.addLayout(header_layout)

        self.stream_status_bar = QFrame()
        self.stream_status_bar.setObjectName("StreamStatusBar")
        self.stream_status_bar.setFixedHeight(32)
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.addStretch()
        self.stream_status = QLabel()
        self.stream_status.setAlignment(Qt.AlignCenter)
        self.stream_status.setText(
            'STREAM STATUS  <span class="status-neutral">● NOT LIVE</span>'
        )
        status_layout.addWidget(self.stream_status)
        status_layout.addStretch()
        self.stream_status_bar.setLayout(status_layout)
        main_layout.addWidget(self.stream_status_bar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)
        main_layout.addLayout(content_layout)

        left_column = QVBoxLayout()
        left_column.setSpacing(7)
        content_layout.addLayout(left_column, 1)

        token_group = QGroupBox("Token Loader")
        token_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left_column.addWidget(token_group)
        token_layout = QVBoxLayout()
        token_layout.setContentsMargins(8, 11, 8, 8)
        token_layout.setSpacing(5)
        token_group.setLayout(token_layout)
        # Token input
        token_entry_row = QHBoxLayout()
        token_entry_row.setSpacing(5)
        self.token_entry = QLineEdit()
        self.token_entry.setPlaceholderText("Paste token here or load below...")
        self.token_entry.setEchoMode(QLineEdit.Password)
        self.token_entry.setFixedHeight(30)
        self.token_entry.textChanged.connect(self.handle_token_change)
        self.token_entry.returnPressed.connect(self.refresh_account_info)
        token_entry_row.addWidget(self.token_entry)
        # Eye button
        self.toggle_token_btn = QPushButton("👁")
        self.toggle_token_btn.setFixedSize(38, 32)
        self.toggle_token_btn.setToolTip("Show token")
        self.toggle_token_btn.clicked.connect(self.toggle_token_visibility)
        token_entry_row.addWidget(self.toggle_token_btn)
        token_layout.addLayout(token_entry_row)
        # Load buttons
        load_buttons_row = QHBoxLayout()
        load_buttons_row.setSpacing(5)
        self.load_local_btn = QPushButton("Load from PC")
        self.load_local_btn.setFixedHeight(30)
        self.load_local_btn.setToolTip("Load token from Streamlabs desktop app data")
        self.load_local_btn.clicked.connect(self.load_local_token)
        load_buttons_row.addWidget(self.load_local_btn)
        self.load_online_btn = QPushButton("Load from Web")
        self.load_online_btn.setFixedHeight(30)
        self.load_online_btn.setToolTip("Get token through browser login")
        self.load_online_btn.clicked.connect(self.fetch_online_token)
        load_buttons_row.addWidget(self.load_online_btn)
        token_layout.addLayout(load_buttons_row)
        # Linux Chrome path
        if platform.system() == "Linux":
            binary_row = QHBoxLayout()
            binary_row.setSpacing(5)
            self.binary_location_entry = QLineEdit()
            self.binary_location_entry.setPlaceholderText(
                "Custom Chrome binary path (optional)"
            )
            self.binary_location_entry.setFixedHeight(28)
            binary_row.addWidget(self.binary_location_entry)
            token_layout.addLayout(binary_row)

        account_info_label = QLabel("Account Information")
        account_info_label.setObjectName("SectionLabel")
        token_layout.addWidget(account_info_label)
        account_grid = QGridLayout()
        account_grid.setHorizontalSpacing(18)
        account_grid.setVerticalSpacing(3)

        # Username
        username_label = QLabel("Username:")
        username_label.setAlignment(Qt.AlignLeft)
        self.tiktok_username = QLabel("-")
        self.tiktok_username.setObjectName("AccountValue")
        self.tiktok_username.setAlignment(Qt.AlignLeft)

        # Status
        status_label = QLabel("Status:")
        self.app_status = QLabel("-")
        self.app_status.setObjectName("AccountValue")
        self.app_status.setAlignment(Qt.AlignLeft)

        # Can Go Live
        live_label = QLabel("Can Go Live:")
        self.can_go_live = QLabel("-")
        self.can_go_live.setObjectName("AccountValue")
        self.can_go_live.setAlignment(Qt.AlignLeft)

        account_grid.addWidget(username_label, 0, 0)
        account_grid.addWidget(self.tiktok_username, 0, 1)

        account_grid.addWidget(status_label, 1, 0)
        account_grid.addWidget(self.app_status, 1, 1)

        account_grid.addWidget(live_label, 2, 0)
        account_grid.addWidget(self.can_go_live, 2, 1)

        # Keep labels together on the left and values clearly on the right.
        account_grid.setColumnMinimumWidth(0, 75)
        account_grid.setColumnStretch(0, 0)
        account_grid.setColumnStretch(1, 1)

        token_layout.addLayout(account_grid)
        # Refresh
        self.refresh_btn = QPushButton("Refresh Account Info")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self.refresh_account_info)
        token_layout.addWidget(self.refresh_btn)

        stream_group = QGroupBox("Stream Details")
        stream_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left_column.addWidget(stream_group)
        stream_layout = QVBoxLayout()
        stream_layout.setContentsMargins(8, 8, 8, 8)
        stream_layout.setSpacing(4)
        stream_group.setLayout(stream_layout)
        # Stream title
        title_label = QLabel("Stream Title:")
        title_label.setObjectName("FieldLabel")
        stream_layout.addWidget(title_label)
        self.stream_title = QLineEdit()
        self.stream_title.setFixedHeight(30)
        stream_layout.addWidget(self.stream_title)
        # Game category
        game_label = QLabel("Game Category:")
        game_label.setObjectName("FieldLabel")
        stream_layout.addWidget(game_label)
        self.game_category = QLineEdit()
        self.game_category.setFixedHeight(30)
        self.game_category.setPlaceholderText("Search a game or category...")
        self.game_category.textChanged.connect(self.handle_game_search)
        self.game_category.installEventFilter(self)
        stream_layout.addWidget(self.game_category)

        self.suggestions_list = QListWidget(self.main_widget)
        self.suggestions_list.hide()
        self.suggestions_list.setFixedHeight(130)
        self.suggestions_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.suggestions_list.itemClicked.connect(self.handle_suggestion_selected)
        self.suggestions_list.setObjectName("SuggestionsList")
        # Mature checkbox
        self.mature_checkbox = QCheckBox("Enable mature content")
        stream_layout.addWidget(self.mature_checkbox)

        control_group = QGroupBox("Stream Control")
        control_group.setMinimumWidth(300)
        control_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        content_layout.addWidget(control_group, 1)
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(8, 11, 8, 8)
        control_layout.setSpacing(6)
        control_group.setLayout(control_layout)
        # Go Live / End Live
        button_row = QHBoxLayout()
        button_row.setSpacing(5)
        self.go_live_btn = QPushButton("Go Live")
        self.go_live_btn.setObjectName("GoLiveButton")
        self.go_live_btn.setEnabled(False)
        self.go_live_btn.setFixedHeight(32)
        self.go_live_btn.clicked.connect(self.start_stream)
        button_row.addWidget(self.go_live_btn)
        self.end_live_btn = QPushButton("End Live")
        self.end_live_btn.setObjectName("EndLiveButton")
        self.end_live_btn.setEnabled(False)
        self.end_live_btn.setFixedHeight(32)
        self.end_live_btn.clicked.connect(self.end_stream)
        button_row.addWidget(self.end_live_btn)
        control_layout.addLayout(button_row)
        # Stream URL
        url_label = QLabel("Stream URL:")
        url_label.setObjectName("FieldLabel")
        control_layout.addWidget(url_label)
        self.stream_url = QLineEdit()
        self.stream_url.setReadOnly(True)
        self.stream_url.setFixedHeight(30)
        control_layout.addWidget(self.stream_url)
        self.copy_url_btn = QPushButton("Copy URL")
        self.copy_url_btn.setFixedHeight(28)
        self.copy_url_btn.clicked.connect(
            lambda: self.copy_to_clipboard(
                self.stream_url, self.copy_url_btn, "Copy URL"
            )
        )
        control_layout.addWidget(self.copy_url_btn)
        # Stream key
        key_label = QLabel("Stream Key:")
        key_label.setObjectName("FieldLabel")
        control_layout.addWidget(key_label)
        key_entry_row = QHBoxLayout()
        key_entry_row.setSpacing(5)
        self.stream_key = QLineEdit()
        self.stream_key.setReadOnly(True)
        self.stream_key.setEchoMode(QLineEdit.Password)
        self.stream_key.setFixedHeight(30)
        key_entry_row.addWidget(self.stream_key)
        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setFixedSize(38, 32)
        self.toggle_key_btn.setToolTip("Show stream key")
        self.toggle_key_btn.clicked.connect(self.toggle_key_visibility)
        key_entry_row.addWidget(self.toggle_key_btn)
        control_layout.addLayout(key_entry_row)
        self.copy_key_btn = QPushButton("Copy Key")
        self.copy_key_btn.setFixedHeight(28)
        self.copy_key_btn.clicked.connect(
            lambda: self.copy_to_clipboard(
                self.stream_key, self.copy_key_btn, "Copy Key"
            )
        )
        control_layout.addWidget(self.copy_key_btn)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.setSpacing(7)
        main_layout.addLayout(bottom_buttons)
        self.save_btn = QPushButton("Save Config")
        self.save_btn.setFixedHeight(30)
        self.save_btn.clicked.connect(self._on_save_config_clicked)
        bottom_buttons.addWidget(self.save_btn)
        self.help_btn = QPushButton("Help")
        self.help_btn.setFixedHeight(30)
        self.help_btn.clicked.connect(self.show_help)
        bottom_buttons.addWidget(self.help_btn)
        self.monitor_btn = QPushButton("Open Live Monitor")
        self.monitor_btn.setFixedHeight(30)
        self.monitor_btn.clicked.connect(self.open_live_monitor)
        bottom_buttons.addWidget(self.monitor_btn)

        self.notification_label = QLabel(self.main_widget)
        self.notification_label.setObjectName("NotificationLabel")
        self.notification_label.setAlignment(Qt.AlignCenter)
        self.notification_label.setFixedHeight(32)
        self.notification_label.setMinimumWidth(320)
        self.notification_label.hide()
        self.notification_label.raise_()

    def apply_styles(self):
        if self.dark_mode:
            self.setStyleSheet("""

                QMainWindow {
                    background-color: #151515;
                }

                QWidget {
                    font-size: 11px;
                    color: #E8E8E8;
                }

                QLabel {
                    color: #E8E8E8;
                }

                QGroupBox {
                    background-color: #191919;
                    border: 1px solid #3A3A3A;
                    border-radius: 7px;
                    margin-top: 10px;
                    padding: 11px 8px 8px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 6px;
                    color: #F0F0F0;
                    background-color: #151515;
                }

                QLineEdit {
                    background-color: #222222;
                    border: 1px solid #444444;
                    border-radius: 5px;
                    padding: 4px 8px;
                    color: #F2F2F2;
                    selection-background-color: #555555;
                }

                QLineEdit:hover {
                    border-color: #555555;
                }

                QLineEdit:focus {
                    border-color: #777777;
                }

                QLineEdit:disabled {
                    background-color: #1A1A1A;
                    color: #666666;
                    border-color: #2D2D2D;
                }

                QPushButton {
                    background-color: #292929;
                    border: 1px solid #454545;
                    border-radius: 5px;
                    padding: 5px 10px;
                    color: #F0F0F0;
                    font-size: 11px;
                }

                QPushButton:hover {
                    background-color: #333333;
                    border-color: #5A5A5A;
                }

                QPushButton:pressed {
                    background-color: #202020;
                }

                QPushButton:disabled {
                    background-color: #1C1C1C;
                    border-color: #2B2B2B;
                    color: #666666;
                }

                QPushButton#GoLiveButton {
                    background-color: #245C35;
                    border: 1px solid #347A49;
                    font-weight: bold;
                }

                QPushButton#GoLiveButton:hover {
                    background-color: #2D7142;
                }

                QPushButton#GoLiveButton:disabled {
                    background-color: #202020;
                    border-color: #303030;
                    color: #666666;
                }

                QPushButton#EndLiveButton {
                    background-color: #722B2B;
                    border: 1px solid #963737;
                    font-weight: bold;
                }

                QPushButton#EndLiveButton:hover {
                    background-color: #873333;
                }

                QPushButton#EndLiveButton:disabled {
                    background-color: #1C1C1C;
                    border-color: #2B2B2B;
                    color: #666666;
                    font-weight: normal;
                }

                QCheckBox {
                    color: #DCDCDC;
                    spacing: 7px;
                }

                QCheckBox:hover {
                    color: #FFFFFF;
                }

                QListWidget#SuggestionsList {
                    background-color: #222222;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    color: #EEEEEE;
                    outline: none;
                }

                QListWidget#SuggestionsList::item {
                    padding: 6px 8px;
                    min-height: 22px;
                }

                QListWidget#SuggestionsList::item:hover {
                    background-color: #303030;
                }

                QListWidget#SuggestionsList::item:selected {
                    background-color: #3A3A3A;
                    color: #FFFFFF;
                }

                QScrollBar:vertical {
                    background: #191919;
                    width: 10px;
                    margin: 0px;
                }

                QScrollBar::handle:vertical {
                    background: #444444;
                    border-radius: 5px;
                    min-height: 20px;
                }

                QScrollBar::handle:vertical:hover {
                    background: #555555;
                }

                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }

                QLabel#BrandLabel {
                    font-size: 21px;
                    font-weight: bold;
                    color: #FFFFFF;
                }

                QLabel#SubtitleLabel {
                    font-size: 11px;
                    color: #9E9E9E;
                }

                QLabel#VersionLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #D0D0D0;
                }

                QLabel#SectionLabel {
                    font-weight: bold;
                    color: #F0F0F0;
                    margin-top: 4px;
                }

                QLabel#FieldLabel {
                    font-weight: bold;
                    color: #F0F0F0;
                    margin-top: 3px;
                }

                QLabel#AccountValue {
                    font-weight: bold;
                    color: #F0F0F0;
                }

                QFrame#StreamStatusBar {
                    background-color: #191919;
                    border: 1px solid #3A3A3A;
                    border-radius: 6px;
                }

                QLabel#NotificationLabel {
                    background-color: #1B3A24;
                    border: 1px solid #2E7D46;
                    border-radius: 5px;
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 4px 12px;
                }

            """)
        else:
            self.setStyleSheet("""

                QMainWindow {
                    background-color: #F2F2F2;
                }

                QWidget {
                    font-size: 11px;
                    color: #202020;
                }

                QLabel {
                    color: #202020;
                }

                QGroupBox {
                    background-color: #FAFAFA;
                    border: 1px solid #C8C8C8;
                    border-radius: 7px;
                    margin-top: 10px;
                    padding: 11px 8px 8px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 6px;
                    color: #202020;
                    background-color: #F2F2F2;
                }

                QLineEdit {
                    background-color: #FFFFFF;
                    border: 1px solid #BDBDBD;
                    border-radius: 5px;
                    padding: 4px 8px;
                    color: #202020;
                    selection-background-color: #D0D0D0;
                }

                QLineEdit:hover {
                    border-color: #999999;
                }

                QLineEdit:focus {
                    border-color: #777777;
                }

                QLineEdit:disabled {
                    background-color: #EAEAEA;
                    color: #888888;
                    border-color: #D0D0D0;
                }

                QPushButton {
                    background-color: #E8E8E8;
                    border: 1px solid #C5C5C5;
                    border-radius: 5px;
                    padding: 5px 10px;
                    color: #202020;
                    font-size: 11px;
                }

                QPushButton:hover {
                    background-color: #DDDDDD;
                    border-color: #AAAAAA;
                }

                QPushButton:pressed {
                    background-color: #D2D2D2;
                }

                QPushButton:disabled {
                    background-color: #EEEEEE;
                    border-color: #DDDDDD;
                    color: #999999;
                }

                QPushButton#GoLiveButton {
                    background-color: #2B8749;
                    border: 1px solid #369C55;
                    color: #FFFFFF;
                    font-weight: bold;
                }

                QPushButton#GoLiveButton:hover {
                    background-color: #329C53;
                }

                QPushButton#GoLiveButton:disabled {
                    background-color: #E8E8E8;
                    border-color: #D0D0D0;
                    color: #999999;
                }

                QPushButton#EndLiveButton {
                    background-color: #963434;
                    border: 1px solid #AC4040;
                    color: #FFFFFF;
                    font-weight: bold;
                }

                QPushButton#EndLiveButton:hover {
                    background-color: #A83B3B;
                }

                QPushButton#EndLiveButton:disabled {
                    background-color: #EEEEEE;
                    border-color: #DDDDDD;
                    color: #999999;
                    font-weight: normal;
                }

                QCheckBox {
                    color: #202020;
                    spacing: 7px;
                }

                QCheckBox:hover {
                    color: #000000;
                }

                QListWidget#SuggestionsList {
                    background-color: #FFFFFF;
                    border: 1px solid #AAAAAA;
                    border-radius: 5px;
                    color: #202020;
                    outline: none;
                }

                QListWidget#SuggestionsList::item {
                    padding: 6px 8px;
                    min-height: 22px;
                }

                QListWidget#SuggestionsList::item:hover {
                    background-color: #E5E5E5;
                }

                QListWidget#SuggestionsList::item:selected {
                    background-color: #D5D5D5;
                    color: #000000;
                }

                QScrollBar:vertical {
                    background: #EEEEEE;
                    width: 10px;
                    margin: 0px;
                }

                QScrollBar::handle:vertical {
                    background: #BBBBBB;
                    border-radius: 5px;
                    min-height: 20px;
                }

                QScrollBar::handle:vertical:hover {
                    background: #999999;
                }

                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }

                QLabel#BrandLabel {
                    font-size: 21px;
                    font-weight: bold;
                    color: #111111;
                }

                QLabel#SubtitleLabel {
                    font-size: 11px;
                    color: #777777;
                }

                QLabel#VersionLabel {
                    font-size: 13px;
                    font-weight: bold;
                    color: #444444;
                }

                QLabel#SectionLabel {
                    font-weight: bold;
                    color: #202020;
                    margin-top: 4px;
                }

                QLabel#FieldLabel {
                    font-weight: bold;
                    color: #202020;
                    margin-top: 3px;
                }

                QLabel#AccountValue {
                    font-weight: bold;
                    color: #202020;
                }

                QFrame#StreamStatusBar {
                    background-color: #FAFAFA;
                    border: 1px solid #C8C8C8;
                    border-radius: 6px;
                }

                QLabel#NotificationLabel {
                    background-color: #E8F5E9;
                    border: 1px solid #82C98E;
                    border-radius: 5px;
                    color: #218838;
                    font-weight: bold;
                    padding: 4px 12px;
                }

            """)
        self.update_status_bar_style()
        self.update_theme_button_style()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_styles()
        if self.dark_mode:
            self.theme_btn.setText("☀  Light mode")
            self.show_notification("Dark mode enabled")
        else:
            self.theme_btn.setText("☾  Dark mode")
            self.show_notification("Light mode enabled")

    def update_theme_button_style(self):
        if self.dark_mode:
            self.theme_btn.setStyleSheet("""
                QPushButton {
                    background-color: #292929;
                    border: 1px solid #454545;
                    color: #F0F0F0;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 12px;
                }

                QPushButton:hover {
                    background-color: #363636;
                }
            """)
        else:
            self.theme_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E8E8E8;
                    border: 1px solid #BBBBBB;
                    color: #202020;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 5px 12px;
                }

                QPushButton:hover {
                    background-color: #DDDDDD;
                }
            """)

    def update_status_bar(self, status, color):
        self.stream_status.setText(
            f'STREAM STATUS  <span style="color:{color};">● {status}</span>'
        )

    def update_status_bar_style(self):
        if self.dark_mode:
            self.stream_status_bar.setStyleSheet("""
                QFrame#StreamStatusBar {
                    background-color: #191919;
                    border: 1px solid #3A3A3A;
                    border-radius: 6px;
                }
            """)
        else:
            self.stream_status_bar.setStyleSheet("""
                QFrame#StreamStatusBar {
                    background-color: #FAFAFA;
                    border: 1px solid #C8C8C8;
                    border-radius: 6px;
                }
            """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_suggestions()
        self.position_notification()

    def position_suggestions(self):
        if not hasattr(self, "suggestions_list"):
            return
        if not self.game_category:
            return
        # Position directly underneath the input.
        pos = self.game_category.mapTo(
            self.main_widget, QPoint(0, self.game_category.height() + 2)
        )
        self.suggestions_list.setGeometry(
            pos.x(), pos.y(), self.game_category.width(), 130
        )
        self.suggestions_list.raise_()

    def toggle_token_visibility(self):
        if self.token_entry.echoMode() == QLineEdit.Normal:
            self.token_entry.setEchoMode(QLineEdit.Password)
            self.toggle_token_btn.setText("👁")
            self.toggle_token_btn.setToolTip("Show token")
        else:
            self.token_entry.setEchoMode(QLineEdit.Normal)
            self.toggle_token_btn.setText("◉")
            self.toggle_token_btn.setToolTip("Hide token")

    def toggle_key_visibility(self):
        if self.stream_key.echoMode() == QLineEdit.Normal:
            self.stream_key.setEchoMode(QLineEdit.Password)
            self.toggle_key_btn.setText("👁")
            self.toggle_key_btn.setToolTip("Show stream key")
        else:
            self.stream_key.setEchoMode(QLineEdit.Normal)
            self.toggle_key_btn.setText("◉")
            self.toggle_key_btn.setToolTip("Hide stream key")

    def handle_token_change(self):
        has_token = bool(self.token_entry.text().strip())
        is_not_live = self.stream_status.text().find("NOT LIVE") != -1
        is_refreshing = not self.refresh_btn.isEnabled()
        self.go_live_btn.setEnabled(
            has_token
            and is_not_live
            and not is_refreshing
            and self.can_go_live.text() == "● Yes"
        )

    def load_config(self):
        try:
            config_path = Path(__file__).resolve().parent / "config.json"

            with open(config_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception:
            data = {}

        self.token_entry.setText(data.get("token", ""))
        self.stream_title.setText(data.get("title", ""))
        self.game_category.setText(data.get("game", ""))
        self.mature_checkbox.setChecked(
            data.get("audience_type", "0") == "1"
        )

        if self.token_entry.text().strip():
            self.refresh_account_info()

    def _on_save_config_clicked(self):
        """Handle Save Config button click."""
        self.save_btn.setText("Saving...")
        self.save_btn.setEnabled(False)

        try:
            self.save_config(show_message=False)

            self.save_btn.setText("✓ Saved!")
            self.show_notification("Configuration saved")

            QTimer.singleShot(
                1500,
                lambda: (
                    self.save_btn.setText("Save Config"),
                    self.save_btn.setEnabled(True),
                )
            )

        except Exception as e:
            self.save_btn.setText("Save Config")
            self.save_btn.setEnabled(True)

            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save configuration:\n{e}"
            )

    def save_config(self, show_message=True):
        data = {
            "title": self.stream_title.text(),
            "game": self.game_category.text(),
            "audience_type": "1" if self.mature_checkbox.isChecked() else "0",
            "token": self.token_entry.text(),
        }

        config_path = Path(__file__).resolve().parent / "config.json"

        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        if show_message:
            self.show_notification("Configuration saved")

    def load_account_info(self):
        if not self.stream:
            return
        try:
            info = self.stream.getInfo()
            self.apply_account_info(info)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load account info: {str(e)}"
            )

    def apply_account_info(self, info):
        user = info.get("user", {})
        username = user.get("username", "Unknown")
        self.tiktok_username.setText(username)
        app_status = info.get("application_status", {})
        status = app_status.get("status", "Unknown")
        self.app_status.setText(f"● {status.capitalize()}")
        if status.lower() == "approved":
            self.app_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif status.lower() in ("rejected", "denied"):
            self.app_status.setStyleSheet("color: #F44336; font-weight: bold;")
        else:
            self.app_status.setStyleSheet("color: #FF9800; font-weight: bold;")
        can_go_live = info.get("can_be_live", False)
        self.can_go_live.setText("● Yes" if can_go_live else "● No")
        if can_go_live:
            self.can_go_live.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.can_go_live.setStyleSheet("color: #F44336; font-weight: bold;")
        # Enable / disable stream details
        self.stream_title.setEnabled(can_go_live)
        self.game_category.setEnabled(can_go_live)
        self.mature_checkbox.setEnabled(can_go_live)
        if can_go_live:
            self.go_live_btn.setEnabled(
                self.stream_status.text().find("NOT LIVE") != -1
            )
        else:
            self.go_live_btn.setEnabled(False)

    def refresh_account_info(self):
        token = self.token_entry.text().strip()
        if not token:
            self.show_notification("No token available", "warning")
            return
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Refreshing...")
        self.go_live_btn.setEnabled(False)

        def _run():
            try:
                stream = Stream(token)
                info = stream.getInfo()
                self._account_refresh_ready.emit(info)
            except Exception as e:
                self._account_refresh_error.emit(
                    "Failed to refresh account information: " + str(e)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _handle_account_refresh(self, info):
        try:
            self.stream = Stream(self.token_entry.text())
            self.apply_account_info(info)
            self.fetch_game_mask_id(self.game_category.text())
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh Account Info")
            self.show_notification("Account information refreshed")
        except Exception as e:
            self._handle_account_refresh_error(
                f"Failed to update account information: {str(e)}"
            )

    def _handle_account_refresh_error(self, message):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Account Info")
        can_go_live = self.can_go_live.text() == "● Yes"
        is_not_live = self.stream_status.text().find("NOT LIVE") != -1
        self.go_live_btn.setEnabled(
            can_go_live and is_not_live and bool(self.token_entry.text())
        )
        QMessageBox.critical(self, "Refresh Error", message)

    def _do_restore_local_btn(self):
        self.load_local_btn.setEnabled(True)
        self.load_local_btn.setText("Load from PC")

    def _do_restore_online_btn(self):
        self.load_online_btn.setEnabled(True)
        self.load_online_btn.setText("Load from Web")

    def load_local_token(self):
        self.load_local_btn.setEnabled(False)
        self.load_local_btn.setText("Searching…")

        def _run():
            try:
                token = self._find_local_token()
            except Exception as e:
                print(traceback.format_exc())
                self._token_error.emit(f"Unexpected error: {e}")
                return
            finally:
                self._restore_local_btn.emit()
            if token:
                self._token_ready.emit(token)
            else:
                self._token_error.emit(
                    "No API Token found locally. "
                    "Make sure Streamlabs is installed "
                    "and you're logged in using TikTok."
                )

        threading.Thread(target=_run, daemon=True).start()

    def _find_local_token(self) -> str | None:
        if platform.system() == "Windows":
            path_pattern = os.path.expandvars(
                r"%appdata%\slobs-client\Local Storage\leveldb\*.log"
            )
        elif platform.system() == "Darwin":
            path_pattern = os.path.expanduser(
                "~/Library/Application Support/slobs-client/"
                "Local Storage/leveldb/*.log"
            )
        else:
            return None
        files = sorted(glob.glob(path_pattern), key=os.path.getmtime, reverse=True)
        token_pattern = re.compile(r'"apiToken":"([a-f0-9]+)"', re.IGNORECASE)
        for file in files:
            try:
                with open(file, "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                content = re.sub(r"[\x00]", "", content)
                matches = token_pattern.findall(content)
                if matches:
                    return matches[-1]
            except Exception as e:
                print(f"Error reading {file}: {e}")
        return None

    def fetch_online_token(self):
        self.load_online_btn.setEnabled(False)
        self.load_online_btn.setText("Waiting for login…")
        retriever = TokenRetriever()

        def _run():
            try:
                token = retriever.retrieve_token()
            except Exception as e:
                print(traceback.format_exc())
                self._token_error.emit(f"Unexpected error: {e}")
                return
            finally:
                self._restore_online_btn.emit()
            if token:
                self._token_ready.emit(token)
            else:
                self._token_error.emit("Failed to obtain token online!")

        threading.Thread(target=_run, daemon=True).start()

    def _apply_token(self, token: str):
        self.token_entry.setText(token)
        self.stream = Stream(token)
        self.load_account_info()
        self.fetch_game_mask_id(self.game_category.text())

    def fetch_game_mask_id(self, game_name):
        self.game_mask_id = ""
        if not self.stream or not game_name:
            return
        stream = self.stream
        searched_text = game_name.strip()

        def _run():
            try:
                categories = stream.search(searched_text)
                for category in categories:
                    name = category.get("full_name", "").strip()
                    if name.lower() == searched_text.lower():
                        self._game_mask_ready.emit(
                            category.get("game_mask_id", ""), searched_text
                        )
                        return
                self._game_mask_ready.emit("", searched_text)
            except Exception:
                self._game_mask_ready.emit("", searched_text)

        threading.Thread(target=_run, daemon=True).start()

    def _handle_game_mask_ready(self, mask_id, searched_text):
        current_text = self.game_category.text().strip()
        if current_text.lower() != searched_text.lower():
            return
        self.game_mask_id = mask_id

    def handle_game_search(self, text):
        if self._ignore_next_game_search:
            self._ignore_next_game_search = False
            return
        text = text.strip()
        if not text or not self.stream:
            self._game_search_timer.stop()
            self._game_searching = False
            self.suggestions_list.clear()
            self.suggestions_list.hide()
            self.game_mask_id = ""
            return
        self._game_search_timer.stop()
        self._game_search_timer.start()

    def _start_game_search(self):
        text = self.game_category.text().strip()
        if not text or not self.stream:
            return
        self._game_searching = True
        self.suggestions_list.clear()
        self.suggestions_list.addItem("Searching...")
        self.suggestions_list.setEnabled(False)
        self.position_suggestions()
        self.suggestions_list.show()
        self.suggestions_list.raise_()
        stream = self.stream

        def _run():
            try:
                categories = stream.search(text)
                self._game_search_ready.emit(categories, text)
            except Exception as e:
                self._game_search_error.emit(f"Game search failed: {str(e)}")

        threading.Thread(target=_run, daemon=True).start()

    def _handle_game_search_results(self, categories, searched_text):
        current_text = self.game_category.text().strip()
        # Ignore stale search results.
        if current_text.lower() != searched_text.lower():
            return
        self._game_searching = False
        self.suggestions_list.setEnabled(True)
        self.suggestions_list.clear()
        search_text = searched_text.lower()
        # Remove duplicates
        unique_categories = {}
        for category in categories:
            name = category.get("full_name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in unique_categories:
                unique_categories[key] = category
        categories = list(unique_categories.values())

        # Relevance
        def relevance(category):
            name = category.get("full_name", "").strip()
            name_lower = name.lower()
            if name_lower == search_text:
                return 0
            if name_lower.startswith(search_text):
                return 1
            if search_text in name_lower:
                return 2
            return 3

        categories.sort(
            key=lambda category: (
                relevance(category),
                category.get("full_name", "").lower(),
            )
        )
        # "Other" at bottom
        other_categories = [
            category
            for category in categories
            if category.get("full_name", "").strip().lower() == "other"
        ]
        categories = [
            category
            for category in categories
            if category.get("full_name", "").strip().lower() != "other"
        ]
        categories.extend(other_categories)
        # Limit
        categories = categories[:8]
        # Exact mask ID
        self.game_mask_id = ""
        for category in categories:
            name = category.get("full_name", "").strip()
            if name.lower() == search_text:
                self.game_mask_id = category.get("game_mask_id", "")
                break
        if not categories:
            self.suggestions_list.hide()
            return
        # Store categories
        self._game_categories.clear()
        for category in categories:
            name = category.get("full_name", "").strip()
            if not name:
                continue
            self._game_categories[name.lower()] = category
            self.suggestions_list.addItem(QListWidgetItem(name))
        self.position_suggestions()
        self.suggestions_list.show()
        self.suggestions_list.raise_()
        self.suggestions_list.setCurrentRow(0)

    def _handle_game_search_error(self, message):
        self._game_searching = False
        self.suggestions_list.setEnabled(True)
        self.suggestions_list.clear()
        self.suggestions_list.hide()
        self.game_mask_id = ""
        self.show_notification("Game search failed", "error")

    def handle_suggestion_selected(self, item):
        if not item:
            return
        text = item.text().strip()
        if not text or text == "Searching...":
            return
        category = self._game_categories.get(text.lower())
        if category:
            self.game_mask_id = category.get("game_mask_id", "")
        self._ignore_next_game_search = True
        self.game_category.setText(text)
        self.suggestions_list.hide()
        self.game_category.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.game_category and event.type() == QEvent.KeyPress:
            if self.suggestions_list.isVisible() and self.suggestions_list.count() > 0:
                key = event.key()
                if key == Qt.Key_Down:
                    current = self.suggestions_list.currentRow()
                    if current < self.suggestions_list.count() - 1:
                        self.suggestions_list.setCurrentRow(current + 1)
                    return True
                if key == Qt.Key_Up:
                    current = self.suggestions_list.currentRow()
                    if current > 0:
                        self.suggestions_list.setCurrentRow(current - 1)
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    item = self.suggestions_list.currentItem()
                    if item:
                        self.handle_suggestion_selected(item)
                    return True
                if key == Qt.Key_Escape:
                    self.suggestions_list.hide()
                    return True
        return super().eventFilter(obj, event)

    def start_stream(self):
        if not self.stream:
            QMessageBox.critical(self, "Error", "No Streamlabs connection available!")
            return
        self.go_live_btn.setEnabled(False)
        self.end_live_btn.setEnabled(False)
        self.go_live_btn.setText("Starting...")
        self.update_status_bar("STARTING...", "#FF9800")
        stream = self.stream
        title = self.stream_title.text()
        game_mask_id = self.game_mask_id
        audience_type = "1" if self.mature_checkbox.isChecked() else "0"

        def _run():
            try:
                stream_url, stream_key = stream.start(
                    title, game_mask_id, audience_type
                )
                if stream_url and stream_key:
                    self._stream_start_ready.emit(stream_url, stream_key)
                else:
                    self._stream_start_error.emit("Failed to start stream!")
            except Exception as e:
                self._stream_start_error.emit(f"Failed to start stream: {str(e)}")

        threading.Thread(target=_run, daemon=True).start()

    def _handle_stream_started(self, stream_url, stream_key):
        self.stream_url.setText(stream_url)
        self.stream_key.setText(stream_key)
        self.go_live_btn.setText("Go Live")
        self.go_live_btn.setEnabled(False)
        self.end_live_btn.setText("End Live")
        self.end_live_btn.setEnabled(True)
        self.update_status_bar("LIVE", "#4CAF50")
        self.show_notification("Stream started successfully")

    def _handle_stream_start_error(self, message):
        self.go_live_btn.setText("Go Live")
        self.go_live_btn.setEnabled(True)
        self.end_live_btn.setText("End Live")
        self.end_live_btn.setEnabled(False)
        self.update_status_bar("NOT LIVE", "#9E9E9E")
        QMessageBox.critical(self, "Error", message)

    def end_stream(self):
        if not self.stream:
            QMessageBox.critical(self, "Error", "No Streamlabs connection available!")
            return
        self.go_live_btn.setEnabled(False)
        self.end_live_btn.setEnabled(False)
        self.end_live_btn.setText("Ending...")
        self.update_status_bar("ENDING...", "#FF9800")
        stream = self.stream

        def _run():
            try:
                success = stream.end()
                self._stream_end_ready.emit(success)
            except Exception as e:
                self._stream_end_error.emit(f"Failed to end stream: {str(e)}")

        threading.Thread(target=_run, daemon=True).start()

    def _handle_stream_ended(self, success):
        if success:
            self.stream_url.clear()
            self.stream_key.clear()
            self.go_live_btn.setText("Go Live")
            self.go_live_btn.setEnabled(self.can_go_live.text() == "● Yes")
            self.end_live_btn.setText("End Live")
            self.end_live_btn.setEnabled(False)
            self.update_status_bar("NOT LIVE", "#9E9E9E")
            self.show_notification("Stream ended successfully")
        else:
            self.go_live_btn.setText("Go Live")
            self.go_live_btn.setEnabled(False)
            self.end_live_btn.setText("End Live")
            self.end_live_btn.setEnabled(True)
            self.update_status_bar("LIVE", "#4CAF50")
            QMessageBox.critical(self, "Error", "Failed to end stream!")

    def _handle_stream_end_error(self, message):
        self.go_live_btn.setText("Go Live")
        self.go_live_btn.setEnabled(False)
        self.end_live_btn.setText("End Live")
        self.end_live_btn.setEnabled(True)
        self.update_status_bar("LIVE", "#4CAF50")
        QMessageBox.critical(self, "Error", message)

    def show_notification(self, message, notification_type="success"):
        if notification_type == "success":
            self.notification_label.setText(f"✓ {message}")
        elif notification_type == "warning":
            self.notification_label.setText(f"⚠ {message}")
        else:
            self.notification_label.setText(f"✕ {message}")
        if self.dark_mode:
            if notification_type == "success":
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #4CAF50;
                        background-color: #1B3A24;
                        border: 1px solid #2E7D46;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
            elif notification_type == "warning":
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #FF9800;
                        background-color: #3A2D1B;
                        border: 1px solid #8A641F;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
            else:
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #F44336;
                        background-color: #3A1B1B;
                        border: 1px solid #8A2E2E;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
        else:
            if notification_type == "success":
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #218838;
                        background-color: #E8F5E9;
                        border: 1px solid #82C98E;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
            elif notification_type == "warning":
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #9A6700;
                        background-color: #FFF4D6;
                        border: 1px solid #D6B656;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
            else:
                self.notification_label.setStyleSheet("""
                    QLabel#NotificationLabel {
                        color: #C62828;
                        background-color: #FDECEC;
                        border: 1px solid #E29B9B;
                        border-radius: 5px;
                        font-weight: bold;
                        padding: 4px 12px;
                    }
                """)
        self.position_notification()
        self.notification_label.show()
        self.notification_label.raise_()
        if hasattr(self, "_notification_timer"):
            self._notification_timer.stop()
        self._notification_timer = QTimer(self)
        self._notification_timer.setSingleShot(True)
        self._notification_timer.timeout.connect(self.notification_label.hide)
        self._notification_timer.start(2500)

    def position_notification(self):
        if not hasattr(self, "notification_label"):
            return
        parent = self.main_widget
        width = min(430, max(320, parent.width() - 30))
        height = 32
        x = (parent.width() - width) // 2
        y = parent.height() - height - 10
        self.notification_label.setGeometry(x, y, width, height)

    def copy_to_clipboard(self, widget, button, default_text):
        text = widget.text()
        if not text:
            button.setText("Nothing to copy")
            QTimer.singleShot(1500, lambda: button.setText(default_text))
            return
        QApplication.clipboard().setText(text)
        button.setText("✓ Copied!")
        self.show_notification("Copied to clipboard")
        QTimer.singleShot(1500, lambda: button.setText(default_text))

    def show_help(self):
        help_text = """
1. Apply for LIVE access on Streamlabs
2. Install Streamlabs and login to TikTok
3. Use this app to get your Streamlabs token
4. Select your stream category
5. Click Go Live
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Help")
        msg.setText(help_text)
        msg.addButton(QMessageBox.Ok)
        msg.exec()

    def check_updates_on_startup(self):
        try:
            update_info = VersionChecker.check_update()

            if not update_info:
                return

            latest = update_info["latest"]
            current = update_info["current"]

            if version.parse(latest) > version.parse(current):
                self.update_btn.setText("Update available!")
                self.update_btn.setObjectName("UpdateAvailableButton")
                self.update_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #725515;
                        border: 1px solid #9A7620;
                        color: #FFFFFF;
                        font-weight: bold;
                    }
                """)
                self.update_btn.setToolTip(f"Version {latest} is available")

        except Exception as e:
            print(f"Update check failed: {e}")


    def check_for_updates(self):
        try:
            update_info = VersionChecker.check_update()

        except Exception as e:
            self.show_notification("Update check failed", "error")
            print(traceback.format_exc())
            return

        if not update_info:
            self.show_notification("Unable to check for updates", "warning")
            return

        latest = update_info["latest"]
        current = update_info["current"]

        if version.parse(latest) > version.parse(current):
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setText(
                f"Version {latest} is available.\n\n"
                f"Current version: {current}"
            )

            open_btn = msg.addButton(
                "Open Release",
                QMessageBox.AcceptRole
            )
            msg.addButton(QMessageBox.Cancel)

            msg.exec()

            if msg.clickedButton() == open_btn:
                QDesktopServices.openUrl(
                    update_info["url"]
                )

        else:
            self.show_notification(
                f"You're up to date! (v{current})",
                "success"
            )

    def open_live_monitor(self):
        QDesktopServices.openUrl(
            "https://livecenter.tiktok.com/live_monitor?lang=fr-FR"
        )

    def handle_ui_update(self):
        self.load_account_info()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StreamApp()
    window.show()
    sys.exit(app.exec())