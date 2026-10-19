# Validação do MVP

Registro publicável das verificações sintéticas. Detalhes de documentos privados foram removidos; os registros originais permanecem apenas no checkout de desenvolvimento. Entradas antigas descrevem a versão testada naquele momento, não substituindo os resultados mais recentes.

## Preparação para publicação — 18/10/2026

- Suíte completa: `.venv/bin/python -m pytest -q` — **275 testes passaram em 66,35 s**. Não houve mudança funcional na preparação para publicação.
- Documentação revisada para remover identificação, caminhos e detalhes de documentos privados; registros originais preservados somente em pasta local ignorada. PDFs não são parte do repositório; testes geram documentos sintéticos.
- A revisão do primeiro commit inclui regras de exclusão, conteúdo preparado no índice, imagens demonstrativas e metadados, links locais da documentação e varredura de segredos com Gitleaks. Relatórios e ferramentas auxiliares ficam em `.local/`, fora da publicação.
- Clone limpo do commit local, sem PDFs ou registros privados: **275 testes passaram em 67,21 s**. Usado o ambiente de dependências existente, com `PYTHONPATH=src`; a origem do módulo foi conferida dentro do clone. Isso verifica independência dos arquivos locais, não uma instalação nova das dependências.
- Gitleaks 8.30.1 não encontrou segredos no conteúdo preparado nem no histórico. Conferidos os 78 arquivos, exclusões, links Markdown e ausência de metadados textuais/EXIF nas duas capturas demonstrativas do protótipo.
- Os aceites interativos de desktop e Obsidian permanecem pendentes.

## Consistência de navegação, zoom e salvamento — 18/10/2026

- Suíte completa: `.venv/bin/python -m pytest -q` — **275 testes passaram em 68,12 s**. Duas regressões novas e integração existente com worker real ampliada.
- Campos numéricos: teclado real na cena QML verifica confirmação ao sair e com Enter, uma única emissão por edição, recuperação de entradas vazias/inválidas, sincronização com navegação e troca de sessão, bloqueio durante exportação e ausência de operações de desfazer no documento.
- Zoom: verificados DPI de 100 no zoom manual de 100%, percentuais dos ajustes de largura/página, incremento a partir do ajuste, redimensionamento em modo automático/manual e limites 25–300. Os testes existentes de renderizações obsoletas e coordenadas de recorte também passaram.
- Exportação real: salvar novamente mantém a mesma pasta e todos os seus bytes; mudanças de texto/opção criam outras saídas; outro vault recebe sua própria exportação; pasta removida é recriada. Exportação individual reconhece também o registro criado pelo lote. Originais sintéticos preservados. Regressões de falha e resposta obsoleta adaptadas ao protocolo interno atualizado.
- `pyside6-qmllint` de todos os QML da aplicação e wrapper do protótipo passou sem avisos. `prototypes/qml_import/run.py --check` confirmou carregamento, Tab, Espaço, Ctrl+O, clique e disabled, sem avisos QML.
- Verificações em software/offscreen; aceite interativo no desktop e Obsidian continua pendente. PDF pessoal e vaults reais não utilizados; sem alterações dos filtros, novas dependências ou commits.

Ambiente: Linux x86_64, Python 3.14.8, PyMuPDF 1.27.2.3, PySide6 6.10.2 e markdown-it-py 4.2.0. O requisito mínimo declarado é Python 3.12; essa versão mínima ainda não foi exercitada neste ambiente.

## Verificações automatizadas

A suíte usa PDFs sintéticos gerados pelos próprios testes, sem documentos privados ou downloads. Abrange ordem do texto, títulos e sumário, acentos, listas, caracteres Markdown, cabeçalhos repetidos, títulos numerados, tabelas, fórmulas reconhecidas, figuras vetoriais, recortes, arquivos inválidos, senha, ausência de texto, cancelamento, alteração da origem, colisões e limpeza após falha. Inclui abertura/fechamento do processo auxiliar e conversão, edição, prévia, recorte e exportação pela interface Qt em modo offscreen.

Execute `.venv/bin/python -m pytest -q` para repetir a suíte.

## Remoção manual e anexos

A ferramenta de sugestões automáticas e seu diálogo foram removidos. O PDF sintético de cinco páginas com logos repetidos continua sendo utilizado para verificar que todas as imagens permanecem na conversão até uma exclusão manual. A opção de omitir marcações de página fica diretamente na janela principal e altera somente a cópia exportada.

Após essa remoção, a suíte passou com 68 testes. Os testes específicos da classificação automática foram retirados e a cobertura de exportação foi adaptada para seleções manuais.

A análise de referências cobre imagens, links comuns, referências nomeadas, tabelas Markdown, wikilinks, nomes codificados em URL e exemplos de código. HTML, YAML e referências incertas preservam os anexos. Testes de exportação verificam links compartilhados, arquivos sem uso, anexos ausentes, integridade do original e atualização do relatório após desfazer.

## Seleção manual na prévia

Uma apostila sintética de duas páginas reproduz o caso de imagens que precisam ser escolhidas manualmente. Os testes clicam na prévia para selecionar raster e vetor, verificam marcação/desmarcação, seleção entre páginas, remoção em lote, desfazer/refazer pela própria prévia e atalho Ctrl+Z. Também validam atualização após edição, preservação de notas com emoji, ocorrências duplicadas, texto ao redor e arquivos temporários.

Os testes do núcleo cobrem legendas editadas, referências compartilhadas, exemplos de código e recusa de imagens misturadas com texto quando não há uma incorporação isolada. O relatório registra quantas ocorrências foram removidas e mantém o arquivo exportado quando outra referência ainda o utiliza. Foi inspecionada uma captura do PDF ao lado da prévia com duas imagens selecionadas por bordas numeradas.

