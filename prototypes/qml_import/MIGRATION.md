# Avaliação de migração: Qt Widgets → Qt Quick/QML

## Estado implementado

Após aprovação do usuário, a janela completa QML tornou-se o frontend padrão. O protótipo desta pasta continua isolado e demonstrativo; a aplicação usa `src/pdf_obsidian/qml/Main.qml` por `QQmlApplicationEngine`.

- Importação/progresso, preparação de lote, lista de documentos, comparação PDF/Markdown, prévia, seleção manual, restauração de imagens, formatação, links, opções, mensagens e confirmações em QML. Somente seletores de arquivo/pasta são nativos.
- `quick.py` possui documentos Python duráveis com layout de texto QtGui; não troca o texto inteiro para alternar sessões. A cena empresta esses documentos via `QQuickTextDocument.setTextDocument()`. O adaptador Widgets anterior fica disponível com `--widgets` e preserva seu layout próprio.
- `RowsModel` mantém IDs e altera papéis pontualmente; progresso de lote não altera a composição das linhas. As incorporações da prévia também têm modelo estável, inclusive para foco por teclado.
- `QQuickImageProvider` entrega somente o bitmap ativo, com URL versionada e sem abrir PDFs. A fila de renderização agrupa pedidos e descarta respostas antigas; recortes usam coordenadas normalizadas sobre a imagem, sem margens do viewport. Página, zoom, posição de leitura, divisão e seleção permanecem por sessão.
- Exportação individual assíncrona com token, sessão e revisão; edição bloqueada durante gravação e registro somente após sucesso. Conversão/recorte da janela Quick usam envelopes com token; renderização usa IDs crescentes vinculados à sessão. O lote mantém o protocolo existente.
- `Tokens.js` é a fonte única de cores/métricas, interpretada como JSON pelo Python sem `eval`. Componentes de botão, campo, checkbox e diálogo compartilham tipografia, foco e estados. Nenhuma dependência de runtime nova, QtPdf ou WebEngine.
- Provas e regressões usam somente PDFs e vaults sintéticos. A validação em desktop/GPU, leitor de tela, Obsidian, Python 3.12 e hardware de 8 GB continua pendente; não equivale à validação automatizada offscreen.

As seções abaixo registram a análise e etapas anteriores. As afirmações sobre componentes ainda Widgets referem-se àquele estágio, e não ao comando padrão atual. O histórico não altera os limites dos filtros, o funcionamento offline ou o formato de exportação.

## Diagnóstico original, anterior à extração da fachada

| Área | Evidência | Consequência |
|---|---|---|
| `gui.py` | `Window(SessionWindowMixin, QMainWindow)` constrói widgets e concentra `update_controls`, `poll`, renderização, recortes, limpeza e exportação | Não basta trocar layouts: primeiro separar coordenação de operações e apresentação |
| `appearance.py` | Paleta, QSS, `QPainter`, checkbox customizado, `AdaptiveRow` e `ElidedLabel` | Reaproveitar valores/semântica; QSS e widgets não são componentes QML e precisarão de equivalentes |
| Núcleo Python | Conversor, filtros, layout, questões, rodapés, Markdown e exportador são módulos separados | Preservar regras e formatos; nova UI deve consumir as mesmas operações |
| `worker.py` | PyMuPDF fica no processo auxiliar; comandos de renderização e lote levam identificadores | Preservar processo, cancelamento e descarte de respostas obsoletas |
| `sessions.py` / `session_ui.py` | Cada documento mantém `QTextDocument`, layout `QPlainTextDocumentLayout`, seleção, histórico, página, zoom, rolagem e auditoria | Um objeto visual QML recriado por `Loader` não pode ser o proprietário exclusivo do estado |
| `batch.py` | `BatchController(QObject)` já tem sinais, mas depende diretamente da janela, sessões e controles | Precisa de uma fachada e extração gradual; não é um serviço independente pronto para QML |
| `preview.py` / `comparison.py` | `QTextBrowser`, âncoras, alinhamentos e geometria de fragmentos para seleção de imagens | Uma simples troca por `Text { textFormat: MarkdownText }` não preserva comportamento |

