# Contexto do projeto PDF-Obsidian

Estado atualizado em 24/10/2026, após modernização visual, estabilização técnica e implementação do OCR local. O histórico abaixo registra etapas de desenvolvimento; o estado atual prevalece sobre os relatos anteriores.

## Auditoria de UI e correções — 24/10/2026

- Usuário pediu auditoria da UI e autorizou corrigir todos os pontos, **usando Git para manter o histórico** (substitui a restrição anterior de não fazer commits nesta etapa; push não foi solicitado).
- Quick/QML: ferramentas compactas desabilitadas sem caixa de borda; `Documentos (N)` e `Opções` bloqueados durante salvamento; campos de página/zoom acompanham a escala de fonte; feedback antigo da importação oculto/limpo ao iniciar conversão; diálogo de link com foco inicial adequado e Enter para avançar/inserir; Ctrl+Z/Ctrl+Y funcionam na aba Markdown com foco fora do editor; `Ocultar PDF`/`Acompanhar página` desabilitados durante o lote; listas reservam espaço para a barra de rolagem; documentos salvos e depois editados exibem `· Não salvo`.
- Widgets: indicador de menu nativo removido (rótulos `Listas ▾`/`Alinhar ▾`), separador órfão e stretch interno da barra removidos; rodapé único em imagens filtradas; OCR do lote alinhado à esquerda e foco inicial em Adicionar PDFs; Abrir/Salvar/opções permanecem disponíveis durante a renderização de página; captura `widgets-editor.png` sem estado sintético de renderização.
- Regressões novas em `tests/test_quick_frontend.py` e `tests/test_appearance.py`; suíte completa com **385 testes em 102,19 s**, protótipo QML 800 × 600/+25% sem avisos. Capturas sintéticas em `/tmp/pdf-obsidian-ui-audit/` (descartáveis). Nenhum PDF pessoal ou vault real utilizado.

## Refinamento visual após revisão frontend-design — 24/10/2026

- Implementadas as melhorias aprovadas de `UI_REVIEW.md`: diálogo de links Widgets com largura preferida de 480 px e campos verticais expansíveis; foco contrastante dos primários; abas sublinhadas próprias; chevron nos avisos; barras com menos espaços verticais; listas de mídia mais compactas; hierarquia de formulário/título; estado vazio orientativo e remoção de mensagem duplicada da importação.
- `FocusRing.qml` mantém anel externo de 2 px com intervalo escuro nos primários Quick. Widgets usa inversão de superfície/texto com borda branca no foco, mantendo dimensões. `TabButton.qml` preserva comandos, nomes acessíveis, foco e navegação por setas. Tokens semânticos de ícones: ferramentas 20, estado 14, importação 22, chevron 12; recursos SVG/fontes intactos.
- Preservados títulos da prévia e mensagem completa de OCR: o ganho de área veio das barras, sem alterar documento/renderização. Nenhuma mudança de processamento, publicação, seleção, desfazer/refazer ou filtros. Alterações anteriores mantidas, sem commits/pushes.
- Validação: 78 testes direcionados em 28,66 s e suíte completa com **380 testes em 86,60 s**; checagem adicional após o ajuste final de foco Widgets registrada em `VALIDATION.md`. Lint QML e protótipo/teclado passaram. Capturas sintéticas em `/tmp/pdf-obsidian-design-refinement/`, com amostras conferidas; foco Quick também em `/tmp/pdf-design-focus.png`. Documentação atualizada em `DESIGN_SYSTEM.md` e `UI_REVIEW.md`. Aceite desktop/GPU e acessibilidade real continuam pendentes.

## Auditoria de produto e confiabilidade — 24/10/2026

- Auditoria e priorização registradas em `AUDIT.md`, com escopo, funcionalidades existentes, limitações e próximos passos. Preservados arquitetura, identidade monocromática, filtros, histórico, anexos relativos e publicação sem sobrescrita.
- Exportação bloqueia links simbólicos nos anexos temporários (raiz, subpastas e arquivos) antes de criar staging, evitando copiar arquivos externos inesperados. Não altera temporários ou originais.
- Estado OCR trata manifestos JSON com estrutura inválida, hashes malformados e caminhos resolvidos para fora da pasta de recursos como indisponíveis. Mensagem explica preservação de texto nativo/imagens e preparação/reparo; SHA-256 integral continua antes de usar os modelos.
- Status OCR reativo compartilhado diferencia modo desligado da disponibilidade, inclusive importação/lote/opções. Recuperação Widgets mostra etapa de OCR e espera de cancelamento. README corrigido onde ainda negava OCR/LaTeX. Digest preexistente incorreto de `fonts/OFL.txt` corrigido no manifesto após confirmar igualdade do arquivo com HEAD; licença/fontes inalteradas.
- Validação final: **380 testes em 86,61 s**, lint QML, protótipo/teclado, compileall, pip check e diff limpos. 174 capturas geradas com documentos sintéticos, amostras inspecionadas; benchmark real de 100 páginas: 7,148 s conversão/transporte, 0,824 s entrega → frame, 8,179 s até PDF. Sem alegação de ganho de desempenho. Detalhes em `VALIDATION.md`.
- **Estado deste ambiente:** o `.venv` estava ausente e foi recriado para a auditoria; os modelos/ambiente OCR real NÃO estão preparados neste checkout. As afirmações abaixo de preparação local são históricas. OCR real, Python 3.12, empacotamento wheel e memória não foram revalidados nesta etapa; desktop/GPU, IME, leitor de tela e Obsidian continuam pendentes.
- Nenhum PDF pessoal/vault real utilizado, commit ou push realizado. O usuário proibiu commits/pushes automáticos nesta missão; isso prevalece sobre a intenção histórica de envio registrada abaixo.

## OCR local e reconhecimento estruturado — 24/10/2026

