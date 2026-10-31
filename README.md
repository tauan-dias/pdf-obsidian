# PDF-Obsidian

Aplicativo desktop para Linux que converte PDFs digitais, escaneados ou mistos em notas Markdown para o Obsidian. A conversão, a revisão e a exportação acontecem localmente; o aplicativo não envia documentos a serviços externos nem modifica os PDFs originais.

## Visão geral

O PDF-Obsidian ajuda a transformar apostilas e documentos de estudo em notas editáveis, mantendo o PDF original e os anexos junto ao Markdown. A extração direta funciona sem OCR; o reconhecimento local opcional acrescenta texto, tabelas e fórmulas em documentos escaneados ou mistos.

## Funcionalidades

- Conversão de PDFs em Markdown, com imagens e recortes preservados como anexos.
- OCR local opcional para português e inglês, tabelas e fórmulas, sem substituir silenciosamente texto nativo.
- Revisão lado a lado do PDF e Markdown, com prévia, navegação por página, zoom e recortes.
- Revisão e restauração individual de imagens recorrentes filtradas nas margens; a remoção de outras imagens é manual.
- Conversão e exportação em lote, sem gravar no vault até a confirmação do usuário.
- Edição com desfazer/refazer e publicação sem sobrescrever arquivos existentes.

## Tecnologias e arquitetura

| Tecnologia | Uso |
| --- | --- |
| Python 3.12+ | Aplicação e processamento |
| PySide6 / Qt Quick / QML | Interface desktop; Widgets permanece como alternativa de recuperação |
| PyMuPDF | Leitura, extração e renderização de PDF |
| markdown-it-py | Análise de Markdown e referências a anexos |
| Docling, RapidOCR e ONNX Runtime | OCR local opcional, instalado em ambiente separado |

`src/pdf_obsidian` contém a aplicação. `worker` isola operações de PDF em processo auxiliar; `converter` prepara Markdown e anexos; `exporter` publica a saída no destino escolhido. `batch` coordena filas, e `sessions` mantém o estado editável de cada documento durante a sessão. A interface Qt Quick usa os mesmos contratos e worker da alternativa Widgets.

## Requisitos

- Linux com ambiente desktop e suporte a Qt 6.
- Python 3.12 ou superior.
- Espaço em disco adicional para OCR: a preparação baixa modelos e dependências CPU; o tamanho local descrito em [OCR.md](OCR.md) é aproximado e varia por plataforma.

## Instalação e execução

Crie e ative um ambiente virtual, instale o projeto e inicie o aplicativo:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pdf-obsidian
```

Para habilitar o OCR, prepare os modelos explicitamente:

```bash
pdf-obsidian-prepare-ocr
pdf-obsidian-prepare-ocr --verify
```

Dependências Python são instaladas durante a instalação; dependências e modelos de OCR são obtidos somente durante a preparação. Depois de preparados, o OCR e a aplicação funcionam localmente. A primeira página que exige OCR pode demorar mais enquanto os modelos são carregados. Consulte [OCR.md](OCR.md) para instalação offline, recursos, cancelamento e limitações.

## Uso

1. Abra um PDF sem senha. Escolha se deseja OCR automático na importação.
2. Confira o Markdown e os avisos comparando-os com o PDF. Revise **Imagens filtradas** e restaure individualmente qualquer figura útil.
3. Edite a nota ou selecione imagens adicionais para remoção manual na prévia. As alterações podem ser desfeitas e refeitas.
4. Selecione **Salvar no vault…** ou converta vários documentos e use **Exportar selecionados**. Escolher uma pasta existente confirma a exportação.

A saída contém uma nota Markdown, `original.pdf`, `assets/` e `conversao.json`, com links relativos entre os arquivos. Colisões recebem sufixos; arquivos existentes não são sobrescritos. O trabalho temporário e o histórico de edição permanecem na sessão e são descartados ao fechar após confirmação.

Atalhos principais: `Ctrl+O` abre um PDF, `Ctrl+S` salva o documento ativo e `Alt+←/→` navega entre páginas. A opção `--widgets` inicia a interface alternativa:

```bash
pdf-obsidian --widgets
```

## Testes e validação

Com o extra de desenvolvimento instalado:

```bash
.venv/bin/python -m pytest -q
```

Os testes criam PDFs sintéticos e não dependem de documentos pessoais. Ferramentas de revisão visual e benchmarks também geram suas próprias entradas. O relatório [PUBLICATION_AUDIT.md](PUBLICATION_AUDIT.md) registra as verificações desta preparação e as limitações pendentes.

## Limitações conhecidas

- A reconstrução de títulos, listas, figuras e ordem de leitura usa heurísticas; documentos com múltiplas colunas precisam de revisão.
- OCR pode errar texto, tabelas ou fórmulas. As imagens originais são mantidas para comparação; confira o resultado antes de exportar.
- A prévia Qt pode exibir LaTeX como código. Confira a apresentação final no Obsidian.
- Compatibilidade visual com Obsidian desktop e Android, GPU, leitores de tela e diferentes ambientes Linux ainda depende de validação manual.
- O aplicativo não implementa sincronização com vaults.

## Documentação adicional

- [OCR.md](OCR.md): preparação, funcionamento offline, consumo e limites do OCR.
- [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md): componentes e recursos visuais.
- [AUDIT.md](AUDIT.md): auditoria funcional e recomendações de produto.
- [PUBLICATION_AUDIT.md](PUBLICATION_AUDIT.md): verificações desta preparação e pendências para publicação.

## Contribuições e licença

O projeto está licenciado sob **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**. Leia [LICENSE](LICENSE). Fontes Geist, ícones Lucide e recursos usados pelo OCR mantêm avisos e licenças próprios, incluídos junto aos respectivos arquivos. As dependências Python também mantêm seus termos; consulte os metadados de cada distribuição antes de redistribuir uma instalação empacotada.

Ainda não há política formal de contribuição ou suporte de segurança. Para propor uma alteração, abra uma issue ou pull request com contexto, passos para reproduzir e testes pertinentes. Não inclua PDFs privados, vaults reais, credenciais ou dados pessoais em issues e testes.
