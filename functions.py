import sys
from PyQt5 import QtWidgets, QtCore
from Interface import Ui_janela_principal
from janela_lancar_manual import Ui_janela_lancar_manual
from janela_login import Ui_janela_login
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem, QPushButton, QWidget, QHBoxLayout
from PyQt5.QtCore import QObject, QTimer, QSize, QDateTime, QDate
import requests
import xml.etree.ElementTree as ET
import locale
from firebase_admin import db
from credentials import *
import datetime

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')  # Define formatação brasileira
ref = db.reference("/")



class Funcoes(QObject):
    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.janela = janela  # Adiciona o widget principal (QMainWindow ou QDialog)


    def importar_xml(self):
        """Abre um diálogo para selecionar arquivos XML e processa os dados."""
        retencao = 'NAO'
        arquivos, _ = QFileDialog.getOpenFileNames(
            None, "Selecionar Arquivos XML", "", "Arquivos XML (*.xml)"
        )
        if not arquivos:
            return

        contador_notas_importadas = 0
        valor_total = 0.0
        valor_total_produtos = 0.0

        for arquivo in arquivos:
            try:
                tree = ET.parse(arquivo)
                root = tree.getroot()

                notas_nfdok = root.findall(".//nfdok")
                if notas_nfdok:
                    # Para cada <nfdok>, buscar os elementos <NOTA_FISCAL>
                    for nfdok in notas_nfdok:
                        notas = nfdok.findall(".//NOTA_FISCAL")
                        for nota in notas:
                            situacao = (nota.findtext("SituacaoNf") or "Normal").strip().upper()
                            if situacao != "NORMAL":
                                continue  

                            cliente = (nota.findtext("ClienteNomeRazaoSocial") or "").strip().upper()
                            cnpj = self.formatar_cnpj(nota.findtext("ClienteCNPJCPF") or "")

                            data_raw = (nota.findtext("DataEmissao") or "").strip()
                            data = self.formatar_data(data_raw.split(" ")[0]) if data_raw else ""

                            tipo = (nota.findtext("DescricaoServico") or "PRODUTO").strip().upper()
                            numero = (nota.findtext("NumeroNota") or "").strip().upper()

                            cidade = (nota.findtext("ClienteCidade") or "").strip().upper()
                            uf = (nota.findtext("ClienteUF") or "").strip().upper()
                            municipio = f"{cidade}-{uf}" if cidade and uf else (cidade or uf)

                            valor_str = (nota.findtext("ValorTotalNota") or "0").strip()
                            valor = self.formatar_moeda(valor_str)

                            # Se a nota não existir, adiciona na tabela
                            if not self.verificar_nota_existente(cliente, tipo, numero):
                                self.adicionar_linha_tabela(cliente, cnpj, data, tipo, numero, municipio, valor,retencao)
                                valor_total += valor
                                if tipo.upper() == "PRODUTO":
                                    valor_total_produtos += valor
                                contador_notas_importadas += 1
                else:
                    # ESTRUTURA ÚNICA (NF-e)
                    ns = {}
                    if root.tag.startswith("{"):
                        ns_uri = root.tag.split("}")[0].strip("{")
                        ns = {'nfe': ns_uri}

                    dest = root.find(".//nfe:dest", ns)
                    if dest is not None:
                        cliente = (dest.findtext("nfe:xNome", default="", namespaces=ns) or "").strip().upper()
                        cnpj = self.formatar_cnpj(dest.findtext("nfe:CNPJ", default="", namespaces=ns) or "")
                        cidade = (dest.findtext(".//nfe:xMun", default="", namespaces=ns) or "").strip().upper()
                        uf = (dest.findtext(".//nfe:UF", default="", namespaces=ns) or "").strip().upper()
                        municipio = f"{cidade}-{uf}" if cidade and uf else (cidade or uf)
                    else:
                        cliente = (root.findtext("xNome") or "").strip().upper()
                        cnpj = self.formatar_cnpj(root.findtext("CNPJ") or "")
                        municipio = ""

                    data_raw = (root.findtext(".//nfe:dhEmi", default="", namespaces=ns) or "").strip()
                    data = self.formatar_data(data_raw.split("T")[0]) if data_raw else ""

                    retencao = "NAO"
                    tipo = "PRODUTO"  # Define default
                    numero = (root.findtext(".//nfe:nNF", default="", namespaces=ns) or "").strip().upper()
                    valor_str = (root.findtext(".//nfe:vOrig", default="0", namespaces=ns) or "0").strip()
                    valor = self.formatar_moeda(valor_str)

                    if not self.verificar_nota_existente(cliente, tipo, numero):
                        self.adicionar_linha_tabela(cliente, cnpj, data, tipo, numero, municipio, retencao, valor, retencao)
                        valor_total += valor
                        if tipo.upper() == "PRODUTO":
                            valor_total_produtos += valor
                        contador_notas_importadas += 1

            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Erro ao processar {arquivo}:\n{str(e)}")

        
        self.atualizar_totais(valor_total_produtos,0)

    def editar_registro(self):
        """Permite editar o valor e reajusta a soma total"""
        button = self.sender() 
        if button:
            tabela = self.ui.tabela_lancamentos
            for linha in range(tabela.rowCount()):
                container = tabela.cellWidget(linha, 8)  
                if container:
                    layout = container.layout()
                    if layout and layout.indexOf(button) != -1: 
                        item_valor = tabela.item(linha, 6)  

                        if item_valor:
                            valor_inicial = self.formatar_moeda(item_valor.text())
                            novo_valor, ok = QtWidgets.QInputDialog.getDouble(
                                None, "Editar Valor", "Digite o novo valor:", valor_inicial, 0, 9999999, 2
                            )

                            if ok and novo_valor != valor_inicial:
                                item_valor.setText(f"R$ {novo_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                                self.recalcular_total()
                        break  


    def excluir_registro(self):
        """Remove a linha correspondente e refaz a soma do total"""
        button = self.sender()  # Agora funciona pois Funcoes herda de QObject
        if button:
            # Encontra o widget container dos botões
            container = button.parent()
            if container:
                # Encontra a linha correspondente na tabela
                tabela = self.ui.tabela_lancamentos
                linha = tabela.indexAt(container.pos()).row()
                
                if linha >= 0:
                    tabela.removeRow(linha)
                    self.recalcular_total()
                    if tabela.rowCount() == 0:
                        self.atualizar_totais(0, 0)  # Passando 0 para serviços também caso a tabela fique vazia

    def encontrar_linha_por_widget(self, widget):
        """Encontra a linha correspondente ao widget na tabela"""
        for linha in range(self.ui.tabela_lancamentos.rowCount()):
            if self.ui.tabela_lancamentos.cellWidget(linha, 7) == widget:
                return linha
        return -1

    def verificar_nota_existente(self, cliente, tipo, numero):
        """Verifica se a nota já existe na tabela comparando CLIENTE, TIPO e NÚMERO."""
        tabela = self.ui.tabela_lancamentos
        for linha in range(tabela.rowCount()):
            item_cliente = tabela.item(linha, 0)
            item_tipo = tabela.item(linha, 3)
            item_numero = tabela.item(linha, 4)
            if (item_cliente is not None and item_cliente.text() == cliente and
                item_tipo is not None and item_tipo.text() == tipo and
                item_numero is not None and item_numero.text() == numero):
                return True
        return False

    def adicionar_linha_tabela(self, cliente, cnpj, data, tipo, numero, municipio, valor, retencao):
        """Insere uma nova linha na tabela"""
        tabela = self.ui.tabela_lancamentos
        linha = tabela.rowCount()
        tabela.insertRow(linha)

        valor_formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        dados = [cliente, cnpj, data, tipo, numero, municipio, valor_formatado, retencao]

        for coluna, valor_texto in enumerate(dados):
            tabela.setItem(linha, coluna, QTableWidgetItem(valor_texto))

        btn_editar = QPushButton("🖋️")
        btn_excluir = QPushButton("❌")

        btn_editar.setStyleSheet("background-color: transparent; border: none;")
        btn_excluir.setStyleSheet("background-color: transparent; border: none;")

        btn_editar.setCursor(QtCore.Qt.PointingHandCursor)
        btn_excluir.setCursor(QtCore.Qt.PointingHandCursor)

        btn_editar.setFixedSize(30, 30)
        btn_excluir.setFixedSize(30, 30)

        btn_editar.clicked.connect(self.editar_registro)
        btn_excluir.clicked.connect(self.excluir_registro)

        h_layout = QHBoxLayout()
        h_layout.addWidget(btn_editar)
        h_layout.addWidget(btn_excluir)
        h_layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setLayout(h_layout)
        tabela.setCellWidget(linha, 8, container)

    def atualizar_totais(self, valor_total_produtos_novo, valor_total_servicos_novo):
        """
        Atualiza os widgets que exibem os totais de notas do tipo "PRODUTO" e "SERVIÇO".
        Acumula os valores novos ao que já estiver no widget e exibe como moeda.
        """
        # Atualiza o total de produtos
        texto_atual_produtos = self.ui.total_notas_produtos.text().strip()
        atual_produtos = self.formatar_moeda(texto_atual_produtos) if texto_atual_produtos else 0.0
        novo_total_produtos = atual_produtos + valor_total_produtos_novo
        
        # Formata o total de produtos como moeda
        total_produtos_formatado = f"R$ {novo_total_produtos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.ui.total_notas_produtos.setText(total_produtos_formatado)  # Exibe no formato de moeda

        # Atualiza o total de serviços
        texto_atual_servicos = self.ui.total_notas_servico.text().strip()
        atual_servicos = self.formatar_moeda(texto_atual_servicos) if texto_atual_servicos else 0.0
        novo_total_servicos = atual_servicos + valor_total_servicos_novo
        
        # Formata o total de serviços como moeda
        total_servicos_formatado = f"R$ {novo_total_servicos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.ui.total_notas_servico.setText(total_servicos_formatado)  # Exibe no formato de moeda

    def recalcular_total(self):
        """Recalcula os totais com base nas linhas existentes, diferenciando Produto e Serviço"""
        tabela = self.ui.tabela_lancamentos
        total_produtos = 0.0
        total_servicos = 0.0

        for linha in range(tabela.rowCount()):
            item_tipo = tabela.item(linha, 3)  
            item_valor = tabela.item(linha, 6)  

            if item_tipo is not None and item_valor is not None:  
                tipo_texto = item_tipo.text().strip() if item_tipo.text() else ""
                valor_texto = item_valor.text().strip() if item_valor.text() else ""

                try:
                    if valor_texto:  
                        valor = float(valor_texto.replace("R$", "").replace(".", "").replace(",", "."))

                        if tipo_texto.upper() == "PRODUTO":
                            total_produtos += valor
                        elif tipo_texto.upper() == "SERVIÇO":
                            total_servicos += valor
                except ValueError:
                    continue  

        total_produtos_formatado = f"R$ {total_produtos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.ui.total_notas_produtos.setText(total_produtos_formatado)

        total_servicos_formatado = f"R$ {total_servicos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.ui.total_notas_servico.setText(total_servicos_formatado)

    def formatar_data(self, data):
        """Converte data de YYYY-MM-DD para DD/MM/YYYY."""
        partes = data.split("-")
        return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 else data

    def formatar_moeda(self, valor):
        """
        Converte uma string de valor monetário para float.
        Se houver vírgula, assume que o separador decimal é a vírgula (ex.: "2.013,61");
        caso contrário, assume que o separador decimal é o ponto (ex.: "2013.61").
        """
        try:
            valor = valor.replace("R$", "").strip()
            if "," in valor:
                valor = valor.replace(".", "").replace(",", ".")
            return float(valor)
        except ValueError:
            return 0.0

    def formatar_cnpj(self, cnpj):
        """Formata o CNPJ para o padrão 00.000.000/0000-00."""
        cnpj = "".join(filter(str.isdigit, cnpj))
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}" if len(cnpj) == 14 else cnpj

    def carregar_dados_cliente(self, event):
        ref = db.reference("/Clientes")
        clientes = ref.get() 
        
        ui.campo_cliente_lancamento.clear()
        ui.campo_cliente_lancamento_2.clear()

        ui.campo_cliente_lancamento.addItem("")  
        ui.campo_cliente_lancamento_2.addItem("")

        for key in clientes:
            ui.campo_cliente_lancamento.addItem(key)
            ui.campo_cliente_lancamento_2.addItem(key)
           
    def carregar_informacoes_cliente(self):
        cliente = ui.campo_cliente_lancamento.currentText()
        if cliente:
            dados = db.reference(f"/Clientes/{cliente}/")
            dados_cliente = dados.get()

            try:
                ui.campo_id.setText(dados_cliente['id'])
                ui.campo_cnpj_cliente.setText(self.formatar_cnpj(dados_cliente['cnpj']))
                ui.campo_ie.setText(dados_cliente['ie'])
            except:
                pass

    def abrir_janela_lancar_manual(self):
        janela_manual.show()
        pass

    def buscar_dados_cnpj(self,cnpj):
        try:
            url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
            resposta = requests.get(url, timeout=10)
            data = resposta.json()
            mun = data['municipio']
            uf = data['uf']
            nome = data['nome']
        except:
            mun = '--'
            uf = '--'
            nome = '--'
        pass

        municipio = f'{mun} - {uf}'  # Pega o municipio e UF pela API da Receita
        cliente = nome

        ui_2.campo_municipio_nota_manual.setText(municipio)
        ui_2.campo_razao_social_manual.setText(cliente)

    def importar_manual(self):
        # Obtém os dados dos campos da janela de lançamento manual
        cnpj = ''.join(filter(str.isdigit, ui_2.campo_cnpj_manual.text()))

        

        cliente = ui_2.campo_razao_social_manual.text()
        municipio = ui_2.campo_municipio_nota_manual.text()
        cnpj = ui_2.campo_cnpj_manual.text()
        data = ui_2.campo_data_manual.text()
        tipo = ui_2.campo_tipo_nota_manual.currentText()
        numero = ui_2.campo_numero_nota_manual.text()

        valor = ui_2.campo_valor_nota_manual.text().replace("R$", "").replace(",", ".") 
        retencao = ui_2.campo_retencao_nota_manual.currentText()

        try:
            valor = float(valor)  
            valor_formatado = self.formatar_moeda(f'R${valor}')

            # Adiciona a linha na tabela com os dados corretos
            self.adicionar_linha_tabela(cliente, cnpj, data, tipo, numero, municipio, valor_formatado, retencao)

            if tipo == "PRODUTO":
                self.atualizar_totais(valor, 0.0)  
            elif tipo == "SERVIÇO":
                self.atualizar_totais(0.0, valor)  

            # Limpa os campos após o lançamento
            ui_2.campo_cnpj_manual.clear()
            ui_2.campo_tipo_nota_manual.setCurrentIndex(0)
            ui_2.campo_numero_nota_manual.clear()
            ui_2.campo_valor_nota_manual.clear()
            ui_2.campo_razao_social_manual.clear()
            ui_2.campo_municipio_nota_manual.clear()
            ui_2.campo_retencao_nota_manual.setCurrentText('NAO')
            ui_2.campo_cnpj_manual.setFocus()

        except ValueError:

            QMessageBox.warning(self, "Erro", "Por favor, insira um valor válido para a nota.")

    def evento_ao_fechar(self, event):
        """Fecha a janela secundária ao fechar a principal"""
        if janela_manual.isVisible():
            janela_manual.close()  

        event.accept()  

    def iniciar_splash(self):
        """Atualiza a barra de progresso suavemente e fecha a splash após 5 segundos"""
        self.progresso = 0.0  

        def atualizar_barra():
            self.progresso += 0.1 

            if self.progresso >= 100:
                self.timer.stop()  
                janela_login.close()  
                janela.show()  
            else:
                ui_login.barra_progresso.setValue(int(self.progresso)) 

        self.timer = QTimer()
        self.timer.timeout.connect(atualizar_barra)
        self.timer.start(2)  

    def iso_para_data(self, data_str):
        """
        Converte uma string no formato "MM/yyyy" para um QDateTime.
        Como só temos mês e ano, definimos o dia como 1 e a hora como 00:00.
        """
        dt = datetime.datetime.strptime(data_str, "%m/%Y")
        # Cria um QDateTime a partir do datetime
        qdt = QDateTime(dt)
        return qdt

    def data_para_iso(self, data):
        """
        Converte um objeto QDate ou QDateTime para uma string no formato "MM/yyyy".
        """
        if isinstance(data, QDate):
            # Se for QDate, usa o método toString para formatar
            return data.toString("MM/yyyy")
        elif isinstance(data, QDateTime):
            # Se for QDateTime, converte para datetime do Python e formata
            dt = data.toPyDateTime()
            return dt.strftime("%m/%Y")
        else:
            # Se for um objeto datetime do Python, formata diretamente
            return data.strftime("%m/%Y")

    def salvar_dados_xml(self):
        usuario = self.ui.campo_cliente_lancamento.currentText()

        lancamentos_ref = db.reference(f"/Lancamentos/{usuario}")
        
        qdate = self.ui.mes_lancamento.date()  
        ano_str = str(qdate.year())
        mes_str = f"{qdate.month():02d}"  
        

        ano_ref = lancamentos_ref.child(ano_str)
        mes_ref = ano_ref.child(mes_str)
        
        table = self.ui.tabela_lancamentos
        num_rows = table.rowCount()
        
        for row in range(num_rows):

            cliente    = table.item(row, 0).text() if table.item(row, 0) else ""
            cnpj       = table.item(row, 1).text() if table.item(row, 1) else ""
            data_nf    = table.item(row, 2).text() if table.item(row, 2) else ""  
            tipo       = table.item(row, 3).text() if table.item(row, 3) else ""
            numero     = table.item(row, 4).text() if table.item(row, 4) else ""
            municipio  = table.item(row, 5).text() if table.item(row, 5) else ""
            valor      = table.item(row, 6).text() if table.item(row, 6) else ""
            retencao   = table.item(row, 7).text() if table.item(row, 7) else ""
            

            raw_key = f"{tipo}_{numero}_{cnpj}"

            nf_key = raw_key.replace('.', '').replace('/', '').replace('$', '').replace('#', '').replace('[', '').replace(']', '')

            try:
                data_nf_obj = datetime.datetime.strptime(data_nf, "%d/%m/%Y")  
            except ValueError:
                data_nf_obj = data_nf  

            data = self.data_para_iso_nota(data_nf_obj)

            nf_data = {
                "cliente": cliente,
                "cnpj": cnpj,
                "data": data,  
                "tipo": tipo,
                "numero": numero,
                "municipio": municipio,
                "valor": valor,
                "retencao": retencao
            }
            
            mes_ref.child("nf").child(nf_key).set(nf_data)
        
        mes_ref.child("obrigacoes").set({})
        
        QMessageBox.information(None, "Salvar XML", "Dados salvos com sucesso!")


    def iso_para_data_nota(self,data):
        dt = datetime.datetime.strptime(data, "%Y-%m-%dT%H:%M:%SZ")
        qdt = QDateTime(dt)
        return qdt

    def data_para_iso_nota(self, data):
        if isinstance(data, QDateTime):  
            dt = data.toPyDateTime()
        elif isinstance(data, datetime.datetime):  
            dt = data
        else:  
            dt = datetime.datetime.strptime(data, "%d/%m/%Y")
        
        iso_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return iso_str
        