- O usuário autorizou e solicitou OCR, substituindo explicitamente a restrição anterior de fora do escopo. Escolhas: automático conservador, páginas mistas, português/inglês, texto/tabelas/fórmulas, estrutura junto à imagem preservada, CPU/8 GB, qualidade equilibrada, dependências/modelos preparados na instalação do projeto sem Tesseract separado. Não foi solicitado instalador portátil.
- Implementados contratos `ConversionOptions(auto/off)`, auditoria opcional em `ConversionResult.recognition`/`conversao.json` e transporte compatível nos comandos individual/lote. Opções capturadas no início e bloqueadas durante processamento. Etapa real por página em QML e Widgets; nenhum OCR sobre documentos já editados.
- Docling 2.142.1, RapidOCR 3.10.0/ONNX Runtime 1.31.0, TableFormer fast e CodeFormulaV2 em subprocesso próprio. Ambiente e modelos já preparados em `.venv/share/pdf-obsidian/ocr/`; console `.venv/bin/pdf-obsidian-prepare-ocr --verify`. Python/fonte da interface continuam separados. Modelos (~1,1 GiB) e ambiente OCR (~1,7 GiB) são locais/ignorados, não entram em commits. Dependências e commits fixados em recursos textuais publicáveis; licenças incluídas.
- Reconhecimento só em regiões candidatas, sem substituir texto nativo confiável. Imagens uniformes e páginas apenas digitais não carregam modelos. Tabelas simples em Markdown, mescladas em HTML restrito, fórmulas em LaTeX. Imagens envolvidas em OCR continuam incorporadas, inclusive scans de página inteira. Resultados inválidos/conflitantes preservam a referência e geram aviso. A prévia Qt não ganhou renderizador matemático; LaTeX pode aparecer como texto.
- Rede IP bloqueada no auxiliar, serviços/plugins remotos desativados. Verificação SHA-256 dos modelos antes do uso, timeout de 180 s/página e orçamento de 4 GiB RSS no auxiliar. Cancelamento encerra o grupo do subprocesso; morte do worker encerra o auxiliar no Linux. Temporários e log OCR permanecem no workspace durante a sessão e não são exportados.
- Benchmark sintético real de 20 páginas (19 OCR, 1 nativa), com páginas mistas sem duplicação de texto: 91,288 s; estimativa conservadora de pico total 3.297.906.688 bytes, abaixo de 6 GiB. Cancelamento real em 0,089 s com reutilização do worker. Reconhecimento real também passou em Python 3.12.15, além do 3.14.8 local. Detalhes, limites e resultados finais em `VALIDATION.md`.
- Desempenho: PDFs escaneados/mistos podem demorar significativamente mais; o primeiro reconhecimento carregou modelos e levou 38,210 s, páginas OCR seguintes ~2,5–2,7 s no benchmark de 20 páginas. Texto digital puro e imagens uniformes não carregam os modelos: 100 páginas digitais passaram pelo caminho rápido em ~6,1 s. OCR automático pode ser desligado na importação, no lote ou em Opções. Tempos dependem do hardware/documento.
- Novos recursos e preparação em `OCR.md`; ferramenta `tools/benchmark_recognition.py` usa apenas entradas geradas. PDF pessoal, vaults reais e originais não foram usados/alterados. Filtro de margens, histórico, restauração, navegação e anexos relativos preservados. Persistência de sessão, manuscritos, tradução e interpretação de gráficos continuam fora do escopo.

## Monochrome Premium — redesign completo, 24/10/2026

- Implementado o plano completo aprovado: manter Qt Quick/QML e recuperação Widgets, identidade estritamente monocromática, fontes Geist incluídas e contornos por grupo de ferramentas. Sem sidebars novas, Live Preview, metadados ou novas etapas de exportação.
- Tokens de cores/métricas/tipografia compartilhados; fundo `#090909`, superfície `#141414`, elevada `#1C1C1C`, divisórias `#303030`, texto `#F5F5F5` e secundário `#A3A3A3`. Controles de 32 px, labels de 13 px, corpo de 14 px, documentos de 15 px e escala de fonte/DPI preservada. Documento de referência em `DESIGN_SYSTEM.md`.
- Geist Sans e Mono 1.8.2 (12 fontes estáticas com pesos/itálicos), 39 SVGs Lucide 1.61.0 e licenças incluídos no pacote, aproximadamente 1,9 MB. `assets/manifest.json` registra fontes e hashes; `visuals.py` compartilha registro de fontes, ícones QtSvg com cache limitado e preferências visuais. Nenhum download durante o uso ou nova dependência de runtime.
- Importação sem cards aninhados; cabeçalho e comparação preservam fluxos; barras em grupos delimitados; campos, checkboxes, menus, scrollbars, listas e diálogos padronizados. Documentos do lote usam linhas/divisores. Mensagens QML são selecionáveis, com títulos/ícones semânticos e ações fixas; símbolos padrão das mensagens Widgets também são monocromáticos. Conteúdo original dos PDFs e figuras conserva as cores.
- “Reduzir movimento” disponível em Opções e na recuperação Widgets, compartilhado no processo e sem persistência. Desativa transições e movimento indeterminado; valor inicial respeita a desativação de animações informada pelo estilo Qt. Qt 6.11 não oferece a preferência universal de movimento do Qt 6.12; não atualizar dependências para esse recurso.
- Inspeção com documentos sintéticos identificou aviso de posição fora do documento ao substituir prévia com imagens. Corrigida somente a ordem de descarte das marcações visuais antes de instalar a prévia vazia/nova, com guarda de geometria e regressão específica. Texto, seleção, histórico e regras de processamento preservados.
- `tools/visual_review.py` reproduz a inspeção com documentos temporários próprios e fixtures visuais de progresso/falha (168 capturas Quick e 6 Widgets). Capturas em `/tmp/pdf-obsidian-premium-final/` são descartáveis; não são requisitos da aplicação. Testes e benchmark validam separadamente o worker real. Evidências finais em `VALIDATION.md`.
- Originais, temporários, filtro autorizado, restauração, navegação, referências relativas, contratos do worker e formatos exportados permanecem. Nenhum PDF pessoal/vault real usado, commit ou envio ao remoto realizado. Aceite de desktop/GPU, IME e leitor de tela continua pendente.

## Legibilidade das ferramentas — 24/10/2026

- Usuário relatou contornos difíceis de distinguir e ícones simplificados após o tema monocromático. Ferramentas QML agora mantêm borda visível em repouso, borda mais clara no hover e foco de teclado de 2 px. Tokens de contorno de controle separados das divisórias; estados desabilitados seguem discretos.
- Ícones QML ampliados para 20 px com traço de 1,9 unidades; redesenhados negrito, itálico, link, marcadores, numeração, citação e desfazer/refazer. Sem imagens geradas, dependências, alteração de comandos ou conteúdo. Recuperação Widgets recebeu contornos nas ferramentas, traço reforçado e citação refinada.
- Validação: 68 testes pertinentes passaram em 18,12 s; lint de todos os QML e `git diff --check` sem diagnósticos. Capturas sintéticas em `/tmp/pdf-obsidian-editor-icons/`, 24 combinações de tamanho, fonte, PDF e aba; amostras da edição em 800 × 600/+25% e 1300 × 850 inspecionadas. Aceite interativo permanece pendente.

## Tema monocromático global — 24/10/2026

