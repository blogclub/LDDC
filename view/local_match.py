import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QPushButton,
    QWidget,
)

from backend.worker import LocalMatchWorker
from ui.local_match_ui import Ui_local_match
from utils.data import cfg
from utils.enum import LocalMatchFileNameMode, LocalMatchSaveMode, LyricsFormat, Source
from utils.threadpool import threadpool
from view.msg_box import MsgBox


class LocalMatchWidget(QWidget, Ui_local_match):
    def __init__(self) -> None:
        super().__init__()

        self.running = False

        self.setupUi(self)
        self.connect_signals()

        self.worker = None

        self.save_mode_changed(self.save_mode_comboBox.currentIndex())

        self.save_path_lineEdit.setText(cfg["default_save_path"])

    def connect_signals(self) -> None:
        self.song_path_pushButton.clicked.connect(lambda: self.select_path(self.song_path_lineEdit))
        self.save_path_pushButton.clicked.connect(lambda: self.select_path(self.save_path_lineEdit))

        self.save_mode_comboBox.currentIndexChanged.connect(self.save_mode_changed)

        self.start_cancel_pushButton.clicked.connect(self.start_cancel_button_clicked)

    def retranslateUi(self, local_match: QWidget) -> None:
        super().retranslateUi(local_match)
        self.save_mode_changed(self.save_mode_comboBox.currentIndex())
        if self.running:
            self.start_cancel_pushButton.setText(self.tr("取消匹配"))

    def select_path(self, path_line_edit: QLineEdit) -> None:
        def file_selected(save_path: str) -> None:
            path_line_edit.setText(os.path.normpath(save_path))
        dialog = QFileDialog(self)
        dialog.setWindowTitle(self.tr("选择文件夹"))
        dialog.setFileMode(QFileDialog.Directory)
        dialog.fileSelected.connect(file_selected)
        dialog.open()

    def save_mode_changed(self, index: int) -> None:
        match index:
            case 0:
                self.save_path_lineEdit.setEnabled(True)
                self.save_path_pushButton.setEnabled(True)
                self.save_path_pushButton.setText(self.tr("选择镜像文件夹"))
            case 1:
                self.save_path_lineEdit.setEnabled(False)
                self.save_path_pushButton.setEnabled(False)
                self.save_path_pushButton.setText(self.tr("选择文件夹"))
            case 2:
                self.save_path_lineEdit.setEnabled(True)
                self.save_path_pushButton.setEnabled(True)
                self.save_path_pushButton.setText(self.tr("选择文件夹"))

    def start_cancel_button_clicked(self) -> None:
        if self.running:
            # 取消
            if self.worker is not None:
                self.worker.stop()
                self.start_cancel_pushButton.setText(self.tr("正在取消..."))
            return

        if not os.path.exists(self.song_path_lineEdit.text()):
            MsgBox.warning(self, self.tr("警告"), self.tr("歌曲文件夹不存在！"))
            return

        lyric_langs = []
        if self.original_checkBox.isChecked():
            lyric_langs.append("orig")
        if self.translate_checkBox.isChecked():
            lyric_langs.append("ts")
        if self.romanized_checkBox.isChecked():
            lyric_langs.append("roma")
        lyrics_order = [lang for lang in cfg["lyrics_order"] if lang in lyric_langs]

        if len(lyric_langs) == 0:
            MsgBox.warning(self, self.tr("警告"), self.tr("请选择至少一种歌词语言！"))

        match self.save_mode_comboBox.currentIndex():
            case 0:
                save_mode = LocalMatchSaveMode.MIRROR
            case 1:
                save_mode = LocalMatchSaveMode.SONG
            case 2:
                save_mode = LocalMatchSaveMode.SPECIFY
            case _:
                MsgBox.critical(self, self.tr("错误"), self.tr("保存模式选择错误！"))
                return

        match self.lyrics_filename_mode_comboBox.currentIndex():
            case 0:
                flienmae_mode = LocalMatchFileNameMode.FORMAT
            case 1:
                flienmae_mode = LocalMatchFileNameMode.SONG
            case _:
                MsgBox.critical(self, self.tr("错误"), self.tr("歌词文件名错误！"))
                return

        source = []
        for source_type in [self.source_listWidget.item(i).text() for i in range(self.source_listWidget.count())]:
            if source_type == self.tr("QQ音乐") and self.qm_checkBox.isChecked():
                source.append(Source.QM)
            elif source_type == self.tr("酷狗音乐") and self.kg_checkBox.isChecked():
                source.append(Source.KG)
            elif source_type == self.tr("网易云音乐") and self.ne_checkBox.isChecked():
                source.append(Source.NE)
        if len(source) == 0:
            MsgBox.warning(self, self.tr("警告"), self.tr("请选择至少一个源！"))
            return

        self.running = True
        self.plainTextEdit.setPlainText("")
        self.start_cancel_pushButton.setText(self.tr("取消匹配"))
        for item in self.findChildren(QWidget):
            if isinstance(item, QLineEdit | QPushButton | QComboBox | QCheckBox | QListWidget) and item != self.start_cancel_pushButton:
                item.setEnabled(False)

        self.worker = LocalMatchWorker(
            {
                "song_path": self.song_path_lineEdit.text(),
                "save_path": self.save_path_lineEdit.text(),
                "min_score": self.min_score_spinBox.value(),
                "save_mode": save_mode,
                "flienmae_mode": flienmae_mode,
                "lyrics_order": lyrics_order,
                "lyrics_format": LyricsFormat(self.lyricsformat_comboBox.currentIndex()),
                "source": source,
            },
        )
        self.worker.signals.error.connect(self.worker_error)
        self.worker.signals.finished.connect(self.worker_finished)
        self.worker.signals.massage.connect(self.worker_massage)
        self.worker.signals.progress.connect(self.change_progress)
        threadpool.start(self.worker)

    def worker_massage(self, massage: str) -> None:
        self.plainTextEdit.appendPlainText(massage)

    def change_progress(self, current: int, maximum: int) -> None:
        self.progressBar.setValue(current)
        self.progressBar.setMaximum(maximum)

    def worker_finished(self) -> None:
        self.start_cancel_pushButton.setText(self.tr("开始匹配"))
        self.running = False
        for item in self.findChildren(QWidget):
            if isinstance(item, QLineEdit | QPushButton | QComboBox | QCheckBox | QListWidget):
                item.setEnabled(True)
        self.save_mode_changed(self.save_mode_comboBox.currentIndex())
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(0)

    def worker_error(self, error: str, level: int) -> None:
        if level == 0:
            self.plainTextEdit.appendPlainText(error)
        else:
            MsgBox.critical(self, self.tr("错误"), error)
            self.worker_finished()
