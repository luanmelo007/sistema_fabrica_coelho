# Sistema de Acompanhamento de Manutenção e OEE

Pipeline: **Google Forms → Google Sheets → App Python/Streamlit (dashboard de OEE)**

---

## 1. Visão geral da arquitetura

```
[Equipe de Manutenção]      [Equipe de Produção]
        │                          │
        ▼                          ▼
  Formulário "Paradas"     Formulário "Produção"
        │                          │
        ▼                          ▼
  Sheet "Paradas"           Sheet "Producao"
        │                          │
        └────────────┬─────────────┘
                      ▼
            app.py (Streamlit)
        lê as duas planilhas via
        Google Sheets API (gspread)
                      │
                      ▼
        Cálculo de OEE (Disponibilidade
        x Performance x Qualidade)
                      │
                      ▼
              Dashboard interativo
```

Uso **dois formulários** (e não um só) porque eles têm frequências e naturezas diferentes:
- **Produção** é preenchido **1x por turno/máquina** (dados agregados do turno).
- **Paradas** é preenchido **cada vez que uma parada ocorre** (pode haver várias por turno).

Isso evita formulário com lógica condicional complicada e facilita a modelagem dos dados.

---

## 2. Formulário 1 — "Registro de Produção" (preenchido pela equipe 1x/turno/máquina)

| Campo do Forms | Tipo | Vai para coluna |
|---|---|---|
| Data | Data | `data` |
| Turno | Múltipla escolha (Manhã/Tarde/Noite) | `turno` |
| Máquina | Múltipla escolha (lista fixa das máquinas) | `maquina` |
| Operador responsável | Texto curto | `operador` |
| Tempo Planejado de Produção (min) | Número | `tempo_planejado_min` |
| Tempo de Ciclo Ideal (segundos/peça) | Número | `tempo_ciclo_ideal_seg` |
| Quantidade Produzida (peças) | Número | `qtd_produzida` |
| Quantidade Refugada (peças) | Número | `qtd_refugada` |
| Observações | Parágrafo | `obs_producao` |

> **Tempo Planejado de Produção** = duração do turno já descontando paradas *programadas* (almoço, reuniões, manutenção preventiva agendada). Isso é o "Planned Production Time" clássico do OEE.

O Google Forms cria automaticamente a coluna `Carimbo de data/hora`; não precisa mexer nela.

---

## 3. Formulário 2 — "Registro de Paradas" (preenchido pela manutenção a cada parada)

| Campo do Forms | Tipo | Vai para coluna |
|---|---|---|
| Data | Data | `data` |
| Turno | Múltipla escolha (Manhã/Tarde/Noite) | `turno` |
| Máquina | Múltipla escolha (mesma lista do Form 1) | `maquina` |
| Tipo de Parada | Múltipla escolha: Planejada / Não Planejada | `tipo_parada` |
| Motivo da Parada | Múltipla escolha (ex: Falha elétrica, Falha mecânica, Troca de ferramenta, Falta de material, Ajuste de setup, Manutenção preventiva, Outro) | `motivo` |
| Duração da Parada (min) | Número | `duracao_min` |
| Técnico responsável | Texto curto | `tecnico` |
| Observações | Parágrafo | `obs_parada` |

Dica: no Google Forms, use **validação de resposta** nos campos numéricos (`>= 0`) para evitar entradas erradas de digitação.

---

## 4. Onde os dados caem

Cada formulário, na aba **Respostas → conectar ao Sheets**, gera automaticamente uma planilha Google Sheets. Você terá então **2 planilhas** (ou 2 abas dentro da mesma, se preferir juntar manualmente depois de criar as duas via Forms).

Anote os IDs das planilhas (o trecho da URL entre `/d/` e `/edit`), você vai precisar deles no app.

---

## 5. Autenticação do app com o Google Sheets

Caminho recomendado: **Service Account** (não expõe sua conta pessoal, funciona em servidor).

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto (ou use um existente).
2. Ative a **Google Sheets API** e a **Google Drive API**.
3. Crie uma **Service Account** e gere uma chave JSON.
4. Compartilhe as duas planilhas (Produção e Paradas) com o e-mail da service account (ex: `oee-app@seu-projeto.iam.gserviceaccount.com`), dando permissão de **Leitor**.
5. No Streamlit, salve as credenciais em `.streamlit/secrets.toml` (não sobe pro Git):

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "oee-app@seu-projeto.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"

[sheets]
producao_sheet_id = "COLE_O_ID_DA_PLANILHA_DE_PRODUCAO"
paradas_sheet_id  = "COLE_O_ID_DA_PLANILHA_DE_PARADAS"
```

Se você for rodar isso no Hostinger VPS (como o resto da sua infra), monte o `secrets.toml` como um arquivo de config separado e faça o volume mount no container, em vez de deixá-lo na imagem Docker.

---

## 6. Fórmulas de OEE usadas no app

Para cada combinação (Data, Turno, Máquina):

- **Tempo Parada Não Planejada** = soma de `duracao_min` em Paradas onde `tipo_parada = "Não Planejada"`
- **Tempo Operacional** = `tempo_planejado_min` − Tempo Parada Não Planejada
- **Disponibilidade** = Tempo Operacional / `tempo_planejado_min`
- **Performance** = (`qtd_produzida` × `tempo_ciclo_ideal_seg` / 60) / Tempo Operacional
- **Qualidade** = (`qtd_produzida` − `qtd_refugada`) / `qtd_produzida`
- **OEE** = Disponibilidade × Performance × Qualidade

Paradas *planejadas* não entram na conta de indisponibilidade (elas já foram descontadas no `tempo_planejado_min` do turno), mas aparecem no dashboard separadamente para você acompanhar o quanto elas consomem.

---

## 7. Rodando localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sem credenciais configuradas, o app sobe em **modo demonstração** com dados sintéticos, para você validar o layout antes de plugar nas planilhas reais.