- O usuário ampliou a aplicação da identidade monocromática para toda a aplicação. Esta decisão substitui a restrição anterior à revisão: importação, progresso, menus, diálogos e recuperação Widgets agora compartilham a mesma paleta em `Tokens.js`.
- Removida a seleção contextual de paleta e a duplicação de cores de revisão. Estados hover/pressionado, barras de rolagem, checkboxes e placeholder Widgets usam cores neutras; seletores nativos de arquivos/pastas continuam seguindo o sistema operacional.
- Preservados o layout e a tipografia de cada tela, recursos de revisão, documentos, histórico, filtros e exportação. Capturas de conferência em `/tmp/pdf-obsidian-global-monochrome-import.png` e `/tmp/pdf-obsidian-global-monochrome-widgets.png`, descartáveis e sem documentos reais. Aceite interativo continua pendente.

## Revisão monocromática — 24/10/2026

- Implementada a direção escolhida: visual e leitura próximos do Obsidian, escuro monocromático, abrangendo a tela de revisão. Sem Live Preview, abas adicionais ou barras laterais. Tema da importação e frontend Widgets preservados.
- Tema contextual em `Theme.qml`, tokens de revisão compartilhados com Python, coluna centralizada de até 760 px lógicos, margens mínimas de 16 px e texto-base de 15 px escalável. Prévia com espaçamento de leitura e links neutros, configurados somente no documento de apresentação.
- `MarkdownHighlighter` por documento durável Quick, sem mudanças no texto/histórico; estados incrementais para cercas e comentários e offsets UTF-16. Cabeçalho discreto e estados com símbolos/texto. Sem dependências novas, mudança de filtros ou uso de PDFs pessoais.
- Validação: suíte completa com 330 testes em 61,52 s, mais uma regressão Quick nova aprovada separadamente (331 casos distintos). Lint QML e diff sem diagnósticos. Capturas sintéticas em `/tmp/pdf-obsidian-monochrome-final/` (descartáveis). Aceite interativo em desktop continua pendente. Resultados finais em `VALIDATION.md`.

## Retomada nas próximas sessões

- A implementação solicitada foi concluída. Não há correção automática pendente do plano de estabilização; o próximo passo é o aceite interativo do usuário no desktop e no Obsidian. Não tratar registros antigos de 275/287 testes ou dependências antigas como estado atual.
- Abrir com `.venv/bin/pdf-obsidian`; alternativa de renderização: `QT_QUICK_BACKEND=software .venv/bin/pdf-obsidian`. O frontend padrão é Qt Quick/QML; `--widgets` mantém a interface de recuperação. O `.venv` local já está atualizado e a instalação é editável, apontando para `src/`.
- Validação atual de OCR: **366 testes** na suíte, compatibilidade Python 3.12/3.14, reconhecimento real, cancelamento, lint QML, protótipo e carregamento de wheel fora do checkout. Resultados finais e tempos em `VALIDATION.md`. Os testes não substituem aceite em GPU/desktop, IME, leitor de tela, Obsidian desktop/Android e hardware físico de 8 GB.
- A modernização visual, estabilização, OCR local e documentação associada serão enviadas em um commit nesta branch `main`; os modelos e ambientes OCR locais ficam fora do Git. Não incluir o PDF pessoal da raiz. Preserve qualquer alteração local que apareça após esse envio.
- A auditoria anterior está no histórico da conversa; não existe um relatório completo separado criado nesta etapa no repositório. As decisões, correções e resultados efetivos estão resumidos abaixo e em `VALIDATION.md`.
- Capturas, wheels, ambientes isolados e scripts auxiliares em `/tmp` são descartáveis e podem não existir em outra sessão. A aplicação e a suíte não dependem desses artefatos. Use PDFs sintéticos ao repetir verificações; nunca utilize o PDF pessoal da raiz nem um vault real para regressões.
- Preservar as decisões já aprovadas: aplicação local/offline; nenhuma sobrescrita de publicação anterior; nova cópia ao detectar saída divergente; bloquear `Importados` externo ao vault. Manter filtro de imagens nos limites autorizados, restauração individual, histórico, navegação e anexos relativos. OCR foi autorizado e implementado conforme a seção atual; persistência entre sessões continua fora do escopo.

## Estabilização técnica — 23/10/2026

- Implementadas as correções da auditoria, preservando a modernização QML preexistente. Dependências fixadas em PyMuPDF/MuPDF 1.28.2 e PySide6/Qt 6.11.2; validação inicial em ambiente isolado e atualização do venv local. O aplicativo permanece offline; downloads ocorreram apenas para preparação do ambiente.
- Decisões do usuário: publicação anterior divergente deve ser preservada, com nova saída sem sobrescrita; links de `Importados` para fora do vault devem ser bloqueados. Reutilização agora valida um manifesto de tamanhos/SHA-256 de todos os arquivos publicados, capturado no staging antes da publicação e mantido somente em memória. Extras do usuário são ignorados na comparação. Quick e lote recebem o manifesto do worker; Widgets compartilha a validação em seu fluxo síncrono. Publicação/limpeza ancoradas a descritor de diretório Linux e destino reconferido antes do rename sem substituição.
- Conversão usa geometria visual consistente com os pixmaps em todas as rotações, incluindo CropBox deslocado e espaçamento entre spans rotacionados. Detector de tabelas recebe a página temporariamente sem rotação apenas em memória, evitando que a biblioteca redefina o CropBox. Figuras válidas menores que oito pontos são preservadas.
- Estado pendente da sessão inclui as opções exportáveis independentemente do histórico textual. Desfazer texto não apaga o aviso de opção não salva; retornar à opção exportada pode limpar o aviso. Confirmar/cancelar/falhar resolve callbacks uma vez; notificações informativas aguardam confirmações, erros cancelam a confirmação anterior. Divisão dos painéis restaura a largura efetiva após interação por teclado ou arraste.
- Marcadores de página respeitam código/YAML/HTML protegido na navegação e prévia. Agrupamento de imagens recorrentes mantém extremos incrementais e aceita cancelamento. Filtro continua limitado aos 10% superiores/inferiores, três páginas e 70%, mesma identidade/posição; restauração, histórico e temporários preservados. Sem OCR ou persistência entre sessões.
- Validação final: **327 testes passaram em 75,10 s**; lint QML, protótipo, dependências e wheel fora do checkout passaram. Testes, evidências e limitações desta etapa estão em `VALIDATION.md`. PDFs e vaults reais não foram utilizados; sem commits.

## Modernização da revisão e consistência visual — 23/10/2026

