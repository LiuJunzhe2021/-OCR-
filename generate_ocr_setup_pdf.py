import sys
from pathlib import Path

ROOT = Path(r"C:\Users\lenovo\Desktop\OCR total")
sys.path.insert(0, str(ROOT / ".pdfdeps"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(TTFont("CN", r"C:\Windows\Fonts\simhei.ttf"))

out = ROOT / "OCR项目环境配置与运行指南.pdf"
styles = getSampleStyleSheet()
title = ParagraphStyle("TitleCN", fontName="CN", fontSize=21, leading=28, textColor=colors.HexColor("#123a63"), alignment=TA_CENTER, spaceAfter=10)
sub = ParagraphStyle("SubCN", fontName="CN", fontSize=9, leading=14, textColor=colors.HexColor("#566573"), alignment=TA_CENTER, spaceAfter=15)
h1 = ParagraphStyle("H1CN", fontName="CN", fontSize=14, leading=20, textColor=colors.HexColor("#174e7a"), spaceBefore=12, spaceAfter=6)
h2 = ParagraphStyle("H2CN", fontName="CN", fontSize=11, leading=16, textColor=colors.HexColor("#245f89"), spaceBefore=8, spaceAfter=4)
body = ParagraphStyle("BodyCN", fontName="CN", fontSize=9.5, leading=15, textColor=colors.HexColor("#1f2937"), spaceAfter=5)
code = ParagraphStyle("CodeCN", fontName="CN", fontSize=8.2, leading=13, leftIndent=7, rightIndent=5, borderColor=colors.HexColor("#3f7daa"), borderWidth=0, borderPadding=6, backColor=colors.HexColor("#f1f5f8"), spaceAfter=7)

story = [Paragraph("OCR 项目环境配置与运行指南", title), Paragraph(r"适用目录：C:\Users\lenovo\Desktop\OCR total　｜　Windows 11", sub)]

def H(text, level=1): story.append(Paragraph(text, h1 if level == 1 else h2))
def P(text): story.append(Paragraph(text, body))
def C(text): story.append(Paragraph(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>"), code))

H("1. 项目结构与端口")
data = [["组件", "目录", "技术与版本", "端口"], ["Python OCR 服务", "ocr-python-service", "Python 3.10/3.11、Flask、PaddleOCR", "5001"], ["Java 业务后端", "ocr-business-server", "JDK 17、Maven 3.9+、Spring Boot", "8080"], ["Web 前端", "ocr-web", "Node.js LTS、npm、Vue 3、Vite", "5173"]]
t = Table(data, colWidths=[34*mm, 38*mm, 80*mm, 16*mm])
t.setStyle(TableStyle([("FONT", (0,0), (-1,-1), "CN", 8.5), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eaf2f8")), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#aebdcc")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
story += [t, Spacer(1, 7)]
P("正确启动顺序：Python OCR 服务 → Java 后端 → Vue 前端。三个服务分别占用一个终端窗口，运行期间不要关闭。")

H("2. Java 17 配置")
C(r"JAVA_HOME=C:\Users\lenovo\AppData\Local\Programs\Eclipse Adoptium\jdk-17.0.20.8-hotspot\nPath 新增：%JAVA_HOME%\bin")
C("where java\njava -version")
P("应优先找到 Adoptium 路径并显示 Java 17。若仍找到 Java 8，检查系统 Path 中是否残留 Oracle 的 java8path 或 javapath。")

H("3. Maven 配置")
C(r"MAVEN_HOME=C:\Users\lenovo\Desktop\apache-maven-3.9.16\nPath 新增：C:\Users\lenovo\Desktop\apache-maven-3.9.16\bin")
C("echo %MAVEN_HOME%\nwhere mvn\nmvn -version")
P("结果应包含 Maven 3.9.16 和 Java 17。在 VS Code 中修改环境变量后，需要彻底关闭所有 Code.exe 再重新打开。")

story.append(PageBreak())
H("4. Python OCR 环境")
P("推荐 Python 3.10 或 3.11（64 位），不要使用 Python 3.13。当前虚拟环境名为 jrrg。")
H("激活环境并安装依赖", 2)
C('conda activate jrrg\npython --version\ncd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-python-service"\npython -m pip install --upgrade pip\npython -m pip install -r requirements.txt')
P("如果不在 Python 服务目录，可对 requirements.txt 使用完整路径。")
H("创建 .env 配置", 2)
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-python-service"\ncopy .env.example .env')
P("没有安装 Tesseract 时：")
C("TESSERACT_CMD=\nVERIFY_WITH_TESSERACT=false")
P("已经安装 Tesseract 及中英文语言包时：")
C(r"TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe\nTESSERACT_LANG=chi_sim+eng\nVERIFY_WITH_TESSERACT=true")
H("Windows CPU 的 oneDNN 兼容处理", 2)
P("出现 ConvertPirAttribute2RuntimeAttribute not support 时，在 .env 增加：")
C("FLAGS_use_mkldnn=0")
P("如果仍报错，在 ocr_service\\ocr_engine.py 创建 PaddleOCR 的参数中加入：")
C("enable_mkldnn=False,")
P("RequestsDependencyWarning、没有 ccache、模型已缓存等通常不是致命错误；真正原因应查看 Traceback 最后几行。")
H("启动与健康检查", 2)
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-python-service"\nconda activate jrrg\npython app.py')
C("curl http://127.0.0.1:5001/health")
P("返回内容中的 ready 应为 true。")

H("5. 启动 Java 后端")
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-business-server"\nmvn spring-boot:run')
P("出现 Tomcat started on port 8080 和 Started OcrBusinessApplication 即成功。终端不返回提示符是正常现象；Ctrl+C 用于停止。")

story.append(PageBreak())
H("6. Node.js 与前端")
P("安装 Node.js LTS（Node.js 22 或更新的兼容 LTS）；npm 会随 Node.js 一起安装：")
C("winget install --id OpenJS.NodeJS.LTS -e --source winget")
C("node --version\nnpm --version")
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-web"\nnpm ci\nnpm run dev')
P("浏览器访问：http://localhost:5173")

H("7. 每次运行项目的快捷流程")
H("终端 1：Python OCR 服务", 2)
C('conda activate jrrg\ncd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-python-service"\npython app.py')
H("终端 2：Java 后端", 2)
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-business-server"\nmvn spring-boot:run')
H("终端 3：Vue 前端", 2)
C('cd /d "C:\\Users\\lenovo\\Desktop\\OCR total\\ocr-web"\nnpm run dev')

H("8. 常见故障")
for item in ["mvn 找不到：检查 MAVEN_HOME 和用户 Path，并彻底重启 VS Code。", "npm 找不到：安装 Node.js LTS，重启终端后检查 node 和 npm 版本。", "requirements.txt 找不到：进入 ocr-python-service，或使用完整路径。", "前端 HTTP 500：查看 Python 服务窗口的完整 Traceback；Java 通常只是转发错误。", "端口占用：检查 5001、8080、5173 是否已有旧服务运行。", "旧版 .doc 无法解析：安装 LibreOffice 并加入 Path；.docx 不需要。"]:
    P("• " + item)
P("补充：项目默认使用本地 H2 数据库，无需安装 MySQL；上传文件默认限制 50 MB；首次 OCR 可能下载模型，需要联网且耗时较长。")

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("CN", 8); canvas.setFillColor(colors.grey); canvas.drawCentredString(A4[0]/2, 9*mm, f"OCR total 项目环境指南　｜　第 {doc.page} 页"); canvas.restoreState()

SimpleDocTemplate(str(out), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=14*mm, bottomMargin=16*mm, title="OCR 项目环境配置与运行指南", author="Codex").build(story, onFirstPage=footer, onLaterPages=footer)
print(out)
