# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'janela_login.ui'
#
# Created by: PyQt5 UI code generator 5.15.10
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_janela_login(object):
    def setupUi(self, janela_login):
        janela_login.setObjectName("janela_login")
        janela_login.resize(682, 376)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/icons/conta.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        janela_login.setWindowIcon(icon)
        janela_login.setDocumentMode(False)
        self.centralwidget = QtWidgets.QWidget(janela_login)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(8, 16, 689, 321))
        self.label.setObjectName("label")
        self.barra_progresso = QtWidgets.QProgressBar(self.centralwidget)
        self.barra_progresso.setGeometry(QtCore.QRect(16, 327, 649, 33))
        self.barra_progresso.setStyleSheet("QProgressBar{\n"
"    border-radius: 14px;\n"
"    background-color:rgb(223, 201, 245)\n"
"}\n"
"\n"
"QProgressBar::chunk{\n"
"    border-radius: 14px;\n"
"    background-color:rgb(126, 14, 237)\n"
"\n"
"}\n"
"")
        self.barra_progresso.setProperty("value", 0)
        self.barra_progresso.setTextVisible(False)
        self.barra_progresso.setFormat("")
        self.barra_progresso.setObjectName("barra_progresso")
        janela_login.setCentralWidget(self.centralwidget)

        self.retranslateUi(janela_login)
        QtCore.QMetaObject.connectSlotsByName(janela_login)

    def retranslateUi(self, janela_login):
        _translate = QtCore.QCoreApplication.translate
        janela_login.setWindowTitle(_translate("janela_login", "MainWindow"))
        self.label.setText(_translate("janela_login", "<html><head/><body><p><img src=\":/icons/d0267b4d9d1d40dab9ec5eac4fedc3f8.png\"/></p></body></html>"))
import icons_rc