- Implementado o plano de refinamento da interface principal QML, preservando a direção aprovada (grafite/coral, fonte compacta de 13 px, alternativas locais, DPI/fonte ampliada) e a recuperação Widgets. Sem novas dependências, serviços, persistência ou mudança nos formatos exportados.
- Tokens compartilhados passaram a incluir cores semânticas de sucesso/atenção/erro, seleção/overlay, tamanho de ícone, margens de leitura/diálogos e duração das transições. Componentes locais padronizam menus/itens/separadores, tooltips, progresso, estados e rodapés de diálogo. Rótulos de interface usam texto simples, sem interpretar nomes/mensagens como HTML.
- Cabeçalho e controles do PDF extraídos para `DocumentHeader.qml` e `PdfToolbar.qml`. Cabeçalho usa espaço disponível e fonte para reorganizar ações; título longo fica abreviado com caminho completo na dica/acessibilidade. PDF original identificado; página e zoom/ajuste quebram em grupos completos, zoom com `%`. Divisão 40/60, ocultação e ausência de sidebar permanente preservadas.
- Avisos com superfície de atenção própria (avisos gerais não exibem “Página 0”); salvamento, falhas e exclusão da exportação com texto/indicadores; seleção manual contextual com ação destrutiva e orientação de desfazer. Foco visível nas imagens selecionáveis, abas com papel acessível e navegação por setas, divisória ajustável também por teclado.
- Diálogos de lote/documentos/imagens filtradas/links/opções/mensagens/confirmações refinados. Ações em rodapé independente do conteúdo rolável; mensagens extensas limitadas à janela. Descarte começa no Cancelar; retorno do foco ao invocador. Esc continua cancelando o lote mesmo com foco no rodapé, esperando o worker terminar.
- Inspeção encontrou o cursor inicialmente no fim de documentos longos: Quick reposicionava o cursor quando o editor se tornava visível/editável. Restauração agora ocorre após atualizar esses bindings, com posição explícita também para seleção vazia. Regressões verificam abertura no início, retorno ao cursor sem seleção e preservação de seleção reversa/Unicode/histórico. Mudança restrita à integração visual; não recriar documentos Qt.
- Filtros e seus limites, originais, temporários de recuperação, histórico, edições, referências relativas, navegação, exportação individual/lote e reutilização de saída permanecem. Prévia e revisão de imagens continuam sob demanda; sem OCR ou novas ferramentas de metadados/reordenação além do Markdown existente.
- Suíte final: **287 testes passaram em 69,61 s**; lint QML/protótipo e wheel offline carregado fora do checkout passaram sem avisos QML. Benchmark sintético de 100 páginas: 0,471 s entrega → primeiro frame, comparado a 0,473 s no código anterior; medições pontuais em software/offscreen. Validações e evidências desta etapa estão em `VALIDATION.md`. Capturas e documentos/vaults de verificação são exclusivamente sintéticos; PDF pessoal e vaults reais não foram utilizados. Desktop/GPU, IME, leitor de tela e Obsidian continuam exigindo aceite interativo.

## Preparação para publicação

- Destino GitHub: `tauan-dias/pdf-obsidian`, privado; branch `main` e remoto `origin` por HTTPS. Autoria Git local usa endereço noreply. Credenciais da CLI estão no cofre do sistema, fora do repositório.
- Documentação publicável conserva decisões técnicas, resultados sintéticos e pendências. Registros originais de desenvolvimento ficam em `.local/private-docs/`, ignorados e exclusivos deste checkout; não são requisitos da aplicação.
- PDFs de entrada, credenciais, configurações privadas, ambientes virtuais e saídas locais não devem entrar em commits. Os testes geram seus próprios PDFs sintéticos. Recursos QML e imagens legítimas do aplicativo continuam publicáveis.
- Publicação do código não altera o funcionamento local/offline, os formatos exportados ou a licença AGPL-3.0-only. Não publicar documentos de terceiros nem usar seus conteúdos em exemplos ou capturas.
- Primeiro commit preparado com 78 arquivos auditados. Gitleaks sem achados; suíte com 275 testes passou no checkout original e no clone limpo, sem PDFs privados. Detalhes e limites em `VALIDATION.md`. Ferramentas e relatórios locais ficam em `.local/`, ignorados.

## Consistência de navegação, zoom e salvamento — 18/10/2026

- Implementado o plano solicitado após a inspeção de melhorias: campos numéricos QML confirmam com Enter ou perda de foco, uma vez por edição; valores inválidos/vazios voltam ao valor efetivo. Novo `NumericField.qml` compartilha essa regra, mantém o vínculo com página/zoom e fica desabilitado durante operações bloqueantes.
- Zoom Quick passa a usar 100 dpi para 100%, como documentado e no frontend Widgets. Ajustes automáticos atualizam o percentual com o DPI inteiro solicitado, respeitando 25–300; +/− parte dessa escala e entra no modo manual. Redimensionamento invalida renderizações anteriores durante o debounce. Página, troca de sessão e recuperação de erro recalculam o ajuste.
- Usuário escolheu reutilizar a saída ao salvar individualmente um estado idêntico no mesmo vault. Worker compara assinatura e pasta existente com o registro da sessão, usando a regra do lote; informa “Documento já salvo”. Alterações, outro vault ou pasta removida geram nova gravação sem sobrescrever. Sem nova persistência ou mudança no formato exportado.
- Protocolo interno `session_export` inclui o registro anterior no comando e um indicador de reutilização na resposta. Snapshot, token/sessão/revisão e tratamento de falha permanecem; os produtores/consumidores e testes foram atualizados juntos.
- Novas regressões de teclado/foco/validação e escala; integração com worker real ampliada para repetição sem nova pasta, mudanças de texto/opção, outro vault, pasta removida e reutilização de saída de lote. Documentos/vaults exclusivamente sintéticos. Conferência interativa no desktop continua pendente. PDF pessoal não utilizado; sem commits ou mudanças de filtros/OCR.
- Verificação final: `.venv/bin/python -m pytest -q` — **275 testes passaram em 68,12 s**. Lint dos QML e `prototypes/qml_import/run.py --check` passaram sem avisos, com renderização software/offscreen.

## Barra compacta agrupada — 18/10/2026

- Plano implementado: Markdown/Prévia e desfazer/refazer vetoriais na primeira linha; Estilo fixo (Parágrafo/H1–H6), texto (negrito/itálico/link), parágrafo (listas/citação diretas e alinhamento em menu). Grupos inteiros em Flow, separadores somente entre grupos na mesma linha.
- Novo `ToolButton.qml` baseado em `ActionButton`, ícones locais de 18 px e área mínima de 30 px, dicas/atalhos, hover/foco/disabled preservados. Sem estado de formatação ativa, análise ao mover cursor, dependências ou mudanças no backend/exportação.
- 272 testes existentes passaram em 63,66 s; nova regressão de teclado/menu, Unicode reverso, foco, histórico, escala, layout e disabled passou separadamente. Lint limpo. Benchmark de 100 páginas: 0,367 s entrega → primeiro frame, 5,698 s conversão/transporte, 6,249 s até PDF visível (software/offscreen).
- Capturas/limites sintéticos nas dimensões solicitadas; ver detalhes e limites em VALIDATION.md. Desktop interativo permanece pendente. PDF pessoal intacto, sem commits.