Ambiente verificado: PySide6 **6.10.2**. `QtQuick`, `QtQuickControls2`, `QQuickTextDocument.setTextDocument`, `QtPdf` e módulo QML `QtQuick.Pdf` estão disponíveis nesta instalação. Isso não demonstra que o visualizador PDF ou editor já foram integrados.

## Etapa 1 implementada: coordenação Python

`src/pdf_obsidian/application.py` contém `ApplicationController(QObject)` e `WorkerRuntime`. A janela Widgets já utiliza essa fachada; o protótipo QML permanece demonstrativo.

- Runtime responsável pelo processo auxiliar, filas, cancelamento, workspaces e encerramento. A fachada centraliza polling, conversão individual, progresso, entrega de resultados/erros e falha do worker.
- Propriedades Qt notificadas e somente leitura: `busy`, `operation`, `workerAvailable`, `sourceName`, `sourcePath`, `progressCurrent` e `progressTotal`. `startConversion(QUrl)` aceita arquivos locais; `cancelConversion()` solicita cancelamento.
- Transporte de renderizações e recortes, além da chamada de exportação individual, passa pela fachada. Identificadores e protocolos do worker foram preservados.
- `BatchController` não recebe mais `Window`: recebe a fachada e `BatchHooks`, com operações de preparação do lote, snapshot e criação de sessão. A fila foi testada com um adaptador em memória, sem editor ou janela.
- O adaptador Widgets ainda conserva os documentos `QTextDocument`, seleção, histórico, geometria/coalescência do PDF, prévia e confirmações. Não há migração do editor nesta etapa. Aliases temporários de runtime/estado em `Window` mantêm esses adaptadores existentes.
- Exportação individual permanece síncrona, como antes; exportação do lote continua no worker. Uma API assíncrona individual exige contrato de snapshot e fica para etapa posterior.

A validação usa uma conversão real em subprocesso com `QCoreApplication`, sem importar `PySide6.QtWidgets`, e um componente QML mínimo com bindings para as propriedades da fachada. Objetos fornecidos ao QML precisam de propriedade/tempo de vida explícitos; o teste conserva o controlador no Python e destrói o consumidor QML antes dele.

Validação da extração: **239 testes passaram em 51,01 s**, incluindo nove casos novos de fachada; o `--check` do protótipo também passou. Consulte `VALIDATION.md` na raiz.

A etapa seguinte de importação/progresso foi concluída conforme a seção abaixo.

## Etapa 2 implementada: importação e progresso QML na aplicação principal

O comando habitual agora apresenta `ImportPage.qml` por um `ImportPanel` com `QQuickWidget`, dentro da mesma janela. A raiz visual é um `FocusScope`; cabeçalho e rodapé da página não se duplicam com o cabeçalho do editor. `Theme`, `ImportAction` e `Icon` são compartilhados com o protótipo e distribuídos junto ao pacote Python.

O painel recebe somente propriedades simples de apresentação e devolve intenções: abrir PDF, preparar lote, acessar documentos e cancelar. Seletores nativos, confirmações e a fachada existente continuam em Python. Não há outro worker nem compartilhamento de documentos Python com a cena QML. O controlador e os objetos visuais têm propriedade explícita pela hierarquia Qt.

A conversão individual mostra arquivo, progresso real (indeterminado enquanto o total é desconhecido) e cancelamento idempotente. A fachada ganhou a propriedade notificada e somente leitura `cancellationRequested`. Sucesso abre o editor atual; falha/cancelamento preserva documento, seleção, histórico e navegação anteriores. O lote continua usando o diálogo Widgets, inclusive progresso/resumo; **Documentos (N)** fica acessível no cabeçalho QML quando necessário.