## Navegação e comparação

Os testes Qt adicionais usam um PDF de três páginas, incluindo uma página horizontal. Validam botões e limites, digitação confirmada com Enter, atalhos, zoom manual, ajuste ao painel, redimensionamento, preservação do centro visível, priorização de pedidos rápidos, falha e recuperação da renderização, coordenadas de recortes em 50% e 200%, acompanhamento opcional, marcadores ausentes/duplicados e preservação de cursor, seleção, alterações, desfazer e posição de leitura da prévia. A exportação também verifica que as âncoras internas não entram no Markdown.

A suíte força a plataforma Qt offscreen e o estilo Fusion, independentemente da sessão Wayland/GNOME. Foi inspecionada uma captura da aplicação exibindo a página 2 do PDF ao lado do capítulo correspondente na prévia. A conferência interativa no desktop real permanece recomendada, sobretudo para atalhos que possam ser interceptados pelo ambiente gráfico.

## Formatação e alinhamento

A suíte completa passou com 124 testes, incluindo 56 casos novos de transformação e interface.

A barra do editor foi exercitada em Qt offscreen: botões, estilos de parágrafo e título, atalhos Ctrl+B/I/K restritos ao editor, diálogo de link com confirmação e cancelamento, seleção reversa com emoji, foco e desfazer/refazer em uma operação. Foram verificadas a disponibilidade durante renderização e a suspensão durante conversão e recorte.

Os testes de transformação cobrem Markdown e o subconjunto de HTML alinhado, quatro alinhamentos, títulos H1–H6, listas, citações, referências nomeadas de links, espaços ao redor de estilos, prefixos literais e preservação de marcadores entre páginas. Seleções incompatíveis, tags ou entidades cortadas, código, imagens e destinos de links são protegidos contra mudanças indevidas. HTML personalizado continua preservando anexos por precaução.

A integração verifica a prévia centralizada, à direita e justificada após os marcadores de página, além da remoção manual de imagem, exportação, relatório e desfazer após alinhar um parágrafo. Foram inspecionadas capturas do editor e da prévia ao lado de um PDF sintético com título centralizado. O alinhamento é aplicado depois da importação Markdown do Qt para evitar a junção indevida com o bloco anterior.

A conferência do modo de leitura no Obsidian desktop e Android não foi realizada nesta sessão e permanece pendente; os testes locais não substituem essa validação.

## Desempenho sintético

Documento: 200 páginas A4 com um título e 35 linhas por página.

- Núcleo: 8,57 s; pico RSS do processo de benchmark de 685,8 MiB, incluindo geração do PDF.
- Interface + processo auxiliar: 9,12 s; pico RSS combinado observado de 265,6 MiB, amostrado em `/proc` aproximadamente a cada 20 ms e após carregar a prévia.

Os números usam metodologias diferentes: RSS máximo histórico de um processo e amostragem da soma de dois processos. Não representam garantia para documentos reais nem uma comparação entre implementações. A medição combinada ficou abaixo da meta inicial de 2 GB para este corpus.

## Reconstrução de parágrafos

Nove testes adicionais cobrem fragmentação entre blocos, mudanças de negrito/itálico, separação de parágrafos, títulos, continuação de listas, barreira de imagens, hifens, colunas e espaços entre segmentos de texto. A reconstrução não une páginas nem resolve a ordem de leitura de múltiplas colunas.

Antes da remoção da ferramenta automática, a suíte completa passou com 80 testes.

## Aceite manual pendente

- Conferir visualmente documentos reais de uma coluna, sobretudo figuras e limites de tabelas/fórmulas.
- Abrir a pasta exportada no Obsidian desktop e conferir imagens e link ao original.
- Transferir a pasta inteira para um vault Android e conferir os mesmos links.
- Executar em um computador com 8 GB e repetir a instalação em Python 3.12.

Esses itens dependem de aplicativos, dispositivos e documentos não disponíveis na sessão. O MVP não implementa sincronização, OCR ou interpretação garantida de layouts complexos.

## Reorganização visual e temas — 18/10/2026

Suíte completa: **127 testes passaram em 26,77 s** com `.venv/bin/python -m pytest -q`.

Três testes novos verificam preferência de tema em arquivo temporário isolado, reabertura, acompanhamento do tema do sistema, preservação de texto/cursor/seleção/estado modificado e desfazer/refazer, manutenção da seleção manual de imagens, avisos recolhíveis, progresso/cancelamento e redimensionamento para 1024 × 700.

Foram inspecionadas capturas Qt offscreen nos temas claro e escuro, em 1300 × 850 e 1024 × 700, com um PDF sintético: estado vazio, editor, prévia com imagem selecionada e avisos abertos. As capturas temporárias ficam em `/tmp/pdf-ui-*.png`. Nenhum PDF pessoal foi utilizado. Os controles ficaram acessíveis sem sobreposição; o PDF permanece com as cores originais. O texto exportado não recebe estilos do tema.

A conferência interativa no ambiente gráfico real, incluindo integração com o tema do desktop e diálogos nativos, permanece recomendada. Não foi realizada validação no Obsidian desktop ou Android nesta alteração.

## Modo escuro exclusivo e refinamento visual — 18/10/2026

Esta alteração substitui a seleção de temas descrita na seção anterior: somente o modo escuro permanece. Seletor, paleta clara, leitura/escrita de preferência e acompanhamento do tema do sistema foram removidos. Preferências antigas não são consultadas.