## Ajuste da importação — 18/10/2026

- Usuário apontou a sequência 01 Importar / 02 Revisar / 03 Salvar, exibida somente na importação, e os ícones contraditórios do cancelamento. Sequência numerada removida, pois não representava um indicador de progresso persistente. A descrição do fluxo e o rodapé local/offline permanecem.
- `ImportAction.showArrow` permite ocultar a seta de avanço. Cancelar conversão mantém somente o X; abrir/importar e lote conservam suas setas. Cancelamento e estados Cancelando/desabilitado não mudaram. Ajuste compartilhado pela aplicação, recuperação de importação e protótipo.

## Correção da transição e ferramentas do editor — 18/10/2026

- Usuário relatou grande lentidão entre conversão individual e editor e especificou inconsistências na barra de ferramentas, botões e hover. Corrigidos os dois pontos, preservando a direção visual aprovada.
- Gargalo confirmado com PDF sintético de 100 páginas/200.718 caracteres/100 imagens filtradas: o adaptador chamava `sync_filtered` duas vezes, fazendo 200 validações e cerca de 400 análises integrais de Markdown na thread da interface. No cProfile, a entrega consumia 100,797 s antes e 0,105 s depois. São valores instrumentados com overhead, não latências usuais do desktop. A conversão isolada permaneceu em ~5,5 s.
- `tools/benchmark_quick.py --pages 100` mede o worker real e o primeiro frame, gera/remove seus próprios PDFs e força software/offscreen: conversão/transporte 5,785 s; entrega → primeiro frame do editor 0,294 s; até PDF visível 6,171 s. Não usa o documento pessoal e não demonstra desempenho em desktop/GPU.
- Prévia agora é preparada por demanda ao abrir a aba, com `setPreviewVisible`, estado “Preparando prévia…” e reaproveitamento até mudar texto/fonte. Editar com Markdown aberto não reconstrói a prévia oculta. Leitura e acompanhamento são reaplicados após a construção adiada; não substituir documentos de edição nem perder históricos.
- Imagens filtradas: `openFiltered` cria só metadados; os delegados pedem `reviewFiltered(index)`. Uma tarefa por vez no worker (`review_filtered`/`filtered_checked`), com prioridade para renderizações/operações e cache por revisão. Token/sessão/revisão/índice rejeitam respostas antigas. Enquanto verifica, Restaurar permanece desabilitado. `closeFiltered` limpa pedidos ainda não enviados. Não voltar a validar todas as imagens sincronicamente ao abrir/trocar/editar documentos.
- `restoration_edit` foi movida, sem mudar a lógica conservadora, para `restoration.py` (sem Qt); `filtered_images.py` reexporta a função para compatibilidade Widgets. A ação de restaurar mantém a validação final do texto atual. Filtros, limiares, recuperação, desfazer/refazer e exportação intactos.
- `ActionButton` ganhou modo compacto, aba selecionada neutra com marcador coral, hover explícito suave (100 ms), dicas sem duplicar rótulos e com atraso de 650 ms/atalhos, estados disabled/focus consistentes e rótulos B/I estilizados. A barra do editor usa esse modo; Salvar no vault continua a ação primária coral. Não ampliar novamente escala/tipografia por causa dessa correção.
- Suíte completa: **272 testes passaram em 64,02 s** (cinco regressões novas, casos anteriores adaptados ao carregamento sob demanda). Lint e protótipo passaram sem avisos. Wheel offline carregou a janela padrão fora do checkout; recursos completos, nenhum PDF. Capturas sintéticas conferidas em 1300 × 850 e 1024 × 700, fonte padrão/+25% (`/tmp/qml-complete-*.png`). Detalhes em VALIDATION.
- PDF pessoal/vaults reais não utilizados; sem commits, novas dependências ou OCR. Próximo passo é o usuário conferir a melhora e o hover no desktop; permanecem pendências de GPU, IME, leitor de tela, Obsidian, Python 3.12, hardware de 8 GB e cargas reais.

## Refinamento de escala e tipografia — 18/10/2026

- Usuário gostou da migração, mas considerou a escala grande e pediu tipografia mais bonita. Interface reduzida de 14 para 13 px, títulos iniciais de 30 para 27 px, controles-base de 32 para 30 px e botões com menor espaçamento interno. Legendas continuam em 12 px; Markdown em 13 px e prévia em 14 px.
- Escala QML agora usa como referência a fonte nativa na abertura, em vez de uma base fixa de 9 pontos que ampliava a interface em sistemas com fontes maiores. Mudanças relativas de fonte e escala de DPI do Qt continuam respeitadas.
- Famílias escolhidas entre fontes já instaladas: Inter → Adwaita Sans → Cantarell → Noto Sans → fonte nativa na interface/prévia; JetBrains Mono → JetBrainsMono Nerd Font Mono → Adwaita Mono → Noto Sans Mono → monoespaçada nativa no Markdown. Neste ambiente, Adwaita Sans e JetBrainsMono Nerd Font Mono estão disponíveis. Sem downloads/dependências novas.
- Verificações pertinentes: 32 testes passaram (Quick, integração da importação e aparência); lint QML sem avisos. Não há alteração do conteúdo, histórico, PDFs, filtros ou exportação. Validação visual no desktop pelo usuário permanece pendente.

## Estado atual — janela completa QML implementada

