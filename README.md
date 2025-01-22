# WhatsApp Bulk Messenger

Uma aplicação web Flask para envio de mensagens em massa via WhatsApp usando a Evolution API.

## Funcionalidades

- ✅ Verificação de status da instância WhatsApp
- ✅ Validação de números WhatsApp
- ✅ Templates de mensagem personalizáveis
- ✅ Envio de mensagens com delay aleatório
- ✅ Interface moderna com Bootstrap 5
- ✅ Histórico de envios
- ✅ Sem necessidade de autenticação

## Configuração

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure as variáveis de ambiente:
- Copie o arquivo `.env.example` para `.env`
- Adicione sua chave da API Evolution no arquivo `.env`

3. Execute a aplicação:
```bash
python run.py
```

## Como Usar

1. Acesse a interface web (geralmente em `http://localhost:5000`)
2. Verifique se a instância do WhatsApp está ativa
3. Cole os números de telefone no formato internacional (ex: 5511999999999)
4. Valide os números para verificar quais têm WhatsApp
5. Gerencie os templates de mensagem
6. Configure o intervalo de delay desejado
7. Inicie o envio das mensagens

## Notas Importantes

- Os números devem estar no formato internacional sem caracteres especiais
- O delay mínimo entre mensagens é de 10 segundos
- As mensagens são selecionadas aleatoriamente dos templates disponíveis
- O histórico de envios é mantido apenas em memória (reiniciar a aplicação limpa o histórico)

## Requisitos

- Python 3.8+
- Flask
- Requests
- Python-dotenv
- Evolution API Key
