# Revisão visual e proposta de refinamento

## Direção

**Monochrome Premium, com foco editorial:** controles precisos e discretos ao redor de uma área de leitura protagonista. O diferencial deve ser a qualidade da comparação entre original e nota, com ferramentas legíveis e hierarquia clara.

A aplicação já possui um design system monocromático implementado. Esta proposta consolida esse sistema; não pressupõe ausência de identidade visual. Manter Qt Quick/QML, recuperação Widgets, fontes locais Geist Sans/Mono, SVGs Lucide e tokens compartilhados. Não introduzir bibliotecas web, gradientes, fontes adicionais, efeitos de entrada ou novas etapas de utilização.

**Estado:** proposta seguida de implementação autorizada pelo usuário. A análise original está preservada abaixo; esta seção diferencia as decisões efetivamente aplicadas.

Implementados: largura e organização do link Widgets; foco contrastante dos primários (anel externo Quick e inversão de superfície com borda branca Widgets); abas próprias e indicador de expansão dos avisos; redução de espaços nas barras; tokens semânticos de ícones, lista de mídia e raio de menu; hierarquia de formulários/títulos; orientação do estado vazio; remoção da garantia duplicada de preservação na importação. Nenhuma alteração dos comandos, conteúdo ou regras de processamento.

Mantidos após avaliação: tamanhos dos títulos da prévia, que continuam distinguindo a hierarquia do documento; mensagem completa sobre indisponibilidade/preparação do OCR. O ganho de área foi obtido nos controles, sem reduzir a tipografia do documento. Não houve motivo suficiente para alterar o renderizador da prévia ou introduzir outra propriedade de estado OCR para um refinamento textual.

As alterações preexistentes no checkout foram preservadas. Especificação atualizada em `DESIGN_SYSTEM.md`; validações desta implementação em `VALIDATION.md`.

## Evidência e abrangência

Revisados `DESIGN_SYSTEM.md`, tokens, tema, botões, campos, grupos, menus, diálogos, cabeçalho, controles do PDF, importação, composição da janela e estilos Widgets. Inspecionadas capturas sintéticas da auditoria anterior, disponíveis em `/tmp/pdf-obsidian-audit-20261024/`, incluindo:

- Importação, conversão e feedback de processamento.
- Editor amplo e compacto, comparação com PDF, prévia, avisos e seleção de imagens.
- Preparação/resumo de lote, documentos vazios, imagens filtradas e opções.
- Menus, inserção de link, mensagens extensas e confirmação de descarte.
- Editor, imagens filtradas, link e erro da interface Widgets.

As capturas incluem janela de 800 × 600 com fonte +25% e comparação em 1300 × 850. São evidências offscreen existentes, não uma nova execução interativa. Seletores nativos e molduras do gerenciador de janelas não foram avaliados. Estados injetados pelas fixtures — como texto de renderização ou progresso — não foram tratados como falhas funcionais reais.

## O que já funciona visualmente

- Paleta neutra coerente e ação principal branca identificável.
- Geist Sans/Mono locais, ícones da mesma família e coluna de leitura controlada.
- Contornos dos grupos visíveis, sem necessidade de enfraquecê-los novamente.
- PDF e figuras mantêm suas cores, diferenciados da superfície da aplicação.
- Mensagens extensas rolam e diálogos mantêm ações no rodapé.
- Revisão e publicação são visualmente distintas; confirmações de descarte dão foco inicial a Cancelar.
- Escala de fonte, reorganização das ferramentas e redução de movimento já existem.

## Inconsistências e melhorias propostas