- Usuário autorizou aplicar a migração a todas as telas e pediu implementar o plano. O comando habitual `.venv/bin/pdf-obsidian` agora abre `qml/Main.qml` por `QQmlApplicationEngine`, com uma única `QApplication`, fachada e worker. `gui.Window`/Widgets permanece disponível com `.venv/bin/pdf-obsidian --widgets` para recuperação e regressões, sem ser instanciado no caminho padrão. Alternativa de renderização: `QT_QUICK_BACKEND=software .venv/bin/pdf-obsidian`.
- Importação/progresso, preparação de lote, lista/resumo de documentos, PDF, editor Markdown, prévia, ferramentas, imagens filtradas, links, opções, mensagens e confirmações estão em QML. Somente seletores de PDFs/pasta do vault continuam nativos. Não há sidebar permanente; divisão inicial 40/60 ajustável, PDF ocultável e lista modal Documentos (N).
- `quick.py`: adaptador Python de sessões/comandos, empréstimo de `QTextDocument` por `QQuickTextDocument.setTextDocument`, com layout QtGui apropriado ao Quick. Não substituir texto inteiro para trocar arquivos. Documentos têm propriedade do controlador; seleção reversa, Unicode, desfazer/refazer, opções e auditoria permanecem por sessão. Snapshot solicita o estado visual QML antes de trocar, inclusive em ativações disparadas por Python. Restauração adiada tem sequência contra callbacks antigos.
- `quick_models.py`: `RowsModel` com IDs estáveis, inserções/remoções/movimentos pontuais e notificações somente dos papéis alterados. Progresso não reconstrói a lista. Incorporações da prévia também têm modelo estável, conservando foco ao selecionar por teclado.
- `PageProvider` fornece somente um `QImage` ativo e URLs versionadas. PyMuPDF permanece no worker, sem QtPdf/WebEngine. Renderizações são agrupadas e rejeitam pedidos antigos, inclusive durante o debounce; bitmap temporário é removido após carregar. Recorte usa coordenadas normalizadas sobre a imagem. Página/zoom, rolagem/centro do PDF, seleção, abas, divisão, acompanhamento e avisos são restaurados por sessão.
- Prévia usa `comparison.preview_document`, preservando alinhamentos/âncoras. Imagens são redimensionadas somente no documento de apresentação para caber na largura; fonte Markdown/anexos não mudam. Remoção manual e restauração usam as regras existentes e um bloco de desfazer. Arquivos temporários continuam disponíveis para recuperação até encerrar.
- Exportação individual Quick agora roda no worker (`session_export`) com snapshot, token, sessão e revisão; edição bloqueada durante a gravação e registro somente após sucesso. Sem exportação automática. Lote continua na mesma fila, com assinaturas e “Já salvo” existentes. Conversão/recorte do caminho Quick usam envelopes com token; fachada rejeita eventos obsoletos/sem token nesse modo. Protocolo Widgets conservado para recuperação.
- Tokens de cores e métricas únicos em `qml/components/Tokens.js`, consumidos como JSON pelo Python (`tokens.py`, sem eval) e pelo QML. Novos componentes compartilhados `ActionButton`, `Field`, `Toggle` e `SurfaceDialog`; fonte nativa e escala explícita da tipografia, foco visível e estados de interação. Nenhuma dependência de runtime nova.
- Atenção à integração Qt: `contentsChanged` pode vir apenas do layout; invalidar a prévia somente se o texto simples mudou. Evitar bindings contínuos a `TextEdit.selectedText` durante `QTextCursor` em bloco (provocaram falha nativa); usar limites de seleção para habilitar ações. Destruir a cena antes dos documentos Python; `engine.destroyed` encerra timers/runtime, sem liberação manual por shiboken.
- Validação final: **267 testes passaram em 61,99 s** (17 novos). Lint de todos os QML e `--check` do protótipo passaram sem avisos. Worker real testado com conversão/renderização/recorte/exportação individual e lote, repetição “Já salvo”, originais sintéticos idênticos. Wheel construído offline e janela padrão carregada fora do checkout; recursos completos, nenhum PDF no pacote. Detalhes em `VALIDATION.md`.
- Capturas sintéticas em `/tmp/qml-complete-*.png`, em 1300 × 850 e 1024 × 700, fonte padrão e +25%, incluindo editor/prévia e diálogos. Desktop/GPU, Wayland/X11, IME, leitor de tela, Obsidian, Python 3.12, hardware de 8 GB e cargas grandes continuam pendentes. Não declarar essas validações como realizadas.
- PDF pessoal e vaults reais não utilizados nesta implementação; sem commits, OCR ou mudanças nos limites dos filtros. Trabalho temporário continua restrito à sessão, sem nova persistência. Próximo passo é o aceite interativo do usuário no desktop e correções que surgirem dessa avaliação; não ampliar filtros nem adicionar funcionalidades por analogia com Raycast.

As seções seguintes preservam o histórico das etapas anteriores; o estado atual acima prevalece sobre afirmações antigas de que editor/PDF ainda são Widgets.

## Estado funcional e decisões


### Conversão e exportação

- Extração de texto com metadados de linhas, imagens raster e figuras vetoriais; reconhecimento heurístico de tabelas e fórmulas com avisos para revisão.
- Linhas iguais sobrepostas são deduplicadas antes da contagem de estilos (texto com espaços normalizados, mesma página/direção e até 1 ponto de diferença em cada coordenada). Preservar repetições legítimas em locais diferentes e registrar decisões.
- Reconstrução de parágrafos por alinhamento, espaçamento e continuidade textual, inclusive entre blocos PDF separados. Mudanças de negrito/itálico não quebram o parágrafo.
- Remoção conservadora de hifens de quebra: hífen suave ou evidência da palavra completa no documento. Preservar palavras compostas.
- Parágrafos continuam sendo reconstruídos dentro de cada página, sem resolver múltiplas colunas. O contexto das questões atravessa páginas, preservando os marcadores e sem repetir o título na continuação.
- Cabeçalhos repetidos mantêm a análise por bloco anterior. Rodapés de texto são tratados por linha, com registro das decisões e proteção de notas/referências; isso é distinto do filtro de imagens.
- Exportação para `Importados/<slug>/`, contendo nota `.md`, `original.pdf`, `assets/` e `conversao.json`. Links relativos, verificação de integridade da origem, publicação sem sobrescrever e sufixos para colisões.
- Anexos sem uso são omitidos da cópia exportada; referências compartilhadas são preservadas. HTML desconhecido, YAML e referências ambíguas mantêm anexos conservadoramente.

### Conversão em lote e documentos da sessão

