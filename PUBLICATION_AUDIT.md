# Auditoria de preparação para publicação pública

Data da auditoria: 31/10/2026  
Escopo: estado local do repositório e histórico Git disponível, sem publicação ou alteração do histórico.

## Resumo executivo

O repositório apresenta uma aplicação desktop Python para converter e revisar PDFs localmente. A estrutura separa código (`src/`), testes, ferramentas e documentação; os recursos OCR são preparados separadamente e os documentos do usuário não são enviados a serviços externos. A licença declarada no `pyproject.toml` e no arquivo `LICENSE` é AGPL-3.0-only, mantida nesta preparação.

Foram reformulados o README e este relatório. A inspeção direcionada não identificou credenciais nos padrões pesquisados, mas scanners especializados de segredos e dependências não estão instalados. A suíte não pôde ser executada porque o ambiente virtual `.venv` está ausente e o Python do sistema não tem pytest nem pip. Por isso, o parecer é **APTO COM RESSALVAS**; as verificações pendentes estão descritas abaixo.

## Segurança

### Achados por severidade

- **Crítico — nenhum identificado nas verificações realizadas.**
- **Alto — nenhum identificado nas verificações realizadas.** Não foi detectado padrão comum de chave privada, credencial AWS, token GitHub ou atribuição de credencial no conteúdo textual pesquisado do estado atual e dos patches do histórico local.
- **Médio — cobertura incompleta de varredura.** `gitleaks`, `trufflehog` e `detect-secrets` não estão disponíveis. A busca por padrões conhecidos é limitada e não comprova ausência de todos os tipos de segredo ou dado pessoal. Não houve revisão especializada dos metadados de todos os binários.
- **Médio — auditoria de dependências incompleta.** `pip-audit` e Bandit não estão disponíveis; não foram consultados avisos atuais de vulnerabilidade nem executada análise estática dedicada. As dependências de runtime estão fixadas em `pyproject.toml`, e as dependências do OCR em `src/pdf_obsidian/ocr_requirements.txt`; fixação de versões não substitui verificação de vulnerabilidades.
- **Baixo — dados de entrada e saídas locais.** O `.gitignore` exclui PDFs, vaults, workspaces, credenciais e arquivos locais usuais, com exceção explícita para `.env.example`. Não foi encontrado arquivo local desses tipos na inspeção feita. O padrão amplo de exclusão de PDFs é intencional para proteger documentos de entrada.

### Estado atual e histórico

- A busca direcionada no conteúdo atual e nos patches do histórico não retornou correspondências dos padrões consultados. Esse resultado é uma triagem, não um certificado de limpeza.
- Nenhum caminho de PDF apareceu nos nomes de arquivos registrados nos commits locais examinados. O repositório não foi reescrito nem seus commits foram removidos.
- Não foram encontrados arquivos locais com extensões de credencial, documentos PDF, logs ou backups nos padrões verificados.
- O remoto configurado é o GitHub do próprio projeto. Nenhuma conexão ou operação de publicação foi realizada.
- Não há configuração de variáveis de ambiente obrigatórias documentada; `PDF_OBSIDIAN_OCR_DIR` é uma opção de configuração do diretório OCR. Por isso não foi criado `.env.example`.

Não há credencial identificada que exija rotação. Se uma revisão posterior com scanner completo encontrar segredo, deve-se revogá-lo/rotacioná-lo e decidir explicitamente o tratamento do histórico antes da publicação.

## Estrutura

- Mantida a organização existente em `src/pdf_obsidian`, `tests`, `tools` e `prototypes`; não foram removidos arquivos nem alterada a arquitetura.
- O `.gitignore` foi revisado e não precisou de alteração. Ele protege ambientes virtuais, caches, builds, PDFs, workspaces, vaults e arquivos de credenciais usuais sem excluir os arquivos de dependência versionados.
- Não foram encontrados motivos objetivos para adicionar `.env.example`, workflow, Dependabot, templates, `CONTRIBUTING.md` ou `SECURITY.md` nesta preparação. O README registra a ausência atual de políticas formais.

## Documentação

- O README foi reorganizado em apresentação, recursos, stack/arquitetura, requisitos, instalação, uso, testes, limitações e licença.
- Os comandos de OCR foram separados da instalação principal e vinculados à documentação detalhada existente.
- O README informa limitações conhecidas e não apresenta screenshots da interface principal porque os materiais visuais disponíveis são do protótipo, não uma demonstração confirmada do aplicativo atual.
- A licença AGPL-3.0-only foi mantida conforme escolha do usuário. Fontes, ícones e recursos OCR têm avisos/licenças próprios versionados junto aos recursos. A compatibilidade jurídica completa do conjunto de dependências não foi verificada por ferramenta especializada.

## Qualidade e verificações

| Verificação | Resultado |
| --- | --- |
| `git diff --check` | Passou, sem diagnósticos |
| `python3 -m compileall -q src tests tools` | Passou |
| `.venv/bin/python -m pytest -q` | Não executado: `.venv/bin/python` ausente |
| `python3 -m pytest -q` | Não executado: pytest não instalado no Python do sistema |
| `python3 -m pip check` | Não executado: pip não instalado no Python do sistema |
| Scanner de segredos | Não executado: gitleaks, trufflehog e detect-secrets indisponíveis; busca direcionada não substitui esses scanners |
| Auditoria de dependências | Não executada: pip-audit indisponível |
| Bandit / Ruff | Não executados: ferramentas indisponíveis |
| Validação visual manual | Não realizada nesta auditoria |

Nenhum pacote foi instalado. Os resultados históricos em `VALIDATION.md` descrevem outras execuções e não foram tratados como validação deste estado.

## Pendências

- Recriar um ambiente virtual conforme `README.md`, instalar o extra de desenvolvimento e executar a suíte completa.
- Executar scanners de segredos no estado atual e no histórico completo antes da publicação, em ambiente autorizado para instalar/obter essas ferramentas.
- Consultar auditoria de vulnerabilidades e metadados de licença das dependências Python, incluindo o conjunto OCR.
- Realizar aceite visual no desktop e confirmar o fluxo exportado no Obsidian, conforme limitações e registros de validação existentes.
- Não há decisão de licença pendente: AGPL-3.0-only foi confirmada. A publicação em si permanece fora do escopo executado.

## Checklist de publicação

- [x] Histórico Git avaliado por caminhos de PDF e busca direcionada de padrões de segredo.
- [x] Arquivos locais e padrões de exclusão do `.gitignore` revisados.
- [x] Estrutura organizada revisada; nenhuma remoção ou refatoração necessária identificada.
- [x] README atualizado.
- [x] Licença existente confirmada e mantida conforme decisão do usuário.
- [ ] Segurança validada por scanner especializado.
- [ ] Credenciais e dados sensíveis confirmados como ausentes por varredura abrangente.
- [ ] Dependências avaliadas por auditoria de vulnerabilidades e licenças.
- [ ] Suíte de testes executada neste checkout.
- [ ] Aceite visual e de exportação no desktop/Obsidian concluído.
- [ ] Ausência de impedimentos críticos confirmada após as verificações pendentes.

## Parecer final

**APTO COM RESSALVAS.** As verificações direcionadas não encontraram credenciais conhecidas nem PDFs registrados no histórico local examinado, e não há achado crítico identificado. Ainda assim, a publicação deve aguardar a varredura especializada de segredos e dependências e a execução dos testes neste checkout. Nenhum push, mudança de visibilidade ou alteração do histórico foi realizado.
