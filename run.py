from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import requests
import json
import os
import time
import random
import sqlite3
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

# Configurações da API
SERVER_URL = os.getenv('SERVER_URL')
API_KEY = os.getenv('API_KEY')
HEADERS = {
    'Content-Type': 'application/json',
    'apikey': API_KEY
}

# Configuração do banco de dados
DATABASE = 'messages.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS message_templates
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS message_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  instance_name TEXT NOT NULL,
                  number TEXT NOT NULL,
                  message TEXT NOT NULL,
                  status TEXT NOT NULL,
                  error TEXT,
                  sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  delay INTEGER)''')
    conn.commit()
    conn.close()

# Inicializa o banco de dados
init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Busca templates
    c.execute('SELECT * FROM message_templates')
    templates = [{'id': row[0], 'content': row[1]} for row in c.fetchall()]
    
    # Busca histórico de envios (últimos 50)
    c.execute('''SELECT instance_name, number, message, status, error, sent_date, delay 
                 FROM message_history 
                 ORDER BY sent_date DESC LIMIT 50''')
    history = [{'instance_name': row[0],
                'number': row[1],
                'message': row[2],
                'status': row[3],
                'error': row[4],
                'sent_date': row[5],
                'delay': row[6]} for row in c.fetchall()]
    
    conn.close()
    
    return render_template('dashboard.html', 
                         message_templates=templates,
                         history=history)

@app.route('/fetch-instances')
def fetch_instances():
    try:
        response = requests.get(
            f'https://{SERVER_URL}/instance/fetchInstances',
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            # Garante que o retorno seja sempre uma lista
            if not isinstance(data, list):
                data = [data] if data else []
            return jsonify(data)
        else:
            return jsonify({
                'error': f'Erro ao buscar instâncias: {response.text}',
                'status_code': response.status_code
            })
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar instâncias: {str(e)}'})

@app.route('/check-instance-status')
def check_instance_status():
    instance = request.args.get('instance')
    if not instance:
        return jsonify({'error': 'Instance name is required'})
    
    try:
        # Primeiro busca as informações da instância
        response = requests.get(
            f'https://{SERVER_URL}/instance/fetchInstances',
            headers=HEADERS
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'error': f'Erro ao buscar informações da instância: {response.text}'
            })
        
        instances_data = response.json()
        if not isinstance(instances_data, list):
            instances_data = [instances_data] if instances_data else []
        
        # Procura a instância específica
        instance_info = None
        for item in instances_data:
            if item.get('instance', {}).get('instanceName') == instance:
                instance_info = item.get('instance', {})
                break
        
        if not instance_info:
            return jsonify({
                'status': 'error',
                'error': 'Instância não encontrada'
            })
        
        # Agora verifica o estado da conexão
        state_response = requests.get(
            f'https://{SERVER_URL}/instance/connectionState/{instance}',
            headers=HEADERS
        )
        
        if state_response.status_code != 200:
            return jsonify({
                'status': 'error',
                'error': f'Erro ao verificar estado da conexão: {state_response.text}'
            })
        
        state_data = state_response.json()
        
        # Determina o status real da instância
        instance_status = instance_info.get('status', 'unknown').upper()
        connection_state = state_data.get('state', 'unknown').upper()
        
        # Se a instância está com status 'open', consideramos que está conectada
        if instance_status == 'OPEN':
            final_status = 'CONNECTED'
        # Se está com status 'connecting', está tentando conectar
        elif instance_status == 'CONNECTING':
            final_status = 'CONNECTING'
        # Se o estado da conexão indica que está conectada
        elif connection_state == 'CONNECTED':
            final_status = 'CONNECTED'
        # Se está em qualquer outro estado, consideramos desconectada
        else:
            final_status = 'DISCONNECTED'
        
        # Retorna todas as informações relevantes
        return jsonify({
            'status': final_status,
            'details': {
                'owner': instance_info.get('owner'),
                'profileName': instance_info.get('name'),
                'connectionState': connection_state,
                'instanceStatus': instance_status
            }
        })
            
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/validate-numbers', methods=['POST'])
def validate_numbers():
    data = request.json
    numbers = data.get('numbers', [])
    instance = data.get('instance')
    
    if not numbers:
        return jsonify({'error': 'Nenhum número fornecido'})
    if not instance:
        return jsonify({'error': 'É necessário selecionar uma instância'})
    
    try:
        # Remove espaços e caracteres especiais dos números
        cleaned_numbers = []
        for number in numbers:
            # Remove espaços e caracteres especiais
            cleaned = ''.join(filter(str.isdigit, number))
            # Adiciona o código do país se não estiver presente
            if len(cleaned) <= 13 and not cleaned.startswith('55'):
                cleaned = '55' + cleaned
            cleaned_numbers.append(cleaned)

        # Monta o payload para a API
        payload = {
            'numbers': cleaned_numbers
        }
        
        print(f"Validando números: {payload}")  # Debug
        
        # Faz a requisição para validar os números
        response = requests.post(
            f'https://{SERVER_URL}/chat/whatsappNumbers/{instance}',
            headers=HEADERS,
            json=payload
        )
        
        print(f"Resposta da API: {response.text}")  # Debug
        
        if response.status_code != 200:
            return jsonify({
                'error': f'Erro ao validar números: {response.text}'
            })
        
        # Processa a resposta
        validation_data = response.json()
        results = []
        
        # A API retorna uma lista de objetos, cada um com os detalhes do número
        for number_info in validation_data:
            number = number_info.get('number', '')
            exists = number_info.get('exists', False)
            jid = number_info.get('jid', '')
            
            results.append({
                'number': number,
                'valid': exists,
                'jid': jid,
                'error': None if exists else 'Número não existe no WhatsApp'
            })
        
        # Retorna os resultados
        return jsonify({
            'results': results,
            'summary': {
                'total': len(results),
                'valid': sum(1 for r in results if r['valid']),
                'invalid': sum(1 for r in results if not r['valid'])
            }
        })
        
    except Exception as e:
        print(f"Erro ao validar números: {str(e)}")  # Debug
        import traceback
        traceback.print_exc()  # Imprime o stack trace completo
        return jsonify({'error': f'Erro ao validar números: {str(e)}'})

@app.route('/message-templates', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_templates():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        if request.method == 'GET':
            c.execute('SELECT * FROM message_templates')
            templates = [{'id': row[0], 'content': row[1]} for row in c.fetchall()]
            return jsonify(templates)
            
        elif request.method == 'POST':
            data = request.json
            content = data.get('content')
            if not content:
                return jsonify({'error': 'Template content is required'}), 400
                
            c.execute('INSERT INTO message_templates (content) VALUES (?)', (content,))
            template_id = c.lastrowid
            conn.commit()
            
            return jsonify({'id': template_id, 'content': content})
            
        elif request.method == 'PUT':
            data = request.json
            template_id = data.get('id')
            content = data.get('content')
            
            if not template_id or not content:
                return jsonify({'error': 'Template ID and content are required'}), 400
                
            c.execute('UPDATE message_templates SET content = ? WHERE id = ?', 
                     (content, template_id))
            conn.commit()
            
            return jsonify({'id': template_id, 'content': content})
            
        elif request.method == 'DELETE':
            data = request.json
            template_id = data.get('id')
            
            if not template_id:
                return jsonify({'error': 'Template ID is required'}), 400
                
            c.execute('DELETE FROM message_templates WHERE id = ?', (template_id,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        conn.close()

@app.route('/send-messages', methods=['POST'])
def send_messages():
    data = request.json
    numbers = data.get('numbers', [])
    template_id = data.get('template_id')
    delay_range = data.get('delay_range', [10, 30])
    instance = data.get('instance')
    
    if not all([numbers, template_id, instance]):
        return jsonify({'error': 'Missing required parameters'}), 400
        
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Busca o template
        c.execute('SELECT content FROM message_templates WHERE id = ?', (template_id,))
        template = c.fetchone()
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
            
        message = template[0]
        
        # Inicia o envio em background
        socketio.start_background_task(
            send_messages_task,
            numbers=numbers,
            message=message,
            instance=instance,
            delay_range=delay_range
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        conn.close()

@app.route('/clear-history', methods=['POST'])
def clear_history():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Limpa a tabela de histórico
        c.execute('DELETE FROM message_history')
        conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
        
    finally:
        conn.close()

def send_messages_task(numbers, message, instance, delay_range):
    total = len(numbers)
    current = 0
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        for number in numbers:
            current += 1
            delay = random.randint(delay_range[0], delay_range[1])
            
            socketio.emit('send_progress', {
                'current': current,
                'total': total,
                'number': number
            })
            
            try:
                # Prepara o payload da mensagem
                payload = {
                    "number": number,
                    "options": {
                        "delay": delay * 1000,  # Converte para milissegundos
                        "presence": "composing"
                    },
                    "textMessage": {
                        "text": message
                    }
                }
                
                print(f"Enviando mensagem para {number}. Payload: {payload}")  # Debug
                
                # Envia a mensagem
                response = requests.post(
                    f'https://{SERVER_URL}/message/sendText/{instance}',
                    headers=HEADERS,
                    json=payload
                )
                
                print(f"Resposta da API: Status {response.status_code} - {response.text}")  # Debug
                
                # Considera tanto 200 quanto 201 como sucesso
                if response.status_code in [200, 201]:
                    result = response.json() if response.text else {}
                    status = 'success'
                    error = None
                else:
                    status = 'error'
                    error = f"Erro {response.status_code}: {response.text}"
                
                # Salva no histórico
                c.execute('''INSERT INTO message_history 
                            (instance_name, number, message, status, error, delay)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (instance, number, message, status, error, delay))
                conn.commit()
                
                # Emite o resultado
                socketio.emit('send_result', {
                    'number': number,
                    'status': status,
                    'error': error,
                    'delay': delay
                })
                
            except Exception as e:
                error_msg = str(e)
                print(f"Erro ao enviar mensagem para {number}: {error_msg}")  # Debug
                
                # Salva o erro no histórico
                c.execute('''INSERT INTO message_history 
                            (instance_name, number, message, status, error, delay)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (instance, number, message, 'error', error_msg, delay))
                conn.commit()
                
                # Emite o erro
                socketio.emit('send_error', {
                    'number': number,
                    'error': error_msg
                })
            
            # Aguarda o delay
            time.sleep(delay)
        
        # Emite conclusão
        socketio.emit('send_complete', {
            'total_sent': total
        })
        
    finally:
        conn.close()

if __name__ == '__main__':
    socketio.run(app, debug=True)