- **Converter em lote…** na tela inicial e no cabeçalho abre preparação com seleção múltipla, remoção e deduplicação por caminho canônico. Uma única fila sequencial usa o processo auxiliar existente. Não exportar ao concluir a conversão.
- Resumo mostra conversões, falhas individuais, avisos e detalhes. **Revisar** abre o arquivo no editor existente; **Documentos (N)** no cabeçalho retorna à lista, sem painel lateral permanente. Desmarcar ou **Excluir da exportação** mantém o resultado e todas as edições para inclusão posterior.
- Cada resultado tem um QTextDocument durável, propriedade da janela. Trocar o documento conserva histórico, cursor/seleção reversa, opções, auditoria de remoção e recortes. Restaurar aba, rolagem do editor/prévia/PDF, seleção manual de imagens, página/zoom, acompanhamento, visibilidade/divisão do PDF e avisos. Apenas a prévia e o bitmap PDF ativos são renderizados; descartar os anteriores ao trocar.
- Documento aberto antes do lote permanece acessível como **Fora do lote**, sem participar da exportação conjunta. Aberturas individuais com um lote presente também ficam disponíveis na sessão. **Salvar no vault…** continua exportando só o documento ativo.
- **Exportar selecionados (N)…** escolhe uma pasta existente como confirmação. Preparar assinatura do estado exportável por documento no worker, então exportar somente novos/alterados para aquele vault. Registros são por caminho canônico do vault e existem somente na sessão; uma saída inalterada cuja pasta ainda existe aparece como **Já salvo**. Exportação individual também alimenta esse registro.
- Assinatura usa a mesma preparação do exportador: Markdown final, opção de marcadores, metadados/anexos e auditoria efetiva; remoções desfeitas não contam como mudanças. Anexos gerados no workspace são considerados imutáveis. A exportação mantém links, formato, integridade da origem, publicação atômica e sufixos sem sobrescrever.
- Falhas não bloqueiam os demais arquivos e conservam documentos para nova tentativa. Cancelar conversão interrompe o atual e os futuros; cancelar exportação termina a gravação atual já iniciada e interrompe os seguintes. Fechar o diálogo durante processamento solicita cancelamento e espera o término.
- Eventos do worker levam identificadores de operação/arquivo; ignorar resultados obsoletos. Pedidos de renderização continuam priorizando o documento/página mais recente. Morte inesperada do worker termina a fila e preserva os documentos concluídos, com instrução para reabrir a aplicação.
- A lista do diálogo mantém linhas por identificador e só altera a composição quando arquivos entram/saem. Progresso usa `BatchController.progress_changed` e atualiza somente a barra; `changed` atualiza os controles da janela e o diálogo uma vez por transição. Preservar seleção, foco e rolagem; não voltar a limpar/recriar a árvore durante o progresso. Alterações programáticas dos checkboxes usam bloqueio de sinais restaurado mesmo após exceções.
- Um lote por sessão ativa; novo lote substitui o anterior após confirmação agregada dos não salvos, incluindo desmarcados. Documento externo ao lote é preservado. Fechar a aplicação confirma descarte de todos os documentos não salvos e remove workspaces temporários. Não há persistência de sessão, OCR ou novas dependências. Muitos textos/históricos e anexos grandes podem aumentar memória e espaço temporário.

### Rodapés de texto

- Usuário pediu remover rodapés e confirmou preservar notas explicativas/referências. Implementação em `footers.py`, sem novos controles, dependências ou mudanças nas APIs públicas.
- Analisar linhas inteiramente nos 10% inferiores e dentro da página, em direção horizontal. Normalizar paginação como “7 de 120”; contar recorrência por página distinta e exigir no mínimo três páginas e 70% do documento. Site/paginação no mesmo bloco não impedem a identificação.
- Proteger marcadores de nota, rótulos Nota/Fonte/Referências/Bibliografia, alternativas e afirmativas, mesmo repetidos. Acompanhar continuações por espaçamento, estilo e coluna, inclusive entre blocos. Marcadores pequenos separados do texto são associados por proximidade. URLs contíguas a uma nota permanecem como referência; casos incertos são conservados.
- Remover somente linhas reconhecidas, atualizando texto, bbox, linhas e tamanho predominante de blocos parcialmente mantidos. Não alterar figuras/anexos ou a lógica anterior de cabeçalhos.
- Limpeza ocorre antes do vocabulário de reconstrução, reconhecimento de questões e união de parágrafos; verifica cancelamento entre páginas. Decisões usam o campo existente do relatório, uma entrada por linha removida.
- Aplicar em novas conversões, preservando os marcadores internos de página e os textos já editados. Rodapés únicos, fora da faixa e documentos abaixo do limite de recorrência permanecem para revisão.

### Questões e gabaritos

- Usuário escolheu títulos navegáveis por questão e organização também do gabarito/comentários, mantendo as seções originais. Gabarito resumido em tabela Questão/Resposta; limites de comentário tratados conservadoramente, sem inferir rótulos a partir de ícones/espaços.
- `questions.py` reconhece componentes antes da reconstrução e serializa os blocos. Usa número, identificação de banca/prova (incluindo parênteses aninhados e quebras entre blocos) e contexto de seção. Questão explícita e questão numerada com metadados de prova são sinais fortes; listas comuns e referências no meio de frases permanecem comuns.
- `TextLine.role` é um campo opcional interno, com padrão None. Papéis novos: question_header, question_metadata, question_option, question_statement, question_comment, question_answer, question_unresolved, answer_key e exam_section. Chamadas públicas de conversão/exportação e estrutura de pastas permanecem iguais.
- Título Questão 001 conserva a numeração original e fica um nível abaixo da seção vigente, limitado a H6. Banca em parágrafo próprio quando reconhecida com segurança; alternativas e afirmativas em parágrafos separados com rótulo em negrito. Continuações alinhadas ou com recuo podem ser unidas dentro da página.
- Contexto atravessa páginas sem mover texto através dos marcadores e sem gerar título repetido na continuação. Novas seções encerram o contexto anterior. Repetições em gabarito comentado e reinícios legítimos de numeração são preservados.
- Números isolados sobrepostos ao prefixo numérico com metadados são removidos somente com o mesmo número/direção e coincidência de x inicial, topo e base até 1 ponto. Números diferentes ou em outras posições são preservados. Correção ocorre antes de contar estilos.
- Alternativas/afirmativas dependem de sequência e recuo compatíveis; casos ambíguos ficam como texto separado e geram aviso. Respostas explícitas são destacadas sem alterar o conteúdo. Rótulos de comentário exigem identificação textual; espaços grandes incertos geram aviso e preservam os parágrafos.
- Gabarito textual reconhecido gera tabelas Markdown de duas colunas, reiniciadas a cada página. Número, resposta, caixa e ordem são preservados. Não transferir respostas entre seções nem produzir soluções. Tabelas/fórmulas já extraídas como imagens continuam assim.
- Aplicar somente em novas conversões, sem reformatar textos já editados. Decisões e avisos usam os campos existentes do relatório; análise verifica cancelamento periodicamente. Sem OCR ou novas dependências.

### Comparação com o PDF

- Anterior/próxima, campo de página, zoom de 25–300%, ajuste à largura e à página, rolagem e recortes manuais.
- Alt+Esquerda/Direita navega por páginas; com foco no painel PDF, Ctrl++/− altera zoom e Ctrl+0 ajusta à largura.
- Acompanhamento opcional do editor/prévia por comentários `<!-- Página N -->`, sem mover o cursor de edição nem modificar o histórico. Marcadores ausentes ou duplicados geram aviso.
- Pedidos de renderização são agrupados e priorizam a solicitação mais recente. A edição continua durante renderização; recorte e conversão suspendem alterações.

### Imagens: filtro de margens autorizado e demais remoções manuais

