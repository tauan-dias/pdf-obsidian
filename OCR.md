# Reconhecimento local de texto, tabelas e fórmulas

O modo **OCR automático** complementa a extração direta nas novas conversões de PDFs escaneados ou mistos. O texto selecionável continua prioritário; o reconhecimento não reprocessa documentos já editados. Português e inglês usam o reconhecedor latino do RapidOCR.

## Preparação

A instalação completa tem duas etapas, ambas explícitas:

```bash
.venv/bin/python -m pip install -e '.[dev]'
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

`--offline` exige ambos os caminhos e usa `pip --no-index`. Não é um instalador portátil: a preparação utiliza o Python do ambiente da aplicação. Dependências estão fixadas em `ocr_requirements.txt`; commits dos modelos em `ocr_models.json`; cada arquivo preparado recebe SHA-256 no manifesto local. Licenças Apache-2.0 e CDLA-Permissive-2.0 acompanham os modelos. Pesos não entram em commits.

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

Docling, RapidOCR/ONNX, TableFormer em modo rápido e CodeFormulaV2 executam em um subprocesso de CPU, separado da interface e do worker PDF. Há uma página em processamento por vez, com reutilização dos modelos durante o documento. O motor bloqueia conexões IP e usa somente arquivos locais; plugins externos e serviços remotos ficam desativados.

O timeout é de 180 segundos por página e o orçamento do subprocesso é de 4 GiB de memória residente. Falha de reconhecimento, recursos corrompidos, resposta inválida, timeout ou excesso de memória preservam a conversão direta e as imagens. Cancelar encerra o subprocesso, sem precisar encerrar o worker principal. No Linux, a morte inesperada do worker também encerra o auxiliar.

Arquivos de sondagem, páginas renderizadas e `ocr/runtime.log` ficam no workspace temporário da conversão para diagnóstico e recuperação durante a sessão. Não são anexos exportados. `conversao.json` recebe a seção opcional `recognition` com modo, idiomas, versões/commits, resultados por página, durações e pico observado. Essa auditoria participa da assinatura de publicação; repetição do mesmo resultado continua reutilizando a saída intacta sem sobrescrevê-la.

## Verificações

```bash
.venv/bin/python -m pytest -q
.venv/bin/python tools/benchmark_recognition.py --pages 20 --output /tmp/ocr-benchmark.json
.venv/bin/python tools/benchmark_quick.py --pages 100
```

Testes comuns usam um diretório de OCR vazio para não carregar modelos implicitamente; os testes específicos usam contratos e processos controláveis. O benchmark usa o worker real, gera PDFs próprios e exige modelos preparados. Nunca usar o PDF pessoal da raiz nem um vault real. Evidências de qualidade, memória, cancelamento e Python 3.12/3.14 estão em `VALIDATION.md`.
