# PDF-Obsidian

Aplicação desktop Linux para converter PDFs digitais, escaneados e mistos em Markdown para Obsidian. Processamento local na CPU, offline, sem serviços externos ou telemetria. A interface Qt Quick utiliza o renderizador disponível no sistema, com alternativa por software.

## Instalação e execução

Requer Python 3.12 ou superior e um ambiente desktop Linux com suporte ao Qt 6.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pdf-obsidian-prepare-ocr
pdf-obsidian
```

Se `venv` ou `pip` não estiver disponível, instale o pacote correspondente à distribuição Linux. As dependências e os modelos de reconhecimento são baixados durante a instalação/preparação explícita; a execução é offline. O OCR ocupa espaço adicional e sua primeira página pode demorar mais para carregar os modelos.

## Fluxo

1. Abra um PDF sem senha. Na importação, mantenha **OCR automático** ativado para reconhecer texto, tabelas e fórmulas quando necessário; a interface informa se os modelos estão preparados.
2. Confira os avisos e compare o editor ou a prévia com as páginas originais. Se aparecer **Imagens filtradas (N)**, revise as miniaturas e restaure qualquer figura útil omitida.
3. Corrija o Markdown. Ative **Recortar** e arraste uma região do PDF para inserir um recorte na posição do cursor do editor. Remova manualmente o texto que o recorte substituir, se necessário.
4. Opcionalmente, selecione imagens manualmente na **Prévia** para removê-las. Para omitir os comentários de página da nota final, abra o menu **⋯** ao lado de **Salvar no vault…** e marque **Remover marcações de página na exportação**.
5. Selecione **Salvar no vault** e indique uma pasta existente. Isso confirma a exportação.
6. Transfira ou sincronize a pasta inteira para o Android usando o mecanismo de sua preferência.

A saída fica em `Importados/<nome>/`, com uma nota Markdown, `original.pdf`, `assets/` e `conversao.json`. Os links são relativos. Pastas já existentes recebem sufixo numérico. O PDF original nunca é modificado. Cabeçalhos e rodapés removidos são registrados no relatório. Ao fechar sem salvar, o trabalho temporário é descartado, após confirmação.

Ao salvar novamente no mesmo vault durante a sessão, se o conteúdo e as opções exportáveis forem iguais e todos os arquivos publicados mantiverem tamanho e SHA-256, o aplicativo informa **Documento já salvo** e mostra o destino existente, sem criar outra cópia. Se a publicação estiver incompleta ou tiver sido editada no Obsidian, uma nova cópia é criada e a anterior é preservada. Arquivos extras adicionados pelo usuário não impedem a reutilização. Alterações no documento, outro vault ou remoção da pasta exigem uma nova exportação; arquivos existentes nunca são sobrescritos. A pasta `Importados` não pode apontar por link simbólico para fora do vault selecionado.

## OCR local

A instalação completa prepara Docling, RapidOCR e modelos de tabelas/fórmulas em um ambiente CPU separado, sem Tesseract e sem alterar as dependências da interface. Depois da preparação, o reconhecimento funciona offline. O comando `pdf-obsidian-prepare-ocr --verify` confere os recursos locais; downloads acontecem somente na preparação explícita.

O OCR complementa o texto nativo em páginas mistas e escaneadas. Tabelas reconhecidas viram Markdown ou HTML restrito; fórmulas geram LaTeX. As imagens originais são conservadas para revisão, e resultados incertos geram avisos. Sem modelos disponíveis, a conversão continua com extração direta e imagens. Desmarcar OCR mantém o caminho anterior e não carrega modelos. A opção é capturada no início da conversão ou do lote.

Consulte [OCR.md](OCR.md) para instalação completa, consumo de recursos, configuração offline, cancelamento e limites de reconhecimento. A prévia Qt pode mostrar LaTeX como código, acompanhado da imagem de referência; confira a apresentação final no Obsidian.

## Conversão em lote

1. Clique em **Converter em lote…** na tela inicial ou em **Abrir → Converter em lote…** no editor, adicione os PDFs e selecione **Converter N documento(s)**. Arquivos repetidos pelo mesmo caminho são ignorados.
2. Aguarde o resumo. A conversão é sequencial, informa falhas por arquivo e não grava nada no vault.
3. Selecione um documento convertido e clique em **Revisar**. Use o editor, a prévia e os recortes normalmente. Volte à lista pelo botão **Documentos (N)** no cabeçalho para revisar outro arquivo.
4. Desmarque os documentos que deseja excluir da exportação na lista. A conversão e as edições continuam disponíveis; basta marcar novamente para incluí-los.
5. Clique em **Exportar selecionados (N)…** e escolha a pasta do vault para confirmar a gravação de todos os marcados.

Cada documento mantém seu texto, cursor, seleção, desfazer/refazer, recortes, remoções manuais, aba, posição de leitura, página, zoom e opção de remover marcações de página. Um documento aberto antes do lote continua acessível na lista como **Fora do lote**, sem participar da exportação conjunta. **Salvar no vault…** também permite salvar apenas o documento em revisão.

Ao repetir a exportação para o mesmo vault nesta sessão, estados já salvos cuja pasta de saída ainda existe são indicados como **Já salvo**. Apenas documentos novos ou alterados geram outra pasta; saídas anteriores são preservadas com sufixos. Escolher outro vault exporta os marcados para esse destino. Uma falha não impede a tentativa dos demais, e os documentos continuam disponíveis para correção e nova tentativa.

**Cancelar** interrompe a conversão atual e os próximos arquivos, preservando os já concluídos. Na exportação, uma gravação já iniciada termina antes de interromper a fila. Use **Cancelar operação** (ou Esc na lista) e aguarde o encerramento; os resultados concluídos continuam disponíveis. Um novo lote substitui o anterior, com confirmação para descartar documentos não salvos, inclusive os desmarcados. Os documentos e o controle de exportações existem apenas na sessão atual; ao fechar a aplicação, o trabalho temporário é descartado após confirmação.

## Interface

A tela inicial em Qt Quick/QML aplica o visual aprovado, com **Abrir PDF**, **Converter em lote…** e informação de funcionamento local e offline. Durante a conversão individual, ela mostra o nome do arquivo, progresso real e cancelamento. Enquanto o cancelamento é concluído, exibe **Cancelando…** e impede solicitações repetidas. O resultado abre no editor QML na mesma janela; falha ou cancelamento conserva o documento anterior. O cabeçalho mostra o documento, a indicação de alterações não salvas, o menu **Abrir** (PDF individual ou lote) e **Salvar no vault…**, com opções no menu adjacente. Nomes longos são abreviados visualmente; o caminho completo permanece na dica do documento. Escolher a pasta confirma a exportação.

O PDF ocupa inicialmente cerca de 40% da área e o editor 60%, com divisória ajustável. **Ocultar PDF / Mostrar PDF** amplia o editor e restaura a divisão anterior, preservando página e zoom. **Acompanhar página**, ao lado desse controle, sincroniza o trecho exibido sem mover o cursor de edição.

A aba inicial é **Markdown**, com **Prévia** como alternativa. A prévia é preparada ao abrir a aba, sem atrasar a entrada no editor; enquanto isso, aparece **Preparando prévia…**. Na revisão de imagens filtradas, **Restaurar** fica disponível após a verificação da imagem, sem bloquear a janela. A barra reúne estilos de parágrafo/título, negrito, itálico e link, além dos menus **Listas** e **Alinhar**. Na prévia, desfazer/refazer ficam separados da seleção manual; contador, remoção e limpeza aparecem somente ao selecionar imagens.

Os **Avisos (N)** ficam recolhidos após cada conversão. Expanda a faixa de avisos e clique em um aviso de página para revelar o PDF e navegar até ela.

A interface utiliza o design system **Monochrome Premium**: fundo quase preto, superfícies em cinza, hierarquia tipográfica e destaque branco. Geist Sans e Geist Mono são incluídas localmente com suas licenças; fontes alternativas nativas são usadas se houver falha de carregamento. A interface usa corpo de 14 px e controles de 13 px; editor e prévia têm texto-base de 15 px, com escala de fonte e DPI preservadas. Ícones Lucide locais são compartilhados entre QML e Widgets, sem dependências adicionais ou downloads durante o uso. Ferramentas têm contorno por grupo, hover individual e foco de teclado reforçado. Os grupos se reorganizam em painéis estreitos sem esconder comandos. Consulte [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) para tokens, recursos, componentes e critérios de acessibilidade.

O cabeçalho adapta a posição das ações à largura e à fonte, mantendo o nome do documento e o estado de salvamento legíveis. A comparação identifica o **PDF original** e agrupa página, zoom percentual e ajuste; os grupos passam inteiros para outra linha quando necessário. Avisos têm uma faixa de atenção própria, e a seleção manual de imagens explica como desfazer a remoção. Estados de salvamento, falha e exclusão da exportação combinam texto com indicadores visuais.

Menus, dicas, barras de progresso, campos e diálogos compartilham os mesmos tokens. Os diálogos mantêm suas ações fora da área rolável: mensagens extensas e listas podem rolar sem esconder Cancelar, Fechar ou a ação principal. Confirmações de descarte começam com foco em **Cancelar**, e fechar um diálogo devolve o foco ao controle que o abriu. A interface é conferida em janelas a partir de 800 × 600 e com fonte ampliada em 25%, usando documentos sintéticos.

Use **Ctrl+O** para abrir um PDF e **Ctrl+S** para salvar o documento ativo no vault. As ferramentas de formatação são acessíveis por Tab; Espaço ativa o botão ou abre o menu. Ao aplicar um comando, o foco retorna ao editor com a seleção preservada. Os atalhos de formatação continuam restritos ao editor. Com foco nas abas Markdown/Prévia, use as setas esquerda/direita para alternar entre elas. A divisória entre PDF e editor também aceita foco por Tab e ajuste pelas setas esquerda/direita. Ao abrir um documento, o Markdown começa no início; ao retornar a outro documento da sessão, o cursor é restaurado inclusive quando não há seleção.

O editor e a prévia mantêm uma coluna centralizada de até 760 px lógicos, com margens adaptáveis. O Markdown recebe destaque incremental para títulos, ênfase, links, imagens, listas, citações, código e comentários; as marcações continuam visíveis. Menus, campos, barras de rolagem e diálogos usam os mesmos tokens. Avisos, falhas e sucesso são identificados por texto e símbolos, sem depender de cor. O conteúdo original de PDFs e imagens conserva suas cores.

No menu **Opções**, ative **Reduzir movimento** para desativar transições e o movimento dos indicadores indeterminados. A preferência vale somente durante a execução e não altera documentos nem a indicação de alterações não salvas. Os seletores nativos de arquivos e pastas continuam seguindo o tema do sistema.

## Interface Qt Quick/QML

O comando `.venv/bin/pdf-obsidian` abre uma janela QML completa: importação, progresso, preparação/resumo de lote, documentos, PDF, editor Markdown, prévia, imagens filtradas, links, opções, mensagens e confirmações. Os seletores de PDFs e de pasta do vault continuam nativos do sistema.

`quick.py` adapta as sessões e comandos à cena; `ApplicationController` e o worker Python permanecem únicos. Documentos `QTextDocument` pertencem ao Python e mantêm histórico ao alternar arquivos. O PDF continua sendo renderizado por PyMuPDF no processo auxiliar; a cena recebe somente o bitmap ativo. A prévia adapta as imagens à largura disponível sem alterar o Markdown ou os anexos.

A exportação individual também ocorre no worker, sobre um snapshot. Enquanto grava, as alterações ficam bloqueadas. Não há publicação automática após converter; escolher a pasta do vault continua confirmando a gravação. As confirmações da aplicação são diálogos QML assíncronos.

Para testar:

```bash
.venv/bin/pdf-obsidian
```

Se o renderizador gráfico apresentar problemas, execute com software:

```bash
QT_QUICK_BACKEND=software .venv/bin/pdf-obsidian
```

A interface Widgets anterior permanece disponível para recuperação e comparação:

```bash
.venv/bin/pdf-obsidian --widgets
```

Falha de carregamento da nova janela informa essa alternativa; a versão Widgets conserva sua recuperação automática da página de importação. Os recursos QML e tokens são locais e incluídos no pacote Python, sem downloads na execução. O [protótipo](prototypes/qml_import/README.md) continua demonstrativo. Consulte o [registro da migração](prototypes/qml_import/MIGRATION.md) e `VALIDATION.md` para cobertura e verificações de desktop ainda pendentes.

## Formatação do Markdown

A aba **Editar Markdown** tem uma barra com **Negrito**, **Itálico**, **Link**, estilos de **Parágrafo** e **Título 1–6**, listas com marcadores ou numeradas e **Citação**. Selecione o texto para formatar; para títulos, listas e alinhamento, o comando também funciona no parágrafo em que está o cursor. Repetir negrito, itálico, o mesmo nível de título, lista ou citação remove a marcação correspondente. Sem seleção, negrito e itálico inserem os delimitadores com o cursor entre eles. Use **Ctrl+B**, **Ctrl+I** e **Ctrl+K** com foco no editor. Cada comando pode ser desfeito com **Ctrl+Z**.

**Esquerda**, **Centro**, **Direita** e **Justificar** afetam parágrafos textuais e títulos, incluindo os vários parágrafos de uma seleção. O alinhamento é salvo em HTML, por exemplo `<p style="text-align: center;">Texto</p>`, sem precisar de plugins ou CSS adicional no Obsidian. Dentro desses blocos, os botões usam tags HTML equivalentes para negrito, itálico e links. **Esquerda** recupera o Markdown equivalente. O editor continua exibindo o código-fonte; confira o resultado na aba **Prévia** e no modo de leitura do Obsidian.

Imagens, listas, citações, tabelas, código, wikilinks e HTML personalizado não são convertidos em blocos alinhados. Se uma seleção misturar conteúdo incompatível, o programa informa o motivo sem aplicar alterações parciais. Para transformar um parágrafo alinhado em lista ou citação, use **Esquerda** primeiro. Negrito, itálico e links atuam em um bloco textual por vez; em listas e citações, selecione o texto de um único item ou linha. Os comentários de página permanecem disponíveis para comparação com o PDF.

## Questões e gabaritos

Novas conversões organizam questões reconhecidas pelo número, identificação da banca/prova e contexto da seção. Cada uma recebe um título navegável como **Questão 001**, um nível abaixo da seção vigente (até o nível 6), mantendo os zeros e reinícios de numeração do PDF. Questões que reaparecem no gabarito comentado permanecem nessa seção.

A identificação da banca fica em um parágrafo em negrito quando seus limites podem ser reconhecidos. Enunciados fragmentados são reconstruídos; cada alternativa aparece em um parágrafo próprio, com rótulo como **a)**, e cada afirmativa romana mantém seu identificador, como **II –**. Linhas de continuação com recuo também são consideradas. Ao atravessar uma página, a questão continua sem repetir seu título; o marcador de página fica no lugar para comparação com o original.

Números isolados sobrepostos ao mesmo prefixo de uma questão são descartados por coincidência textual e geométrica. Listas numeradas comuns e referências a alternativas no meio de frases continuam sendo tratadas como texto/lista, sem criar questões.

Comentários conservam seus parágrafos. Rótulos textuais explícitos, como **Comentário:**, são destacados, assim como respostas isoladas como **Certo.**, **Errado.** e **Letra e.**. Ícones ou espaços isolados não geram um rótulo novo; limites incertos recebem aviso de página. Respostas e comentários são preservados conforme o PDF.

Gabaritos textuais reconhecidos usam uma tabela simples de **Questão** e **Resposta**, preservando a capitalização das respostas. Uma continuação em outra página inicia outra tabela após o marcador. Entradas ou sequências ambíguas permanecem como texto para revisão. Tabelas/fórmulas já preservadas como imagens continuam disponíveis dessa forma.

A organização é aplicada ao abrir e converter o PDF novamente. O texto de um documento já editado não é reformatado automaticamente. As decisões e os avisos ficam em `conversao.json` na exportação.

## Conversão e limpeza

Rodapés de texto recorrentes são analisados **por linha**, inclusive quando o PDF agrupa site e paginação no mesmo bloco ou os mistura com conteúdo útil. A limpeza considera linhas inteiramente nos 10% inferiores da página e exige repetição em pelo menos três páginas e 70% do documento. Números como “7 de 120” são normalizados para reconhecer a paginação variável; site e avisos recorrentes são removidos separadamente.

Notas explicativas, referências, suas continuações e alternativas de questões recebem proteção, mesmo quando repetidas nessa região. Marcadores pequenos separados do texto da nota também são considerados pela proximidade geométrica. Conteúdo único, fora da faixa ou de identificação incerta permanece para revisão. As decisões ficam em `conversao.json`. Essa limpeza vale para novas conversões; os marcadores `<!-- Página N -->` continuam disponíveis para navegação e documentos já editados não são reformatados.

A conversão reconstrói parágrafos usando alinhamento, espaçamento e continuidade das linhas, inclusive quando o PDF as armazena em blocos separados. Mudanças de negrito ou itálico não interrompem o parágrafo. Títulos, listas, legendas e figuras delimitam a reconstrução. Hifens de fim de linha são removidos apenas quando há indicação explícita de quebra ou a palavra completa aparece no documento. A reconstrução ocorre dentro de cada página; revise continuações entre páginas e layouts com colunas.

Antes de reconstruir os parágrafos, o conversor elimina linhas idênticas sobrepostas na mesma página (tolerância de 1 ponto nas coordenadas). Isso corrige títulos desenhados duas vezes no PDF, sem eliminar títulos iguais em páginas ou posições diferentes. As decisões ficam no relatório.

O filtro de margens omite incorporações de imagens raster e desenhos vetoriais com a mesma identidade e posição, inteiramente nos 10% superiores ou inferiores da página. Exige recorrência em pelo menos três páginas e 70% do documento, com tolerância de 0,5% para posição e tamanho relativos. Figuras no corpo, tabelas, fórmulas, recortes e casos incertos são preservados. O filtro é aplicado automaticamente a novas conversões e não altera o PDF original.

**Imagens filtradas (N)**, ao lado dos controles do PDF, abre uma revisão com miniaturas, página e motivo. **Mostrar no PDF** revela o painel e navega à página. **Restaurar imagem** insere a figura ao final do trecho da página, antes do próximo marcador; a ação entra no histórico de desfazer/refazer. O botão fica indisponível quando a figura já está incorporada. Se o marcador estiver ausente ou duplicado, corrija-o ou use um recorte manual. Estruturas Markdown incompletas que impediriam renderizar a inserção também bloqueiam a restauração.

Na aba **Prévia**, ative **Selecionar imagens** e clique nas imagens que deseja remover. Elas recebem uma borda numerada; clicar novamente desmarca a imagem. Você pode selecionar várias imagens, inclusive em páginas diferentes, e clicar em **Remover selecionadas** para aplicar tudo de uma vez. **Limpar seleção** cancela as marcações sem alterar o Markdown.

A seleção manual permite escolher imagens raster, figuras vetoriais convertidas e recortes. Ela remove apenas as ocorrências clicadas: outras cópias da imagem e os textos ao redor permanecem. Use **Desfazer/Refazer** na própria prévia ou **Ctrl+Z/Ctrl+Shift+Z** para restaurar ou reaplicar a operação. A edição do Markdown limpa a seleção pendente e atualiza a prévia antes de permitir novas remoções.

As imagens geradas pelo conversor aparecem como incorporações isoladas e podem ser selecionadas diretamente. Se uma edição manual misturar a imagem com texto ou links no mesmo parágrafo e impedir uma associação segura, a interface orienta removê-la pelo editor Markdown. Exemplos de código não são tratados como imagens para exclusão.

A remoção de outras imagens continua manual pela prévia. Os arquivos temporários, inclusive os filtrados nas margens, permanecem disponíveis para recuperação e desfazer/refazer durante a sessão.

A opção **Remover marcações de página na exportação** começa desativada para cada documento. Quando ativada, remove os comentários gerados pelo aplicativo da cópia final, mantendo os marcadores no editor para a comparação com o PDF. Exemplos em blocos de código, comentários dentro de HTML e metadados YAML são preservados.

A exportação copia os anexos usados pelo Markdown final, considerando imagens, links comuns, referências nomeadas, wikilinks do Obsidian e links nos blocos alinhados gerados pelo programa. Arquivos sem referência reconhecida são omitidos. Quando HTML personalizado, metadados YAML ou referências ambíguas impedem determinar o uso com segurança, todos os anexos são preservados; o motivo fica em `conversao.json`. Um link explícito para um arquivo inexistente em `assets/` interrompe a exportação com uma mensagem. A limpeza nunca apaga arquivos do vault ou modifica o PDF original.

O relatório registra as linhas sobrepostas removidas, as imagens filtradas (página, região, assinatura e motivo), sua incorporação/referência atual e inclusão do arquivo na exportação. Também registra a opção de paginação, as incorporações removidas ainda ausentes, a origem manual das escolhas na prévia, os arquivos omitidos e os motivos para preservar anexos. Se uma ocorrência da imagem ainda for usada, seu arquivo permanece na exportação. Desfazer a limpeza antes de exportar restaura também a inclusão desses arquivos na saída.

## Comparação e navegação

O painel **PDF original** tem botões **Anterior/Próxima** e o campo **Página X de Y**. Digite uma página e confirme com Enter ou saindo do campo. Use **−/+** ou digite um zoom entre 25% e 300%; os modos **Ajustar à largura** e **Ajustar à página** acompanham o tamanho do painel. O zoom de 100% usa a referência de 100 dpi.

O zoom digitado também é confirmado com Enter ou ao sair do campo. Valores vazios ou inválidos voltam ao valor efetivo. Nos ajustes automáticos, o percentual mostra a resolução solicitada; **−/+** parte desse valor e passa ao zoom manual. Os campos acompanham a navegação e a troca de documento e ficam desabilitados durante operações que bloqueiam a edição.

- **Alt+Esquerda/Direita**: página anterior/próxima, inclusive durante a edição.
- Com foco no painel do PDF, **Ctrl++/−** aumenta/diminui o zoom e **Ctrl+0** ajusta à largura.
- A roda do mouse e as barras de rolagem percorrem a página atual; use os controles para trocar de página.

**Acompanhar página no Markdown** vem ativado. Ao trocar a página exibida, o editor e a prévia vão ao trecho correspondente, sem mover o cursor de edição, alterar a seleção ou criar operações de desfazer. Desmarque essa opção para navegar independentemente. O acompanhamento usa os comentários `<!-- Página N -->` da nota; se um marcador for removido ou duplicado, uma mensagem informa que o trecho não pôde ser localizado. As âncoras da prévia são internas e não entram no arquivo exportado.

Durante a preparação de uma página, você pode continuar navegando, ajustando o zoom e editando o Markdown. Apenas o recorte fica suspenso até a imagem solicitada estar pronta. Pedidos rápidos priorizam a última escolha; se uma página falhar, a última imagem válida permanece disponível.

## Limites

A conversão usa heurísticas: revise a hierarquia dos títulos, listas, figuras e ordem de leitura. O OCR local complementa texto, tabelas e fórmulas quando os modelos estão preparados, preservando imagens para conferência. Com OCR desligado ou indisponível, a extração direta continua e regiões sem texto nativo exigem revisão pelas imagens ou recortes. Não há suporte garantido a múltiplas colunas; fórmulas em LaTeX precisam ser conferidas no Obsidian. O objetivo é preservar conteúdo para estudo, não reproduzir paginação no Markdown. Lotes mantêm os textos convertidos e seus históricos em memória até fechar a aplicação; muitos documentos grandes podem exigir mais memória e espaço temporário.

A renderização da prévia Qt pode diferir do Obsidian. A validação visual no Obsidian desktop e Android é uma etapa manual de aceite. O aplicativo não implementa sincronização.

## Arquitetura

`models` define os contratos de páginas, blocos, avisos e resultados. `pdf` isola PyMuPDF; `converter` reconstrói o conteúdo e gera anexos; `exporter` prepara a saída e publica a pasta por renomeação sem sobrescrever. `worker` serializa as operações PDF em processo separado, enquanto `gui` contém a interface PySide6. A publicação usa `renameat2` do Linux para impedir colisões entre processos.

`batch` controla as filas de conversão, verificação e exportação, com eventos identificados por lote e arquivo. `batch_dialog` apresenta preparação e resumo; `sessions` e `session_ui` mantêm um documento Qt por arquivo e restauram sua visualização no editor existente. Somente o PDF e a prévia ativos ficam renderizados. A assinatura de exportação usa a mesma preparação do exportador, incluindo texto, opções e auditoria efetiva.

`markdown` analisa referências e blocos protegidos usando [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/using.html). `cleanup` prepara remoções manuais vinculadas à versão analisada do texto. Os metadados dos anexos preservam origem, finalidade conhecida, página, região e identidade do raster original, permitindo distinguir figuras de tabelas, fórmulas e recortes manuais.

`footers` remove linhas recorrentes no rodapé, protegendo notas e referências e atualizando somente os trechos afetados dos blocos. A limpeza ocorre antes da organização de questões e da reconstrução de parágrafos. Cabeçalhos mantêm o tratamento anterior.

`questions` reconhece componentes de questões antes da reconstrução e gera seus títulos, alternativas, comentários e gabaritos, mantendo contexto entre páginas. O campo opcional interno de papel de cada linha não altera a estrutura de pastas exportada.

`conversion_filters` identifica linhas e números sobrepostos e elementos recorrentes nas margens; `filtered_images` apresenta a revisão e prepara restaurações localizadas. A conversão primeiro extrai texto/regiões de todas as páginas e depois gera os anexos com o filtro decidido, sem remover texto coberto por uma figura filtrada. O progresso acompanha as duas passagens.

`preview` associa as imagens renderizadas às ocorrências do Markdown atual, permite seleção visual e encaminha remoções ao mesmo mecanismo de desfazer e exportação usado pela revisão de limpeza.

`formatting` prepara alterações localizadas e valida o subconjunto de HTML alinhado. `editor_tools` apresenta os controles e aplica cada mudança em uma operação de desfazer. A prévia insere os blocos alinhados depois da importação Markdown do Qt para preservar sua separação e alinhamento.

As páginas são processadas sequencialmente e renderizadas sob demanda. Um documento aberto não é compartilhado entre threads/processos. O aplicativo não precisa de banco de dados ou servidor.

## Validação

```bash
python -m pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui.py
python tools/benchmark.py
python tools/benchmark.py --gui
```

Os testes criam PDFs sintéticos redistribuíveis, verificando texto, títulos, figuras vetoriais, recortes, falhas e exportação. O benchmark gera uma apostila sintética de 200 páginas e informa tempo e pico de memória do processo de conversão. A opção `--gui` mede o RSS combinado da interface e do processo auxiliar por amostragem em `/proc`. Essas medições sintéticas não substituem testes com documentos reais em hardware de 8 GB. Meta inicial: consumo combinado abaixo de 2 GB.

## Licença

AGPL-3.0-only. Consulte `LICENSE`. PyMuPDF, PySide6 e markdown-it-py mantêm seus próprios termos de licenciamento e avisos.
