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
                  name TEXT NOT NULL,
                  content TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS message_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  instance_name TEXT NOT NULL,
                  number TEXT NOT NULL,
                  message TEXT NOT NULL,
                  status TEXT NOT NULL,
                  error TEXT,
                  sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  delay INTEGER,
                  total_time INTEGER)''')
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
    templates = [{'id': row[0], 'name': row[1], 'content': row[2]} for row in c.fetchall()]
    
    # Busca histórico de envios (últimos 50)
    c.execute('''SELECT instance_name, number, message, status, error, sent_date, delay, total_time 
                 FROM message_history 
                 ORDER BY sent_date DESC LIMIT 50''')
    history = [{'instance_name': row[0],
                'number': row[1],
                'message': row[2],
                'status': row[3],
                'error': row[4],
                'sent_date': row[5],
                'delay': row[6],
                'total_time': row[7]} for row in c.fetchall()]
    
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
            # Remove espaços, pontos e outros caracteres especiais
            number = number.replace('.', '').replace('+', '').replace('-', '').replace(' ', '')
            # Remove qualquer caractere que não seja dígito
            cleaned = ''.join(filter(str.isdigit, number))
            # Adiciona o código do país se não estiver presente
            if len(cleaned) <= 13 and not cleaned.startswith('55'):
                cleaned = '55' + cleaned
            cleaned_numbers.append(cleaned)

        # Remove números duplicados mantendo a ordem
        cleaned_numbers = list(dict.fromkeys(cleaned_numbers))

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
            templates = [{'id': row[0], 'name': row[1], 'content': row[2]} for row in c.fetchall()]
            return jsonify(templates)
            
        elif request.method == 'POST':
            data = request.json
            name = data.get('name')
            content = data.get('content')
            if not name or not content:
                return jsonify({'error': 'Nome e conteúdo são obrigatórios'}), 400
                
            c.execute('INSERT INTO message_templates (name, content) VALUES (?, ?)', (name, content))
            template_id = c.lastrowid
            conn.commit()
            
            return jsonify({'id': template_id, 'name': name, 'content': content})
            
        elif request.method == 'PUT':
            data = request.json
            template_id = data.get('id')
            name = data.get('name')
            content = data.get('content')
            
            if not template_id or not name or not content:
                return jsonify({'error': 'ID, nome e conteúdo são obrigatórios'}), 400
                
            c.execute('UPDATE message_templates SET name = ?, content = ? WHERE id = ?', 
                     (name, content, template_id))
            conn.commit()
            
            return jsonify({'id': template_id, 'name': name, 'content': content})
            
        elif request.method == 'DELETE':
            data = request.json
            template_id = data.get('id')
            
            if not template_id:
                return jsonify({'error': 'ID do template é obrigatório'}), 400
                
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

@app.route('/get-history')
def get_history():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Busca histórico de envios (ordenado por data mais recente)
        c.execute('''SELECT instance_name, number, message, status, error, sent_date, delay, total_time 
                     FROM message_history 
                     ORDER BY sent_date DESC''')
        
        history = [{'instance_name': row[0],
                    'number': row[1],
                    'message': row[2],
                    'status': row[3],
                    'error': row[4],
                    'sent_date': row[5],
                    'delay': row[6],
                    'total_time': row[7]} for row in c.fetchall()]
        
        return jsonify(history)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        conn.close()

@app.route('/add-template', methods=['POST'])
def add_template():
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'content' not in data:
            return jsonify({'error': 'Nome e conteúdo são obrigatórios'}), 400
            
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('INSERT INTO message_templates (name, content) VALUES (?, ?)',
                 (data['name'], data['content']))
        conn.commit()
        
        template_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'id': template_id,
            'message': 'Template criado com sucesso'
        })
        
    except Exception as e:
        print(f"Erro ao adicionar template: {str(e)}")
        return jsonify({'error': 'Erro ao salvar template'}), 500

@app.route('/update-template/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'content' not in data:
            return jsonify({'error': 'Nome e conteúdo são obrigatórios'}), 400
            
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('UPDATE message_templates SET name = ?, content = ? WHERE id = ?',
                 (data['name'], data['content'], template_id))
        conn.commit()
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Template não encontrado'}), 404
            
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Template atualizado com sucesso'
        })
        
    except Exception as e:
        print(f"Erro ao atualizar template: {str(e)}")
        return jsonify({'error': 'Erro ao atualizar template'}), 500

@app.route('/delete-template/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('DELETE FROM message_templates WHERE id = ?', (template_id,))
        conn.commit()
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Template não encontrado'}), 404
            
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Template excluído com sucesso'
        })
        
    except Exception as e:
        print(f"Erro ao excluir template: {str(e)}")
        return jsonify({'error': 'Erro ao excluir template'}), 500

@app.route('/get-template/<int:template_id>', methods=['GET'])
def get_template(template_id):
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT name, content FROM message_templates WHERE id = ?', (template_id,))
        template = c.fetchone()
        
        if not template:
            conn.close()
            return jsonify({'error': 'Template não encontrado'}), 404
            
        conn.close()
        return jsonify({
            'name': template[0],
            'content': template[1]
        })
        
    except Exception as e:
        print(f"Erro ao buscar template: {str(e)}")
        return jsonify({'error': 'Erro ao buscar template'}), 500

@app.route('/list-templates', methods=['GET'])
def list_templates():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT id, name, content FROM message_templates ORDER BY id DESC')
        templates = [{
            'id': row[0],
            'name': row[1],
            'content': row[2]
        } for row in c.fetchall()]
        
        conn.close()
        return jsonify(templates)
        
    except Exception as e:
        print(f"Erro ao listar templates: {str(e)}")
        return jsonify({'error': 'Erro ao listar templates'}), 500

def send_messages_task(numbers, message, instance, delay_range):
    total = len(numbers)
    current = 0
    success_count = 0
    error_count = 0
    start_time = time.time()  # Marca o início do envio
    
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        for number in numbers:
            try:
                # Prepara o payload da mensagem
                payload = {
                    "number": number,
                    "options": {
                        "delay": delay_range[1] * 1000,  # Converte para milissegundos
                        "presence": "composing"
                    },
                    "textMessage": {
                        "text": message
                    }
                }
                
                print(f"Enviando mensagem para {number}. Payload: {payload}")  # Debug
                
                # Gera o delay aleatório
                delay = random.randint(delay_range[0], delay_range[1])
                
                # Envia a mensagem
                response = requests.post(
                    f'https://{SERVER_URL}/message/sendText/{instance}',
                    headers=HEADERS,
                    json=payload
                )
                
                print(f"Resposta da API: Status {response.status_code} - {response.text}")  # Debug
                
                # Calcula o tempo decorrido até agora
                elapsed_time = int(time.time() - start_time)
                
                # Considera tanto 200 quanto 201 como sucesso
                if response.status_code in [200, 201]:
                    result = response.json() if response.text else {}
                    status = 'success'
                    error = None
                    success_count += 1
                else:
                    status = 'error'
                    error = f"Erro {response.status_code}: {response.text}"
                    error_count += 1
                
                # Salva no histórico com o tempo total até o momento
                c.execute('''INSERT INTO message_history 
                            (instance_name, number, message, status, error, delay, total_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (instance, number, message, status, error, delay, elapsed_time))
                conn.commit()
                
                # Emite o resultado
                socketio.emit('send_result', {
                    'number': number,
                    'status': status,
                    'error': error,
                    'delay': delay,
                    'total_time': elapsed_time
                })

                # Incrementa o contador e emite o progresso após o envio
                current += 1
                socketio.emit('send_progress', {
                    'current': current,
                    'total': total,
                    'number': number,
                    'elapsed_time': elapsed_time
                })
                
                # Aguarda o delay para o próximo envio
                time.sleep(delay)
                
            except Exception as e:
                error_msg = str(e)
                print(f"Erro ao enviar mensagem para {number}: {error_msg}")  # Debug
                
                # Calcula o tempo decorrido mesmo em caso de erro
                elapsed_time = int(time.time() - start_time)
                error_count += 1
                
                # Salva o erro no histórico com o tempo total
                c.execute('''INSERT INTO message_history 
                            (instance_name, number, message, status, error, delay, total_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (instance, number, message, 'error', error_msg, delay, elapsed_time))
                conn.commit()
                
                # Emite o erro
                socketio.emit('send_error', {
                    'number': number,
                    'error': error_msg,
                    'total_time': elapsed_time
                })

                # Incrementa o contador e emite o progresso mesmo em caso de erro
                current += 1
                socketio.emit('send_progress', {
                    'current': current,
                    'total': total,
                    'number': number,
                    'elapsed_time': elapsed_time
                })
                
                # Aguarda o delay mesmo em caso de erro
                time.sleep(delay)
        
        # Calcula o tempo total gasto
        total_time = int(time.time() - start_time)
        
        # Calcula a média de tempo por mensagem (em segundos)
        avg_time = total_time / total if total > 0 else 0
        
        # Emite conclusão com estatísticas detalhadas
        socketio.emit('send_complete', {
            'total_sent': current,
            'success_count': success_count,
            'error_count': error_count,
            'total_time': total_time,
            'avg_time': round(avg_time, 1),
            'success_rate': round((success_count / total) * 100 if total > 0 else 0, 1)
        })
        
    finally:
        conn.close()

if __name__ == '__main__':
    socketio.run(app, debug=True)