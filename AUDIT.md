# Auditoria de produto — 24/10/2026

## Escopo e diagnóstico

Revisão do contexto, documentação, dependências, conversão, análise de referências Markdown, OCR, publicação, coordenação do worker, sessões, lote e interfaces Quick/Widgets. Conferência funcional pela suíte sintética e inspeção de capturas offscreen. Não equivale a aceite no desktop ou no Obsidian, nem a uma auditoria formal de segurança.

O produto já oferece uma jornada completa: importar/configurar → converter localmente → comparar PDF/Markdown → revisar e desfazer → publicar em uma nova pasta no vault. O vault é uma pasta local; não há API, sincronização ou plugin obrigatório do Obsidian. A publicação mantém nota, PDF, anexos relativos e relatório. A arquitetura separa processamento em subprocesso, coordenação QtCore, documentos duráveis e apresentação QML/Widgets. Não surgiu evidência que justifique trocar tecnologias ou reescrever essas camadas.

Conversão, OCR conservador, revisão manual, restauração das imagens filtradas, edição Markdown, recortes, histórico, navegação por página e lote existem. Editor visual, interface específica de metadados, arraste de blocos, recuperação persistente entre execuções e renderização matemática completa na prévia não existem. A edição livre do Markdown permite algumas dessas alterações textuais, mas não deve ser descrita como uma ferramenta dedicada.

## Priorização e decisões

| Prioridade | Evidência/oportunidade | Impacto no usuário / benefício técnico | Complexidade / risco da mudança | Decisão |
| --- | --- | --- | --- | --- |
| P0 | Inventário de anexos seguia links simbólicos para arquivos externos ao workspace | Evita copiar conteúdo externo inesperado; valida a fronteira da publicação | Baixa / baixo: anexos gerados são arquivos regulares | Implementado bloqueio de links na raiz, arquivos e subpastas de assets |
| P1 | Manifesto OCR com JSON não objeto provocava AttributeError | Instalação danificada deixa de quebrar a consulta de estado; fallback continua acessível | Baixa / baixo | Implementadas validações de estrutura, hashes e caminhos resolvidos |
| P1 | Hash de fonts/OFL.txt divergente do arquivo já versionado em HEAD | Restaura a verificação do pacote; erro passa a identificar o arquivo | Baixa / baixo | Manifesto corrigido; licença e fontes intactas |
| P2 | Importação Widgets recebia a etapa OCR mas não a exibia | Explica espera e cancelamento em uma operação potencialmente longa | Baixa / baixo | Incluído texto de etapa com quebra de linha |
| P2 | OCR desligado continuava acompanhado do estado da instalação | Distingue escolha do usuário de disponibilidade; feedback consistente | Baixa / baixo | Estado reativo compartilhado por importação/lote/opções |
| P2 | Aviso de OCR ausente não explicava o resultado da conversão | Permite decidir continuar com extração direta sem presumir perda de imagens | Baixa / baixo | Mensagem informa fallback e comando de preparação/reparo |
| P2 | README ainda afirmava que não havia OCR/LaTeX | Elimina contradição na descrição do produto | Baixa / baixo | Limitações atualizadas |
| P2 | Aceite em leitor de tela, IME, desktop e Obsidian não demonstrado neste ambiente | Valida acesso e apresentação no uso real | Média / baixo para validar | Próxima prioridade de validação |
| P3 | QuickController e Window concentram bastante coordenação visual | Separação futura pode facilitar manutenção | Alta / médio: seleção, histórico e ciclos Qt são sensíveis | Sem refatoração ampla sem demanda concreta |
| P3 | Históricos/anexos de lotes grandes permanecem na sessão | Possível pressão de RAM/disco | Média / médio | Medir cargas representativas antes de alterar retenção |
| P4 | Tipografia, ícones e contornos já seguem tokens compartilhados | Consistência já existente | Custo sem benefício comprovado para redesenho | Preservados |

## Alterações e arquivos

