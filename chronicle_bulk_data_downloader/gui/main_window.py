from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chronicle_bulk_data_downloader import __version__
from chronicle_bulk_data_downloader.core import (
    AuthConfig,
    DataTypeConfig,
    DownloadConfig,
    FilterConfig,
)
from chronicle_bulk_data_downloader.download_worker import DownloadThreadWorker

LOGGER = logging.getLogger(__name__)


class ChronicleBulkDataDownloader(QWidget):
    """
    A QWidget-based application for downloading bulk data from Chronicle.

    This is a thin GUI wrapper that delegates all business logic to ChronicleDownloader.
    """

    @staticmethod
    def get_config_path(*, ensure_dir: bool = False) -> Path:
        """
        Gets the correct path for the config file, handling both script and PyInstaller EXE cases.

        On macOS, PyInstaller bundles run from a read-only filesystem, so the config
        must be stored in a user-writable location (~/Library/Application Support/).
        On Windows, we use the APPDATA directory to avoid permission issues in
        Program Files or other restricted locations.

        Args:
            ensure_dir: If True, create the parent directory if it doesn't exist.
                        Only pass True when writing the config file.
        """
        from chronicle_bulk_data_downloader.constants import CONFIG_FILENAME, get_user_dir

        if getattr(sys, "frozen", False):
            config_dir = get_user_dir("config")
            if ensure_dir:
                config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir / CONFIG_FILENAME
        else:
            return Path(CONFIG_FILENAME)

    def __init__(self) -> None:
        """
        Initializes the ChronicleBulkDataDownloader class.
        """
        super().__init__()

        self.download_folder: Path | str = ""
        self.download_active = False
        self.worker = None
        self.ios_sensor_warning_label: QLabel

        self._init_UI()
        self._load_and_set_config()

    def _select_and_validate_download_folder(self) -> None:
        """
        Select and validate the download folder.
        """
        LOGGER.debug("Selecting download folder")
        current_download_folder_label = self.download_folder_label.text().strip()
        selected_folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")

        if selected_folder and Path(selected_folder).is_dir():
            self.download_folder = selected_folder
            self.download_folder_label.setText(selected_folder)
            LOGGER.debug(f"Selected download folder: {selected_folder}")
        else:
            self.download_folder_label.setText(current_download_folder_label)
            LOGGER.debug("Invalid folder selected or no folder selected, reset to previous value")

    def _update_list_label_text(self) -> None:
        """
        Updates the label text based on the state of the inclusive filter checkbox.
        """
        if self.inclusive_filter_checkbox.isChecked():
            self.list_ids_label.setText("List of participant IDs to *include* (separated by commas):")
        else:
            self.list_ids_label.setText("List of participant IDs to *exclude* (separated by commas):")
        LOGGER.debug("Updated label text based on inclusive filter checkbox state")

    def _init_UI(self) -> None:
        """
        Initializes the user interface.
        """
        LOGGER.debug("Initializing UI")
        self.setWindowTitle(f"Chronicle Bulk Data Downloader v{__version__}")
        self.setGeometry(100, 100, 500, 450)

        main_layout = QVBoxLayout()

        main_layout.addWidget(self._create_folder_selection_group())
        main_layout.addSpacing(10)

        main_layout.addWidget(self._create_authorization_token_entry_group())
        main_layout.addSpacing(10)

        main_layout.addWidget(self._create_study_id_entry_group())
        main_layout.addSpacing(10)

        main_layout.addWidget(self._create_participant_ids_entry_group())
        main_layout.addSpacing(10)

        main_layout.addLayout(self._create_basic_data_checkbox_layout())
        main_layout.addSpacing(10)

        main_layout.addLayout(self._create_ios_sensor_checkbox_layout())
        main_layout.addSpacing(10)

        main_layout.addLayout(self._create_time_use_diary_checkbox_layout())
        main_layout.addSpacing(10)

        main_layout.addLayout(self._create_options_checkbox_layout())
        main_layout.addSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                width: 1px;
            }
        """)

        main_layout.addWidget(self.progress_bar)
        main_layout.addSpacing(10)

        main_layout.addLayout(self._create_button_layout())
        main_layout.addSpacing(10)

        self.setLayout(main_layout)
        self._center_window()
        LOGGER.debug("Initialized UI")

    def _create_folder_selection_group(self) -> QGroupBox:
        """
        Creates the folder selection group box.
        """
        group_box = QGroupBox("Folder Selection")
        group_layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.select_download_folder_button = QPushButton("Select Download Folder")
        self.select_download_folder_button.clicked.connect(self._select_and_validate_download_folder)
        self.select_download_folder_button.setStyleSheet("QPushButton { padding: 10px; }")
        button_layout.addWidget(self.select_download_folder_button)
        button_layout.addStretch()
        group_layout.addLayout(button_layout)

        label_layout = QHBoxLayout()
        self.download_folder_label = QLabel("Select the folder to download the Chronicle data to")
        self.download_folder_label.setStyleSheet(
            """QLabel {
                font-size: 10pt;
                font-weight: bold;
                padding: 5px;
                border-radius: 4px;
                background-color: #f5f5f5;
                border: 1px solid #dcdcdc;
                color: #333;
            }"""
        )
        self.download_folder_label.setWordWrap(True)
        self.download_folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.download_folder_label.setMinimumWidth(400)
        self.download_folder_label.setFixedHeight(50)
        label_layout.addWidget(self.download_folder_label, 1)
        group_layout.addLayout(label_layout)

        group_box.setLayout(group_layout)
        return group_box

    def _create_authorization_token_entry_group(self) -> QGroupBox:
        """
        Creates the authorization token entry group box.
        """
        group_box = QGroupBox("Authorization Token Entry")
        group_layout = QVBoxLayout()

        label_layout = QHBoxLayout()
        label_layout.addStretch()
        self.authorization_token_label = QLabel("Please paste the temporary authorization token:")
        self.authorization_token_label.setWordWrap(True)
        self.authorization_token_label.setFixedWidth(250)
        label_layout.addWidget(self.authorization_token_label)
        label_layout.addStretch()
        group_layout.addLayout(label_layout)

        entry_layout = QHBoxLayout()
        entry_layout.addStretch()
        self.authorization_token_entry = QTextEdit()
        self.authorization_token_entry.setFixedSize(300, 50)
        self.authorization_token_entry.setStyleSheet("""
            QTextEdit {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QTextEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        entry_layout.addWidget(self.authorization_token_entry)
        entry_layout.addStretch()
        group_layout.addLayout(entry_layout)

        group_box.setLayout(group_layout)
        return group_box

    def _create_study_id_entry_group(self) -> QGroupBox:
        """
        Creates the study ID entry group box.
        """
        group_box = QGroupBox("Study ID Entry")
        group_layout = QVBoxLayout()

        label_layout = QHBoxLayout()
        label_layout.addStretch()
        self.study_id_label = QLabel("Please paste the study ID:")
        label_layout.addWidget(self.study_id_label)
        label_layout.addStretch()
        group_layout.addLayout(label_layout)

        entry_layout = QHBoxLayout()
        entry_layout.addStretch()
        self.study_id_entry = QLineEdit()
        self.study_id_entry.setFixedWidth(236)
        self.study_id_entry.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        entry_layout.addWidget(self.study_id_entry)
        entry_layout.addStretch()
        group_layout.addLayout(entry_layout)

        group_box.setLayout(group_layout)
        return group_box

    def _create_participant_ids_entry_group(self) -> QGroupBox:
        """
        Creates the participant IDs entry group box.
        """
        group_box = QGroupBox("Participant IDs Entry")
        group_layout = QVBoxLayout()

        label_layout = QHBoxLayout()
        label_layout.addStretch()
        self.list_ids_label = QLabel("List of participant IDs to *exclude* (separated by commas):")
        label_layout.addWidget(self.list_ids_label)
        label_layout.addStretch()
        group_layout.addLayout(label_layout)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()
        self.inclusive_filter_checkbox = QCheckBox("Use *Inclusive* List Instead")
        self.inclusive_filter_checkbox.stateChanged.connect(self._update_list_label_text)
        checkbox_layout.addWidget(self.inclusive_filter_checkbox)
        checkbox_layout.addStretch()
        group_layout.addLayout(checkbox_layout)

        entry_layout = QHBoxLayout()
        entry_layout.addStretch()
        self.participant_ids_to_filter_list_entry = QTextEdit()
        self.participant_ids_to_filter_list_entry.setFixedSize(300, 75)
        self.participant_ids_to_filter_list_entry.setStyleSheet("""
            QTextEdit {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QTextEdit:focus {
                border: 1px solid #3498db;
            }
        """)
        entry_layout.addWidget(self.participant_ids_to_filter_list_entry)
        entry_layout.addStretch()
        group_layout.addLayout(entry_layout)

        group_box.setLayout(group_layout)
        return group_box

    def _center_window(self):
        """
        Centers the application window on the screen.
        """
        frame_geometry = self.frameGeometry()
        screen = QApplication.primaryScreen()
        if screen is not None:
            center_point = screen.availableGeometry().center()
            frame_geometry.moveCenter(center_point)
            self.move(frame_geometry.topLeft())
            LOGGER.debug("Centered the window")
        else:
            LOGGER.warning("Could not center window - primary screen not available")

    def _create_basic_data_checkbox_layout(self) -> QVBoxLayout:
        """
        Creates the basic data checkbox layout.
        """
        main_layout = QVBoxLayout()

        self.ios_sensor_warning_label = QLabel("Uncheck iOS Sensor data download to download Android data types")
        self.ios_sensor_warning_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.ios_sensor_warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ios_sensor_warning_label.hide()
        main_layout.addWidget(self.ios_sensor_warning_label)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()

        self.download_raw_data_checkbox = QCheckBox("Download Raw Data")
        self.download_raw_data_checkbox.setChecked(True)
        checkbox_layout.addWidget(self.download_raw_data_checkbox)

        self.download_preprocessed_data_checkbox = QCheckBox("Download Preprocessed Data")
        self.download_preprocessed_data_checkbox.setChecked(True)
        checkbox_layout.addWidget(self.download_preprocessed_data_checkbox)

        self.download_survey_data_checkbox = QCheckBox("Download Survey Data")
        self.download_survey_data_checkbox.setChecked(True)
        checkbox_layout.addWidget(self.download_survey_data_checkbox)

        checkbox_layout.addStretch()
        main_layout.addLayout(checkbox_layout)
        return main_layout

    def _create_ios_sensor_checkbox_layout(self) -> QHBoxLayout:
        """
        Creates the layout for the iOS sensor checkbox.
        """
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()

        self.download_ios_sensor_checkbox = QCheckBox("Download iOS Sensor Data")
        self.download_ios_sensor_checkbox.stateChanged.connect(self._handle_ios_sensor_checkbox_state_changed)
        checkbox_layout.addWidget(self.download_ios_sensor_checkbox)

        checkbox_layout.addStretch()
        return checkbox_layout

    def _handle_ios_sensor_checkbox_state_changed(self):
        """
        Handles the state change of the iOS sensor checkbox.
        When checked, disables all other data type checkboxes.
        """
        is_checked = self.download_ios_sensor_checkbox.isChecked()
        if self.ios_sensor_warning_label is not None:
            self.ios_sensor_warning_label.setVisible(is_checked)

        if is_checked:
            self.download_raw_data_checkbox.setEnabled(False)
            self.download_preprocessed_data_checkbox.setEnabled(False)
            self.download_survey_data_checkbox.setEnabled(False)
            self.download_raw_data_checkbox.setChecked(False)
            self.download_preprocessed_data_checkbox.setChecked(False)
            self.download_survey_data_checkbox.setChecked(False)
        else:
            self.download_raw_data_checkbox.setEnabled(True)
            self.download_preprocessed_data_checkbox.setEnabled(True)
            self.download_survey_data_checkbox.setEnabled(True)

    def _create_time_use_diary_checkbox_layout(self) -> QHBoxLayout:
        """
        Creates the layout for the time use diary checkboxes.
        """
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()

        self.download_time_use_diary_daytime_checkbox = QCheckBox("Download Daytime Time Use Diary")
        checkbox_layout.addWidget(self.download_time_use_diary_daytime_checkbox)

        self.download_time_use_diary_nighttime_checkbox = QCheckBox("Download Nighttime Time Use Diary")
        checkbox_layout.addWidget(self.download_time_use_diary_nighttime_checkbox)

        self.download_time_use_diary_summarized_checkbox = QCheckBox("Download Summarized Time Use Diary")
        checkbox_layout.addWidget(self.download_time_use_diary_summarized_checkbox)

        checkbox_layout.addStretch()
        return checkbox_layout

    def _create_options_checkbox_layout(self) -> QHBoxLayout:
        """
        Creates the layout for additional options checkboxes.
        """
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch()

        self.delete_zero_byte_files_checkbox = QCheckBox("Delete Zero-Byte Files After Download")
        checkbox_layout.addWidget(self.delete_zero_byte_files_checkbox)

        checkbox_layout.addStretch()
        return checkbox_layout

    def _create_button_layout(self) -> QHBoxLayout:
        """
        Creates the layout for the button.
        """
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._run)
        self.run_button.setStyleSheet("QPushButton { padding: 10px; }")
        button_layout.addWidget(self.run_button)
        button_layout.addStretch()
        return button_layout

    def _load_and_set_config(self) -> None:
        """
        Loads and sets the configuration from a JSON file.
        """
        try:
            with self.get_config_path().open("r") as f:
                config = json.load(f)
            LOGGER.debug("Loaded configuration from file")
        except FileNotFoundError:
            LOGGER.warning("Configuration file not found")
            return

        self.download_folder = config.get("download_folder", "")
        self.study_id_entry.setText(config.get("study_id", ""))
        self.participant_ids_to_filter_list_entry.setText(config.get("participant_ids_to_filter", ""))
        self.inclusive_filter_checkbox.setChecked(config.get("inclusive_checked", False))
        self.download_raw_data_checkbox.setChecked(config.get("raw_checked", False))
        self.download_preprocessed_data_checkbox.setChecked(config.get("preprocessed_checked", False))
        self.download_survey_data_checkbox.setChecked(config.get("survey_checked", False))
        self.download_ios_sensor_checkbox.setChecked(config.get("ios_sensor_checked", False))
        self.download_time_use_diary_daytime_checkbox.setChecked(config.get("time_use_diary_daytime_checked", False))
        self.download_time_use_diary_nighttime_checkbox.setChecked(config.get("time_use_diary_nighttime_checked", False))
        self.download_time_use_diary_summarized_checkbox.setChecked(config.get("time_use_diary_summarized_checked", False))
        self.delete_zero_byte_files_checkbox.setChecked(config.get("delete_zero_byte_files_checked", False))

        if self.download_folder:
            self.download_folder_label.setText(str(self.download_folder))

        self._handle_ios_sensor_checkbox_state_changed()

        LOGGER.debug("Set configuration from loaded file")

    def _build_download_config(self) -> DownloadConfig:
        """
        Build DownloadConfig from current UI state.

        Returns:
            DownloadConfig object with current settings
        """
        auth = AuthConfig(
            auth_token=self.authorization_token_entry.toPlainText().strip(),
            study_id=self.study_id_entry.text().strip(),
        )

        data_types = DataTypeConfig(
            download_raw=self.download_raw_data_checkbox.isChecked(),
            download_preprocessed=self.download_preprocessed_data_checkbox.isChecked(),
            download_survey=self.download_survey_data_checkbox.isChecked(),
            download_ios_sensor=self.download_ios_sensor_checkbox.isChecked(),
            download_time_use_diary_daytime=self.download_time_use_diary_daytime_checkbox.isChecked(),
            download_time_use_diary_nighttime=self.download_time_use_diary_nighttime_checkbox.isChecked(),
            download_time_use_diary_summarized=self.download_time_use_diary_summarized_checkbox.isChecked(),
        )

        participant_ids_text = self.participant_ids_to_filter_list_entry.toPlainText()
        participant_ids = participant_ids_text.split(",") if participant_ids_text else []

        filter_config = FilterConfig(
            participant_ids=participant_ids,
            inclusive=self.inclusive_filter_checkbox.isChecked(),
        )

        return DownloadConfig(
            auth=auth,
            download_folder=Path(self.download_folder),
            data_types=data_types,
            filter_config=filter_config,
            delete_zero_byte_files=self.delete_zero_byte_files_checkbox.isChecked(),
        )

    def _run(self):
        """
        Initiates the download process.
        """
        if self.download_active:
            LOGGER.warning("Download already in progress, ignoring request")
            return

        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.cancel()
                self.worker.terminate()
                self.worker.wait()

            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
                self.worker.progress.disconnect()
                if hasattr(self.worker, "progress_text"):
                    self.worker.progress_text.disconnect()
                if hasattr(self.worker, "cancelled"):
                    self.worker.cancelled.disconnect()
            except (RuntimeError, TypeError):
                pass

            self.worker.deleteLater()

        self.worker = DownloadThreadWorker(self)
        self.worker.finished.connect(self.on_download_complete)
        self.worker.error.connect(self.on_download_error)
        self.worker.progress.connect(self.progress_bar.setValue)
        if hasattr(self.worker, "progress_text"):
            self.worker.progress_text.connect(self.progress_bar.setFormat)
        if hasattr(self.worker, "cancelled"):
            self.worker.cancelled.connect(lambda: LOGGER.info("Download cancelled"))

        self.download_active = True

        self._disable_ui_during_download()
        self.progress_bar.setValue(0)
        self.worker.start()

    def _disable_ui_during_download(self) -> None:
        """
        Disable UI controls during download.
        """
        self.select_download_folder_button.setEnabled(False)
        self.authorization_token_entry.setEnabled(False)
        self.study_id_entry.setEnabled(False)
        self.inclusive_filter_checkbox.setEnabled(False)
        self.participant_ids_to_filter_list_entry.setEnabled(False)
        self.download_raw_data_checkbox.setEnabled(False)
        self.download_survey_data_checkbox.setEnabled(False)
        self.download_preprocessed_data_checkbox.setEnabled(False)
        self.download_ios_sensor_checkbox.setEnabled(False)
        self.download_time_use_diary_daytime_checkbox.setEnabled(False)
        self.download_time_use_diary_nighttime_checkbox.setEnabled(False)
        self.download_time_use_diary_summarized_checkbox.setEnabled(False)
        self.delete_zero_byte_files_checkbox.setEnabled(False)
        self.run_button.setText("Cancel")
        self.run_button.clicked.disconnect()
        self.run_button.clicked.connect(self._cancel_download)
        self.run_button.setEnabled(True)

    def _enable_ui_after_download(self) -> None:
        """
        Enable UI controls after download completion or error.
        """
        self.select_download_folder_button.setEnabled(True)
        self.authorization_token_entry.setEnabled(True)
        self.study_id_entry.setEnabled(True)
        self.inclusive_filter_checkbox.setEnabled(True)
        self.participant_ids_to_filter_list_entry.setEnabled(True)

        if self.download_ios_sensor_checkbox.isChecked():
            self._handle_ios_sensor_checkbox_state_changed()
        else:
            self.download_raw_data_checkbox.setEnabled(True)
            self.download_survey_data_checkbox.setEnabled(True)
            self.download_preprocessed_data_checkbox.setEnabled(True)
            self._handle_ios_sensor_checkbox_state_changed()

        self.download_ios_sensor_checkbox.setEnabled(True)
        self.download_time_use_diary_daytime_checkbox.setEnabled(True)
        self.download_time_use_diary_nighttime_checkbox.setEnabled(True)
        self.download_time_use_diary_summarized_checkbox.setEnabled(True)

        self.delete_zero_byte_files_checkbox.setEnabled(True)

        self.run_button.setText("Run")
        self.run_button.clicked.disconnect()
        self.run_button.clicked.connect(self._run)
        self.run_button.setEnabled(True)

    def _cancel_download(self) -> None:
        """
        Cancels the current download process.
        """
        if self.worker and self.worker.isRunning():
            LOGGER.info("Cancelling download process")

            try:
                self.worker.finished.disconnect(self.on_download_complete)
            except (RuntimeError, TypeError):
                pass

            try:
                self.worker.error.disconnect(self.on_download_error)
            except (RuntimeError, TypeError):
                pass

            self.worker.finished.connect(self._handle_cancellation_complete)

            self.worker.cancel()
            self.run_button.setEnabled(False)
            self.run_button.setText("Cancelling...")
            LOGGER.debug("Waiting for download process to gracefully terminate")

            QTimer.singleShot(3000, self._force_cancellation_if_needed)
        elif self.download_active:
            LOGGER.warning("Resetting inconsistent download_active state")
            self.download_active = False
            self._enable_ui_after_download()

    def _force_cancellation_if_needed(self) -> None:
        """
        Forcibly resets the UI if the worker is still running after cancellation timeout.
        """
        if self.run_button.text() == "Cancelling...":
            LOGGER.warning("Cancellation timed out or signal was missed, forcing UI reset")

            self.download_active = False

            self.run_button.setText("Run")

            self._enable_ui_after_download()

            self.progress_bar.setFormat("Download cancelled")

            if self.worker and self.worker.isRunning():
                try:
                    self.worker.terminate()
                    self.worker.wait(500)
                except Exception as e:
                    LOGGER.error(f"Error terminating worker: {e}")

    def _handle_cancellation_complete(self) -> None:
        """
        Handles the completion of cancellation process.
        """
        LOGGER.info("Cancellation complete, resetting UI")

        self.download_active = False

        self._enable_ui_after_download()
        self.progress_bar.setFormat("Download cancelled")

        if self.worker:
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
                self.worker.progress.disconnect()
                if hasattr(self.worker, "progress_text"):
                    self.worker.progress_text.disconnect()
                if hasattr(self.worker, "cancelled"):
                    self.worker.cancelled.disconnect()
            except Exception:
                pass

    def on_download_complete(self) -> None:
        """
        Handles the completion of the download process.
        """
        self.download_active = False

        if self.worker:
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass

        self._enable_ui_after_download()
        if self.worker and self.worker.is_cancelled:
            self.progress_bar.setFormat("Download cancelled")
            LOGGER.info("Download process was cancelled")
        else:
            self.progress_bar.setFormat("Download complete!")
            LOGGER.info("Download process completed successfully")

    def on_download_error(self, error_message: str) -> None:
        """
        Handles errors that occur during the download process.
        """
        self.download_active = False

        if self.worker:
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (RuntimeError, TypeError):
                pass

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Download Error")
        msg_box.setText("An error occurred during the download process.")
        msg_box.setInformativeText(error_message)

        msg_box.exec()

        self._enable_ui_after_download()
        self.progress_bar.setFormat("Error: %p%")
        LOGGER.error("Download error occurred")