Referências: [refinamento visual do Linear](https://linear.app/now/behind-the-latest-design-refresh) e [interface do Penpot](https://help.penpot.app/user-guide/first-steps/the-interface/). Aplicados superfícies grafite, bordas discretas, destaque lavanda, abas compactas, ferramentas de formatação em uma fileira, ícones vetoriais locais e barras de rolagem escuras. Nenhuma dependência ou conexão remota foi adicionada.

Suíte completa: **127 testes passaram em 26,15 s**. A cobertura de apresentação foi adaptada para validar modo escuro fixo, preservação de texto/seleção/histórico, controles de estado, geometria em 1024 × 700 e ícones com dicas e nomes acessíveis. A suíte inclui as regressões anteriores de edição, prévia, navegação, recorte, remoção manual e exportação.

Capturas offscreen inspecionadas com PDF sintético: estado vazio, editor, prévia com uma imagem selecionada e avisos, em 1300 × 850 e 1024 × 700. Arquivos temporários em `/tmp/pdf-dark-*.png`. A conferência interativa no desktop real permanece pendente.

## Redesenho como editor de documentos — 18/10/2026

Suíte completa: **129 testes passaram em 27,93 s** com `.venv/bin/python -m pytest -q`. Após ampliar as asserções da tela inicial/conversão, os três testes de apresentação passaram novamente em 0,79 s.

Dois testes novos verificam restauração da divisão do PDF, página e zoom manual, preservação de texto/cursor/seleção e desfazer/refazer, indicação de alterações, revelação do PDF por aviso, comandos dos menus Listas/Alinhar e retorno do foco ao editor. A cobertura existente continua validando conversão/cancelamento, recortes, exportação, referências e seleção manual. Corrigida uma regressão exposta pela largura maior da prévia: páginas curtas próximas do final precisam de espaço inferior para permitir posicionar a âncora no topo.

Inspecionadas dez capturas Qt offscreen com PDF sintético em 1300 × 850 e 1024 × 700: tela inicial, edição, PDF recolhido, prévia com seleção e avisos expandidos. Arquivos temporários em `/tmp/document-editor-*.png`. Controles acessíveis nas duas dimensões, sem sobreposição observada. A captura da seleção foi feita com uma incorporação sintética marcada; os testes de interação existentes continuam cobrindo cliques e remoção.

Nenhum PDF pessoal ou vault foi utilizado ou alterado. Sem novas dependências, recursos remotos ou commits. A validação no desktop real e no Obsidian desktop/Android permanece pendente.

## Títulos sobrepostos e filtro conservador de margens — 18/10/2026

Esta alteração substitui a restrição anterior de remoção exclusivamente manual: o usuário autorizou filtrar automaticamente raster/vetores recorrentes nas margens, com revisão e recuperação. Não foi reintroduzido um classificador geral de decoração. Figuras no corpo e casos incertos continuam dependendo da seleção manual. OCR permanece fora do escopo.

Suíte completa: **148 testes passaram em 30,38 s** com `.venv/bin/python -m pytest -q`. Após corrigir a herança da paleta escura do novo diálogo e acrescentar uma asserção de regressão, o teste de revisão passou novamente em **1,26 s**.

Dezenove novos casos sintéticos cobrem texto Unicode, normalização de espaços, direção e tolerância das linhas sobrepostas, repetições legítimas, identidades raster/vetoriais, cores e translação dos caminhos, frequência mínima, cabeçalho/rodapé, limites de posição/tamanho, ausência de encadeamento de deslocamentos e contagem por páginas distintas. Também verificam preservação de figuras no corpo e texto sob vetores filtrados, proteção de tabelas/fórmulas, cancelamento entre as passagens, arquivos temporários, restauração no trecho correto, exemplos de código, marcadores ausentes/duplicados, estruturas incompletas, edição de descrição, links compartilhados, histórico e remoção manual após recuperação.

O relatório de exportação foi verificado para figuras omitidas, incorporadas e referenciadas apenas por link, incluindo as flags `incorporated`, `referenced` e `file_exported`. Anexos filtrados continuam no workspace, mas são omitidos da exportação quando não utilizados. Referências incertas continuam usando a preservação conservadora anterior.

Capturas Qt offscreen inspecionadas com PDF sintético em 1300 × 850 e 1024 × 700: janela com o botão Imagens filtradas, diálogo com miniaturas/motivos/ações e estado após restauração. Arquivos temporários em `/tmp/filtered-workspace-*.png`, `/tmp/filtered-review-*.png` e `/tmp/filtered-review-restored.png`. Na inspeção inicial foi detectado e corrigido o fundo claro do diálogo; na versão final as instruções e botões estão legíveis no modo escuro. A conferência interativa no desktop real permanece pendente.

Sem novas dependências, acesso remoto, alterações em vaults ou commits. Aceite no Obsidian desktop/Android, Python 3.12 e hardware de 8 GB continua pendente.

## Organização de questões e gabaritos — 18/10/2026

Suíte completa: **173 testes passaram em 30,86 s** com `.venv/bin/python -m pytest -q`. Vinte e cinco novos casos verificam questões de múltipla escolha e certo/errado, metadados de banca com parênteses aninhados e quebras entre blocos, mudanças de fonte, números sobrepostos, sequências alfabéticas/romanas, alternativas longas com recuo, reinício de numeração e preservação de listas comuns. Também cobrem metadados incompletos, rótulos e recuos ambíguos, entradas de gabarito incertas, numeração explícita não suportada sem truncamento, cancelamento e continuação entre páginas.

Um PDF sintético de seis páginas exercita teoria com questões, alternativas que continuam na página seguinte, figura intermediária, comentários explícitos, questões de concurso, gabarito em duas páginas e gabarito comentado. Os testes conferem exportação, integridade do original, referências dos anexos, preservação/remoção opcional dos marcadores, decisões no relatório, títulos reais na prévia Qt, tabelas renderizadas e edição com desfazer/refazer após alternar abas. A suíte anterior permanece cobrindo remoção manual, recuperação de imagens filtradas, navegação, recortes e formatação.

Inspecionadas oito capturas sintéticas Qt offscreen em 1300 × 850 e 1024 × 700: editor, prévia de questões, continuação de alternativas e tabela de gabarito. Arquivos temporários em `/tmp/questions-{editor,preview,continuation,key}-{1300,1024}.png`. Títulos, rótulos e tabelas ficaram legíveis; layout e ferramentas permaneceram acessíveis nas duas dimensões. O teste Qt verifica que o gabarito renderiza como tabela e que os títulos são reconhecidos como cabeçalhos.

README e contexto atualizados. Sem novas dependências, acesso remoto, OCR, alterações de vaults ou commits. Aceite interativo no desktop real, Obsidian desktop/Android, Python 3.12 e hardware de 8 GB continua pendente.

## Rodapés por linha com proteção de notas — 18/10/2026

Suíte completa: **206 testes passaram em 26,56 s** com `.venv/bin/python -m pytest -q`. Os 33 casos novos específicos passaram isoladamente em 0,25 s.

Cobertura sintética: paginação variável e site em duas linhas do mesmo bloco PDF, remoção parcial de blocos mistos com atualização de texto/geometria/linhas/tamanho predominante, idempotência e preservação de imagens. Verificados os limiares de três páginas/70%, contagem por página distinta, normalização de formatos de paginação, faixa inferior, conteúdo único e geometria incerta.

Notas, referências, alternativas e afirmativas repetidas permanecem, inclusive continuações que começam acima dos 10% inferiores, fragmentadas em blocos, com URLs de referência e paginação em outra coluna. Testes de marcadores pequenos separados abrangem número simples, número com ponto, colchetes, sobrescrito, asterisco e símbolo de nota. A proteção usa proximidade, estilo e coluna; conteúdo incerto permanece.

Um PDF sintético de cinco páginas verifica questões e alternativas próximas à faixa inferior, navegação por âncoras na prévia Qt, preservação do cursor e histórico de edição, exportação com revisão manual, relatório de decisões e integridade da cópia original. A suíte anterior cobre cabeçalhos, figuras, filtros, questões/gabaritos e fluxos da janela. Não houve mudança visual nem novos controles.

## Conversão em lote com revisão — 18/10/2026

Suíte completa final: **224 testes passaram em 48,57 s** com `.venv/bin/python -m pytest -q`.

Implementada fila sequencial de conversão sem exportação automática, seguida de resumo com seleção para revisar cada documento no editor existente. Desmarcar preserva conversão e edições; a exportação conjunta exige escolher a pasta do vault. Documentos abertos fora do lote permanecem disponíveis para revisão e exportação individual. Sem OCR, novas dependências ou alterações nos formatos exportados.

A suíte inclui **18 novos testes**, todos com PDFs e destinos sintéticos. Cobrem:

- Deduplicação por caminho canônico/atalho, PDFs inválidos ou com senha, continuação após falha, ausência de exportação automática e integridade das origens.
- Troca de documentos com texto, cursor/seleção reversa, desfazer/refazer, recortes, remoções manuais/auditoria, seleção de imagens, aba, posição de leitura, página, zoom, visibilidade do PDF, acompanhamento, avisos e opções individuais preservados.
- Resultados obsoletos de renderização/operação e navegação nova durante restauração; documento anterior fora do lote e substituição de lote com limpeza dos workspaces antigos.
- Exportação dos marcados com edições e opções próprias, exclusão/inclusão posterior, arquivos de mesmo nome, vaults distintos, repetição sem cópias de estados iguais, mudanças com sufixo e pasta exportada removida.
- Registro compartilhado entre exportação individual e conjunta; assinatura sem efeito de remoções desfeitas; totais do resumo de cada operação.
- Falha por origem alterada, anexo ausente e obstáculo real à gravação, com preservação dos documentos e nova tentativa após corrigir a causa.
- Cancelamento de conversão com resultados concluídos preservados, interrupção dos seguintes, término de gravação já iniciada e fechamento do diálogo durante a operação. Cancelamento repetido é idempotente.
- Confirmação agregada de descarte incluindo documentos desmarcados, preparação/resumo/retorno ao editor e término inesperado do worker sem perder os documentos concluídos.

Inspecionadas capturas Qt offscreen em **1300 × 850 e 1024 × 700**: preparação, conversão em andamento, resumo com falha, editor individual, prévia com seleção manual, exclusão de um arquivo e exportação concluída. Arquivos temporários `/tmp/batch-*.png`, com janela e diálogo capturados separadamente. Corrigidos o fundo/contraste da lista e da barra de progresso, as dimensões das linhas e o contador final. A atualização de checkbox é adiada para depois do sinal Qt, evitando destruir o item durante sua interação.

README e contexto atualizados. Apenas documentos e vaults sintéticos temporários foram usados nesta implementação; PDF pessoal e vaults reais não foram utilizados ou modificados. Sem commits. Os textos e históricos dos documentos permanecem em memória e os anexos em workspaces temporários; consumo com muitos PDFs grandes ainda não foi medido. Interação no desktop real, Obsidian desktop/Android, Python 3.12 e máquina de 8 GB permanecem pendentes.

## Correção da cintilação da lista do lote — 18/10/2026

Suíte completa: **227 testes passaram em 51,23 s** com `.venv/bin/python -m pytest -q`.

A lista apagava e recriava todas as linhas a cada evento de progresso. Agora preserva os itens por identificador, atualiza seus dados e adiciona/remove linhas somente quando a composição muda. O sinal `progress_changed` atualiza apenas a barra; as transições de estado passam uma vez pelos controles da janela, eliminando a atualização duplicada do diálogo. O bloqueio de sinais dos checkboxes é restaurado mesmo após exceções.

Três regressões novas verificam:

- Trinta eventos sucessivos de progresso em uma lista de 38 entradas, sem sinais de alteração/reset/inserção/remoção do modelo e com seleção, foco e rolagem horizontal/vertical preservados. Eventos obsoletos são ignorados. Conclusão, falha e cancelamento atualizam as mesmas linhas, com uma atualização do diálogo por transição de arquivo.
- Atualização sem mudanças não altera o modelo; checkboxes programáticos não disparam `itemChanged`, interação manual mantém a inclusão correta e exportação/repetição apresentam **Salvo** e **Já salvo** nas mesmas linhas.
- Remover uma entrada na preparação preserva as demais linhas; exceções restauram o bloqueio anterior dos sinais e permitem novas atualizações.

Os testes usam PDFs e vaults sintéticos; os eventos do teste de progresso são entregues de forma controlada, sem depender da velocidade do worker. O teste existente de cancelamento por progresso passou a usar o sinal específico de progresso. Nenhum PDF pessoal ou vault real foi utilizado; nenhum commit criado. Os testes offscreen não equivalem à conferência visual no desktop.

Após a implementação, o usuário confirmou: **“A cintilação parou”**. Essa validação do usuário encerra a pendência específica da cintilação da lista durante a conversão em lote; não representa validação das demais interações ou dos ambientes ainda pendentes.

## Redesign inspirado no Raycast — 18/10/2026

Suíte completa final: **230 testes passaram em 51,27 s** com `.venv/bin/python -m pytest -q`.

Aplicados tokens de cor e métricas compartilhadas, superfícies grafite com destaque coral, cartão inicial, progresso com nome do arquivo, menu Abrir com abertura individual/lote, título abreviado visualmente, foco por teclado e reorganização de grupos de ferramentas. Editor, prévia, PDF, lista do lote, revisão de imagens filtradas e diálogo de links compartilham os novos estilos. Ícones locais Qt reaproveitados e ampliados; sem Lucide, downloads, dependências ou animações adicionais.

Três regressões novas verificam: formatação e menu de listas pelo teclado com seleção Unicode reversa e desfazer; reorganização da barra ao reduzir de 650 para 300 px e retornar, conservando documento, cursor, seleção e histórico; cor dos links da prévia com destino e âncora interna preservados. A asserção de paleta existente foi atualizada. As demais regressões continuam cobrindo lote, lista sem cintilação, exportação, documentos da sessão, recortes, remoções/restaurações e integridade das origens sintéticas.

Capturas Qt offscreen geradas com PDF sintético de cinco páginas, inspecionadas na tela inicial, editor, prévia e seleção em 1300 × 850 e 1024 × 700; preparação do lote e revisão de imagens filtradas também inspecionadas. Repetida a geração com fonte do sistema ampliada em 25%, com inspeção da tela inicial, editor, seleção e preparação do lote. Corrigidos corte do título inicial e azul padrão dos links da prévia. As capturas são temporárias em `/tmp/redesign-*.png` e `/tmp/redesign-scale-*.png`.

Contraste calculado pela luminância relativa sRGB: texto/superfície **14,50:1**, texto secundário/superfície **7,68:1**, texto do botão/coral **6,81:1**, link coral/fundo de leitura **6,61:1**. Isso verifica essas combinações, sem representar auditoria integral de acessibilidade. Fontes ampliadas não equivalem à validação em monitor de alta densidade real.

PDF pessoal e vaults reais não utilizados nem alterados. Sem commits. README e PROJECT_CONTEXT atualizados. Conferência interativa no desktop real, leitor de tela, alta densidade real, Obsidian desktop/Android, Python 3.12 e máquina de 8 GB continuam pendentes.

## Migração QML — primeira extração da coordenação Python — 18/10/2026

Suíte completa final: **239 testes passaram em 51,01 s** com `.venv/bin/python -m pytest -q`.

Criados `WorkerRuntime` e `ApplicationController` em `application.py`. A fachada possui o ciclo de vida do processo auxiliar e filas, workspaces, polling, conversão, progresso, cancelamento e roteamento de resultados/erros. Renderizações e recortes usam o protocolo existente; a exportação individual chama o exportador pela fachada, mantendo seu comportamento síncrono. `BatchController` recebe a fachada e `BatchHooks`, sem referências diretas a `Window`. A aplicação Widgets já usa essa camada; editor, documentos duráveis, seleção, geometria/coalescência de renderizações e prévia continuam nos adaptadores atuais.

Nove casos novos de regressão em `tests/test_application.py` verificam:

- Aceite de URL local com Unicode e recusa de URL remota/vazia, impedimento de conversões simultâneas, propriedade do workspace e atualização pontual do progresso.
- Entrega de conversão com agendamento de renderização no callback sem apagar o novo estado e sem aceitar progresso de conversão quando essa operação já terminou.
- Cancelamento repetido, falha, retorno a ocioso, recuperação para nova conversão e manutenção dos workspaces até o encerramento.
- Transporte de recortes/renderizações e encerramento idempotente durante callback de resultado.
- Lote com adaptador em memória: deduplicação por caminho, resultados obsoletos ignorados, progresso separado de alterações estruturais, identidade dos itens, cancelamento e preservação das sessões concluídas.
- Veto da preparação do lote, snapshots, protocolo de verificação/exportação e repetição “Já salvo”, sem janela ou editor.
- Falha inesperada do worker reportada uma única vez, interrupção do lote, resultados anteriores conservados e bloqueio de novos trabalhos.
- Conversão real de PDF sintético em subprocesso com `QCoreApplication`, sem importar `PySide6.QtWidgets`; falha posterior não perde o resultado; hash da origem preservado; worker encerrado e diretório temporário removido ao fechar.
- Bindings de um componente QML mínimo refletem estado, nome do arquivo e progresso. As propriedades da fachada têm notificações e são somente leitura para QML.

O ensaio inicial do teste QML falhou durante a liberação manual de objetos pelo binding. O teste final explicita a propriedade Python do controlador e a hierarquia/lifetime dos consumidores QML, usando destruição adiada pelo Qt; a suíte completa acima passou após a correção. Isso reforça a necessidade de tratar ownership na futura integração da janela QML, sem indicar que o editor ou visualizador já foram migrados.

O protótipo visual continua demonstrativo. `.venv/bin/python prototypes/qml_import/run.py --check` passou, verificando carregamento, Tab, Espaço, Ctrl+O, clique e disabled, sem avisos QML. Nenhum seletor real foi conectado ao protótipo nesta etapa.

README, PROJECT_CONTEXT e plano da migração atualizados. Sem novas dependências, mudanças nos filtros, formatos de exportação ou comandos de execução. Apenas PDFs e destinos sintéticos utilizados; PDF pessoal e vaults reais intactos; sem commits. Conferência interativa no desktop/Obsidian, Python 3.12, hardware de 8 GB e desempenho continuam pendentes.

## Migração QML — importação e progresso integrados — 18/10/2026

Suíte completa final: **250 testes passaram em 57,73 s** com `.venv/bin/python -m pytest -q`.

A aplicação principal usa `ImportPanel`/`QQuickWidget` para a página inicial e o progresso individual. QML recebe somente valores simples e emite intenções para os fluxos Python existentes. A fachada/worker é a mesma antes e depois da importação; o editor e os diálogos de lote permanecem Widgets. Componentes visuais movidos para `src/pdf_obsidian/qml/` e compartilhados com o protótipo; recursos incluídos via package-data. Não existe um segundo Ctrl+O no componente embutido.

Onze casos novos em `tests/test_import_qml.py` verificam:

- Tab/Shift+Tab/Espaço, Ctrl+O sem disparo duplicado, cancelamento do seletor e abertura do diálogo de lote.
- Conversão real iniciada pelo botão QML, mesmo controlador/worker, integridade do PDF sintético, edição/desfazer no editor e ausência de exportação automática.
- Progresso indeterminado/determinado, cancelamento repetido e desabilitado, falha e retorno ao documento anterior com texto, seleção reversa, histórico e zoom preservados (dois casos parametrizados). A entrega de transporte nesses casos é controlada para não depender da velocidade do worker.
- PDF inválido com retorno à importação, e acesso a Documentos/Revisar após converter lote pela página inicial.
- QML ausente com recuperação Widgets que continua capaz de converter um PDF real sintético.
- Erro de cena gráfica simulado, preservação do worker/progresso, cancelamento pela recuperação Widgets e descarregamento adiado da cena falha.
- Fechamento durante conversão, encerramento do processo auxiliar e limpeza do diretório temporário.
- Mudança da fonte global em 25% chegando ao QML mesmo sob QSS, mantendo ações acessíveis em 1024 × 700.
- Recusa da confirmação de descarte e cancelamento posterior do seletor, sem perder documento, edição ou workspaces.

Regressões da fachada ampliadas para a propriedade notificada e somente leitura `cancellationRequested`, reset e idempotência. Testes antigos da apresentação foram adaptados aos estados reais do painel novo; não foram conservados controles Widgets invisíveis para satisfazer asserções anteriores.

A revisão encontrou e corrigiu o primeiro valor de progresso preso no limite anterior ao atualizar o total, e a fonte QML que não recebia a ampliação global devido à propagação de fontes sob QSS. `qmllint` dos recursos compartilhados e do wrapper demonstrativo passou sem diagnósticos. O `--check` do protótipo passou em 1120 × 760 e em 640 × 600 com `--text-scale 1.25`, sem avisos QML.

Capturas sintéticas inspecionadas em 1300 × 850 e 1024 × 700: importação, progresso indeterminado/determinado, cancelamento e editor após conversão real. Importação e progresso também conferidos com fonte ampliada em 25%. Os estados de progresso das capturas são controlados para permitir inspeção estável, enquanto conversão e falha reais são cobertas pelos testes. Capturas temporárias em `/tmp/qml-import-*.png`, sem avisos QML no ensaio.

Wheel construído offline com `python3 -m build --wheel --no-isolation --outdir /tmp/pdf-obsidian-qml-wheel`, usando ferramentas de build já instaladas no sistema (não foram instaladas dependências na `.venv`). Inspecionados os quatro recursos QML, confirmada ausência de PDFs e carregada a página a partir do wheel extraído fora do checkout, usando o ambiente PySide6 existente.

README, PROJECT_CONTEXT e documentos do protótipo/plano atualizados. Sem mudanças nos filtros, formatos de exportação ou dependências de execução. PDF pessoal e vaults reais não utilizados nem alterados; sem commits. Testes e capturas usam software/offscreen: desktop real, GPU, Wayland/X11, leitor de tela, Obsidian desktop/Android, Python 3.12 e hardware de 8 GB continuam pendentes.

## Janela completa Qt Quick/QML — 18/10/2026

A migração autorizada foi aplicada ao frontend padrão. A janela usa `QQmlApplicationEngine` e `ApplicationWindow`; há uma única `QApplication`, fachada e processo auxiliar. Somente seletores de PDFs/pasta são nativos. `--widgets` mantém o adaptador anterior para recuperação.

Validação final: `.venv/bin/python -m pytest -q` — **267 testes passaram em 61,99 s**. Os 250 testes anteriores permanecem; foram acrescentados 16 casos em `tests/test_quick_frontend.py` e uma regressão do protocolo em `tests/test_application.py`.

Cobertura nova:

- Editor Quick com documento Python durável, texto simples/HTML literal, Unicode com par substituto, seleção reversa, comandos/atalhos, edição nativa, desfazer/refazer e troca de sessões.
- Snapshot da apresentação antes de trocas disparadas tanto por QML quanto por Python: aba, visibilidade, posição de leitura e centro normalizado do PDF. Restaurações visuais adiadas possuem sequência para ignorar callbacks antigos.
- Prévia usando o mesmo construtor Qt de documentos, imagens proporcionais limitadas à largura disponível sem alterar o Markdown, modelo estável de incorporações, seleção por mouse/Espaço e preservação do delegado/foco ao marcar. Redimensionar conserva seleção e texto.
- Remoção manual em um bloco de desfazer, conservação dos anexos temporários e auditoria; restauração individual de imagem filtrada conserva seleção e pode ser desfeita.
- PDF com bitmap ativo versionado, pedidos agrupados, rejeição da página anterior durante o debounce, DPI inteiro, transformação do recorte e inclusão de metadados para exportação.
- Preparação de lote com deduplicação e remoção, sessões externas conservadas e nenhuma reconstrução/alteração de linhas durante progresso. Conversão e exportação reais de lote, segunda exportação “Já salvo” sem mudar os destinos.
- Exportação individual real no worker: snapshot identificado por token/sessão/revisão, bloqueio de edições, rejeição de resposta obsoleta, falha preservando alterações e registro somente no sucesso. Original sintético idêntico na saída e opção de marcadores aplicada só à cópia exportada.
- Conversão/recorte Quick com envelopes identificados; eventos atrasados e eventos legados sem token são recusados pela fachada nesse modo. O adaptador Widgets conserva seu protocolo para recuperação.
- Confirmações assíncronas, veto e cancelamento do seletor nativo, preservação do documento anterior, erro do worker sem perder o texto e possibilidade de encerrar após falha.
- Janela em 1024 × 700 com fonte +25%, diálogos dentro dos limites e captura não vazia. Os testes coletam também os avisos emitidos durante a carga da cena.

Durante o desenvolvimento, uma ligação contínua a `TextEdit.selectedText` em itens do menu provocou falha nativa do Qt ao executar um `QTextCursor` em bloco. A implementação usa apenas os limites de seleção para habilitar as ações; as operações de cópia/leitura são feitas sob comando. A regressão com edição pelo teclado e os testes completos passaram após essa correção. `contentsChanged` também pode ocorrer por layout: o adaptador invalida a prévia somente quando o texto simples muda.

Verificações adicionais:

- `pyside6-qmllint` em todos os componentes da aplicação e no wrapper do protótipo: saída limpa, sem avisos.
- Protótipo `prototypes/qml_import/run.py --check`: carga, Tab, Espaço, Ctrl+O, clique e disabled passaram, sem avisos QML.
- Wheel construído offline com `python3 -m build --wheel --no-isolation`. Descompactado em diretório temporário, carregou a janela QML padrão fora do checkout pelo launcher `gui.main`, confirmou encerramento e recursos `Main.qml`, componentes e `Tokens.js`. Nenhum PDF no pacote.
- Capturas de importação, editor, prévia/seleção, documentos, imagens filtradas, opções e links, com PDF sintético de cinco páginas: `/tmp/qml-complete-*.png`. Resoluções 1300 × 850 e 1024 × 700, fontes padrão e +25%; editor, prévia e diálogos inspecionados. São arquivos temporários, não necessários à execução.

Não foram utilizados o PDF pessoal nem vaults reais. Não houve commits, novas dependências de runtime, OCR, mudança de filtros ou formato exportado. Desktop/GPU, Wayland/X11, IME, leitor de tela, Obsidian desktop/Android, Python 3.12, hardware de 8 GB e cargas grandes continuam pendentes. Testes e capturas usam software/offscreen e PDFs sintéticos; não substituem esses aceites.

## Refinamento de escala e tipografia — 18/10/2026

Interface QML compactada (corpo 13 px, controles-base 30 px, título inicial 27 px), com legendas de 12 px. Markdown usa monoespaçada local mais refinada (prioridade JetBrains Mono/Adwaita Mono) e prévia usa a família sans da interface, em 14 px. A seleção de fontes consulta apenas famílias instaladas e conserva fallbacks nativos. A base da escala acompanha a fonte nativa na abertura, eliminando a ampliação acidental causada pela referência fixa de 9 pontos, e mantém aumentos relativos de fonte.

`.venv/bin/python -m pytest -q tests/test_quick_frontend.py tests/test_import_qml.py tests/test_appearance.py`: **32 testes passaram em 11,42 s**. Lint de todos os componentes QML limpo. Sem mudanças no conteúdo dos documentos ou nos fluxos de conversão/exportação. A conferência no desktop real continua pendente.

## Desempenho da transição e barra do editor — 18/10/2026

Relato do usuário: espera excessiva entre a conversão individual e a tela do editor; inconsistências na barra de ferramentas, botões e hover.

Diagnóstico reproduzido exclusivamente com PDF sintético de 100 páginas, 200.718 caracteres e 100 imagens filtradas. A conversão isolada ficou em 5,465 s antes e 5,471 s depois. Sob `cProfile`, o callback de entrega antigo consumiu 100,797 s: duas chamadas a `sync_filtered` executavam 200 validações de restauração e cerca de 400 análises completas de Markdown. O mesmo callback corrigido consumiu 0,105 s sob o mesmo profiler. Esses valores instrumentados identificam o gargalo; não devem ser apresentados como latência habitual no desktop, pois o profiler acrescenta overhead.

Medição sem profiler pelo novo `tools/benchmark_quick.py --pages 100`, usando o worker real e o primeiro frame QML: **5,785 s** para conversão/transporte, **0,294 s** da entrega ao primeiro frame do editor e **6,171 s** até o primeiro PDF visível. Software/offscreen; não mede GPU ou o PDF pessoal. O script gera e remove seu próprio PDF e workspace temporários.

Correções:

- Abertura do editor não constrói a prévia nem analisa imagens filtradas. A prévia é preparada ao abrir sua aba e reaproveitada até mudar o texto/fonte. Edição com a aba oculta não inicia o timer de reconstrução. O estado “Preparando prévia…” não exibe conteúdo antigo; a posição de leitura é restaurada após a construção adiada.
- A lista de imagens filtradas recebe metadados leves. Delegados solicitam a validação sob demanda, com uma única tarefa por vez no worker e prioridade para PDF/conversão/exportação. Resultados levam token, sessão, revisão e índice; respostas antigas não habilitam restauração. Fechar a lista elimina os pedidos ainda não enviados. Verificações ficam em cache por revisão; restaurar/undo invalida os estados imediatamente.
- `restoration.py` contém a função conservadora existente, movida sem alterações de lógica para permitir uso no worker sem importar a interface Widgets. O clique de restauração mantém a validação final do texto atual. Limiares, arquivos temporários, desfazer e regras de remoção não mudaram.
- Barra do editor com botões compactos, áreas mínimas de interação consistentes, negrito/itálico reconhecíveis e hover neutro de 100 ms. Abas deixam de usar o preenchimento coral de ação principal: recebem superfície neutra e marcador. Dicas somente nas ferramentas relevantes, com atraso de 650 ms, descrição e atalho; botões desabilitados não simulam hover ativo.

Cinco regressões novas cobrem ausência de análises na abertura/edição com prévia oculta, construção única e reaproveitamento da prévia, revisão assíncrona serial e rejeição de respostas obsoletas, revisão/restauração/desfazer no worker real, hover/clique preservando seleção/histórico e restauração da leitura após troca de sessão com prévia adiada. Casos anteriores foram ajustados para solicitar explicitamente os recursos que agora são preparados por demanda.

Lint QML e `prototypes/qml_import/run.py --check` passaram sem avisos. Wheel construído offline e janela padrão carregada fora do checkout, com todos os recursos locais e nenhum PDF no pacote. Capturas sintéticas `/tmp/qml-complete-*.png` conferidas em 1300 × 850 e 1024 × 700, com fonte padrão e +25%. Aceite no desktop real continua pendente; não foram usados PDFs/vaults pessoais nem criados commits.

Suíte completa após essas correções: `.venv/bin/python -m pytest -q` — **272 testes passaram em 64,02 s**. Acompanhamento da página e posição de leitura também são reaplicados quando a prévia é construída por demanda, preservando cursor/seleção e histórico.

## Clareza da importação — 18/10/2026

Removida a sequência numerada exclusiva da importação, que sugeria etapas acompanhadas pela aplicação. `ImportAction.showArrow=false` no cancelamento elimina a seta de avanço e conserva somente o X. Estados de cancelamento e demais ações intactos. Lint QML e checagem do protótipo passaram sem avisos; os 11 testes de integração da importação passaram em 6,23 s. Sem mudanças em PDFs, backend ou exportação.

## Barra compacta agrupada — 18/10/2026

- `ToolButton.qml` reaproveita os estados, dicas e foco de `ActionButton`, com ícones vetoriais locais de 18 px, área mínima de 30 × 30 px e indicador opcional de menu. Markdown/Prévia e desfazer/refazer permanecem na primeira linha. Estilo, texto e parágrafo quebram em grupos inteiros; separadores ficam invisíveis no início da linha. Sem detecção de formatação ativa ou mudanças no backend/exportação.
- Suíte existente completa: **272 testes passaram em 63,66 s**. A regressão adicional passou separadamente (**1 teste, 1,58 s**): menu por Espaço/setas/Enter, seleção reversa com Unicode, retorno do foco, desfazer, Tab, controles desabilitados na exportação e quebra de grupo em painel estreito.
- Capturas sintéticas `/tmp/toolbar-*.png` geradas em 1300 × 850 e 1024 × 700, fonte padrão/+25%, com painel PDF mostrado/oculto. Inspecionada a captura 1024 × 700/+25% com painel mostrado; limites dos controles verificados automaticamente em todas as combinações. O painel dessas capturas aguarda renderização; conversão/renderização reais continuam cobertas pela suíte e benchmark. Conferência interativa desktop/GPU e dicas no desktop permanece pendente.
- Benchmark sintético real de 100 páginas: conversão/transporte **5,698 s**, entrega → primeiro frame **0,367 s**, até PDF visível **6,249 s**, software/offscreen. Nenhum PDF pessoal utilizado. Lint QML limpo.