- `exporter.py`: examina links antes da análise e da criação de staging. Em erro, nenhuma publicação é iniciada. Não amplia a limpeza nem remove temporários. Essa validação não pretende proteger contra todas as corridas possíveis de outro processo com acesso ao mesmo usuário durante a cópia.
- `recognition.py`: manifestos inválidos retornam indisponibilidade controlada; hashes malformados e modelos resolvidos fora da pasta são recusados. A conferência integral SHA-256 continua antes do reconhecimento, sem carregar modelos na interface.
- `application.py`: `recognitionStatus` notifica mudanças de modo em vez de ser constante. A escolha continua bloqueada durante processamento e não altera o documento atual.
- `import_panel.py`, `batch_dialog.py`, `gui.py`: etapa/cancelamento na recuperação Widgets e mensagens coerentes com a opção selecionada. QML consome a propriedade compartilhada existente, sem duplicar textos ou criar novos componentes.
- `assets/manifest.json`: corrigido somente o digest da licença que já estava em HEAD. Os demais hashes conferem. Não houve alteração de fontes, ícones ou termos da licença.
- Testes de reconhecimento, publicação, fachada e frontends cobrem os casos novos; o teste de recursos agora informa o nome do arquivo divergente. `README.md` esclarece limites reais.

## Qualidade visual e experiência

Geradas 168 capturas Quick e seis Widgets em `/tmp/pdf-obsidian-audit-20261024/`, com entradas sintéticas. A matriz Quick inclui 800 × 600, 1024 × 700 e 1300 × 850, fonte normal/+25%, importação, conversão/cancelamento, revisão, menus, prévia, seleção, lote, documentos, restauração, opções, mensagens e confirmação. Progresso/falha dessas capturas são fixtures de apresentação, não prova de operações reais.

Inspeção direta de amostras: importação e editor na menor janela com fonte ampliada; opções; preparação/resumo de lote; imagens filtradas; mensagem extensa de erro; importação Widgets. Controles e rodapés permanecem acessíveis, textos quebram linha e mensagens extensas rolam. As figuras mantêm suas cores. Não foram encontrados nessas amostras motivos para alterar hierarquia, tipografia, ícones, organização dos painéis ou componentes. O ganho visual desta etapa é a clareza do feedback, incluindo etapa de OCR e cancelamento na recuperação Widgets.

## Validação e desempenho

Resultados finais e comandos estão em `VALIDATION.md`. A primeira execução encontrou uma falha preexistente no manifesto da licença (378 passaram, um falhou); ela foi investigada e corrigida sem afrouxar o teste. A regressão impede publicação com links simbólicos e verifica preservação do PDF e do arquivo externo. Casos OCR usam modelos sintéticos e subprocessos controlados.

Benchmark real com PDF gerado de 100 páginas e 200.718 caracteres: conversão/transporte 7,148 s, entrega ao primeiro frame 0,824 s, total até PDF visível 8,179 s, software/offscreen. Não houve comparação controlada antes/depois; não se alega otimização de desempenho. Nenhuma dependência de execução foi adicionada. O ambiente virtual ausente foi recriado com as versões fixadas do projeto.

## Limites e próximos passos

1. Validar teclado, IME, leitor de tela, foco, escalas e renderização no desktop/GPU real e a saída no Obsidian desktop/Android.
2. Repetir o reconhecimento com modelos reais preparados e hardware físico de 8 GB. Os modelos não estavam presentes neste ambiente e não foram baixados nesta auditoria. Resultados históricos de OCR não são novas validações.
3. Avaliar lotes extensos com perfis representativos antes de introduzir cache, paralelismo ou políticas de descarte. A revisão continua em memória; recuperação entre execuções permanece fora do escopo aprovado.
4. Se surgirem demandas concretas de manutenção, extrair responsabilidades localizadas dos adaptadores de interface, preservando os documentos Qt duráveis. Não adicionar edição visual ou metadados por analogia com outros produtos.

Nenhum PDF pessoal, vault real, commit ou push utilizado. Funcionamento offline, originais, filtros autorizados, restauração individual, anexos relativos e históricos preservados. A instalação das dependências para validação exigiu acesso à rede; a aplicação não ganhou acesso remoto.