| Prioridade | Achado e evidência | Proposta | Benefício / risco |
| --- | --- | --- | --- |
| Alta | O link Widgets abre muito estreito; a captura `widgets-link.png` corta o placeholder e deixa pouco espaço para revisar o destino. `LinkDialog` não define largura inicial. | Largura preferida próxima de 480 px, limitada à área disponível; campos expansíveis; rótulos acima dos campos em espaço estreito. | Melhora a revisão de caminhos; baixo risco, sem alterar validação/inserção. |
| Alta | Foco dos botões primários não tem tratamento uniforme. `ImportAction` desenha anel externo; `ActionButton` usa borda clara sobre preenchimento igualmente claro; Widgets também usa borda branca. | Anel externo de 2 px com intervalo escuro de 2 px em ações brancas. Manter foco interno visível nos controles escuros. Reservar espaço para não cortar o anel. | Torna a navegação por teclado mais perceptível; risco baixo a médio por clipping/layout. |
| Média | Em 800 × 600/+25%, cabeçalho, comandos, controles e seleção manual deixam pouca área de documento. Em `image-selection`, a área da prévia começa perto de y=370. | Reduzir espaços verticais redundantes entre linhas; distribuir contador/ações contextuais com quebra previsível. Manter todos os comandos e a explicação de desfazer. | Mais área de leitura; risco médio, exige conferir foco e dimensões mínimas. Não reduzir a fonte para acomodar. |
| Média | A aba ativa Quick usa caixa, fundo e pequeno traço; Widgets usa principalmente sublinhado. Avisos expandidos reutilizam o mesmo traço de seleção de abas. | Definir variante própria de aba: faixa inferior de 2 px e texto ativo, sem borda completa. Para Avisos, usar superfície pressionada e indicador de expansão. | Distingue navegação de expansão; risco médio. Preservar setas, foco, papéis acessíveis e estado atual. |
| Média | Documentos usam linhas/divisores; imagens filtradas usam cartões elevados com raio 8 e altura mínima 125. Não é erro, mas a diferença não está formalizada. | Documentar duas variantes de lista: documentos compactos e mídia com miniatura. Na lista de mídia, alinhar margens e ações à mesma grade; definir altura pelo conteúdo, com mínimo suficiente para a miniatura. | Consistência sem perder legibilidade de figuras; baixo risco. |
| Média | Valores locais de espaçamento/raio coexistem com tokens: raio 8 em imagens, 5 em menu, 10 em painel; margens 10 e 12 em formulários. | Nomear tokens por função e mapear exceções intencionais. Consolidar apenas valores equivalentes, sem substituição numérica global. | Reduz divergências futuras; baixo risco com revisão visual. |
| Média | Iconografia tem ativos consistentes, mas escala pouco explícita: token geral 18 px, ferramentas Widgets 20 px, estados 14 px e importação 22 px. A documentação histórica menciona ferramentas QML de 20 px. | Definir tamanhos semânticos: estado 14–16, ferramenta 20, importação 22, chevron 12. Conferir peso óptico no mesmo tamanho lógico entre frontends. | Consistência óptica e documentação precisa; baixo risco, conferir quebra de grupos. |
| Média | Rótulos de formulário Quick usam corpo de 14 px, enquanto campos/botões usam 13 px; diálogos Widgets variam mais em largura, título e composição. | Rótulos 13 px/500, valores 14 px, auxiliares 12 px; título de diálogo 18 px/600. Compartilhar hierarquia, margens e altura visual entre frontends. | Melhor hierarquia e leitura de formulários; baixo risco. Respeitar molduras nativas. |
| Baixa | H1 da prévia tem grande peso visual em coluna estreita; na captura mínima domina o primeiro trecho visível. | Experimentar H1 de 28–30 px e H2 de 22–24 px na escala-base, com espaçamento proporcional; comparar antes/depois em notas extensas. | Pode melhorar densidade de leitura; é hipótese de design, não bug. Alterar só apresentação, nunca Markdown exportado. |
| Baixa | Estado vazio de documentos deixa grande área sem orientação próxima à mensagem; Novo lote fica distante no rodapé. | Mensagem central com título curto e orientação explícita para a ação já existente no rodapé. Ícone de documento discreto opcional. | Melhora descoberta sem criar CTA duplicado ou novo fluxo; baixo risco. |
| Baixa | Importação repete garantias de funcionamento local/preservação em regiões diferentes; instrução técnica de preparar OCR pode pesar na primeira leitura. | Separar mensagem de disponibilidade e comando em linhas com hierarquia, conservando informação e possibilidade de revisão. Evitar repetir a mesma garantia no corpo e rodapé. | Reduz ruído textual; baixo risco. Não esconder indisponibilidade nem prometer OCR preparado. |

## Especificação proposta

### Cores e superfícies

Manter a paleta atual: fundo `#090909`, superfície `#141414`, elevada `#1C1C1C`, hover `#262626`, divisória `#303030`, borda de controle `#666666`, hover de borda `#A3A3A3`, texto `#F5F5F5` e texto secundário `#A3A3A3`.

