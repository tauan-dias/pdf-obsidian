# Monochrome Premium

Sistema de apresentação local do PDF → Obsidian. Implementado em Qt Quick Controls Basic e Qt Widgets, sem alterar conversão, exportação ou documentos editáveis.

## Fundamentos

- Fundo `#090909`, superfície `#141414`, superfície elevada `#1C1C1C`, divisória `#303030`, texto principal `#F5F5F5` e secundário `#A3A3A3`.
- Cinza `#737373` reservado a estados desabilitados e informação não essencial. Bordas de controles e grupos usam `#666666`; hover usa `#A3A3A3`. Divisórias decorativas permanecem discretas.
- Espaçamentos de 4, 8, 12, 16, 24 e 32 px lógicos. Controles-base de 32 px, raios de 6 px nos controles e 10 px nos diálogos; alturas crescem com fonte e conteúdo.
- Geist Sans para interface; Geist Mono para edição técnica. Auxiliares 12 px, controles/labels 13 px, corpo 14 px, documentos 15 px, seções 18 px e título inicial 28 px. Fontes ampliadas e DPI continuam suportados. Pesos 400, 500 e 600, com itálicos locais.
- Recursos oficiais locais: Geist 1.8.2 (SIL OFL 1.1) e subconjunto Lucide 1.61.0 (ISC/MIT). Arquivos e licenças ficam em `src/pdf_obsidian/assets/`; `manifest.json` registra versões e SHA-256. Falha ao carregar fonte usa fallback nativo.
- Escala semântica de ícones: ferramentas 20 px (Quick/Widgets), estados 14 px, importação 22 px e chevron 12 px. Tamanhos definidos em tokens; SVGs e cores dos documentos permanecem intactos.
- Botões QML e rótulos de formulário usam peso 500; ação principal e títulos de diálogo usam 600. Campos de texto QML usam corpo de 14 px; rótulos usam 13 px e auxiliares 12 px, respeitando a escala.
- Os mesmos SVGs são renderizados por QtSvg nos dois frontends. O provedor Quick tem cache limitado de ícones, independente dos documentos. Sem fontes de ícones, serviços externos ou downloads na execução.

## Componentes

| Componente | Regra visual e interação |
| --- | --- |
| Primário | Fundo quase branco, texto preto, hover sutil e rótulo explícito. |
| Secundário | Superfície escura com borda visível; contraste sem competir com o primário. |
| Ferramentas | Contorno no grupo; ícones individuais sem caixa permanente, hover individual e foco de teclado de 2 px. |
| Destrutivo | Verbo explícito, ícone de remoção e confirmação existente; não depende de vermelho. |
| Campos | Superfície escura, borda interativa, seleção neutra e foco claro; regras de confirmação preservadas. |
| Abas | Sublinhado branco de 2 px, sem caixa de seleção; hover discreto e contorno somente no foco de teclado. Setas navegam sem modificar o documento. |
| Listas | Documento, estado e detalhes alinhados, linhas separadas por divisores; ações e seleção preservadas. |
| Diálogos | Título de seção, ícone semântico quando pertinente, conteúdo rolável e ações em rodapé fixo. |
| Notificações | Texto simples selecionável, caminhos legíveis, identificação textual e ícones neutros, incluindo mensagens padrão Widgets. |
| Progresso | Dados reais; indicador indeterminado acompanhado de texto. Modo reduzido mantém indicador estacionário. |

`Tokens.js` é a fonte compartilhada de tokens. `Theme.qml`, componentes QML e `appearance.py` consomem esses valores; `visuals.py` carrega fontes, ícones e a preferência visual de movimento. Estilos técnicos de edição e imagens nunca são aplicados ao PDF original.

`TabButton.qml` diferencia abas dos controles expansíveis. Avisos usa superfície selecionada e chevron para indicar expansão, sem reutilizar o sublinhado das abas. `FocusRing.qml` aplica anel externo branco de 2 px com intervalo escuro de 2 px às ações principais Quick; no Widgets, o botão primário recebe preenchimento escuro, texto branco e borda branca de 2 px no foco, mantendo a largura da borda em repouso para evitar mudança de tamanho.

Listas têm duas variantes intencionais: documentos usam linhas/divisores; mídia usa miniaturas em superfície elevada, raio de controle, margem de 12 px e altura mínima de 104 px, expansível pelo conteúdo. Menus usam raio interno de 4 px. Exceções ópticas de 2–3 px dentro de grupos permanecem.

O diálogo de links Widgets abre com largura preferida de 480 px limitada à tela, rótulos acima dos campos e campos expansíveis. A importação concentra a garantia de preservação no rodapé. A lista vazia de documentos orienta para Novo lote sem duplicar o botão. Barras de revisão têm margens verticais menores, preservando tamanhos dos controles e todos os comandos.

## Telas e fluxos

- Importação: título, explicação e ações diretas, sem cards aninhados. A mesma composição apresenta arquivo, progresso e cancelamento.
- Revisão: cabeçalho do documento com salvamento, comandos e avisos; PDF inicialmente em 40% e editor em 60%, com divisão ajustável e ocultação preservadas. Fonte-base de 15 px e coluna de leitura de até 760 px escalável.
- Ferramentas: estilo, texto e parágrafo em grupos que quebram por inteiro. Markdown e Prévia permanecem separados; não há estado de formatação ativo presumido.
- Lote: preparação, documentos, inclusão na exportação e estados Pronto/Salvo/Falhou/Cancelado preservam seus modelos e controles.
- Imagens filtradas: miniaturas coloridas originais, explicação, verificação e restauração individual. Seleção manual na prévia continua contextual e reversível.
- Publicação: a pasta escolhida continua confirmando a exportação. Destinos são exibidos nas mensagens existentes; não há nova etapa ou alteração de contratos.
- Recuperação Widgets e protótipo compartilham tokens, fontes e ícones. Seletores nativos de arquivo/pasta seguem o tema do sistema.

## Acessibilidade e movimento

Texto comum exige contraste de 4,5:1; indicadores necessários para identificar controles exigem 3:1. Estados continuam claros por texto, forma e ícone, inclusive sem cores convencionais. Tooltips, nomes acessíveis, ordem de foco e atalhos são mantidos.

Em **Opções**, “Reduzir movimento” desativa transições e movimento de carregamento. A opção é compartilhada entre interfaces no processo e não é persistida nem altera o estado de salvamento. O valor inicial respeita a desativação de animações informada pelo estilo Qt. Qt 6.11 não oferece a propriedade universal de preferência de movimento introduzida no Qt 6.12; quando o estilo não informa a preferência, use a opção da aplicação. Transições normais duram até 120 ms; sem animações de layout, sombras pesadas ou blur.

## Verificação reproduzível

```bash
.venv/bin/python -m pytest -q
.venv/bin/python prototypes/qml_import/run.py --check --size 800x600 --text-scale 1.25
.venv/bin/python tools/visual_review.py --output /tmp/pdf-obsidian-visual
.venv/bin/python tools/benchmark_quick.py --pages 100
```

A inspeção visual gera documentos e workspaces temporários próprios, além de capturas em três tamanhos e duas escalas de fonte. Progresso e falhas são fixtures de apresentação, não execuções reais desses estados; integração com worker é coberta pela suíte e pelo benchmark. Nunca usar o PDF pessoal da raiz ou vaults reais para esse procedimento.

Capturas offscreen não substituem aceite interativo em desktop/GPU, IME ou leitor de tela. Evidências e limitações estão em `VALIDATION.md`.
