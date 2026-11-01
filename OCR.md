# Reconhecimento local de texto, tabelas e fórmulas

O modo **OCR automático** complementa a extração direta nas novas conversões de PDFs escaneados ou mistos. O texto selecionável continua prioritário; o reconhecimento não reprocessa documentos já editados. Português e inglês usam o reconhecedor latino do RapidOCR.

## Preparação

A instalação completa tem duas etapas, ambas explícitas:

```bash
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/pdf-obsidian-prepare-ocr
```

Alternativa equivalente ao segundo comando:

```bash
.venv/bin/python -m pdf_obsidian.prepare_ocr
```

A preparação instala dependências de CPU em um ambiente separado e baixa os modelos oficiais. Não exige instalar Tesseract. Os arquivos ficam por padrão em `.venv/share/pdf-obsidian/ocr/`, fora do código-fonte e do pacote leve da interface. Há aproximadamente 1,1 GiB de modelos e 1,7 GiB de ambiente instalado nesta configuração; tamanho do download e do disco podem variar com a plataforma.

Para escolher outra pasta, use `--directory CAMINHO` na preparação e defina `PDF_OBSIDIAN_OCR_DIR=CAMINHO` ao abrir a aplicação. A pasta deve conter o ambiente e o manifesto produzidos pelo preparador. Reinicie uma janela já aberta depois de preparar os modelos.

Verificação sem rede:

```bash
.venv/bin/pdf-obsidian-prepare-ocr --verify
```

A preparação também aceita um repositório local completo de wheels e uma pasta de modelos previamente preparada:

```bash
.venv/bin/pdf-obsidian-prepare-ocr --offline \
  --wheelhouse /caminho/wheels \
  --model-source /caminho/modelos-preparados
```

`--offline` exige ambos os caminhos e usa `pip --no-index`. Não é um instalador portátil: a preparação utiliza o Python do ambiente da aplicação. Dependências e hashes aprovados de wheels estão fixados em `ocr_requirements.lock` (pins legíveis em `ocr_requirements.txt`); a instalação exige hashes e somente binários, inclusive no modo offline. Commits dos modelos estão em `ocr_models.json`; SHA-256 esperados, inclusive do RapidOCR, em `ocr_trusted_models.json`, distribuído com a aplicação. O manifesto local deve coincidir com esse conjunto e todos os arquivos são verificados antes do uso. Alterar pesos e reescrever o manifesto local não autoriza um modelo diferente. A preparação deve usar uma pasta limpa se houver arquivos de modelos extras. Os hashes pressupõem confiança na distribuição da aplicação e não são assinatura contra um invasor com controle do mesmo usuário. Licenças Apache-2.0 e CDLA-Permissive-2.0 acompanham os modelos. Pesos não entram em commits.

## Uso

- Na importação, na preparação do lote ou em **Opções → OCR automático nas próximas conversões**, mantenha **OCR automático · texto, tabelas e fórmulas** marcado. Desmarcar mantém a conversão anterior, sem carregar modelos.
- O estado informa se o OCR está preparado. Sem recursos, a conversão continua com extração direta e imagens, registrando avisos nas páginas candidatas.
- A escolha vale para o trabalho iniciado e para todos os documentos daquele lote. Não pode ser alterada durante o processamento e não modifica opções de documentos já convertidos.
- O progresso informa a página e a etapa real. A primeira página envolve carregar os modelos e pode ser sensivelmente mais lenta que as seguintes.
- Confira os avisos por página antes de salvar no vault. Resultados automáticos podem conter erros; as imagens são mantidas para comparação e remoção manual pela prévia.

## Composição e limites

**Texto:** análise visual só nas páginas com regiões candidatas — imagens com detalhes, tabelas ou fórmulas detectadas — excluindo os elementos já identificados pelo filtro de margens autorizado. Páginas apenas com texto nativo e imagens uniformes não carregam o motor. A sondagem de imagens uniformes apenas evita OCR desnecessário: não remove arquivos ou incorporações.

Texto reconhecido é aceito somente dentro das regiões candidatas. Coincidências com o texto nativo são eliminadas. Sobreposição com conteúdo diferente ou parcialmente coincidente gera aviso e preserva a extração direta; não há substituição silenciosa. Reconhecimento não recupera automaticamente a fonte, o negrito ou o itálico original.

**Tabelas:** estruturas retangulares simples viram tabelas Markdown; células mescladas usam HTML restrito com `rowspan`/`colspan`. Texto nativo das células é aproveitado quando a associação geométrica é segura. Estruturas inconsistentes ou conflitantes ficam como imagem e geram aviso. Não há garantia de reconstrução fiel de toda tabela.