- Nesta sessão o usuário autorizou explicitamente um novo filtro automático limitado às margens, com revisão e recuperação. Essa decisão substitui a restrição anterior de remoção exclusivamente manual; não autoriza classificadores gerais nem filtragem de figuras no corpo. OCR foi discutido e excluído por solicitação explícita.
- Filtrar somente raster/vetor inteiramente nos 10% superiores/inferiores, mesma identidade e geometria relativa (tolerância de 0,5%), recorrentes em pelo menos três páginas e 70% do documento. Identidade raster por digest; vetor por assinatura local de caminhos, cores e espessuras. Casos incertos, corpo, tabelas, fórmulas e recortes permanecem.
- A conversão extrai texto/regiões de todas as páginas antes de decidir o filtro e renderizar anexos. Não remover texto coberto por vetores filtrados. Progresso em duas passagens, com cancelamento entre páginas/regiões.
- `ConversionResult.filtered_images` tem lista opcional vazia por padrão; `FilteredImage` registra asset, página, bbox, motivo e assinatura. Todos os anexos, inclusive filtrados, permanecem no workspace para recuperação.
- Imagens filtradas (N), junto ao controle do PDF, abre diálogo escuro com miniaturas, motivo, navegação e restauração individual. Restauração insere ao final do trecho da página em uma operação de desfazer, preservando cursor/seleção. Marcador ausente/duplicado ou estrutura incompleta que impeça renderizar a imagem bloqueia a ação. Incorporação existente desabilita nova restauração.
- Demais remoções continuam exclusivamente manuais na Prévia: selecionar imagens, remover em lote, limpar seleção e desfazer/refazer. Edição do Markdown limpa a seleção pendente e atualiza a prévia; arquivos temporários permanecem para desfazer.
- Exportação considera referências atuais e omite arquivos sem uso. Relatório registra os filtrados e flags `incorporated`, `referenced` e `file_exported`; referências compartilhadas e HTML/YAML incertos continuam preservando anexos conservadoramente.
- Remover marcações de página na exportação permanece no menu ⋯, desativado em cada documento, e afeta somente a cópia final.

### Barra de formatação Markdown

Escolhas confirmadas pelo usuário: botões sobre o Markdown, conjunto essencial de formatação e alinhamento persistido na nota usando HTML, sem plugins ou CSS adicional no Obsidian.

- Negrito, itálico, links, parágrafo, títulos H1–H6, listas com marcadores/numeradas e citações.
- Esquerda, centro, direita e justificado para parágrafos textuais e títulos. Com seleção, alcançar os blocos abrangidos; sem seleção, usar o bloco atual.
- Ctrl+B, Ctrl+I e Ctrl+K restritos ao editor. Cada comando representa uma operação de desfazer; seleção reversa e offsets UTF-16/Unicode são tratados.
- O editor continua sendo código-fonte Markdown; a prévia mostra o resultado. Não foi implementado editor visual WYSIWYG.
- Alinhamento usa blocos como `<p style="text-align: center;">Texto</p>` ou `<h2 style="text-align: right;">Título</h2>`. Dentro deles, os comandos usam HTML equivalente para estilos e links. Esquerda recupera Markdown equivalente.
- Reconhecer somente o subconjunto gerado. Proteger tags/entidades parciais, HTML personalizado, código e destinos de links contra alterações indevidas.
- Não alinhar imagens, listas, citações, tabelas, código ou wikilinks. Seleções incompatíveis são recusadas integralmente. Para converter bloco alinhado em lista/citação, retornar à esquerda primeiro.
- Negrito/itálico/link atuam em um bloco por vez; em lista/citação, em um item ou linha. Comandos de título sobre listas/citações exigem primeiro remover seus prefixos.
- A prévia Qt pode perder alinhamento e juntar HTML ao bloco anterior. A solução substitui blocos reconhecidos por sentinelas temporárias, insere o HTML depois do parser e aplica o alinhamento Qt explicitamente. As sentinelas e âncoras internas não entram na exportação.
- Links de blocos alinhados são analisados para exportação; alinhamento conhecido não deve obrigar a manter todos os anexos. Links por referência são resolvidos com as definições do documento.

## Mapa da implementação


- `appearance.py`: paleta escura, estilos, ícones locais e indicador de checkbox com marca explícita.
- `src/pdf_obsidian/models.py`: contratos de linhas, blocos, páginas, anexos e resultado.
- `converter.py`, `layout.py`, `pdf.py`: extração, reconstrução e operações PDF.
- `footers.py`: limpeza de rodapés por linha com proteção de notas/referências.
- `questions.py`: reconhecimento de questões antes da união de linhas, contexto entre páginas e serialização estruturada.
- `conversion_filters.py`: deduplicação de linhas e filtro de margens; `filtered_images.py`: revisão e preparação de restaurações.
- `application.py`: fachada QtCore e runtime de processamento compartilháveis entre frontends.
- `worker.py`: processamento PDF em processo auxiliar; `gui.py` e `viewer.py`: janela e navegação.
- `batch.py` e `batch_dialog.py`: filas sequenciais e preparação/resumo do lote com revisão e seleção para exportar.
- `sessions.py` e `session_ui.py`: documento Qt durável por arquivo, restauração de estado e registros de exportação por vault.
- `comparison.py`: âncoras por página, posição de leitura e renderização dos blocos alinhados.
- `formatting.py`: transformações localizadas, validação do HTML alinhado e conversão de volta para Markdown. `Edit` usa offsets em caracteres Python.
- `editor_tools.py`: barra, atalhos, diálogo de links e aplicação atômica via QTextCursor, com conversão para offsets UTF-16.
- `markdown.py`: referências, imagens, regiões protegidas e comentários de página.
- `preview.py`: associação entre imagens renderizadas e ocorrências do Markdown, seleção e comandos manuais.
- `cleanup.py`: planos de remoção manual vinculados ao hash do texto. O nome permanece, mas não contém classificação automática.
- `exporter.py`: exportação, integridade, anexos e auditoria das remoções.
- `tests/`: PDFs sintéticos e testes de núcleo/interface; `tools/benchmark.py`: benchmark sintético.

## Cuidados para continuar

- Ler este contexto antes de alterar o projeto e preservar as regras de `AGENTS.md`.
- Não ampliar os filtros: imagens recorrentes somente nos 10% superiores/inferiores, mesma identidade/posição, mínimo de três páginas e 70% do documento. Demais remoções seguem manuais pela prévia. OCR local automático está autorizado e implementado conforme a seção atual; preserva as imagens para revisão.
- Preservar documentos originais, temporários de recuperação, históricos, edições, navegação e referências relativas dos anexos.
- Executar `.venv/bin/python -m pytest -q` para as verificações pertinentes; detalhes e limitações em `VALIDATION.md`.
- Desktop/GPU, Wayland/X11, IME, leitor de tela, Obsidian desktop/Android e máquina física de 8 GB continuam pendentes. Python 3.12 e 3.14 foram testados; benchmark de recursos e memória está descrito em `VALIDATION.md`. Não tratar testes offscreen como aceite desses ambientes.