Usar três níveis de superfície com função clara: área de trabalho, componente e sobreposição. Não tornar todos os painéis elevados. Bordas de controle precisam continuar distinguíveis; divisórias decorativas podem permanecer discretas. Sucesso, atenção e erro devem combinar texto e ícone, preservando a ausência de cores semânticas saturadas.

### Tipografia

| Papel | Fonte | Escala-base / peso |
| --- | --- | --- |
| Título da importação | Geist Sans | 28 px / 600 |
| Título de diálogo | Geist Sans | 18 px / 600 |
| Nome do documento | Geist Sans | 15 px / 600 |
| Texto de interface e valores | Geist Sans | 14 px / 400 |
| Botões e rótulos | Geist Sans | 13 px / 500; ação principal 600 |
| Descrições e estado | Geist Sans | 12 px / 400 |
| Markdown | Geist Mono | 15 px / 400 |
| Corpo da prévia | Geist Sans | 15 px / 400 |

Manter escala de fonte/DPI. Não aplicar fontes da interface dentro do bitmap PDF. Não trocar Geist por uma fonte de exibição apenas para diferenciar o produto: leitura prolongada e continuidade entre telas são mais importantes neste contexto.

### Botões, campos e ferramentas

- Altura-base de 32 px, expansível conforme fonte e conteúdo; botões com ícone devem manter área de interação equivalente.
- Raio 6 px para controles, 10 px para diálogos; possíveis variantes menores precisam de token explícito.
- Primário branco para a ação principal do contexto; secundário escuro com borda visível; ferramenta sem caixa individual dentro de grupo delimitado.
- Hover de até 120 ms, sem deslocamento ou mudança de tamanho. Respeitar Reduzir movimento.
- Desabilitado não simula hover ativo. Foco não pode depender apenas de uma mudança sutil de cinza.
- Botão destrutivo conserva verbo/ícone e as confirmações existentes; não recebe destaque que compita com Cancelar em descarte.
- Campos e botões alinhados pela altura visual e baseline, com padding consistente; comprimentos de caminho precisam ser revisáveis.

### Organização espacial

Usar grade de 4/8/12/16/24/32 px, com 24 px em diálogos, 16 px entre seções e 8 px entre controles relacionados. Exceções ópticas pequenas, como 2–3 px dentro de grupos, são válidas se documentadas. Preservar a comparação 40/60 inicial, a divisória ajustável, o PDF ocultável e a coluna de leitura existente.

## Sequência recomendada

1. Corrigir largura do link Widgets e foco dos primários; são os ganhos mais claros de usabilidade.
2. Consolidar variantes de abas/expansão, tamanhos de ícones e tipografia de formulário.
3. Refinar densidade vertical e listas com capturas comparativas. Tratar cabeçalhos da prévia como experimento, adotando apenas se a leitura melhorar.
4. Atualizar `DESIGN_SYSTEM.md` e os tokens conforme decisões efetivamente implementadas, evitando documentar proposta como recurso concluído.

## Preservação e critérios de aceite

Não alterar comandos, atalhos, seleção, foco restaurado, desfazer/refazer, conversão, OCR, filtro de margens, anexos, navegação, textos editados ou publicação. Nenhum PDF pessoal ou vault real deve entrar nas verificações.

Para cada conjunto implementado, comparar capturas nos três tamanhos já utilizados e fonte normal/+25%; incluir nomes extensos, mensagens longas, estado vazio, processamento, erro, seleção e controles desabilitados. Conferir Tab/Shift+Tab, Espaço/Enter, Esc, abas por setas, retorno ao editor e foco no Cancelar. Rodar testes de interface pertinentes e lint QML; ampliar para a suíte quando componentes compartilhados forem alterados.

Critérios: nenhuma ação cortada, nenhum controle sobreposto, foco visível em fundo claro e escuro, cores dos documentos intactas, sem redução forçada da fonte ou remoção de comandos para caber. Desktop, leitor de tela, IME e seletores nativos exigem validação própria.

Na entrega inicial foi criado somente este documento de análise. A implementação posterior foi conferida com capturas novas, testes de interface e suíte completa; resultados e limitações estão em `VALIDATION.md`.