**Fórmulas:** regiões classificadas pelo modelo e linhas matemáticas explícitas podem gerar LaTeX em blocos `$$`. A validação básica rejeita saídas vazias, truncadas ou com delimitadores inválidos; não prova correção matemática. Na prévia Qt, o LaTeX pode aparecer como código; a imagem de referência continua disponível. A interpretação matemática final deve ser conferida no Obsidian.

**Imagens:** as regiões envolvidas em OCR permanecem, inclusive digitalizações de página inteira. Assim, a nota pode conter tanto a imagem quanto o conteúdo reconhecido. O filtro autorizado de margens continua limitado aos 10% superiores/inferiores, mesma identidade/posição, mínimo de três páginas e 70% do documento. OCR não autoriza nenhuma nova remoção de imagens.

Manuscritos, tradução, interpretação de gráficos e um novo renderizador matemático ficam fora desta etapa. Documentos com múltiplas colunas continuam exigindo conferência da ordem de leitura.

## Execução, recuperação e auditoria

Docling, RapidOCR/ONNX, TableFormer em modo rápido e CodeFormulaV2 executam em um subprocesso de CPU, separado da interface e do worker PDF. Há uma página em processamento por vez, com reutilização dos modelos durante o documento. O auxiliar aplica seccomp no kernel antes de carregar o motor: bloqueia criação de sockets IP, conexões inclusive Unix para serviços externos ao processo e inspeção de outros processos. Landlock limita leitura a bibliotecas do sistema, pacote da aplicação, recursos OCR e informações locais necessárias do kernel; escrita fica no workspace OCR, cache e `/dev/null`. Credenciais e variáveis arbitrárias do ambiente não são herdadas. Plugins externos e serviços remotos ficam desativados. Isso exige Linux x86_64/aarch64 com Landlock ABI 3+ habilitado (Linux 6.2+ normalmente) e `libseccomp.so.2`; falta de suporte interrompe o reconhecimento com preservação da conversão direta, sem fallback desprotegido.

O timeout é de 180 segundos por página e o orçamento do subprocesso e seus eventuais descendentes é de 4 GiB de memória residente. Falha de reconhecimento, recursos corrompidos, resposta inválida, timeout ou excesso de memória preservam a conversão direta e as imagens. Cancelar encerra o subprocesso, sem precisar encerrar o worker principal. No Linux, a morte inesperada do worker também encerra o auxiliar.

O worker PDF também bloqueia conexões no kernel. Um supervisor externo ao processo limita RSS do worker a 2 GiB, arquivos da sessão a 2 GiB e tempo por comando a uma hora (30 segundos para renderização). Há limite de CPU de 300 segundos por comando e de 256 MiB por arquivo escrito; rasterizações grandes são recusadas antes de alocar mais de 24 milhões de pixels. RSS e disco são monitorados periodicamente, podendo ter picos entre verificações; não equivalem a quotas de cgroup. Ao exceder o orçamento, o processamento para e o controlador preserva documentos concluídos e arquivos temporários até a confirmação de fechamento. Texto editado deve ser copiado/salvo antes de reabrir a aplicação; não há persistência automática de sessão. PDFs que exigem arquivos de saída acima do limite podem ser recusados. Os limites não modificam o original nem os filtros de imagens.

A prévia aceita apenas PNGs regulares dentro de `assets/`, sem symlinks, com até 64 MiB de dados e 24 milhões de pixels. URLs remotas, referências externas e arquivos especiais são recusados. O Markdown editável e exportado mantém seus links: essa restrição de visualização não é sanitização para todos os consumidores externos.

Arquivos de sondagem, páginas renderizadas e `ocr/runtime.log` ficam no workspace temporário da conversão para diagnóstico e recuperação durante a sessão. Não são anexos exportados. `conversao.json` recebe a seção opcional `recognition` com modo, idiomas, versões/commits, resultados por página, durações e pico observado. Essa auditoria participa da assinatura de publicação; repetição do mesmo resultado continua reutilizando a saída intacta sem sobrescrevê-la.

## Verificações

```bash
.venv/bin/python -m pytest -q
.venv/bin/python tools/benchmark_recognition.py --pages 20 --output /tmp/ocr-benchmark.json
.venv/bin/python tools/benchmark_quick.py --pages 100
```

Testes comuns usam um diretório de OCR vazio para não carregar modelos implicitamente; os testes específicos usam contratos e processos controláveis. O benchmark usa o worker real, gera PDFs próprios e exige modelos preparados. Use apenas PDFs sintéticos nos testes. Registros detalhados de validações anteriores são mantidos no checkout de desenvolvimento e não fazem parte da documentação pública.
