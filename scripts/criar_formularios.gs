/**
 * Script para gerar automaticamente os 2 formulários do sistema de OEE:
 *   - "Registro de Produção" (preenchido 1x por turno/máquina)
 *   - "Registro de Paradas"  (preenchido a cada evento de parada)
 *
 * COMO USAR:
 * 1. Acesse https://script.google.com/home/my  → "Novo projeto"
 * 2. Apague o conteúdo padrão e cole este arquivo inteiro
 * 3. Ajuste os arrays MAQUINAS e MOTIVOS_PARADA abaixo com os nomes reais
 * 4. No topo, selecione a função "criarFormularios" e clique em ▶ Executar
 * 5. Na primeira execução, o Google vai pedir autorização (Forms, Sheets, Drive)
 * 6. Veja os links gerados em: Ver → Registros de execução (Ctrl+Enter)
 */

// ============================================================
// CONFIGURAÇÃO — AJUSTE AQUI
// ============================================================
const MAQUINAS = [
  "Torno CNC 01",
  "Fresadora 02",
  "Prensa Hidráulica 03",
  "Injetora 04",
];

const TURNOS = ["Manhã", "Tarde", "Noite"];

const MOTIVOS_PARADA = [
  "Falha elétrica",
  "Falha mecânica",
  "Troca de ferramenta",
  "Falta de material",
  "Ajuste de setup",
  "Manutenção preventiva",
  "Outro",
];

// ============================================================
// FUNÇÃO PRINCIPAL
// ============================================================
function criarFormularios() {
  const producao = criarFormularioProducao();
  const paradas = criarFormularioParadas();

  Logger.log("========== FORMULÁRIO DE PRODUÇÃO ==========");
  Logger.log("Link para preencher: " + producao.form.getPublishedUrl());
  Logger.log("Link para editar:    " + producao.form.getEditUrl());
  Logger.log("Planilha de respostas: " + producao.sheetUrl);

  Logger.log("========== FORMULÁRIO DE PARADAS ==========");
  Logger.log("Link para preencher: " + paradas.form.getPublishedUrl());
  Logger.log("Link para editar:    " + paradas.form.getEditUrl());
  Logger.log("Planilha de respostas: " + paradas.sheetUrl);

  Logger.log("========== IDs DAS PLANILHAS (usar no secrets.toml do Streamlit) ==========");
  Logger.log("producao_sheet_id = \"" + producao.sheetId + "\"");
  Logger.log("paradas_sheet_id  = \"" + paradas.sheetId + "\"");
}

// ============================================================
// FORMULÁRIO 1: REGISTRO DE PRODUÇÃO
// ============================================================
function criarFormularioProducao() {
  const form = FormApp.create("Registro de Produção - OEE")
    .setDescription(
      "Preencher 1 vez por turno, para cada máquina em operação."
    )
    .setCollectEmail(false);

  form.addDateItem().setTitle("Data").setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Turno")
    .setChoiceValues(TURNOS)
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Máquina")
    .setChoiceValues(MAQUINAS)
    .setRequired(true);

  form.addTextItem().setTitle("Operador responsável").setRequired(true);

  const validacaoNumeroPositivo = FormApp.createTextValidation()
    .setHelpText("Digite apenas números (use ponto para decimais, ex: 12.5)")
    .requireNumberGreaterThanOrEqualTo(0)
    .build();

  form
    .addTextItem()
    .setTitle("Tempo Planejado de Produção (min)")
    .setHelpText(
      "Duração do turno já descontando paradas programadas (almoço, reuniões, manutenção preventiva agendada)."
    )
    .setValidation(validacaoNumeroPositivo)
    .setRequired(true);

  form
    .addTextItem()
    .setTitle("Tempo de Ciclo Ideal (segundos/peça)")
    .setValidation(validacaoNumeroPositivo)
    .setRequired(true);

  form
    .addTextItem()
    .setTitle("Quantidade Produzida (peças)")
    .setValidation(validacaoNumeroPositivo)
    .setRequired(true);

  form
    .addTextItem()
    .setTitle("Quantidade Refugada (peças)")
    .setValidation(validacaoNumeroPositivo)
    .setRequired(true);

  form.addParagraphTextItem().setTitle("Observações").setRequired(false);

  const sheet = SpreadsheetApp.create("Respostas - Registro de Produção (OEE)");
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  return { form: form, sheetId: sheet.getId(), sheetUrl: sheet.getUrl() };
}

// ============================================================
// FORMULÁRIO 2: REGISTRO DE PARADAS
// ============================================================
function criarFormularioParadas() {
  const form = FormApp.create("Registro de Paradas - OEE")
    .setDescription("Preencher pela equipe de manutenção a cada parada ocorrida.")
    .setCollectEmail(false);

  form.addDateItem().setTitle("Data").setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Turno")
    .setChoiceValues(TURNOS)
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Máquina")
    .setChoiceValues(MAQUINAS)
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Tipo de Parada")
    .setChoiceValues(["Planejada", "Não Planejada"])
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle("Motivo da Parada")
    .setChoiceValues(MOTIVOS_PARADA)
    .setRequired(true);

  const validacaoNumeroPositivo = FormApp.createTextValidation()
    .setHelpText("Digite apenas números (use ponto para decimais, ex: 12.5)")
    .requireNumberGreaterThanOrEqualTo(0)
    .build();

  form
    .addTextItem()
    .setTitle("Duração da Parada (min)")
    .setValidation(validacaoNumeroPositivo)
    .setRequired(true);

  form.addTextItem().setTitle("Técnico responsável").setRequired(true);

  form.addParagraphTextItem().setTitle("Observações").setRequired(false);

  const sheet = SpreadsheetApp.create("Respostas - Registro de Paradas (OEE)");
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  return { form: form, sheetId: sheet.getId(), sheetUrl: sheet.getUrl() };
}