# Configuração da aplicação
app = QtWidgets.QApplication(sys.argv)

# Cria as janelas principais e de lançamento manual
janela = QtWidgets.QMainWindow()
janela_manual = QtWidgets.QMainWindow()
janela_login = QtWidgets.QMainWindow()

# Cria as interfaces
ui = Ui_janela_principal()
ui_2 = Ui_janela_lancar_manual()
ui_login = Ui_janela_login()


ui.setupUi(janela)
ui_2.setupUi(janela_manual)
ui_login.setupUi(janela_login)

funcoes_app = Funcoes(ui)

janela.setWindowTitle("Gerenciador")
janela_login.setWindowTitle("Gerenciador")
janela_manual.setWindowTitle("Lançamento manual")

janela_login.setWindowFlags(QtCore.Qt.FramelessWindowHint)

ui_2.campo_cnpj_manual.editingFinished.connect(lambda: funcoes_app.buscar_dados_cnpj(ui_2.campo_cnpj_manual.text()))
ui_2.campo_cnpj_manual.editingFinished.connect(lambda: ui_2.campo_cnpj_manual.setText(funcoes_app.formatar_cnpj(ui_2.campo_cnpj_manual.text())))


ui.btn_salvar.clicked.connect(lambda: funcoes_app.salvar_dados_xml())
ui_2.campo_cnpj_manual.editingFinished.connect(lambda: ui_2.campo_cnpj_manual.setText(funcoes_app.formatar_cnpj(ui_2.campo_cnpj_manual.text())))
ui_2.btn_importar_manual.clicked.connect(lambda: funcoes_app.importar_manual())
ui.btn_importar_xml.clicked.connect(lambda: funcoes_app.importar_xml())
ui.btn_lancar_manual.clicked.connect(lambda: funcoes_app.abrir_janela_lancar_manual())
ui.campo_cliente_lancamento.currentIndexChanged.connect(lambda: funcoes_app.carregar_informacoes_cliente())

ui.btn_importar_xml.setIconSize(QSize(64, 64))
janela.showEvent = funcoes_app.carregar_dados_cliente
janela.closeEvent = funcoes_app.evento_ao_fechar

janela.setFixedSize(1126, 803)
janela_login.show()
funcoes_app.iniciar_splash() 

sys.exit(app.exec_())