A página QML não declara um segundo Ctrl+O: o atalho pertence à janela. A fonte QML acompanha explicitamente a fonte da aplicação, inclusive quando QSS impede a propagação normal de fontes Widgets. Falha no carregamento ou cena gráfica aciona uma página Widgets funcional, mantém o backend e informa a recuperação na barra de estado. A cena com falha é descarregada de forma adiada pelo Qt, interrompendo suas animações.

A renderização padrão do Qt é preservada; `QT_QUICK_BACKEND=software` é uma alternativa de execução. Capturas e testes automatizados usam software/offscreen. Isso não representa validação de GPU, Wayland/X11, leitor de tela ou desempenho em hardware real. A exportação continua manual, após revisão.

Validação final da integração: **250 testes passaram em 57,73 s**, lint QML e checagens do protótipo sem avisos; recursos QML conferidos no wheel e página carregada fora do checkout. Detalhes em `VALIDATION.md`.

Próxima etapa do plano: modelo de documentos e fluxo de lote em QML, seguido das provas técnicas de PDF e editor.

## Arquitetura de destino proposta

```text
Qt Quick/QML
  ├─ Importação, progresso e lista de documentos
  ├─ Comandos e estados visuais
  └─ PDF / editor / prévia, após provas de equivalência
          ↕ propriedades notificadas, sinais e slots
Fachada Python de aplicação (QObject)
  ├─ Modelo de documentos (QAbstractListModel, IDs estáveis)
  ├─ Sessões duráveis e comandos de edição
  ├─ Navegação, renderização, cancelamento e estado de operações
  └─ Adaptador das filas do worker
          ↕ mensagens existentes + identificadores de revisão
Processo auxiliar Python
  └─ Conversão / PyMuPDF / recortes / exportação
```

A fachada permanece no thread da interface; slots apenas validam e despacham operações. Trabalho pesado continua no processo auxiliar. QML representa estado e envia intenções; não duplica regras de conversão, filtros ou exportação em JavaScript.

A ponte mínima deste protótipo usa um sinal QML conectado a um `@Slot(str)` e um sinal Python para feedback. Uma aplicação completa deve expor propriedades com `notify`, tipos registrados ou propriedades de entrada explícitas e modelos, evitando usar `findChild` e `setProperty` como API geral de domínio. A integração Python/QML por objetos e slots é suportada oficialmente pelo [Qt for Python](https://doc.qt.io/qtforpython-6.10/tutorials/qmlintegration/qmlintegration.html).

## Riscos e mitigação

### Visualização de PDF — risco alto

Preservar inicialmente o renderizador PyMuPDF do worker. Um adaptador pode disponibilizar os bitmaps concluídos por URLs locais versionadas ou image provider, mantendo somente a página ativa. O [QQuickImageProvider](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QQuickImageProvider.html) oferece essa integração com `Image` QML; o provider deve servir imagens já disponíveis, sem converter PDFs durante uma solicitação da cena.

Os riscos do projeto são a diferença entre pixels lógicos e físicos, proporção, rotação, zoom, área visível e transformação de um arrasto em coordenadas PDF. Manter revisão por documento/página/zoom, descartar respostas antigas e não reutilizar URLs de cache sem revisão. Proteger o acesso compartilhado ao cache caso seja servido por carregamento assíncrono. Evitar referências de `QPixmap` ou widgets em threads de renderização/carregamento; transferir dados de imagem apropriados.

O módulo `QtQuick.Pdf` é uma alternativa futura, mas mudaria o renderizador e exigiria comparar geometria dos recortes, enquadramento e qualidade com o backend PyMuPDF existente. Não introduzir essa troca junto da primeira migração visual.

**Critério de avanço:** PDFs sintéticos com tamanhos e rotações diferentes; zoom manual 25–300%; ajustar à página/largura; recortes corretos; navegação rápida sem resposta obsoleta; memória estável ao alternar documentos. Medir também em Linux real e renderizador por software.

### Edição de Markdown — risco muito alto

O editor precisa continuar exibindo **código-fonte em texto simples**, inclusive HTML de alinhamento e marcadores de página. Em QML, usar `TextEdit`/`TextArea` em `PlainText`; interpretar Markdown no próprio editor alteraria a experiência.

Há uma via para reutilizar `QTextDocument`: `QQuickTextDocument.setTextDocument()` existe desde Qt 6.7, mantém a propriedade do documento no chamador e está disponível no PySide6 instalado. Isso permite investigar sessões duráveis, mas não prova a compatibilidade do `QPlainTextDocumentLayout` atual com o editor Quick. Validar o layout e a propriedade dos documentos em um experimento próprio. Referência: [QQuickTextDocument no Qt 6.10](https://doc.qt.io/qt-6.10/qquicktextdocument.html).

Preservar os comandos de `formatting.py` e sua aplicação por `QTextCursor` em uma única operação de desfazer. Não sincronizar o documento inteiro por atribuições a `text` em cada tecla ou troca de aba: isso pode destruir histórico/seleção e produzir cópias caras em documentos longos. A seleção reversa exige preservar âncora e posição separadamente; offsets Qt/JavaScript são UTF-16 e os comandos atuais usam caracteres Python. Também validar IME, clipboard, atalhos por foco e rolagem.

**Critério de avanço:** mesma matriz de Unicode, seleção reversa, formatação, HTML protegido, recortes, desfazer/refazer e troca de sessões da suíte atual, mais medição com textos grandes. Se não houver equivalência, manter o editor Widgets como opção de produção.

### Prévia e correção de imagens — risco muito alto

O Markdown exportado é a fonte de verdade. A prévia atual calcula posições de imagens em fragmentos do documento Qt e associa ocorrências, inclusive anexos compartilhados. Isso não migra automaticamente para a geometria de um `TextEdit` Quick.

Investigar uma prévia somente leitura com documento de apresentação separado e renderização/recursos locais. Preservar âncoras de página e tratamento de alinhamentos; implementar detecção de imagens por ocorrência, bordas de seleção e histórico antes de substituir a prévia atual. Não usar `WebEngine` como atalho sem avaliar custo e dependências.

**Critério de avanço:** restauração individual, remoção apenas das ocorrências selecionadas, limpar seleção ao editar, links relativos, marcadores ausentes/duplicados e anexos temporários recuperáveis.

### Comunicação QML ↔ Python — risco médio/alto

- Definir um dono único de cada estado; evitar bindings bidirecionais que realimentem comandos.
- Expor comandos curtos e assíncronos. Não bloquear a interface com leitura/conversão em slots.
- Preservar identificadores de operação, documento e revisão; ampliar o envelope de mensagens quando faltar informação, sem aceitar resultados obsoletos.
- Usar `QAbstractListModel` com papéis estáveis e atualizações pontuais; não reconstruir a lista a cada progresso, evitando a regressão de cintilação já corrigida.
- Definir propriedade e tempo de vida dos `QObject`/documentos Python; não depender da coleta de objetos visuais QML para encerrar sessões ou worker.
- Tratar seleção de arquivos com `QUrl.toLocalFile()` e normalização no Python, preservando Unicode, deduplicação e cancelamento.
- Manter confirmação de descarte, limpeza de workspaces e encerramento do worker no controlador de aplicação.

**Critério de avanço:** fila sequencial, falha parcial, cancelamento repetido, fechamento durante operação e exportação “Já salvo” conservam o comportamento atual; testes da fachada sem acesso direto a widgets.

### Desempenho, acessibilidade e implantação — risco médio

Qt Quick adiciona uma cena gráfica; menor consumo ou maior velocidade não são garantidos. Comparar memória, inicialização e fluidez em GPU integrada e backend software. Validar foco, Tab, contraste, ampliação de fonte, leitor de tela, diálogos e Wayland/X11. O pacote final deve incluir os módulos QML realmente importados.

A transição adotada mantém a janela Widgets e embute **somente importação/progresso individual** por `QQuickWidget`, com raiz `FocusScope`. O `ApplicationWindow` continua somente no protótipo demonstrativo. Isso conserva o editor existente. `QQuickWidget` tem passagem de renderização extra e desativa o render loop em thread; medir o custo, conforme a [documentação Qt 6.10](https://doc.qt.io/qt-6.10/qquickwidget.html).

Também é possível manter a importação QML em janela independente e abrir a janela Widgets para revisão, usando um único `QApplication` no processo. Não criar `QApplication` e `QGuiApplication` simultâneos nem tentar colocar um `QWidget` diretamente dentro de um `Item` QML.

## Plano incremental e critérios de decisão

| Etapa | Trabalho futuro | Condição para prosseguir |
|---|---|---|
| 0. Avaliar este estudo — concluída | Aparência e direção visual aprovadas pelo usuário | Protótipo permanece isolado |
| 1. Separar coordenação — extração inicial concluída | Fachada de processamento/runtime e adaptador de lote; UI Widgets mantida | Testes de fachada sem janela e regressões existentes |
| 2. Importação e progresso — concluída | Página QML por `QQuickWidget` na aplicação principal; backend e revisão existentes compartilhados | Seleção real, progresso, cancelamento, recuperação Widgets e regressões |
| 3. Documentos e lote | Modelo com IDs estáveis, resumo, inclusão/exclusão e revisão pelo editor existente | Lista estável, falhas parciais e sessões preservadas |
| 4. Prova técnica do PDF | Bitmaps do worker em QML, navegação, zoom e recortes | Geometria, ordem de respostas e memória equivalentes |
| 5. Prova técnica do editor | Texto simples, documento durável, comandos e histórico | Todos os critérios de edição acima; etapa bloqueante para migração completa |
| 6. Prévia e ferramentas | Âncoras, alinhamento, seleção/restauração por ocorrência e avisos | Correções e exportação equivalentes, sem ampliar filtros |
| 7. Publicação e consolidação | UI de exportação usando exportador Python; empacotamento e escolha explícita de frontend | Saídas iguais para entradas/edições iguais; aceite desktop/Obsidian e desempenho |

As provas de PDF/editor podem ser investigadas cedo em isolamento para descobrir bloqueios antes de investir em toda a interface. Não publicar o editor QML nem remover o frontend Widgets antes dos critérios de equivalência. O recuo é continuar usando o ponto de entrada Widgets com os mesmos serviços Python.

## Limites preservados

Processamento local/offline; PDFs originais intactos; sem OCR; filtro automático restrito às margens e aos limites já autorizados; remoção restante manual; histórico e anexos temporários recuperáveis; referências relativas; conversão em lote → resumo → revisão → exportação selecionada. A nova UI não deve acrescentar exportação automática nem persistência de sessão.

## Validação desta entrega

- Cena QML carregada com Qt Quick por software e sem avisos no `--check`.
- `qmllint` dos quatro arquivos QML sem diagnósticos.
- Teclado, clique, disabled e ida/volta demonstrativa QML/Python verificados em 1120 × 760 e 640 × 600 com texto ampliado em 25% no segundo caso.
- Capturas `preview.png` e `preview-compact.png` inspecionadas; conteúdo central rolável em alturas pequenas.
- Nenhuma validação de integração real de PDF/editor; nenhum ensaio de GPU, Wayland/X11, leitor de tela ou Obsidian realizado nesta entrega.
- Suíte de produção: **230 testes passaram em 49,85 s** com `.venv/bin/python -m pytest -q`.
- Comparados SHA-256 de **46 arquivos preexistentes** (fontes Python, testes, configuração e documentação principal): **nenhuma alteração**. Todos os arquivos desta entrega estão em `prototypes/qml_import/`.
